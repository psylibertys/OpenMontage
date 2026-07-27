#!/usr/bin/env python3
"""Prepare and package independent TreeElf fable GPU batches.

This module contains deterministic planning, state persistence, asset
verification, and local Remotion staging. Creative decisions remain in the
reviewed episode JSON files and generation is performed through OpenMontage's
normal pipeline/tools using the emitted GPU job manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.treeelf_music import (  # noqa: E402
    DEFAULT_CATALOG_PATH,
    DEFAULT_OVERRIDES_PATH,
    DEFAULT_USAGE_LEDGER_PATH,
    normalize_background_music,
    record_music_usage,
    select_music_track,
)
from scripts.finalize_autodl_comfyui_batch import (  # noqa: E402
    _require_empty_queue,
    remote_runtime_manifest,
)


PROJECTS_ROOT = REPO_ROOT / "projects"
DEFAULT_SERIES = REPO_ROOT / "workflow_configs" / "treeelf-fable" / "series-v1.json"
DEFAULT_BATCH = REPO_ROOT / "workflow_configs" / "treeelf-fable" / "batch-template.json"
REMOTION_ROOT = REPO_ROOT / "remotion-composer"

CAMERA_VARIATIONS = (
    "establishing wide composition with readable geography",
    "medium composition focused on the protagonist's action",
    "close detail emphasizing the story object and tactile texture",
    "over-the-shoulder composition with layered foreground",
    "quiet reaction composition with restrained optimistic expression",
)

TECHNICAL_GUARDRAILS = (
    "text-free generated image",
    "no readable text",
    "no letters",
    "no logo",
    "no watermark",
    "no pseudo typography",
)

FABLE_NARRATION_INSTRUCT = (
    "成年女性中文旁白，音色温暖清澈，语速中等、略有从容感，发音清晰自然。"
    "整体像在讲一个真实发生过的寓言故事：亲近、安静、有画面感。"
    "情绪表达克制而有微光，奇妙或荒诞的句子语气轻轻变亮，"
    "关键转折处有自然停顿，结尾保留一点温柔余韵，让寓意慢慢落下。"
)

TECHNICAL_NEGATIVE_TERMS = (
    "no text",
    "no letters",
    "no logo",
    "no watermark",
    "no readable text",
    "no pseudo typography",
    "no morphing",
    "no extra limbs",
    "stable anatomy",
    "stable identity",
    "stable structure",
)

AESTHETIC_NEGATIVE_PATTERNS = (
    "no under-eye shadows",
    "no male figure",
    "no male movers",
    "no hiding gesture",
    "no pattern to hide",
    "avoid ",
    "不要",
    "避免",
)

COVER_HUMAN_TERMS = (
    "woman", "girl", "boy", "man", "person", "people", "portrait", "protagonist",
    "young woman", "young man", "character", "face", "hand", "hands",
    "女人", "女孩", "男孩", "男人", "人物", "人像", "肖像", "主角", "脸", "手",
)

TTS_WORKFLOWS_WITH_EFFECTIVE_INSTRUCT = {
    "qwen3_tts_custom_voice",
    "qwen3_tts_voice_design",
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"planned", "failed"},
    "planned": {"gpu_queued", "failed"},
    "gpu_queued": {"gpu_assets_complete", "needs_gpu_repair", "failed"},
    "needs_gpu_repair": {"gpu_queued", "gpu_assets_complete", "failed"},
    "gpu_assets_complete": {"local_packaging", "needs_gpu_repair", "failed"},
    "local_packaging": {"completed", "needs_gpu_repair", "failed"},
    "completed": set(),
    "failed": {"planned"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def elapsed_seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 3)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_filename(value: str, *, fallback: str = "树精灵寓言") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]+", " ", str(value)).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or fallback


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_v{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"too many filename collisions:{path}")


def _atomic_link_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.part"
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    try:
        os.link(source, temporary)
        mode = "hardlink"
    except OSError:
        shutil.copy2(source, temporary)
        mode = "copy"
    temporary.replace(destination)
    return mode


def _delivery_video_path(episode: dict[str, Any], delivery_root: Path) -> Path:
    title = _safe_filename(str(episode.get("title") or episode.get("project_id")))
    video_name = episode.get("delivery_filename") or f"{title}.mp4"
    video = delivery_root / _safe_filename(video_name)
    if not video.suffix:
        video = video.with_suffix(".mp4")
    return _unique_path(video)


def media_duration_seconds(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def _prompt_guardrails(series: dict[str, Any]) -> list[str]:
    return [
        str(item)
        for item in series.get("visual", {}).get("technical_guardrails", TECHNICAL_GUARDRAILS)
        if str(item).strip()
    ]


def _append_guardrails(prompt: str, guardrails: list[str]) -> str:
    existing = prompt.lower()
    additions = [item for item in guardrails if item.lower() not in existing]
    if not additions:
        return prompt
    return f"{prompt.rstrip(' .')}. {', '.join(additions)}"


def _contains_allowed_technical_negative(value: str, pattern: str) -> bool:
    lowered = value.lower()
    if pattern in {"不要", "避免", "avoid "}:
        return False
    return any(term in lowered and pattern in term for term in TECHNICAL_NEGATIVE_TERMS)


def cover_human_prompt_terms(prompt: str) -> list[str]:
    lowered = prompt.lower()
    found: list[str] = []
    for term in COVER_HUMAN_TERMS:
        term_lower = term.lower()
        if re.search(r"[a-z]", term_lower):
            if re.search(rf"(?<![a-z]){re.escape(term_lower)}(?![a-z])", lowered):
                found.append(term)
        elif term_lower in lowered:
            found.append(term)
    return found


def prompt_review_warnings(episode: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []

    def check(label: str, value: str) -> None:
        lowered = value.lower()
        for pattern in AESTHETIC_NEGATIVE_PATTERNS:
            if pattern in lowered and not _contains_allowed_technical_negative(lowered, pattern):
                warnings.append(
                    {
                        "field": label,
                        "pattern": pattern,
                        "message": "creative prompt contains an aesthetic negative; rewrite as a positive visual target",
                    }
                )

    for label, value in (
        ("character_pack.master_prompt", episode.get("character_pack", {}).get("master_prompt", "")),
        ("cover_prompt", episode.get("cover_prompt", "")),
        ("hero_wan.prompt", episode.get("hero_wan", {}).get("prompt", "")),
    ):
        check(label, str(value))
    for index, prompt in enumerate(episode.get("character_pack", {}).get("reference_prompts", []), start=1):
        check(f"character_pack.reference_prompts[{index}]", str(prompt))
    for beat in episode.get("semantic_beats", []):
        if beat.get("prompt"):
            check(f"{beat.get('id')}.prompt", str(beat["prompt"]))
        for index, prompt in enumerate(beat.get("prompt_variants", []), start=1):
            check(f"{beat.get('id')}.prompt_variants[{index}]", str(prompt))
    return warnings


def voice_instruction_report(series: dict[str, Any]) -> dict[str, Any]:
    template = str(series.get("voice", {}).get("workflow_template", ""))
    instruct = str(series.get("voice", {}).get("instruct", "")).strip()
    effective = bool(instruct and template in TTS_WORKFLOWS_WITH_EFFECTIVE_INSTRUCT)
    return {
        "version": "1.0",
        "workflow_template": template,
        "instruct_present": bool(instruct),
        "instruct_effective_in_current_workflow": effective,
        "checked_at": utc_now(),
        "note": (
            "当前 Qwen3-TTS workflow 有独立 instruct 输入，配音提示词会进入模型。"
            if effective
            else "当前 voice_clone_load workflow 与心哲灵固定声线一致：正式批量生成以已保存 voice_name 声包为准；instruct 只作为声线档案和审核说明，不作为 clone-load 阶段的强控制参数。"
        ),
    }


def _tts_inputs(series: dict[str, Any], narration_text: str, output_path: Path) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "text": narration_text,
        "voice_name": series["voice"]["voice_name"],
        "language": series["voice"]["language"],
        **(
            {"max_new_tokens": series["voice"]["max_new_tokens"]}
            if series["voice"].get("max_new_tokens") is not None
            else {}
        ),
        "output_path": str(output_path),
    }
    if voice_instruction_report(series)["instruct_effective_in_current_workflow"]:
        inputs["instruct"] = series["voice"].get("instruct", FABLE_NARRATION_INSTRUCT)
    return inputs


def _text_fragments(text: str, *, max_chars: int = 28) -> list[str]:
    clauses = [part.strip() for part in re.findall(r"[^，。；：！？!?\n]+[，。；：！？!?]?", text) if part.strip()]
    fragments: list[str] = []
    for clause in clauses:
        if len(clause) <= max_chars:
            fragments.append(clause)
            continue
        remaining = clause
        while len(remaining) > max_chars:
            split_at = max(remaining.rfind(mark, 0, max_chars + 1) for mark in "，；：,;:") + 1
            if split_at <= 0:
                split_at = max_chars
            fragments.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()
        if remaining:
            fragments.append(remaining)
    return fragments


def build_fable_captions(text: str, duration_seconds: float) -> list[dict[str, Any]]:
    fragments = _text_fragments(text)
    if not fragments:
        return []
    weights = [max(1, len(re.sub(r"[，。；：！？!?\s]", "", item))) for item in fragments]
    total = sum(weights)
    cursor = 0.0
    rows: list[dict[str, Any]] = []
    for index, (fragment, weight) in enumerate(zip(fragments, weights)):
        end = duration_seconds if index == len(fragments) - 1 else cursor + duration_seconds * weight / total
        rows.append(
            {
                "text": fragment,
                "startMs": round(cursor * 1000),
                "endMs": round(max(cursor + 0.12, end) * 1000),
            }
        )
        cursor = end
    return rows


def _chunk_caption_segments(
    captions: list[dict[str, Any]],
    count: int,
    duration_seconds: float,
) -> list[dict[str, Any]]:
    if not captions:
        return []
    count = max(1, count)
    duration_ms = max(1, round(duration_seconds * 1000))
    if count == 1:
        return [
            {
                "items": captions,
                "start_index": 0,
                "end_index": len(captions) - 1,
                "startMs": 0,
                "endMs": duration_ms,
            }
        ]
    boundaries = sorted(
        {
            0,
            duration_ms,
            *(
                int(caption["endMs"])
                for caption in captions
                if 0 < int(caption["endMs"]) < duration_ms
            ),
        }
    )
    minimum_segment_ms = max(1800, round(duration_ms / count * 0.55))
    cuts = [0]
    for index in range(1, count):
        remaining = count - index
        minimum = cuts[-1] + minimum_segment_ms
        maximum = duration_ms - minimum_segment_ms * remaining
        target = round(index * duration_ms / count)
        if minimum > maximum:
            cut = target
        else:
            candidates = [value for value in boundaries if minimum <= value <= maximum]
            cut = min(candidates, key=lambda value: (abs(value - target), value)) if candidates else max(minimum, min(target, maximum))
        cuts.append(round(cut))
    cuts.append(duration_ms)
    groups: list[dict[str, Any]] = []
    for index in range(count):
        start_ms = int(cuts[index])
        end_ms = int(cuts[index + 1])
        overlapping = [
            (caption_index, caption)
            for caption_index, caption in enumerate(captions)
            if int(caption["endMs"]) > start_ms and int(caption["startMs"]) < end_ms
        ]
        if not overlapping:
            nearest_index = min(
                range(len(captions)),
                key=lambda caption_index: abs(
                    ((int(captions[caption_index]["startMs"]) + int(captions[caption_index]["endMs"])) / 2)
                    - ((start_ms + end_ms) / 2)
                ),
            )
            overlapping = [(nearest_index, captions[nearest_index])]
        groups.append(
            {
                "items": [item for _, item in overlapping],
                "start_index": overlapping[0][0],
                "end_index": overlapping[-1][0],
                "startMs": start_ms,
                "endMs": end_ms,
            }
        )
    return groups


def _caption_group_from_items(
    captions: list[dict[str, Any]],
    start_index: int,
    end_index: int,
) -> dict[str, Any]:
    start_index = max(0, min(start_index, len(captions) - 1))
    end_index = max(start_index, min(end_index, len(captions) - 1))
    items = captions[start_index : end_index + 1]
    return {
        "items": items,
        "start_index": start_index,
        "end_index": end_index,
        "startMs": int(items[0]["startMs"]),
        "endMs": int(items[-1]["endMs"]),
    }


def _caption_groups_from_existing_ranges(
    captions: list[dict[str, Any]],
    slots: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    if not captions or not slots:
        return None
    groups: list[dict[str, Any]] = []
    last_end = -1
    for slot in slots:
        caption_range = slot.get("caption_range") if isinstance(slot.get("caption_range"), dict) else None
        if not caption_range:
            return None
        start_index = int(caption_range.get("start_index", -1))
        end_index = int(caption_range.get("end_index", -1))
        if start_index < 0 or end_index < start_index or end_index >= len(captions):
            return None
        if start_index < last_end:
            return None
        groups.append(_caption_group_from_items(captions, start_index, end_index))
        last_end = end_index
    return groups


def _caption_groups_from_beat_anchors(
    captions: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    previous_duration: float,
    calibrated_duration: float,
) -> list[dict[str, Any]] | None:
    if not captions or not slots or previous_duration <= 0 or calibrated_duration <= 0:
        return None
    ranges: list[tuple[int, int, str]] = []
    cursor = 0
    while cursor < len(slots):
        beat_id = str(slots[cursor].get("beat_id", ""))
        end = cursor + 1
        while end < len(slots) and str(slots[end].get("beat_id", "")) == beat_id:
            end += 1
        ranges.append((cursor, end, beat_id))
        cursor = end

    result: list[dict[str, Any] | None] = [None] * len(slots)
    caption_centers = [
        (int(row["startMs"]) + int(row["endMs"])) / 2
        for row in captions
    ]
    used_until = 0
    for range_index, (start_slot, end_slot, _beat_id) in enumerate(ranges):
        old_start = min(float(slot.get("from", 0)) for slot in slots[start_slot:end_slot])
        old_end = max(float(slot.get("to", old_start)) for slot in slots[start_slot:end_slot])
        mapped_start = old_start / previous_duration * calibrated_duration * 1000
        mapped_end = old_end / previous_duration * calibrated_duration * 1000
        if range_index == len(ranges) - 1:
            candidate_indices = list(range(used_until, len(captions)))
        else:
            candidate_indices = [
                index
                for index in range(used_until, len(captions))
                if mapped_start <= caption_centers[index] < mapped_end
            ]
        remaining_slot_count = sum(end - start for start, end, _ in ranges[range_index + 1 :])
        maximum_end_exclusive = len(captions) - remaining_slot_count
        if not candidate_indices:
            take = max(1, min(end_slot - start_slot, maximum_end_exclusive - used_until + 1))
            candidate_indices = list(range(used_until, min(len(captions), used_until + take)))
        last_allowed = max(used_until, maximum_end_exclusive)
        candidate_indices = [index for index in candidate_indices if index <= last_allowed]
        if not candidate_indices:
            return None
        slot_count = end_slot - start_slot
        caption_count = len(candidate_indices)
        for offset in range(slot_count):
            local_start = math.floor(offset * caption_count / slot_count)
            local_end = max(local_start, math.floor((offset + 1) * caption_count / slot_count) - 1)
            absolute_start = candidate_indices[local_start]
            absolute_end = candidate_indices[local_end]
            result[start_slot + offset] = _caption_group_from_items(captions, absolute_start, absolute_end)
        used_until = candidate_indices[-1] + 1
    if any(group is None for group in result):
        return None
    return [group for group in result if group is not None]


def _semantic_caption_groups_for_slots(
    captions: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    previous_duration: float,
    calibrated_duration: float,
) -> tuple[list[dict[str, Any]], str]:
    by_existing_ranges = _caption_groups_from_existing_ranges(captions, slots)
    if by_existing_ranges:
        return by_existing_ranges, "existing_caption_ranges"
    by_beat_anchors = _caption_groups_from_beat_anchors(captions, slots, previous_duration, calibrated_duration)
    if by_beat_anchors:
        return by_beat_anchors, "beat_anchor_ranges"
    return _chunk_caption_segments(captions, len(slots), calibrated_duration), "duration_even_caption_chunks"


def _slot_motion_safety_score(slot: dict[str, Any]) -> int:
    text = " ".join(
        str(slot.get(key, ""))
        for key in ("prompt", "story_event", "fable_law", "art_style_logic", "script_excerpt")
    ).lower()
    score = 0
    if any(term in text for term in ("stable", "calm camera", "camera drift", "光", "风", "水", "雾", "影", "缓慢", "轻轻", "漂移")):
        score += 2
    if any(term in text for term in ("hand", "hands", "finger", "transparent body", "multiple people", "crowd", "手", "脚", "透明身体", "多人", "人群", "残肢")):
        score -= 3
    return score


def select_fable_wan_slot(
    slots: list[dict[str, Any]],
    hero: dict[str, Any],
    series: dict[str, Any],
) -> dict[str, Any] | None:
    if not slots or not hero.get("enabled"):
        return None
    manual_scene_id = str(hero.get("scene_id", "")).strip()
    policy = str(hero.get("selection_policy") or ("manual_scene_id" if manual_scene_id else series.get("pacing", {}).get("wan_selection_policy", "")) or "manual_scene_id")
    if policy in {"manual", "manual_scene_id"} and manual_scene_id:
        return next((slot for slot in slots if slot["id"] == manual_scene_id), None)
    if policy != "opening_fable_event_only_or_none":
        if manual_scene_id:
            return next((slot for slot in slots if slot["id"] == manual_scene_id), None)
        return slots[0]

    opening = slots[0]
    if str(opening.get("wan_motion_safety", "")).lower() in {"rejected", "risky"}:
        return None
    explicit_opening_candidate = opening.get("wan_candidate") is True or str(opening.get("fable_event_stage", "")) == "first_manifestation"
    if not explicit_opening_candidate:
        return None
    opening_text = " ".join(str(opening.get(key, "")) for key in ("story_event", "fable_law", "script_excerpt", "prompt"))
    opening_has_fable_event = bool(str(opening.get("fable_law", "")).strip()) or any(
        marker in opening_text
        for marker in ("第一次", "显现", "出现", "发生", "开始", "透明", "变成", "长出", "候车室", "墙纸")
    )
    if opening_has_fable_event and _slot_motion_safety_score(opening) >= -1:
        selected = dict(opening)
        selected["wan_selection_reason"] = "opening_fable_event"
        return selected
    return None


def _beat_prompt(beat: dict[str, Any], within_beat: int) -> str:
    if beat.get("prompt"):
        return str(beat["prompt"]).strip()
    prompts = [str(value).strip() for value in beat.get("prompt_variants", []) if str(value).strip()]
    if not prompts:
        raise ValueError(f"{beat.get('id', 'semantic beat')} requires prompt or prompt_variants")
    return prompts[min(within_beat, len(prompts) - 1)]


def _beat_story_fields(beat: dict[str, Any]) -> dict[str, str]:
    return {
        "story_event": str(beat.get("story_event") or beat.get("summary") or "").strip(),
        "fable_law": str(beat.get("fable_law", "")).strip(),
        "art_style_logic": str(beat.get("art_style_logic", "")).strip(),
    }


def build_visual_brief(episode: dict[str, Any], series: dict[str, Any], narration_text: str) -> dict[str, Any]:
    provided = episode.get("visual_brief", {}) if isinstance(episode.get("visual_brief"), dict) else {}
    protagonist = episode.get("protagonist", {})
    beats = episode.get("semantic_beats", [])
    return {
        "version": "1.0",
        "project_id": episode.get("project_id"),
        "title": episode.get("title"),
        "generated_at": utc_now(),
        "source_text_sha256": hashlib.sha256(narration_text.encode("utf-8")).hexdigest(),
        "fable_law": provided.get("fable_law") or next((beat.get("fable_law") for beat in beats if beat.get("fable_law")), ""),
        "central_metaphor": provided.get("central_metaphor", ""),
        "emotional_core": provided.get("emotional_core", []),
        "symbolic_objects": provided.get("symbolic_objects", []),
        "protagonist_identity": provided.get("protagonist_identity") or protagonist.get("description", ""),
        "art_style_logic": provided.get("art_style_logic") or series.get("visual", {}).get("art_style_default", ""),
        "technical_guardrails": provided.get("technical_guardrails") or _prompt_guardrails(series),
        "visual_logic": {
            "story_event": "清楚说明这张图发生了什么：人物、地点、动作、物件。",
            "fable_law": "说明本篇超现实规则如何像真实事件一样显现。",
            "art_style_logic": "说明艺术语言为什么适合这篇寓言，而不是作为装饰。",
        },
    }


def _music_candidates(config: dict[str, Any], series: dict[str, Any]) -> list[Path]:
    music = series.get("music", {})
    roots = [
        config.get("music_library_dir"),
        config.get("music", {}).get("library_dir") if isinstance(config.get("music"), dict) else None,
        music.get("library_dir"),
    ]
    source = Path(str(config.get("music_source", ""))).expanduser()
    if source.is_file():
        roots.append(str(source.parent))
    suffixes = {".mp3", ".wav", ".m4a", ".flac", ".aac"}
    paths: list[Path] = []
    for raw in roots:
        if not raw:
            continue
        root = Path(str(raw)).expanduser()
        if root.is_file() and root.suffix.lower() in suffixes:
            paths.append(root)
        elif root.is_dir():
            paths.extend(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)
    return sorted(set(paths), key=lambda path: str(path))


def select_music_source(
    episode: dict[str, Any],
    series: dict[str, Any],
    *,
    used_music_paths: list[str] | None = None,
    usage_ledger_path: Path | None = None,
) -> dict[str, Any]:
    text = "\n".join(
        [
            str(episode.get("title", "")),
            str(episode.get("cover_title", "")),
            str(episode.get("narration_text", "")),
            str(episode.get("visual_brief", {}).get("central_metaphor", "")) if isinstance(episode.get("visual_brief"), dict) else "",
        ]
    )
    keywords = ["ambient", "chillwave", "piano", "soundtrack", "温暖", "梦幻", "轻音乐", "纯音乐"]
    if any(word in text for word in ("雨", "透明", "雾", "光")):
        keywords += ["ambient", "dreamy", "梦幻"]
    if any(word in text for word in ("候车", "时间", "日历", "等待")):
        keywords += ["lo-fi", "downtempo", "study"]
    if any(word in text for word in ("墙", "家具", "房间", "家")):
        keywords += ["neo-classical", "piano", "soundtrack"]
    configured = episode.get("music", {}).get("preferred_keywords", []) if isinstance(episode.get("music"), dict) else []
    keywords.extend(str(item) for item in configured)
    keywords = list(dict.fromkeys(keyword.lower() for keyword in keywords))
    fallback = Path(str(episode.get("music_source", ""))).expanduser()
    music = series.get("music", {})
    roots: list[Path] = []
    for raw in (
        episode.get("music_library_dir"),
        episode.get("music", {}).get("library_dir") if isinstance(episode.get("music"), dict) else None,
        music.get("library_dir"),
    ):
        if raw:
            roots.append(Path(str(raw)).expanduser())
    if fallback.is_file() and fallback.parent not in roots:
        roots.append(fallback.parent)
    return select_music_track(
        project_id=str(episode.get("project_id", "")),
        series="treeelf-fable",
        keywords=keywords,
        library_dirs=roots,
        fallback_source=fallback,
        used_music_paths=used_music_paths,
        catalog_path=Path(str(music.get("catalog_path", DEFAULT_CATALOG_PATH))).expanduser(),
        overrides_path=Path(str(music.get("overrides_path", DEFAULT_OVERRIDES_PATH))).expanduser(),
        usage_ledger_path=usage_ledger_path or Path(str(music.get("usage_ledger_path", DEFAULT_USAGE_LEDGER_PATH))).expanduser(),
    )


def _strict_gate(series: dict[str, Any], key: str, default: bool = True) -> bool:
    gates = series.get("quality_gates", {})
    if key in gates:
        return bool(gates[key])
    return default


def _caption_source_is_calibrated(path: Path) -> bool:
    if not path.is_file():
        return False
    payload = load_json(path)
    source = str(payload.get("source", "")).lower()
    return bool(payload.get("whisper_corrected") or payload.get("manually_corrected") or "whisper" in source or "manual" in source)


def sync_visual_plan_to_captions(plan: dict[str, Any], captions: list[dict[str, Any]]) -> dict[str, Any]:
    slots = plan.get("slots", [])
    if not slots or not captions:
        return plan
    previous_duration = float(plan["duration_seconds"])
    calibrated_duration = max(int(caption["endMs"]) for caption in captions) / 1000
    duration = calibrated_duration or previous_duration
    groups, sync_strategy = _semantic_caption_groups_for_slots(captions, slots, previous_duration, duration)
    updated = json.loads(json.dumps(plan))
    updated["previous_duration_seconds"] = round(previous_duration, 3)
    updated["duration_seconds"] = round(duration, 3)
    updated["duration_source"] = "calibrated_captions"
    updated["duration_delta_seconds"] = round(duration - previous_duration, 3)
    updated["caption_sync_strategy"] = sync_strategy
    for slot, group in zip(updated["slots"], groups):
        slot["from"] = round(int(group["startMs"]) / 1000, 3)
        slot["to"] = round(int(group["endMs"]) / 1000, 3)
        slot["duration"] = round(slot["to"] - slot["from"], 3)
        slot["script_excerpt"] = "".join(str(item["text"]) for item in group["items"])
        slot["caption_range"] = {
            "start_index": group["start_index"],
            "end_index": group["end_index"],
            "startMs": int(group["startMs"]),
            "endMs": int(group["endMs"]),
        }
    updated["timing_policy"] = "scene ranges are synchronized from calibrated captions before Remotion staging, preserving existing caption ranges or beat anchors when available"
    updated["caption_sync_updated_at"] = utc_now()
    return updated


def build_wan_retarget_report(original_plan: dict[str, Any], synced_plan: dict[str, Any]) -> dict[str, Any]:
    original = original_plan.get("wan_selection", {}) if isinstance(original_plan.get("wan_selection"), dict) else {}
    current = synced_plan.get("wan_selection", {}) if isinstance(synced_plan.get("wan_selection"), dict) else {}
    scene_id = str(current.get("scene_id") or original.get("scene_id", ""))
    original_slot = next((slot for slot in original_plan.get("slots", []) if slot.get("id") == scene_id), None)
    current_slot = next((slot for slot in synced_plan.get("slots", []) if slot.get("id") == scene_id), None)
    original_duration = round(float(original_slot["to"]) - float(original_slot["from"]), 3) if original_slot else 0
    current_duration = round(float(current_slot["to"]) - float(current_slot["from"]), 3) if current_slot else 0
    duration_delta = round(current_duration - original_duration, 3)
    usable = bool(scene_id and current_slot)
    recommendation = "reuse_existing_wan_with_timeline_retarget"
    if not scene_id:
        recommendation = "no_wan_selected"
    elif not current_slot:
        recommendation = "manual_review_required_scene_anchor_missing"
    elif abs(duration_delta) > 2.0:
        recommendation = "reuse_existing_wan_but_review_timing_shift"
    return {
        "version": "1.0",
        "scene_id": scene_id,
        "semantic_anchor": {
            "beat_id": original.get("beat_id", current.get("beat_id", "")),
            "story_event": original.get("story_event", current_slot.get("story_event", "") if current_slot else ""),
            "fable_law": original.get("fable_law", current_slot.get("fable_law", "") if current_slot else ""),
            "script_excerpt": original.get("script_excerpt", ""),
        },
        "original_range": {
            "from": original_slot.get("from") if original_slot else None,
            "to": original_slot.get("to") if original_slot else None,
            "duration_seconds": original_duration,
        },
        "retargeted_range": {
            "from": current_slot.get("from") if current_slot else None,
            "to": current_slot.get("to") if current_slot else None,
            "duration_seconds": current_duration,
            "script_excerpt": current_slot.get("script_excerpt", "") if current_slot else "",
        },
        "duration_delta_seconds": duration_delta,
        "usable_without_regeneration": usable,
        "recommendation": recommendation,
        "policy": "Wan is treated as a semantic event asset; calibrated captions retarget timing in Remotion and do not trigger GPU regeneration by default.",
        "checked_at": utc_now(),
    }


def build_character_contact_sheet(
    references: list[str],
    output_path: Path,
    *,
    title: str,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image_paths = [Path(value).expanduser() for value in references]
    missing = [str(path) for path in image_paths if not path.is_file() or path.stat().st_size <= 0]
    if missing:
        raise FileNotFoundError("cannot build character contact sheet; missing references:\n" + "\n".join(missing))

    thumb_w, thumb_h = 240, 426
    padding = 28
    header_h = 72
    label_h = 42
    sheet = Image.new("RGB", (padding * 5 + thumb_w * 4, header_h + thumb_h + label_h + padding), "#151414")
    draw = ImageDraw.Draw(sheet)
    font_candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    font = next((ImageFont.truetype(path, 20) for path in font_candidates if Path(path).is_file()), ImageFont.load_default())
    try:
        draw.text((padding, 22), title, fill="#F7F2E8", font=font)
    except UnicodeEncodeError:
        draw.text((padding, 22), str(title).encode("ascii", "ignore").decode("ascii"), fill="#F7F2E8", font=ImageFont.load_default())
    labels = ["front", "left 3/4", "right profile", "back 3/4"]
    for index, path in enumerate(image_paths):
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_w, thumb_h))
        x = padding + index * (thumb_w + padding)
        y = header_h + (thumb_h - image.height) // 2
        sheet.paste(image, (x, y))
        draw.text((x, header_h + thumb_h + 12), labels[index], fill="#D9B56D", font=font)
    sheet.save(output_path)
    return {
        "path": str(output_path),
        "size": output_path.stat().st_size,
        "sha256": sha256_file(output_path),
    }


def default_character_review(episode: dict[str, Any], references: list[str], contact_sheet: Path) -> dict[str, Any]:
    return {
        "version": "1.0",
        "project_id": episode["project_id"],
        "approved": False,
        "reviewer": "",
        "reviewed_at": "",
        "contact_sheet": str(contact_sheet),
        "reference_image_paths": references,
        "checks": {
            "same_identity_all_views": False,
            "four_distinct_views": False,
            "stable_face_or_design": False,
            "stable_clothing_or_signature_features": False,
            "anatomy_acceptable": False,
            "no_text_or_pseudo_text": False,
        },
        "notes": "人工审核通过后，把 approved 和各项 checks 改为 true，再刷新正文视觉任务。",
    }


def require_character_review(episode: dict[str, Any], target: Path) -> dict[str, Any]:
    review_path = target / "artifacts" / "character_review.json"
    if not review_path.is_file():
        raise PermissionError(f"{episode['project_id']} needs approved character_review.json before Flux scene generation")
    review = load_json(review_path)
    failed = [key for key, value in review.get("checks", {}).items() if value is not True]
    if review.get("approved") is not True or failed:
        raise PermissionError(f"{episode['project_id']} character review is not approved; failed checks: {failed}")
    return review


def default_visual_qc(episode: dict[str, Any], plan: dict[str, Any], target: Path | None = None) -> dict[str, Any]:
    scene_root = target / "assets" / "images" / "scenes" if target else None
    cover_root = target / "assets" / "images" / "cover" if target else None
    return {
        "version": "1.0",
        "project_id": episode["project_id"],
        "approved": False,
        "reviewed_at": "",
        "scenes": {
            slot["id"]: {
                "image_path": str(scene_root / slot["output_name"]) if scene_root and slot.get("output_name") else "",
                "output_name": slot.get("output_name", ""),
                "beat_id": slot.get("beat_id", ""),
                "workflow": slot.get("workflow", ""),
                "caption_excerpt": slot.get("script_excerpt", ""),
                "caption_range": slot.get("caption_range"),
                "story_event": slot.get("story_event", ""),
                "fable_law": slot.get("fable_law", ""),
                "art_style_logic": slot.get("art_style_logic", ""),
                "approved": False,
                "story_matches_caption": False,
                "anatomy_acceptable": False,
                "identity_stable_when_applicable": False,
                "text_free": False,
                "wan_motion_safety": "approved | risky | rejected",
                "repair_needed": True,
                "notes": "",
            }
            for slot in plan.get("slots", [])
        },
        "cover": {
            "background_path": str(cover_root / "cover-background.png") if cover_root else "",
            "final_cover_path": str(cover_root / "cover-final.png") if cover_root else "",
            "cover_title": episode.get("cover_title", ""),
            "approved": False,
            "human_free": False,
            "text_free": False,
            "logo_free": False,
            "watermark_free": False,
            "title_safe_space": False,
            "notes": "",
        },
        "notes": "人工审核每张正文图和封面背景；未通过的图重生或修复后再进入 Remotion。",
    }


def _slot_needs_identity_check(slot: dict[str, Any]) -> bool:
    if str(slot.get("workflow", "")) == "flux2_klein_4ref":
        return True
    text = " ".join(
        str(slot.get(key, ""))
        for key in ("prompt", "story_event", "script_excerpt")
    ).lower()
    return any(
        marker in text
        for marker in (
            "episode protagonist identity",
            "protagonist",
            "same identity",
            "stable identity",
            "person",
            "woman",
            "girl",
            "主角",
            "人物",
            "女人",
            "女孩",
            "她",
            "他",
        )
    )


def require_visual_qc(episode: dict[str, Any], target: Path, plan: dict[str, Any]) -> dict[str, Any]:
    qc_path = target / "artifacts" / "visual_qc.json"
    if not qc_path.is_file():
        dump_json(qc_path, default_visual_qc(episode, plan, target))
        raise PermissionError(f"{episode['project_id']} needs approved visual_qc.json before Remotion staging")
    qc = load_json(qc_path)
    failed_scenes = [
        scene_id
        for scene_id, row in qc.get("scenes", {}).items()
        if row.get("approved") is not True
        or row.get("story_matches_caption") is not True
        or row.get("anatomy_acceptable") is not True
        or row.get("text_free") is not True
        or row.get("repair_needed") is True
    ]
    slots_by_id = {str(slot.get("id", "")): slot for slot in plan.get("slots", [])}
    failed_scenes.extend(
        scene_id
        for scene_id, row in qc.get("scenes", {}).items()
        if _slot_needs_identity_check(slots_by_id.get(str(scene_id), {}))
        and row.get("identity_stable_when_applicable") is not True
    )
    cover = qc.get("cover", {})
    wan_selection = plan.get("wan_selection", {}) if isinstance(plan.get("wan_selection"), dict) else {}
    wan_scene_id = str(wan_selection.get("scene_id", ""))
    if wan_scene_id:
        row = qc.get("scenes", {}).get(wan_scene_id, {})
        if str(row.get("wan_motion_safety", "")).lower() != "approved":
            failed_scenes.append(wan_scene_id)
    cover_failed = [
        key
        for key in ("approved", "human_free", "text_free", "logo_free", "watermark_free", "title_safe_space")
        if cover.get(key) is not True
    ]
    if qc.get("approved") is not True or failed_scenes or cover_failed:
        raise PermissionError(
            f"{episode['project_id']} visual QC is not approved; failed_scenes={failed_scenes}; cover_failed={cover_failed}"
        )
    return qc


def _ffmpeg_mean_volume(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stderr + result.stdout
    mean_match = re.search(r"mean_volume:\s*(-?[0-9.]+)\s*dB", output)
    max_match = re.search(r"max_volume:\s*(-?[0-9.]+)\s*dB", output)
    if result.returncode != 0 or not mean_match:
        return {"path": str(path), "ok": False, "error": output[-1200:]}
    return {
        "path": str(path),
        "ok": True,
        "mean_volume_db": float(mean_match.group(1)),
        "max_volume_db": float(max_match.group(1)) if max_match else None,
    }


def build_audio_mix_qc(narration: Path, music: Path, music_volume: float) -> dict[str, Any]:
    narration_report = _ffmpeg_mean_volume(narration)
    music_report = _ffmpeg_mean_volume(music)
    audible_baseline = 0.18 <= float(music_volume) <= 0.34
    ok = bool(narration_report.get("ok") and music_report.get("ok") and audible_baseline)
    return {
        "version": "1.0",
        "checked_at": utc_now(),
        "narration": narration_report,
        "music": music_report,
        "remotion_music_volume": music_volume,
        "audible_baseline_ok": audible_baseline,
        "approved_for_render": ok,
        "notes": "这是旁白优先 B3 渲染前基准检查；最终仍需要试听确认音乐有氛围但不压旁白。",
    }


def _resolve_episode_paths(batch_path: Path, batch: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for value in batch.get("episode_configs", []):
        path = Path(value).expanduser()
        paths.append(path.resolve() if path.is_absolute() else (batch_path.parent / path).resolve())
    return paths


def _batch_dir(batch: dict[str, Any], projects_root: Path = PROJECTS_ROOT) -> Path:
    return projects_root / str(batch["batch_id"])


def _episode_dir(episode: dict[str, Any], projects_root: Path = PROJECTS_ROOT) -> Path:
    return projects_root / str(episode["project_id"])


def target_image_count(
    duration_seconds: float,
    semantic_beat_count: int,
    target_seconds: float = 5,
) -> int:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if semantic_beat_count <= 0:
        raise ValueError("semantic_beat_count must be positive")
    return max(semantic_beat_count, math.ceil(duration_seconds / target_seconds))


def _beat_ranges(beats: list[dict[str, Any]], duration: float) -> list[tuple[float, float]]:
    timed = all("start" in beat and "end" in beat for beat in beats)
    if timed:
        ranges = [(float(beat["start"]), float(beat["end"])) for beat in beats]
        if any(start < 0 or end <= start for start, end in ranges):
            raise ValueError("semantic beat time ranges must be positive and ordered")
        if any(current[1] > following[0] + 0.001 for current, following in zip(ranges, ranges[1:])):
            raise ValueError("semantic beat time ranges must not overlap")
        return ranges

    weights = [max(0.001, float(beat.get("weight", 1))) for beat in beats]
    total = sum(weights)
    cursor = 0.0
    ranges: list[tuple[float, float]] = []
    for index, weight in enumerate(weights):
        end = duration if index == len(weights) - 1 else cursor + duration * weight / total
        ranges.append((cursor, end))
        cursor = end
    return ranges


def _allocate_counts(ranges: list[tuple[float, float]], total_count: int) -> list[int]:
    if total_count < len(ranges):
        raise ValueError("total_count must cover every semantic beat")
    counts = [1] * len(ranges)
    remaining = total_count - len(ranges)
    if remaining == 0:
        return counts
    durations = [end - start for start, end in ranges]
    total_duration = sum(durations)
    raw = [remaining * duration / total_duration for duration in durations]
    floors = [math.floor(value) for value in raw]
    counts = [base + extra for base, extra in zip(counts, floors)]
    leftovers = remaining - sum(floors)
    order = sorted(range(len(raw)), key=lambda index: raw[index] - floors[index], reverse=True)
    for index in order[:leftovers]:
        counts[index] += 1
    return counts


def build_visual_slots(
    duration_seconds: float,
    beats: list[dict[str, Any]],
    *,
    target_seconds: float = 5,
    captions: list[dict[str, Any]] | None = None,
    protagonist_identity: str = "",
    technical_guardrails: list[str] | None = None,
) -> list[dict[str, Any]]:
    count = target_image_count(duration_seconds, len(beats), target_seconds)
    slots: list[dict[str, Any]] = []
    scene_number = 1
    motion_names = ("push-in", "drift-left", "pull-back", "drift-right", "drift-up")
    guardrails = technical_guardrails or list(TECHNICAL_GUARDRAILS)
    if captions:
        grouped_captions = _chunk_caption_segments(captions, count, duration_seconds)
        for group_index, group in enumerate(grouped_captions):
            beat_index = min(len(beats) - 1, math.floor(group_index * len(beats) / max(1, len(grouped_captions))))
            beat = beats[beat_index]
            base_prompt = _beat_prompt(beat, group_index)
            if protagonist_identity and "protagonist identity" not in base_prompt.lower():
                base_prompt = f"{base_prompt.rstrip(' .')}. Episode protagonist identity: {protagonist_identity}"
            camera = CAMERA_VARIATIONS[group_index % len(CAMERA_VARIATIONS)]
            slot_start = int(group["startMs"]) / 1000
            slot_end = int(group["endMs"]) / 1000
            fields = _beat_story_fields(beat)
            slots.append(
                {
                    "id": f"scene-{scene_number:03d}",
                    "beat_id": str(beat.get("id", f"beat-{beat_index + 1:03d}")),
                    "from": round(slot_start, 3),
                    "to": round(slot_end, 3),
                    "duration": round(slot_end - slot_start, 3),
                    "workflow": beat.get("workflow", "krea2_low_vram"),
                    "prompt": _append_guardrails(f"{base_prompt.rstrip(' .')}. {camera}", guardrails),
                    "story_event": fields["story_event"],
                    "fable_law": fields["fable_law"],
                    "art_style_logic": fields["art_style_logic"],
                    "wan_candidate": beat.get("wan_candidate") is True,
                    "fable_event_stage": str(beat.get("fable_event_stage", "")),
                    "script_excerpt": "".join(str(item["text"]) for item in group["items"]),
                    "caption_range": {
                        "start_index": group["start_index"],
                        "end_index": group["end_index"],
                        "startMs": int(group["startMs"]),
                        "endMs": int(group["endMs"]),
                    },
                    "motion": motion_names[(scene_number - 1) % len(motion_names)],
                    "output_name": f"scene-{scene_number:03d}.png",
                }
            )
            scene_number += 1
        return slots

    ranges = _beat_ranges(beats, duration_seconds)
    allocations = _allocate_counts(ranges, count)
    for beat, (start, end), allocation in zip(beats, ranges, allocations):
        step = (end - start) / allocation
        for within_beat in range(allocation):
            slot_start = start + within_beat * step
            slot_end = end if within_beat == allocation - 1 else start + (within_beat + 1) * step
            base_prompt = _beat_prompt(beat, within_beat)
            if protagonist_identity and "protagonist identity" not in base_prompt.lower():
                base_prompt = f"{base_prompt.rstrip(' .')}. Episode protagonist identity: {protagonist_identity}"
            camera = CAMERA_VARIATIONS[within_beat % len(CAMERA_VARIATIONS)]
            fields = _beat_story_fields(beat)
            slots.append(
                {
                    "id": f"scene-{scene_number:03d}",
                    "beat_id": str(beat.get("id", f"beat-{scene_number:03d}")),
                    "from": round(slot_start, 3),
                    "to": round(slot_end, 3),
                    "duration": round(slot_end - slot_start, 3),
                    "workflow": beat.get("workflow", "krea2_low_vram"),
                    "prompt": _append_guardrails(f"{base_prompt.rstrip(' .')}. {camera}", guardrails),
                    "story_event": fields["story_event"],
                    "fable_law": fields["fable_law"],
                    "art_style_logic": fields["art_style_logic"],
                    "wan_candidate": beat.get("wan_candidate") is True,
                    "fable_event_stage": str(beat.get("fable_event_stage", "")),
                    "script_excerpt": fields["story_event"],
                    "caption_range": None,
                    "motion": motion_names[(scene_number - 1) % len(motion_names)],
                    "output_name": f"scene-{scene_number:03d}.png",
                }
            )
            scene_number += 1
    return slots


def validate_episode(episode: dict[str, Any], series: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ("project_id", "title", "cover_title", "source_script_md", "protagonist", "semantic_beats", "cover_prompt")
    for key in required:
        if not episode.get(key):
            errors.append(f"missing:{key}")
    if not str(episode.get("project_id", "")).startswith("treeelf-fable-"):
        errors.append("project_id must start with treeelf-fable-")
    protagonist = str(episode.get("protagonist", {}).get("type", ""))
    allowed = set(series.get("character", {}).get("allowed_protagonists", []))
    forbidden = set(series.get("character", {}).get("forbidden_protagonists", []))
    if protagonist not in allowed:
        errors.append(f"unsupported protagonist type:{protagonist}")
    if protagonist in forbidden or protagonist in {"成年男性", "中年男人"}:
        errors.append(f"forbidden protagonist type:{protagonist}")
    beats = episode.get("semantic_beats", [])
    if not beats:
        errors.append("semantic_beats must not be empty")
    for beat in beats:
        if not beat.get("id"):
            errors.append("semantic beat missing id")
        if not beat.get("prompt") and not beat.get("prompt_variants"):
            errors.append(f"{beat.get('id', 'semantic beat')}: prompt or prompt_variants must not be empty")
        for field in ("story_event", "fable_law", "art_style_logic"):
            if not str(beat.get(field, "")).strip():
                errors.append(f"{beat.get('id', 'semantic beat')}: missing fable visual field:{field}")
    needs_references = any(beat.get("workflow") == "flux2_klein_4ref" for beat in beats)
    provided_references = episode.get("character_reference_paths", [])
    character_pack = episode.get("character_pack", {})
    generated_references = character_pack.get("reference_prompts", [])
    if needs_references and len(provided_references) != 4:
        if not character_pack.get("enabled") or len(generated_references) != 4:
            errors.append("flux2_klein_4ref requires four existing references or an enabled four-reference character_pack")
    hero = episode.get("hero_wan", {})
    if hero.get("enabled"):
        manual_scene_id = str(hero.get("scene_id", "")).strip()
        policy = str(
            hero.get("selection_policy")
            or ("manual_scene_id" if manual_scene_id else series.get("pacing", {}).get("wan_selection_policy", "manual_scene_id"))
        )
        if not hero.get("prompt"):
            errors.append("enabled hero_wan requires prompt")
        if policy in {"manual", "manual_scene_id"} and not hero.get("scene_id"):
            errors.append("manual hero_wan requires scene_id")
        if policy not in {"manual", "manual_scene_id", "opening_fable_event_only_or_none"}:
            errors.append(f"unsupported hero_wan selection_policy:{policy}")
        if float(series.get("pacing", {}).get("wan_duration_seconds", 5)) > float(series.get("pacing", {}).get("wan_max_generation_seconds", 5)):
            errors.append("pacing.wan_duration_seconds must be <= wan_max_generation_seconds")
    cover_terms = cover_human_prompt_terms(str(episode.get("cover_prompt", "")))
    if cover_terms:
        errors.append(
            "cover_prompt must be human-free symbolic/environment imagery; remove people/portrait terms: "
            + ", ".join(cover_terms)
        )
    source = Path(str(episode.get("source_script_md", ""))).expanduser()
    if episode.get("source_script_md") and not source.is_file():
        errors.append(f"source does not exist:{source}")
    return errors


def validate_batch(batch: dict[str, Any], batch_path: Path, series: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(batch.get("batch_id", "")).startswith("treeelf-fable-batch-"):
        errors.append("batch_id must start with treeelf-fable-batch-")
    paths = _resolve_episode_paths(batch_path, batch)
    maximum = int(series.get("gpu", {}).get("max_episodes_per_batch", 12))
    if not 1 <= len(paths) <= maximum:
        errors.append(f"episode_configs must contain between 1 and {maximum} episodes")
    if int(batch.get("queue_depth", 0)) != int(series.get("gpu", {}).get("queue_depth", 2)):
        errors.append("queue_depth must match the independent fable series profile")
    project_ids: list[str] = []
    source_paths: list[str] = []
    for path in paths:
        if not path.is_file():
            errors.append(f"missing episode config:{path}")
            continue
        episode = load_json(path)
        project_ids.append(str(episode.get("project_id", "")))
        source_paths.append(str(Path(str(episode.get("source_script_md", ""))).expanduser()))
        errors.extend(f"{path.name}:{error}" for error in validate_episode(episode, series))
    if len(project_ids) != len(set(project_ids)):
        errors.append("episode project_id values must be unique")
    if len(source_paths) != len(set(source_paths)):
        errors.append("episode source paths must be unique")
    return errors


def build_batch_readiness_report(
    batch: dict[str, Any],
    batch_path: Path,
    series: dict[str, Any],
    *,
    ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors = validate_batch(batch, batch_path, series)
    target_seconds = float(series.get("pacing", {}).get("target_seconds_per_image", 5))
    episodes: list[dict[str, Any]] = []
    totals = {
        "episodes": 0,
        "estimated_images": 0,
        "estimated_wan_jobs": 0,
        "episodes_requiring_character_review": 0,
        "episodes_with_manual_wan_override": 0,
    }
    blockers = list(errors)
    warnings: list[str] = []
    ledger_items = {row.get("source"): row for row in (ledger or {}).get("items", [])}
    for config_path in _resolve_episode_paths(batch_path, batch):
        if not config_path.is_file():
            continue
        episode = load_json(config_path)
        source = Path(str(episode.get("source_script_md", ""))).expanduser()
        source_name = source.name
        beats = episode.get("semantic_beats", [])
        needs_character_review = any(beat.get("workflow") == "flux2_klein_4ref" for beat in beats)
        estimated_duration = float(episode.get("estimated_duration_seconds") or 0)
        estimated_images = (
            target_image_count(estimated_duration, len(beats), target_seconds)
            if estimated_duration > 0 and beats
            else 0
        )
        hero = episode.get("hero_wan", {}) if isinstance(episode.get("hero_wan"), dict) else {}
        manual_wan_scene_id = str(hero.get("scene_id", "")).strip()
        has_explicit_wan_candidate = any(
            beat.get("wan_candidate") is True or str(beat.get("fable_event_stage", "")) == "first_manifestation"
            for beat in beats[:1]
        )
        expected_wan_jobs = 1 if hero.get("enabled") and (manual_wan_scene_id or has_explicit_wan_candidate) else 0
        missing_fields = [
            f"{beat.get('id', 'semantic beat')}:{field}"
            for beat in beats
            for field in ("story_event", "fable_law", "art_style_logic")
            if not str(beat.get(field, "")).strip()
        ]
        prompt_warnings = prompt_review_warnings(episode)
        ledger_item = ledger_items.get(source_name, {})
        ledger_status = str(ledger_item.get("status", "missing")) if ledger else "not_checked"
        if ledger and ledger_status not in {"pending", "planned", "failed"}:
            blockers.append(f"{source_name}: ledger status is not ready:{ledger_status}")
        if hero.get("enabled") and manual_wan_scene_id:
            warnings.append(f"{episode.get('project_id')}: manual Wan scene override:{manual_wan_scene_id}")
        if hero.get("enabled") and not manual_wan_scene_id and not has_explicit_wan_candidate:
            warnings.append(f"{episode.get('project_id')}: Wan enabled but no opening explicit candidate; expected no Wan job")
        totals["episodes"] += 1
        totals["estimated_images"] += estimated_images
        totals["estimated_wan_jobs"] += expected_wan_jobs
        totals["episodes_requiring_character_review"] += 1 if needs_character_review else 0
        totals["episodes_with_manual_wan_override"] += 1 if manual_wan_scene_id else 0
        episodes.append(
            {
                "project_id": episode.get("project_id", ""),
                "title": episode.get("title", ""),
                "source": str(source),
                "source_exists": source.is_file(),
                "ledger_status": ledger_status,
                "semantic_beat_count": len(beats),
                "fable_visual_fields_complete": not missing_fields,
                "missing_fable_visual_fields": missing_fields,
                "prompt_warning_count": len(prompt_warnings),
                "needs_character_review": needs_character_review,
                "estimated_duration_seconds": estimated_duration,
                "estimated_images": estimated_images,
                "hero_wan_enabled": bool(hero.get("enabled")),
                "manual_wan_scene_id": manual_wan_scene_id,
                "has_opening_wan_candidate": has_explicit_wan_candidate,
                "expected_wan_jobs": expected_wan_jobs,
                "ready": not missing_fields and not prompt_warnings and source.is_file() and ledger_status in {"pending", "planned", "failed", "not_checked"},
            }
        )
    return {
        "version": "1.0",
        "batch_id": batch.get("batch_id", ""),
        "series": series.get("series", "treeelf-fable"),
        "checked_at": utc_now(),
        "valid": not errors,
        "ready_for_prepare": not blockers,
        "errors": errors,
        "warnings": warnings,
        "blockers": blockers,
        "totals": totals,
        "episodes": episodes,
        "next_action": "fix blockers before prepare; review warnings before opening GPU",
    }


def transition_ledger_item(
    ledger: dict[str, Any],
    source_name: str,
    new_status: str,
    *,
    project_id: str | None = None,
    batch_id: str | None = None,
    output: str | None = None,
    cover: str | None = None,
) -> None:
    item = next((row for row in ledger.get("items", []) if row.get("source") == source_name), None)
    if item is None:
        raise KeyError(f"source is absent from fable ledger:{source_name}")
    current = str(item.get("status", "pending"))
    if current == new_status:
        if project_id:
            item["project_id"] = project_id
        if batch_id:
            item["batch_id"] = batch_id
        if output:
            item["output"] = output
        if cover:
            item["cover"] = cover
        return
    if new_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid fable status transition:{current}->{new_status}")
    item["status"] = new_status
    item["updated_at"] = utc_now()
    if project_id:
        item["project_id"] = project_id
    if batch_id:
        item["batch_id"] = batch_id
    if output:
        item["output"] = output
    if cover:
        item["cover"] = cover
    if new_status == "completed":
        item["completed"] = datetime.now().astimezone().date().isoformat()


def _narration_text(source: Path) -> str:
    text = source.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) == 3:
            text = parts[2]
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#")).strip()


def prepare_batch(
    batch: dict[str, Any],
    batch_path: Path,
    series: dict[str, Any],
    *,
    projects_root: Path = PROJECTS_ROOT,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    errors = validate_batch(batch, batch_path, series)
    if errors:
        raise ValueError("Invalid TreeElf fable batch:\n- " + "\n- ".join(errors))
    target = _batch_dir(batch, projects_root)
    for path in (target / "assets", target / "artifacts", target / "renders"):
        path.mkdir(parents=True, exist_ok=True)

    ledger_file = ledger_path or Path(series["status_ledger"])
    ledger = load_json(ledger_file)
    dump_json(
        target / "artifacts" / "batch_readiness_report.json",
        build_batch_readiness_report(batch, batch_path, series, ledger=ledger),
    )
    episodes: list[dict[str, Any]] = []
    narration_jobs: list[dict[str, Any]] = []
    character_jobs: list[dict[str, Any]] = []
    for config_path in _resolve_episode_paths(batch_path, batch):
        episode = load_json(config_path)
        source = Path(episode["source_script_md"]).expanduser().resolve()
        source_name = source.name
        ledger_item = next((row for row in ledger.get("items", []) if row.get("source") == source_name), None)
        if ledger_item is None:
            raise KeyError(f"source is absent from fable ledger:{source_name}")
        if ledger_item.get("status") == "completed":
            raise ValueError(f"source is already completed:{source_name}")
        if ledger_item.get("status") not in {"pending", "planned", "failed"}:
            raise ValueError(f"source is already reserved:{source_name}:{ledger_item.get('status')}")

        episode_target = _episode_dir(episode, projects_root)
        for path in (
            episode_target / "artifacts",
            episode_target / "assets" / "audio",
            episode_target / "assets" / "images" / "scenes",
            episode_target / "assets" / "images" / "cover",
            episode_target / "assets" / "video",
            episode_target / "renders",
        ):
            path.mkdir(parents=True, exist_ok=True)
        snapshot = episode_target / "artifacts" / "source_script.md"
        shutil.copy2(source, snapshot)
        dump_json(episode_target / "artifacts" / "episode_config.json", episode)
        narration_text = episode.get("narration_text") or _narration_text(source)
        dump_json(
            episode_target / "artifacts" / "visual_brief.json",
            build_visual_brief(episode, series, str(narration_text)),
        )
        dump_json(
            episode_target / "artifacts" / "prompt_review_warnings.json",
            {
                "version": "1.0",
                "project_id": episode["project_id"],
                "warnings": prompt_review_warnings(episode),
                "technical_guardrails": _prompt_guardrails(series),
                "checked_at": utc_now(),
            },
        )
        warnings = prompt_review_warnings(episode)
        if warnings and _strict_gate(series, "strict_aesthetic_prompt_review", True):
            raise ValueError(
                f"{episode['project_id']} creative prompts contain aesthetic negatives; "
                "rewrite them as positive visual targets before prepare:\n"
                + "\n".join(f"- {row['field']}: {row['pattern']}" for row in warnings)
            )
        dump_json(episode_target / "artifacts" / "voice_instruction_report.json", voice_instruction_report(series))
        dump_json(
            episode_target / "project.json",
            {
                "version": "1.0",
                "project_id": episode["project_id"],
                "title": episode["title"],
                "pipeline": "cinematic",
                "series": "treeelf-fable",
                "render_runtime": "remotion",
                "composition_mode": "templated",
                "status": "gpu_queued",
                "source_path": str(source),
                "source_sha256": sha256_file(source),
                "prepared_at": utc_now(),
            },
        )
        transition_ledger_item(ledger, source_name, "planned", project_id=episode["project_id"], batch_id=batch["batch_id"])
        transition_ledger_item(ledger, source_name, "gpu_queued", project_id=episode["project_id"], batch_id=batch["batch_id"])
        narration_job = {
            "job_id": f"{episode['project_id']}:narration",
            "project_id": episode["project_id"],
            "tool": "comfyui_tts",
            "workflow_template": series["voice"]["workflow_template"],
            "voice_instruction": voice_instruction_report(series),
            "inputs": _tts_inputs(series, str(narration_text), episode_target / "assets" / "audio" / "narration.mp3"),
            "status": "queued",
        }
        narration_jobs.append(narration_job)
        character_pack = episode.get("character_pack", {})
        if character_pack.get("enabled"):
            character_root = episode_target / "assets" / "images" / "character"
            character_root.mkdir(parents=True, exist_ok=True)
            character_prompts = [
                ("master", character_pack["master_prompt"]),
                *[
                    (f"ref-{index:02d}", prompt)
                    for index, prompt in enumerate(character_pack.get("reference_prompts", []), start=1)
                ],
            ]
            for name, prompt in character_prompts:
                character_jobs.append(
                    {
                        "job_id": f"{episode['project_id']}:character-{name}",
                        "project_id": episode["project_id"],
                        "tool": "comfyui_image",
                        "workflow_template": series["gpu"]["ordinary_image_workflow"],
                        "inputs": {
                            "prompt": _append_guardrails(str(prompt), _prompt_guardrails(series)),
                            "aspect_preset": "portrait_9_16",
                            "output_path": str(character_root / f"{name}.png"),
                        },
                        "status": "queued",
                    }
                )
        episodes.append(
            {
                "project_id": episode["project_id"],
                "source": source_name,
                "source_sha256": sha256_file(source),
                "config_path": str(config_path),
                "status": "gpu_queued",
                "estimated_duration_seconds": episode.get("estimated_duration_seconds"),
            }
        )

    dump_json(ledger_file, ledger)
    manifest = {
        "version": "1.0",
        "workflow": "treeelf_fable_independent_batch",
        "batch_id": batch["batch_id"],
        "status": "gpu_queued",
        "queue_depth": batch["queue_depth"],
        "exclusive_remote_runtime": True,
        "asset_scope": "all_assets_generated_in_current_batch",
        "created_at": utc_now(),
        "episodes": episodes,
        "gpu_groups": [
            {"id": "narration", "workflow": series["voice"]["workflow_template"], "jobs": narration_jobs},
            {"id": "character_pack", "workflow": series["gpu"]["ordinary_image_workflow"], "jobs": character_jobs},
            {"id": "scene_images_krea", "workflow": series["gpu"]["ordinary_image_workflow"], "jobs": []},
            {"id": "scene_images_flux", "workflow": series["gpu"]["character_consistency_workflow"], "jobs": []},
            {"id": "covers", "workflow": series["gpu"]["cover_workflow"], "jobs": []},
            {"id": "wan", "workflow": series["gpu"]["wan_workflow"], "jobs": []},
        ],
        "next_action": "generate narration group, then run refresh-visuals before image groups",
    }
    manifest_path = target / "artifacts" / "gpu_batch_manifest.json"
    dump_json(manifest_path, manifest)
    dump_json(
        target / "artifacts" / "retention_policy.json",
        {
            "project_id": batch["batch_id"],
            "decision": "current_fable_batch_only",
            "retain_infrastructure": [
                "/root/ComfyUI-Easy-Install/ComfyUI",
                "/root/autodl-tmp/comfyui-models",
                "/root/autodl-tmp/comfyui-runtime/validation",
            ],
            "retain_project_assets": [],
            "backup_then_delete_runtime_types": ["input", "output", "temp"],
            "backup_then_delete_voice_files": [],
            "cleanup_scope": "only files added after this batch's empty-queue remote baseline",
            "concurrency_rule": "no other project may use this ComfyUI runtime until batch finalization",
            "download_scope": "all assets generated in this batch, including candidates and repairs",
            "delete_gate": "Mac backup exists and local/remote size and SHA-256 match",
            "shutdown_gate": "queue empty, all expected local assets verified, cleanup verified, no pending repairs",
        },
    )
    return {"batch_dir": str(target), "manifest": str(manifest_path), "episodes": len(episodes)}


def capture_gpu_baseline(
    batch: dict[str, Any],
    *,
    projects_root: Path = PROJECTS_ROOT,
    ssh_host: str = "autodl-comfyui",
) -> dict[str, Any]:
    """Freeze pre-batch runtime files so only this batch is later collected."""

    target = _batch_dir(batch, projects_root)
    manifest_path = target / "artifacts" / "gpu_batch_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("run prepare before capture-gpu-baseline")
    manifest = load_json(manifest_path)
    if manifest.get("status") not in {"gpu_queued", "baseline_captured"}:
        raise ValueError("GPU baseline must be captured before generation starts")
    _require_empty_queue(ssh_host)
    rows = remote_runtime_manifest(ssh_host)
    policy_path = target / "artifacts" / "retention_policy.json"
    policy = load_json(policy_path)
    policy["retain_project_assets"] = [row["path"] for row in rows]
    policy["runtime_baseline_captured_at"] = utc_now()
    policy["runtime_baseline_file_count"] = len(rows)
    dump_json(policy_path, policy)
    baseline_path = target / "artifacts" / "remote_runtime_baseline.json"
    dump_json(
        baseline_path,
        {
            "version": "1.0",
            "batch_id": batch["batch_id"],
            "ssh_host": ssh_host,
            "captured_at": utc_now(),
            "files": rows,
        },
    )
    manifest["status"] = "baseline_captured"
    manifest["gpu_window_started_at"] = utc_now()
    manifest["remote_baseline"] = str(baseline_path)
    manifest["next_action"] = "generate narration group only; no other project may use the runtime"
    dump_json(manifest_path, manifest)
    return {"baseline": str(baseline_path), "retained_preexisting_files": len(rows)}


def refresh_visuals(
    batch: dict[str, Any],
    batch_path: Path,
    series: dict[str, Any],
    *,
    projects_root: Path = PROJECTS_ROOT,
) -> dict[str, Any]:
    target = _batch_dir(batch, projects_root)
    manifest_path = target / "artifacts" / "gpu_batch_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("run prepare before refresh-visuals")
    manifest = load_json(manifest_path)
    if manifest.get("status") not in {"baseline_captured", "visual_jobs_queued"}:
        raise ValueError("capture-gpu-baseline must run before narration or visual generation")
    scene_jobs_krea: list[dict[str, Any]] = []
    scene_jobs_flux: list[dict[str, Any]] = []
    cover_jobs: list[dict[str, Any]] = []
    wan_jobs: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    target_seconds = float(series["pacing"]["target_seconds_per_image"])
    for config_path in _resolve_episode_paths(batch_path, batch):
        episode = load_json(config_path)
        episode_target = _episode_dir(episode, projects_root)
        narration = episode_target / "assets" / "audio" / "narration.mp3"
        if not narration.is_file():
            raise FileNotFoundError(f"narration is missing:{narration}")
        duration = media_duration_seconds(narration)
        narration_text = str(episode.get("narration_text") or _narration_text(Path(episode["source_script_md"]).expanduser()))
        captions_path = episode_target / "artifacts" / "captions.json"
        captions = _load_captions(captions_path) if captions_path.is_file() else build_fable_captions(narration_text, duration)
        captions_calibrated = _caption_source_is_calibrated(captions_path)
        if not captions_path.is_file():
            dump_json(
                captions_path,
                {
                    "version": "1.0",
                    "source": "proportional timing from approved narration text and Qwen narration duration; replace with Whisper-corrected timings when available",
                    "whisper_corrected": False,
                    "duration_seconds": round(duration, 3),
                    "captions": captions,
                },
            )
        references = [str(Path(value).expanduser()) for value in episode.get("character_reference_paths", [])]
        if len(references) != 4 and episode.get("character_pack", {}).get("enabled"):
            character_root = episode_target / "assets" / "images" / "character"
            references = [str(character_root / f"ref-{index:02d}.png") for index in range(1, 5)]
        needs_references = any(beat.get("workflow") == "flux2_klein_4ref" for beat in episode["semantic_beats"])
        character_gate = {
            "version": "1.0",
            "project_id": episode["project_id"],
            "requires_references": needs_references,
            "reference_image_paths": references,
            "reference_images_exist": [Path(value).is_file() and Path(value).stat().st_size > 0 for value in references],
            "protagonist_identity": episode.get("protagonist", {}).get("description", ""),
            "contact_sheet": "",
            "review_required": bool(needs_references and _strict_gate(series, "require_character_review", True)),
            "review_approved": False,
            "checked_at": utc_now(),
        }
        if needs_references and len(references) == 4 and all(character_gate["reference_images_exist"]):
            sheet_path = episode_target / "artifacts" / "character_contact_sheet.png"
            character_gate["contact_sheet"] = build_character_contact_sheet(
                references,
                sheet_path,
                title=f"{episode['title']} / {episode['project_id']}",
            )
            review_path = episode_target / "artifacts" / "character_review.json"
            if not review_path.is_file():
                dump_json(review_path, default_character_review(episode, references, sheet_path))
            elif _strict_gate(series, "require_character_review", True):
                require_character_review(episode, episode_target)
                character_gate["review_approved"] = True
        dump_json(episode_target / "artifacts" / "character_gate_report.json", character_gate)
        if needs_references and (len(references) != 4 or not all(character_gate["reference_images_exist"])):
            raise FileNotFoundError(f"{episode['project_id']} character reference gate failed; generate/review four references before scene images")
        if needs_references and _strict_gate(series, "require_character_review", True) and not character_gate["review_approved"]:
            raise PermissionError(f"{episode['project_id']} character contact sheet created; approve character_review.json before scene images")
        slots = build_visual_slots(
            duration,
            episode["semantic_beats"],
            target_seconds=target_seconds,
            captions=captions,
            protagonist_identity=str(episode.get("protagonist", {}).get("description", "")),
            technical_guardrails=_prompt_guardrails(series),
        )
        for slot in slots:
            output = episode_target / "assets" / "images" / "scenes" / slot["output_name"]
            inputs: dict[str, Any] = {
                "prompt": slot["prompt"],
                "aspect_preset": "portrait_9_16",
                "output_path": str(output),
            }
            if slot["workflow"] == "flux2_klein_4ref":
                if len(references) != 4:
                    raise ValueError(f"{episode['project_id']} requires exactly four character references")
                inputs["reference_image_paths"] = references
            job = {
                "job_id": f"{episode['project_id']}:{slot['id']}",
                "project_id": episode["project_id"],
                "tool": "comfyui_image",
                "workflow_template": slot["workflow"],
                "inputs": inputs,
                "status": "queued",
            }
            if slot["workflow"] == "flux2_klein_4ref":
                job["depends_on_group"] = "character_pack"
                scene_jobs_flux.append(job)
            else:
                scene_jobs_krea.append(job)
        cover_jobs.append(
            {
                "job_id": f"{episode['project_id']}:cover",
                "project_id": episode["project_id"],
                "tool": "comfyui_image",
                "workflow_template": series["gpu"]["cover_workflow"],
                "inputs": {
                    "prompt": _append_guardrails(
                        f"{episode['cover_prompt'].rstrip(' .')}. symbolic object/environment-only cover background, generous title-safe negative space, refined material composition aligned with the philosophy cover visual system",
                        _prompt_guardrails(series),
                    ),
                    "aspect_preset": "portrait_9_16",
                    "output_path": str(episode_target / "assets" / "images" / "cover" / "cover-background.png"),
                },
                "status": "queued",
            }
        )
        hero = episode.get("hero_wan", {})
        selected_wan_slot = select_fable_wan_slot(slots, hero, series)
        if hero.get("enabled") and selected_wan_slot is not None:
            matching = selected_wan_slot
            reference = episode_target / "assets" / "images" / "scenes" / matching["output_name"]
            wan_duration = min(
                float(series["pacing"].get("wan_duration_seconds", 5)),
                float(series["pacing"].get("wan_max_generation_seconds", series["pacing"].get("wan_duration_seconds", 5))),
            )
            wan_jobs.append(
                {
                    "job_id": f"{episode['project_id']}:wan-hero",
                    "project_id": episode["project_id"],
                    "tool": "comfyui_video",
                    "workflow_template": series["gpu"]["wan_workflow"],
                    "depends_on": f"{episode['project_id']}:{matching['id']}",
                    "inputs": {
                        "prompt": hero["prompt"],
                        "reference_image_path": str(reference),
                        "duration_seconds": wan_duration,
                        "aspect_preset": "portrait_9_16",
                        "output_path": str(episode_target / "assets" / "video" / "wan-hero.mp4"),
                    },
                    "selection": {
                        "scene_id": matching["id"],
                        "selection_policy": hero.get("selection_policy") or series["pacing"].get("wan_selection_policy", "manual_scene_id"),
                        "selection_reason": matching.get("wan_selection_reason", "manual_scene_id"),
                        "script_excerpt": matching.get("script_excerpt", ""),
                        "scene_duration_seconds": round(float(matching["to"]) - float(matching["from"]), 3),
                        "generation_duration_seconds": wan_duration,
                    },
                    "status": "queued",
                }
            )
        visual_plan = {
            "version": "1.0",
            "project_id": episode["project_id"],
            "duration_source": str(narration),
            "duration_seconds": round(duration, 3),
            "target_seconds_per_image": target_seconds,
            "image_count": len(slots),
            "wan_count": 1 if selected_wan_slot else 0,
            "timing_policy": "scene ranges are derived from caption/script timing, not only beat weights",
            "captions_path": str(captions_path),
            "captions_calibrated": captions_calibrated,
            "wan_selection": {
                "enabled": bool(hero.get("enabled")),
                "selected": bool(selected_wan_slot),
                "scene_id": selected_wan_slot["id"] if selected_wan_slot else "",
                "selection_policy": hero.get("selection_policy") or series["pacing"].get("wan_selection_policy", "manual_scene_id"),
                "selection_reason": selected_wan_slot.get("wan_selection_reason", "manual_scene_id") if selected_wan_slot else "",
                "beat_id": selected_wan_slot.get("beat_id", "") if selected_wan_slot else "",
                "story_event": selected_wan_slot.get("story_event", "") if selected_wan_slot else "",
                "fable_law": selected_wan_slot.get("fable_law", "") if selected_wan_slot else "",
                "script_excerpt": selected_wan_slot.get("script_excerpt", "") if selected_wan_slot else "",
                "scene_duration_seconds": round(float(selected_wan_slot["to"]) - float(selected_wan_slot["from"]), 3) if selected_wan_slot else 0,
                "generation_duration_seconds": min(
                    float(series["pacing"].get("wan_duration_seconds", 5)),
                    float(series["pacing"].get("wan_max_generation_seconds", series["pacing"].get("wan_duration_seconds", 5))),
                ) if selected_wan_slot else 0,
            },
            "slots": slots,
        }
        dump_json(episode_target / "artifacts" / "visual_plan.json", visual_plan)
        summary.append({"project_id": episode["project_id"], "duration_seconds": round(duration, 3), "images": len(slots), "wan": visual_plan["wan_count"]})

    groups = {group["id"]: group for group in manifest["gpu_groups"]}
    groups["scene_images_krea"]["jobs"] = scene_jobs_krea
    groups["scene_images_flux"]["jobs"] = scene_jobs_flux
    groups["covers"]["jobs"] = cover_jobs
    groups["wan"]["jobs"] = wan_jobs
    manifest["status"] = "visual_jobs_queued"
    manifest["narration_group_completed_at"] = utc_now()
    manifest["visual_plan_refreshed_at"] = utc_now()
    manifest["next_action"] = "generate scene_images, covers, and wan groups; add every repair job to this manifest"
    dump_json(manifest_path, manifest)
    return {
        "batch_id": batch["batch_id"],
        "episodes": summary,
        "scene_jobs": len(scene_jobs_krea) + len(scene_jobs_flux),
        "scene_jobs_krea": len(scene_jobs_krea),
        "scene_jobs_flux": len(scene_jobs_flux),
        "cover_jobs": len(cover_jobs),
        "wan_jobs": len(wan_jobs),
    }


def _all_jobs(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [job for group in manifest.get("gpu_groups", []) for job in group.get("jobs", [])]


def verify_gpu_assets(
    batch: dict[str, Any],
    series: dict[str, Any],
    *,
    projects_root: Path = PROJECTS_ROOT,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    target = _batch_dir(batch, projects_root)
    manifest_path = target / "artifacts" / "gpu_batch_manifest.json"
    manifest = load_json(manifest_path)
    rows_by_path: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for job in _all_jobs(manifest):
        output = Path(job["inputs"]["output_path"])
        if not output.is_file() or output.stat().st_size <= 0:
            missing.append(str(output))
            continue
        rows_by_path[str(output)] = {
            "job_id": job["job_id"],
            "path": str(output),
            "size": output.stat().st_size,
            "sha256": sha256_file(output),
        }
    if missing:
        raise FileNotFoundError("GPU asset inventory is incomplete:\n" + "\n".join(missing))
    # Candidates, repair outputs, contact sheets, and provider provenance may
    # be appended during review. Include every file under this batch's episode
    # asset roots even if it was not part of the initial job plan.
    for episode in manifest.get("episodes", []):
        asset_root = projects_root / episode["project_id"] / "assets"
        for output in asset_root.rglob("*"):
            if not output.is_file() or output.stat().st_size <= 0:
                continue
            key = str(output)
            rows_by_path.setdefault(
                key,
                {
                    "job_id": "discovered-current-batch-asset",
                    "path": key,
                    "size": output.stat().st_size,
                    "sha256": sha256_file(output),
                },
            )
    rows = sorted(rows_by_path.values(), key=lambda row: row["path"])
    inventory = {
        "version": "1.0",
        "batch_id": batch["batch_id"],
        "scope": "all jobs recorded for the current batch, including appended candidates and repairs",
        "verified_at": utc_now(),
        "assets": rows,
    }
    inventory_path = target / "artifacts" / "gpu_asset_inventory.json"
    dump_json(inventory_path, inventory)
    manifest["status"] = "gpu_assets_complete"
    manifest["gpu_assets_verified_at"] = utc_now()
    manifest["gpu_generation_completed_at"] = manifest["gpu_assets_verified_at"]
    manifest["next_action"] = "review finalize-gpu dry-run, then finalize with --yes --shutdown"
    for episode in manifest["episodes"]:
        episode["status"] = "gpu_assets_complete"
    dump_json(manifest_path, manifest)

    ledger_file = ledger_path or Path(series["status_ledger"])
    ledger = load_json(ledger_file)
    for episode in manifest["episodes"]:
        transition_ledger_item(ledger, episode["source"], "gpu_assets_complete", project_id=episode["project_id"], batch_id=batch["batch_id"])
    dump_json(ledger_file, ledger)
    return {"inventory": str(inventory_path), "assets": len(rows), "bytes": sum(row["size"] for row in rows)}


def _load_captions(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    payload = load_json(path)
    values = payload.get("captions", payload.get("segments", []))
    rows: list[dict[str, Any]] = []
    for item in values:
        if "startMs" in item:
            rows.append({"text": item["text"], "startMs": int(item["startMs"]), "endMs": int(item["endMs"])})
        else:
            rows.append({"text": item["text"], "startMs": round(float(item["start"]) * 1000), "endMs": round(float(item["end"]) * 1000)})
    return rows


def stage_local_episode(
    episode: dict[str, Any],
    series: dict[str, Any],
    *,
    projects_root: Path = PROJECTS_ROOT,
    used_music_paths: list[str] | None = None,
) -> dict[str, Any]:
    target = _episode_dir(episode, projects_root)
    plan = load_json(target / "artifacts" / "visual_plan.json")
    captions_path_value = episode.get("captions_path")
    captions_path = Path(captions_path_value).expanduser() if captions_path_value else target / "artifacts" / "captions.json"
    if _strict_gate(series, "require_calibrated_captions_for_stage", True) and not _caption_source_is_calibrated(captions_path):
        raise PermissionError(f"{episode['project_id']} needs Whisper/manually calibrated captions before Remotion staging:{captions_path}")
    captions = _load_captions(captions_path)
    if captions:
        original_plan = json.loads(json.dumps(plan))
        plan = sync_visual_plan_to_captions(plan, captions)
        dump_json(target / "artifacts" / "visual_plan.json", plan)
        dump_json(target / "artifacts" / "wan_retarget_report.json", build_wan_retarget_report(original_plan, plan))
    if _strict_gate(series, "require_visual_qc_for_stage", True):
        require_visual_qc(episode, target, plan)

    cover_background = target / "assets" / "images" / "cover" / "cover-background.png"
    if not cover_background.is_file() or cover_background.stat().st_size <= 0:
        raise FileNotFoundError(f"cover background missing before Remotion cover render:{cover_background}")

    public_root = REMOTION_ROOT / "public" / "treeelf-fable" / episode["project_id"]
    if public_root.exists():
        shutil.rmtree(public_root)
    public_root.mkdir(parents=True)
    for source in (target / "assets").rglob("*"):
        if source.is_file():
            destination = public_root / source.relative_to(target / "assets")
            _atomic_link_or_copy(source, destination)

    hero = episode.get("hero_wan", {})
    wan_selection = plan.get("wan_selection", {}) if isinstance(plan.get("wan_selection"), dict) else {}
    wan_scene_id = str(wan_selection.get("scene_id") or hero.get("scene_id", ""))
    scenes: list[dict[str, Any]] = []
    for slot in plan["slots"]:
        use_wan = bool(hero.get("enabled") and wan_scene_id == slot["id"])
        scene_duration = max(0.12, float(slot["to"]) - float(slot["from"]))
        generated_wan_duration = float(wan_selection.get("generation_duration_seconds") or series["pacing"].get("wan_duration_seconds", 5))
        scenes.append(
            {
                "id": slot["id"],
                "kind": "video" if use_wan else "still",
                "src": "video/wan-hero.mp4" if use_wan else f"images/scenes/{slot['output_name']}",
                "from": slot["from"],
                "to": slot["to"],
                "motion": slot["motion"],
                "playbackRate": round(max(0.5, min(1.0, generated_wan_duration / scene_duration)), 2) if use_wan else None,
                "scriptExcerpt": slot.get("script_excerpt", ""),
                "captionRange": slot.get("caption_range"),
                "storyEvent": slot.get("story_event", ""),
                "wanSelectionReason": wan_selection.get("selection_reason") if use_wan else None,
            }
        )
        scenes[-1] = {key: value for key, value in scenes[-1].items() if value is not None}
        media_path = target / "assets" / scenes[-1]["src"]
        if not media_path.is_file() or media_path.stat().st_size <= 0:
            raise FileNotFoundError(f"scene media missing or rejected before Remotion staging:{media_path}")
    music_runtime = series.get("music", {})
    usage_ledger_path = (
        PROJECTS_ROOT / ".treeelf-music-usage-ledger.json"
        if projects_root.resolve() != PROJECTS_ROOT.resolve()
        else Path(str(music_runtime.get("usage_ledger_path", DEFAULT_USAGE_LEDGER_PATH))).expanduser()
    )
    music_selection = select_music_source(
        episode, series, used_music_paths=used_music_paths, usage_ledger_path=usage_ledger_path
    )
    music_source = Path(str(music_selection.get("path", ""))).expanduser()
    if not music_source.is_file():
        raise FileNotFoundError(f"fable requires background music; no usable music source found for {episode['project_id']}")
    music_target = target / "assets" / "music" / "background.mp3"
    normalize_cfg = music_runtime.get("normalization", {})
    normalization = normalize_background_music(
        music_source,
        music_target,
        target_lufs=float(normalize_cfg.get("target_lufs", -18.0)),
        true_peak_dbfs=float(normalize_cfg.get("true_peak_dbfs", -2.0)),
        loudness_range_lu=float(normalize_cfg.get("loudness_range_lu", 7.0)),
    )
    public_music = public_root / "music" / "background.mp3"
    _atomic_link_or_copy(music_target, public_music)
    usage = record_music_usage(
        music_selection,
        project_id=episode["project_id"],
        series="treeelf-fable",
        ledger_path=usage_ledger_path,
    )
    dump_json(
        target / "artifacts" / "music_selection.json",
        {
            "version": "2.0",
            "project_id": episode["project_id"],
            "selected": music_selection,
            "normalization": normalization,
            "usage_record": usage,
            "selected_at": utc_now(),
        },
    )
    audio_qc = build_audio_mix_qc(
        target / "assets" / "audio" / "narration.mp3",
        music_target,
        float(series["music"]["remotion_volume"]),
    )
    dump_json(target / "artifacts" / "audio_mix_qc.json", audio_qc)
    if _strict_gate(series, "require_audio_loudness_qc", True) and audio_qc.get("approved_for_render") is not True:
        raise ValueError(f"{episode['project_id']} audio mix QC failed before Remotion staging")

    props = {
        "assetRoot": f"treeelf-fable/{episode['project_id']}",
        "title": episode["title"],
        "totalSeconds": plan["duration_seconds"],
        "coverSrc": "images/cover/cover-final.png",
        "scenes": scenes,
        "captions": captions,
        "narrationSrc": "audio/narration.mp3",
        "musicSrc": "music/background.mp3",
        "musicVolume": series["music"]["remotion_volume"],
        "brand": "树精灵",
        "transitionFrames": 10,
        "timelinePolicy": plan.get("timing_policy", ""),
        "wanPolicy": wan_selection,
        "captionStyle": {
            "fontSize": series["captions"]["font_size"],
            "color": series["captions"]["color"],
            "outlineColor": series["captions"]["outline_color"],
            "outlineWidth": series["captions"]["outline_width"],
            "safeBottom": series["captions"]["safe_bottom"],
        },
    }
    props_path = target / "artifacts" / "remotion_props.json"
    dump_json(props_path, props)
    cover_props_path = target / "artifacts" / "cover_props.json"
    dump_json(
        cover_props_path,
        {
            "backgroundSrc": f"treeelf-fable/{episode['project_id']}/images/cover/cover-background.png",
            "chineseTitle": episode["cover_title"],
            "englishTitle": episode.get("cover_english_title", ""),
            "brand": "树精灵",
            "titlePosition": episode.get("cover_title_position", "center"),
            "textAlign": episode.get("cover_text_align", "center"),
            "textColor": "#F7F2E8",
            "accentColor": "#D9B56D",
            "overlayOpacity": 0.34,
            "gradientDirection": episode.get("cover_gradient_direction", "center"),
        },
    )
    return {
        "project_id": episode["project_id"],
        "public_dir": str(public_root),
        "props": str(props_path),
        "cover_props": str(cover_props_path),
        "music_path": str(music_source),
    }


def stage_local_batch(
    batch: dict[str, Any],
    batch_path: Path,
    series: dict[str, Any],
    *,
    projects_root: Path = PROJECTS_ROOT,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    target = _batch_dir(batch, projects_root)
    manifest_path = target / "artifacts" / "gpu_batch_manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") not in {"gpu_assets_complete", "gpu_finalized", "local_packaging"}:
        raise ValueError("GPU assets must be complete before local staging")
    results = []
    used_music_paths: list[str] = []
    for path in _resolve_episode_paths(batch_path, batch):
        staged = stage_local_episode(
            load_json(path),
            series,
            projects_root=projects_root,
            used_music_paths=used_music_paths,
        )
        if staged.get("music_path"):
            used_music_paths.append(str(staged["music_path"]))
        results.append(staged)
    manifest["status"] = "local_packaging"
    manifest["local_staged_at"] = utc_now()
    manifest.setdefault("local_packaging_started_at", manifest["local_staged_at"])
    for episode in manifest["episodes"]:
        episode["status"] = "local_packaging"
    dump_json(manifest_path, manifest)
    ledger_file = ledger_path or Path(series["status_ledger"])
    ledger = load_json(ledger_file)
    for episode in manifest["episodes"]:
        current = next(row for row in ledger["items"] if row["source"] == episode["source"])["status"]
        if current == "gpu_assets_complete":
            transition_ledger_item(ledger, episode["source"], "local_packaging")
    dump_json(ledger_file, ledger)
    return {"batch_id": batch["batch_id"], "episodes": results}


def create_qc_templates(
    batch: dict[str, Any],
    batch_path: Path,
    *,
    projects_root: Path = PROJECTS_ROOT,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for config_path in _resolve_episode_paths(batch_path, batch):
        episode = load_json(config_path)
        target = _episode_dir(episode, projects_root)
        plan_path = target / "artifacts" / "visual_plan.json"
        if not plan_path.is_file():
            raise FileNotFoundError(f"refresh-visuals must create visual_plan before QC template:{episode['project_id']}")
        plan = load_json(plan_path)
        visual_qc_path = target / "artifacts" / "visual_qc.json"
        if not visual_qc_path.is_file():
            dump_json(visual_qc_path, default_visual_qc(episode, plan, target))

        references = [str(Path(value).expanduser()) for value in episode.get("character_reference_paths", [])]
        if len(references) != 4 and episode.get("character_pack", {}).get("enabled"):
            character_root = target / "assets" / "images" / "character"
            references = [str(character_root / f"ref-{index:02d}.png") for index in range(1, 5)]
        contact_sheet_path = target / "artifacts" / "character_contact_sheet.png"
        character_review_path = target / "artifacts" / "character_review.json"
        if len(references) == 4 and all(Path(value).is_file() and Path(value).stat().st_size > 0 for value in references):
            if not contact_sheet_path.is_file():
                build_character_contact_sheet(references, contact_sheet_path, title=f"{episode['title']} / {episode['project_id']}")
            if not character_review_path.is_file():
                dump_json(character_review_path, default_character_review(episode, references, contact_sheet_path))
        results.append(
            {
                "project_id": episode["project_id"],
                "visual_qc": str(visual_qc_path),
                "character_review": str(character_review_path) if character_review_path.is_file() else None,
                "contact_sheet": str(contact_sheet_path) if contact_sheet_path.is_file() else None,
            }
        )
    return {"batch_id": batch["batch_id"], "episodes": results}


def render_local(
    batch: dict[str, Any],
    batch_path: Path,
    *,
    projects_root: Path = PROJECTS_ROOT,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for config_path in _resolve_episode_paths(batch_path, batch):
        episode = load_json(config_path)
        target = _episode_dir(episode, projects_root)
        props = target / "artifacts" / "remotion_props.json"
        if not props.is_file():
            raise FileNotFoundError(f"run stage-local before render-local:{episode['project_id']}")
        cover_output = target / "assets" / "images" / "cover" / "cover-final.png"
        cover_command = [
            "npx",
            "remotion",
            "still",
            "src/index.tsx",
            "TreeElfCover",
            str(cover_output),
            "--props",
            str(target / "artifacts" / "cover_props.json"),
        ]
        subprocess.run(cover_command, cwd=REMOTION_ROOT, check=True)
        public_cover = REMOTION_ROOT / "public" / "treeelf-fable" / episode["project_id"] / "images" / "cover" / "cover-final.png"
        _atomic_link_or_copy(cover_output, public_cover)
        output = target / "renders" / "final.mp4"
        command = [
            "npx",
            "remotion",
            "render",
            "src/index.tsx",
            "TreeElfFableEpisode",
            str(output),
            "--props",
            str(props),
        ]
        subprocess.run(command, cwd=REMOTION_ROOT, check=True)
        results.append(
            {
                "project_id": episode["project_id"],
                "output": str(output),
                "size": output.stat().st_size,
                "sha256": sha256_file(output),
                "cover": str(cover_output),
                "cover_sha256": sha256_file(cover_output),
            }
        )
    return {"batch_id": batch["batch_id"], "renders": results}


def complete_local_batch(
    batch: dict[str, Any],
    batch_path: Path,
    series: dict[str, Any],
    *,
    projects_root: Path = PROJECTS_ROOT,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    target = _batch_dir(batch, projects_root)
    manifest_path = target / "artifacts" / "gpu_batch_manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") not in {"local_packaging", "completed"}:
        raise ValueError("batch must be local_packaging before completion")
    delivery_root = Path(series["delivery_dir"]).expanduser()
    delivery_root.mkdir(parents=True, exist_ok=True)
    ledger_file = ledger_path or Path(series["status_ledger"])
    ledger = load_json(ledger_file)
    delivered: list[dict[str, Any]] = []
    for config_path in _resolve_episode_paths(batch_path, batch):
        episode = load_json(config_path)
        episode_target = _episode_dir(episode, projects_root)
        final_video = episode_target / "renders" / "final.mp4"
        final_cover = episode_target / "assets" / "images" / "cover" / "cover-final.png"
        if not final_video.is_file() or final_video.stat().st_size <= 0:
            raise FileNotFoundError(f"final render is missing:{final_video}")
        if media_duration_seconds(final_video) <= 0:
            raise ValueError(f"final render is not decodable:{final_video}")
        video_destination = _delivery_video_path(episode, delivery_root)
        delivery_mode = _atomic_link_or_copy(final_video, video_destination)
        if sha256_file(final_video) != sha256_file(video_destination):
            raise ValueError(f"Movies delivery SHA-256 mismatch:{video_destination}")
        cover_asset = str(final_cover) if final_cover.is_file() else None
        source_name = Path(episode["source_script_md"]).name
        transition_ledger_item(
            ledger,
            source_name,
            "completed",
            project_id=episode["project_id"],
            batch_id=batch["batch_id"],
            output=str(video_destination),
            cover=cover_asset,
        )
        delivery_report = {
            "version": "1.0",
            "project_id": episode["project_id"],
            "output": str(video_destination),
            "sha256": sha256_file(video_destination),
            "delivery_mode": delivery_mode,
            "delivery_policy": "Movies contains the final mp4 only; cover remains in the project asset library.",
            "cover_asset": cover_asset,
            "movies_contains_cover": False,
            "completed_at": utc_now(),
        }
        dump_json(episode_target / "artifacts" / "delivery_report.json", delivery_report)
        project_path = episode_target / "project.json"
        project = load_json(project_path)
        project["status"] = "completed"
        project["completed_at"] = delivery_report["completed_at"]
        project["delivery"] = str(video_destination)
        project["cover_asset"] = cover_asset
        dump_json(project_path, project)
        delivered.append(
            {
                "project_id": episode["project_id"],
                "video": str(video_destination),
                "cover_asset": cover_asset,
                "movies_contains_cover": False,
                "sha256": delivery_report["sha256"],
                "delivery_mode": delivery_mode,
            }
        )
    dump_json(ledger_file, ledger)
    manifest["status"] = "completed"
    manifest["completed_at"] = utc_now()
    for episode in manifest["episodes"]:
        episode["status"] = "completed"
    dump_json(manifest_path, manifest)
    inventory_path = target / "artifacts" / "gpu_asset_inventory.json"
    inventory = load_json(inventory_path) if inventory_path.is_file() else {"assets": []}
    visual_counts = []
    for config_path in _resolve_episode_paths(batch_path, batch):
        episode = load_json(config_path)
        plan_path = _episode_dir(episode, projects_root) / "artifacts" / "visual_plan.json"
        if plan_path.is_file():
            plan = load_json(plan_path)
            visual_counts.append(
                {
                    "project_id": episode["project_id"],
                    "duration_seconds": plan["duration_seconds"],
                    "scene_images": plan["image_count"],
                    "wan_clips": plan["wan_count"],
                }
            )
    timing = {
        "version": "1.0",
        "batch_id": batch["batch_id"],
        "created_at": manifest.get("created_at"),
        "gpu_window_started_at": manifest.get("gpu_window_started_at"),
        "gpu_generation_completed_at": manifest.get("gpu_generation_completed_at"),
        "gpu_window_closed_at": manifest.get("gpu_window_closed_at"),
        "local_packaging_started_at": manifest.get("local_packaging_started_at"),
        "completed_at": manifest.get("completed_at"),
        "gpu_generation_seconds": elapsed_seconds(
            manifest.get("gpu_window_started_at"),
            manifest.get("gpu_generation_completed_at"),
        ),
        "gpu_window_seconds": elapsed_seconds(
            manifest.get("gpu_window_started_at"),
            manifest.get("gpu_window_closed_at"),
        ),
        "local_packaging_seconds": elapsed_seconds(
            manifest.get("local_packaging_started_at"),
            manifest.get("completed_at"),
        ),
        "total_batch_seconds": elapsed_seconds(
            manifest.get("created_at"),
            manifest.get("completed_at"),
        ),
        "current_batch_asset_files": len(inventory.get("assets", [])),
        "current_batch_asset_bytes": sum(int(row.get("size", 0)) for row in inventory.get("assets", [])),
        "episodes": visual_counts,
    }
    dump_json(target / "artifacts" / "production_timing.json", timing)
    return {"batch_id": batch["batch_id"], "deliveries": delivered}


def _logical_size(path: Path) -> int:
    if path.is_file() or path.is_symlink():
        return path.stat().st_size
    if path.is_dir():
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    return 0


def _cleanup_target(path: Path, reason: str, kind: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "kind": kind,
        "reason": reason,
        "logical_bytes": _logical_size(path),
        "reclaimable_bytes": _logical_size(path),
    }


def cleanup_local_batch(
    batch: dict[str, Any],
    batch_path: Path,
    series: dict[str, Any],
    *,
    projects_root: Path = PROJECTS_ROOT,
    dry_run: bool = True,
    yes: bool = False,
    include_delayed: bool = False,
) -> dict[str, Any]:
    """Clean only derivative local fable files after verified delivery.

    Canonical project assets remain under projects/<project_id>/assets. Movies
    remains the final-video archive and should not receive cover files.
    """

    if not dry_run and not yes:
        raise ValueError("cleanup-local requires --yes after reviewing --dry-run")
    batch_target = _batch_dir(batch, projects_root)
    manifest_path = batch_target / "artifacts" / "gpu_batch_manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") != "completed":
        raise ValueError("cleanup-local requires a completed local batch")

    retention_days = int(series.get("local_storage", {}).get("delayed_cleanup_days", 7))
    all_targets: list[dict[str, Any]] = []
    deleted: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    for config_path in _resolve_episode_paths(batch_path, batch):
        episode = load_json(config_path)
        target = _episode_dir(episode, projects_root).resolve()
        if target.parent != projects_root.resolve():
            raise ValueError(f"Unsafe episode project path:{target}")
        delivery_report_path = target / "artifacts" / "delivery_report.json"
        if not delivery_report_path.is_file():
            raise FileNotFoundError(f"Verified delivery report is required before local cleanup:{delivery_report_path}")
        delivery_report = load_json(delivery_report_path)
        output = Path(str(delivery_report.get("output", ""))).expanduser()
        if not output.is_file():
            raise FileNotFoundError(f"Movies final video is missing:{output}")

        episode_targets: list[dict[str, Any]] = []
        public_dir = (REMOTION_ROOT / "public" / "treeelf-fable" / episode["project_id"]).resolve()
        expected_public_parent = (REMOTION_ROOT / "public" / "treeelf-fable").resolve()
        if public_dir.parent != expected_public_parent:
            raise ValueError(f"Unsafe Remotion staging path:{public_dir}")
        if public_dir.exists():
            episode_targets.append(_cleanup_target(public_dir, "Remotion staging duplicate", "directory"))

        renders = (target / "renders").resolve()
        if renders.parent != target:
            raise ValueError(f"Unsafe project renders path:{renders}")
        if renders.exists() and any(renders.iterdir()):
            episode_targets.append(_cleanup_target(renders, "Movies is the verified final-video archive", "directory_contents"))

        background = target / "assets" / "music" / "background.mp3"
        selection_report = target / "artifacts" / "music_selection.json"
        selected_music = Path("")
        if selection_report.is_file():
            selected_music = Path(str(load_json(selection_report).get("selected", {}).get("path", ""))).expanduser()
        if background.is_file() and selected_music.is_file():
            selected_sha = str(load_json(selection_report).get("selected", {}).get("source_sha256", ""))
            if not selected_sha or sha256_file(selected_music) == selected_sha:
                episode_targets.append(_cleanup_target(background, "Regenerable normalized music derivative; verified central source remains available", "file"))

        if include_delayed:
            completed_at = datetime.fromisoformat(delivery_report["completed_at"])
            age_days = (datetime.now(timezone.utc) - completed_at.astimezone(timezone.utc)).total_seconds() / 86400
            if age_days < retention_days:
                raise ValueError(
                    f"Delayed cleanup requires {retention_days} days after delivery; current age is {age_days:.1f} days"
                )
            for name in ("review", "review_frames"):
                review_dir = target / "artifacts" / name
                if review_dir.exists():
                    episode_targets.append(_cleanup_target(review_dir, "Visual QC report JSON remains canonical", "directory"))

        if not dry_run:
            for item in episode_targets:
                path = Path(item["path"])
                if item["kind"] == "directory_contents":
                    shutil.rmtree(path)
                    path.mkdir(parents=True, exist_ok=True)
                elif path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                elif path.exists() or path.is_symlink():
                    path.unlink()
                deleted.append(item)

        all_targets.extend(episode_targets)
        episodes.append(
            {
                "project_id": episode["project_id"],
                "targets": episode_targets,
                "canonical_assets_retained": str(target / "assets"),
                "cover_asset_retained": delivery_report.get("cover_asset"),
                "final_video_retained": str(output),
            }
        )

    result = {
        "version": "1.0",
        "batch_id": batch["batch_id"],
        "dry_run": dry_run,
        "include_delayed": include_delayed,
        "targets": all_targets,
        "deleted": deleted,
        "logical_bytes_removed": sum(item["logical_bytes"] for item in all_targets),
        "bytes_reclaimable": sum(item["reclaimable_bytes"] for item in all_targets),
        "episodes": episodes,
        "checked_at": utc_now(),
    }
    dump_json(batch_target / "artifacts" / "local_storage_cleanup_report.json", result)
    return result


def finalize_gpu_command(
    batch: dict[str, Any],
    *,
    projects_root: Path = PROJECTS_ROOT,
    dry_run: bool,
    yes: bool,
    shutdown: bool,
    ssh_host: str,
) -> dict[str, Any]:
    target = _batch_dir(batch, projects_root)
    manifest_path = target / "artifacts" / "gpu_batch_manifest.json"
    inventory = target / "artifacts" / "gpu_asset_inventory.json"
    if not inventory.is_file():
        raise FileNotFoundError("verify-gpu-assets must pass before finalization")
    if not (target / "artifacts" / "remote_runtime_baseline.json").is_file():
        raise FileNotFoundError("capture-gpu-baseline must pass before finalization")
    manifest = load_json(manifest_path)
    if manifest.get("status") != "gpu_assets_complete":
        raise ValueError("batch must be gpu_assets_complete before finalization")
    if shutdown and (dry_run or not yes):
        raise ValueError("shutdown requires --yes and a non-dry-run invocation")
    command = [
        str(REPO_ROOT / ".venv" / "bin" / "python"),
        str(REPO_ROOT / "scripts" / "finalize_autodl_comfyui_batch.py"),
        "--project-dir",
        str(target),
        "--policy",
        str(target / "artifacts" / "retention_policy.json"),
        "--ssh-host",
        ssh_host,
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
        manifest["gpu_window_closed_at"] = manifest["gpu_finalized_at"]
        manifest["shutdown_requested"] = shutdown
        dump_json(manifest_path, manifest)
    return {"command": command, "output": result.stdout.strip(), "status": manifest["status"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "validate",
            "prepare",
            "capture-gpu-baseline",
            "refresh-visuals",
            "verify-gpu-assets",
            "create-qc-templates",
            "stage-local",
            "render-local",
            "complete-local",
            "cleanup-local",
            "finalize-gpu",
            "status",
        ),
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_BATCH)
    parser.add_argument("--series", type=Path, default=DEFAULT_SERIES)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--shutdown", action="store_true")
    parser.add_argument("--include-delayed", action="store_true")
    parser.add_argument("--ssh-host", default="autodl-comfyui")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    batch = load_json(args.config)
    series = load_json(args.series)
    errors = validate_batch(batch, args.config, series)
    if args.command == "validate":
        result: Any = {"valid": not errors, "errors": errors}
    elif errors:
        raise SystemExit("Invalid TreeElf fable batch:\n- " + "\n- ".join(errors))
    elif args.command == "prepare":
        result = prepare_batch(batch, args.config, series)
    elif args.command == "capture-gpu-baseline":
        result = capture_gpu_baseline(batch, ssh_host=args.ssh_host)
    elif args.command == "refresh-visuals":
        result = refresh_visuals(batch, args.config, series)
    elif args.command == "verify-gpu-assets":
        result = verify_gpu_assets(batch, series)
    elif args.command == "create-qc-templates":
        result = create_qc_templates(batch, args.config)
    elif args.command == "stage-local":
        result = stage_local_batch(batch, args.config, series)
    elif args.command == "render-local":
        result = render_local(batch, args.config)
    elif args.command == "complete-local":
        result = complete_local_batch(batch, args.config, series)
    elif args.command == "cleanup-local":
        if not args.dry_run and not args.yes:
            raise SystemExit("cleanup-local requires --dry-run or --yes")
        result = cleanup_local_batch(
            batch,
            args.config,
            series,
            dry_run=args.dry_run,
            yes=args.yes,
            include_delayed=args.include_delayed,
        )
    elif args.command == "finalize-gpu":
        result = finalize_gpu_command(
            batch,
            dry_run=args.dry_run,
            yes=args.yes,
            shutdown=args.shutdown,
            ssh_host=args.ssh_host,
        )
    else:
        manifest = _batch_dir(batch) / "artifacts" / "gpu_batch_manifest.json"
        result = load_json(manifest) if manifest.is_file() else {"batch_id": batch.get("batch_id"), "status": "not_prepared"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
