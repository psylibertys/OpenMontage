#!/usr/bin/env python3
"""Prepare and run the memory-repair-shop GPU batch (story-to-storyboard acceptance).

Batch 1 scope: character turnaround sheets, 25 shot keyframes (Krea + Flux 4ref)
and narration TTS.  Generation reuses the fable GPU job executor
(`scripts.run_treeelf_fable_gpu_group.run_group`) so jobs are manifest-driven,
resumable and gated by per-character human review.  Video shots (FastH3 i2v)
belong to batch 2 and are configured after the H3 templates pass smoke test.

Commands
--------
prepare               Build gpu_batch_manifest_<batch>.json + retention_policy_<batch>.json (offline).
capture-gpu-baseline  Require empty remote queue, snapshot runtime files (GPU session).
run-gpu-batch         Advance narration -> character_pack -> krea -> (gates) -> flux.
cut-refs              Split each turnaround sheet into ref-01..04 + write default review.
approve <character>   Mark a character review approved after human inspection.
verify-gpu-assets     Offline QC: existence, size, SHA-256, TTS pacing vs plan.
status                Print manifest progress summary.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.finalize_autodl_comfyui_batch import (  # noqa: E402
    _require_empty_queue,
    remote_runtime_manifest,
)
from scripts.run_treeelf_fable_gpu_group import run_group  # noqa: E402
from scripts.treeelf_fable_batch import (  # noqa: E402
    TECHNICAL_GUARDRAILS,
    _append_guardrails,
    crop_character_turnaround_sheet,
    media_duration_seconds,
)

PROJECTS_ROOT = REPO_ROOT / "projects"
DEFAULT_CONFIG = REPO_ROOT / "workflow_configs" / "memory-repair-shop" / "batch-1.json"
FINALIZE_SCRIPT = REPO_ROOT / "scripts" / "finalize_autodl_comfyui_batch.py"

CHARACTER_CHECK_KEYS = (
    "same_identity_all_views",
    "four_distinct_views",
    "anatomy_acceptable",
    "no_text_or_pseudo_text",
)


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def project_root(config: dict[str, Any]) -> Path:
    return PROJECTS_ROOT / str(config["project_id"])


def manifest_path(config: dict[str, Any]) -> Path:
    return project_root(config) / "artifacts" / f"gpu_batch_manifest_{config['batch_id']}.json"


def _apply_prompt_adaptations(
    prompt: str,
    scene_key: str,
    adaptations: dict[str, dict[str, str]],
) -> tuple[str, bool]:
    entry = adaptations.get(scene_key)
    if not entry:
        return prompt, False
    needle = entry["from"]
    if needle not in prompt:
        raise ValueError(f"prompt adaptation for {scene_key} no longer matches the storyboard prompt")
    return prompt.replace(needle, entry["to"]), True


def _scene_key(export_scene: dict[str, Any]) -> str:
    return str(export_scene["scene_plan_scene_id"])


def prepare(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    if "video" in config:
        return prepare_video_batch(config, config_path)
    return prepare_still_batch(config, config_path)


def prepare_still_batch(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    export = load_json(REPO_ROOT / str(config["storyboard_export"]))
    root = project_root(config)
    routing = {str(k): str(v) for k, v in config.get("scene_routing", {}).items()}
    adaptations = {str(k): v for k, v in config.get("prompt_adaptations", {}).items()}
    packs = {str(pack["character_id"]): pack for pack in config["character_packs"]}

    scenes = list(export["scenes"])
    scene_keys = {_scene_key(scene) for scene in scenes}
    errors: list[str] = []
    if len(scenes) != int(config["metadata"]["shot_count"]):
        errors.append(f"storyboard shot count {len(scenes)} != configured {config['metadata']['shot_count']}")
    # v1 storyboard is narration-driven; the v2 drama-form rework (2026-10-13)
    # drops narration entirely and speaks through dialogue + overlay captions.
    narration_mode = bool(str(export.get("narration_all", "")).strip())

    pack_bindings: dict[str, str] = {}
    for pack_id, pack in packs.items():
        for scene in pack["binding_scenes"]:
            if scene in pack_bindings:
                errors.append(f"scene {scene} bound to two character packs")
            pack_bindings[scene] = pack_id

    adapted_prompts: dict[str, tuple[str, bool]] = {}
    for scene in scenes:
        key = _scene_key(scene)
        workflow = routing.get(key, config["gpu"]["ordinary_image_workflow"])
        if workflow == config["gpu"]["character_image_workflow"] and key not in pack_bindings:
            errors.append(f"scene {key} routed to flux2_klein_4ref but has no character pack binding")
        if workflow != config["gpu"]["character_image_workflow"] and key in pack_bindings:
            errors.append(f"scene {key} has a pack binding but is not routed to flux")
        if narration_mode and not str(scene.get("narration", "")).strip():
            errors.append(f"scene {key} narration is empty")
        dialogue = scene.get("dialogue")
        if dialogue is not None:
            if not narration_mode and not str(scene.get("narration", "")).strip() and not str(dialogue.get("line", "")).strip():
                errors.append(f"scene {key} has neither narration nor dialogue")
            for field in ("character_id", "line", "delivery"):
                if not str(dialogue.get(field, "")).strip():
                    errors.append(f"scene {key} dialogue.{field} is empty")
            if str(dialogue.get("mode", "")) not in {"lip_sync", "voice_over"}:
                errors.append(f"scene {key} dialogue.mode must be lip_sync or voice_over")
        if not str(scene.get("t2i_prompt", "")).strip():
            errors.append(f"scene {key} t2i_prompt is empty")
        if float(scene.get("duration_seconds", 0)) <= 0:
            errors.append(f"scene {key} duration must be positive")
        adapted_prompts[key] = _apply_prompt_adaptations(str(scene["t2i_prompt"]), key, adaptations)
    unknown_routes = set(routing) - scene_keys
    if unknown_routes:
        errors.append(f"scene_routing references unknown scenes: {sorted(unknown_routes)}")
    if errors:
        raise SystemExit("Invalid memory-repair-shop batch:\n- " + "\n- ".join(errors))

    aspect = str(config["aspect_preset"])
    voice_jobs: list[dict[str, Any]] = []
    voice_group_id = "narration"
    if narration_mode:
        voice = config["voice"]
        for scene in scenes:
            key = _scene_key(scene)
            index = int(scene["scene_id"])
            voice_jobs.append(
                {
                    "job_id": f"narration:scene-{index:02d}",
                    "tool": "comfyui_tts",
                    "workflow_template": voice["workflow_template"],
                    "inputs": {
                        "text": str(scene["narration"]),
                        "voice_name": voice["voice_name"],
                        "language": voice["language"],
                        "instruct": voice["instruct"],
                        "output_path": str(root / "assets" / "audio" / f"scene-{index:02d}.mp3"),
                    },
                    "planned_duration_seconds": float(scene["duration_seconds"]),
                    "status": "queued",
                }
            )
        voice_jobs.append(
            {
                "job_id": "narration:full",
                "tool": "comfyui_tts",
                "workflow_template": voice["workflow_template"],
                "inputs": {
                    "text": str(export["narration_all"]),
                    "voice_name": voice["voice_name"],
                    "language": voice["language"],
                    "instruct": voice["instruct"],
                    "output_path": str(root / "assets" / "audio" / "narration-full.mp3"),
                },
                "planned_duration_seconds": float(config["metadata"]["total_duration_seconds"]),
                "status": "queued",
            }
        )
    else:
        # v2 dialogue-driven sound design: the first line of each character is
        # synthesised with VoiceDesign (timbre + performance via instruct);
        # any further line reuses that take through VoiceCloneSave so one
        # character keeps one voice across shots.
        dialogue_cfg = config["dialogue"]
        voice_group_id = "dialogue_tts"
        first_line: dict[str, dict[str, str]] = {}
        for scene in scenes:
            dialogue = scene.get("dialogue")
            if not dialogue:
                continue
            character = str(dialogue["character_id"])
            index = int(scene["scene_id"])
            char_cfg = dialogue_cfg["characters"][character]
            output = str(root / "assets" / "audio" / "dialogue" / f"scene-{index:02d}.mp3")
            instruct = f"{char_cfg['voice_prompt']} 这一句的表演：{dialogue['delivery']}"
            common = {
                "tool": "comfyui_tts",
                "language": dialogue_cfg["language"],
                "seed": int(char_cfg["seed"]),
                "status": "queued",
                "character_id": character,
                "scene_key": _scene_key(scene),
                "delivery_mode": str(dialogue.get("mode", "voice_over")),
            }
            if character not in first_line:
                voice_jobs.append(
                    {
                        "job_id": f"dialogue:scene-{index:02d}",
                        "workflow_template": dialogue_cfg["workflow_single"],
                        "inputs": {
                            "text": str(dialogue["line"]),
                            "instruct": instruct,
                            "language": common["language"],
                            "seed": common["seed"],
                            "output_path": output,
                        },
                        **{k: v for k, v in common.items() if k not in {"language", "seed"}},
                    }
                )
                first_line[character] = {"job_id": f"dialogue:scene-{index:02d}", "text": str(dialogue["line"]), "output": output}
            else:
                reference = first_line[character]
                voice_jobs.append(
                    {
                        "job_id": f"dialogue:scene-{index:02d}",
                        "workflow_template": dialogue_cfg["workflow_clone"],
                        "inputs": {
                            "text": str(dialogue["line"]),
                            "instruct": instruct,
                            "reference_audio_path": reference["output"],
                            "reference_text": reference["text"],
                            "voice_name": f"{character}_v2",
                            "language": common["language"],
                            "seed": common["seed"],
                            "output_path": output,
                        },
                        **{k: v for k, v in common.items() if k not in {"language", "seed"}},
                        "depends_on": reference["job_id"],
                    }
                )
        unknown_chars = {
            str(scene["dialogue"]["character_id"])
            for scene in scenes if scene.get("dialogue")
        } - set(dialogue_cfg["characters"])
        if unknown_chars:
            raise SystemExit(f"dialogue characters missing from config: {sorted(unknown_chars)}")

    character_jobs: list[dict[str, Any]] = []
    for pack_id, pack in packs.items():
        character_jobs.append(
            {
                "job_id": f"{pack_id}:turnaround",
                "tool": "comfyui_image",
                "workflow_template": config["gpu"]["ordinary_image_workflow"],
                "inputs": {
                    "prompt": _append_guardrails(str(pack["turnaround_prompt"]), list(TECHNICAL_GUARDRAILS)),
                    "aspect_preset": aspect,
                    "output_path": str(root / "assets" / "images" / "character" / pack_id / "turnaround-sheet.png"),
                },
                "status": "queued",
            }
        )

    krea_jobs: list[dict[str, Any]] = []
    flux_jobs: list[dict[str, Any]] = []
    for scene in scenes:
        key = _scene_key(scene)
        index = int(scene["scene_id"])
        if scene.get("keep_keyframe_from_v1"):
            # Empty-scene stills survive the drama-form rework untouched;
            # the batch must not regenerate (or overwrite) them.
            output = root / "assets" / "images" / "scenes" / f"scene-{index:02d}.png"
            if not output.is_file():
                errors.append(f"scene {key} marked keep_keyframe_from_v1 but v1 still missing:{output}")
            continue
        prompt, adapted = adapted_prompts[key]
        workflow = routing.get(key, config["gpu"]["ordinary_image_workflow"])
        inputs: dict[str, Any] = {
            "prompt": prompt,
            "aspect_preset": aspect,
            "output_path": str(root / "assets" / "images" / "scenes" / f"scene-{index:02d}.png"),
        }
        if workflow == config["gpu"]["ordinary_image_workflow"]:
            inputs["prompt"] = _append_guardrails(prompt, list(TECHNICAL_GUARDRAILS))
            krea_jobs.append(
                {
                    "job_id": f"keyframe:scene-{index:02d}",
                    "tool": "comfyui_image",
                    "workflow_template": workflow,
                    "inputs": inputs,
                    "scene_key": key,
                    "prompt_adapted": adapted,
                    "status": "queued",
                }
            )
            continue
        pack_id = pack_bindings[key]
        character_root = root / "assets" / "images" / "character" / pack_id
        inputs["reference_image_paths"] = [str(character_root / f"ref-{position:02d}.png") for position in range(1, 5)]
        flux_jobs.append(
            {
                "job_id": f"keyframe:scene-{index:02d}",
                "tool": "comfyui_image",
                "workflow_template": workflow,
                "inputs": inputs,
                "scene_key": key,
                "prompt_adapted": adapted,
                "character_id": pack_id,
                "depends_on": f"{pack_id}:turnaround",
                "gate": {
                    "type": "character_review",
                    "character_id": pack_id,
                    "review_path": str(character_root / "character_review.json"),
                },
                "status": "blocked_character_review",
            }
        )
    if errors:
        raise SystemExit("Invalid memory-repair-shop batch:\n- " + "\n- ".join(errors))

    manifest = {
        "version": "1.0",
        "batch_id": config["batch_id"],
        "project_id": config["project_id"],
        "pipeline": config.get("pipeline"),
        "status": "prepared",
        "prepared_at": utc_now(),
        "config_path": str(config_path),
        "storyboard_export": config["storyboard_export"],
        "aspect_preset": aspect,
        "gpu_groups": [
            {"id": voice_group_id, "workflow": "comfyui_tts", "jobs": voice_jobs},
            {"id": "character_pack", "workflow": config["gpu"]["ordinary_image_workflow"], "jobs": character_jobs},
            {"id": "scene_images_krea", "workflow": config["gpu"]["ordinary_image_workflow"], "jobs": krea_jobs},
            {"id": "scene_images_flux", "workflow": config["gpu"]["character_image_workflow"], "jobs": flux_jobs},
        ],
        "next_action": "GPU session: start session script, upload voice pack, run comfyui_workflow_preflight, then capture-gpu-baseline",
    }
    dump_json(manifest_path(config), manifest)
    dump_json(
        root / "artifacts" / f"retention_policy_{config['batch_id']}.json",
        {
            "version": "1.0",
            "batch_id": config["batch_id"],
            "retain_project_assets": [],
            "notes": "capture-gpu-baseline fills retain_project_assets with the preexisting remote runtime files; batch assets download to projects/memory-repair-shop/assets before cleanup",
        },
    )
    return {
        "manifest": str(manifest_path(config)),
        "jobs": {
            voice_group_id: len(voice_jobs),
            "character_pack": len(character_jobs),
            "scene_images_krea": len(krea_jobs),
            "scene_images_flux": len(flux_jobs),
        },
        "keyframes_reused": [
            _scene_key(scene) for scene in scenes if scene.get("keep_keyframe_from_v1")
        ],
        "adapted_prompts": [key for key, (_, adapted) in adapted_prompts.items() if adapted],
    }


def capture_gpu_baseline(config_path: Path, ssh_host: str) -> dict[str, Any]:
    config = load_json(config_path)
    _require_empty_queue(ssh_host)
    rows = remote_runtime_manifest(ssh_host)
    policy_path = project_root(config) / "artifacts" / f"retention_policy_{config['batch_id']}.json"
    policy = load_json(policy_path)
    policy["retain_project_assets"] = [row["path"] for row in rows]
    policy["runtime_baseline_captured_at"] = utc_now()
    policy["runtime_baseline_file_count"] = len(rows)
    dump_json(policy_path, policy)
    path = manifest_path(config)
    manifest = load_json(path)
    manifest["status"] = "baseline_captured"
    manifest["gpu_window_started_at"] = utc_now()
    manifest["next_action"] = "run-gpu-batch; review turnaround sheets after character_pack completes"
    dump_json(path, manifest)
    return {"baseline_files": len(rows), "manifest": str(path)}


def _review_state(config: dict[str, Any], character_id: str) -> tuple[bool, Path]:
    review_path = project_root(config) / "assets" / "images" / "character" / character_id / "character_review.json"
    if not review_path.is_file():
        return False, review_path
    review = load_json(review_path)
    checks_ok = all(review.get("checks", {}).get(key) is True for key in CHARACTER_CHECK_KEYS)
    return review.get("approved") is True and checks_ok, review_path


def refresh_character_gates(config: dict[str, Any]) -> list[str]:
    """Unlock flux jobs whose turnaround completed and review passed; re-block the rest."""
    path = manifest_path(config)
    manifest = load_json(path)
    all_jobs = {
        str(job.get("job_id")): job
        for group in manifest.get("gpu_groups", [])
        for job in group.get("jobs", [])
    }
    waiting: list[str] = []
    for group in manifest.get("gpu_groups", []):
        if group["id"] != "scene_images_flux":
            continue
        for job in group["jobs"]:
            if job.get("status") == "complete":
                continue
            parent = all_jobs.get(str(job.get("depends_on", "")))
            parent_done = bool(parent and parent.get("status") == "complete")
            approved, _ = _review_state(config, str(job["character_id"]))
            if parent_done and approved:
                job["status"] = "queued"
            elif parent_done and not approved:
                job["status"] = "blocked_character_review"
                if str(job["character_id"]) not in waiting:
                    waiting.append(str(job["character_id"]))
    dump_json(path, manifest)
    return waiting


def prepare_video_batch(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    """Batch 2: FastH3 i2v two-stage (seed -> starred HD rerun) + enhancements."""
    export = load_json(REPO_ROOT / str(config["storyboard_export"]))
    root = project_root(config)
    video = config["video"]
    two_stage = video["two_stage"]
    base_seed = int(config.get("base_seed", 20261013))

    seed_jobs: list[dict[str, Any]] = []
    hd_jobs: list[dict[str, Any]] = []
    lip_sync_cfg = video.get("dialogue_shots", {}).get("lip_sync", {})
    lip_scenes = {str(key) for key in lip_sync_cfg.get("scenes", [])}
    margin = float(lip_sync_cfg.get("duration_margin_seconds", 1.0))
    lip_hd_side = int(two_stage["hd_pass"]["longest_side"])
    for scene in export["scenes"]:
        key = _scene_key(scene)
        index = int(scene["scene_id"])
        # v2 designs every shot at >=4s (the H3 minimum); generation length
        # equals design length instead of the old fixed seed/hd durations.
        duration = float(scene["duration_seconds"])
        common = {
            "prompt": str(scene["i2v_prompt"]),
            "operation": "image_to_video",
            "reference_image_path": str(root / "assets" / "images" / "scenes" / f"scene-{index:02d}.png"),
            "seed": base_seed + index,
        }
        if key in lip_scenes:
            # Lip-sync dialogue shots run the audio-sync template straight at
            # HD in a single pass; the TTS take must already exist (batch 3).
            audio = root / "assets" / "audio" / "dialogue" / f"scene-{index:02d}.mp3"
            if not audio.is_file():
                raise SystemExit(f"lip-sync scene {key} missing dialogue audio:{audio} (finish batch 3 first)")
            continue
        seed_jobs.append(
            {
                "job_id": f"vseed:scene-{index:02d}",
                "tool": "comfyui_video",
                "workflow_template": video["workflow_template"],
                "inputs": {
                    **common,
                    "duration_seconds": duration,
                    "longest_side": two_stage["seed_pass"]["longest_side"],
                    "output_path": str(root / "assets" / "videos" / "seed" / f"scene-{index:02d}.mp4"),
                },
                "scene_key": key,
                "status": "queued",
            }
        )
        hd_jobs.append(
            {
                "job_id": f"vhd:scene-{index:02d}",
                "tool": "comfyui_video",
                "workflow_template": video["workflow_template"],
                "inputs": {
                    **common,
                    "duration_seconds": duration,
                    "longest_side": two_stage["hd_pass"]["longest_side"],
                    "output_path": str(root / "assets" / "videos" / "hd" / f"scene-{index:02d}.mp4"),
                },
                "scene_key": key,
                "depends_on": f"vseed:scene-{index:02d}",
                "gate": {"type": "seed_selection", "scene_key": key},
                "status": "blocked_seed_review",
            }
        )

    lip_jobs: list[dict[str, Any]] = []
    for key in sorted(lip_scenes):
        index = int(key.rsplit("-", 1)[-1])
        audio = root / "assets" / "audio" / "dialogue" / f"scene-{index:02d}.mp3"
        duration = _scene_duration(export, index) + margin
        lip_jobs.append(
            {
                "job_id": f"dvideo:scene-{index:02d}",
                "tool": "comfyui_video",
                "workflow_template": str(lip_sync_cfg.get("workflow", "minimax_h3_audio_sync")),
                "inputs": {
                    "prompt": _scene_prompt(export, index),
                    "operation": "image_to_video",
                    "reference_image_path": str(root / "assets" / "images" / "scenes" / f"scene-{index:02d}.png"),
                    "reference_audio_path": str(audio),
                    "duration_seconds": duration,
                    "longest_side": lip_hd_side,
                    "seed": base_seed + index,
                    "output_path": str(root / "assets" / "videos" / "hd" / f"scene-{index:02d}.mp4"),
                },
                "scene_key": key,
                "status": "queued",
            }
        )

    enhancements: list[dict[str, Any]] = []
    for entry in config.get("shot_enhancements", []):
        if "scenes" in entry and entry.get("replace_with") == "minimax_h3_audio_sync":
            for key in entry["scenes"]:
                index = int(key.rsplit("-", 1)[-1])
                enhancements.append(
                    {
                        "job_id": f"enh:audio-sync-{index:02d}",
                        "tool": "comfyui_video",
                        "workflow_template": "minimax_h3_audio_sync",
                        "inputs": {
                            "prompt": _scene_prompt(export, index),
                            "operation": "image_to_video",
                            "reference_image_path": str(root / "assets" / "images" / "scenes" / f"scene-{index:02d}.png"),
                            "reference_audio_path": str(root / entry["audio_source"].format(nn=f"{index:02d}")),
                            "duration_seconds": entry["duration_seconds"][key],
                            "longest_side": two_stage["hd_pass"]["longest_side"],
                            "output_path": str(root / "assets" / "videos" / "enhanced" / f"scene-{index:02d}-audio-sync.mp4"),
                        },
                        "scene_key": key,
                        "status": "queued",
                    }
                )
        elif "transition" in entry:
            src = int(entry["transition"]["from"].rsplit("-", 1)[-1])
            dst = int(entry["transition"]["to"].rsplit("-", 1)[-1])
            enhancements.append(
                {
                    "job_id": f"enh:fflf-{src:02d}-{dst:02d}",
                    "tool": "comfyui_video",
                    "workflow_template": str(entry["workflow"]),
                    "inputs": {
                        "prompt": _scene_prompt(export, dst),
                        "operation": "image_to_video",
                        "reference_image_path": str(root / "assets" / "images" / "scenes" / f"scene-{src:02d}.png"),
                        "last_image_path": str(root / "assets" / "images" / "scenes" / f"scene-{dst:02d}.png"),
                        "duration_seconds": entry["duration_seconds"],
                        "longest_side": two_stage["hd_pass"]["longest_side"],
                        "output_path": str(root / "assets" / "videos" / "enhanced" / f"transition-{src:02d}-{dst:02d}.mp4"),
                    },
                    "scene_key": entry["transition"]["to"],
                    "status": "queued",
                }
            )

    manifest = {
        "version": "1.0",
        "batch_kind": "video",
        "batch_id": config["batch_id"],
        "project_id": config["project_id"],
        "pipeline": config.get("pipeline"),
        "status": "prepared",
        "prepared_at": utc_now(),
        "config_path": str(config_path),
        "storyboard_export": config["storyboard_export"],
        "gpu_groups": [
            {"id": "video_seed", "workflow": video["workflow_template"], "jobs": seed_jobs},
            {"id": "video_hd", "workflow": video["workflow_template"], "jobs": hd_jobs},
            {"id": "dialogue_video", "workflow": str(lip_sync_cfg.get("workflow", "minimax_h3_audio_sync")), "jobs": lip_jobs},
            {"id": "enhancements", "workflow": "minimax_h3_audio_sync / minimax_fasth3_fflf", "jobs": enhancements},
        ],
        "next_action": "GPU session: preflight, capture-gpu-baseline, then run-gpu-batch (seed pass first)",
    }
    dump_json(manifest_path(config), manifest)
    dump_json(
        root / "artifacts" / f"retention_policy_{config['batch_id']}.json",
        {
            "version": "1.0",
            "batch_id": config["batch_id"],
            "retain_project_assets": [],
            "notes": "batch 2 videos download to projects/memory-repair-shop/assets/videos before cleanup",
        },
    )
    return {
        "manifest": str(manifest_path(config)),
        "jobs": {
            "video_seed": len(seed_jobs),
            "video_hd": len(hd_jobs),
            "dialogue_video": len(lip_jobs),
            "enhancements": len(enhancements),
        },
    }


def _scene_duration(export: dict[str, Any], index: int) -> float:
    for scene in export["scenes"]:
        if int(scene["scene_id"]) == index:
            return float(scene["duration_seconds"])
    raise SystemExit(f"scene-{index:02d} not found in storyboard export")


def _scene_prompt(export: dict[str, Any], index: int) -> str:
    for scene in export["scenes"]:
        if int(scene["scene_id"]) == index:
            return str(scene["i2v_prompt"])
    raise SystemExit(f"scene-{index:02d} not found in storyboard export")


def _selection(config: dict[str, Any]) -> set[str]:
    path = project_root(config) / "artifacts" / "seed_selection.json"
    if not path.is_file():
        return set()
    return set(load_json(path).get("selected", []))


def star_scenes(config_path: Path, scene_keys: list[str]) -> dict[str, Any]:
    """Mark seed clips approved for the HD rerun pass."""
    config = load_json(config_path)
    path = project_root(config) / "artifacts" / "seed_selection.json"
    selected = sorted(set(scene_keys) | _selection(config))
    dump_json(path, {"selected": selected, "updated_at": utc_now()})
    waiting = refresh_seed_gates(config)
    return {"selected": selected, "still_waiting_seed_review": waiting}


def refresh_seed_gates(config: dict[str, Any]) -> list[str]:
    """Unlock HD jobs whose seed clip completed and was starred; re-block the rest."""
    path = manifest_path(config)
    manifest = load_json(path)
    all_jobs = {
        str(job.get("job_id")): job
        for group in manifest.get("gpu_groups", [])
        for job in group.get("jobs", [])
    }
    selected = _selection(config)
    waiting: list[str] = []
    for group in manifest.get("gpu_groups", []):
        if group["id"] != "video_hd":
            continue
        for job in group["jobs"]:
            if job.get("status") == "complete":
                continue
            parent = all_jobs.get(str(job.get("depends_on", "")))
            parent_done = bool(parent and parent.get("status") == "complete")
            if parent_done and str(job["scene_key"]) in selected:
                job["status"] = "queued"
            elif parent_done and str(job["scene_key"]) not in selected:
                job["status"] = "blocked_seed_review"
                if str(job["scene_key"]) not in waiting:
                    waiting.append(str(job["scene_key"]))
    dump_json(path, manifest)
    return waiting


def _run_video_batch(config: dict[str, Any], path: Path, workers: int) -> dict[str, Any]:
    manifest = load_json(path)
    if manifest.get("status") not in {"baseline_captured", "waiting_seed_review", "batch_2_running"}:
        raise SystemExit(f"manifest status must allow GPU work, got: {manifest.get('status')}")
    manifest["status"] = "batch_2_running"
    dump_json(path, manifest)

    stages = [run_group(path, "video_seed", workers=workers)]
    waiting = refresh_seed_gates(config)
    stages.append(run_group(path, "dialogue_video", workers=workers))
    stages.append(run_group(path, "enhancements", workers=workers))
    stages.append(run_group(path, "video_hd", workers=workers))
    waiting = refresh_seed_gates(config)

    manifest = load_json(path)
    manifest["status"] = "waiting_seed_review" if waiting else "batch_2_complete"
    manifest["next_action"] = (
        "review seed clips, run star <scene-keys>, then rerun run-gpu-batch for the HD pass"
        if waiting
        else "run verify-gpu-assets offline, then finalize-gpu --dry-run"
    )
    dump_json(path, manifest)
    return {
        "batch_id": manifest["batch_id"],
        "status": manifest["status"],
        "waiting_seed_review": waiting,
        "stages": stages,
    }


def run_gpu_batch_cmd(config_path: Path, workers: int) -> dict[str, Any]:
    config = load_json(config_path)
    path = manifest_path(config)
    manifest = load_json(path)
    if "video" in config:
        return _run_video_batch(config, path, workers)
    if manifest.get("status") not in {"baseline_captured", "waiting_character_review", "batch_1_running"}:
        raise SystemExit(f"manifest status must allow GPU work, got: {manifest.get('status')}")
    manifest["status"] = "batch_1_running"
    dump_json(path, manifest)

    group_ids = [group["id"] for group in manifest.get("gpu_groups", [])]
    voice_group = next((gid for gid in group_ids if gid in {"narration", "dialogue_tts"}), "narration")
    stages = [
        run_group(path, voice_group, workers=workers),
        run_group(path, "character_pack", workers=workers),
    ]
    waiting = refresh_character_gates(config)
    stages.append(run_group(path, "scene_images_krea", workers=workers))
    waiting = refresh_character_gates(config)
    stages.append(run_group(path, "scene_images_flux", workers=workers))
    waiting = refresh_character_gates(config)

    manifest = load_json(path)
    manifest["status"] = "waiting_character_review" if waiting else "batch_1_complete"
    manifest["next_action"] = (
        "inspect turnaround sheets, run cut-refs + approve, then rerun run-gpu-batch"
        if waiting
        else "run verify-gpu-assets offline, then finalize-gpu --dry-run"
    )
    dump_json(path, manifest)
    return {
        "batch_id": manifest["batch_id"],
        "status": manifest["status"],
        "waiting_character_review": waiting,
        "stages": stages,
    }


def cut_refs(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    results: dict[str, Any] = {}
    for pack in config["character_packs"]:
        pack_id = str(pack["character_id"])
        character_root = project_root(config) / "assets" / "images" / "character" / pack_id
        sheet = character_root / "turnaround-sheet.png"
        references = crop_character_turnaround_sheet(sheet, character_root)
        review_path = character_root / "character_review.json"
        review = {
            "version": "1.0",
            "character_id": pack_id,
            "approved": False,
            "reviewer": "",
            "reviewed_at": "",
            "contact_sheet": str(sheet),
            "reference_image_paths": references,
            "blocking_findings": [],
            "checks": {key: False for key in CHARACTER_CHECK_KEYS},
            "notes": "人审四视图：同一身份、四个有效不同视角、无严重人体错误、无可读文字。通过后运行 approve 命令释放对应 Flux 镜头。",
        }
        dump_json(review_path, review)
        results[pack_id] = {"references": references, "review": str(review_path)}
    return results


def approve_review(config_path: Path, character_id: str, reviewer: str, notes: str) -> dict[str, Any]:
    config = load_json(config_path)
    approved, review_path = _review_state(config, character_id)
    if approved:
        return {"character_id": character_id, "already_approved": True, "review": str(review_path)}
    if not review_path.is_file():
        raise SystemExit(f"no character_review.json for {character_id}; run cut-refs first")
    review = load_json(review_path)
    review["approved"] = True
    review["reviewer"] = reviewer or "user"
    review["reviewed_at"] = utc_now()
    review["checks"] = {key: True for key in CHARACTER_CHECK_KEYS}
    if notes:
        review["notes"] = notes
    dump_json(review_path, review)
    return {"character_id": character_id, "approved": True, "review": str(review_path)}


def verify_gpu_assets(config_path: Path) -> dict[str, Any]:
    """Offline QC after the GPU window: outputs exist, SHA-256 recorded, TTS pacing sane."""
    import hashlib

    config = load_json(config_path)
    path = manifest_path(config)
    manifest = load_json(path)
    report: list[dict[str, Any]] = []
    problems: list[str] = []
    for group in manifest.get("gpu_groups", []):
        for job in group.get("jobs", []):
            output = Path(str(job["inputs"].get("output_path", "")))
            row: dict[str, Any] = {"job_id": job["job_id"], "output": str(output)}
            if not output.is_file() or output.stat().st_size <= 0:
                row["status"] = "missing"
                problems.append(f"{job['job_id']} output missing:{output}")
            else:
                row["status"] = "ok"
                row["size_bytes"] = output.stat().st_size
                row["sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
                planned = job.get("planned_duration_seconds")
                if job["tool"] == "comfyui_tts" and planned:
                    actual = media_duration_seconds(output)
                    row["planned_seconds"] = planned
                    row["actual_seconds"] = round(actual, 2) if actual is not None else None
                    if actual is not None and actual > planned * 1.35:
                        row["pacing"] = "slow"
                        problems.append(f"{job['job_id']} TTS {actual:.1f}s exceeds plan {planned:.1f}s by >35%")
                    else:
                        row["pacing"] = "ok"
            report.append(row)
    dump_json(project_root(config) / "artifacts" / "gpu_asset_verification.json", {
        "version": "1.0",
        "batch_id": manifest.get("batch_id"),
        "verified_at": utc_now(),
        "problems": problems,
        "assets": report,
    })
    return {"checked": len(report), "problems": problems}


def status_cmd(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    path = manifest_path(config)
    if not path.is_file():
        return {"status": "not_prepared", "next_action": "run prepare"}
    manifest = load_json(path)
    groups = {
        group["id"]: {
            "total": len(group.get("jobs", [])),
            "complete": sum(1 for job in group.get("jobs", []) if job.get("status") == "complete"),
            "blocked": sum(1 for job in group.get("jobs", []) if str(job.get("status", "")).startswith("blocked_")),
        }
        for group in manifest.get("gpu_groups", [])
    }
    return {
        "batch_id": manifest.get("batch_id"),
        "status": manifest.get("status"),
        "groups": groups,
        "next_action": manifest.get("next_action"),
    }


def finalize_gpu(config_path: Path, *, dry_run: bool, yes: bool, shutdown: bool) -> int:
    config = load_json(config_path)
    command = [
        sys.executable,
        str(FINALIZE_SCRIPT),
        "--project-dir",
        str(project_root(config)),
        "--policy",
        str(project_root(config) / "artifacts" / f"retention_policy_{config['batch_id']}.json"),
        "--ssh-host",
        str(config.get("ssh_host", "autodl-comfyui")),
    ]
    if dry_run:
        command.append("--dry-run")
    else:
        if not yes:
            raise SystemExit("finalize requires --yes (or --dry-run to preview)")
        command.append("--yes")
        if shutdown:
            command.append("--shutdown")
    return subprocess.run(command).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    capture = sub.add_parser("capture-gpu-baseline")
    capture.add_argument("--ssh-host", default=None)
    run = sub.add_parser("run-gpu-batch")
    run.add_argument("--workers", type=int, default=None)
    sub.add_parser("cut-refs")
    star = sub.add_parser("star")
    star.add_argument("scene_keys", nargs="+")
    approve = sub.add_parser("approve")
    approve.add_argument("character_id")
    approve.add_argument("--reviewer", default="user")
    approve.add_argument("--notes", default="")
    sub.add_parser("verify-gpu-assets")
    sub.add_parser("status")
    finalize = sub.add_parser("finalize-gpu")
    finalize.add_argument("--dry-run", action="store_true")
    finalize.add_argument("--yes", action="store_true")
    finalize.add_argument("--shutdown", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config_path = args.config.expanduser().resolve()
    if args.command == "prepare":
        result = prepare(config_path)
    elif args.command == "capture-gpu-baseline":
        config = load_json(config_path)
        result = capture_gpu_baseline(config_path, args.ssh_host or str(config.get("ssh_host", "autodl-comfyui")))
    elif args.command == "run-gpu-batch":
        config = load_json(config_path)
        result = run_gpu_batch_cmd(config_path, int(args.workers or config.get("queue_depth", 2)))
    elif args.command == "cut-refs":
        result = cut_refs(config_path)
    elif args.command == "star":
        result = star_scenes(config_path, args.scene_keys)
    elif args.command == "approve":
        result = approve_review(config_path, args.character_id, args.reviewer, args.notes)
    elif args.command == "verify-gpu-assets":
        result = verify_gpu_assets(config_path)
    elif args.command == "status":
        result = status_cmd(config_path)
    elif args.command == "finalize-gpu":
        raise SystemExit(finalize_gpu(config_path, dry_run=args.dry_run, yes=args.yes, shutdown=args.shutdown))
    else:  # pragma: no cover
        raise SystemExit(f"unknown command:{args.command}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
