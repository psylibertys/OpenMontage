from __future__ import annotations

import pytest

from lib.checkpoint import CheckpointValidationError, _validate_artifacts_for_stage


def render_report(count: int = 1) -> dict:
    return {
        "version": "1.0",
        "outputs": [
            {
                "path": f"renders/final/{index}.mp4",
                "format": "mp4",
                "resolution": "1080x1920",
                "duration_seconds": 10.0,
            }
            for index in range(count)
        ],
    }


def audit(count: int = 1, status: str = "pass") -> dict:
    failed = [] if status == "pass" else ["clip-1"]
    return {
        "version": "1.0",
        "status": status,
        "acceptance": {
            "minimum_matched_ratio": 0.7,
            "maximum_p90_error_seconds": 0.3,
            "frame_zero_requires_expected_hook": True,
            "standalone_cover_required": True,
        },
        "outputs": [
            {
                "clip_id": f"clip-{index}",
                "video_path": f"renders/final/{index}.mp4",
                "cover_path": f"covers/{index}.jpg",
                "technical": {},
                "frame_zero": {
                    "sample_path": f"qa/{index}.jpg",
                    "expected_hook_title": "标题",
                    "title_visible": True,
                    "review_method": "human_visual_exact_frame_n0",
                },
                "subtitle_sync": {"status": "pass"},
                "status": "pass",
                "issues": [],
            }
            for index in range(count)
        ],
        "failed_clip_ids": failed,
    }


def test_clip_factory_compose_requires_delivery_audit() -> None:
    with pytest.raises(CheckpointValidationError, match="without clip_delivery_audit"):
        _validate_artifacts_for_stage(
            "compose", "completed", {"render_report": render_report()}, "clip-factory"
        )


def test_clip_factory_compose_rejects_failed_delivery_audit() -> None:
    with pytest.raises(CheckpointValidationError, match="failed clip_delivery_audit"):
        _validate_artifacts_for_stage(
            "compose",
            "completed",
            {"render_report": render_report(), "clip_delivery_audit": audit(status="fail")},
            "clip-factory",
        )


def test_clip_factory_compose_rejects_partial_delivery_audit() -> None:
    with pytest.raises(CheckpointValidationError, match="counts do not match"):
        _validate_artifacts_for_stage(
            "compose",
            "completed",
            {"render_report": render_report(2), "clip_delivery_audit": audit(1)},
            "clip-factory",
        )


def test_clip_factory_compose_accepts_complete_passing_audit() -> None:
    _validate_artifacts_for_stage(
        "compose",
        "completed",
        {"render_report": render_report(2), "clip_delivery_audit": audit(2)},
        "clip-factory",
    )
