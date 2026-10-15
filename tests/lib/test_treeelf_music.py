from __future__ import annotations

import json
import math
import struct
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lib.treeelf_music import (
    build_final_audio_mix_qc,
    build_catalog,
    ensure_catalog_fresh,
    normalize_background_music,
    record_music_usage,
    select_and_record_music_usage,
    select_music_track,
    transition_music_usage,
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


def test_catalog_relative_paths_survive_library_root_move(tmp_path: Path) -> None:
    original = tmp_path / "old-root"
    _tone(original / "nested" / "warm-ambient-纯音乐.wav")
    catalog, overrides, usage = _paths(tmp_path)
    build_catalog(original, catalog, analyze_loudness=False)
    moved = tmp_path / "new-root"
    original.rename(moved)

    selected = select_music_track(
        project_id="moved-library",
        series="zh-philosophy-video",
        keywords=["ambient"],
        library_dirs=[moved],
        catalog_path=catalog,
        overrides_path=overrides,
        usage_ledger_path=usage,
    )

    assert Path(selected["path"]).is_file()
    assert Path(selected["path"]).is_relative_to(moved)


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


def test_concurrent_selection_reserves_different_tracks(tmp_path: Path) -> None:
    library = tmp_path / "music"
    _tone(library / "a-ambient-纯音乐.wav", 330)
    _tone(library / "b-ambient-纯音乐.wav", 550)
    catalog, overrides, usage = _paths(tmp_path)
    build_catalog(library, catalog, analyze_loudness=False)

    def reserve(project_id: str) -> dict:
        selection, _ = select_and_record_music_usage(
            lambda preferred_track_id: select_music_track(
                project_id=project_id,
                series="zh-philosophy-video",
                keywords=["ambient"],
                library_dirs=[library],
                catalog_path=catalog,
                overrides_path=overrides,
                usage_ledger_path=usage,
                preferred_track_id=preferred_track_id,
            ),
            project_id=project_id,
            series="zh-philosophy-video",
            ledger_path=usage,
        )
        return selection

    with ThreadPoolExecutor(max_workers=2) as executor:
        selections = list(executor.map(reserve, ["parallel-a", "parallel-b"]))

    assert len({row["track_id"] for row in selections}) == 2
    assert len(json.loads(usage.read_text(encoding="utf-8"))["events"]) == 2


def test_same_project_reuses_reserved_track_and_commits(tmp_path: Path) -> None:
    library = tmp_path / "music"
    _tone(library / "a-ambient-纯音乐.wav", 330)
    _tone(library / "b-ambient-纯音乐.wav", 550)
    catalog, overrides, usage = _paths(tmp_path)
    build_catalog(library, catalog, analyze_loudness=False)

    def reserve() -> tuple[dict, dict]:
        return select_and_record_music_usage(
            lambda preferred_track_id: select_music_track(
                project_id="same-project",
                series="zh-philosophy-video",
                keywords=["ambient"],
                library_dirs=[library],
                catalog_path=catalog,
                overrides_path=overrides,
                usage_ledger_path=usage,
                preferred_track_id=preferred_track_id,
            ),
            project_id="same-project",
            series="zh-philosophy-video",
            ledger_path=usage,
        )

    first, first_record = reserve()
    second, second_record = reserve()
    transition = transition_music_usage(
        project_id="same-project",
        series="zh-philosophy-video",
        status="committed",
        ledger_path=usage,
    )

    assert first_record["event"]["status"] == "reserved"
    assert second["track_id"] == first["track_id"]
    assert second["mode"] == "existing_project_reuse"
    assert second_record["reason"] == "existing project music reused"
    assert transition["event"]["status"] == "committed"
    assert len(json.loads(usage.read_text(encoding="utf-8"))["events"]) == 1


def test_failed_reservation_does_not_penalize_future_selection(tmp_path: Path) -> None:
    library = tmp_path / "music"
    _tone(library / "a-ambient-纯音乐.wav", 330)
    _tone(library / "b-ambient-纯音乐.wav", 550)
    catalog, overrides, usage = _paths(tmp_path)
    build_catalog(library, catalog, analyze_loudness=False)
    first, _ = select_and_record_music_usage(
        lambda preferred_track_id: select_music_track(
            project_id="failed-project",
            series="treeelf-fable",
            keywords=["ambient"],
            library_dirs=[library],
            catalog_path=catalog,
            overrides_path=overrides,
            usage_ledger_path=usage,
            preferred_track_id=preferred_track_id,
        ),
        project_id="failed-project",
        series="treeelf-fable",
        ledger_path=usage,
    )
    transition_music_usage(
        project_id="failed-project",
        series="treeelf-fable",
        status="failed",
        ledger_path=usage,
        reason="test failure",
    )
    later = select_music_track(
        project_id="same-jitter-project",
        series="zh-philosophy-video",
        keywords=["ambient"],
        library_dirs=[library],
        catalog_path=catalog,
        overrides_path=overrides,
        usage_ledger_path=usage,
    )

    assert later["top_candidates"][0]["history_penalty"] == 0
    assert first["track_id"] in {row["track_id"] for row in later["top_candidates"]}


def test_failed_track_is_excluded_when_same_project_reselects(tmp_path: Path) -> None:
    library = tmp_path / "music"
    _tone(library / "a-ambient-纯音乐.wav", 330)
    _tone(library / "b-ambient-纯音乐.wav", 550)
    catalog, overrides, usage = _paths(tmp_path)
    build_catalog(library, catalog, analyze_loudness=False)

    def reserve() -> tuple[dict, dict]:
        return select_and_record_music_usage(
            lambda preferred_track_id: select_music_track(
                project_id="retry-project",
                series="treeelf-fable",
                keywords=["ambient"],
                library_dirs=[library],
                catalog_path=catalog,
                overrides_path=overrides,
                usage_ledger_path=usage,
                preferred_track_id=preferred_track_id,
            ),
            project_id="retry-project",
            series="treeelf-fable",
            ledger_path=usage,
        )

    first, _ = reserve()
    transition_music_usage(
        project_id="retry-project",
        series="treeelf-fable",
        status="failed",
        ledger_path=usage,
        reason="normalization failed",
    )
    second, _ = reserve()

    assert second["track_id"] != first["track_id"]
    assert first["track_id"] in second["failed_project_tracks_excluded"]


def test_stale_reservation_expires_before_new_selection(tmp_path: Path) -> None:
    library = tmp_path / "music"
    _tone(library / "a-ambient-纯音乐.wav", 330)
    catalog, overrides, usage = _paths(tmp_path)
    payload = build_catalog(library, catalog, analyze_loudness=False)
    track = payload["tracks"][0]
    usage.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "events": [
                    {
                        "project_id": "abandoned",
                        "series": "treeelf-fable",
                        "track_id": track["id"],
                        "status": "reserved",
                        "reserved_at": "2020-01-01T00:00:00+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    select_and_record_music_usage(
        lambda preferred_track_id: select_music_track(
            project_id="new-project",
            series="treeelf-fable",
            keywords=["ambient"],
            library_dirs=[library],
            catalog_path=catalog,
            overrides_path=overrides,
            usage_ledger_path=usage,
            preferred_track_id=preferred_track_id,
        ),
        project_id="new-project",
        series="treeelf-fable",
        ledger_path=usage,
        reservation_ttl_hours=1,
    )
    events = json.loads(usage.read_text(encoding="utf-8"))["events"]

    assert events[0]["status"] == "failed"
    assert events[0]["failure_reason"] == "reservation_expired"
    assert events[1]["status"] == "reserved"


def test_incremental_refresh_adds_new_track(tmp_path: Path) -> None:
    library = tmp_path / "music"
    _tone(library / "a-ambient-纯音乐.wav", 330)
    catalog, _, _ = _paths(tmp_path)
    build_catalog(library, catalog, analyze_loudness=False)
    _tone(library / "b-piano-纯音乐.wav", 550)

    refresh = ensure_catalog_fresh(library, catalog, analyze_loudness=False)
    payload = json.loads(catalog.read_text(encoding="utf-8"))

    assert refresh["status"] == "rebuilt"
    assert payload["file_count"] == 2
    assert payload["track_count"] == 2


def test_pure_music_keyword_is_qualification_not_semantic_match(tmp_path: Path) -> None:
    library = tmp_path / "music"
    _tone(library / "a-纯音乐.wav", 330)
    catalog, overrides, usage = _paths(tmp_path)
    build_catalog(library, catalog, analyze_loudness=False)

    selected = select_music_track(
        project_id="generic-only",
        series="zh-philosophy-video",
        keywords=["纯音乐", "instrumental"],
        library_dirs=[library],
        catalog_path=catalog,
        overrides_path=overrides,
        usage_ledger_path=usage,
    )

    assert selected["mode"] == "weighted_deterministic_fallback"
    assert selected["matched_keywords"] == []
    assert selected["ignored_generic_keywords"] == ["纯音乐", "instrumental"]


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
    assert report["verified"] is True


def test_normalization_failure_stops_without_passthrough(tmp_path: Path) -> None:
    source = tmp_path / "broken.mp3"
    target = tmp_path / "background.mp3"
    source.write_bytes(b"not-audio")

    try:
        normalize_background_music(source, target)
    except RuntimeError as exc:
        assert "normalization failed" in str(exc).lower()
    else:
        raise AssertionError("invalid music must not pass through normalization")
    assert not target.exists()


def test_final_audio_mix_qc_checks_loudness_peak_and_tail(tmp_path: Path) -> None:
    render = tmp_path / "final.mp4"
    import subprocess

    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-filter:a", "volume=0.15",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(render),
        ],
        check=True,
    )
    report = build_final_audio_mix_qc(
        render,
        minimum_lufs=-40,
        maximum_lufs=-5,
        maximum_true_peak_dbfs=0,
        maximum_audio_tail_gap_seconds=0.5,
    )

    assert report["approved_for_delivery"] is True
    assert report["checks"]["audio_covers_video_tail"] is True
