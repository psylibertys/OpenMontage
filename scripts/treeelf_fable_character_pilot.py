#!/usr/bin/env python3
"""Prepare and run the TreeElf fable actress selection batch.

CPU preparation writes the approved creative contract, source snapshots,
three blind candidate prompts, the later consistency-test matrix, and the
AutoDL retention contract. GPU execution is deliberately phase-gated: the
first batch generates exactly A01-A03 and stops for human selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.checkpoint import init_project, write_checkpoint
from lib.paths import PROJECTS_DIR
from schemas.artifacts import validate_artifact
from tools.graphics.comfyui_image import ComfyUIImage

from scripts.treeelf_philosophy_brand_pilot import ensure_gpu_preflight


DEFAULT_CONFIG = (
    REPO_ROOT
    / "workflow_configs"
    / "zh-philosophy-video"
    / "treeelf-fable-actress-pilot.json"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_dir(config: dict[str, Any], projects_dir: Path = PROJECTS_DIR) -> Path:
    return projects_dir / str(config["project_id"])


def candidate_prompt(config: dict[str, Any], candidate: dict[str, Any]) -> str:
    return f"{config['candidate_selection']['shared_prompt']} {candidate['identity_delta']}"


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "project_id",
        "title",
        "pipeline",
        "profile",
        "aspect_preset",
        "render_runtime",
        "composition_mode",
        "retention_policy",
        "source_scripts",
        "character_bible",
        "candidate_selection",
        "consistency_tests",
        "motion_sample",
        "gpu_policy",
    ]
    for key in required:
        if not config.get(key):
            errors.append(f"missing:{key}")

    if config.get("pipeline") != "animated-explainer":
        errors.append("pipeline must be animated-explainer")
    if config.get("profile") != "tiktok" or config.get("aspect_preset") != "portrait_9_16":
        errors.append("profile/aspect must lock vertical 9:16")
    if config.get("render_runtime") != "remotion":
        errors.append("render_runtime must be remotion")
    if config.get("composition_mode") != "atelier":
        errors.append("composition_mode must be atelier")

    sources = config.get("source_scripts", [])
    if len(sources) != 3:
        errors.append("source_scripts must contain exactly three test fables")
    for source in sources:
        if not Path(source).is_file():
            errors.append(f"missing source script:{source}")

    bible = config.get("character_bible", {})
    identity = str(bible.get("identity", ""))
    if "女性" not in identity:
        errors.append("character_bible.identity must explicitly state 女性")
    forbidden = " ".join(bible.get("forbidden_drift", []))
    for phrase in ("眼下阴影", "疲惫", "男性化"):
        if phrase not in forbidden:
            errors.append(f"character_bible.forbidden_drift must include:{phrase}")

    selection = config.get("candidate_selection", {})
    if selection.get("workflow_template") != "krea2_low_vram":
        errors.append("candidate workflow must be krea2_low_vram")
    candidates = selection.get("candidates", [])
    if [item.get("id") for item in candidates] != ["A01", "A02", "A03"]:
        errors.append("candidate ids must be exactly A01, A02, A03")
    if len({item.get("seed") for item in candidates}) != 3:
        errors.append("candidate seeds must be unique")
    if not selection.get("shared_prompt"):
        errors.append("candidate_selection.shared_prompt is required")
    if any(not item.get("identity_delta") for item in candidates):
        errors.append("every candidate requires identity_delta")

    tests = config.get("consistency_tests", [])
    if [item.get("id") for item in tests] != ["T01", "T02", "T03"]:
        errors.append("consistency test ids must be exactly T01, T02, T03")

    gpu = config.get("gpu_policy", {})
    if gpu.get("phase_one_assets") != 3 or not gpu.get("phase_one_only"):
        errors.append("GPU phase one must contain only three candidate assets")
    if gpu.get("automatic_follow_on_generation") is not False:
        errors.append("automatic follow-on generation must be false")
    if gpu.get("lora_allowed") is not False:
        errors.append("LoRA must remain disabled")

    policy = REPO_ROOT / str(config.get("retention_policy", ""))
    if not policy.is_file():
        errors.append(f"missing retention policy:{policy}")
    elif load_json(policy).get("project_id") != config.get("project_id"):
        errors.append("retention policy project_id mismatch")
    return errors


def visual_style_markdown(config: dict[str, Any]) -> str:
    return """---
