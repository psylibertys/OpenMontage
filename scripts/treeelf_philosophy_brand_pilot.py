#!/usr/bin/env python3
"""Prepare and run the first TreeElf philosophy brand-selection batch.

The creative choices live in a reviewed JSON config. This module provides
mechanical persistence and execution only: inbox discovery, candidate asset
generation through registered OpenMontage tools, GPU timing, local Remotion
cover rendering, selection profiles, and delegation to the audited AutoDL
batch finalizer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.checkpoint import init_project, write_checkpoint
from lib.paths import PROJECTS_DIR
from tools.audio.comfyui_tts import ComfyUITTS
from tools.graphics.comfyui_image import ComfyUIImage
from tools.video.comfyui_video import ComfyUIVideo
from scripts.treeelf_philosophy_timeline import resolve_wan_generation_plan_for_project


DEFAULT_CONFIG = (
    REPO_ROOT
    / "workflow_configs"
    / "zh-philosophy-video"
    / "treeelf-habit-door-brand-pilot.json"
)
DEFAULT_INBOX = Path(
    "/Users/treeelf/Desktop/Psynaut/treeElfNotes/07产出/心哲灵/短视频文案"
)
INBOX_PROJECT_ID = "treeelf-philosophy-inbox"


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


def media_duration_seconds(path: Path) -> float | None:
    """Return playable media duration; tool result duration is generation time."""

    if not path.is_file():
        return None
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return round(float(result.stdout.strip()), 2)
    except ValueError:
        return None


def parse_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"Missing YAML frontmatter: {path}")
    try:
        frontmatter, body = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError(f"Unclosed YAML frontmatter: {path}") from exc
    metadata = yaml.safe_load(frontmatter) or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"Frontmatter must be an object: {path}")
    return metadata, body.strip()


def scan_inbox(
    inbox_dir: Path = DEFAULT_INBOX,
    *,
    ledger_path: Path | None = None,
    reservations_dir: Path | None = None,
) -> dict[str, Any]:
    """Scan only root Markdown files and update a content-hash ledger."""

    if ledger_path is None:
        ledger_path = PROJECTS_DIR / INBOX_PROJECT_ID / "ledger.json"
    if reservations_dir is None:
        reservations_dir = PROJECTS_DIR
    reservations: dict[str, dict[str, Any]] = {}
    for manifest_path in reservations_dir.glob("*/artifacts/batch_manifest.json"):
        try:
            manifest = load_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if manifest.get("workflow") != "treeelf_philosophy_gpu_batch":
            continue
        for episode in manifest.get("episodes", []):
            if episode.get("status") in {"delivered", "completed", "cancelled"}:
                continue
            source_path = episode.get("source_path")
            if source_path:
                reservations[str(Path(source_path).resolve())] = {
                    "batch_id": manifest.get("batch_id"),
                    "status": episode.get("status"),
                    "manifest": str(manifest_path),
                }
    previous = load_json(ledger_path) if ledger_path.exists() else {"version": "1.0", "items": {}}
    previous_items = previous.get("items", {})
    items: dict[str, Any] = {}
    counts = {"eligible": 0, "draft": 0, "other": 0, "changed": 0}

    for path in sorted(inbox_dir.glob("*.md")):
        metadata, body = parse_markdown(path)
        asset_id = str(metadata.get("asset_id") or path.stem)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        production_status = str(metadata.get("production_status") or "discovered")
        reservation = reservations.get(str(path.resolve()))
        eligible = (
            metadata.get("type") == "短视频文案"
            and metadata.get("status") == "ready"
            and metadata.get("review_status") == "passed"
            and production_status not in {"completed", "produced", "archived"}
            and reservation is None
        )
        category = "eligible" if eligible else "draft" if metadata.get("status") == "draft" else "other"
        counts[category] += 1
        old = previous_items.get(asset_id, {})
        changed = bool(old and old.get("source_sha256") != digest)
        if changed:
            counts["changed"] += 1
        revision = int(old.get("revision", 0)) + 1 if changed else int(old.get("revision", 1))
        items[asset_id] = {
            "asset_id": asset_id,
            "title": next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), path.stem),
            "source_path": str(path),
            "source_sha256": digest,
            "revision": revision,
            "eligibility": category,
            "status": metadata.get("status"),
            "review_status": metadata.get("review_status"),
            "cover_title": metadata.get("cover_title"),
            "production_status": production_status,
            "video_project_id": metadata.get("video_project_id"),
            "video_output": metadata.get("video_output"),
            "changed_since_last_scan": changed,
            "batch_reservation": reservation,
        }

    report = {
        "version": "1.0",
        "scanned_at": utc_now(),
        "inbox_dir": str(inbox_dir),
        "root_markdown_count": len(items),
        "counts": counts,
        "items": items,
    }
    dump_json(ledger_path, report)
    return report


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["project_id", "title", "source_script_md", "voice_selection", "cover_selection"]
    for key in required:
        if not config.get(key):
            errors.append(f"missing:{key}")

    voice = config.get("voice_selection", {})
    voices = voice.get("candidates", [])
    if len(voices) != 10:
        errors.append("voice_selection.candidates must contain exactly 10 items")
    voice_ids = [item.get("id") for item in voices]
    if voice_ids != [f"A{index:02d}" for index in range(1, 11)]:
        errors.append("voice candidate ids must be A01..A10 in order")
    if len({item.get("seed") for item in voices}) != len(voices):
        errors.append("voice candidate seeds must be unique")
    if not voice.get("sample_text"):
        errors.append("voice_selection.sample_text is required")

    cover = config.get("cover_selection", {})
    directions = cover.get("directions", [])
    if len(directions) != 12:
        errors.append("cover_selection.directions must contain exactly 12 items")
    cover_ids = [item.get("id") for item in directions]
    if cover_ids != [f"C{index:02d}" for index in range(1, 13)]:
        errors.append("cover direction ids must be C01..C12 in order")
    if len({item.get("seed") for item in directions}) != len(directions):
        errors.append("cover direction seeds must be unique")
    if cover.get("brand") != "树精灵":
        errors.append("cover_selection.brand must be 树精灵")
    for item in directions:
        if len(item.get("philosophy", [])) < 4:
            errors.append(f"{item.get('id')}: philosophy must contain at least 4 paragraphs")
        prompt = str(item.get("krea_prompt", "")).lower()
        if not all(token in prompt for token in ("no text", "no letters", "no logo")):
            errors.append(f"{item.get('id')}: Krea prompt must explicitly forbid text, letters, and logos")

    return errors


def project_dir(config: dict[str, Any], projects_dir: Path = PROJECTS_DIR) -> Path:
    return projects_dir / str(config["project_id"])


def direction_markdown(config: dict[str, Any], direction: dict[str, Any]) -> str:
    layout = direction["layout"]
    paragraphs = "\n\n".join(direction["philosophy"])
    return (
        f"# {direction['id']} · {direction['name']}\n\n"
        f"## 视觉哲学\n\n{paragraphs}\n\n"
        f"## 隐性母题\n\n{direction['subtle_reference']}\n\n"
        f"## Krea执行提示词\n\n{direction['krea_prompt']}\n\n"
        f"## Remotion文字安全区\n\n"
        f"- 标题位置：{layout['title_position']}\n"
        f"- 对齐：{layout['text_align']}\n"
        f"- 渐变方向：{layout['gradient_direction']}\n"
        f"- 文字色：{layout['text_color']}\n"
        f"- 强调色：{layout['accent_color']}\n"
        f"- 中文标题：{config['cover_selection']['chinese_title']}\n"
        f"- 英文副标题：{config['cover_selection']['english_title']}\n"
        f"- 栏目标识：{config['cover_selection']['brand']}\n"
    )


def build_proposal(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    common = {
        "title": config["title"],
        "hook": "整栋习惯大楼，不必今天开业。",
        "target_duration_seconds": config["target_duration_seconds"],
        "target_platform": "tiktok",
        "target_audience": "关注心理机制、哲学解释和自我成长的中文短视频观众",
        "key_points": ["复杂习惯由多个动作组成", "先固定入口节点", "入口稳定后再参与完整流程"],
        "core_message": "先让那扇门认得你，剩下的路交给已经进门的人。",
        "tone": "清醒、温暖、轻微幽默",
        "grounded_in": ["user_approved_source_script"],
        "suggested_playbook": "treeelf-philosophy-v1",
    }
    proposal = {
        "version": "1.0",
        "concept_options": [
            {
                **common,
                "id": "hybrid-door-metaphor",
                "narrative_structure": "analogy",
                "visual_approach": "Krea原创重点帧与Wan动作测试承载入口隐喻，Remotion精确文字卡与字幕保证信息清晰。",
                "why_this_works": "用户批准的持续生产路线同时检验原创视觉、真实运动和批量排版能力。",
            },
            {
                **common,
                "id": "graphic-led",
                "narrative_structure": "tutorial",
                "visual_approach": "以Remotion图形系统和文字卡为主，生成图仅作封面与少量背景。",
                "why_this_works": "生产稳定且信息密度可控，但不足以充分测试本次已部署的ComfyUI资产能力。",
            },
            {
                **common,
                "id": "stock-led",
                "narrative_structure": "story",
                "visual_approach": "生活化实拍素材为主，原创图和动态图只用于开头与收束。",
                "why_this_works": "人物感最直接，但栏目差异化和原创视觉资产沉淀较弱。",
            },
        ],
        "selected_concept": {
            "concept_id": "hybrid-door-metaphor",
            "rationale": "用户明确批准混合型栏目模板，并指定Canvas设计、Krea执行、Remotion文字。",
            "modifications": ["封面栏目标识固定为树精灵", "语速中等", "有趣处自然轻笑"],
        },
        "production_plan": {
            "pipeline": "animated-explainer",
            "playbook": "treeelf-philosophy-v1",
            "stages": [
                {
                    "stage": "proposal",
                    "tools": [],
                    "approach": "锁定10个声线候选、12个封面方向和GPU批次生命周期。",
                },
                {
                    "stage": "assets",
                    "tools": [
                        {"tool_name": "comfyui_tts", "role": "生成10个Qwen3-TTS VoiceDesign候选", "provider": "comfyui", "available": False, "estimated_cost_usd": 0.0, "why_this_provider": "服务器已部署并验收，但当前等待用户以GPU模式开机。"},
                        {"tool_name": "comfyui_image", "role": "用Krea生成12张无字封面背景和3张风格帧", "provider": "comfyui", "available": False, "estimated_cost_usd": 0.0, "why_this_provider": "用户批准Krea作为Canvas设计的执行器。"},
                        {"tool_name": "comfyui_video", "role": "用Wan 2.2 I2V生成1个动作测试", "provider": "comfyui", "available": False, "estimated_cost_usd": 0.0, "why_this_provider": "已批准的关键静帧动态化路径。"}
                    ],
                    "approach": "GPU开机并通过15/15预检后执行候选批次；失败时停止，不自动切换提供方。",
                    "fallback_if_unavailable": "保持阻塞并报告，不使用Edge、OpenAI图像或其他模型替代。",
                },
                {
                    "stage": "compose",
                    "tools": [
                        {"tool_name": "video_compose", "role": "GPU关机后在Mac本地执行Remotion排版与合成", "provider": "local", "available": True, "estimated_cost_usd": 0.0}
                    ],
                    "approach": "TreeElfCover为Krea背景叠加准确中英标题与树精灵标识。",
                },
            ],
            "delivery_promise": {"promise_type": "hybrid", "motion_required": True, "source_required": False, "tone_mode": "intimate", "quality_floor": "presentable", "approved_fallback": None},
            "renderer_family": "explainer-data",
            "render_runtime": "remotion",
            "composition_mode": "templated",
            "voice_selection": {"provider": "comfyui", "voice_id": "qwen3_tts_voice_design:A01-A10", "rationale": "首次栏目定型批次进行匿名盲选。", "estimated_cost_usd": 0.0, "delivery_style": "20岁左右、清晰温暖、乐观阳光的普通话女声；有趣处自然轻笑。", "pacing_policy": "中等语速；相同试听稿和推理参数，候选指令与seed不同。", "sample_approval_required": True},
            "music_source": {"source_type": "user_library", "track_path": "", "provider": "local", "mood_direction": "样片成片阶段从现有纯音乐库选择", "estimated_cost_usd": 0.0},
            "decision_log_ref": "artifacts/decision_log.json",
        },
        "cost_estimate": {
            "total_estimated_usd": 0.0,
            "line_items": [
                {"tool": "comfyui_tts", "operation": "Qwen3-TTS VoiceDesign候选", "quantity": 10, "estimated_usd": 0.0, "notes": "无单次API费；AutoDL GPU在线成本将在实跑后记录。"},
                {"tool": "comfyui_image", "operation": "Krea封面背景与风格帧", "quantity": 15, "estimated_usd": 0.0, "notes": "无单次API费；记录逐项GPU耗时。"},
                {"tool": "comfyui_video", "operation": "Wan I2V动作测试", "quantity": 1, "estimated_usd": 0.0, "notes": "无单次API费；记录逐项GPU耗时。"},
                {"tool": "video_compose", "operation": "本地Remotion静态封面与后续合成", "quantity": 1, "estimated_usd": 0.0}
            ],
            "budget_verdict": "no_budget_set",
        },
        "approval": {
            "status": "approved_with_changes",
            "user_notes": "用户批准实施；生产前由Agent通知用户开启GPU，生成后备份、校验、清理、关机，再本地合成。",
        },
        "metadata": {"project_id": config["project_id"], "source_script_md": config["source_script_md"]},
    }
    decisions = {
        "version": "1.0",
        "project_id": config["project_id"],
        "decisions": [
            {"decision_id": "d-001", "stage": "proposal", "category": "pipeline_selection", "subject": "Pipeline", "options_considered": [{"option_id": "animated-explainer", "label": "Animated explainer", "score": 0.98, "reason": "已验证的中文哲思解释视频主线。"}], "selected": "animated-explainer", "reason": "匹配现有zh-philosophy-video持续流程。", "user_visible": True, "user_approved": True, "confidence": 0.98},
            {"decision_id": "d-002", "stage": "proposal", "category": "render_runtime_selection", "subject": "Composition runtime", "options_considered": [{"option_id": "remotion", "label": "Remotion", "score": 0.96, "reason": "精确中英文字、字幕和9:16模板复用最成熟。"}, {"option_id": "hyperframes", "label": "HyperFrames", "score": 0.72, "reason": "强动态排版能力好。", "rejected_because": "本栏目已批准Remotion模板化持续生产。"}, {"option_id": "ffmpeg", "label": "FFmpeg", "score": 0.4, "reason": "适合封装与媒体准备。", "rejected_because": "不承担主视觉排版。"}], "selected": "remotion", "reason": "用户批准Remotion负责最终文字与本地合成。", "user_visible": True, "user_approved": True, "confidence": 0.98},
            {"decision_id": "d-003", "stage": "proposal", "category": "composition_mode", "subject": "Composition authoring mode", "options_considered": [{"option_id": "templated", "label": "Templated", "score": 0.95, "reason": "适合后续每篇直接复用栏目模板。"}, {"option_id": "atelier", "label": "Atelier", "score": 0.65, "reason": "单篇独特性更高。", "rejected_because": "不符合持续批量生产目标。"}], "selected": "templated", "reason": "首次定型后需稳定复用。", "user_visible": True, "user_approved": True, "confidence": 0.97},
            {"decision_id": "d-004", "stage": "assets", "category": "voice_selection", "subject": "Narration TTS provider", "options_considered": [{"option_id": "qwen3-voice-design", "label": "Qwen3-TTS VoiceDesign", "score": 0.98, "reason": "本地GPU、可设计10个候选并以seed复现。"}, {"option_id": "edge-tts", "label": "Edge-TTS", "score": 0.55, "reason": "免费稳定。", "rejected_because": "栏目辨识度较弱，且用户已批准Qwen候选流程。"}], "selected": "qwen3-voice-design", "reason": "生成10个不同提示词候选，盲选主声线与备用声线。", "user_visible": True, "user_approved": True, "confidence": 0.98},
            {"decision_id": "d-005", "stage": "assets", "category": "provider_selection", "subject": "Cover visual execution", "options_considered": [{"option_id": "canvas-krea-remotion", "label": "Canvas design → Krea → Remotion", "score": 0.99, "reason": "设计、无字图像执行和精确文字职责清晰。"}], "selected": "canvas-krea-remotion", "reason": "用户明确指定的封面生产链。", "user_visible": True, "user_approved": True, "confidence": 1.0}
        ],
    }
    return proposal, decisions


def prepare_project(config: dict[str, Any], *, projects_dir: Path = PROJECTS_DIR) -> dict[str, Any]:
    errors = validate_config(config)
    if errors:
        raise ValueError("Invalid brand pilot config:\n- " + "\n- ".join(errors))
    source = Path(config["source_script_md"])
    if not source.is_file():
        raise FileNotFoundError(source)
    target = init_project(
        config["project_id"],
        title=config["title"],
        pipeline_type="animated-explainer",
        pipeline_dir=projects_dir,
        style_playbook="treeelf-philosophy-v1",
    )
    artifacts = target / "artifacts"
    snapshot = artifacts / "source_script.md"
    shutil.copy2(source, snapshot)
    dump_json(
        artifacts / "source_snapshot.json",
        {
            "source_path": str(source),
            "snapshot_path": str(snapshot),
            "source_sha256": sha256_file(source),
            "snapshot_sha256": sha256_file(snapshot),
            "captured_at": utc_now(),
            "read_only_source": True,
        },
    )
    dump_json(artifacts / "voice_candidates.json", config["voice_selection"])
    dump_json(artifacts / "cover_directions.json", config["cover_selection"])
    proposal, decisions = build_proposal(config)
    dump_json(artifacts / "proposal_packet.json", proposal)
    dump_json(artifacts / "decision_log.json", decisions)
    directions_dir = artifacts / "cover_directions"
    directions_dir.mkdir(parents=True, exist_ok=True)
    for direction in config["cover_selection"]["directions"]:
        (directions_dir / f"{direction['id']}.md").write_text(
            direction_markdown(config, direction), encoding="utf-8"
        )
    report_path = artifacts / "gpu_usage_report.json"
    if not report_path.exists():
        dump_json(
            report_path,
            {
                "version": "1.0",
                "project_id": config["project_id"],
                "status": "not_started",
                "events": [],
                "summary": {},
                "created_at": utc_now(),
            },
        )
    write_checkpoint(
        projects_dir,
        config["project_id"],
        "proposal",
        "completed",
        {"proposal_packet": proposal, "decision_log": decisions},
        pipeline_type="animated-explainer",
        style_playbook="treeelf-philosophy-v1",
        human_approval_required=True,
        human_approved=True,
        cost_snapshot={"estimated_usd": 0.0, "gpu_cost_pending_measurement": True},
        metadata={"approved_plan_source": "user implementation request", "gpu_gate": "waiting_for_user_power_on"},
    )
    return {
        "project_id": config["project_id"],
        "project_dir": str(target),
        "source_snapshot": str(snapshot),
        "voice_candidates": 10,
        "cover_directions": 12,
        "gpu_required_next": True,
    }


def _event_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [event for event in events if event.get("status") == "completed"]
    failed = [event for event in events if event.get("status") == "failed"]
    by_kind: dict[str, list[float]] = {}
    for event in completed:
        by_kind.setdefault(str(event["kind"]), []).append(float(event.get("wall_seconds", 0)))
    active = sum(float(event.get("wall_seconds", 0)) for event in completed)
    return {
        "completed": len(completed),
        "failed": len(failed),
        "retry_count": sum(int(event.get("retry_count", 0)) for event in events),
        "effective_generation_seconds": round(active, 2),
        "average_seconds_by_kind": {
            kind: round(sum(values) / len(values), 2) for kind, values in sorted(by_kind.items())
        },
    }


def validate_live_gpu_state(system_stats: dict[str, Any], queue: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    devices = system_stats.get("devices", [])
    device_text = json.dumps(devices, ensure_ascii=False).lower()
    if not devices or not any(marker in device_text for marker in ("cuda", "nvidia", "gpu")):
        errors.append("ComfyUI system_stats does not report a GPU device")
    if queue.get("queue_running"):
        errors.append("ComfyUI queue_running is not empty")
    if queue.get("queue_pending"):
        errors.append("ComfyUI queue_pending is not empty")
    return errors


def ensure_gpu_preflight(report_path: Path) -> dict[str, Any]:
    server = os.environ.get("COMFYUI_SERVER_URL", "")
    if server.rstrip("/") != "http://127.0.0.1:18188":
        raise RuntimeError(
            "generate-gpu requires COMFYUI_SERVER_URL=http://127.0.0.1:18188 "
            "through the monitored SSH tunnel"
        )
    started = time.monotonic()
    with urllib.request.urlopen(server + "/system_stats", timeout=15) as response:
        stats = json.load(response)
    with urllib.request.urlopen(server + "/queue", timeout=15) as response:
        queue = json.load(response)
    errors = validate_live_gpu_state(stats, queue)
    if errors:
        raise RuntimeError("GPU preflight failed: " + "; ".join(errors))
    command = [
        str(REPO_ROOT / ".venv" / "bin" / "python"),
        str(REPO_ROOT / "scripts" / "comfyui_workflow_preflight.py"),
        "--server", server,
        "--json",
    ]
    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"15-workflow preflight failed:\n{result.stdout}\n{result.stderr}")
    workflow_report = json.loads(result.stdout)
    if len(workflow_report) != 15 or not all(item.get("ok") for item in workflow_report.values()):
        raise RuntimeError("Expected all 15 ComfyUI workflows to pass preflight")
    payload = {
        "checked_at": utc_now(),
        "server": server,
        "gpu_devices": devices_for_report(stats),
        "queue_empty": True,
        "workflow_count": len(workflow_report),
        "workflow_passed": sum(1 for item in workflow_report.values() if item.get("ok")),
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }
    report = load_json(report_path)
    report["gpu_health_passed_at"] = payload["checked_at"]
    report["preflight"] = payload
    dump_json(report_path, report)
    return payload


def devices_for_report(system_stats: dict[str, Any]) -> list[dict[str, Any]]:
    safe_fields = ("name", "type", "index", "vram_total", "vram_free")
    return [
        {key: device[key] for key in safe_fields if key in device}
        for device in system_stats.get("devices", [])
        if isinstance(device, dict)
    ]


def _record_event(report_path: Path, event: dict[str, Any]) -> None:
    report = load_json(report_path)
    report.setdefault("events", []).append(event)
    report["summary"] = _event_summary(report["events"])
    report["updated_at"] = utc_now()
    dump_json(report_path, report)


def _execute_candidate(
    *,
    tool: Any,
    inputs: dict[str, Any],
    candidate_id: str,
    kind: str,
    report_path: Path,
    retry_count: int = 0,
) -> dict[str, Any]:
    started_at = utc_now()
    wall_start = time.monotonic()
    result = tool.execute(inputs)
    elapsed = round(time.monotonic() - wall_start, 2)
    event = {
        "candidate_id": candidate_id,
        "kind": kind,
        "tool": tool.name,
        "workflow_template": inputs.get("workflow_template"),
        "seed": inputs.get("seed"),
        "started_at": started_at,
        "completed_at": utc_now(),
        "wall_seconds": elapsed,
        "tool_reported_seconds": result.duration_seconds,
        "queue_wait_seconds": result.data.get("queue_wait_seconds") if result.data else None,
        "retry_count": retry_count,
        "status": "completed" if result.success else "failed",
        "output_path": inputs.get("output_path"),
        "error": result.error,
    }
    _record_event(report_path, event)
    if not result.success:
        raise RuntimeError(f"{candidate_id} failed: {result.error}")
    output_path = Path(inputs["output_path"])
    asset = {
        "id": candidate_id,
        "type": kind,
        "path": str(output_path),
        "source_tool": tool.name,
        "provider": tool.provider,
        "seed": result.seed,
        "generation_seconds": result.duration_seconds,
        "size_bytes": output_path.stat().st_size,
        "sha256_local": sha256_file(output_path),
        "workflow_provenance": result.data.get("workflow_provenance", {}),
        "generation_inputs": inputs,
    }
    if kind in {"voice_candidate", "motion_test"}:
        duration = media_duration_seconds(output_path)
        if duration is not None:
            asset["duration_seconds"] = duration
    return asset


def generate_gpu_candidates(config: dict[str, Any], *, projects_dir: Path = PROJECTS_DIR) -> dict[str, Any]:
    target = project_dir(config, projects_dir)
    if not (target / "project.json").is_file():
        prepare_project(config, projects_dir=projects_dir)
    report_path = target / "artifacts" / "gpu_usage_report.json"
    ensure_gpu_preflight(report_path)
    report = load_json(report_path)
    report.update({"status": "running", "gpu_session_started_at": utc_now()})
    dump_json(report_path, report)
    os.environ["COMFYUI_REMOTE_ASSET_POLICY"] = "retain_until_batch_end"

    audio_dir = target / "assets" / "audio" / "voice_candidates"
    cover_dir = target / "assets" / "images" / "cover_backgrounds"
    style_dir = target / "assets" / "images" / "style_frames"
    video_dir = target / "assets" / "video" / "motion_tests"
    for directory in (audio_dir, cover_dir, style_dir, video_dir):
        directory.mkdir(parents=True, exist_ok=True)

    manifest_path = target / "artifacts" / "candidate_asset_manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {
        "version": "1.0", "project_id": config["project_id"], "assets": []
    }
    completed_ids = {asset["id"] for asset in manifest["assets"]}

    tts = ComfyUITTS()
    image = ComfyUIImage()
    video = ComfyUIVideo()
    shared_text = config["voice_selection"]["sample_text"]

    for candidate in config["voice_selection"]["candidates"]:
        candidate_id = candidate["id"]
        if candidate_id in completed_ids:
            continue
        inputs = {
            "text": shared_text,
            "workflow_template": "qwen3_tts_voice_design",
            "output_path": str(audio_dir / f"{candidate_id}.mp3"),
            "instruct": candidate["instruct"],
            "language": "Chinese",
            "seed": candidate["seed"],
            **config["voice_selection"]["inference"],
        }
        manifest["assets"].append(_execute_candidate(
            tool=tts, inputs=inputs, candidate_id=candidate_id, kind="voice_candidate", report_path=report_path
        ))
        dump_json(manifest_path, manifest)

    for direction in config["cover_selection"]["directions"]:
        candidate_id = direction["id"]
        if candidate_id in completed_ids:
            continue
        inputs = {
            "prompt": direction["krea_prompt"],
            "workflow_template": "krea2_low_vram",
            "aspect_preset": "portrait_9_16",
            "seed": direction["seed"],
            "steps": config["cover_selection"].get("steps", 8),
            "output_path": str(cover_dir / f"{candidate_id}.png"),
        }
        manifest["assets"].append(_execute_candidate(
            tool=image, inputs=inputs, candidate_id=candidate_id, kind="cover_background", report_path=report_path
        ))
        dump_json(manifest_path, manifest)

    for frame in config.get("style_frames", []):
        candidate_id = frame["id"]
        if candidate_id in completed_ids:
            continue
        inputs = {
            "prompt": frame["prompt"],
            "workflow_template": "krea2_low_vram",
            "aspect_preset": "portrait_9_16",
            "seed": frame["seed"],
            "steps": frame.get("steps", 8),
            "output_path": str(style_dir / f"{candidate_id}.png"),
        }
        manifest["assets"].append(_execute_candidate(
            tool=image, inputs=inputs, candidate_id=candidate_id, kind="style_frame", report_path=report_path
        ))
        dump_json(manifest_path, manifest)

    for motion in config.get("motion_tests", []):
        candidate_id = motion["id"]
        if candidate_id in completed_ids:
            continue
        reference = style_dir / f"{motion['reference_style_frame']}.png"
        inputs = {
            "prompt": motion["prompt"],
            "workflow_template": "wan22_i2v_q6",
            "reference_image_path": str(reference),
            "aspect_preset": "portrait_9_16",
            "duration_seconds": motion.get("duration_seconds", 4),
            "seed": motion["seed"],
            "output_path": str(video_dir / f"{candidate_id}.mp4"),
        }
        manifest["assets"].append(_execute_candidate(
            tool=video, inputs=inputs, candidate_id=candidate_id, kind="motion_test", report_path=report_path
        ))
        dump_json(manifest_path, manifest)

    report = load_json(report_path)
    report.update({"status": "generated_local_copy_pending_finalize", "gpu_generation_completed_at": utc_now()})
    report["summary"] = _event_summary(report.get("events", []))
    dump_json(report_path, report)
    return {"manifest": str(manifest_path), "gpu_report": str(report_path), "assets": len(manifest["assets"])}


def regenerate_style_frames(
    config: dict[str, Any],
    *,
    frame_ids: list[str],
    projects_dir: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    """Replace rejected style frames while retaining the originals for review."""

    frames = {frame["id"]: frame for frame in config.get("style_frames", [])}
    unknown = sorted(set(frame_ids) - set(frames))
    if unknown:
        raise ValueError(f"Unknown style frame ids: {', '.join(unknown)}")
    target = project_dir(config, projects_dir)
    report_path = target / "artifacts" / "gpu_usage_report.json"
    manifest_path = target / "artifacts" / "candidate_asset_manifest.json"
    ensure_gpu_preflight(report_path)
    manifest = load_json(manifest_path)
    image = ComfyUIImage()
    style_dir = target / "assets" / "images" / "style_frames"
    rejected_dir = target / "review" / "rejected" / "style_frames_v1"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    os.environ["COMFYUI_REMOTE_ASSET_POLICY"] = "retain_until_batch_end"

    replacements = []
    for candidate_id in frame_ids:
        frame = frames[candidate_id]
        output = style_dir / f"{candidate_id}.png"
        old_asset = next((a for a in manifest["assets"] if a["id"] == candidate_id), None)
        if output.is_file():
            shutil.copy2(output, rejected_dir / output.name)
        if old_asset:
            rejected = dict(old_asset)
            rejected["review_status"] = "rejected_quality"
            rejected["rejection_reason"] = "model-generated pseudo subtitles; text belongs in Remotion"
            rejected["archived_path"] = str(rejected_dir / output.name)
            manifest.setdefault("rejected_assets", []).append(rejected)
        inputs = {
            "prompt": frame["prompt"],
            "workflow_template": "krea2_low_vram",
            "aspect_preset": "portrait_9_16",
            "seed": frame["seed"],
            "steps": frame.get("steps", 8),
            "output_path": str(output),
        }
        replacement = _execute_candidate(
            tool=image,
            inputs=inputs,
            candidate_id=candidate_id,
            kind="style_frame",
            report_path=report_path,
            retry_count=1,
        )
        replacement["review_status"] = "pending_review"
        manifest["assets"] = [a for a in manifest["assets"] if a["id"] != candidate_id]
        manifest["assets"].append(replacement)
        replacements.append(replacement)
        dump_json(manifest_path, manifest)
    return {
        "replaced": [item["id"] for item in replacements],
        "rejected_archive": str(rejected_dir),
        "manifest": str(manifest_path),
    }


def generate_additional_voice_test(
    config: dict[str, Any],
    *,
    candidate_id: str,
    projects_dir: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    tests = {item["id"]: item for item in config["voice_selection"].get("additional_tests", [])}
    if candidate_id not in tests:
        raise ValueError(f"Unknown additional voice test: {candidate_id}")
    target = project_dir(config, projects_dir)
    report_path = target / "artifacts" / "gpu_usage_report.json"
    manifest_path = target / "artifacts" / "candidate_asset_manifest.json"
    ensure_gpu_preflight(report_path)
    candidate = tests[candidate_id]
    audio_dir = target / "assets" / "audio" / "voice_candidates"
    audio_dir.mkdir(parents=True, exist_ok=True)
    output = audio_dir / f"{candidate_id}.mp3"
    inputs = {
        "text": config["voice_selection"]["sample_text"],
        "workflow_template": "qwen3_tts_voice_design",
        "output_path": str(output),
        "instruct": candidate["instruct"],
        "language": "Chinese",
        "seed": candidate["seed"],
        **config["voice_selection"]["inference"],
    }
    os.environ["COMFYUI_REMOTE_ASSET_POLICY"] = "retain_until_batch_end"
    asset = _execute_candidate(
        tool=ComfyUITTS(),
        inputs=inputs,
        candidate_id=candidate_id,
        kind="voice_prompt_test",
        report_path=report_path,
    )
    manifest = load_json(manifest_path)
    manifest["assets"] = [item for item in manifest["assets"] if item["id"] != candidate_id]
    manifest["assets"].append(asset)
    dump_json(manifest_path, manifest)
    return {"candidate_id": candidate_id, "path": str(output), "manifest": str(manifest_path)}


def generate_formal_narration(
    config: dict[str, Any],
    *,
    projects_dir: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    """Generate the selected A07 narration while retaining remote batch assets."""

    target = project_dir(config, projects_dir)
    report_path = target / "artifacts" / "gpu_usage_report.json"
    ensure_gpu_preflight(report_path)
    voice_profile = load_json(target / "artifacts" / "brand_profiles" / "voice_profile_v1.json")
    script = load_json(target / "artifacts" / "script.json")
    main_voice = voice_profile["main"]
    narration_text = " ".join(
        section.get("delivery_cues", {}).get("provider_text", section["text"])
        for section in script["sections"]
    )
    output_dir = target / "assets" / "audio" / "narration"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"narration_{main_voice['id']}_raw.mp3"
    inputs = {
        "text": narration_text,
        "workflow_template": "qwen3_tts_voice_design",
        "output_path": str(output),
        "instruct": main_voice["instruct"],
        "language": "Chinese",
        "seed": main_voice["seed"],
        **config["voice_selection"]["inference"],
    }
    os.environ["COMFYUI_REMOTE_ASSET_POLICY"] = "retain_until_batch_end"
    asset = _execute_candidate(
        tool=ComfyUITTS(),
        inputs=inputs,
        candidate_id=f"narration-{main_voice['id']}",
        kind="formal_narration",
        report_path=report_path,
    )
    asset["text"] = narration_text
    asset["voice_profile"] = {
        "id": main_voice["id"],
        "name": main_voice["name"],
        "seed": main_voice["seed"],
        "instruct": main_voice["instruct"],
    }
    manifest_path = target / "artifacts" / "formal_narration_manifest.json"
    dump_json(
        manifest_path,
        {
            "version": "1.0",
            "project_id": config["project_id"],
            "status": "generated_pending_normalization_and_review",
            "asset": asset,
        },
    )
    report = load_json(report_path)
    report["status"] = "formal_narration_generated_gpu_retained"
    report["formal_narration_generated_at"] = utc_now()
    report["summary"] = _event_summary(report.get("events", []))
    dump_json(report_path, report)
    return {
        "voice": main_voice["id"],
        "path": str(output),
        "duration_seconds": asset.get("duration_seconds"),
        "manifest": str(manifest_path),
    }


def generate_article_visual_assets(
    config: dict[str, Any],
    *,
    projects_dir: Path = PROJECTS_DIR,
    include_images: bool = True,
    include_videos: bool = True,
    run_preflight: bool = True,
) -> dict[str, Any]:
    target = project_dir(config, projects_dir)
    report_path = target / "artifacts" / "gpu_usage_report.json"
    if run_preflight:
        ensure_gpu_preflight(report_path)
    report = load_json(report_path)
    report["status"] = "article_visual_batch_running"
    report["article_visual_generation_started_at"] = utc_now()
    dump_json(report_path, report)
    os.environ["COMFYUI_REMOTE_ASSET_POLICY"] = "retain_until_batch_end"

    image_dir = target / "assets" / "images" / "article"
    video_dir = target / "assets" / "video" / "article"
    image_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target / "artifacts" / "article_visual_manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {
        "version": "1.0",
        "project_id": config["project_id"],
        "text_policy": config["article_visual_assets"]["text_policy"],
        "technical_guardrails": config["article_visual_assets"].get("technical_guardrails", []),
        "assets": [],
    }
    completed_ids = {asset["id"] for asset in manifest["assets"]}
    image_tool = ComfyUIImage()
    video_tool = ComfyUIVideo()

    for item in config["article_visual_assets"]["images"] if include_images else []:
        if item["id"] in completed_ids:
            continue
        inputs = {
            "prompt": item["prompt"],
            "workflow_template": "krea2_low_vram",
            "aspect_preset": "portrait_9_16",
            "seed": item["seed"],
            "steps": item.get("steps", 4),
            "output_path": str(image_dir / f"{item['id']}.png"),
        }
        asset = _execute_candidate(
            tool=image_tool,
            inputs=inputs,
            candidate_id=item["id"],
            kind="article_image",
            report_path=report_path,
        )
        asset["prompt_review"] = item["prompt_review"]
        manifest["assets"].append(asset)
        completed_ids.add(item["id"])
        dump_json(manifest_path, manifest)

    video_items = config["article_visual_assets"]["videos"]
    wan_policy_report: dict[str, Any] | None = None
    if include_videos:
        video_items, wan_policy_report = resolve_wan_generation_plan_for_project(config, target)
        if wan_policy_report:
            dump_json(target / "artifacts" / "wan_selection_plan.json", wan_policy_report)

    for item in video_items if include_videos else []:
        if item["id"] in completed_ids:
            continue
        reference_id = item["reference"]
        if reference_id.startswith("P"):
            reference_path = image_dir / f"{reference_id}.png"
        elif reference_id.startswith("S"):
            reference_path = target / "assets" / "images" / "style_frames" / f"{reference_id}.png"
        else:
            raise ValueError(f"Unsupported article video reference: {reference_id}")
        if not reference_path.is_file():
            raise FileNotFoundError(reference_path)
        inputs = {
            "prompt": item["prompt"],
            "workflow_template": "wan22_i2v_q6",
            "reference_image_path": str(reference_path),
            "aspect_preset": "portrait_9_16",
            "duration_seconds": item.get("duration_seconds", 4),
            "seed": item["seed"],
            "output_path": str(video_dir / f"{item['id']}.mp4"),
        }
        asset = _execute_candidate(
            tool=video_tool,
            inputs=inputs,
            candidate_id=item["id"],
            kind="article_video",
            report_path=report_path,
        )
        asset["reference_asset_id"] = reference_id
        asset["prompt_review"] = item["prompt_review"]
        manifest["assets"].append(asset)
        completed_ids.add(item["id"])
        dump_json(manifest_path, manifest)

    report = load_json(report_path)
    report["status"] = "article_visual_batch_generated_pending_review"
    report["article_visual_generation_completed_at"] = utc_now()
    report["summary"] = _event_summary(report.get("events", []))
    dump_json(report_path, report)
    return {
        "manifest": str(manifest_path),
        "images": len([a for a in manifest["assets"] if a["type"] == "article_image"]),
        "videos": len([a for a in manifest["assets"] if a["type"] == "article_video"]),
    }


def _gpu_is_online() -> bool:
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", "autodl-comfyui", "true"],
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    return result.returncode == 0


def cover_props(config: dict[str, Any], direction: dict[str, Any], public_prefix: str) -> dict[str, Any]:
    layout = direction["layout"]
    return {
        "backgroundSrc": f"{public_prefix}/backgrounds/{direction['id']}.png",
        "chineseTitle": config["cover_selection"]["chinese_title"],
        "englishTitle": config["cover_selection"]["english_title"],
        "brand": "树精灵",
        "titlePosition": layout["title_position"],
        "textAlign": layout["text_align"],
        "textColor": layout["text_color"],
        "accentColor": layout["accent_color"],
        "overlayOpacity": layout["overlay_opacity"],
        "gradientDirection": layout["gradient_direction"],
        "chineseFontSrc": f"{public_prefix}/fonts/LiyuXingkai.ttf",
    }


def render_covers_local(
    config: dict[str, Any],
    *,
    projects_dir: Path = PROJECTS_DIR,
    allow_gpu_online: bool = False,
) -> dict[str, Any]:
    if _gpu_is_online() and not allow_gpu_online:
        raise RuntimeError("AutoDL is still online; finalize and shut down the GPU batch before local composition")
    target = project_dir(config, projects_dir)
    source_dir = target / "assets" / "images" / "cover_backgrounds"
    output_dir = target / "assets" / "images" / "cover_candidates"
    public_prefix = f"{config['project_id']}/cover"
    public_dir = REPO_ROOT / "remotion-composer" / "public" / public_prefix
    backgrounds_public = public_dir / "backgrounds"
    fonts_public = public_dir / "fonts"
    backgrounds_public.mkdir(parents=True, exist_ok=True)
    fonts_public.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    font_source = REPO_ROOT / "fronts" / "漓雨手书_100font" / "LiyuXingkai.ttf"
    if not font_source.is_file():
        raise FileNotFoundError(font_source)
    shutil.copy2(font_source, fonts_public / "LiyuXingkai.ttf")

    outputs = []
    for direction in config["cover_selection"]["directions"]:
        background = source_dir / f"{direction['id']}.png"
        if not background.is_file():
            raise FileNotFoundError(background)
        shutil.copy2(background, backgrounds_public / background.name)
        output = output_dir / f"{direction['id']}.png"
        props = cover_props(config, direction, public_prefix)
        subprocess.run(
            [
                "npx", "remotion", "still", "src/index.tsx", "TreeElfCover", str(output),
                "--props", json.dumps(props, ensure_ascii=False), "--image-format", "png",
            ],
            cwd=REPO_ROOT / "remotion-composer",
            check=True,
        )
        outputs.append({"id": direction["id"], "path": str(output), "sha256": sha256_file(output)})
    dump_json(target / "artifacts" / "cover_render_report.json", {"rendered_at": utc_now(), "outputs": outputs})
    shutil.rmtree(public_dir)
    return {"cover_candidates": len(outputs), "output_dir": str(output_dir)}


def select_profiles(
    config: dict[str, Any],
    *,
    voice_main: str,
    voice_backup: str,
    cover: str,
    projects_dir: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    voice_items = config["voice_selection"]["candidates"] + config["voice_selection"].get("additional_tests", [])
    voices = {item["id"]: item for item in voice_items}
    covers = {item["id"]: item for item in config["cover_selection"]["directions"]}
    if voice_main not in voices or voice_backup not in voices or voice_main == voice_backup:
        raise ValueError("Choose two distinct generated voice candidate ids")
    if cover not in covers:
        raise ValueError("Choose one cover id from C01..C12")
    target = project_dir(config, projects_dir)
    profiles = target / "artifacts" / "brand_profiles"
    profiles.mkdir(parents=True, exist_ok=True)
    voice_profile = {
        "version": "1.0",
        "status": "pending_30s_90s_stability_test",
        "main": voices[voice_main],
        "backup": voices[voice_backup],
        "persistence_policy": "reuse VoiceDesign instruct+seed; clone only if identity drift is material",
        "selected_at": utc_now(),
    }
    cover_profile = {
        "version": "1.0",
        "status": "approved_template",
        "selected_direction": covers[cover],
        "chinese_title_policy": "frontmatter.cover_title",
        "english_title_policy": "short reviewed translation",
        "brand": "树精灵",
        "composition": "TreeElfCover",
        "embed_frames": 1,
        "selected_at": utc_now(),
    }
    dump_json(profiles / "voice_profile_v1.json", voice_profile)
    dump_json(profiles / "cover_template_v1.json", cover_profile)
    dump_json(
        profiles / "visual_style_v1.json",
        {
            "version": "1.0",
            "status": "approved",
            "pipeline": "Canvas design → Krea text-free background → Remotion exact text",
            "selected_cover_direction": cover,
            "palette": covers[cover]["layout"],
            "profile": "tiktok",
            "brand": "树精灵",
            "subtitle_policy": "white with black outline inside portrait platform safe area",
            "motion_policy": "use Wan I2V only for approved key frames",
            "approved_at": utc_now(),
        },
    )
    dump_json(
        REPO_ROOT / "workflow_configs" / "zh-philosophy-video" / "treeelf-philosophy-brand-v1.json",
        {
            "version": "1.0",
            "source_project": config["project_id"],
            "profile": "tiktok",
            "render_runtime": "remotion",
            "composition_mode": "templated",
            "voice_profile_path": str(profiles / "voice_profile_v1.json"),
            "cover_template_path": str(profiles / "cover_template_v1.json"),
            "visual_style_path": str(profiles / "visual_style_v1.json"),
            "future_batch_policy": "one narration, one cover background, approved hero frames and Wan shots only",
        },
    )
    selected_cover = target / "assets" / "images" / "cover_candidates" / f"{cover}.png"
    if selected_cover.is_file():
        shutil.copy2(selected_cover, target / "assets" / "images" / "platform_cover.png")
    return {
        "voice_profile": str(profiles / "voice_profile_v1.json"),
        "cover_profile": str(profiles / "cover_template_v1.json"),
        "visual_style": str(profiles / "visual_style_v1.json"),
        "reusable_config": str(REPO_ROOT / "workflow_configs" / "zh-philosophy-video" / "treeelf-philosophy-brand-v1.json"),
    }


def status_report(config: dict[str, Any], *, projects_dir: Path = PROJECTS_DIR) -> dict[str, Any]:
    target = project_dir(config, projects_dir)
    report_path = target / "artifacts" / "gpu_usage_report.json"
    manifest_path = target / "artifacts" / "candidate_asset_manifest.json"
    report = load_json(report_path) if report_path.exists() else {"status": "not_prepared", "events": []}
    manifest = load_json(manifest_path) if manifest_path.exists() else {"assets": []}
    counts: dict[str, int] = {}
    for asset in manifest.get("assets", []):
        counts[asset["type"]] = counts.get(asset["type"], 0) + 1
    return {
        "project_id": config["project_id"],
        "prepared": (target / "project.json").exists(),
        "gpu_online": _gpu_is_online(),
        "gpu_status": report.get("status"),
        "asset_counts": counts,
        "expected_asset_counts": {"voice_candidate": 10, "cover_background": 12, "style_frame": 3, "motion_test": 1},
        "cover_candidates_rendered": len(list((target / "assets" / "images" / "cover_candidates").glob("C*.png"))),
        "profiles_selected": (target / "artifacts" / "brand_profiles" / "cover_template_v1.json").exists(),
    }


def write_gpu_baseline(report_path: Path) -> Path:
    report = load_json(report_path)
    baseline_path = report_path.parent / "brand_profiles" / "gpu_baseline_v1.json"
    dump_json(
        baseline_path,
        {
            "version": "1.0",
            "source_report": str(report_path),
            "total_managed_session_seconds": report.get("total_managed_session_seconds"),
            "effective_generation_seconds": report.get("summary", {}).get("effective_generation_seconds"),
            "average_seconds_by_kind": report.get("summary", {}).get("average_seconds_by_kind", {}),
            "finalization_seconds": report.get("finalization_seconds"),
            "created_at": utc_now(),
        },
    )
    return baseline_path


def finalize_gpu_batch(config: dict[str, Any], *, yes: bool, shutdown: bool) -> int:
    command = [
        str(REPO_ROOT / ".venv" / "bin" / "python"),
        str(REPO_ROOT / "scripts" / "finalize_autodl_comfyui_batch.py"),
        "--project-dir", str(project_dir(config)),
        "--policy", str(REPO_ROOT / config["retention_policy"]),
    ]
    if yes:
        command.append("--yes")
    else:
        command.append("--dry-run")
    if shutdown:
        if not yes:
            raise ValueError("--shutdown requires --yes")
        command.append("--shutdown")
    target = project_dir(config)
    report_path = target / "artifacts" / "gpu_usage_report.json"
    started = time.monotonic()
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    if report_path.exists():
        report = load_json(report_path)
        report["finalization_seconds"] = round(time.monotonic() - started, 2)
        report["finalization_completed_at"] = utc_now()
        report["finalization_exit_code"] = result.returncode
        if yes and shutdown and result.returncode == 0:
            report["status"] = "finalized_remote_cleaned_gpu_shutdown"
            report["gpu_session_finished_at"] = utc_now()
            session_start = report.get("gpu_session_started_at")
            if session_start:
                started_dt = datetime.fromisoformat(session_start)
                report["total_managed_session_seconds"] = round(
                    (datetime.now(timezone.utc) - started_dt).total_seconds(), 2
                )
        dump_json(report_path, report)
        if yes and shutdown and result.returncode == 0:
            write_gpu_baseline(report_path)
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TreeElf philosophy brand-selection workflow")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    scan = sub.add_parser("scan")
    scan.add_argument("--inbox", type=Path, default=DEFAULT_INBOX)
    sub.add_parser("prepare")
    sub.add_parser("generate-gpu")
    regenerate = sub.add_parser("regenerate-style-frames")
    regenerate.add_argument("--ids", nargs="+", required=True)
    voice_test = sub.add_parser("generate-voice-test")
    voice_test.add_argument("--id", required=True)
    sub.add_parser("generate-formal-narration")
    sub.add_parser("generate-article-visuals")
    render = sub.add_parser("render-covers")
    render.add_argument(
        "--allow-gpu-online",
        action="store_true",
        help="Render locally while AutoDL remains online after explicit user approval.",
    )
    sub.add_parser("status")
    final = sub.add_parser("finalize-gpu")
    final.add_argument("--yes", action="store_true")
    final.add_argument("--shutdown", action="store_true")
    select = sub.add_parser("select")
    select.add_argument("--voice-main", required=True)
    select.add_argument("--voice-backup", required=True)
    select.add_argument("--cover", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_json(args.config)
    if args.command == "validate":
        errors = validate_config(config)
        print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1 if errors else 0)
    if args.command == "scan":
        result = scan_inbox(args.inbox)
    elif args.command == "prepare":
        result = prepare_project(config)
    elif args.command == "generate-gpu":
        result = generate_gpu_candidates(config)
    elif args.command == "regenerate-style-frames":
        result = regenerate_style_frames(config, frame_ids=args.ids)
    elif args.command == "generate-voice-test":
        result = generate_additional_voice_test(config, candidate_id=args.id)
    elif args.command == "generate-formal-narration":
        result = generate_formal_narration(config)
    elif args.command == "generate-article-visuals":
        result = generate_article_visual_assets(config)
    elif args.command == "render-covers":
        result = render_covers_local(config, allow_gpu_online=args.allow_gpu_online)
    elif args.command == "status":
        result = status_report(config)
    elif args.command == "finalize-gpu":
        raise SystemExit(finalize_gpu_batch(config, yes=args.yes, shutdown=args.shutdown))
    elif args.command == "select":
        result = select_profiles(
            config,
            voice_main=args.voice_main,
            voice_backup=args.voice_backup,
            cover=args.cover,
        )
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
