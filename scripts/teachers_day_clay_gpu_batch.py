#!/usr/bin/env python3
"""Resumable GPU batch runner for the teachers-day-clay-bouquet project.

Executes the reviewed window-1 job manifest (krea2 stills + cover + Qwen3-TTS
voice_design narration) against the AutoDL ComfyUI server, with live preflight,
per-job resume, a usage report, and a local SHA-256 inventory for the finalize
step. Reuses the execution helpers of the fable GPU group runner so both
runners share identical server contracts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_treeelf_fable_gpu_group import (  # noqa: E402
    _output_path,
    _queue_snapshot,
    execute_job,
)
from scripts.treeelf_philosophy_brand_pilot import dump_json, load_json  # noqa: E402

KNOWN_TOOLS = {"comfyui_image", "comfyui_tts", "comfyui_video"}
KNOWN_TEMPLATES = {
    "krea2_low_vram",
    "krea2_extra_pass",
    "z_image_turbo_gguf",
    "flux2_klein_4ref",
    "flux2_klein_inpaint",
    "seedvr2_upscale",
    "qwen3_tts_custom_voice",
    "qwen3_tts_voice_design",
    "qwen3_tts_voice_clone_save",
    "qwen3_tts_voice_clone_load",
    "wan22_i2v_q6",
}
REQUIRED_JOB_FIELDS = ("job_id", "tool", "workflow_template", "status", "inputs")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def live_preflight(manifest_path: Path) -> dict[str, Any]:
    """Health x2 + empty queue + preflight of every workflow the manifest needs.

    Unlike the fable runner's 15/15 gate, non-required workflows may fail when
    the hot set is a deliberate subset (two-window hot-set plan); every
    workflow_template referenced by the manifest must still pass.
    """
    server = os.environ.get("COMFYUI_SERVER_URL", "http://127.0.0.1:8188").rstrip("/")
    manifest = load_json(manifest_path)
    needed = sorted(
        {
            str(job["workflow_template"])
            for group in manifest.get("gpu_groups", [])
            for job in group.get("jobs", [])
        }
    )
    health_checks: list[dict[str, Any]] = []
    for index in range(2):
        checked_at = utc_now()
        try:
            with urllib.request.urlopen(f"{server}/system_stats", timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            health_checks.append({"checked_at": checked_at, "ok": True, "payload": payload})
        except (OSError, ValueError, urllib.error.URLError) as exc:
            raise ConnectionError(
                f"ComfyUI repeated health preflight failed before submission:{exc}"
            ) from exc
        if index == 0:
            time.sleep(0.25)
    queue = _queue_snapshot()
    if not queue.get("reachable") or int(queue.get("depth", -1)) != 0:
        raise RuntimeError(f"ComfyUI queue must be reachable and empty before batch:{queue}")
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
        raise RuntimeError(
            f"workflow preflight returned invalid JSON:{result.stdout[-1000:]}"
        ) from exc
    failed_needed = [
        name for name in needed if not workflows.get(name, {}).get("ok") is True
    ]
    report = {
        "version": "1.0",
        "server": server,
        "checked_at": utc_now(),
        "health_checks": health_checks,
        "queue": queue,
        "workflow_preflight": {
            "required": needed,
            "failed_required": failed_needed,
            "required_results": {name: bool(workflows.get(name, {}).get("ok")) for name in needed},
            "passed_total": sum(1 for row in workflows.values() if row.get("ok") is True),
            "total": len(workflows),
        },
    }
    dump_json(manifest_path.parent / "gpu_live_preflight.json", report)
    if failed_needed:
        raise RuntimeError(f"required workflows failed preflight:{failed_needed}")
    return report


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """Offline manifest checks; returns a list of human-readable errors."""
    errors: list[str] = []
    groups = manifest.get("gpu_groups", [])
    if not groups:
        errors.append("manifest has no gpu_groups")
    seen_ids: set[str] = set()
    for group in groups:
        group_id = group.get("id")
        if not group_id:
            errors.append("a gpu_group is missing id")
            continue
        jobs = group.get("jobs", [])
        if not jobs:
            errors.append(f"group {group_id} has no jobs")
        for job in jobs:
            job_id = job.get("job_id", "<missing>")
            for field in REQUIRED_JOB_FIELDS:
                if field not in job:
                    errors.append(f"{group_id}/{job_id}: missing field {field}")
            if job_id in seen_ids:
                errors.append(f"duplicate job_id: {job_id}")
            seen_ids.add(job_id)
            if job.get("tool") not in KNOWN_TOOLS:
                errors.append(f"{job_id}: unknown tool {job.get('tool')!r}")
            template = job.get("workflow_template")
            if template not in KNOWN_TEMPLATES:
                errors.append(f"{job_id}: unknown workflow_template {template!r}")
            inputs = job.get("inputs", {})
            output = str(inputs.get("output_path", ""))
            if not output:
                errors.append(f"{job_id}: inputs.output_path is required")
            if job.get("tool") == "comfyui_tts" and not output.endswith(".mp3"):
                errors.append(f"{job_id}: TTS output_path must end in .mp3 (got {output})")
            if job.get("tool") == "comfyui_image":
                prompt = str(inputs.get("prompt", ""))
                if not prompt:
                    errors.append(f"{job_id}: image job requires a compiled prompt")
                elif not any(marker in prompt.lower() for marker in ("no text", "text-free")) or "watermark" not in prompt.lower():
                    errors.append(f"{job_id}: image prompt lacks the no-text/watermark guardrail")
            if not str(output).startswith("projects/"):
                errors.append(f"{job_id}: output_path must live under projects/ (got {output})")
    return errors


def hydrate_prompt_refs(manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    """Resolve compact prompt_ref entries and persist the exact compiled prompts.

    This keeps reviewed prompt prose in one project artifact while ensuring the
    ComfyUI tool still receives a concrete ``inputs.prompt`` value.
    """
    raw_pack = str(manifest.get("prompt_pack_path") or "").strip()
    if not raw_pack:
        return manifest
    pack_path = Path(raw_pack)
    if not pack_path.is_absolute():
        pack_path = REPO_ROOT / pack_path
    pack = load_json(pack_path)
    prompts = {str(row["id"]): str(row["prompt"]) for row in pack.get("jobs", [])}
    compiled = []
    for group in manifest.get("gpu_groups", []):
        for job in group.get("jobs", []):
            inputs = job.setdefault("inputs", {})
            prompt_ref = str(inputs.get("prompt_ref") or "").strip()
            if not prompt_ref:
                continue
            if prompt_ref not in prompts:
                raise KeyError(f"unknown prompt_ref {prompt_ref!r} in {pack_path}")
            inputs["prompt"] = prompts[prompt_ref]
            compiled.append(
                {
                    "job_id": job.get("job_id"),
                    "prompt_ref": prompt_ref,
                    "workflow_template": job.get("workflow_template"),
                    "prompt": inputs["prompt"],
                }
            )
    dump_json(
        manifest_path.parent / "compiled_prompt_report.json",
        {
            "version": "1.0",
            "prompt_pack_path": str(pack_path),
            "compiled_prompts": compiled,
        },
    )
    return manifest


def expand_compact_image_jobs(manifest: dict[str, Any]) -> dict[str, Any]:
    """Expand reviewed project shorthand into ordinary ComfyUI image jobs."""
    project_id = str(manifest.get("project_id") or "").strip()
    refs = [
        f"projects/{project_id}/assets/images/character/ref-{index:02d}.png"
        for index in range(1, 5)
    ]
    for group in manifest.get("gpu_groups", []):
        rows = group.get("jobs", [])
        if not rows or not isinstance(rows[0], list):
            continue
        expanded = []
        if group.get("id") == "krea":
            for prompt_ref, relative_output, seed in rows:
                expanded.append(
                    {
                        "job_id": f"image-{prompt_ref}",
                        "tool": "comfyui_image",
                        "workflow_template": "krea2_low_vram",
                        "status": "pending",
                        "inputs": {
                            "prompt_ref": prompt_ref,
                            "aspect_preset": "portrait_9_16",
                            "seed": seed,
                            "output_path": f"projects/{project_id}/{relative_output}",
                        },
                    }
                )
        elif group.get("id") == "flux":
            for prompt_ref, seed in rows:
                expanded.append(
                    {
                        "job_id": f"image-{prompt_ref}",
                        "tool": "comfyui_image",
                        "workflow_template": "flux2_klein_4ref",
                        "status": "pending",
                        "inputs": {
                            "prompt_ref": prompt_ref,
                            "aspect_preset": "portrait_9_16",
                            "megapixels": 1.0,
                            "seed": seed,
                            "reference_image_paths": refs,
                            "output_path": f"projects/{project_id}/assets/images/scenes/{prompt_ref}.png",
                        },
                    }
                )
        else:
            raise ValueError(f"compact jobs are unsupported for group {group.get('id')!r}")
        group["jobs"] = expanded
    return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_inventory(manifest_path: Path) -> Path:
    """Build artifacts/gpu_asset_inventory.json from completed jobs with local outputs."""
    manifest = load_json(manifest_path)
    project_dir = REPO_ROOT / "projects" / str(manifest.get("project_id", ""))
    rows = []
    for group in manifest.get("gpu_groups", []):
        for job in group.get("jobs", []):
            if job.get("status") != "complete":
                continue
            output = _output_path(job)
            if output is None or not output.is_file() or output.stat().st_size <= 0:
                continue
            rows.append(
                {
                    "job_id": job["job_id"],
                    "path": str(output),
                    "size": output.stat().st_size,
                    "sha256": _sha256(output),
                }
            )
    if not rows:
        raise SystemExit("no completed jobs with local outputs; refusing to write an empty inventory")
    inventory_path = project_dir / "artifacts" / "gpu_asset_inventory.json"
    dump_json(
        inventory_path,
        {"version": "1.0", "batch_id": manifest.get("batch_id"), "generated_at": utc_now(), "assets": rows},
    )
    return inventory_path


def run_manifest(manifest_path: Path, *, group_filter: str | None = None) -> dict[str, Any]:
    manifest = hydrate_prompt_refs(
        expand_compact_image_jobs(load_json(manifest_path)), manifest_path
    )
    errors = validate_manifest(manifest)
    if errors:
        raise RuntimeError("manifest validation failed:\n- " + "\n- ".join(errors))

    live_preflight(manifest_path)

    report_path = manifest_path.parent / "gpu_usage_report.json"
    report = (
        load_json(report_path)
        if report_path.is_file()
        else {
            "version": "1.0",
            "batch_id": manifest.get("batch_id"),
            "started_at": utc_now(),
            "jobs": [],
        }
    )

    groups = [
        group
        for group in manifest.get("gpu_groups", [])
        if group_filter is None or group.get("id") == group_filter
    ]
    if not groups:
        raise KeyError(f"no gpu_group matches filter {group_filter!r}")

    failures: list[str] = []
    summary: dict[str, Any] = {"batch_id": manifest.get("batch_id"), "groups": []}
    for group in groups:
        group_started_at = utc_now()
        group_rows: list[dict[str, Any]] = []
        for job in group.get("jobs", []):
            output = _output_path(job)
            if (
                job.get("status") == "complete"
                and output is not None
                and output.is_file()
                and output.stat().st_size > 0
            ):
                group_rows.append({"job_id": job["job_id"], "status": "skipped_existing"})
                continue
            row = execute_job(job)
            report["jobs"].append(row)
            dump_json(report_path, report)
            group_rows.append(row)
            if row.get("status") == "succeeded":
                job["status"] = "complete"
                job["completed_at"] = row.get("completed_at")
                job["duration_seconds"] = row.get("duration_seconds")
                job["artifacts"] = row.get("artifacts")
            else:
                job["status"] = "failed"
                job["error"] = row.get("error")
                failures.append(f"{job['job_id']}:{row.get('error')}")
            dump_json(manifest_path, manifest)
        group["completed_at"] = utc_now() if not failures else None
        summary["groups"].append(
            {
                "group_id": group.get("id"),
                "started_at": group_started_at,
                "completed_at": group.get("completed_at"),
                "rows": group_rows,
            }
        )

    manifest["last_run_at"] = utc_now()
    dump_json(manifest_path, manifest)
    if failures:
        raise RuntimeError("GPU batch failed:\n- " + "\n- ".join(failures))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--group", default=None, help="run only this gpu_group id")
    parser.add_argument(
        "--write-inventory",
        action="store_true",
        help="skip generation; only rebuild the local SHA-256 asset inventory",
    )
    args = parser.parse_args()

    manifest_path = args.manifest.expanduser().resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"manifest not found: {manifest_path}")

    if args.write_inventory:
        inventory_path = write_inventory(manifest_path)
        print(json.dumps({"inventory": str(inventory_path)}, ensure_ascii=False))
        return 0

    summary = run_manifest(manifest_path, group_filter=args.group)
    inventory_path = write_inventory(manifest_path)
    summary["inventory"] = str(inventory_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