name: "雨后青苔寓言电影绘本"
version: "1.0"
tags: ["poetic 2.5D", "storybook cinema", "Chinese fable", "portrait video"]
author: "TreeElf / OpenMontage"
source_url: ""
created: "2026-07-24"

style_prompt_short: >
  雨后安静下来的城市绘本：低饱和灰绿、柔和自然光、克制的成年女性表演，
  通过一个微小暖色变化让寓言世界松动一点。

style_prompt_full: >
  Poetic 2.5D illustrated cinema in vertical 9:16. Use rain-washed plaster gray #C9CCC4,
  muted moss green #66745D, warm paper ivory #EEE8D8 and charcoal #343735 as the stable
  world palette, with one restrained amber warmth #D7A45A appearing only after a truthful
  action. Preserve delicate paper grain, hand-painted edges, natural anatomy, soft cinematic
  depth and motivated window light. The recurring protagonist is an adult East Asian woman,
  age 25 to 32, with short naturally voluminous black curls, bright calm eyes, relaxed brows
  and a gentle optimistic presence. Keep emotions small and readable. Avoid exhausted or sickly
  styling, under-eye shadows, childish cuteness, fantasy elf traits, advertising smiles,
  glossy 3D plastic, neon spectacle, crowded typography and triumphant transformation endings.

colors:
  primary:
    - {name: "雨洗墙灰", hex: "#C9CCC4", role: "interiors, sky and quiet negative space"}
    - {name: "青苔灰绿", hex: "#66745D", role: "recurring signature in wardrobe or props"}
  accent:
    - {name: "微光琥珀", hex: "#D7A45A", role: "small warmth after the protagonist acts"}
  neutral:
    - {name: "纸张米白", hex: "#EEE8D8", role: "skin-adjacent light, cloth and subtitle support"}
    - {name: "炭笔深灰", hex: "#343735", role: "line work, deep objects and text outline"}

typography:
  display: {family: "Liyu Xingkai", weight: "regular", style: "short Chinese cover titles only"}
  body: {family: "system sans-serif", weight: "regular", style: "clean accessible subtitles"}
  caption: {family: "system sans-serif", weight: "medium", style: "white with restrained dark outline"}
  rules:
    - "Never ask an image model to render Chinese text"
    - "Keep story frames free of decorative typography"
    - "Use exact text only in Remotion"

layout:
  grid: "Portrait 9:16 with central character corridor and protected subtitle lower zone"
  alignment: "Asymmetric cinematic framing with generous breathing room"
  aspect_ratio: "9:16"
  notes:
    - "Keep face, hands and the active metaphor away from platform UI edges"
    - "Use one dominant symbolic object per shot"

motion:
  transitions: ["motivated soft cut", "object match cut", "light or rain veil transition"]
  animation_style: >
    Film-picturebook hybrid: a few real 1-5 second character or object motions surrounded by
    deterministic depth, light, particles and slow camera movement. Motion begins from story cause,
    never as decoration.
  pacing: "unhurried, intimate, with held frames before and after each small decision"
  audio_cues: ["quiet room tone", "subtle rain and object sounds", "music remains below narration"]

mood:
  keywords: ["柔和", "乐观", "清醒", "诗意", "克制"]
  era: "contemporary timeless"
  cultural_reference: "adult literary picturebook and restrained cinematic magical realism"
  avoid:
    - "fatigue, illness, under-eye shadows or permanent sadness"
    - "childlike mascot styling or fantasy elf costume"
    - "large inspirational smiles and complete miracle cures"
    - "generic stock-video polish or glossy plastic 3D"

assets:
  reference_images: []
  gsep_elements: []
  html_snippets: []
  color_palette_image: {url: ""}

x_openmontage:
  render_runtime: "remotion"
  composition_mode: "atelier"
  profile: "tiktok"
---

## Design Principles

每个故事先让日常空间可信，再允许一条超现实规则出现。异象可以越来越多，镜头语言却保持克制。
结尾不表现彻底治愈，只用一束暖光、一个放松动作或一件物体的轻微变化，证明世界松动了一点。

角色识别依靠脸、短卷发轮廓和体态，不依靠固定制服。灰绿色每集只出现一次或两次，不能铺满画面。

## Connectors

### ComfyUI
候选阶段使用相同机位、服装、背景和光线，只替换角色身份差异。选定后才建立四参考图并进入一致性测试。

