#!/usr/bin/env python3
"""Execute one reviewed TreeElf fable GPU manifest group with resumable logging."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import treeelf_fable_batch as fable
from scripts.treeelf_philosophy_brand_pilot import dump_json, load_json
from tools.audio.comfyui_tts import ComfyUITTS
from tools.graphics.comfyui_image import ComfyUIImage
from tools.video.comfyui_video import ComfyUIVideo


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tool(name: str) -> Any:
    if name == "comfyui_tts":
        return ComfyUITTS()
    if name == "comfyui_image":
        return ComfyUIImage()
    if name == "comfyui_video":
        return ComfyUIVideo()
    raise ValueError(f"unsupported fable GPU tool:{name}")


def _output_path(job: dict[str, Any]) -> Path | None:
    raw = str(job.get("inputs", {}).get("output_path") or "").strip()
    return Path(raw).expanduser() if raw else None


def _queue_snapshot() -> dict[str, Any]:
    server = os.environ.get("COMFYUI_SERVER_URL", "http://127.0.0.1:8188").rstrip("/")
    checked_at = utc_now()
    try:
        with urllib.request.urlopen(f"{server}/queue", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        running = len(payload.get("queue_running", []))
        pending = len(payload.get("queue_pending", []))
        return {
            "checked_at": checked_at,
            "reachable": True,
            "running": running,
            "pending": pending,
            "depth": running + pending,
        }
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {"checked_at": checked_at, "reachable": False, "error": str(exc)}


def _live_preflight(manifest_path: Path) -> dict[str, Any]:
    server = os.environ.get("COMFYUI_SERVER_URL", "http://127.0.0.1:8188").rstrip("/")
    health_checks: list[dict[str, Any]] = []
    for index in range(2):
        checked_at = utc_now()
        try:
            with urllib.request.urlopen(f"{server}/system_stats", timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            health_checks.append({"checked_at": checked_at, "ok": True, "payload": payload})
        except (OSError, ValueError, urllib.error.URLError) as exc:
            raise ConnectionError(f"ComfyUI repeated health preflight failed before submission:{exc}") from exc
        if index == 0:
            time.sleep(0.25)
    queue = _queue_snapshot()
    if not queue.get("reachable") or int(queue.get("depth", -1)) != 0:
        raise RuntimeError(f"ComfyUI queue must be reachable and empty before fable batch:{queue}")
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "comfyui_workflow_preflight.py"),
        "--server",
        server,
        "--json",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=120)
    try:
        workflows = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"workflow preflight returned invalid JSON:{result.stdout[-1000:]}") from exc
    passed = sum(1 for row in workflows.values() if row.get("ok") is True)
    total = len(workflows)
    if result.returncode != 0 or total != 15 or passed != 15:
        raise RuntimeError(
            f"ComfyUI workflow preflight must pass 15/15 before generation: "
            f"passed={passed} total={total} stderr={result.stderr[-1000:]}"
        )
    report = {
        "version": "1.0",
        "server": server,
        "checked_at": utc_now(),
        "health_checks": health_checks,
        "queue": queue,
        "workflow_preflight": {"passed": passed, "total": total},
    }
    dump_json(manifest_path.parent / "gpu_live_preflight.json", report)
    return report


def _dependency_ready(job: dict[str, Any], all_jobs: dict[str, dict[str, Any]]) -> bool:
    dependency = str(job.get("depends_on", "")).strip()
    if not dependency:
        return True
    parent = all_jobs.get(dependency)
    if not parent or parent.get("status") != "complete":
        return False
    output = _output_path(parent)
    return bool(output and output.is_file() and output.stat().st_size > 0)


def _job_is_runnable(job: dict[str, Any], all_jobs: dict[str, dict[str, Any]]) -> bool:
    status = str(job.get("status", ""))
    if status in {"complete", "failed_optional"} or status.startswith("blocked_"):
        return False
    return _dependency_ready(job, all_jobs)


def execute_job(job: dict[str, Any]) -> dict[str, Any]:
    output = _output_path(job)
    if job.get("status") == "complete" and output and output.is_file() and output.stat().st_size > 0:
        return {"job_id": job["job_id"], "status": "skipped_existing", "output": str(output)}
    submitted_at = utc_now()
    inputs = dict(job["inputs"])
    inputs["workflow_template"] = job["workflow_template"]
    result = _tool(str(job["tool"])).execute(inputs)
    completed_at = utc_now()
    row = {
        "job_id": job["job_id"],
        "tool": job["tool"],
        "workflow_template": job["workflow_template"],
        "submitted_at": submitted_at,
        "completed_at": completed_at,
        "status": "succeeded" if result.success else "failed",
        "duration_seconds": result.duration_seconds,
        "artifacts": result.artifacts,
        "error": result.error,
        "data": result.data,
        "seed": result.seed,
        "model": result.model,
    }
    if result.success and output and (not output.is_file() or output.stat().st_size <= 0):
        row["status"] = "failed"
        row["error"] = f"tool reported success but output is missing:{output}"
    return row


def run_group(manifest_path: Path, group_id: str, *, workers: int = 2) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    group = next((item for item in manifest.get("gpu_groups", []) if item.get("id") == group_id), None)
    if group is None:
        raise KeyError(f"unknown GPU group:{group_id}")
    if group_id == "repairs":
        repair_counts: dict[str, int] = {}
        for job in group.get("jobs", []):
            repair_of = str(job.get("repair_of", "")).strip()
            attempt = int(job.get("repair_attempt", 0))
            if not repair_of or attempt != 1:
                raise ValueError("repair jobs require repair_of and repair_attempt=1")
            repair_counts[repair_of] = repair_counts.get(repair_of, 0) + 1
        repeated = [job_id for job_id, count in repair_counts.items() if count > 1]
        if repeated:
            raise ValueError(f"only one online repair attempt is allowed per asset:{repeated}")
    report_path = manifest_path.parent / "gpu_usage_report.json"
    report = load_json(report_path) if report_path.is_file() else {
        "version": "1.0",
        "batch_id": manifest.get("batch_id"),
        "started_at": utc_now(),
        "jobs": [],
    }
    all_jobs = {
        str(job.get("job_id")): job
        for manifest_group in manifest.get("gpu_groups", [])
        for job in manifest_group.get("jobs", [])
    }
    pending = [
        job for job in group.get("jobs", [])
        if not (
            job.get("status") == "complete"
            and _output_path(job)
            and _output_path(job).is_file()
            and _output_path(job).stat().st_size > 0
        )
        and _job_is_runnable(job, all_jobs)
    ]
    blocked = [
        job for job in group.get("jobs", [])
        if str(job.get("status", "")).startswith("blocked_")
        or (
            job.get("status") != "complete"
            and not _dependency_ready(job, all_jobs)
        )
    ]
    results: dict[str, dict[str, Any]] = {}
    queue_samples: list[dict[str, Any]] = []
    queue_idle_alerts: list[dict[str, Any]] = []
    eligible_empty_seconds = 0
    group_started_at = utc_now()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 2))) as executor:
        futures = {executor.submit(execute_job, job): job for job in pending}
        remaining = set(futures)
        while remaining:
            done, remaining = wait(remaining, timeout=15, return_when=FIRST_COMPLETED)
            snapshot = _queue_snapshot()
            snapshot["eligible_jobs_waiting"] = len(remaining)
            queue_samples.append(snapshot)
            if snapshot.get("reachable") and snapshot.get("depth") == 0 and remaining:
                eligible_empty_seconds += 15
                if eligible_empty_seconds >= 60 and eligible_empty_seconds % 60 == 0:
                    queue_idle_alerts.append(
                        {
                            "detected_at": snapshot["checked_at"],
                            "empty_seconds": eligible_empty_seconds,
                            "eligible_jobs_waiting": len(remaining),
                            "reason": "ComfyUI queue empty while submitted worker futures remain active",
                        }
                    )
            else:
                eligible_empty_seconds = 0
            for future in done:
                job = futures[future]
                try:
                    row = future.result()
                except Exception as exc:
                    row = {
                        "job_id": job["job_id"],
                        "tool": job["tool"],
                        "workflow_template": job["workflow_template"],
                        "completed_at": utc_now(),
                        "status": "failed",
                        "duration_seconds": 0,
                        "artifacts": [],
                        "error": str(exc),
                        "data": {},
                    }
                results[job["job_id"]] = row
                report["jobs"].append(row)
                dump_json(report_path, report)

    failures: list[str] = []
    for job in group.get("jobs", []):
        row = results.get(job["job_id"])
        if row is None:
            continue
        if row["status"] == "succeeded":
            job["status"] = "complete"
            job["completed_at"] = row["completed_at"]
            job["duration_seconds"] = row["duration_seconds"]
            job["artifacts"] = row["artifacts"]
        elif job.get("optional") is True:
            job["status"] = "failed_optional"
            job["error"] = row.get("error")
            job["fallback"] = job.get("failure_policy", "skip_optional_asset")
        else:
            job["status"] = "failed"
            job["error"] = row.get("error")
            failures.append(f"{job['job_id']}:{row.get('error')}")
    if not failures and not blocked:
        group["completed_at"] = utc_now()
    group_event = {
        "group_id": group_id,
        "started_at": group_started_at,
        "completed_at": utc_now(),
        "runnable_jobs": len(pending),
        "blocked_jobs": len(blocked),
        "queue_samples": queue_samples,
        "queue_idle_alerts": queue_idle_alerts,
    }
    report.setdefault("group_events", []).append(group_event)
    dump_json(report_path, report)
    manifest["last_gpu_group"] = group_id
    manifest["last_gpu_group_updated_at"] = utc_now()
    dump_json(manifest_path, manifest)
    if failures:
        raise RuntimeError("fable GPU group failed:\n- " + "\n- ".join(failures))
    return {
        "batch_id": manifest.get("batch_id"),
        "group_id": group_id,
        "completed": len(results),
        "skipped_existing": len(group.get("jobs", [])) - len(pending),
        "blocked": len(blocked),
        "blocked_job_ids": [job["job_id"] for job in blocked],
        "report": str(report_path),
    }


def _manifest_group(manifest: dict[str, Any], group_id: str) -> dict[str, Any]:
    group = next((item for item in manifest.get("gpu_groups", []) if item.get("id") == group_id), None)
    if group is None:
        raise KeyError(f"unknown GPU group:{group_id}")
    return group


def _pending_character_projects(manifest: dict[str, Any]) -> list[str]:
    return sorted({
        str(job.get("project_id"))
        for job in _manifest_group(manifest, "scene_images_flux").get("jobs", [])
        if job.get("status") == "blocked_character_review"
    })


def _usage_summary(report: dict[str, Any], scheduler_started_at: str) -> dict[str, Any]:
    scheduler_start = datetime.fromisoformat(scheduler_started_at)
    succeeded = [
        row for row in report.get("jobs", [])
        if row.get("status") == "succeeded"
        and row.get("submitted_at")
        and row.get("completed_at")
        and datetime.fromisoformat(row["submitted_at"]) >= scheduler_start
    ]
    intervals = sorted(
        (
            datetime.fromisoformat(row["submitted_at"]),
            datetime.fromisoformat(row["completed_at"]),
        )
        for row in succeeded
    )
    starts = [pair[0] for pair in intervals]
    first_prompt_delay = (
        (min(starts) - datetime.fromisoformat(scheduler_started_at)).total_seconds()
        if starts else None
    )
    busy_seconds = 0.0
    idle_seconds = 0.0
    cursor = None
    for start, end in intervals:
        if cursor is None:
            cursor = start
        if start > cursor:
            idle_seconds += (start - cursor).total_seconds()
        if end > cursor:
            busy_seconds += (end - max(start, cursor)).total_seconds()
            cursor = end
    total = busy_seconds + idle_seconds
    current_events = [
        event for event in report.get("group_events", [])
        if event.get("started_at")
        and datetime.fromisoformat(event["started_at"]) >= scheduler_start
    ]
    group_switch_seconds = 0.0
    previous_end: datetime | None = None
    for event in current_events:
        start = datetime.fromisoformat(event["started_at"])
        if previous_end is not None and start > previous_end:
            group_switch_seconds += (start - previous_end).total_seconds()
        if event.get("completed_at"):
            previous_end = datetime.fromisoformat(event["completed_at"])
    return {
        "first_prompt_submission_delay_seconds": round(first_prompt_delay, 3) if first_prompt_delay is not None else None,
        "first_prompt_target_seconds": 90,
        "first_prompt_within_target": first_prompt_delay is not None and first_prompt_delay <= 90,
        "effective_generation_seconds": round(busy_seconds, 3),
        "inter_job_idle_seconds": round(idle_seconds, 3),
        "group_switch_and_cpu_planning_seconds": round(group_switch_seconds, 3),
        "model_load_time_measurement": "included in individual ComfyUI job duration; not separately observable from the current API",
        "avoidable_idle_ratio": round(idle_seconds / total, 4) if total else 0.0,
        "target_avoidable_idle_ratio": 0.10,
        "queue_watchdog_interval_seconds": 15,
        "queue_idle_alert_seconds": 60,
    }


def run_gpu_batch(
    manifest_path: Path,
    batch_config: Path,
    series_path: Path,
    *,
    workers: int = 2,
) -> dict[str, Any]:
    """Continuously advance every currently eligible fable GPU job."""

    scheduler_started_at = utc_now()
    batch = load_json(batch_config)
    series = load_json(series_path)
    projects_root = manifest_path.parent.parent.parent
    manifest = load_json(manifest_path)
    if manifest.get("status") not in {
        "baseline_captured",
        "visual_jobs_queued",
        "waiting_character_review",
        "gpu_generation_complete",
    }:
        raise ValueError("capture-gpu-baseline must pass before run-gpu-batch")

    live_preflight = _live_preflight(manifest_path)

    stages: list[dict[str, Any]] = []
    if not any(group.get("id") == "repairs" for group in manifest.get("gpu_groups", [])):
        manifest.setdefault("gpu_groups", []).insert(-1, {
            "id": "repairs",
            "workflow": "mixed_explicit_repair",
            "jobs": [],
        })
        dump_json(manifest_path, manifest)
    for group_id in ("narration", "character_pack"):
        stages.append(run_group(manifest_path, group_id, workers=workers))

    refresh = fable.refresh_visuals(
        batch,
        batch_config,
        series,
        projects_root=projects_root,
    )
    stages.append({"group_id": "refresh_visuals", **refresh})

    # Krea work continues independently of the character review gate.  This
    # is the useful GPU work that fills the former online-review gap.
    for group_id in ("scene_images_krea", "covers"):
        stages.append(run_group(manifest_path, group_id, workers=workers))

    # Re-read reviews in case they were approved while the Krea queue ran.
    refresh = fable.refresh_visuals(
        batch,
        batch_config,
        series,
        projects_root=projects_root,
    )
    stages.append({"group_id": "refresh_character_gates", **refresh})
    stages.append(run_group(manifest_path, "scene_images_flux", workers=workers))
    stages.append(run_group(manifest_path, "repairs", workers=workers))
    stages.append(run_group(manifest_path, "wan", workers=workers))

    manifest = load_json(manifest_path)
    waiting = _pending_character_projects(manifest)
    report_path = manifest_path.parent / "gpu_usage_report.json"
    report = load_json(report_path) if report_path.is_file() else {"jobs": []}
    scheduler_record = {
        "version": "1.0",
        "started_at": scheduler_started_at,
        "updated_at": utc_now(),
        "status": "waiting_character_review" if waiting else "all_eligible_gpu_jobs_complete",
        "waiting_character_projects": waiting,
        "live_preflight": live_preflight,
        "stages": stages,
        "metrics": _usage_summary(report, scheduler_started_at),
    }
    report.setdefault("scheduler_runs", []).append(scheduler_record)
    report["scheduler"] = scheduler_record
    dump_json(report_path, report)
    manifest["gpu_scheduler"] = scheduler_record
    manifest["status"] = "waiting_character_review" if waiting else "gpu_generation_complete"
    manifest["next_action"] = (
        "approve each listed character_review.json, then rerun the same run-gpu-batch command"
        if waiting
        else "run verify-gpu-assets"
    )
    dump_json(manifest_path, manifest)
    return {
        "batch_id": manifest.get("batch_id"),
        "status": manifest["status"],
        "waiting_character_projects": waiting,
        "stages": stages,
        "metrics": scheduler_record["metrics"],
        "report": str(report_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--group")
    mode.add_argument("--all", action="store_true")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--series", type=Path, default=fable.DEFAULT_SERIES)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    manifest = args.manifest.expanduser().resolve()
    if args.all:
        if args.config is None:
            parser.error("--all requires --config")
        result = run_gpu_batch(
            manifest,
            args.config.expanduser().resolve(),
            args.series.expanduser().resolve(),
            workers=args.workers,
        )
    else:
        result = run_group(manifest, args.group, workers=args.workers)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
