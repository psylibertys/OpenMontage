from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

from lib.treeelf_music import (
    build_catalog,
    normalize_background_music,
    record_music_usage,
    select_music_track,
)


def _tone(path: Path, frequency: float = 440.0, seconds: float = 0.2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 16000
    frames = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        payload = b"".join(
            struct.pack("<h", int(6000 * math.sin(2 * math.pi * frequency * index / sample_rate)))
            for index in range(frames)
        )
        handle.writeframes(payload)


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    return (
        tmp_path / "catalog.json",
        tmp_path / "overrides.json",
        tmp_path / "usage.json",
    )


def test_catalog_deduplicates_by_sha_and_keeps_aliases(tmp_path: Path) -> None:
    library = tmp_path / "music"
    first = library / "warm-ambient-纯音乐.wav"
    duplicate = library / "renamed-copy.wav"
    _tone(first)
    duplicate.write_bytes(first.read_bytes())
    catalog, _, _ = _paths(tmp_path)

    payload = build_catalog(library, catalog, analyze_loudness=False)

    assert payload["file_count"] == 2
    assert payload["track_count"] == 1
    assert payload["duplicate_file_count"] == 1
    assert sorted([payload["tracks"][0]["relative_path"], *payload["tracks"][0]["aliases"]]) == [
        "renamed-copy.wav",
        "warm-ambient-纯音乐.wav",
    ]
    assert payload["tracks"][0]["duration_seconds"] is not None
    assert payload["tracks"][0]["rights_status"] == "user_supplied_unverified"


def test_manual_override_survives_rebuild_and_disables_track(tmp_path: Path) -> None:
    library = tmp_path / "music"
    first = library / "a-ambient-纯音乐.wav"
    second = library / "b-piano-纯音乐.wav"
    _tone(first, 330)
    _tone(second, 550)
    catalog, overrides, usage = _paths(tmp_path)
    payload = build_catalog(library, catalog, analyze_loudness=False)
    first_id = next(row["id"] for row in payload["tracks"] if row["filename"].startswith("a-"))
    overrides.write_text(json.dumps({
        "schema_version": "1.0",
        "tracks": {first_id: {"enabled": False, "notes": "manual reject"}},
    }), encoding="utf-8")

    rebuilt = build_catalog(library, catalog, analyze_loudness=False)
    selected = select_music_track(
        project_id="manual-override-test",
        series="zh-philosophy-video",
        keywords=["ambient"],
        library_dirs=[library],
        catalog_path=catalog,
        overrides_path=overrides,
        usage_ledger_path=usage,
    )

    assert overrides.read_text(encoding="utf-8").find("manual reject") >= 0
    assert rebuilt["track_count"] == 2
    assert Path(selected["path"]).name == second.name


def test_lyrics_are_excluded_and_no_match_fallback_is_deterministic(tmp_path: Path) -> None:
    library = tmp_path / "music"
    _tone(library / "有歌词-warm.wav", 220)
    _tone(library / "metal-instrumental.wav", 440)
    _tone(library / "piano-instrumental.wav", 660)
    catalog, overrides, usage = _paths(tmp_path)
    build_catalog(library, catalog, analyze_loudness=False)

    kwargs = {
        "project_id": "stable-fallback",
        "series": "treeelf-fable",
        "keywords": ["keyword-that-does-not-exist"],
        "library_dirs": [library],
        "catalog_path": catalog,
        "overrides_path": overrides,
        "usage_ledger_path": usage,
    }
    first = select_music_track(**kwargs)
    second = select_music_track(**kwargs)

    assert first["mode"] == "weighted_deterministic_fallback"
    assert first["path"] == second["path"]
    assert "有歌词" not in Path(first["path"]).name


def test_usage_ledger_is_idempotent_and_penalizes_history(tmp_path: Path) -> None:
    library = tmp_path / "music"
    _tone(library / "a-ambient-纯音乐.wav", 330)
    _tone(library / "b-ambient-纯音乐.wav", 550)
    catalog, overrides, usage = _paths(tmp_path)
    build_catalog(library, catalog, analyze_loudness=False)
    first = select_music_track(
        project_id="first-project", series="zh-philosophy-video", keywords=["ambient"],
        library_dirs=[library], catalog_path=catalog, overrides_path=overrides,
        usage_ledger_path=usage,
    )
    assert record_music_usage(first, project_id="first-project", series="zh-philosophy-video", ledger_path=usage)["recorded"]
    assert not record_music_usage(first, project_id="first-project", series="zh-philosophy-video", ledger_path=usage)["recorded"]
    second = select_music_track(
        project_id="second-project", series="treeelf-fable", keywords=["ambient"],
        library_dirs=[library], catalog_path=catalog, overrides_path=overrides,
        usage_ledger_path=usage,
    )

    assert second["track_id"] != first["track_id"]
    assert len(json.loads(usage.read_text(encoding="utf-8"))["events"]) == 1


def test_normalization_writes_project_derivative_without_changing_source(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    target = tmp_path / "project" / "background.mp3"
    _tone(source, seconds=0.5)
    before = source.read_bytes()

    report = normalize_background_music(source, target)

    assert report["mode"] == "ffmpeg_loudnorm"
    assert target.is_file() and target.stat().st_size > 0
    assert source.read_bytes() == before
    assert report["source_sha256"] != report["output_sha256"]
