#!/usr/bin/env python3
"""Reusable TreeElf philosophy-video episode workflow.

The JSON file is the production contract.  This module deliberately keeps
creative decisions in that reviewed contract and only performs repeatable
mechanical work: validation, source snapshotting, GPU generation, Remotion
staging, delivery verification, and completion-state persistence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.paths import PROJECTS_DIR
from lib.treeelf_music import (
    DEFAULT_CATALOG_PATH,
    DEFAULT_OVERRIDES_PATH,
    DEFAULT_USAGE_LEDGER_PATH,
    normalize_background_music,
    record_music_usage,
    select_music_track,
)
from scripts.treeelf_philosophy_brand_pilot import (
    _event_summary,
    _execute_candidate,
    dump_json,
    ensure_gpu_preflight,
    generate_article_visual_assets,
    load_json,
    media_duration_seconds,
    parse_markdown,
    scan_inbox,
    sha256_file,
)
from tools.audio.comfyui_tts import ComfyUITTS
from scripts import treeelf_philosophy_timeline as timeline

DEFAULT_SERIES_CONFIG = (
    REPO_ROOT / "workflow_configs" / "zh-philosophy-video" / "treeelf-continuing-series-v1.json"
)
DEFAULT_EPISODE_CONFIG = (
    REPO_ROOT / "workflow_configs" / "zh-philosophy-video" / "treeelf-episode-template.json"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def episode_dir(config: dict[str, Any], projects_dir: Path = PROJECTS_DIR) -> Path:
    return projects_dir / str(config["project_id"])


def remotion_public_dir(config: dict[str, Any]) -> Path:
    root = Path(
        config.get(
            "remotion_public_root",
            REPO_ROOT / "remotion-composer" / "public",
        )
    )
    return root / str(config["project_id"])


def _atomic_link_or_copy(source: Path, destination: Path) -> str:
    """Prefer a zero-copy hard link and fall back to an atomic byte copy."""

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


def _path_size(path: Path) -> int:
    if path.is_file() or path.is_symlink():
        return path.lstat().st_size
    if path.is_dir():
        return sum(item.lstat().st_size for item in path.rglob("*") if item.is_file() or item.is_symlink())
    return 0


def _path_reclaimable_size(path: Path) -> int:
    candidates = [path] if path.is_file() or path.is_symlink() else list(path.rglob("*")) if path.is_dir() else []
    return sum(
        item.lstat().st_size
        for item in candidates
        if (item.is_file() or item.is_symlink()) and item.lstat().st_nlink <= 1
    )


def _safe_chinese_filename(value: str, *, fallback: str = "树精灵成片") -> str:
    """Keep Chinese titles readable while removing filesystem-hostile characters."""

    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]+", " ", str(value)).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" .")
    return cleaned or fallback


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}_v{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Too many delivery filename collisions: {path}")


def _delivery_output_path(config: dict[str, Any], render: Path, delivery_dir: Path) -> Path:
    explicit = str(config.get("delivery_filename", "")).strip()
    if explicit:
        filename = _safe_chinese_filename(explicit)
        if not Path(filename).suffix:
            filename += render.suffix or ".mp4"
    else:
        title = str(config.get("title") or config.get("cover_title") or config.get("project_id"))
        date_match = re.search(r"(20\d{6})", str(config.get("project_id", "")))
        date_prefix = ""
        if date_match:
            raw = date_match.group(1)
            date_prefix = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}_"
        filename = f"{date_prefix}{_safe_chinese_filename(title)}{render.suffix or '.mp4'}"
    return _unique_path(delivery_dir / filename)


def _cleanup_target(path: Path, reason: str, kind: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "reason": reason,
        "kind": kind,
        "logical_bytes": _path_size(path),
        "reclaimable_bytes": _path_reclaimable_size(path),
    }


def _script_fragments(text: str, *, limit: int = 8) -> list[str]:
    fragments = [
        part.strip()
        for part in re.findall(r"[^。！？!?\n]+[。！？!?]?", text)
        if len(part.strip()) >= 6
    ]
    return fragments[:limit]


def _keyword_hits(text: str, keyword_map: dict[str, list[str]]) -> list[str]:
    hits: list[str] = []
    for label, keywords in keyword_map.items():
        if any(keyword in text for keyword in keywords):
            hits.append(label)
    return hits


def build_visual_brief(config: dict[str, Any], series: dict[str, Any], script_body: str) -> dict[str, Any]:
    """Create an auditable semantic brief before writing image prompts/assets.

    Episode configs may still provide a hand-reviewed ``visual_brief``.  This
    function fills the missing baseline so every episode leaves behind the
    same analysis artifact: emotion, metaphors, visual modes, and style logic.
    """

    provided = config.get("visual_brief", {}) if isinstance(config.get("visual_brief"), dict) else {}
    title = str(config.get("title", "")).strip()
    text = f"{title}\n{script_body}"
    emotion_map = {
        "松弛": ["松弛", "放下", "轻", "允许", "自由", "安心", "慢"],
        "清醒": ["清醒", "看见", "意识到", "事实", "证据", "判断", "边界"],
        "孤独": ["孤独", "一个人", "没人", "空", "冷", "远"],
        "焦虑": ["焦虑", "紧张", "害怕", "担心", "控制", "失控", "压力"],
        "温柔": ["温柔", "爱", "喜欢", "靠近", "陪伴", "接住", "心疼"],
        "荒诞": ["荒诞", "好笑", "奇怪", "反差", "滑稽", "误会"],
        "坚定": ["坚定", "选择", "行动", "练习", "开始", "站稳"],
    }
    metaphor_map = {
        "榜单/坐标": ["榜", "排名", "坐标", "标准", "比较", "位置"],
        "门/边界": ["门", "门槛", "边界", "进入", "离开", "打开"],
        "身体/地面": ["身体", "呼吸", "脚", "地面", "落地", "感受"],
        "镜子/回声": ["镜", "看见", "回声", "投射", "反射"],
        "频率/信号": ["频率", "信号", "共振", "同步", "节奏"],
        "容器/空间": ["容器", "空间", "房间", "盒子", "塞", "空白"],
        "证据/痕迹": ["证据", "痕迹", "线索", "记录", "事实"],
        "时间/旧脚本": ["过去", "未来", "时间", "旧", "脚本", "循环"],
    }
    emotions = provided.get("emotional_core") or _keyword_hits(text, emotion_map) or ["清醒", "温柔"]
    metaphors = provided.get("metaphor_candidates") or _keyword_hits(text, metaphor_map) or ["容器/空间", "证据/痕迹"]
    visuals = config.get("article_visual_assets", {})
    brief = {
        "version": "1.0",
        "project_id": config.get("project_id"),
        "title": title,
        "source_script_md": config.get("source_script_md"),
        "generated_at": utc_now(),
        "source_text_sha256": hashlib.sha256(script_body.encode("utf-8")).hexdigest(),
        "emotional_core": emotions,
        "metaphor_candidates": metaphors,
        "script_fragments_for_prompting": provided.get("script_fragments_for_prompting") or _script_fragments(script_body),
        "visual_modes": {
            "narrative_concrete": {
                "definition": "用具体场景表达句子：人物、地点、动作、物件。",
                "priority": "这件事像真实发生过。",
            },
            "abstract_imagery": {
                "definition": "用象征物、空间关系、材质、光线表达句子。",
                "priority": "这句话在心理层面像什么。",
                "hard_rule": "每个抽象元素必须对应一个文案概念。",
                "generation_order": "先想象征物，再想画面。",
            },
            "style_fusion_translation": {
                "definition": "用一种或多种艺术语言，把文案中的情绪、隐喻、认知动作转译成几个风格相融合的画面。",
                "priority": "这篇文章如果变成一组艺术镜头，会长什么样。",
                "hard_rule": "每个风格选择必须说明它和文案的关系。",
                "generation_order": "先想艺术语言，再把语义转译进去。",
            },
            "overlap_note": "抽象意象和风格融合转译不是完全互斥；很多风格融合图本身也会抽象。分类的意义在于生成时的主目标不同。",
        },
        "target_ratios": visuals.get("target_ratios") or {
            "narrative_concrete": 0.15,
            "abstract_imagery": 0.40,
            "style_fusion_translation": 0.45,
        },
        "style_families": visuals.get("style_families", []),
        "style_source": visuals.get("style_source") or series.get("visual", {}).get("style_source"),
        "technical_guardrails": visuals.get("technical_guardrails") or series.get("visual", {}).get("technical_guardrails", []),
        "prompt_contract": [
            "每张图写清 semantic_anchor。",
            "风格融合图写清 style_logic。",
            "抽象元素和风格词都必须能解释为什么适合当前文案。",
            "创意 prompt 写正向画面目标，技术护栏单独保留。",
        ],
    }
    brief.update({key: value for key, value in provided.items() if key not in brief})
    return brief


def _music_library_candidates(config: dict[str, Any], series: dict[str, Any]) -> list[Path]:
    music_config = series.get("music", {})
    roots = []
    for raw in (
        config.get("music_library_dir"),
        config.get("music", {}).get("library_dir") if isinstance(config.get("music"), dict) else None,
        music_config.get("library_dir"),
    ):
        if raw:
            roots.append(Path(str(raw)).expanduser())
    fallback_source = Path(str(config.get("music_source", ""))).expanduser()
    if fallback_source.is_file():
        roots.append(fallback_source.parent)
    files: list[Path] = []
    suffixes = {".mp3", ".wav", ".m4a", ".flac", ".aac"}
    for root in roots:
        if root.is_file() and root.suffix.lower() in suffixes:
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)
    return sorted(set(files), key=lambda path: str(path))


def _infer_music_keywords(config: dict[str, Any], script_body: str) -> list[str]:
    text = f"{config.get('title', '')}\n{config.get('cover_title', '')}\n{script_body}"
    rules = [
        (("爱", "温柔", "关系", "靠近", "心疼", "喜欢"), ["温暖", "浪漫", "钢琴", "ambient", "chillwave", "neo-classical"]),
        (("焦虑", "压力", "失控", "恐惧", "紧张"), ["downtempo", "lo-fi", "ambient", "低吟", "缓慢", "冷静"]),
        (("身体", "呼吸", "地面", "感受", "落地"), ["new age", "竖琴", "ambient", "冥想", "轻音乐", "calming"]),
        (("证据", "事实", "清醒", "判断", "理性"), ["minimal", "lo-fi", "piano", "ambient", "study", "冷静"]),
        (("行动", "开始", "练习", "选择", "坚定"), ["自信", "post-rock", "soundtrack", "uplifting", "cinematic"]),
        (("荒诞", "好笑", "反差", "误会", "榜", "排名"), ["jazz", "lo-fi", "fusion", "轻盈", "bossa", "downtempo"]),
        (("孤独", "夜", "空", "远", "过去", "时间"), ["ambient", "chillwave", "dreamy", "梦幻", "downtempo"]),
    ]
    keywords: list[str] = []
    for triggers, additions in rules:
        if any(trigger in text for trigger in triggers):
            keywords.extend(additions)
    configured = config.get("music", {}).get("preferred_keywords", []) if isinstance(config.get("music"), dict) else []
    keywords.extend(str(item) for item in configured)
    return list(dict.fromkeys(keyword.lower() for keyword in keywords if str(keyword).strip())) or [
        "ambient",
        "纯音乐",
        "梦幻",
        "lo-fi",
    ]


def select_music_source(
    config: dict[str, Any],
    series: dict[str, Any],
    *,
    script_body: str | None = None,
    used_music_paths: list[str] | None = None,
    usage_ledger_path: Path | None = None,
) -> dict[str, Any]:
    if script_body is None:
        try:
            _, script_body = parse_markdown(Path(config["source_script_md"]))
        except Exception:
            script_body = ""
    keywords = _infer_music_keywords(config, script_body)
    fallback = Path(str(config.get("music_source", ""))).expanduser()
    music_config = series.get("music", {})
    roots: list[Path] = []
    for raw in (
        config.get("music_library_dir"),
        config.get("music", {}).get("library_dir") if isinstance(config.get("music"), dict) else None,
        music_config.get("library_dir"),
    ):
        if raw:
            roots.append(Path(str(raw)).expanduser())
    if fallback.is_file() and fallback.parent not in roots:
        roots.append(fallback.parent)
    return select_music_track(
        project_id=str(config.get("project_id", "")),
        series="zh-philosophy-video",
        keywords=keywords,
        library_dirs=roots,
        fallback_source=fallback,
        used_music_paths=used_music_paths,
        catalog_path=Path(str(music_config.get("catalog_path", DEFAULT_CATALOG_PATH))).expanduser(),
        overrides_path=Path(str(music_config.get("overrides_path", DEFAULT_OVERRIDES_PATH))).expanduser(),
        usage_ledger_path=usage_ledger_path or Path(str(music_config.get("usage_ledger_path", DEFAULT_USAGE_LEDGER_PATH))).expanduser(),
    )


def cleanup_local_storage(
    config: dict[str, Any],
    series: dict[str, Any],
    *,
    projects_dir: Path = PROJECTS_DIR,
    dry_run: bool = True,
    yes: bool = False,
    include_delayed: bool = False,
) -> dict[str, Any]:
    """Remove only reviewed derivative copies while preserving canonical assets."""

    if not dry_run and not yes:
        raise ValueError("Local cleanup requires --yes after reviewing --dry-run")
    target = episode_dir(config, projects_dir).resolve()
    delivery_report = target / "artifacts" / "delivery_report.json"
    if not delivery_report.is_file():
        raise FileNotFoundError("Verified delivery report is required before local cleanup")
    policy = series.get("local_storage", {})
    targets: list[dict[str, Any]] = []
    public_dir = remotion_public_dir(config).resolve()
    expected_public_parent = Path(
        config.get("remotion_public_root", REPO_ROOT / "remotion-composer" / "public")
    ).resolve()
    if public_dir.parent != expected_public_parent:
        raise ValueError(f"Unsafe Remotion staging path: {public_dir}")
    if public_dir.exists():
        targets.append(_cleanup_target(public_dir, "Remotion staging duplicate", "directory"))

    renders = (target / "renders").resolve()
    if renders.parent != target:
        raise ValueError(f"Unsafe project renders path: {renders}")
    if renders.exists() and any(renders.iterdir()):
        targets.append(_cleanup_target(renders, "Movies is the verified final-video archive", "directory_contents"))

    raw_narration = target / "assets" / "audio" / "narration_raw.mp3"
    if raw_narration.is_file():
        targets.append(_cleanup_target(raw_narration, "Normalized narration.wav is canonical", "file"))

    background = target / "assets" / "audio" / "background.mp3"
    music_source = Path(config.get("music_source", "")).expanduser()
    selection_report = target / "artifacts" / "music_selection.json"
    if selection_report.is_file():
        selected_music = Path(str(load_json(selection_report).get("selected", {}).get("path", ""))).expanduser()
        if selected_music.is_file():
            music_source = selected_music
    if background.is_file() and music_source.is_file():
        selected_sha = ""
        if selection_report.is_file():
            selected_sha = str(load_json(selection_report).get("selected", {}).get("source_sha256", ""))
        if not selected_sha or sha256_file(music_source) == selected_sha:
            targets.append(_cleanup_target(background, "Regenerable normalized music derivative; verified central source remains available", "file"))

    if include_delayed:
        retention_days = int(policy.get("delayed_cleanup_days", 7))
        completed_at = datetime.fromisoformat(load_json(delivery_report)["completed_at"])
        age_days = (datetime.now(timezone.utc) - completed_at.astimezone(timezone.utc)).total_seconds() / 86400
        if age_days < retention_days:
            raise ValueError(
                f"Delayed cleanup requires {retention_days} days after delivery; current age is {age_days:.1f} days"
            )
        segments = target / "assets" / "audio" / "voice02_segments"
        if segments.exists():
            targets.append(_cleanup_target(segments, "Paragraph patch window expired", "directory"))
        for name in ("review", "review_frames"):
            review_dir = target / "artifacts" / name
            if review_dir.exists():
                targets.append(_cleanup_target(review_dir, "Visual QC report JSON remains canonical", "directory"))

    deleted: list[dict[str, Any]] = []
    if not dry_run:
        for item in targets:
            path = Path(item["path"])
            if item["kind"] == "directory_contents":
                shutil.rmtree(path)
                path.mkdir(parents=True, exist_ok=True)
            elif path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            elif path.exists() or path.is_symlink():
                path.unlink()
            deleted.append(item)
    result = {
        "version": "1.0",
        "project_id": config["project_id"],
        "dry_run": dry_run,
        "include_delayed": include_delayed,
        "targets": targets,
        "deleted": deleted,
        "logical_bytes_removed": sum(item["logical_bytes"] for item in targets),
        "bytes_reclaimable": sum(item["reclaimable_bytes"] for item in targets),
        "canonical_assets_retained": str(target / "assets"),
        "final_video_retained": load_json(delivery_report)["output"],
        "checked_at": utc_now(),
    }
    dump_json(target / "artifacts" / "local_storage_cleanup_report.json", result)
    return result


TEXT_RISK_PROMPT_TERMS = (
    "phrase", "sentence", "word", "caption", "quote",
    "note", "notebook", "page", "document", "chart",
    "label", "tag", "ticket", "form", "letter", "hand marks",
    "typography", "editorial layout", "idea table",
)


def prompt_text_artifact_risk(prompt: str) -> list[str]:
    """Return text-bearing subject terms that often make Krea invent pseudo text.

    Paper, desks and archives are useful TreeElf motifs, so they are not banned
    by themselves.  The gate focuses on objects that ask the model to depict
    language-bearing surfaces or structured written information.
    """

    lowered = prompt.lower()
    risks: list[str] = []
    for term in TEXT_RISK_PROMPT_TERMS:
        pattern = r"(?<![a-z0-9_-])" + re.escape(term) + r"(?![a-z0-9_-])"
        if re.search(pattern, lowered):
            risks.append(term)
    return risks


def validate_episode(config: dict[str, Any], series: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("project_id", "title", "cover_title", "source_script_md", "article_visual_assets", "edit"):
        if not config.get(key):
            errors.append(f"missing:{key}")

    visuals = config.get("article_visual_assets", {})
    images = visuals.get("images", [])
    videos = visuals.get("videos", [])
    technical_guardrails = [str(item).lower() for item in visuals.get("technical_guardrails", [])]
    defaults = series.get("production_defaults", {})
    minimum_images = int(
        defaults.get("minimum_images_per_episode", defaults.get("images_per_episode", 15))
    )
    expected_videos = int(defaults.get("wan_clips_per_episode", 2))
    wan_max_seconds = float(defaults.get("wan_max_generation_seconds", 5))
    cover_count = sum(item.get("role") == "cover" or item.get("id") == "C01" for item in images)
    if cover_count != 1:
        errors.append("article_visual_assets.images must contain exactly one cover")
    if not images:
        errors.append("article_visual_assets.images must not be empty")
    if len(images) < minimum_images:
        errors.append(f"article_visual_assets.images must contain at least {minimum_images} items")
    if len(videos) != expected_videos:
        errors.append(f"article_visual_assets.videos must contain exactly {expected_videos} items")
    wan_policy = visuals.get("wan_policy", {})
    if wan_policy.get("enabled"):
        if str(wan_policy.get("selection_policy")) != "opening_hook_plus_longest_semantic_safe":
            errors.append("article_visual_assets.wan_policy.selection_policy must be opening_hook_plus_longest_semantic_safe")
        if float(wan_policy.get("max_generation_seconds", wan_max_seconds)) > wan_max_seconds:
            errors.append(f"article_visual_assets.wan_policy.max_generation_seconds must be <= {wan_max_seconds:g}")
        roles = [item.get("selection_role") for item in videos]
        if "opening_hook" not in roles or "longest_semantic_safe" not in roles:
            errors.append("Wan videos must include opening_hook and longest_semantic_safe selection roles")
    for item in videos:
        if float(item.get("duration_seconds", 4)) > wan_max_seconds:
            errors.append(f"{item.get('id')}: Wan duration_seconds must be <= {wan_max_seconds:g}")
    ids = [item.get("id") for item in images + videos]
    if len(ids) != len(set(ids)):
        errors.append("visual asset ids must be unique")
    required_guardrail_terms = ("text", "logo", "watermark", "pseudo")
    if not technical_guardrails or not all(
        any(term in guardrail for guardrail in technical_guardrails)
        for term in required_guardrail_terms
    ):
        errors.append(
            "article_visual_assets.technical_guardrails must cover text-free media, logos, watermarks and pseudo typography"
        )
    aesthetic_negative_patterns = (
        "no red thread", "no red line", "no stamp", "no shattered glass",
        "no spiritual glow", "no dramatic recovery smile", "不要红绳", "不要红线",
        "不要裂镜", "避免红绳", "避免裂镜",
    )
    for item in images + videos:
        prompt = str(item.get("prompt", "")).lower()
        review = str(item.get("prompt_review", "")).lower()
        if any(pattern in prompt for pattern in aesthetic_negative_patterns):
            errors.append(f"{item.get('id')}: creative prompt must use positive semantic imagery, not aesthetic bans")
        text_risk_terms = prompt_text_artifact_risk(prompt)
        if text_risk_terms and "text_risk_mitigation:" not in review:
            errors.append(
                f"{item.get('id')}: prompt uses text-bearing visual terms "
                f"({', '.join(text_risk_terms)}); add prompt_review text_risk_mitigation "
                "and rewrite with text-free visual substitutes before GPU generation"
            )
        if item.get("visual_mode") in {"abstract_imagery", "style_fusion_translation"}:
            if "semantic_anchor" not in review:
                errors.append(f"{item.get('id')}: abstract/style prompts require semantic_anchor in prompt_review")
            if item.get("visual_mode") == "style_fusion_translation" and "style_logic" not in review:
                errors.append(f"{item.get('id')}: style-fusion prompts require style_logic in prompt_review")
    style_family_count = len(visuals.get("style_families", []))
    visual_rules = series.get("visual", {})
    style_range = visual_rules.get("style_families_per_episode", [2, 3])
    if not int(style_range[0]) <= style_family_count <= int(style_range[1]):
        errors.append(
            f"article_visual_assets.style_families must contain {style_range[0]} to {style_range[1]} families"
        )
    ratios = visuals.get("target_ratios", {})
    if ratios:
        total = sum(float(value) for value in ratios.values())
        if abs(total - 1.0) > 0.001:
            errors.append("article_visual_assets.target_ratios must sum to 1.0")

    edit = config.get("edit", {})
    cards = edit.get("info_cards", [])
    if not 2 <= len(cards) <= 3:
        errors.append("edit.info_cards must contain 2 or 3 cards")
    motions = [scene.get("motion") for scene in edit.get("scenes", []) if scene.get("kind") == "still"]
    if any(a == b for a, b in zip(motions, motions[1:])):
        errors.append("adjacent still scenes must not repeat the same motion")
    still_sources = [str(scene.get("src", "")) for scene in edit.get("scenes", []) if scene.get("kind") == "still"]
    video_sources = [str(scene.get("src", "")) for scene in edit.get("scenes", []) if scene.get("kind") == "video"]
    if len(still_sources) != len(set(still_sources)):
        errors.append("edit.scenes must not reuse a still-image src")
    if len(video_sources) != len(set(video_sources)):
        errors.append("edit.scenes must not reuse a video src")
    video_references = [str(item.get("reference", "")) for item in videos]
    if len(video_references) != len(set(video_references)):
        errors.append("article_visual_assets.videos must use unique reference images")
    still_image_ids = {Path(source).stem for source in still_sources}
    if still_image_ids.intersection(video_references):
        errors.append("Wan reference images must not also be reused as ordinary still scenes")
    content_image_ids = {str(item.get("id")) for item in images if item.get("role") != "cover" and item.get("id") != "C01"}
    used_content_ids = still_image_ids.union(video_references)
    if content_image_ids != used_content_ids:
        errors.append("every content image must be used exactly once: either as one still scene or one Wan reference")

    caption = series.get("caption", {})
    if caption.get("color") != "#FFFFFF" or caption.get("background") != "none":
        errors.append("series caption must be white with no background")
    if float(caption.get("safe_bottom", 0)) < 330:
        errors.append("series caption.safe_bottom must keep subtitles above platform bottom UI")
    if float(series.get("music", {}).get("remotion_volume", -1)) != 0.30:
        errors.append("series music.remotion_volume must be locked to narration-first profile B3 (0.30)")
    if series.get("voice", {}).get("workflow_template") != "qwen3_tts_voice_clone_load":
        errors.append("series voice must use qwen3_tts_voice_clone_load")
    if series.get("cover", {}).get("brand") != "树精灵":
        errors.append("series cover.brand must be 树精灵")
    return errors


def prepare_episode(
    config: dict[str, Any], series: dict[str, Any], *, projects_dir: Path = PROJECTS_DIR
) -> dict[str, Any]:
    errors = validate_episode(config, series)
    if errors:
        raise ValueError("Invalid episode config:\n- " + "\n- ".join(errors))
    source = Path(config["source_script_md"])
    if not source.is_file():
        raise FileNotFoundError(source)
    metadata, body = parse_markdown(source)
    if str(metadata.get("production_status", "")) in {"completed", "produced", "archived"}:
        raise ValueError(f"Source is already completed: {source}")

    target = episode_dir(config, projects_dir)
    artifacts = target / "artifacts"
    for path in (
        artifacts,
        target / "assets" / "audio",
        target / "assets" / "images" / "article",
        target / "assets" / "video" / "article",
        target / "renders",
    ):
        path.mkdir(parents=True, exist_ok=True)
    snapshot = artifacts / "source_script.md"
    shutil.copy2(source, snapshot)
    dump_json(
        target / "project.json",
        {
            "version": "1.0",
            "project_id": config["project_id"],
            "title": config["title"],
            "pipeline": "animated-explainer",
            "status": "prepared",
            "source_path": str(source),
            "source_sha256": sha256_file(source),
            "source_snapshot_sha256": sha256_file(snapshot),
            "prepared_at": utc_now(),
        },
    )
    dump_json(artifacts / "episode_config.json", config)
    dump_json(artifacts / "series_profile.json", series)
    json_safe_metadata = json.loads(json.dumps(metadata, ensure_ascii=False, default=str))
    dump_json(
        artifacts / "script.json",
        {"title": config["title"], "body": body, "source_metadata": json_safe_metadata},
    )
    visual_brief = build_visual_brief(config, series, body)
    dump_json(artifacts / "visual_brief.json", visual_brief)
    report_path = artifacts / "gpu_usage_report.json"
    if not report_path.exists():
        dump_json(
            report_path,
            {
                "version": "1.0",
                "project_id": config["project_id"],
                "status": "prepared_gpu_not_started",
                "events": [],
                "created_at": utc_now(),
            },
        )
    return {
        "project_dir": str(target),
        "source_sha256": sha256_file(source),
        "visual_brief": str(artifacts / "visual_brief.json"),
    }


def generate_narration(
    config: dict[str, Any], series: dict[str, Any], *, projects_dir: Path = PROJECTS_DIR,
    run_preflight: bool = True,
) -> dict[str, Any]:
    target = episode_dir(config, projects_dir)
    report_path = target / "artifacts" / "gpu_usage_report.json"
    if run_preflight:
        ensure_gpu_preflight(report_path)
    _, body = parse_markdown(Path(config["source_script_md"]))
    narration_source = str(config.get("narration_text") or body).strip()
    narration_text = "\n".join(
        line for line in narration_source.splitlines() if not line.lstrip().startswith("#")
    ).strip()
    paragraphs = [part.strip() for part in narration_text.split("\n\n") if part.strip()]
    output_dir = target / "assets" / "audio"
    segment_dir = output_dir / "voice02_segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "narration_raw.mp3"
    voice = series["voice"]
    os.environ["COMFYUI_REMOTE_ASSET_POLICY"] = "retain_until_batch_end"
    assets: list[dict[str, Any]] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        segment = segment_dir / f"s{index:02d}.mp3"
        asset = _execute_candidate(
            tool=ComfyUITTS(),
            inputs={
                "text": paragraph,
                "workflow_template": voice["workflow_template"],
                "voice_name": voice["voice_name"],
                "language": "Chinese",
                "seed": int(voice["seed"]) + index - 1,
                "temperature": voice["temperature"],
                "top_p": voice["top_p"],
                "top_k": voice["top_k"],
                "max_new_tokens": voice["max_new_tokens"],
                "output_path": str(segment),
            },
            candidate_id=f"narration-voice02-s{index:02d}",
            kind="formal_narration_segment",
            report_path=report_path,
        )
        asset["text_sha256"] = hashlib.sha256(paragraph.encode("utf-8")).hexdigest()
        asset["voice_name"] = voice["voice_name"]
        assets.append(asset)

    concat_list = target / "artifacts" / "voice02_segments.concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{segment.resolve()}'" for segment in sorted(segment_dir.glob("s*.mp3"))) + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(output)],
        check=True,
        capture_output=True,
    )
    normalized = output_dir / "narration.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(output), "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-ar", "48000", "-ac", "1", str(normalized)],
        check=True,
        capture_output=True,
    )
    dump_json(
        target / "artifacts" / "formal_narration_manifest.json",
        {
            "version": "1.0",
            "voice_name": voice["voice_name"],
            "text_sha256": hashlib.sha256(narration_text.encode("utf-8")).hexdigest(),
            "segments": assets,
            "concat_path": str(output),
            "normalized_path": str(normalized),
        },
    )
    report = load_json(report_path)
    report["status"] = "narration_generated_remote_retained"
    report["summary"] = _event_summary(report.get("events", []))
    dump_json(report_path, report)
    return {"path": str(normalized), "raw_path": str(output), "duration_seconds": media_duration_seconds(normalized), "segments": len(assets)}


def generate_gpu(
    config: dict[str, Any], series: dict[str, Any], *, projects_dir: Path = PROJECTS_DIR
) -> dict[str, Any]:
    narration = generate_narration(config, series, projects_dir=projects_dir)
    captions = build_exact_captions(config, projects_dir=projects_dir)
    visuals = generate_article_visual_assets(config, projects_dir=projects_dir)
    return {"narration": narration, "captions": captions, "visuals": visuals}


def _caption_chunks(paragraph: str, *, max_chars: int = 22) -> list[str]:
    clauses = [part.strip() for part in re.findall(r"[^，。；：！？!?]+[，。；：！？!?]?", paragraph) if part.strip()]
    chunks: list[str] = []
    for clause in clauses:
        if len(clause) <= max_chars:
            chunks.append(clause)
            continue
        text = clause
        while len(text) > max_chars:
            split_at = max(text.rfind(mark, 0, max_chars + 1) for mark in "，；：") + 1
            if split_at <= 0:
                split_at = max_chars
            chunks.append(text[:split_at].strip())
            text = text[split_at:].strip()
        if text:
            chunks.append(text)
    return chunks


def build_exact_captions(
    config: dict[str, Any], *, projects_dir: Path = PROJECTS_DIR
) -> dict[str, Any]:
    target = episode_dir(config, projects_dir)
    _, body = parse_markdown(Path(config["source_script_md"]))
    narration_source = str(config.get("narration_text") or body).strip()
    narration_text = "\n".join(
        line for line in narration_source.splitlines() if not line.lstrip().startswith("#")
    ).strip()
    paragraphs = [part.strip().replace("\n", "") for part in narration_text.split("\n\n") if part.strip()]
    segment_paths = sorted((target / "assets" / "audio" / "voice02_segments").glob("s*.mp3"))
    if len(segment_paths) != len(paragraphs):
        raise ValueError(f"Narration paragraph/segment mismatch: {len(paragraphs)} != {len(segment_paths)}")
    captions: list[dict[str, Any]] = []
    offset = 0.0
    for paragraph, segment_path in zip(paragraphs, segment_paths):
        duration = media_duration_seconds(segment_path)
        if duration is None:
            raise ValueError(f"Cannot read narration segment duration: {segment_path}")
        chunks = _caption_chunks(paragraph)
        weights = [max(1, len(re.sub(r"[，。；：！？!?\s]", "", chunk))) for chunk in chunks]
        total_weight = sum(weights)
        cursor = offset
        for index, (chunk, weight) in enumerate(zip(chunks, weights)):
            allocation = duration * weight / total_weight
            end = offset + duration if index == len(chunks) - 1 else cursor + allocation
            captions.append({"start": round(cursor, 2), "end": round(max(cursor + 0.12, end - 0.06), 2), "text": chunk})
            cursor += allocation
        offset += duration
    payload = {
        "version": "1.0",
        "source": str(config["source_script_md"]),
        "source_text_sha256": hashlib.sha256(narration_text.encode("utf-8")).hexdigest(),
        "timing_source": "Qwen paragraph segment durations; MLX Whisper is QC only",
        "duration_seconds": round(offset, 2),
        "segments": captions,
    }
    output = target / "artifacts" / "exact_captions.json"
    dump_json(output, payload)
    return {"path": str(output), "segments": len(captions), "duration_seconds": round(offset, 2)}


def _caption_end_boundaries(captions: list[dict[str, Any]], duration: float) -> list[float]:
    boundaries = {
        0.0,
        round(float(duration), 2),
    }
    for caption in captions:
        try:
            end = float(caption["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 < end < duration:
            boundaries.add(round(end, 2))
    return sorted(boundaries)


def _snap_caption_boundary(
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


def _scene_caption_annotation(
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
    """Retiming policy for Remotion staging.

    The episode JSON still owns scene order, assets and motion.  Once exact
    caption timings exist, however, fixed placeholder slices are only a rough
    sketch.  This retimes scene cuts to the nearest caption end boundary so the
    image changes after a spoken idea lands, not a beat before it.
    """

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
        scene.update(_scene_caption_annotation(captions, 0.0, duration))
        return [scene], {
            "scene_timing": "caption_boundaries",
            "reason": "single scene stretched to exact narration/caption duration",
            "minimum_scene_seconds": None,
            "opening_target_seconds": None,
        }

    boundaries = _caption_end_boundaries(captions, duration)
    minimum_scene_seconds = 4.0
    opening_target_seconds = min(9.2, max(8.5, duration / max(3, count)))
    cuts = [0.0]

    first_maximum = max(opening_target_seconds, min(duration - minimum_scene_seconds * (count - 1), 11.5))
    first_maximum = min(first_maximum, duration - minimum_scene_seconds * (count - 1))
    if first_maximum <= minimum_scene_seconds:
        first_cut = round(duration / count, 2)
    else:
        first_cut = _snap_caption_boundary(
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
            cut = _snap_caption_boundary(boundaries, target, minimum=minimum, maximum=maximum)
        cuts.append(cut)
    cuts.append(round(duration, 2))

    retimed: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes):
        start = round(cuts[index], 2)
        end = round(max(start + 0.12, cuts[index + 1]), 2)
        updated = dict(scene)
        updated["from"] = start
        updated["to"] = end
        updated.update(_scene_caption_annotation(captions, start, end))
        retimed.append(updated)

    return retimed, {
        "scene_timing": "caption_boundaries",
        "reason": "scene cuts snapped to exact caption end boundaries so visual changes follow semantic units",
        "minimum_scene_seconds": minimum_scene_seconds,
        "opening_target_seconds": opening_target_seconds,
        "caption_boundaries_used": True,
    }


def stage_remotion(
    config: dict[str, Any], series: dict[str, Any], *, projects_dir: Path = PROJECTS_DIR,
    used_music_paths: list[str] | None = None,
) -> dict[str, Any]:
    target = episode_dir(config, projects_dir)
    public_root = remotion_public_dir(config)
    if public_root.exists():
        shutil.rmtree(public_root)
    public_root.mkdir(parents=True, exist_ok=True)
    music_runtime = series.get("music", {})
    usage_ledger_path = (
        projects_dir / ".treeelf-music-usage-ledger.json"
        if projects_dir.resolve() != PROJECTS_DIR.resolve()
        else Path(str(music_runtime.get("usage_ledger_path", DEFAULT_USAGE_LEDGER_PATH))).expanduser()
    )
    music_selection = select_music_source(
        config, series, used_music_paths=used_music_paths, usage_ledger_path=usage_ledger_path
    )
    music_source = Path(music_selection["path"]).expanduser() if music_selection["path"] else Path("")
    if music_source.is_file():
        normalize_cfg = music_runtime.get("normalization", {})
        normalization = normalize_background_music(
            music_source,
            target / "assets" / "audio" / "background.mp3",
            target_lufs=float(normalize_cfg.get("target_lufs", -18.0)),
            true_peak_dbfs=float(normalize_cfg.get("true_peak_dbfs", -2.0)),
            loudness_range_lu=float(normalize_cfg.get("loudness_range_lu", 7.0)),
        )
        usage = record_music_usage(
            music_selection,
            project_id=config["project_id"],
            series="zh-philosophy-video",
            ledger_path=usage_ledger_path,
        )
    else:
        raise FileNotFoundError(f"zh-philosophy-video requires background music; no usable music source found for {config['project_id']}")
    dump_json(
        target / "artifacts" / "music_selection.json",
        {
            "version": "2.0",
            "project_id": config["project_id"],
            "selected": music_selection,
            "normalization": normalization,
            "usage_record": usage,
            "selected_at": utc_now(),
            "policy": "Shared catalog match with cross-series usage history; normalize only the project derivative and preserve the central source.",
        },
    )
    captions = config["edit"].get("captions", [])
    captions_path = config["edit"].get("captions_path")
    if not captions_path:
        default_captions = target / "artifacts" / "exact_captions.json"
        captions_path = str(default_captions) if default_captions.is_file() else ""
    if captions_path:
        payload = load_json(Path(captions_path))
        captions = [
            {"start": item["start"], "end": item["end"], "text": str(item["text"]).strip()}
            for item in payload.get("segments", [])
            if str(item.get("text", "")).strip()
        ]
    scenes = [dict(scene) for scene in config["edit"].get("scenes", [])]
    info_cards = [dict(card) for card in config["edit"].get("info_cards", [])]
    narration_rel = config["edit"].get("narration_src", "audio/narration.wav")
    narration_source = target / "assets" / narration_rel
    narration_duration = media_duration_seconds(narration_source) if narration_source.is_file() else None
    duration_candidates = [
        float(config.get("duration_seconds", 80)),
        max((float(caption["end"]) for caption in captions), default=0.0),
        max((float(scene.get("to", 0)) for scene in scenes), default=0.0),
        max((float(card.get("to", 0)) for card in info_cards), default=0.0),
    ]
    if narration_duration:
        duration_candidates.append(float(narration_duration))
    # Keep a short visual/audio tail so the final syllable, caption, and music fade are not clipped.
    dynamic_duration = round(max(duration_candidates) + 0.8, 2)
    scenes, timeline_policy = timeline.retime_scenes_to_caption_boundaries(scenes, captions, dynamic_duration)
    if scenes and timeline_policy["scene_timing"] == "config_placeholders":
        last_scene = max(scenes, key=lambda scene: float(scene.get("to", 0)))
        if float(last_scene.get("to", 0)) < dynamic_duration:
            last_scene["to"] = dynamic_duration
    if timeline_policy["scene_timing"] == "caption_boundaries":
        video_jobs, wan_policy = timeline.resolve_wan_generation_plan(config, scenes)
        scenes = timeline.apply_wan_scene_policy(config, scenes, video_jobs)
    else:
        video_jobs = [dict(item) for item in config["article_visual_assets"].get("videos", [])]
        wan_policy = {
            "enabled": False,
            "reason": "exact captions unavailable; preserving reviewed episode video references",
        }
    mappings = {
        target / "assets" / "images" / "article": public_root / "images",
        target / "assets" / "video" / "article": public_root / "video",
        target / "assets" / "audio": public_root / "audio",
    }
    staged = {"hardlink": 0, "copy": 0}
    media_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".mp3", ".wav", ".m4a"}
    for source_dir, output_dir in mappings.items():
        output_dir.mkdir(parents=True, exist_ok=True)
        for source in source_dir.glob("*"):
            if source.is_file() and source.suffix.lower() in media_suffixes:
                mode = _atomic_link_or_copy(source, output_dir / source.name)
                staged[mode] += 1

    props = {
        "assetRoot": config["project_id"],
        "brand": "树精灵",
        "durationSeconds": dynamic_duration,
        "cover": {
            "src": "images/C01.png",
            "title": config["cover_title"],
            "englishTitle": config.get("cover_english_title", ""),
        },
        "scenes": scenes,
        "infoCards": info_cards,
        "captions": captions,
        "narrationSrc": narration_rel,
        "musicSrc": config["edit"].get("music_src", "audio/background.mp3"),
        "musicVolume": series["music"]["remotion_volume"],
        "captionStyle": series["caption"],
        "timelinePolicy": timeline_policy,
        "wanPolicy": wan_policy,
    }
    props_path = target / "artifacts" / "remotion_props.json"
    dump_json(props_path, props)
    return {
        "public_dir": str(public_root),
        "props": str(props_path),
        "staged": staged,
        "music_selection": str(target / "artifacts" / "music_selection.json"),
    }


def _write_completion_frontmatter(path: Path, fields: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError(f"Missing YAML frontmatter: {path}")
    frontmatter, body = text[4:].split("\n---\n", 1)
    lines = frontmatter.splitlines()
    for key, value in fields.items():
        replacement = f"{key}: {json.dumps(value, ensure_ascii=False)}"
        index = next((i for i, line in enumerate(lines) if line.startswith(f"{key}:")), None)
        if index is None:
            lines.append(replacement)
        else:
            lines[index] = replacement
    updated = "---\n" + "\n".join(lines) + "\n---\n" + body
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(updated, encoding="utf-8")
    temporary.replace(path)


def deliver(
    config: dict[str, Any], render: Path, *, projects_dir: Path = PROJECTS_DIR,
    series: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not render.is_file() or (media_duration_seconds(render) or 0) < 10:
        raise ValueError(f"Render is missing or not a playable final video: {render}")
    target = episode_dir(config, projects_dir)
    source = Path(config["source_script_md"])
    project = load_json(target / "project.json")
    if sha256_file(source) != project["source_sha256"]:
        raise ValueError("Source changed after prepare; review the revision before delivery")

    delivery_dir = Path(config.get("final_output_dir", "/Users/treeelf/Movies/zh-philosophy-video"))
    delivery_dir.mkdir(parents=True, exist_ok=True)
    output = _delivery_output_path(config, render, delivery_dir)
    delivery_mode = _atomic_link_or_copy(render, output)
    if sha256_file(render) != sha256_file(output):
        raise ValueError("Project/Movies SHA-256 verification failed")
    generated = utc_now()
    _write_completion_frontmatter(
        source,
        {
            "production_status": "completed",
            "video_project_id": config["project_id"],
            "video_output": str(output),
            "video_generated": generated,
        },
    )
    result = {
        "status": "delivered_and_source_marked_completed",
        "output": str(output),
        "sha256": sha256_file(output),
        "duration_seconds": media_duration_seconds(output),
        "source": str(source),
        "completed_at": generated,
        "delivery_mode": delivery_mode,
        "delivery_filename_policy": "Chinese-readable title, optional YYYY-MM-DD prefix from project_id, collision-safe _vN suffix",
    }
    dump_json(target / "artifacts" / "delivery_report.json", result)
    cleanup = cleanup_local_storage(
        config,
        series or load_json(DEFAULT_SERIES_CONFIG),
        projects_dir=projects_dir,
        dry_run=False,
        yes=True,
        include_delayed=False,
    )
    result["immediate_cleanup"] = {
        "deleted": len(cleanup["deleted"]),
        "bytes_reclaimed": cleanup["bytes_reclaimable"],
        "report": str(target / "artifacts" / "local_storage_cleanup_report.json"),
    }
    dump_json(target / "artifacts" / "delivery_report.json", result)
    _mark_batch_episode_delivered(config, projects_dir=projects_dir)
    return result


def _mark_batch_episode_delivered(
    config: dict[str, Any], *, projects_dir: Path = PROJECTS_DIR
) -> None:
    for manifest_path in projects_dir.glob("*/artifacts/batch_manifest.json"):
        try:
            manifest = load_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        changed = False
        for episode in manifest.get("episodes", []):
            if episode.get("project_id") == config.get("project_id"):
                episode["status"] = "delivered"
                episode["delivered_at"] = utc_now()
                changed = True
        if changed:
            if manifest.get("episodes") and all(
                episode.get("status") == "delivered" for episode in manifest["episodes"]
            ):
                manifest["status"] = "delivered"
                manifest["all_episodes_delivered_at"] = utc_now()
                manifest["next_action"] = "retain remote-final-backup for grace period, then dry-run local batch cleanup"
            dump_json(manifest_path, manifest)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reusable TreeElf philosophy episode workflow")
    parser.add_argument("command", choices=("validate", "scan", "prepare", "preflight", "generate-narration", "generate-gpu", "build-captions", "stage-remotion", "deliver", "cleanup-local", "status"))
    parser.add_argument("--config", type=Path, default=DEFAULT_EPISODE_CONFIG)
    parser.add_argument("--series", type=Path, default=DEFAULT_SERIES_CONFIG)
    parser.add_argument("--render", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--include-delayed", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_json(args.config)
    series = load_json(args.series)
    if args.command == "validate":
        result: Any = {"valid": not validate_episode(config, series), "errors": validate_episode(config, series)}
    elif args.command == "scan":
        result = scan_inbox()
    elif args.command == "prepare":
        result = prepare_episode(config, series)
    elif args.command == "preflight":
        report = episode_dir(config) / "artifacts" / "gpu_usage_report.json"
        ensure_gpu_preflight(report)
        result = {"status": "gpu_preflight_passed", "report": str(report)}
    elif args.command == "generate-narration":
        result = generate_narration(config, series)
    elif args.command == "generate-gpu":
        result = generate_gpu(config, series)
    elif args.command == "build-captions":
        result = build_exact_captions(config)
    elif args.command == "stage-remotion":
        result = stage_remotion(config, series)
    elif args.command == "deliver":
        if args.render is None:
            raise SystemExit("deliver requires --render")
        result = deliver(config, args.render, series=series)
    elif args.command == "cleanup-local":
        if not args.dry_run and not args.yes:
            raise SystemExit("cleanup-local requires --dry-run or --yes")
        result = cleanup_local_storage(
            config,
            series,
            dry_run=args.dry_run,
            yes=args.yes,
            include_delayed=args.include_delayed,
        )
    else:
        target = episode_dir(config)
        result = {
            "project_dir": str(target),
            "prepared": (target / "project.json").is_file(),
            "narration": (target / "assets" / "audio" / "narration.wav").is_file(),
            "visual_manifest": (target / "artifacts" / "article_visual_manifest.json").is_file(),
            "visual_brief": (target / "artifacts" / "visual_brief.json").is_file(),
            "music_selection": (target / "artifacts" / "music_selection.json").is_file(),
            "remotion_props": (target / "artifacts" / "remotion_props.json").is_file(),
            "delivery_report": (target / "artifacts" / "delivery_report.json").is_file(),
            "local_cleanup_report": (target / "artifacts" / "local_storage_cleanup_report.json").is_file(),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
