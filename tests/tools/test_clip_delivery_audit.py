from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from schemas.artifacts import validate_artifact
from tools.analysis.clip_delivery_audit import ClipDeliveryAudit, compare_word_timings


def words(offset: float = 0.0) -> list[dict]:
    return [
        {"word": "你", "start": 0.10 + offset, "end": 0.20 + offset},
        {"word": "好", "start": 0.20 + offset, "end": 0.30 + offset},
        {"word": "世", "start": 0.40 + offset, "end": 0.50 + offset},
        {"word": "界", "start": 0.50 + offset, "end": 0.60 + offset},
    ]


def captions() -> dict:
    return {
        "words": [
            {"word": item["word"], "startMs": int(item["start"] * 1000), "endMs": int(item["end"] * 1000)}
            for item in words()
        ]
    }


def test_compare_word_timings_accepts_aligned_words() -> None:
    result = compare_word_timings(captions()["words"], words(offset=0.12))
    assert result["status"] == "pass"
    assert result["matched_ratio"] == 1.0
    assert result["p90_absolute_error_seconds"] == 0.12


def test_compare_word_timings_rejects_large_drift() -> None:
    result = compare_word_timings(captions()["words"], words(offset=0.65))
    assert result["status"] == "fail"
    assert result["p90_absolute_error_seconds"] == 0.65


def test_delivery_audit_requires_visible_frame_zero_and_final_audio_sync(
    tmp_path: Path, monkeypatch
) -> None:
    video = tmp_path / "clip.mp4"
    caption_path = tmp_path / "captions.json"
    video.write_bytes(b"mp4")
    caption_path.write_text(json.dumps(captions()), encoding="utf-8")
    tool = ClipDeliveryAudit()

    probe = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920, "r_frame_rate": "30/1"},
            {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 1},
        ],
        "format": {"duration": "4.0"},
    }

    def fake_run(command, **_kwargs):
        if command[0] == "ffprobe":
            return SimpleNamespace(stdout=json.dumps(probe), stderr="", returncode=0)
        Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(command[-1]).write_bytes(b"jpg")
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(tool, "run_command", fake_run)
    monkeypatch.setattr(tool, "_transcribe", lambda *_args, **_kwargs: words(offset=0.08))
    artifact = tmp_path / "audit.json"
    cover = tmp_path / "covers" / "clip.jpg"
    result = tool.execute(
        {
            "clips": [
                {
                    "clip_id": "clip-01",
                    "video_path": str(video),
                    "captions_path": str(caption_path),
                    "expected_hook_title": "你好世界",
                    "frame_zero_title_visible": True,
                    "cover_path": str(cover),
                }
            ],
            "output_dir": str(tmp_path / "qa"),
            "artifact_path": str(artifact),
        }
    )
    assert result.success
    assert cover.is_file()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    validate_artifact("clip_delivery_audit", payload)
    assert payload["outputs"][0]["subtitle_sync"]["status"] == "pass"


def test_delivery_audit_blocks_missing_frame_zero_title(tmp_path: Path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    caption_path = tmp_path / "captions.json"
    video.write_bytes(b"mp4")
    caption_path.write_text(json.dumps(captions()), encoding="utf-8")
    tool = ClipDeliveryAudit()
    monkeypatch.setattr(
        tool,
        "_probe",
        lambda *_: {"duration_seconds": 4.0, "width": 1080, "height": 1920, "fps": 30.0, "video_codec": "h264", "audio_codec": "aac", "sample_rate": 48000, "channels": 1},
    )
    monkeypatch.setattr(tool, "_transcribe", lambda *_args, **_kwargs: words())
    monkeypatch.setattr(
        tool,
        "_extract_frame_zero",
        lambda _video, destination: (destination.parent.mkdir(parents=True, exist_ok=True), destination.write_bytes(b"jpg")),
    )
    artifact = tmp_path / "audit.json"
    result = tool.execute(
        {
            "clips": [{"clip_id": "clip-01", "video_path": str(video), "captions_path": str(caption_path), "expected_hook_title": "你好世界", "frame_zero_title_visible": False}],
            "output_dir": str(tmp_path / "qa"),
            "artifact_path": str(artifact),
        }
    )
    assert not result.success
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert "expected_hook_not_visible_at_frame_zero" in payload["outputs"][0]["issues"]
