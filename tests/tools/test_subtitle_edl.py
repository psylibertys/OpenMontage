import json

import pytest

from tools.subtitle.subtitle_gen import SubtitleGen


def _segments():
    return [{
        "start": 10.0,
        "end": 16.0,
        "text": "你好垃圾世界 hello world",
        "words": [
            {"word": "你", "start": 10.0, "end": 10.4},
            {"word": "好", "start": 10.4, "end": 10.8},
            {"word": "垃", "start": 11.0, "end": 11.2},
            {"word": "圾", "start": 11.2, "end": 11.4},
            {"word": "世", "start": 12.0, "end": 12.4},
            {"word": "界", "start": 12.4, "end": 12.8},
            {"word": "删", "start": 13.2, "end": 13.5},
            {"word": "除", "start": 13.5, "end": 13.8},
            {"word": "hello", "start": 15.0, "end": 15.4},
            {"word": "world", "start": 15.5, "end": 16.0},
        ],
    }]


def _operations():
    return [
        {"action": "KEEP", "start": 10.0, "end": 14.0},
        {"action": "CUT", "start": 13.0, "end": 14.0},
        {"action": "KEEP", "start": 15.0, "end": 16.0},
        {"action": "BLEEP", "start": 11.0, "end": 11.4, "subtitle": "[哔]"},
        {"action": "RISK_LABEL", "start": 0, "end": 4, "text": "仅供参考"},
    ]


def test_edl_rebases_cuts_and_collapses_bleep():
    segments, metadata = SubtitleGen._rebase_segments_to_edl(
        _segments(), _operations(), "[哔]"
    )
    words = segments[0]["words"]
    assert metadata["duration_seconds"] == pytest.approx(4.0)
    assert [word["word"] for word in words].count("[哔]") == 1
    assert "垃" not in [word["word"] for word in words]
    assert "圾" not in [word["word"] for word in words]
    assert "删" not in [word["word"] for word in words]
    assert words[0]["start"] == pytest.approx(0.0)
    assert words[-1]["end"] == pytest.approx(4.0)
    assert metadata["bleeps"] == [
        {"startMs": 1000, "endMs": 1400, "replacement": "[哔]"}
    ]
    assert all(a["end"] <= b["start"] for a, b in zip(words, words[1:]))


def test_remotion_json_schema_and_chinese_spacing(tmp_path):
    output = tmp_path / "captions.json"
    result = SubtitleGen().execute({
        "segments": _segments(),
        "edl_operations": _operations(),
        "format": "remotion_json",
        "output_path": str(output),
        "max_words_per_cue": 20,
    })
    assert result.success
    data = json.loads(output.read_text())
    assert data["durationMs"] == 4000
    assert data["timebase"] == "clip_relative"
    assert data["words"][0] == {"word": "你", "startMs": 0, "endMs": 400}
    assert data["captions"][0]["timestampMs"] == 0

    cues = SubtitleGen()._build_cues(_segments(), max_words=20, max_chars=100)
    assert cues[0]["text"] == "你好垃圾世界删除hello world"


def test_edl_can_preserve_declared_keep_order_for_cold_open():
    operations = [
        {"action": "KEEP", "start": 15.0, "end": 16.0},
        {"action": "KEEP", "start": 10.0, "end": 10.8},
    ]
    segments, metadata = SubtitleGen._rebase_segments_to_edl(
        _segments(), operations, "[哔]", preserve_keep_order=True
    )
    words = segments[0]["words"]
    assert metadata["duration_seconds"] == pytest.approx(1.8)
    assert [word["word"] for word in words] == ["hello", "world", "你", "好"]
    assert words[0]["start"] == pytest.approx(0.0)
    assert words[2]["start"] == pytest.approx(1.0)


def test_ordered_edl_rejects_accidental_overlap():
    operations = [
        {"action": "KEEP", "start": 11.0, "end": 12.0},
        {"action": "KEEP", "start": 10.0, "end": 14.0},
    ]
    with pytest.raises(ValueError, match="would replay source speech"):
        SubtitleGen._rebase_segments_to_edl(
            _segments(), operations, "[哔]", preserve_keep_order=True
        )


def test_ordered_edl_allows_explicit_audited_overlap():
    operations = [
        {"action": "KEEP", "start": 11.0, "end": 12.0},
        {"action": "KEEP", "start": 10.0, "end": 14.0},
    ]
    _, metadata = SubtitleGen._rebase_segments_to_edl(
        _segments(), operations, "[哔]", preserve_keep_order=True,
        allow_overlapping_keeps=True,
    )
    assert metadata["duration_seconds"] == pytest.approx(5.0)
