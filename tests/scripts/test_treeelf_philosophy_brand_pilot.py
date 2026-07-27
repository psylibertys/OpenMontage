from __future__ import annotations

import json
from pathlib import Path

from scripts.treeelf_philosophy_brand_pilot import (
    DEFAULT_CONFIG,
    _event_summary,
    cover_props,
    load_json,
    media_duration_seconds,
    prepare_project,
    scan_inbox,
    validate_config,
    validate_live_gpu_state,
)


def test_media_duration_seconds_reads_playable_duration(tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp3"

    assert media_duration_seconds(missing) is None


def test_reviewed_brand_pilot_config_is_valid() -> None:
    config = load_json(DEFAULT_CONFIG)

    assert validate_config(config) == []
    assert len(config["voice_selection"]["candidates"]) == 10
    assert len(config["cover_selection"]["directions"]) == 12
    assert config["cover_selection"]["brand"] == "树精灵"
    assert {item["instruct"] for item in config["voice_selection"]["candidates"]}
    assert len({item["instruct"] for item in config["voice_selection"]["candidates"]}) == 10


def test_scan_inbox_only_reads_root_and_filters_review_status(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    eligible = inbox / "ready.md"
    eligible.write_text(
        "---\ntype: 短视频文案\nasset_id: ready-id\nstatus: ready\nreview_status: passed\ncover_title: 先开门\n---\n# 合格文章\n\n正文",
        encoding="utf-8",
    )
    draft = inbox / "draft.md"
    draft.write_text(
        "---\ntype: 短视频文案\nasset_id: draft-id\nstatus: draft\nreview_status: pending\n---\n# 草稿\n\n正文",
        encoding="utf-8",
    )
    nested = inbox / "_reviews"
    nested.mkdir()
    (nested / "ignored.md").write_text(eligible.read_text(encoding="utf-8"), encoding="utf-8")

    ledger = tmp_path / "ledger.json"
    report = scan_inbox(inbox, ledger_path=ledger)

    assert report["root_markdown_count"] == 2
    assert report["counts"]["eligible"] == 1
    assert report["counts"]["draft"] == 1
    assert set(report["items"]) == {"ready-id", "draft-id"}


def test_scan_inbox_increments_revision_when_source_changes(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    source = inbox / "ready.md"
    source.write_text(
        "---\ntype: 短视频文案\nasset_id: same-id\nstatus: ready\nreview_status: passed\n---\n# 标题\n\n第一版",
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    first = scan_inbox(inbox, ledger_path=ledger)
    source.write_text(source.read_text(encoding="utf-8") + "修订", encoding="utf-8")
    second = scan_inbox(inbox, ledger_path=ledger)

    assert first["items"]["same-id"]["revision"] == 1
    assert second["items"]["same-id"]["revision"] == 2
    assert second["items"]["same-id"]["changed_since_last_scan"] is True


def test_scan_inbox_excludes_completed_production(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "done.md").write_text(
        "---\n"
        "type: 短视频文案\n"
        "asset_id: done-1\n"
        "status: ready\n"
        "review_status: passed\n"
        "production_status: completed\n"
        "video_project_id: project-1\n"
        "video_output: /tmp/final.mp4\n"
        "---\n\n# 已完成\n",
        encoding="utf-8",
    )
    report = scan_inbox(inbox, ledger_path=tmp_path / "ledger.json")
    item = report["items"]["done-1"]
    assert item["eligibility"] == "other"
    assert item["production_status"] == "completed"
    assert item["video_project_id"] == "project-1"
    assert item["video_output"] == "/tmp/final.mp4"


def test_scan_inbox_excludes_source_reserved_by_active_batch(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    source = inbox / "reserved.md"
    source.write_text(
        "---\ntype: 短视频文案\nasset_id: reserved-1\nstatus: ready\nreview_status: passed\n---\n# 已预约\n",
        encoding="utf-8",
    )
    reservations = tmp_path / "projects"
    artifacts = reservations / "treeelf-batch-test" / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "batch_manifest.json").write_text(
        json.dumps({
            "workflow": "treeelf_philosophy_gpu_batch",
            "batch_id": "treeelf-batch-test",
            "episodes": [{"source_path": str(source.resolve()), "status": "local_pending"}],
        }),
        encoding="utf-8",
    )

    report = scan_inbox(
        inbox,
        ledger_path=tmp_path / "ledger.json",
        reservations_dir=reservations,
    )

    item = report["items"]["reserved-1"]
    assert item["eligibility"] == "other"
    assert item["batch_reservation"]["batch_id"] == "treeelf-batch-test"


def test_prepare_project_writes_snapshot_and_twelve_direction_docs(tmp_path: Path) -> None:
    config = load_json(DEFAULT_CONFIG)
    source = tmp_path / "source.md"
    source.write_text("---\ntype: 短视频文案\n---\n# 测试\n\n正文", encoding="utf-8")
    config["source_script_md"] = str(source)
    config["project_id"] = "brand-pilot-test"

    result = prepare_project(config, projects_dir=tmp_path / "projects")
    project = Path(result["project_dir"])

    assert (project / "project.json").is_file()
    assert (project / "artifacts" / "source_script.md").read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    assert len(list((project / "artifacts" / "cover_directions").glob("C*.md"))) == 12
    snapshot = json.loads((project / "artifacts" / "source_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["source_sha256"] == snapshot["snapshot_sha256"]


def test_cover_props_use_treeelf_brand_and_direction_layout() -> None:
    config = load_json(DEFAULT_CONFIG)
    direction = config["cover_selection"]["directions"][0]

    props = cover_props(config, direction, "demo/cover")

    assert props["brand"] == "树精灵"
    assert props["chineseTitle"] == "先开门"
    assert props["englishTitle"] == "OPEN ONE DOOR"
    assert props["backgroundSrc"].endswith("/C01.png")


def test_gpu_event_summary_tracks_kind_averages_and_failures() -> None:
    summary = _event_summary(
        [
            {"kind": "voice_candidate", "status": "completed", "wall_seconds": 10, "retry_count": 0},
            {"kind": "voice_candidate", "status": "completed", "wall_seconds": 14, "retry_count": 1},
            {"kind": "cover_background", "status": "failed", "wall_seconds": 8, "retry_count": 0},
        ]
    )

    assert summary["completed"] == 2
    assert summary["failed"] == 1
    assert summary["retry_count"] == 1
    assert summary["effective_generation_seconds"] == 24
    assert summary["average_seconds_by_kind"]["voice_candidate"] == 12


def test_live_gpu_state_requires_gpu_and_empty_queue() -> None:
    assert validate_live_gpu_state(
        {"devices": [{"name": "NVIDIA RTX", "type": "cuda"}]},
        {"queue_running": [], "queue_pending": []},
    ) == []
    errors = validate_live_gpu_state(
        {"devices": [{"name": "CPU", "type": "cpu"}]},
        {"queue_running": [[1]], "queue_pending": [[2]]},
    )
    assert "ComfyUI system_stats does not report a GPU device" in errors
    assert "ComfyUI queue_running is not empty" in errors
    assert "ComfyUI queue_pending is not empty" in errors
