#!/usr/bin/env python3
"""Batch GPU asset production for the TreeElf philosophy series.

Creative decisions remain in reviewed episode JSON files.  This module only
coordinates deterministic lifecycle operations: reserve prepared episodes,
keep a shallow rolling ComfyUI queue grouped by model family, verify every
downloaded asset, hand off all episodes to local post-production, and invoke
the audited cleanup/shutdown gate.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.paths import PROJECTS_DIR
from scripts.treeelf_philosophy_brand_pilot import (
    dump_json,
    ensure_gpu_preflight,
    generate_article_visual_assets,
    load_json,
    parse_markdown,
    sha256_file,
)
from scripts.treeelf_philosophy_episode import (
    DEFAULT_SERIES_CONFIG,
    build_exact_captions,
    generate_narration,
    prepare_episode,
    stage_remotion,
    utc_now,
    validate_episode,
)
from scripts.finalize_autodl_comfyui_batch import remote_runtime_manifest

DEFAULT_BATCH_CONFIG = (
    REPO_ROOT / "workflow_configs" / "zh-philosophy-video" / "treeelf-batch-template.json"
)


def _resolve_config_paths(batch_config_path: Path, payload: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for value in payload.get("episode_configs", []):
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = (batch_config_path.parent / path).resolve()
        paths.append(path)
    return paths


def _batch_dir(batch: dict[str, Any], projects_dir: Path = PROJECTS_DIR) -> Path:
    return projects_dir / str(batch["batch_id"])


def _manifest_path(batch: dict[str, Any], projects_dir: Path = PROJECTS_DIR) -> Path:
    return _batch_dir(batch, projects_dir) / "artifacts" / "batch_manifest.json"


def validate_batch(
    batch: dict[str, Any], batch_config_path: Path, series: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    batch_id = str(batch.get("batch_id", ""))
    if not batch_id.startswith("treeelf-batch-"):
        errors.append("batch_id must start with treeelf-batch-")
    config_paths = _resolve_config_paths(batch_config_path, batch)
    if not 1 <= len(config_paths) <= 8:
        errors.append("episode_configs must contain between 1 and 8 episodes")
    queue_depth = int(batch.get("queue_depth", series.get("gpu", {}).get("queue_depth", 2)))
    if queue_depth != 2:
        errors.append("queue_depth must be 2 for the approved rolling GPU batch")
    project_ids: list[str] = []
    source_paths: list[str] = []
    for path in config_paths:
        if not path.is_file():
            errors.append(f"missing episode config:{path}")
            continue
        episode = load_json(path)
        project_ids.append(str(episode.get("project_id")))
        source_paths.append(str(episode.get("source_script_md")))
        errors.extend(f"{path.name}:{error}" for error in validate_episode(episode, series))
    if len(project_ids) != len(set(project_ids)):
        errors.append("episode project_id values must be unique")
    if len(source_paths) != len(set(source_paths)):
        errors.append("episode source_script_md values must be unique")
    return errors


def _load_episodes(
    batch: dict[str, Any], batch_config_path: Path
) -> list[tuple[Path, dict[str, Any]]]:
    return [(path, load_json(path)) for path in _resolve_config_paths(batch_config_path, batch)]


def prepare_batch(
    batch: dict[str, Any], batch_config_path: Path, series: dict[str, Any], *,
    projects_dir: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    errors = validate_batch(batch, batch_config_path, series)
    if errors:
        raise ValueError("Invalid TreeElf batch:\n- " + "\n- ".join(errors))
    target = _batch_dir(batch, projects_dir)
    for path in (target / "assets", target / "artifacts", target / "renders"):
        path.mkdir(parents=True, exist_ok=True)
    episodes = []
    for config_path, config in _load_episodes(batch, batch_config_path):
        prepared = prepare_episode(config, series, projects_dir=projects_dir)
        metadata, _ = parse_markdown(Path(config["source_script_md"]))
        episodes.append({
            "asset_id": str(metadata.get("asset_id") or Path(config["source_script_md"]).stem),
            "project_id": config["project_id"],
            "config_path": str(config_path),
            "source_path": str(Path(config["source_script_md"]).resolve()),
            "source_sha256": prepared["source_sha256"],
            "status": "prepared",
        })
    manifest = {
        "version": "1.0",
        "workflow": "treeelf_philosophy_gpu_batch",
        "batch_id": batch["batch_id"],
        "status": "prepared",
        "queue_depth": 2,
        "model_group_order": ["qwen3_tts_voice_clone_load", "krea2_low_vram", "wan22_i2v_q6"],
        "created_at": utc_now(),
        "episodes": episodes,
    }
    dump_json(_manifest_path(batch, projects_dir), manifest)
    dump_json(target / "project.json", {
        "version": "1.0",
        "project_id": batch["batch_id"],
        "title": f"树精灵GPU批次 {batch['batch_id']}",
        "pipeline": "animated-explainer",
        "status": "prepared",
        "created_at": utc_now(),
    })
    policy = {
        "project_id": batch["batch_id"],
        "decision": "review_before_each_batch",
        "retain_infrastructure": [
            "/root/ComfyUI-Easy-Install/ComfyUI",
            "/root/autodl-tmp/comfyui-models",
            "/root/autodl-tmp/comfyui-runtime/validation",
        ],
        "retain_project_assets": [],
        "backup_then_delete_runtime_types": ["input", "output", "temp"],
        "backup_then_delete_voice_files": [],
        "delete_gate": "Mac backup exists and local/remote size and SHA-256 match",
        "shutdown_gate": "queue empty, backup verified, cleanup verified, no pending failures",
    }
    policy_path = target / "artifacts" / "retention_policy.json"
    dump_json(policy_path, policy)
    report_path = target / "artifacts" / "gpu_usage_report.json"
    dump_json(report_path, {
        "version": "1.0",
        "batch_id": batch["batch_id"],
        "status": "prepared_gpu_not_started",
        "events": [],
        "created_at": utc_now(),
    })
    return {"batch_dir": str(target), "manifest": str(_manifest_path(batch, projects_dir)), "retention_policy": str(policy_path), "episodes": len(episodes)}


def gpu_plan(
    batch: dict[str, Any], batch_config_path: Path, series: dict[str, Any]
) -> dict[str, Any]:
    baseline = series.get("gpu_baseline", {"image_seconds": 12.4, "wan_seconds": 137.72, "narration_segment_seconds": 34.92})
    rows = []
    totals = {"narration_segments": 0, "images": 0, "wan_clips": 0}
    for _, config in _load_episodes(batch, batch_config_path):
        _, body = parse_markdown(Path(config["source_script_md"]))
        narration = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("#")).strip()
        paragraphs = len([part for part in narration.split("\n\n") if part.strip()])
        images = len(config["article_visual_assets"]["images"])
        videos = len(config["article_visual_assets"]["videos"])
        totals["narration_segments"] += paragraphs
        totals["images"] += images
        totals["wan_clips"] += videos
        rows.append({"project_id": config["project_id"], "narration_segments": paragraphs, "images": images, "wan_clips": videos})
    effective = (
        totals["narration_segments"] * float(baseline["narration_segment_seconds"])
        + totals["images"] * float(baseline["image_seconds"])
        + totals["wan_clips"] * float(baseline["wan_seconds"])
    )
    return {"batch_id": batch["batch_id"], "episodes": rows, "totals": totals, "estimated_effective_gpu_seconds": round(effective, 2), "estimated_effective_gpu_minutes": round(effective / 60, 1), "queue_depth": 2}


def _run_rolling_stage(
    episodes: list[tuple[Path, dict[str, Any]]],
    worker: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    completed: dict[str, Any] = {}
    failures: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(worker, config): config["project_id"] for _, config in episodes}
        for future in as_completed(futures):
            project_id = futures[future]
            try:
                completed[project_id] = future.result()
            except Exception as exc:  # preserve other in-flight job, then stop before next stage
                failures[project_id] = str(exc)
    if failures:
        raise RuntimeError("GPU batch stage failed: " + json.dumps(failures, ensure_ascii=False))
    return completed


def _verify_episode_assets(config: dict[str, Any], projects_dir: Path) -> list[dict[str, Any]]:
    target = projects_dir / config["project_id"]
    expected = [target / "assets" / "audio" / "narration.wav"]
    expected.extend(target / "assets" / "images" / "article" / f"{item['id']}.png" for item in config["article_visual_assets"]["images"])
    expected.extend(target / "assets" / "video" / "article" / f"{item['id']}.mp4" for item in config["article_visual_assets"]["videos"])
    rows = []
    for path in expected:
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(f"Missing GPU batch deliverable: {path}")
        rows.append({"path": str(path), "size": path.stat().st_size, "sha256": sha256_file(path)})
    return rows


def generate_gpu_batch(
    batch: dict[str, Any], batch_config_path: Path, series: dict[str, Any], *,
    projects_dir: Path = PROJECTS_DIR,
    ssh_host: str = "autodl-comfyui",
) -> dict[str, Any]:
    manifest_path = _manifest_path(batch, projects_dir)
    if not manifest_path.is_file():
        raise FileNotFoundError("Run prepare before generate-gpu")
    target = _batch_dir(batch, projects_dir)
    report_path = target / "artifacts" / "gpu_usage_report.json"
    ensure_gpu_preflight(report_path)
    baseline = remote_runtime_manifest(ssh_host)
    policy_path = target / "artifacts" / "retention_policy.json"
    policy = load_json(policy_path)
    policy["retain_project_assets"] = [row["path"] for row in baseline]
    policy["runtime_baseline_captured_at"] = utc_now()
    policy["runtime_baseline_file_count"] = len(baseline)
    policy["cleanup_scope"] = "Only files created after this empty-queue batch baseline"
    dump_json(policy_path, policy)
    dump_json(
        target / "artifacts" / "remote_runtime_baseline.json",
        {"version": "1.0", "captured_at": utc_now(), "ssh_host": ssh_host, "files": baseline},
    )
    manifest = load_json(manifest_path)
    manifest["status"] = "gpu_running"
    manifest["gpu_started_at"] = utc_now()
    for episode in manifest["episodes"]:
        episode["status"] = "gpu_running"
    dump_json(manifest_path, manifest)
    episodes = _load_episodes(batch, batch_config_path)

    stages = {
        "narration": _run_rolling_stage(
            episodes,
            lambda config: generate_narration(config, series, projects_dir=projects_dir, run_preflight=False),
        ),
        "captions": [
            {
                "project_id": config["project_id"],
                **build_exact_captions(config, projects_dir=projects_dir),
            }
            for _, config in episodes
        ],
        "images": _run_rolling_stage(
            episodes,
            lambda config: generate_article_visual_assets(config, projects_dir=projects_dir, include_images=True, include_videos=False, run_preflight=False),
        ),
        "wan": _run_rolling_stage(
            episodes,
            lambda config: generate_article_visual_assets(config, projects_dir=projects_dir, include_images=False, include_videos=True, run_preflight=False),
        ),
    }
    inventory = []
    for _, config in episodes:
        rows = _verify_episode_assets(config, projects_dir)
        inventory.append({"project_id": config["project_id"], "assets": rows})
    dump_json(target / "artifacts" / "gpu_asset_inventory.json", {"version": "1.0", "verified_at": utc_now(), "episodes": inventory})
    manifest = load_json(manifest_path)
    manifest["status"] = "local_pending"
    manifest["gpu_completed_at"] = utc_now()
    manifest["next_action"] = "review retention dry-run, finalize with shutdown, then run local Whisper/Remotion"
    for episode in manifest["episodes"]:
        episode["status"] = "local_pending"
    dump_json(manifest_path, manifest)
    return {"batch_id": batch["batch_id"], "status": "local_pending", "stages": stages, "inventory": str(target / "artifacts" / "gpu_asset_inventory.json")}


def finalize_command(
    batch: dict[str, Any], *, projects_dir: Path, dry_run: bool, yes: bool,
    shutdown: bool, ssh_host: str = "autodl-comfyui",
) -> dict[str, Any]:
    target = _batch_dir(batch, projects_dir)
    manifest_path = _manifest_path(batch, projects_dir)
    inventory_path = target / "artifacts" / "gpu_asset_inventory.json"
    if not manifest_path.is_file() or not inventory_path.is_file():
        raise FileNotFoundError("GPU asset inventory is incomplete; refusing cleanup or shutdown")
    manifest = load_json(manifest_path)
    if manifest.get("status") != "local_pending":
        raise ValueError("Batch must be local_pending before cleanup or shutdown")
    if shutdown and (dry_run or not yes):
        raise ValueError("Shutdown requires the reviewed non-dry-run form: --yes --shutdown")
    command = [
        str(REPO_ROOT / ".venv" / "bin" / "python"),
        str(REPO_ROOT / "scripts" / "finalize_autodl_comfyui_batch.py"),
        "--project-dir", str(target),
        "--policy", str(target / "artifacts" / "retention_policy.json"),
        "--ssh-host", ssh_host,
    ]
    if dry_run:
        command.append("--dry-run")
    if yes:
        command.append("--yes")
    if shutdown:
        command.append("--shutdown")
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    if yes and not dry_run:
        manifest["status"] = "gpu_finalized"
        manifest["gpu_finalized_at"] = utc_now()
        manifest["remote_cleanup_completed"] = True
        manifest["shutdown_requested"] = shutdown
        manifest["next_action"] = "run local Whisper, Remotion, QC, and delivery"
        dump_json(manifest_path, manifest)
    return {"command": command, "output": result.stdout.strip(), "status": manifest["status"]}


def cleanup_batch_local_storage(
    batch: dict[str, Any],
    series: dict[str, Any],
    *,
    projects_dir: Path = PROJECTS_DIR,
    dry_run: bool = True,
    yes: bool = False,
    retention_days: int | None = None,
) -> dict[str, Any]:
    """Delete aged remote-final-backup copies only after every episode is delivered."""

    if not dry_run and not yes:
        raise ValueError("Batch local cleanup requires --yes after reviewing --dry-run")
    target = _batch_dir(batch, projects_dir).resolve()
    manifest_path = _manifest_path(batch, projects_dir)
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = load_json(manifest_path)
    if manifest.get("status") != "delivered" or not manifest.get("episodes"):
        raise ValueError("Every episode must be delivered before batch backup cleanup")
    for episode in manifest["episodes"]:
        report = projects_dir / episode["project_id"] / "artifacts" / "delivery_report.json"
        if episode.get("status") != "delivered" or not report.is_file():
            raise ValueError(f"Missing verified episode delivery: {episode['project_id']}")
        output = Path(load_json(report)["output"])
        if not output.is_file():
            raise FileNotFoundError(f"Delivered Movies file is missing: {output}")

    days = int(
        retention_days
        if retention_days is not None
        else series.get("local_storage", {}).get("delayed_cleanup_days", 7)
    )
    if days < 0:
        raise ValueError("retention_days must be non-negative")
    backup_root = (target / "assets" / "remote-final-backup").resolve()
    expected_parent = (target / "assets").resolve()
    if backup_root.parent != expected_parent:
        raise ValueError(f"Unsafe remote-final-backup path: {backup_root}")
    now = datetime.now(timezone.utc)
    candidates = []
    if backup_root.is_dir():
        for path in sorted(item for item in backup_root.iterdir() if item.is_dir()):
            age_days = (now - datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)).total_seconds() / 86400
            if age_days >= days:
                size = sum(item.lstat().st_size for item in path.rglob("*") if item.is_file() or item.is_symlink())
                candidates.append({
                    "path": str(path),
                    "bytes": size,
                    "age_days": round(age_days, 2),
                    "reason": "All episodes delivered and local backup grace period expired",
                })
    deleted = []
    if not dry_run:
        for item in candidates:
            path = Path(item["path"])
            if path.parent != backup_root:
                raise ValueError(f"Unsafe batch backup cleanup target: {path}")
            shutil.rmtree(path)
            deleted.append(item)
    result = {
        "version": "1.0",
        "batch_id": batch["batch_id"],
        "dry_run": dry_run,
        "retention_days": days,
        "targets": candidates,
        "deleted": deleted,
        "bytes_reclaimable": sum(item["bytes"] for item in candidates),
        "checked_at": utc_now(),
    }
    dump_json(target / "artifacts" / "local_batch_storage_cleanup_report.json", result)
    return result


def stage_local_batch(
    batch: dict[str, Any],
    batch_config_path: Path,
    series: dict[str, Any],
    *,
    projects_dir: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    """Stage every episode sequentially so music diversity is batch-aware."""

    manifest_path = _manifest_path(batch, projects_dir)
    if not manifest_path.is_file():
        raise FileNotFoundError("Run prepare before stage-local")
    manifest = load_json(manifest_path)
    if manifest.get("status") not in {"local_pending", "gpu_finalized", "local_staged"}:
        raise ValueError("Batch must have complete local GPU assets before stage-local")
    used_music_paths: list[str] = []
    results: list[dict[str, Any]] = []
    for _, config in _load_episodes(batch, batch_config_path):
        staged = stage_remotion(
            config,
            series,
            projects_dir=projects_dir,
            used_music_paths=used_music_paths,
        )
        selection = load_json(Path(staged["music_selection"]))
        selected_path = str(selection.get("selected", {}).get("path", ""))
        if selected_path:
            used_music_paths.append(selected_path)
        results.append({
            "project_id": config["project_id"],
            "music_path": selected_path,
            "props": staged["props"],
            "public_dir": staged["public_dir"],
        })
    manifest["status"] = "local_staged"
    manifest["local_staged_at"] = utc_now()
    manifest["next_action"] = "render, QC, and deliver every staged episode"
    for episode in manifest.get("episodes", []):
        episode["status"] = "local_staged"
    dump_json(manifest_path, manifest)
    return {
        "batch_id": batch["batch_id"],
        "status": "local_staged",
        "episodes": results,
        "used_music_paths": used_music_paths,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TreeElf rolling GPU asset batch")
    parser.add_argument("command", choices=("validate", "prepare", "gpu-plan", "generate-gpu", "stage-local", "status", "finalize-gpu", "cleanup-local"))
    parser.add_argument("--config", type=Path, default=DEFAULT_BATCH_CONFIG)
    parser.add_argument("--series", type=Path, default=DEFAULT_SERIES_CONFIG)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--shutdown", action="store_true")
    parser.add_argument("--ssh-host", default="autodl-comfyui")
    parser.add_argument("--retention-days", type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    batch = load_json(args.config)
    series = load_json(args.series)
    errors = validate_batch(batch, args.config, series)
    if args.command == "validate":
        result: Any = {"valid": not errors, "errors": errors}
    elif errors:
        raise SystemExit("Invalid batch:\n- " + "\n- ".join(errors))
    elif args.command == "prepare":
        result = prepare_batch(batch, args.config, series)
    elif args.command == "gpu-plan":
        result = gpu_plan(batch, args.config, series)
    elif args.command == "generate-gpu":
        result = generate_gpu_batch(batch, args.config, series, ssh_host=args.ssh_host)
    elif args.command == "finalize-gpu":
        result = finalize_command(
            batch,
            projects_dir=PROJECTS_DIR,
            dry_run=args.dry_run,
            yes=args.yes,
            shutdown=args.shutdown,
            ssh_host=args.ssh_host,
        )
    elif args.command == "cleanup-local":
        if not args.dry_run and not args.yes:
            raise SystemExit("cleanup-local requires --dry-run or --yes")
        result = cleanup_batch_local_storage(
            batch,
            series,
            projects_dir=PROJECTS_DIR,
            dry_run=args.dry_run,
            yes=args.yes,
            retention_days=args.retention_days,
        )
    elif args.command == "stage-local":
        result = stage_local_batch(batch, args.config, series, projects_dir=PROJECTS_DIR)
    else:
        path = _manifest_path(batch)
        result = load_json(path) if path.is_file() else {"batch_id": batch["batch_id"], "status": "not_prepared"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
