"""Contracts for the local Qwen3-ASR + ForcedAligner backend."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.analysis.qwen3_asr_runner import (
    build_transcript_payload,
    normalize_language,
    prepare_audio_input,
)
from tools.analysis.transcriber import Transcriber
from tools.base_tool import ToolResult


def test_normalize_language_accepts_iso_codes_and_auto() -> None:
    assert normalize_language(None) is None
    assert normalize_language("auto") is None
    assert normalize_language("zh") == "Chinese"
    assert normalize_language("en") == "English"
    assert normalize_language("Cantonese") == "Cantonese"


def test_build_transcript_payload_normalizes_aligner_objects() -> None:
    result = SimpleNamespace(
        language="Chinese",
        text="你好，世界。",
        time_stamps=[
            SimpleNamespace(text="你", start_time=0.10, end_time=0.24),
            SimpleNamespace(text="好", start_time=0.24, end_time=0.40),
            SimpleNamespace(text="，", start_time=0.40, end_time=0.44),
            SimpleNamespace(text="世", start_time=0.70, end_time=0.86),
            SimpleNamespace(text="界", start_time=0.86, end_time=1.02),
            SimpleNamespace(text="。", start_time=1.02, end_time=1.08),
        ],
    )

    payload = build_transcript_payload(
        result,
        model_path="/models/Qwen3-ASR-1.7B",
        aligner_path="/models/Qwen3-ForcedAligner-0.6B",
        device="mps",
    )

    assert payload["backend"] == "qwen3-asr"
    assert payload["language"] == "zh"
    assert payload["text"] == "你好，世界。"
    assert payload["duration_seconds"] == 1.08
    assert payload["word_timestamps"][0] == {
        "word": "你",
        "start": 0.1,
        "end": 0.24,
        "probability": 1.0,
    }
    assert "你好，" in "".join(segment["text"] for segment in payload["segments"])
    assert payload["segments"][0]["words"]


def test_build_transcript_payload_without_aligner_has_safe_segment() -> None:
    result = {"language": "English", "text": "A short transcript", "time_stamps": []}
    payload = build_transcript_payload(
        result,
        model_path="/models/asr",
        aligner_path=None,
        device="cpu",
        audio_duration=2.5,
    )

    assert payload["word_timestamps"] == []
    assert payload["segments"] == [
        {"id": 0, "start": 0.0, "end": 2.5, "text": "A short transcript"}
    ]


def test_transcriber_dispatches_qwen_backend(monkeypatch, tmp_path: Path) -> None:
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF")
    expected = ToolResult(success=True, data={"backend": "qwen3-asr"})
    called: dict[str, object] = {}

    def fake_execute(self, input_path, output_dir, inputs):
        called.update(input_path=input_path, output_dir=output_dir, inputs=inputs)
        return expected

    monkeypatch.setattr(Transcriber, "_execute_qwen", fake_execute)
    result = Transcriber().execute(
        {
            "input_path": str(audio),
            "output_dir": str(tmp_path),
            "backend": "qwen3-asr",
        }
    )

    assert result is expected
    assert called["input_path"] == audio


def test_transcriber_rejects_unknown_backend(tmp_path: Path) -> None:
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF")
    result = Transcriber().execute({"input_path": str(audio), "backend": "other"})
    assert not result.success
    assert "backend" in (result.error or "").lower()


def test_prepare_audio_input_keeps_wav_unchanged(tmp_path: Path) -> None:
    wav = tmp_path / "sample.wav"
    wav.write_bytes(b"RIFF")

    with prepare_audio_input(wav) as prepared:
        assert prepared == wav.resolve()


def test_prepare_audio_input_extracts_mp4_and_cleans_up(monkeypatch, tmp_path: Path) -> None:
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"video")
    observed: dict[str, object] = {}

    def fake_run(command, capture_output, text):
        observed["command"] = command
        Path(command[-1]).write_bytes(b"RIFF")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("tools.analysis.qwen3_asr_runner.shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr("tools.analysis.qwen3_asr_runner.subprocess.run", fake_run)

    with prepare_audio_input(video) as prepared:
        prepared_path = prepared
        assert prepared.is_file()
        assert prepared.suffix == ".wav"
        assert "-ar" in observed["command"]
        assert "16000" in observed["command"]
        assert "-af" in observed["command"]
        assert "aresample=16000:async=1000:first_pts=0" in observed["command"]
        assert "-ac" in observed["command"]
        assert "1" in observed["command"]

    assert not prepared_path.exists()


def test_prepare_audio_input_reports_ffmpeg_failure(monkeypatch, tmp_path: Path) -> None:
    video = tmp_path / "sample.mov"
    video.write_bytes(b"video")

    monkeypatch.setattr("tools.analysis.qwen3_asr_runner.shutil.which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "tools.analysis.qwen3_asr_runner.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="decode failed"),
    )

    with pytest.raises(RuntimeError, match="decode failed"):
        with prepare_audio_input(video):
            pass
