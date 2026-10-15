#!/usr/bin/env python3
"""Export a validated storyboard.json from a storyboard_export artifact.

Reads the canonical storyboard_export artifact (and, optionally, the scene_plan
it was derived from), validates structure + semantic lint + traceability via
lib/storyboard_export.py, and writes the deliverable to

    projects/<project-id>/exports/storyboard/<theme>/<theme>.json

That file is the direct feed for generation chains (ComfyUI t2i/i2v batches).

Usage:
    python scripts/export_storyboard_json.py \
        projects/my-story/artifacts/storyboard_export.json \
        --scene-plan projects/my-story/artifacts/scene_plan.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.storyboard_export import (  # noqa: E402
    MAX_SHOT_SECONDS,
    check_traceability,
    lint_storyboard,
)
from schemas.artifacts import validate_artifact  # noqa: E402


def safe_path_component(value: str) -> str:
    cleaned = re.sub(r"[^\w\.\-]+", "_", value.strip(), flags=re.UNICODE)
    return cleaned.strip("-_ ") or "untitled"


def infer_project_id(storyboard_path: Path) -> str | None:
    """Infer the project id from projects/<id>/artifacts/... layout."""
    try:
        relative = storyboard_path.resolve().relative_to(PROJECT_ROOT / "projects")
        return relative.parts[0]
    except ValueError:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and export storyboard.json for generation chains."
    )
    parser.add_argument(
        "storyboard",
        help="Path to the storyboard_export artifact JSON (canonical form).",
    )
    parser.add_argument(
        "--scene-plan",
        help="Path to the scene_plan artifact for traceability checking.",
    )
    parser.add_argument(
        "--output-dir",
        help="Override the export base directory "
        "(default: projects/<project-id>/exports/storyboard).",
    )
    parser.add_argument(
        "--theme",
        help="Override the export directory/file name (default: video_theme).",
    )
    parser.add_argument(
        "--max-shot-seconds",
        type=float,
        default=MAX_SHOT_SECONDS,
        help=f"Tighten the per-shot duration cap, in (0, {MAX_SHOT_SECONDS}] "
        f"(default: {MAX_SHOT_SECONDS}).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    storyboard_path = Path(args.storyboard)
    if not storyboard_path.exists():
        print(f"error: storyboard artifact not found: {storyboard_path}", file=sys.stderr)
        return 1

    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))

    failures: list[str] = []

    try:
        validate_artifact("storyboard_export", storyboard)
    except Exception as exc:  # jsonschema.ValidationError
        failures.append(f"schema validation failed: {exc.message}")

    failures.extend(
        lint_storyboard(storyboard, max_shot_seconds=args.max_shot_seconds)
    )

    if args.scene_plan:
        scene_plan_path = Path(args.scene_plan)
        if not scene_plan_path.exists():
            print(f"error: scene_plan not found: {scene_plan_path}", file=sys.stderr)
            return 1
        scene_plan = json.loads(scene_plan_path.read_text(encoding="utf-8"))
        failures.extend(check_traceability(storyboard, scene_plan))

    if failures:
        print("storyboard export FAILED validation:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    metadata = storyboard.setdefault("metadata", {})
    metadata.setdefault("absorbed_from", "copy-to-storyboard-json (2026-10 snapshot)")
    metadata["max_shot_seconds"] = args.max_shot_seconds
    if args.scene_plan:
        metadata["scene_plan_traceability_checked"] = str(Path(args.scene_plan))

    theme = safe_path_component(args.theme or storyboard["video_theme"])
    project_id = infer_project_id(storyboard_path)
    base = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else PROJECT_ROOT / "projects" / (project_id or "unassigned") / "exports" / "storyboard"
    )
    out_dir = base / theme
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{theme}.json"
    out_path.write_text(
        json.dumps(storyboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    total = sum(scene["duration_seconds"] for scene in storyboard["scenes"])
    print(f"exported: {out_path}")
    print(f"shots: {len(storyboard['scenes'])}  total duration: {total:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
