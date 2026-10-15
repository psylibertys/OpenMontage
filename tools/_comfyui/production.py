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
    "minimax_fasth3_t2v": {
        "media": "video",
        "file": "minimax-fasth3-t2v.json",
        "output_node": "228",
        "prompt_state": ("236", "PromptState", "text"),
        "seed": ("240", "seed"),
        "seed_state": ("240", "SeedState", "runSeed"),
        "steps": ("225", "steps"),
        "size_state": ("223", "SizesState"),
        "duration_state": ("234", "DurationState", "seconds"),
        "output_prefix": ("228", "filename_prefix"),
        "fps": 24,
        "duration_mode": "seconds",
        "duration_bounds": (4, 15),
        "default_duration": 5,
        "model": "MiniMax FastH3 8-step text-to-video with native audio",
    },
    "minimax_fasth3_i2v": {
        "media": "video",
        "file": "minimax-fasth3-i2v.json",
        "output_node": "228",
        "prompt_state": ("239", "PromptState", "text"),
        "seed": ("243", "seed"),
        "seed_state": ("243", "SeedState", "runSeed"),
        "source_image": ("236", "image"),
        "longest_side_state": ("237", "LongestSideState", "size"),
        "duration_state": ("238", "DurationState", "seconds"),
        "output_prefix": ("228", "filename_prefix"),
        "fps": 24,
        "duration_mode": "seconds",
        "duration_bounds": (4, 15),
        "default_duration": 5,
        "model": "MiniMax FastH3 8-step first-frame-to-video with native audio",
    },
    "minimax_fasth3_fflf": {
        "media": "video",
        "file": "minimax-fasth3-fflf.json",
        "output_node": "228",
        "prompt_state": ("239", "PromptState", "text"),
        "seed": ("243", "seed"),
        "seed_state": ("243", "SeedState", "runSeed"),
        "source_image": ("236", "image"),
        "last_image": ("244", "image"),
        "longest_side_state": ("237", "LongestSideState", "size"),
        "duration_state": ("238", "DurationState", "seconds"),
        "output_prefix": ("228", "filename_prefix"),
        "fps": 24,
        "duration_mode": "seconds",
        "duration_bounds": (4, 15),
        "default_duration": 5,
        "model": "MiniMax FastH3 8-step first-and-last-frame transition",
    },
    "minimax_h3_audio_sync": {
        "media": "video",
        "file": "minimax-h3-audio-sync.json",
        "output_node": "228",
        "prompt_state": ("239", "PromptState", "text"),
        "seed": ("225", "seed"),
        "steps_state": ("253", "DropdownState", 2),
        "source_image": ("236", "image"),
        "source_audio_state": ("247", "LoadAudioState", "file"),
        "audio_length_state": ("247", "LoadAudioState", "length"),
        "longest_side_state": ("243", "LongestSideState", "size"),
        "duration_state": ("234", "DurationState", "seconds"),
        "output_prefix": ("228", "filename_prefix"),
        "fps": 24,
        "duration_mode": "audio",
        "duration_bounds": (1, 15),
        "default_duration": 15,
        "model": "MiniMax H3 ref2va lip-sync + Speed LoRA 4-step",
    },
    "flux2_klein_outpaint": {
        "media": "image",
        "file": "flux2-klein-outpaint.json",
        "output_node": "226",
        "prompt": ("247", "text_1"),
        "seed": ("243", "seed"),
        "seed_state": ("243", "SeedState", "runSeed"),
        "source_image": ("240", "image"),
        "outpaint_state": ("241", "OutpaintState", "ratio"),
        "output_prefix": ("226", "filename_prefix"),
        "model": "FLUX.2 Klein 9B KV FP8 + pixaoutpaint outpaint",
    },
    "krea2_edit_lora": {
        "media": "image",
        "file": "krea2-edit-lora.json",
        "output_node": "199",
        "prompt_state": ("221", "PromptState", "text"),
        "seed": ("163", "seed"),
        "steps": ("163", "steps"),
        "source_image": ("226", "image"),
        "ref_boost_state": ("234", "SlidersState", ("sliders", 0, "value")),
        "output_prefix": ("199", "filename_prefix"),
        "model": "Krea 2 Turbo INT8 + identity edit LoRA in-context edit",
    },
    "krea2_outfit_transfer": {
        "media": "image",
        "file": "krea2-outfit-transfer.json",
        "output_node": "199",
        "prompt": ("236", "text_1"),
        "seed": ("163", "seed"),
        "steps": ("163", "steps"),
        "source_image": ("226", "image"),
        "resolution_state": ("235", "ResolutionState"),
        "output_prefix": ("199", "filename_prefix"),
        "model": "Krea 2 Turbo INT8 + outfit transfer LoRA",
    },
}