### Remotion Atelier
逐篇手写镜头与运动，不调用库存创意场景组件。字幕承担无障碍功能，不与画面中的同句文字重复。
"""


def build_proposal(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    concepts = []
    for candidate in config["candidate_selection"]["candidates"]:
        concepts.append(
            {
                "id": candidate["id"].lower(),
                "title": candidate["blind_label"],
                "hook": "同一位女性，走进十六种寓言人生。",
                "narrative_structure": "story",
                "visual_approach": "同条件盲选角色肖像；选择后再建立四参考图和跨寓言一致性测试。",
                "suggested_playbook": "rain-after-moss-fable",
                "target_audience": "关注心理、哲学、自我成长与文学寓言的中文短视频观众",
                "target_platform": "tiktok",
                "target_duration_seconds": 12,
                "key_points": ["成年女性身份稳定", "柔和乐观而非疲惫", "短卷发轮廓可跨集识别"],
                "core_message": "固定的是演员，不是她每一集的人生。",
                "tone": "温暖、清醒、克制",
                "grounded_in": ["user-approved character direction", "three selected fable scripts"],
                "why_this_works": "在相同构图条件下只比较脸与卷发，可避免把灯光或服装偏好误当成角色偏好。",
            }
        )

    proposal = {
        "version": "1.0",
        "concept_options": concepts,
        "selected_concept": {
            "concept_id": "a01",
            "rationale": "A01仅作为配置占位；三张GPU候选出图后由用户盲选，选择结果会追加到decision_log。",
            "modifications": [
                "角色必须明确为女性",
                "删除眼下阴影与疲惫感",
                "角色气质改为柔和乐观",
                "第一批生成三个候选并停止等待选择",
            ],
        },
        "production_plan": {
            "pipeline": "animated-explainer",
            "playbook": "rain-after-moss-fable",
            "stages": [
                {
                    "stage": "proposal",
                    "tools": [],
                    "approach": "CPU落盘角色圣经、视觉系统、三候选盲选协议与GPU门禁。",
                },
                {
                    "stage": "assets",
                    "tools": [
                        {
                            "tool_name": "comfyui_image",
                            "role": "使用Krea 2 Low VRAM生成A01-A03三张同条件女性角色候选图",
                            "provider": "comfyui",
                            "available": False,
                            "estimated_cost_usd": 0.0,
                            "why_this_provider": "模板已经通过GPU验收；当前仅因AutoDL无GPU资源而不可用。",
                        }
                    ],
                    "approach": "GPU恢复后只运行三张候选，下载到Mac并停在人工选择门禁。",
                    "fallback_if_unavailable": "保持等待，不自动切换模型或用其他提供方替代。",
                },
                {
                    "stage": "compose",
                    "tools": [
                        {
                            "tool_name": "video_compose",
                            "role": "候选选定后的寓言样片使用Remotion Atelier合成",
                            "provider": "local",
                            "available": True,
                            "estimated_cost_usd": 0.0,
                            "why_this_provider": "用户已批准竖屏电影绘本、精确字幕与逐篇定制。",
                        }
                    ],
                    "approach": "本批不渲染成片；仅锁定后续合成路径。",
                },
            ],
            "quality_tradeoffs": [
                {
                    "tradeoff": "先生成3张候选 vs 直接生成完整四视图",
                    "recommendation": "先候选后扩展",
                    "quality_impact": "减少错误角色带来的GPU浪费，并保留人工审美门禁。",
                }
            ],
            "alternative_paths": [
                {
                    "description": "本地SVG可动角色",
                    "total_cost_usd": 0.0,
                    "quality_level": "standard",
                    "what_changes": "一致性更强，但不符合诗意2.5D电影绘本材质。",
                }
            ],
            "delivery_promise": {
                "promise_type": "hybrid",
                "motion_required": True,
                "source_required": False,
                "tone_mode": "intimate cinematic",
                "quality_floor": "presentable",
                "approved_fallback": None,
            },
            "renderer_family": "animation-first",
            "render_runtime": "remotion",
            "composition_mode": "atelier",
            "art_direction": "artifacts/visual-style.md；雨后青苔、成年女性、柔和乐观、电影绘本混合。",
            "taste_profile": {
                "design_read": "文学寓言而非心理知识卡；世界的变化克制地跟随女性演员的一次小行动。",
                "visual_variance": 7,
                "motion_intensity": 4,
                "information_density": 3,
            },
            "music_source": {
                "source_type": "none",
                "track_path": "",
                "provider": "",
                "mood_direction": "角色定型批不使用音乐；完整视频另行选择。",
                "estimated_cost_usd": 0.0,
            },
            "voice_selection": {
                "provider": "none",
                "voice_id": "independent-warm-narrator-pending",
                "rationale": "本批只选择视觉角色；旁白声线不与角色候选混选。",
                "estimated_cost_usd": 0.0,
                "delivery_style": "独立温暖旁白",
                "pacing_policy": "完整视频阶段单独试听批准",
                "sample_approval_required": True,
            },
            "decision_log_ref": "artifacts/decision_log.json",
        },
        "cost_estimate": {
            "total_estimated_usd": 0.0,
            "line_items": [
                {
                    "tool": "comfyui_image",
                    "operation": "Krea 2 Low VRAM同条件女性角色候选",
                    "quantity": 3,
                    "estimated_usd": 0.0,
                    "notes": "无单次API费用；AutoDL在线成本待实跑记录。",
                }
            ],
            "budget_verdict": "no_budget_set",
            "savings_options": ["本批严格限制为三张，不自动进入四视图和动态生成。"],
        },
        "approval": {
            "status": "approved_with_changes",
            "user_notes": "用户批准角色定型批，并要求三个女性角色版本出图后再选择。",
            "approved_budget_usd": 0.0,
        },
        "metadata": {"project_id": config["project_id"], "gpu_gate": "waiting_for_resource"},
    }

    decisions = {
        "version": "1.0",
        "project_id": config["project_id"],
        "decisions": [
            {
                "decision_id": "d-001",
                "stage": "proposal",
                "category": "pipeline_selection",
                "subject": "Pipeline",
                "options_considered": [
                    {"option_id": "animated-explainer", "label": "Animated explainer", "score": 0.96, "reason": "匹配中文旁白寓言与生成视觉。"},
                    {"option_id": "character-animation", "label": "Character animation", "score": 0.62, "reason": "适合SVG可动角色。", "rejected_because": "用户选择诗意2.5D电影绘本而非本地刚性角色。"},
                ],
                "selected": "animated-explainer",
                "reason": "使用固定人物参考包驱动逐篇生成视觉。",
                "user_visible": True,
                "user_approved": True,
                "confidence": 0.97,
            },
            {
                "decision_id": "d-002",
                "stage": "proposal",
                "category": "render_runtime_selection",
                "subject": "Composition runtime",
                "options_considered": [
                    {"option_id": "remotion", "label": "Remotion", "score": 0.96, "reason": "适合竖屏人物绘本、精确字幕和生成镜头整合。"},
                    {"option_id": "hyperframes", "label": "HyperFrames", "score": 0.74, "reason": "适合GSAP强排版。", "rejected_because": "人物叙事与长旁白管理成本更高。"},
                    {"option_id": "ffmpeg", "label": "FFmpeg", "score": 0.35, "reason": "适合封装剪辑。", "rejected_because": "无法独立承担2.5D设计。"},
                ],
                "selected": "remotion",
                "reason": "用户明确批准Remotion。",
                "user_visible": True,
                "user_approved": True,
                "confidence": 0.99,
            },
            {
                "decision_id": "d-003",
                "stage": "proposal",
                "category": "composition_mode",
                "subject": "Composition authoring mode",
                "options_considered": [
                    {"option_id": "atelier", "label": "Atelier", "score": 0.96, "reason": "逐篇隐喻需要独特镜头语言。"},
                    {"option_id": "templated", "label": "Templated", "score": 0.58, "reason": "批量更快。", "rejected_because": "模板感会削弱文学寓言质感。"},
                ],
                "selected": "atelier",
                "reason": "用户明确选择逐篇定制Atelier。",
                "user_visible": True,
                "user_approved": True,
                "confidence": 0.99,
            },
            {
                "decision_id": "d-004",
                "stage": "proposal",
                "category": "concept_selection",
                "subject": "Recurring fable actor identity",
                "options_considered": [
                    {"option_id": "adult-woman", "label": "成年女性寓言演员", "score": 1.0, "reason": "用户明确要求强调女性。"},
                    {"option_id": "neutral", "label": "中性青年", "score": 0.4, "reason": "投射面较广。", "rejected_because": "用户明确否决中性表达。"},
                ],
                "selected": "adult-woman",
                "reason": "固定演员为25至32岁东亚女性。",
                "user_visible": True,
                "user_approved": True,
                "confidence": 1.0,
            },
            {
                "decision_id": "d-005",
                "stage": "assets",
                "category": "provider_selection",
                "subject": "Three candidate character images",
                "options_considered": [
                    {"option_id": "krea2-low-vram", "label": "Krea 2 Low VRAM", "score": 0.95, "reason": "已验收并适合常规角色概念图。"},
                    {"option_id": "openai-image", "label": "OpenAI image", "score": 0.7, "reason": "当前可用。", "rejected_because": "固定角色后续已批准走ComfyUI多参考链路，不自动更换提供方。"},
                ],
                "selected": "krea2-low-vram",
                "reason": "GPU恢复后生成三张同条件候选并停止。",
                "user_visible": True,
                "user_approved": True,
                "confidence": 0.96,
            },
        ],
    }
    validate_artifact("proposal_packet", proposal)
    validate_artifact("decision_log", decisions)
    return proposal, decisions


def prepare_project(config: dict[str, Any], *, projects_dir: Path = PROJECTS_DIR) -> dict[str, Any]:
    errors = validate_config(config)
    if errors:
        raise ValueError("Invalid fable character pilot config:\n- " + "\n- ".join(errors))

    target = init_project(
        config["project_id"],
        title=config["title"],
        pipeline_type=config["pipeline"],
        pipeline_dir=projects_dir,
        style_playbook="rain-after-moss-fable",
    )
    artifacts = target / "artifacts"
    snapshots = artifacts / "source_scripts"
    snapshots.mkdir(parents=True, exist_ok=True)
    source_records = []
    for index, source_text in enumerate(config["source_scripts"], start=1):
        source = Path(source_text)
        snapshot = snapshots / f"{index:02d}_{source.name}"
        snapshot.write_bytes(source.read_bytes())
        source_records.append(
            {
                "source_path": str(source),
                "snapshot_path": str(snapshot),
                "source_sha256": sha256_file(source),
                "snapshot_sha256": sha256_file(snapshot),
                "read_only_source": True,
            }
        )

    dump_json(artifacts / "source_snapshots.json", {"captured_at": utc_now(), "items": source_records})
    dump_json(artifacts / "character_bible.json", config["character_bible"])
    (artifacts / "visual-style.md").write_text(visual_style_markdown(config), encoding="utf-8")
    dump_json(artifacts / "character_candidates.json", config["candidate_selection"])
    dump_json(artifacts / "consistency_test_matrix.json", {"tests": config["consistency_tests"]})
    dump_json(artifacts / "motion_sample_plan.json", config["motion_sample"])

    gpu_tasks = {
        "version": "1.0",
        "project_id": config["project_id"],
        "gate": "phase-one-candidate-selection",
        "automatic_follow_on_generation": False,
        "phase_one": [
            {
                "task_id": f"candidate-{candidate['id']}",
                "status": "waiting_for_gpu",
                "tool": "comfyui_image",
                "provider": "comfyui",
                "workflow_template": config["candidate_selection"]["workflow_template"],
                "prompt": candidate_prompt(config, candidate),
                "seed": candidate["seed"],
                "steps": config["candidate_selection"]["steps"],
                "aspect_preset": config["aspect_preset"],
                "output_path": str(target / "assets" / "images" / "character_candidates" / f"{candidate['id']}.png"),
            }
            for candidate in config["candidate_selection"]["candidates"]
        ],
        "blocked_until_selection": [
            {"stage": "four_reference_views", "tool": "flux2_klein_4ref"},
            {"stage": "three_fable_consistency_tests", "tool": "flux2_klein_4ref"},
            {"stage": "local_repairs", "tool": "flux2_klein_inpaint"},
            {"stage": "twelve_second_motion_sample", "tool": "wan22_i2v_q6"},
        ],
    }
    dump_json(artifacts / "gpu_task_plan.json", gpu_tasks)
    dump_json(
        artifacts / "gpu_usage_report.json",
        {"version": "1.0", "project_id": config["project_id"], "status": "not_started", "events": [], "summary": {}, "created_at": utc_now()},
    )

    proposal, decisions = build_proposal(config)
    dump_json(artifacts / "proposal_packet.json", proposal)
    dump_json(artifacts / "decision_log.json", decisions)
    write_checkpoint(
        projects_dir,
        config["project_id"],
        "proposal",
        "completed",
        {"proposal_packet": proposal, "decision_log": decisions},
        pipeline_type=config["pipeline"],
        style_playbook="rain-after-moss-fable",
        human_approval_required=True,
        human_approved=True,
        cost_snapshot={"estimated_usd": 0.0, "gpu_cost_pending_measurement": True},
        metadata={
            "approved_plan_source": "user approved three-version female character selection batch",
            "cpu_preparation_complete": True,
            "gpu_gate": "waiting_for_resource",
            "next_action": "generate exactly A01-A03 when GPU is available",
        },
    )
    return {
        "project_id": config["project_id"],
        "project_dir": str(target),
        "source_snapshots": len(source_records),
        "candidate_versions": 3,
        "cpu_preparation_complete": True,
        "gpu_required_next": True,
        "next_gate": "human selects A01, A02, or A03",
    }


def _record_event(report_path: Path, event: dict[str, Any]) -> None:
    report = load_json(report_path)
    report.setdefault("events", []).append(event)
    completed = [item for item in report["events"] if item.get("status") == "completed"]
    failed = [item for item in report["events"] if item.get("status") == "failed"]
    report["summary"] = {
        "completed": len(completed),
        "failed": len(failed),
        "effective_generation_seconds": round(sum(float(item.get("wall_seconds", 0)) for item in completed), 2),
    }
    report["updated_at"] = utc_now()
    dump_json(report_path, report)


def generate_gpu_candidates(config: dict[str, Any], *, projects_dir: Path = PROJECTS_DIR) -> dict[str, Any]:
    errors = validate_config(config)
    if errors:
        raise ValueError("Invalid fable character pilot config:\n- " + "\n- ".join(errors))
    target = project_dir(config, projects_dir)
    if not (target / "project.json").is_file():
        raise RuntimeError("Project is not prepared. Run prepare first.")
    if (target / "artifacts" / "character_selection.json").exists():
        raise RuntimeError("A character is already selected; phase-one generation cannot be repeated silently.")

    report_path = target / "artifacts" / "gpu_usage_report.json"
    ensure_gpu_preflight(report_path)
    report = load_json(report_path)
    report["status"] = "in_progress"
    report["gpu_session_started_at"] = utc_now()
    dump_json(report_path, report)

    output_dir = target / "assets" / "images" / "character_candidates"
    output_dir.mkdir(parents=True, exist_ok=True)
    tool = ComfyUIImage()
    outputs = []
    for candidate in config["candidate_selection"]["candidates"]:
        output = output_dir / f"{candidate['id']}.png"
        if output.is_file() and output.stat().st_size > 0:
            outputs.append(str(output))
            continue
        inputs = {
            "prompt": candidate_prompt(config, candidate),
            "workflow_template": config["candidate_selection"]["workflow_template"],
            "steps": config["candidate_selection"]["steps"],
            "seed": candidate["seed"],
            "aspect_preset": config["aspect_preset"],
            "output_path": str(output),
        }
        started = time.monotonic()
        result = tool.execute(inputs)
        event = {
            "candidate_id": candidate["id"],
            "kind": "character_candidate",
            "tool": tool.name,
            "workflow_template": inputs["workflow_template"],
            "seed": inputs["seed"],
            "completed_at": utc_now(),
            "wall_seconds": round(time.monotonic() - started, 2),
            "status": "completed" if result.success else "failed",
            "output_path": str(output),
            "error": result.error,
        }
        _record_event(report_path, event)
        if not result.success:
            raise RuntimeError(f"{candidate['id']} generation failed: {result.error}")
        outputs.append(str(output))

    report = load_json(report_path)
    report["status"] = "awaiting_human_selection"
    report["phase_one_completed_at"] = utc_now()
    dump_json(report_path, report)
    dump_json(
        target / "artifacts" / "candidate_asset_manifest.json",
        {
            "version": "1.0",
            "project_id": config["project_id"],
            "assets": [
                {
                    "candidate_id": candidate["id"],
                    "blind_label": candidate["blind_label"],
                    "path": str(output_dir / f"{candidate['id']}.png"),
                    "sha256": sha256_file(output_dir / f"{candidate['id']}.png"),
                    "seed": candidate["seed"],
                    "workflow_template": config["candidate_selection"]["workflow_template"],
                }
                for candidate in config["candidate_selection"]["candidates"]
            ],
            "selection_status": "awaiting_human",
        },
    )
    return {"generated": outputs, "status": "awaiting_human_selection", "automatic_follow_on_generation": False}


def select_candidate(config: dict[str, Any], candidate_id: str, *, projects_dir: Path = PROJECTS_DIR) -> dict[str, Any]:
    valid_ids = {item["id"] for item in config["candidate_selection"]["candidates"]}
    if candidate_id not in valid_ids:
        raise ValueError(f"candidate must be one of {sorted(valid_ids)}")
    target = project_dir(config, projects_dir)
    image = target / "assets" / "images" / "character_candidates" / f"{candidate_id}.png"
    if not image.is_file():
        raise FileNotFoundError(f"Candidate image does not exist: {image}")
    selection = {
        "version": "1.0",
        "project_id": config["project_id"],
        "selected_candidate": candidate_id,
        "selected_image": str(image),
        "selected_image_sha256": sha256_file(image),
        "selected_at": utc_now(),
        "next_stage": "prepare four standard reference views for separate approval",
        "automatic_generation_started": False,
    }
    dump_json(target / "artifacts" / "character_selection.json", selection)
    return selection


def gpu_online() -> bool:
    server = os.environ.get("COMFYUI_SERVER_URL", "http://127.0.0.1:18188").rstrip("/")
    try:
        with urllib.request.urlopen(server + "/system_stats", timeout=1.5):
            return True
    except Exception:
        return False


def status_report(config: dict[str, Any], *, projects_dir: Path = PROJECTS_DIR) -> dict[str, Any]:
    target = project_dir(config, projects_dir)
    candidate_dir = target / "assets" / "images" / "character_candidates"
    images = sorted(path.name for path in candidate_dir.glob("A*.png")) if candidate_dir.exists() else []
    selection_path = target / "artifacts" / "character_selection.json"
    report_path = target / "artifacts" / "gpu_usage_report.json"
    report = load_json(report_path) if report_path.exists() else {"status": "not_prepared"}
    return {
        "project_id": config["project_id"],
        "prepared": (target / "project.json").is_file(),
        "cpu_preparation_complete": (target / "artifacts" / "gpu_task_plan.json").is_file(),
        "gpu_online": gpu_online(),
        "gpu_status": report.get("status"),
        "candidate_images": images,
        "candidate_count": len(images),
        "expected_candidate_count": 3,
        "selected_candidate": load_json(selection_path).get("selected_candidate") if selection_path.exists() else None,
        "follow_on_generation_blocked": not selection_path.exists(),
    }


def finalize_gpu_batch(config: dict[str, Any], *, yes: bool, shutdown: bool) -> int:
    command = [
        str(REPO_ROOT / ".venv" / "bin" / "python"),
        str(REPO_ROOT / "scripts" / "finalize_autodl_comfyui_batch.py"),
        "--project-dir",
        str(project_dir(config)),
        "--policy",
        str(REPO_ROOT / config["retention_policy"]),
    ]
    command.append("--yes" if yes else "--dry-run")
    if shutdown:
        if not yes:
            raise ValueError("--shutdown requires --yes")
        command.append("--shutdown")
    return subprocess.run(command, cwd=REPO_ROOT, check=False).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TreeElf fable actress character-selection workflow")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("prepare")
    sub.add_parser("status")
    sub.add_parser("generate-gpu")
    select = sub.add_parser("select")
    select.add_argument("--candidate", required=True, choices=["A01", "A02", "A03"])
    final = sub.add_parser("finalize-gpu")
    final.add_argument("--yes", action="store_true")
    final.add_argument("--shutdown", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_json(args.config)
    if args.command == "validate":
        errors = validate_config(config)
        result = {"valid": not errors, "errors": errors}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1 if errors else 0)
    if args.command == "prepare":
        result = prepare_project(config)
    elif args.command == "status":
        result = status_report(config)
    elif args.command == "generate-gpu":
        result = generate_gpu_candidates(config)
    elif args.command == "select":
        result = select_candidate(config, args.candidate)
    elif args.command == "finalize-gpu":
        raise SystemExit(finalize_gpu_batch(config, yes=args.yes, shutdown=args.shutdown))
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
