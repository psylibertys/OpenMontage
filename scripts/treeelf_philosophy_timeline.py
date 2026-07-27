"""Timeline helpers for the TreeElf philosophy-video workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def caption_end_boundaries(captions: list[dict[str, Any]], duration: float) -> list[float]:
    boundaries = {0.0, round(float(duration), 2)}
    for caption in captions:
        try:
            end = float(caption["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 < end < duration:
            boundaries.add(round(end, 2))
    return sorted(boundaries)


def snap_caption_boundary(
    boundaries: list[float],
    target: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    candidates = [boundary for boundary in boundaries if minimum <= boundary <= maximum]
    if not candidates:
        return round(max(minimum, min(target, maximum)), 2)
    return round(min(candidates, key=lambda boundary: (abs(boundary - target), boundary)), 2)


def scene_caption_annotation(
    captions: list[dict[str, Any]], start: float, end: float
) -> dict[str, Any]:
    overlapping: list[tuple[int, dict[str, Any]]] = []
    for index, caption in enumerate(captions):
        try:
            caption_start = float(caption["start"])
            caption_end = float(caption["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if caption_end > start + 0.01 and caption_start < end - 0.01:
            overlapping.append((index, caption))
    if not overlapping:
        return {"caption_range": None, "script_excerpt": ""}
    excerpt = "".join(str(caption["text"]).strip() for _, caption in overlapping)
    if len(excerpt) > 140:
        excerpt = excerpt[:137].rstrip() + "…"
    return {
        "caption_range": {
            "start_index": overlapping[0][0],
            "end_index": overlapping[-1][0],
            "start": round(max(start, float(overlapping[0][1]["start"])), 2),
            "end": round(min(end, float(overlapping[-1][1]["end"])), 2),
        },
        "script_excerpt": excerpt,
    }


def retime_scenes_to_caption_boundaries(
    scenes: list[dict[str, Any]],
    captions: list[dict[str, Any]],
    duration: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Snap scene cuts to caption end boundaries after exact narration timing exists."""

    if not scenes or not captions or duration <= 0:
        return scenes, {
            "scene_timing": "config_placeholders",
            "reason": "exact captions unavailable; preserving reviewed edit.scenes timing",
        }

    count = len(scenes)
    if count == 1:
        scene = dict(scenes[0])
        scene["from"] = 0.0
        scene["to"] = round(duration, 2)
        scene.update(scene_caption_annotation(captions, 0.0, duration))
        return [scene], {
            "scene_timing": "caption_boundaries",
            "reason": "single scene stretched to exact narration/caption duration",
            "minimum_scene_seconds": None,
            "opening_target_seconds": None,
        }

    boundaries = caption_end_boundaries(captions, duration)
    minimum_scene_seconds = 4.0
    opening_target_seconds = min(9.2, max(8.5, duration / max(3, count)))
    cuts = [0.0]

    first_maximum = max(opening_target_seconds, min(duration - minimum_scene_seconds * (count - 1), 11.5))
    first_maximum = min(first_maximum, duration - minimum_scene_seconds * (count - 1))
    if first_maximum <= minimum_scene_seconds:
        first_cut = round(duration / count, 2)
    else:
        first_cut = snap_caption_boundary(
            boundaries,
            opening_target_seconds,
            minimum=minimum_scene_seconds,
            maximum=first_maximum,
        )
    cuts.append(first_cut)

    for index in range(2, count):
        remaining = count - index
        prior = cuts[-1]
        minimum = prior + minimum_scene_seconds
        maximum = duration - minimum_scene_seconds * remaining
        if minimum > maximum:
            cut = round(duration * index / count, 2)
        else:
            target = first_cut + (duration - first_cut) * (index - 1) / (count - 1)
            cut = snap_caption_boundary(boundaries, target, minimum=minimum, maximum=maximum)
        cuts.append(cut)
    cuts.append(round(duration, 2))

    retimed: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes):
        start = round(cuts[index], 2)
        end = round(max(start + 0.12, cuts[index + 1]), 2)
        updated = dict(scene)
        updated["from"] = start
        updated["to"] = end
        updated.update(scene_caption_annotation(captions, start, end))
        retimed.append(updated)

    return retimed, {
        "scene_timing": "caption_boundaries",
        "reason": "scene cuts snapped to exact caption end boundaries so visual changes follow semantic units",
        "minimum_scene_seconds": minimum_scene_seconds,
        "opening_target_seconds": opening_target_seconds,
        "caption_boundaries_used": True,
    }