# outfit_transfer 的 PixaromaResolution 预设（节点执行只读 w/h，ratio 仅保持一致）
_RESOLUTION_PRESETS = {
    "portrait_9_16": {"ratio": "9:16", "w": 720, "h": 1280},
    "landscape_16_9": {"ratio": "16:9", "w": 1280, "h": 720},
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


def _load_state(workflow: dict[str, Any], node_id: str, state_key: str) -> dict[str, Any]:
    return json.loads(workflow[node_id]["inputs"][state_key])


def _save_state(workflow: dict[str, Any], node_id: str, state_key: str, state: dict[str, Any]) -> None:
    workflow[node_id]["inputs"][state_key] = json.dumps(state, ensure_ascii=False)


def _patch_state(
    workflow: dict[str, Any],
    node_id: str,
    state_key: str,
    field: str | tuple[Any, ...],
    value: Any,
) -> None:
    """Patch one field inside a serialized Pixaroma widget-state JSON blob."""
    state = _load_state(workflow, node_id, state_key)
    if isinstance(field, tuple):
        cursor: Any = state
        for part in field[:-1]:
            cursor = cursor[part]
        cursor[field[-1]] = value
    else:
        state[field] = value
    _save_state(workflow, node_id, state_key, state)


def _select_size_index(sizes: list[list[int]], long_edge: int) -> int:
    """Map a requested long edge onto the closest Pixaroma size preset."""
    return min(range(len(sizes)), key=lambda i: abs(sizes[i][0] - long_edge))


def _snap_resolution(value: int) -> int:
    """Clamp into the PixaromaResolution node's 64-16384 range and snap to 16."""
    return max(64, min(16384, int(round(value / 16)) * 16))


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
    if spec.get("prompt_state") and inputs.get("prompt"):
        node_id, state_key, field = spec["prompt_state"]
        _patch_state(workflow, node_id, state_key, field, inputs["prompt"])
    seed = inputs.get("seed")
    if seed is not None:
        if spec.get("seed"):
            _set(workflow, spec["seed"], int(seed))
        for offset, node_id in enumerate(spec.get("seed_nodes", ())):
            workflow[node_id]["inputs"]["seed"] = int(seed) + offset
    if seed is not None and spec.get("seed_state"):
        node_id, state_key, field = spec["seed_state"]
        _patch_state(workflow, node_id, state_key, field, int(seed))
    if spec.get("steps") and inputs.get("steps") is not None:
        _set(workflow, spec["steps"], int(inputs["steps"]))
    if spec.get("steps_state") and inputs.get("steps") is not None:
        node_id, state_key, index = spec["steps_state"]
        _patch_state(workflow, node_id, state_key, ("values", int(index)), str(int(inputs["steps"])))

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
    if spec.get("size_state"):
        node_id, state_key = spec["size_state"]
        state = _load_state(workflow, node_id, state_key)
        state["orientation"] = "portrait" if aspect == "portrait_9_16" else "landscape"
        if "width" in inputs or "height" in inputs:
            state["selected"] = _select_size_index(state["sizes"], max(width, height))
        _save_state(workflow, node_id, state_key, state)
    if spec.get("longest_side_state") and inputs.get("longest_side") is not None:
        node_id, state_key, field = spec["longest_side_state"]
        _patch_state(workflow, node_id, state_key, field, int(inputs["longest_side"]))
    if spec.get("outpaint_state") and inputs.get("outpaint_ratio"):
        node_id, state_key, field = spec["outpaint_state"]
        _patch_state(workflow, node_id, state_key, field, str(inputs["outpaint_ratio"]))
    if spec.get("ref_boost_state") and inputs.get("reference_boost") is not None:
        boost = float(inputs["reference_boost"])
        if not 0 <= boost <= 10:
            raise ValueError(
                f"Workflow template {template!r} accepts reference_boost between 0 and 10, "
                f"got {inputs['reference_boost']}"
            )
        node_id, state_key, field = spec["ref_boost_state"]
        _patch_state(workflow, node_id, state_key, field, boost)
    if spec.get("resolution_state"):
        node_id, state_key = spec["resolution_state"]
        state = _load_state(workflow, node_id, state_key)
        preset = _RESOLUTION_PRESETS[aspect]
        state["ratio"], state["w"], state["h"] = preset["ratio"], preset["w"], preset["h"]
        if "width" in inputs or "height" in inputs:
            state["w"] = _snap_resolution(width)
            state["h"] = _snap_resolution(height)
        _save_state(workflow, node_id, state_key, state)

    if spec.get("source_image"):
        if not uploads.get("source_image"):
            raise ValueError(f"Workflow template {template!r} requires source_image")
        _set(workflow, spec["source_image"], uploads["source_image"])
    if spec.get("last_image"):
        if not uploads.get("last_image"):
            raise ValueError(f"Workflow template {template!r} requires last_image (the closing frame)")
        _set(workflow, spec["last_image"], uploads["last_image"])
    for target, name in zip(spec.get("reference_images", ()), uploads.get("reference_images", ())):
        _set(workflow, target, name)
    if spec.get("reference_images") and len(uploads.get("reference_images", ())) != 4:
        raise ValueError(f"Workflow template {template!r} requires exactly four reference images")
    if spec.get("source_audio"):
        if not uploads.get("source_audio"):
            raise ValueError(f"Workflow template {template!r} requires source_audio")
        _set(workflow, spec["source_audio"], uploads["source_audio"])
    if spec.get("source_audio_state"):
        if not uploads.get("source_audio"):
            raise ValueError(f"Workflow template {template!r} requires source_audio")
        node_id, state_key, field = spec["source_audio_state"]
        _patch_state(workflow, node_id, state_key, field, uploads["source_audio"])
        length_node, length_key, length_field = spec["audio_length_state"]
        audio_limit = float(spec["duration_bounds"][1])
        audio_seconds = (
            float(inputs["duration_seconds"])
            if inputs.get("duration_seconds") is not None
            else audio_limit
        )
        _patch_state(
            workflow, length_node, length_key, length_field,
            min(audio_seconds, audio_limit),
        )
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
        if spec.get("duration_state"):
            bounds = spec.get("duration_bounds")
            if bounds and requested_duration is not None and not (
                bounds[0] <= requested_duration <= bounds[1]
            ):
                raise ValueError(
                    f"Workflow template {template!r} accepts duration_seconds "
                    f"between {bounds[0]} and {bounds[1]} seconds, got {requested_duration}"
                )
            if requested_duration is None:
                requested_duration = float(spec["default_duration"])
            selected_duration = requested_duration
            node_id, state_key, field = spec["duration_state"]
            _patch_state(workflow, node_id, state_key, field, selected_duration)
        else:
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
