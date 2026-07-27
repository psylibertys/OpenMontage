"""Parameterized API-format workflows for the AutoDL production suite.

The JSON graphs are exported from the course workflows and remain canonical.
This module only changes inputs that OpenMontage owns at call time.  Model
loaders and graph wiring are intentionally left fixed for reproducibility.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from tools._comfyui.duration import (
    infinitetalk_duration_seconds,
    resolve_frame_bucket,
)


WORKFLOW_DIR = Path(__file__).resolve().parent / "workflows" / "production"

ASPECT_LABELS = {
    "portrait_9_16": "9:16 (Portrait Widescreen)",
    "landscape_16_9": "16:9 (Widescreen)",
}

PRODUCTION_WORKFLOWS: dict[str, dict[str, Any]] = {
    "flux2_klein_4ref": {
        "media": "image",
        "file": "flux2-klein-4ref.json",
        "output_node": "203",
        "prompt": ("6", "text"),
        "resolution_selector": "216",
        "seed": ("163", "seed"),
        "steps": ("163", "steps"),
        "output_prefix": ("203", "filename_prefix"),
        "reference_images": [("198", "image"), ("213", "image"), ("219", "image"), ("225", "image")],
        "model": "FLUX.2 Klein 9B KV FP8 four-reference",
    },
    "flux2_klein_inpaint": {
        "media": "image",
        "file": "flux2-klein-inpaint.json",
        "output_node": "203",
        "prompt": ("6", "text"),
        "seed": ("163", "seed"),
        "steps": ("163", "steps"),
        "output_prefix": ("203", "filename_prefix"),
        "source_image": ("198", "image"),
        "inpaint_size": "209",
        "model": "FLUX.2 Klein 9B KV FP8 inpaint",
    },
    "wan_infinitetalk_short": {
        "media": "video",
        "file": "wan-infinitetalk-short.json",
        "output_node": "182",
        "prompt": ("14", "text"),
        "source_image": ("32", "image"),
        "source_audio": ("171", "audio"),
        "size_nodes": ("149", "150"),
        "length_nodes": ("129", "130"),
        "seed_nodes": ("180", "181"),
        "output_prefix": ("182", "filename_prefix"),
        "fps": 25,
        "segment_count": 2,
        "default_frames": 49,
        "model": "Wan 2.1 InfiniteTalk two-segment",
    },
    "wan_infinitetalk_extend": {
        "media": "video",
        "file": "wan-infinitetalk-extend.json",
        "output_node": "240",
        "prompt": ("14", "text"),
        "source_image": ("32", "image"),
        "source_audio": ("171", "audio"),
        "size_nodes": ("149", "150"),
        "length_nodes": ("129", "130", "183", "193", "200", "206", "212", "218", "224", "228", "236", "242"),
        "seed_nodes": ("180", "181", "184", "189", "195", "201", "207", "213", "219", "230", "235", "241"),
        "output_prefix": ("240", "filename_prefix"),
        "fps": 25,
        "segment_count": 12,
        "default_frames": 81,
        "model": "Wan 2.1 InfiniteTalk 34-second extension chain",
    },
    "wan22_animate_character": {
        "media": "video",
        "file": "wan22-animate-character.json",
        "output_node": "56",
        "prompt": ("276", "positive"),
        "source_image": ("55", "image"),
        "source_video": ("181", "video"),
        "size_nodes": ("43", "49"),
        "seed_nodes": ("58",),
        "output_prefix": ("56", "filename_prefix"),
        "fps": 16,
        "duration_mode": "driving_video",
        "model": "Wan 2.2 Animate 14B FP8 character transfer",
    },
    "wan_scail_character": {
        "media": "video",
        "file": "wan-scail-character.json",
        "output_node": "139",
        "prompt": ("417", "positive"),
        "source_image": ("106", "image"),
        "source_video": ("130", "video"),
        "size_nodes": ("203", "204"),
        "seed_nodes": ("348",),
        "output_prefix": ("139", "filename_prefix"),
        "fps": 24,
        "duration_mode": "driving_video",
        "model": "Wan 2.1 SCAIL preview character transfer",
    },
}


def get_spec(template: str, *, media: str | None = None) -> dict[str, Any]:
    try:
        spec = PRODUCTION_WORKFLOWS[template]
    except KeyError as exc:
        choices = ", ".join(sorted(PRODUCTION_WORKFLOWS))
        raise ValueError(f"Unknown production workflow template {template!r}; choose: {choices}") from exc
    if media and spec["media"] != media:
        raise ValueError(f"Workflow template {template!r} produces {spec['media']}, not {media}")
    return spec


def _set(workflow: dict[str, Any], target: tuple[str, str], value: Any) -> None:
    node_id, field = target
    workflow[node_id]["inputs"][field] = value


def _linux_model_paths(workflow: dict[str, Any]) -> None:
    """Normalize course exports made on Windows without changing graph links."""
    for node in workflow.values():
        for key, value in node.get("inputs", {}).items():
            if isinstance(value, str) and "\\" in value and key in {
                "unet_name", "model", "model_name", "lora", "lora_name", "lora_0", "lora_1",
                "lora_2", "lora_3", "lora_4",
            }:
                node["inputs"][key] = value.replace("\\", "/")


def _prune_to_output(workflow: dict[str, Any], output_node: str) -> None:
    """Drop UI-only/dead API nodes that cannot affect the chosen deliverable."""
    keep: set[str] = set()
    pending = [output_node]
    while pending:
        node_id = pending.pop()
        if node_id in keep or node_id not in workflow:
            continue
        keep.add(node_id)
        for value in workflow[node_id].get("inputs", {}).values():
            if (
                isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], str)
                and value[0] in workflow
            ):
                pending.append(value[0])
    for node_id in list(workflow):
        if node_id not in keep:
            del workflow[node_id]


def build_workflow(
    template: str,
    inputs: dict[str, Any],
    *,
    media: str,
    uploads: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    spec = get_spec(template, media=media)
    with open(WORKFLOW_DIR / spec["file"], encoding="utf-8") as handle:
        workflow = copy.deepcopy(json.load(handle))
    _linux_model_paths(workflow)
    uploads = uploads or {}

    if spec.get("prompt") and "prompt" in inputs:
        _set(workflow, spec["prompt"], inputs["prompt"])
    seed = inputs.get("seed")
    if seed is not None:
        if spec.get("seed"):
            _set(workflow, spec["seed"], int(seed))
        for offset, node_id in enumerate(spec.get("seed_nodes", ())):
            workflow[node_id]["inputs"]["seed"] = int(seed) + offset
    if spec.get("steps") and inputs.get("steps") is not None:
        _set(workflow, spec["steps"], int(inputs["steps"]))

    aspect = inputs.get("aspect_preset", "portrait_9_16")
    if aspect not in ASPECT_LABELS:
        raise ValueError(f"Unknown aspect_preset {aspect!r}; choose: {', '.join(ASPECT_LABELS)}")
    width = int(inputs.get("width", 768 if media == "image" else 480))
    height = int(inputs.get("height", 1344 if media == "image" else 832))
    if aspect == "landscape_16_9" and "width" not in inputs and "height" not in inputs:
        width, height = height, width

    if spec.get("size"):
        node, wf, hf = spec["size"]
        workflow[node]["inputs"][wf] = width
        workflow[node]["inputs"][hf] = height
    if spec.get("resolution_selector"):
        workflow[spec["resolution_selector"]]["inputs"]["aspect_ratio"] = ASPECT_LABELS[aspect]
        workflow[spec["resolution_selector"]]["inputs"]["megapixels"] = float(inputs.get("megapixels", 1.0))
    for index, node_id in enumerate(spec.get("size_nodes", ())):
        workflow[node_id]["inputs"]["value"] = width if index == 0 else height
    if spec.get("inpaint_size"):
        node = workflow[spec["inpaint_size"]]["inputs"]
        node["output_target_width"] = width
        node["output_target_height"] = height

    if spec.get("source_image"):
        if not uploads.get("source_image"):
            raise ValueError(f"Workflow template {template!r} requires source_image")
        _set(workflow, spec["source_image"], uploads["source_image"])
    for target, name in zip(spec.get("reference_images", ()), uploads.get("reference_images", ())):
        _set(workflow, target, name)
    if spec.get("reference_images") and len(uploads.get("reference_images", ())) != 4:
        raise ValueError(f"Workflow template {template!r} requires exactly four reference images")
    if spec.get("source_audio"):
        if not uploads.get("source_audio"):
            raise ValueError(f"Workflow template {template!r} requires source_audio")
        _set(workflow, spec["source_audio"], uploads["source_audio"])
    if spec.get("source_video"):
        if not uploads.get("source_video"):
            raise ValueError(f"Workflow template {template!r} requires source_video")
        _set(workflow, spec["source_video"], uploads["source_video"])

    duration_mode = spec.get(
        "duration_mode",
        "frame_bucket" if spec.get("length_nodes") else None,
    )
    if duration_mode == "driving_video" and "num_frames" in inputs:
        raise ValueError(
            f"Workflow template {template!r} derives its frame count from driving_video_path; "
            "num_frames would be ignored. Trim the driving video to the desired duration instead."
        )
    if spec.get("length_nodes"):
        segment_count = int(spec["segment_count"])
        num_frames, requested_duration, selected_duration = resolve_frame_bucket(
            inputs,
            default_frames=int(spec["default_frames"]),
            duration_for_frames=lambda frames: infinitetalk_duration_seconds(
                frames, segment_count
            ),
            label=template,
        )
    else:
        num_frames = None
        requested_duration = (
            float(inputs["duration_seconds"])
            if inputs.get("duration_seconds") is not None
            else None
        )
        if requested_duration is not None and requested_duration <= 0:
            raise ValueError("duration_seconds must be greater than 0")
        selected_duration = requested_duration
    for node_id in spec.get("length_nodes", ()):
        workflow[node_id]["inputs"]["length"] = num_frames
    if spec.get("force_save"):
        workflow[spec["force_save"]]["inputs"]["save_output"] = True
    if spec.get("output_prefix") and inputs.get("output_path"):
        _set(workflow, spec["output_prefix"], Path(inputs["output_path"]).stem)

    _prune_to_output(workflow, spec["output_node"])

    provenance = {
        "source": "bundled_production",
        "workflow_template": template,
        "workflow_file": spec["file"],
        "model": spec["model"],
        "aspect_preset": aspect,
        "width": width,
        "height": height,
        "num_frames": (
            num_frames
            if media == "video" and duration_mode != "driving_video"
            else None
        ),
        "fps": spec.get("fps"),
        "segment_count": spec.get("segment_count"),
        "duration_mode": duration_mode,
        "requested_duration_seconds": requested_duration,
        "selected_duration_seconds": selected_duration,
    }
    return workflow, spec["output_node"], provenance
