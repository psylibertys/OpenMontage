"""Shared TreeElf music catalog, selection, usage, and normalization helpers."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import random
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from lib.env_loader import load_env


REPO_ROOT = Path(__file__).resolve().parents[1]
load_env(REPO_ROOT)
DEFAULT_LIBRARY_DIR = Path(
    os.environ.get(
        "TREEELF_MUSIC_LIBRARY_DIR",
        str(REPO_ROOT / "music_library"),
    )
).expanduser()
DEFAULT_CATALOG_DIR = REPO_ROOT / "workflow_configs" / "treeelf-music"
DEFAULT_CATALOG_PATH = DEFAULT_CATALOG_DIR / "catalog-v1.json"
DEFAULT_OVERRIDES_PATH = DEFAULT_CATALOG_DIR / "manual-overrides-v1.json"
DEFAULT_USAGE_LEDGER_PATH = DEFAULT_CATALOG_DIR / "usage-ledger-v1.json"
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aiff", ".aif"}
GENERIC_QUALIFICATION_KEYWORDS = {"纯音乐", "instrumental"}


def configured_music_library_dir() -> Path:
    """Resolve the movable TreeElf music root from the project environment."""

    return Path(os.environ.get("TREEELF_MUSIC_LIBRARY_DIR", str(DEFAULT_LIBRARY_DIR))).expanduser()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def list_audio_files(library_dir: Path) -> list[Path]:
    if not library_dir.is_dir():
        return []
    return sorted(
        (path for path in library_dir.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS),
        key=lambda path: path.as_posix().lower(),
    )


def _library_source_rows(library_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in list_audio_files(library_dir):
        stat = path.stat()
        rows.append(
            {
                "relative_path": path.relative_to(library_dir).as_posix(),
                "size_bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
    return rows


def _source_fingerprint(rows: list[dict[str, Any]]) -> str:
    stable = [
        {
            "relative_path": row["relative_path"],
            "size_bytes": int(row["size_bytes"]),
            "mtime_ns": int(row["mtime_ns"]),
        }
        for row in rows
    ]
    return hashlib.sha256(
        json.dumps(stable, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


_TAG_TERMS: dict[str, tuple[str, ...]] = {
    "ambient": ("ambient", "氛围"),
    "piano": ("piano", "钢琴"),
    "lo-fi": ("lo-fi", "lofi"),
    "downtempo": ("downtempo", "慢拍"),
    "chillwave": ("chillwave",),
    "soundtrack": ("soundtrack", "配乐", "电影感"),
    "neo-classical": ("neo-classical", "neo classical", "新古典"),
    "classical": ("classical", "古典"),
    "jazz": ("jazz", "爵士"),
    "fusion": ("fusion", "融合"),
    "bossa": ("bossa", "波萨"),
    "post-rock": ("post-rock", "post rock", "后摇"),
    "reggae": ("reggae", "雷鬼"),
    "electronic": ("electronic", "电子"),
    "metal": ("metal", "金属"),
    "hardcore": ("hardcore", "硬核"),
    "drum-and-bass": ("drum and bass", "dnb"),
    "war-drums": ("war drums", "战争鼓"),
    "gregorian": ("gregorian", "格里高利"),
    "chinese-traditional": ("chinese traditional", "中国传统", "古筝"),
    "instrumental": ("instrumental", "纯音乐", "轻音乐"),
    "warm": ("warm", "温暖", "暖"),
    "dreamy": ("dreamy", "梦幻"),
    "calm": ("calm", "calming", "冷静", "平静", "舒缓", "冥想"),
    "hopeful": ("hopeful", "uplifting", "希望", "自信", "明亮"),
    "melancholy": ("melancholy", "somber", "忧郁", "悲伤"),
    "playful": ("playful", "轻盈", "俏皮", "有趣"),
    "cinematic": ("cinematic", "史诗", "赞歌感"),
}


def infer_filename_metadata(filename: str) -> tuple[list[str], list[str]]:
    name = filename.lower()
    tags = sorted(tag for tag, terms in _TAG_TERMS.items() if any(term in name for term in terms))
    risks: list[str] = []
    risk_rules = {
        "lyrics": ("有歌词", "with lyrics", "歌词版"),
        "watermark": ("watermark", "水印"),
        "vocal_slice": ("人声切片", "vocal slice", "vocal chop"),
        "male_voice": ("男声", "male voice", "male vocal"),
        "female_voice": ("女声", "female voice", "female vocal"),
        "rap": ("说唱", " rap ", "-rap-"),
        "chant": ("gregorian", "chant", "吟唱", "合唱"),
        "high_energy": ("metal", "hardcore", "war drums", "drum and bass", "战争鼓"),
    }
    padded = f" {name} "
    for risk, terms in risk_rules.items():
        if any(term in padded for term in terms):
            risks.append(risk)
    return tags, sorted(risks)


def probe_audio(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels:format=duration,format_name,bit_rate",
        "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        payload = json.loads(result.stdout)
        stream = (payload.get("streams") or [{}])[0]
        fmt = payload.get("format") or {}
        return {
            "duration_seconds": round(float(fmt["duration"]), 3) if fmt.get("duration") else None,
            "format": fmt.get("format_name"),
            "codec": stream.get("codec_name"),
            "sample_rate": int(stream["sample_rate"]) if stream.get("sample_rate") else None,
            "channels": int(stream["channels"]) if stream.get("channels") else None,
            "bit_rate": int(fmt["bit_rate"]) if fmt.get("bit_rate") else None,
            "probe_error": None,
        }
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
        return {
            "duration_seconds": None, "format": None, "codec": None,
            "sample_rate": None, "channels": None, "bit_rate": None,
            "probe_error": str(exc),
        }


def _extract_loudnorm_json(stderr: str) -> dict[str, Any] | None:
    matches = re.findall(r"\{\s*\"input_i\".*?\}", stderr, flags=re.DOTALL)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def measure_loudness(path: Path) -> dict[str, Any]:
    command = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-af", "loudnorm=I=-18:TP=-2:LRA=7:print_format=json", "-f", "null", "-",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
        metrics = _extract_loudnorm_json(result.stderr)
        if not metrics:
            raise ValueError("ffmpeg loudnorm metrics missing")
        return {
            "integrated_lufs": float(metrics["input_i"]),
            "true_peak_dbfs": float(metrics["input_tp"]),
            "loudness_range_lu": float(metrics["input_lra"]),
            "loudness_error": None,
        }
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {
            "integrated_lufs": None, "true_peak_dbfs": None,
            "loudness_range_lu": None, "loudness_error": str(exc),
        }


def build_catalog(
    library_dir: Path = DEFAULT_LIBRARY_DIR,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    *,
    analyze_loudness: bool = True,
) -> dict[str, Any]:
    library_dir = library_dir.expanduser().resolve()
    previous = load_json(catalog_path, {}) or {}
    previous_by_sha = {row.get("sha256"): row for row in previous.get("tracks", []) if row.get("sha256")}
    previous_sources = {
        row.get("relative_path"): row
        for row in previous.get("source_files", [])
        if row.get("relative_path") and row.get("sha256")
    }
    source_rows = _library_source_rows(library_dir)
    grouped: dict[str, list[Path]] = {}
    source_files: list[dict[str, Any]] = []
    for source_row in source_rows:
        path = library_dir / source_row["relative_path"]
        old_source = previous_sources.get(source_row["relative_path"], {})
        if (
            old_source.get("size_bytes") == source_row["size_bytes"]
            and old_source.get("mtime_ns") == source_row["mtime_ns"]
            and old_source.get("sha256")
        ):
            digest = str(old_source["sha256"])
        else:
            digest = sha256_file(path)
        source_files.append({**source_row, "sha256": digest})
        grouped.setdefault(digest, []).append(path)

    tracks: list[dict[str, Any]] = []
    for digest, paths in sorted(grouped.items(), key=lambda item: item[1][0].as_posix().lower()):
        canonical = paths[0]
        old = previous_by_sha.get(digest, {})
        probe = {
            key: old.get(key)
            for key in ("duration_seconds", "format", "codec", "sample_rate", "channels", "bit_rate", "probe_error")
        }
        if not old or old.get("size_bytes") != canonical.stat().st_size or not probe.get("duration_seconds"):
            probe = probe_audio(canonical)
        loudness = {
            key: old.get(key)
            for key in ("integrated_lufs", "true_peak_dbfs", "loudness_range_lu", "loudness_error")
        }
        if analyze_loudness and (not old or loudness.get("integrated_lufs") is None):
            loudness = measure_loudness(canonical) if probe.get("duration_seconds") else {
                "integrated_lufs": None, "true_peak_dbfs": None,
                "loudness_range_lu": None, "loudness_error": "audio probe failed",
            }
        tags, risks = infer_filename_metadata(canonical.name)
        if probe.get("probe_error"):
            risks = sorted(set(risks + ["corrupt_or_unreadable"]))
        excluded = bool({"lyrics", "watermark", "corrupt_or_unreadable"}.intersection(risks))
        row = {
            "id": f"sha256:{digest}",
            "sha256": digest,
            "relative_path": canonical.relative_to(library_dir).as_posix(),
            "aliases": [path.relative_to(library_dir).as_posix() for path in paths[1:]],
            "filename": canonical.name,
            "size_bytes": canonical.stat().st_size,
            "suffix": canonical.suffix.lower(),
            **probe,
            **loudness,
            "tags": tags,
            "risk_flags": risks,
            "selection_status": "excluded" if excluded else "eligible",
            "rights_status": "user_supplied_unverified",
        }
        tracks.append(row)

    payload = {
        "schema_version": "1.0",
        "library_root": str(library_dir),
        "generated_at": utc_now(),
        "source_fingerprint": _source_fingerprint(source_rows),
        "source_files": source_files,
        "file_count": sum(1 + len(row["aliases"]) for row in tracks),
        "track_count": len(tracks),
        "duplicate_file_count": sum(len(row["aliases"]) for row in tracks),
        "total_bytes": sum(row["size_bytes"] for row in tracks),
        "tracks": tracks,
    }
    atomic_dump_json(catalog_path, payload)
    return payload


def ensure_catalog_fresh(
    library_dir: Path,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    *,
    analyze_loudness: bool = True,
) -> dict[str, Any]:
    """Incrementally rebuild a stale catalog under a cross-process lock."""

    library_dir = library_dir.expanduser().resolve()
    if not library_dir.is_dir():
        return {
            "status": "library_missing",
            "library_root": str(library_dir),
            "catalog_path": str(catalog_path),
        }
    lock_path = catalog_path.with_suffix(catalog_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        current_rows = _library_source_rows(library_dir)
        current_fingerprint = _source_fingerprint(current_rows)
        catalog = load_json(catalog_path, {}) or {}
        catalog_root = str(catalog.get("library_root", ""))
        if (
            catalog.get("tracks")
            and catalog_root
            and catalog_root != str(library_dir)
            and catalog.get("source_fingerprint") != current_fingerprint
        ):
            return {
                "status": "root_mismatch_transient_scan",
                "library_root": str(library_dir),
                "catalog_library_root": catalog_root,
                "catalog_path": str(catalog_path),
            }
        if catalog.get("source_fingerprint") != current_fingerprint:
            rebuilt = build_catalog(
                library_dir,
                catalog_path,
                analyze_loudness=analyze_loudness,
            )
            return {
                "status": "rebuilt",
                "library_root": str(library_dir),
                "catalog_path": str(catalog_path),
                "file_count": rebuilt["file_count"],
                "track_count": rebuilt["track_count"],
            }
        if catalog.get("library_root") != str(library_dir):
            catalog["library_root"] = str(library_dir)
            catalog["relocated_at"] = utc_now()
            atomic_dump_json(catalog_path, catalog)
            return {
                "status": "root_relocated",
                "library_root": str(library_dir),
                "catalog_path": str(catalog_path),
            }
        return {
            "status": "fresh",
            "library_root": str(library_dir),
            "catalog_path": str(catalog_path),
            "file_count": catalog.get("file_count", 0),
            "track_count": catalog.get("track_count", 0),
        }


def _manual_overrides(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path, {}) or {}
    return payload.get("tracks", {}) if isinstance(payload, dict) else {}


def _usage_events(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path, {}) or {}
    return payload.get("events", []) if isinstance(payload, dict) else []


def _catalog_candidates(
    roots: Iterable[Path],
    *,
    catalog_path: Path,
    overrides_path: Path,
    use_catalog: bool = True,
) -> list[dict[str, Any]]:
    roots = [root.expanduser().resolve() for root in roots if root]
    catalog = load_json(catalog_path, {}) or {}
    overrides = _manual_overrides(overrides_path)
    rows: list[dict[str, Any]] = []
    catalog_root_raw = catalog.get("library_root")
    catalog_root = Path(catalog_root_raw).expanduser().resolve() if catalog_root_raw else None
    catalog_relatives = [str(row.get("relative_path", "")) for row in catalog.get("tracks", [])]
    selected_root = next(
        (
            root
            for root in roots
            if root.is_dir()
            and (
                catalog_root is None
                or root == catalog_root
                or any(relative and (root / relative).is_file() for relative in catalog_relatives[:10])
            )
        ),
        None,
    )
    if use_catalog and selected_root and catalog.get("tracks"):
        for source in catalog["tracks"]:
            row = dict(source)
            override = overrides.get(row["id"], {})
            row["tags"] = sorted(set(row.get("tags", []) + list(override.get("add_tags", []))))
            row["risk_flags"] = sorted(set(row.get("risk_flags", []) + list(override.get("add_risk_flags", []))))
            row["manual_rating"] = override.get("rating")
            row["manual_notes"] = override.get("notes", "")
            row["rights_status"] = override.get("rights_status", row.get("rights_status", "user_supplied_unverified"))
            if override.get("enabled") is False:
                row["selection_status"] = "excluded"
            path = selected_root / row["relative_path"]
            row["path"] = str(path)
            row["available"] = path.is_file()
            rows.append(row)
        return rows

    seen: set[str] = set()
    for root in roots:
        for path in list_audio_files(root):
            digest = sha256_file(path)
            if digest in seen:
                continue
            seen.add(digest)
            tags, risks = infer_filename_metadata(path.name)
            rows.append({
                "id": f"sha256:{digest}", "sha256": digest, "path": str(path),
                "relative_path": path.relative_to(root).as_posix(), "filename": path.name,
                "size_bytes": path.stat().st_size, "duration_seconds": None,
                "integrated_lufs": None, "true_peak_dbfs": None,
                "tags": tags, "risk_flags": risks,
                "selection_status": "excluded" if {"lyrics", "watermark"}.intersection(risks) else "eligible",
                "rights_status": "user_supplied_unverified", "available": True,
            })
    return rows


def catalog_tracks_for_library(
    library_dir: Path,
    *,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    overrides_path: Path = DEFAULT_OVERRIDES_PATH,
) -> list[dict[str, Any]]:
    """Return catalog-enriched tracks, falling back to a transient scan."""

    return _catalog_candidates(
        [library_dir], catalog_path=catalog_path, overrides_path=overrides_path
    )


def _stable_jitter(project_id: str, track_id: str) -> float:
    seed = int(hashlib.sha256(f"{project_id}|{track_id}".encode("utf-8")).hexdigest()[:12], 16)
    return random.Random(seed).random()


def select_music_track(
    *,
    project_id: str,
    series: str,
    keywords: list[str],
    library_dirs: list[Path],
    fallback_source: Path | None = None,
    used_music_paths: list[str] | None = None,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    overrides_path: Path = DEFAULT_OVERRIDES_PATH,
    usage_ledger_path: Path = DEFAULT_USAGE_LEDGER_PATH,
    preferred_track_id: str | None = None,
) -> dict[str, Any]:
    primary_root = next(
        (root.expanduser() for root in library_dirs if root and root.expanduser().is_dir()),
        None,
    )
    catalog_refresh = (
        ensure_catalog_fresh(primary_root, catalog_path)
        if primary_root is not None
        else {"status": "no_library_root"}
    )
    candidates = _catalog_candidates(
        library_dirs,
        catalog_path=catalog_path,
        overrides_path=overrides_path,
        use_catalog=catalog_refresh.get("status") != "root_mismatch_transient_scan",
    )
    fallback = fallback_source.expanduser().resolve() if fallback_source and fallback_source.is_file() else None
    if fallback and all(Path(row["path"]).resolve() != fallback for row in candidates):
        digest = sha256_file(fallback)
        tags, risks = infer_filename_metadata(fallback.name)
        candidates.append({
            "id": f"sha256:{digest}", "sha256": digest, "path": str(fallback),
            "filename": fallback.name, "tags": tags, "risk_flags": risks,
            "selection_status": "excluded" if {"lyrics", "watermark"}.intersection(risks) else "eligible",
            "rights_status": "user_supplied_unverified", "available": True,
            "duration_seconds": None, "integrated_lufs": None, "true_peak_dbfs": None,
        })
    used = {str(Path(value).expanduser().resolve()) for value in (used_music_paths or [])}
    all_events = _usage_events(usage_ledger_path)
    events = [
        row
        for row in all_events
        if row.get("status", "committed") in {"reserved", "committed"}
    ]
    # A track that already failed for this exact project must not be selected
    # again by deterministic ranking. Failed tracks remain eligible for other
    # projects, so one source-specific normalization problem does not poison
    # the shared library.
    failed_for_project = {
        str(row.get("track_id", ""))
        for row in all_events
        if row.get("project_id") == project_id
        and row.get("series") == series
        and row.get("status") == "failed"
    }
    usage_counts: dict[str, int] = {}
    recent_ids = [str(row.get("track_id", "")) for row in events[-24:]]
    for event in events:
        track_id = str(event.get("track_id", ""))
        usage_counts[track_id] = usage_counts.get(track_id, 0) + 1

    requested = list(dict.fromkeys(str(value).strip().lower() for value in keywords if str(value).strip()))
    semantic_keywords = [
        keyword for keyword in requested if keyword not in GENERIC_QUALIFICATION_KEYWORDS
    ]
    ignored_generic_keywords = [
        keyword for keyword in requested if keyword in GENERIC_QUALIFICATION_KEYWORDS
    ]
    scored: list[dict[str, Any]] = []
    for row in candidates:
        path = Path(row["path"])
        if row.get("id") in failed_for_project:
            continue
        if row.get("selection_status") != "eligible" or not row.get("available", path.is_file()) or not path.is_file():
            continue
        haystack = " ".join([row.get("filename", ""), *row.get("tags", [])]).lower()
        matched = [keyword for keyword in semantic_keywords if keyword in haystack]
        score = float(len(matched) * 10 + 1)
        tags = set(row.get("tags", []))
        risks = set(row.get("risk_flags", []))
        if "instrumental" in tags:
            score += 7
        if tags.intersection({"ambient", "piano", "lo-fi", "downtempo", "chillwave", "soundtrack", "neo-classical"}):
            score += 3
        risk_penalties = {
            "vocal_slice": 5, "male_voice": 5, "female_voice": 5,
            "rap": 8, "chant": 5, "high_energy": 4,
        }
        risk_penalty = sum(risk_penalties.get(flag, 0) for flag in risks)
        score -= risk_penalty
        if fallback and path.resolve() == fallback:
            score += 1
        same_batch_penalty = 12 if str(path.resolve()) in used else 0
        score -= same_batch_penalty
        use_count = usage_counts.get(row["id"], 0)
        history_penalty = min(12, use_count * 2) + (6 if row["id"] in recent_ids else 0)
        score -= history_penalty
        if row.get("manual_rating") is not None:
            score += float(row["manual_rating"]) * 2
        score += _stable_jitter(project_id, row["id"])
        scored.append({
            "track_id": row["id"], "path": str(path), "source_sha256": row["sha256"],
            "relative_path": row.get("relative_path"),
            "score": round(score, 6), "matched_keywords": matched,
            "risk_flags": sorted(risks), "risk_penalty": risk_penalty,
            "same_batch_penalty": same_batch_penalty, "history_penalty": history_penalty,
            "historical_use_count": use_count, "rights_status": row.get("rights_status"),
            "integrated_lufs": row.get("integrated_lufs"), "true_peak_dbfs": row.get("true_peak_dbfs"),
            "duration_seconds": row.get("duration_seconds"),
        })
    scored.sort(key=lambda row: (-row["score"], row["path"]))
    if not scored:
        return {
            "mode": "no_music_source_found", "path": "", "track_id": "", "source_sha256": "",
            "requested_keywords": requested, "candidate_count": len(candidates), "top_candidates": [],
            "fallback_reason": "no eligible and available track",
            "semantic_keywords": semantic_keywords,
            "ignored_generic_keywords": ignored_generic_keywords,
            "catalog_refresh": catalog_refresh,
        }
    preferred = next(
        (row for row in scored if row["track_id"] == preferred_track_id),
        None,
    )
    has_content_match = any(row["matched_keywords"] for row in scored)
    selected = preferred or scored[0]
    return {
        "mode": (
            "existing_project_reuse"
            if preferred
            else "content_based_catalog_match"
            if has_content_match
            else "weighted_deterministic_fallback"
        ),
        **selected,
        "requested_keywords": requested,
        "semantic_keywords": semantic_keywords,
        "ignored_generic_keywords": ignored_generic_keywords,
        "candidate_count": len(candidates),
        "eligible_candidate_count": len(scored),
        "used_music_paths_penalized": sorted(used),
        "fallback_reason": None if has_content_match else "no candidate matched requested keywords",
        "diversity_policy": "Shared cross-series history penalty, same-batch penalty, and deterministic project-specific tie breaking.",
        "catalog_path": str(catalog_path),
        "catalog_refresh": catalog_refresh,
        "usage_ledger_path": str(usage_ledger_path),
        "series": series,
        "failed_project_tracks_excluded": sorted(failed_for_project),
        "top_candidates": scored[:5],
    }


def record_music_usage(
    selection: dict[str, Any],
    *,
    project_id: str,
    series: str,
    ledger_path: Path = DEFAULT_USAGE_LEDGER_PATH,
) -> dict[str, Any]:
    track_id = str(selection.get("track_id", ""))
    if not track_id:
        return {"recorded": False, "reason": "selection has no track_id"}
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger_path.with_suffix(ledger_path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        payload = load_json(ledger_path, {}) or {"schema_version": "1.0", "events": []}
        events = payload.setdefault("events", [])
        existing = next(
            (row for row in events if row.get("project_id") == project_id and row.get("series") == series and row.get("track_id") == track_id),
            None,
        )
        if existing:
            return {"recorded": False, "reason": "usage already recorded", "event": existing}
        event = {
            "event_id": hashlib.sha256(f"{series}|{project_id}|{track_id}".encode("utf-8")).hexdigest()[:20],
            "selected_at": utc_now(), "series": series, "project_id": project_id,
            "track_id": track_id, "source_sha256": selection.get("source_sha256"),
            "relative_or_absolute_path": selection.get("path"), "selection_mode": selection.get("mode"),
            "status": "committed",
            "committed_at": utc_now(),
            "selection": selection,
        }
        events.append(event)
        payload["updated_at"] = event["selected_at"]
        atomic_dump_json(ledger_path, payload)
        return {"recorded": True, "event": event}


def select_and_record_music_usage(
    selection_factory: Callable[[str | None], dict[str, Any]],
    *,
    project_id: str,
    series: str,
    ledger_path: Path = DEFAULT_USAGE_LEDGER_PATH,
    force_reselect: bool = False,
    reservation_ttl_hours: float = 168.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Atomically select against history and reserve the chosen track.

    The lock covers only catalog ranking and the small ledger write. Audio
    normalization happens after this function returns, outside the lock.
    """

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger_path.with_suffix(ledger_path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        payload = load_json(ledger_path, {}) or {"schema_version": "1.0", "events": []}
        events = payload.setdefault("events", [])
        now = datetime.now(timezone.utc)
        expired = False
        for event in events:
            if event.get("status") != "reserved":
                continue
            reserved_at = event.get("reserved_at") or event.get("selected_at")
            try:
                reserved_time = datetime.fromisoformat(str(reserved_at))
                if reserved_time.tzinfo is None:
                    reserved_time = reserved_time.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
            age_hours = (now - reserved_time.astimezone(timezone.utc)).total_seconds() / 3600
            if age_hours > reservation_ttl_hours:
                event["status"] = "failed"
                event["failed_at"] = utc_now()
                event["failure_reason"] = "reservation_expired"
                expired = True
        if expired:
            payload["updated_at"] = utc_now()
            atomic_dump_json(ledger_path, payload)
        existing = next(
            (
                row
                for row in reversed(events)
                if row.get("project_id") == project_id
                and row.get("series") == series
                and row.get("status", "committed") in {"reserved", "committed"}
            ),
            None,
        )
        if existing and force_reselect:
            existing["status"] = "failed"
            existing["failed_at"] = utc_now()
            existing["failure_reason"] = "explicit_reselection"
            existing = None
        preferred_track_id = str(existing.get("track_id")) if existing else None
        selection = selection_factory(preferred_track_id)
        if existing and selection.get("track_id") == preferred_track_id:
            return selection, {
                "recorded": False,
                "reason": "existing project music reused",
                "event": existing,
            }
        if existing:
            existing["status"] = "failed"
            existing["failed_at"] = utc_now()
            existing["failure_reason"] = "previous selected track is no longer available"
        track_id = str(selection.get("track_id", ""))
        if not track_id:
            atomic_dump_json(ledger_path, payload)
            return selection, {"recorded": False, "reason": "selection has no track_id"}
        event = {
            "event_id": hashlib.sha256(f"{series}|{project_id}|{track_id}".encode("utf-8")).hexdigest()[:20],
            "selected_at": utc_now(), "reserved_at": utc_now(),
            "series": series, "project_id": project_id,
            "track_id": track_id, "source_sha256": selection.get("source_sha256"),
            "relative_or_absolute_path": selection.get("path"), "selection_mode": selection.get("mode"),
            "status": "reserved",
            "selection": selection,
        }
        events.append(event)
        payload["updated_at"] = event["selected_at"]
        atomic_dump_json(ledger_path, payload)
        return selection, {"recorded": True, "event": event}


def transition_music_usage(
    *,
    project_id: str,
    series: str,
    status: str,
    ledger_path: Path = DEFAULT_USAGE_LEDGER_PATH,
    reason: str | None = None,
) -> dict[str, Any]:
    if status not in {"committed", "failed"}:
        raise ValueError("Music usage status must be committed or failed")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger_path.with_suffix(ledger_path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        payload = load_json(ledger_path, {}) or {"schema_version": "1.0", "events": []}
        event = next(
            (
                row
                for row in reversed(payload.setdefault("events", []))
                if row.get("project_id") == project_id
                and row.get("series") == series
                and row.get("status", "committed") in {"reserved", "committed"}
            ),
            None,
        )
        if not event:
            return {"updated": False, "reason": "active reservation not found"}
        if status == "committed" and event.get("status", "committed") == "committed":
            return {"updated": False, "reason": "already committed", "event": event}
        event["status"] = status
        event[f"{status}_at"] = utc_now()
        if reason:
            event["failure_reason" if status == "failed" else "commit_note"] = reason
        payload["updated_at"] = utc_now()
        atomic_dump_json(ledger_path, payload)
        return {"updated": True, "event": event}


def normalize_background_music(
    source: Path,
    target: Path,
    *,
    target_lufs: float = -18.0,
    true_peak_dbfs: float = -2.0,
    loudness_range_lu: float = 7.0,
    tolerance_lu: float = 1.0,
) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".normalized.tmp.mp3")
    command = [
        "ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(source),
        "-af", f"loudnorm=I={target_lufs}:TP={true_peak_dbfs}:LRA={loudness_range_lu}:print_format=json",
        "-codec:a", "libmp3lame", "-b:a", "192k", str(temporary),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
        metrics = _extract_loudnorm_json(result.stderr) or {}
        verification = measure_loudness(temporary)
        measured_lufs = verification.get("integrated_lufs")
        measured_peak = verification.get("true_peak_dbfs")
        if measured_lufs is None or measured_peak is None:
            raise ValueError(f"normalized music verification failed: {verification}")
        if abs(float(measured_lufs) - target_lufs) > tolerance_lu:
            raise ValueError(
                f"normalized music LUFS outside tolerance: {measured_lufs} vs {target_lufs}"
            )
        if float(measured_peak) > true_peak_dbfs + 0.5:
            raise ValueError(
                f"normalized music true peak exceeds tolerance: {measured_peak}"
            )
        temporary.replace(target)
        return {
            "mode": "ffmpeg_loudnorm", "path": str(target), "source_path": str(source),
            "source_sha256": sha256_file(source), "output_sha256": sha256_file(target),
            "target_lufs": target_lufs, "target_true_peak_dbfs": true_peak_dbfs,
            "measured_output_lufs": measured_lufs,
            "measured_output_true_peak_dbfs": measured_peak,
            "filter_reported_output_lufs": float(metrics["output_i"]) if metrics.get("output_i") else None,
            "filter_reported_output_true_peak_dbfs": float(metrics["output_tp"]) if metrics.get("output_tp") else None,
            "verified": True,
        }
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        if temporary.exists():
            temporary.unlink()
        raise RuntimeError(f"Background music normalization failed for {source}: {exc}") from exc


def _media_audio_durations(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        payload = json.loads(result.stdout)
        format_duration = float(payload.get("format", {}).get("duration") or 0)
        audio_streams = [
            row for row in payload.get("streams", []) if row.get("codec_type") == "audio"
        ]
        audio_duration = (
            float(audio_streams[0].get("duration") or 0) if audio_streams else 0.0
        )
        return {
            "ok": bool(format_duration > 0 and audio_streams),
            "video_duration_seconds": round(format_duration, 3),
            "audio_duration_seconds": round(audio_duration, 3),
            "audio_stream_present": bool(audio_streams),
            "error": None,
        }
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "video_duration_seconds": 0.0,
            "audio_duration_seconds": 0.0,
            "audio_stream_present": False,
            "error": str(exc),
        }


def build_final_audio_mix_qc(
    render: Path,
    *,
    minimum_lufs: float = -22.0,
    maximum_lufs: float = -12.0,
    maximum_true_peak_dbfs: float = 0.0,
    maximum_audio_tail_gap_seconds: float = 1.25,
) -> dict[str, Any]:
    durations = _media_audio_durations(render)
    loudness = measure_loudness(render) if durations.get("audio_stream_present") else {
        "integrated_lufs": None,
        "true_peak_dbfs": None,
        "loudness_range_lu": None,
        "loudness_error": "audio stream missing",
    }
    audio_duration = float(durations.get("audio_duration_seconds") or 0)
    video_duration = float(durations.get("video_duration_seconds") or 0)
    tail_gap = max(0.0, video_duration - audio_duration)
    integrated = loudness.get("integrated_lufs")
    peak = loudness.get("true_peak_dbfs")
    checks = {
        "audio_stream_present": bool(durations.get("audio_stream_present")),
        "audio_covers_video_tail": tail_gap <= maximum_audio_tail_gap_seconds,
        "integrated_loudness_in_range": (
            integrated is not None and minimum_lufs <= float(integrated) <= maximum_lufs
        ),
        "true_peak_safe": peak is not None and float(peak) <= maximum_true_peak_dbfs,
    }
    return {
        "version": "1.0",
        "checked_at": utc_now(),
        "render": str(render),
        "durations": durations,
        "loudness": loudness,
        "audio_tail_gap_seconds": round(tail_gap, 3),
        "thresholds": {
            "minimum_lufs": minimum_lufs,
            "maximum_lufs": maximum_lufs,
            "maximum_true_peak_dbfs": maximum_true_peak_dbfs,
            "maximum_audio_tail_gap_seconds": maximum_audio_tail_gap_seconds,
        },
        "checks": checks,
        "approved_for_delivery": all(checks.values()),
    }