def _image_id_from_scene(scene: dict[str, Any]) -> str:
    src = str(scene.get("src", ""))
    if not src.startswith("images/"):
        return ""
    return Path(src).stem


def _video_id_from_scene(scene: dict[str, Any]) -> str:
    src = str(scene.get("src", ""))
    if not src.startswith("video/"):
        return ""
    return Path(src).stem


def _image_lookup(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id")): item
        for item in config.get("article_visual_assets", {}).get("images", [])
        if item.get("id")
    }


def _base_video_jobs(config: dict[str, Any], max_generation_seconds: float) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for item in config.get("article_visual_assets", {}).get("videos", []):
        job = dict(item)
        duration = float(job.get("duration_seconds", 4))
        job["duration_seconds"] = round(min(max(duration, 1.0), max_generation_seconds), 2)
        jobs.append(job)
    return jobs


def resolve_wan_generation_plan(
    config: dict[str, Any],
    scenes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Choose Wan references from the retimed edit timeline when enabled.

    Policy: keep one clip for the opening hook and one for the longest
    semantic-safe still scene.  The generated clip duration is capped; Remotion
    stretches or tails the result when the scene remains on screen longer.
    """

    visuals = config.get("article_visual_assets", {})
    policy = visuals.get("wan_policy", {})
    max_generation_seconds = float(policy.get("max_generation_seconds", 5))
    jobs = _base_video_jobs(config, max_generation_seconds)
    if not policy.get("enabled") or len(jobs) < 2:
        return jobs, {
            "enabled": False,
            "reason": "wan_policy not enabled; using reviewed episode video references",
            "max_generation_seconds": max_generation_seconds,
        }

    images = _image_lookup(config)
    original_references = {str(job.get("id")): str(job.get("reference", "")) for job in jobs}
    opening_job = next((job for job in jobs if job.get("selection_role") == "opening_hook"), jobs[0])
    longest_job = next((job for job in jobs if job.get("selection_role") == "longest_semantic_safe"), jobs[1])

    opening_reference = str(opening_job.get("reference", ""))
    if scenes:
        first_scene = scenes[0]
        first_image = _image_id_from_scene(first_scene)
        first_video = _video_id_from_scene(first_scene)
        if first_image:
            opening_reference = first_image
        elif first_video in original_references:
            opening_reference = original_references[first_video]

    candidates: list[dict[str, Any]] = []
    for scene in scenes:
        image_id = _image_id_from_scene(scene)
        if not image_id or image_id == opening_reference:
            continue
        image = images.get(image_id)
        if not image or image.get("role") == "cover":
            continue
        duration = max(0.0, float(scene.get("to", 0)) - float(scene.get("from", 0)))
        review = str(image.get("prompt_review", "")).lower()
        prompt = str(image.get("prompt", "")).lower()
        safety_bonus = 0
        if "suitable as wan" in review or "motion-ready" in prompt or "motion-ready" in review:
            safety_bonus += 3
        if any(term in prompt for term in ("water", "light", "wind", "drift", "dust", "curtain", "camera")):
            safety_bonus += 1
        candidates.append({
            "image_id": image_id,
            "duration": round(duration, 2),
            "score": round(duration * 10 + safety_bonus, 2),
            "scene_id": scene.get("id"),
            "script_excerpt": scene.get("script_excerpt", ""),
        })
    best = max(candidates, key=lambda row: (row["score"], row["duration"], str(row["image_id"])), default=None)

    for job in jobs:
        if job.get("id") == opening_job.get("id"):
            job["reference"] = opening_reference
            job["selection_reason"] = "opening_hook"
        elif best and job.get("id") == longest_job.get("id"):
            job["reference"] = best["image_id"]
            job["selection_reason"] = "longest_semantic_safe_scene"

    return jobs, {
        "enabled": True,
        "selection_policy": policy.get("selection_policy", "opening_hook_plus_longest_semantic_safe"),
        "max_generation_seconds": max_generation_seconds,
        "opening_reference": opening_reference,
        "longest_reference": best["image_id"] if best else str(longest_job.get("reference", "")),
        "longest_candidate": best,
        "original_references": original_references,
        "note": "Wan clips are generated for at most the configured cap; longer on-screen scene durations are handled in Remotion.",
    }


def apply_wan_scene_policy(
    config: dict[str, Any],
    scenes: list[dict[str, Any]],
    video_jobs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    policy = config.get("article_visual_assets", {}).get("wan_policy", {})
    if not policy.get("enabled"):
        return scenes

    original_references = {
        str(item.get("id")): str(item.get("reference", ""))
        for item in config.get("article_visual_assets", {}).get("videos", [])
    }
    selected_by_reference = {
        str(job.get("reference")): str(job.get("id"))
        for job in video_jobs
        if str(job.get("reference", "")).startswith("P")
    }
    selected_reference_by_video = {
        str(job.get("id")): str(job.get("reference", ""))
        for job in video_jobs
    }
    duration_by_video = {
        str(job.get("id")): float(job.get("duration_seconds", 4))
        for job in video_jobs
    }

    updated_scenes: list[dict[str, Any]] = []
    for scene in scenes:
        updated = dict(scene)
        image_id = _image_id_from_scene(updated)
        video_id = _video_id_from_scene(updated)
        if image_id in selected_by_reference:
            target_video = selected_by_reference[image_id]
            scene_duration = max(0.12, float(updated.get("to", 0)) - float(updated.get("from", 0)))
            generated_duration = duration_by_video.get(target_video, 4.0)
            updated["kind"] = "video"
            updated["src"] = f"video/{target_video}.mp4"
            updated.pop("motion", None)
            updated["playbackRate"] = round(max(0.5, min(1.0, generated_duration / scene_duration)), 2)
            updated["wan_reference"] = image_id
            updated["wan_selection_reason"] = "selected_reference_scene"
        elif video_id and original_references.get(video_id) != selected_reference_by_video.get(video_id):
            fallback_reference = original_references.get(video_id, "")
            if fallback_reference.startswith("P"):
                updated["kind"] = "still"
                updated["src"] = f"images/{fallback_reference}.png"
                updated["motion"] = updated.get("motion") or "drift-up"
                updated.pop("playbackRate", None)
                updated["wan_selection_reason"] = "converted_old_wan_placeholder_to_still"
        updated_scenes.append(updated)
    return updated_scenes


def load_exact_captions_for_project(target: Path) -> list[dict[str, Any]]:
    path = target / "artifacts" / "exact_captions.json"
    if not path.is_file():
        return []
    payload = load_json(path)
    return [
        {"start": item["start"], "end": item["end"], "text": str(item["text"]).strip()}
        for item in payload.get("segments", [])
        if str(item.get("text", "")).strip()
    ]


def resolve_wan_generation_plan_for_project(
    config: dict[str, Any],
    target: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    captions = load_exact_captions_for_project(target)
    max_generation_seconds = float(
        config.get("article_visual_assets", {}).get("wan_policy", {}).get("max_generation_seconds", 5)
    )
    if not captions:
        return _base_video_jobs(config, max_generation_seconds), {
            "enabled": False,
            "reason": "exact captions unavailable; using reviewed episode video references",
            "max_generation_seconds": max_generation_seconds,
        }
    scenes = [dict(scene) for scene in config.get("edit", {}).get("scenes", [])]
    cards = [dict(card) for card in config.get("edit", {}).get("info_cards", [])]
    duration = max(
        float(config.get("duration_seconds", 80)),
        max((float(caption["end"]) for caption in captions), default=0.0),
        max((float(scene.get("to", 0)) for scene in scenes), default=0.0),
        max((float(card.get("to", 0)) for card in cards), default=0.0),
    ) + 0.8
    retimed, timeline_policy = retime_scenes_to_caption_boundaries(scenes, captions, round(duration, 2))
    jobs, wan_policy = resolve_wan_generation_plan(config, retimed)
    wan_policy["timeline_policy"] = timeline_policy
    return jobs, wan_policy
