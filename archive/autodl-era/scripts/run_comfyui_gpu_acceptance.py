#!/usr/bin/env python3
"""Run the approved ComfyUI GPU acceptance matrix serially and fail closed."""

from __future__ import annotations

import argparse
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


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_CONFIG = PROJECT_ROOT / "production-planning" / "GPU_ACCEPTANCE_CASES.json"


def _get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)


def _resolve(value: Any, fixtures: dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$fixtures."):
        return fixtures[value.split(".", 1)[1]]
    if isinstance(value, list):
        return [_resolve(item, fixtures) for item in value]
    if isinstance(value, dict):
        return {key: _resolve(item, fixtures) for key, item in value.items()}
    return value


def _expand_cases(config: dict[str, Any]) -> list[dict[str, Any]]:
    fixtures = config["fixtures"]
    expanded: list[dict[str, Any]] = []
    for case in config["cases"]:
        if case.get("enabled", True) is False:
            continue
        if "shared_inputs" in case:
            for template in case["templates"]:
                expanded.append({
                    "id": f"{case['id']}-{template}", "tool": case["tool"],
                    "workflow_template": template,
                    "inputs": _resolve(case["shared_inputs"], fixtures),
                })
        elif case["id"] == "qwen-tts-four-workflows":
            for template in case["templates"]:
                inputs = {"text": case["text"]}
                inputs.update(case.get("template_overrides", {}).get(template, {}))
                expanded.append({
                    "id": f"{case['id']}-{template}", "tool": case["tool"],
                    "workflow_template": template, "inputs": _resolve(inputs, fixtures),
                })
        elif "workflow_template" in case:
            expanded.append({**case, "inputs": _resolve(case.get("inputs", {}), fixtures)})
        else:
            expanded.append({**case, "manual": True})
    return expanded


def _validate_fixture_paths(cases: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    path_fields = {
        "reference_image_path", "reference_audio_path", "driving_video_path",
        "mask_image_path",
    }
    for case in cases:
        for field, value in case.get("inputs", {}).items():
            values = value if field == "reference_image_paths" else [value]
            if field in path_fields or field == "reference_image_paths":
                for path in values:
                    if not Path(path).expanduser().is_file():
                        missing.append(f"{case['id']}: {field}={path}")
    return missing


def _create_inpaint_mask(config: dict[str, Any], project_dir: Path) -> None:
    mask_value = config["fixtures"].get("inpaint_mask")
    if not mask_value:
        return
    mask_path = PROJECT_ROOT / mask_value
    if mask_path.is_file():
        return
    from PIL import Image, ImageDraw

    source = Image.open(config["fixtures"]["character_portrait"])
    width, height = source.size
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse(
        (int(width * 0.32), int(height * 0.13), int(width * 0.68), int(height * 0.52)),
        fill=255,
    )
    mask.save(mask_path)


def _create_extended_audio(config: dict[str, Any]) -> None:
    value = config["fixtures"].get("extended_narration")
    if not value:
        return
    target = PROJECT_ROOT / value
    if target.is_file():
        return
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to create the 35-second InfiniteTalk fixture")
    target.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            ffmpeg, "-y", "-v", "error", "-stream_loop", "-1",
            "-i", config["fixtures"]["narration"], "-t", "35",
            "-c:a", "libmp3lame", "-q:a", "2", str(target),
        ],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise SystemExit(f"Failed to create extended audio fixture: {proc.stderr}")


def _check_gpu_server(server: str) -> None:
    stats = _get_json(server + "/system_stats")
    devices = stats.get("devices", [])
    has_gpu = any(
        "cuda" in json.dumps(device).lower()
        or "nvidia" in json.dumps(device).lower()
        or device.get("type") in {"cuda", "gpu"}
        for device in devices
    )
    if not has_gpu:
        raise SystemExit("ComfyUI is reachable but reports no GPU; switch AutoDL to GPU mode first")
    queue = _get_json(server + "/queue")
    if queue.get("queue_running") or queue.get("queue_pending"):
        raise SystemExit("ComfyUI queue is not empty; acceptance run aborted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="keep prior successful results and skip cases whose local artifacts still exist",
    )
    parser.add_argument("--yes", action="store_true", help="confirm GPU generation")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    cases = _expand_cases(config)
    if args.case_ids:
        wanted = set(args.case_ids)
        cases = [case for case in cases if case["id"] in wanted]
        unknown = wanted - {case["id"] for case in cases}
        if unknown:
            raise SystemExit(f"Unknown case IDs: {', '.join(sorted(unknown))}")
    if args.dry_run:
        print(json.dumps(cases, ensure_ascii=False, indent=2))
        return 0
    if not args.yes:
        parser.error("GPU generation requires --yes")

    os.environ["COMFYUI_SERVER_URL"] = args.server.rstrip("/")
    _check_gpu_server(os.environ["COMFYUI_SERVER_URL"])

    from lib.checkpoint import init_project
    from tools.audio.comfyui_tts import ComfyUITTS
    from tools.graphics.comfyui_image import ComfyUIImage
    from tools.video.comfyui_video import ComfyUIVideo

    project_dir = init_project(
        config["project_id"], title="ComfyUI GPU Acceptance", pipeline_type="unknown"
    )
    _create_inpaint_mask(config, project_dir)
    _create_extended_audio(config)
    missing = _validate_fixture_paths(cases)
    if missing:
        raise SystemExit("Missing acceptance fixtures:\n" + "\n".join(missing))

    tools = {
        "comfyui_image": ComfyUIImage(),
        "comfyui_video": ComfyUIVideo(),
        "comfyui_tts": ComfyUITTS(),
    }
    extensions = {"comfyui_image": ".png", "comfyui_video": ".mp4", "comfyui_tts": ".mp3"}
    folders = {"comfyui_image": "images", "comfyui_video": "video", "comfyui_tts": "audio"}
    results_path = project_dir / "artifacts" / "gpu_acceptance_results.json"
    results: list[dict[str, Any]] = []
    completed_ids: set[str] = set()
    if args.resume and results_path.is_file():
        loaded = json.loads(results_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise SystemExit(f"Invalid prior acceptance report: {results_path}")
        results = loaded
        completed_ids = {
            record["id"]
            for record in results
            if record.get("success") is True
            and not record.get("data", {}).get("cleanup_failures")
            and record.get("artifacts")
            and all(Path(path).is_file() for path in record["artifacts"])
        }
        print(f"Resume: keeping {len(completed_ids)} completed case(s)")

    for case in cases:
        if case["id"] in completed_ids:
            print(f"SKIP completed: {case['id']}")
            continue
        if case.get("manual"):
            results.append({"id": case["id"], "status": "manual"})
            continue
        # A resumed retry replaces its prior failed record so the final report
        # stays one-record-per-case while completed cases remain immutable.
        results = [record for record in results if record.get("id") != case["id"]]
        tool_name = case["tool"]
        output = project_dir / "assets" / folders[tool_name] / (
            case["id"] + extensions[tool_name]
        )
        inputs = {
            **case.get("inputs", {}),
            "workflow_template": case["workflow_template"],
            "output_path": str(output),
        }
        started = time.time()
        result = tools[tool_name].execute(inputs)
        record = {
            "id": case["id"], "tool": tool_name,
            "workflow_template": case["workflow_template"],
            "success": result.success, "error": result.error,
            "data": result.data, "artifacts": result.artifacts,
            "elapsed_seconds": round(time.time() - started, 2),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        results.append(record)
        results_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        if not result.success or result.data.get("cleanup_failures"):
            raise SystemExit(f"Acceptance stopped at {case['id']}: {result.error or 'cleanup failed'}")

    print(json.dumps({"project_dir": str(project_dir), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
