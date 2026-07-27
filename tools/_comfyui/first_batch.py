"""Parameterized first-batch ComfyUI workflows used by OpenMontage.

The JSON files remain canonical API-format graphs.  This module only patches
the inputs that are intentionally variable at call time: prompt, seed, aspect
ratio, source image, duration, and output prefix.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from tools._comfyui.duration import resolve_frame_bucket, wan_i2v_duration_seconds


WORKFLOW_DIR = Path(__file__).resolve().parent / "workflows" / "first_batch"

ASPECT_PRESETS: dict[str, dict[str, tuple[int, int]]] = {
    "image": {
        "portrait_9_16": (768, 1344),
        "landscape_16_9": (1344, 768),
    },
    "video": {
        "portrait_9_16": (576, 1024),
        "landscape_16_9": (1024, 576),
    },
}

FIRST_BATCH_WORKFLOWS: dict[str, dict[str, Any]] = {
    "z_image_turbo_gguf": {
        "media": "image",
        "file": "z-image-turbo-gguf.json",
        "output_node": "171",
        "prompt": ("6", "text"),
        "size": ("162", "width", "height"),
        "seed": ("163", "seed"),
        "steps": ("163", "steps"),
        "output_prefix": ("171", "filename_prefix"),
        "model": "Z-Image Turbo Q4_K_S GGUF",
    },
    "krea2_low_vram": {
        "media": "image",
        "file": "krea2-low-vram.json",
        "output_node": "199",
        "prompt": ("6", "text"),
        "size": ("162", "width", "height"),
        "seed": ("163", "seed"),
        "steps": ("163", "steps"),
        "output_prefix": ("199", "filename_prefix"),
        "model": "Krea 2 Turbo FP8 Low VRAM",
    },
    "krea2_extra_pass": {
        "media": "image",
        "file": "krea2-extra-pass.json",
        "output_node": "199",
        "prompt": ("6", "text"),
        "size": ("162", "width", "height"),
        "seed": ("163", "seed"),
        "steps": ("163", "steps"),
        "output_prefix": ("199", "filename_prefix"),
        "model": "Krea 2 Turbo FP8 Extra Pass",
    },
    "wan22_i2v_q6": {
        "media": "video",
        "file": "wan22-i2v-q6.json",
        "output_node": "122",
        "prompt": ("112", "text"),
        "size": ("203", "value", "204", "value"),
        "seed": ("114", "noise_seed"),
        "duration": ("205", "value"),
        "fps": 16,
        "default_frames": 49,
        "source_image": ("113", "image"),
        "output_prefix": ("122", "filename_prefix"),
        "model": "Wan 2.2 I2V A14B LightX2V 4-step Q6_K GGUF",
    },
    "seedvr2_upscale": {
        "media": "image",
        "file": "seedvr2-upscale.json",
        "output_node": "6",
        "seed": ("4", "seed"),
        "resolution": ("4", "resolution"),
        "source_image": ("5", "image"),
        "output_prefix": ("6", "filename_prefix"),
        "model": "SeedVR2 7B FP8 mixed-block",
        "follows_source_aspect": True,
    },
}


def get_spec(template: str, *, media: str | None = None) -> dict[str, Any]:
    try:
        spec = FIRST_BATCH_WORKFLOWS[template]
    except KeyError as exc:
        choices = ", ".join(sorted(FIRST_BATCH_WORKFLOWS))
        raise ValueError(f"Unknown first-batch workflow template {template!r}; choose: {choices}") from exc
    if media and spec["media"] != media:
        raise ValueError(
            f"Workflow template {template!r} produces {spec['media']}, not {media}"
        )
    return spec


def load_workflow(template: str, *, media: str | None = None) -> dict[str, Any]:
    spec = get_spec(template, media=media)
    with open(WORKFLOW_DIR / spec["file"], encoding="utf-8") as handle:
        return json.load(handle)


def _set_input(workflow: dict[str, Any], target: tuple[str, str], value: Any) -> None:
    node_id, field = target
    workflow[node_id]["inputs"][field] = value


def build_workflow(
    template: str,
    inputs: dict[str, Any],
    *,
    media: str,
    source_image_name: str | None = None,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Build a patched API workflow and return graph, output node, provenance."""

    spec = get_spec(template, media=media)
    workflow = copy.deepcopy(load_workflow(template, media=media))
    aspect_preset = inputs.get("aspect_preset", "portrait_9_16")

    if spec.get("size"):
        try:
            preset_width, preset_height = ASPECT_PRESETS[media][aspect_preset]
        except KeyError as exc:
            choices = ", ".join(sorted(ASPECT_PRESETS[media]))
            raise ValueError(f"Unknown aspect_preset {aspect_preset!r}; choose: {choices}") from exc
        width = int(inputs.get("width", preset_width))
        height = int(inputs.get("height", preset_height))
        size_target = spec["size"]
        if len(size_target) == 3:
            node_id, width_field, height_field = size_target
            workflow[node_id]["inputs"][width_field] = width
            workflow[node_id]["inputs"][height_field] = height
        else:
            width_node, width_field, height_node, height_field = size_target
            workflow[width_node]["inputs"][width_field] = width
            workflow[height_node]["inputs"][height_field] = height
    else:
        width = height = None

    if spec.get("prompt") and "prompt" in inputs:
        _set_input(workflow, spec["prompt"], inputs["prompt"])
    if spec.get("seed") and inputs.get("seed") is not None:
        _set_input(workflow, spec["seed"], int(inputs["seed"]))
    if spec.get("steps") and inputs.get("steps") is not None:
        _set_input(workflow, spec["steps"], int(inputs["steps"]))
    if spec.get("resolution") and inputs.get("resolution") is not None:
        _set_input(workflow, spec["resolution"], int(inputs["resolution"]))
    if spec.get("duration"):
        num_frames, requested_duration, selected_duration = resolve_frame_bucket(
            inputs,
            default_frames=int(spec["default_frames"]),
            duration_for_frames=wan_i2v_duration_seconds,
            label="Wan 2.2 I2V",
        )
        _set_input(workflow, spec["duration"], (num_frames - 1) // 16)
    else:
        num_frames = requested_duration = selected_duration = None
    if spec.get("source_image"):
        if not source_image_name:
            raise ValueError(f"Workflow template {template!r} requires a source image")
        _set_input(workflow, spec["source_image"], source_image_name)
    if spec.get("output_prefix") and inputs.get("output_path"):
        _set_input(workflow, spec["output_prefix"], Path(inputs["output_path"]).stem)

    provenance = {
        "source": "bundled_first_batch",
        "workflow_template": template,
        "workflow_file": spec["file"],
        "model": spec["model"],
        "aspect_preset": aspect_preset,
        "width": width,
        "height": height,
        "follows_source_aspect": bool(spec.get("follows_source_aspect")),
        "num_frames": num_frames,
        "fps": spec.get("fps"),
        "requested_duration_seconds": requested_duration,
        "selected_duration_seconds": selected_duration,
    }
    return workflow, spec["output_node"], provenance
