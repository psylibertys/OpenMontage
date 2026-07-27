"""Contract and behavior tests for the Edge-TTS provider."""

from __future__ import annotations

import json
from pathlib import Path

from tools.audio.edge_tts import EdgeTTS
from tools.base_tool import BaseTool, ToolRuntime, ToolStatus, ToolTier


def test_contract_and_defaults():
    tool = EdgeTTS()
    assert isinstance(tool, BaseTool)
    assert tool.name == "edge_tts"
    assert tool.provider == "edge"
    assert tool.capability == "tts"
    assert tool.tier == ToolTier.VOICE
    assert tool.runtime == ToolRuntime.API
    assert tool.input_schema["properties"]["voice"]["default"] == "zh-CN-XiaoxiaoNeural"
    assert tool.input_schema["properties"]["rate"]["default"] == "+0%"
    assert tool.retry_policy.max_retries == 2
    assert tool.fallback is None
    assert tool.fallback_tools == []


def test_status_is_available_when_dependency_is_installed():
    assert EdgeTTS().get_status() == ToolStatus.AVAILABLE


def test_single_stream_writes_all_artifacts(tmp_path, monkeypatch):
    calls = 0

    async def fake_stream(self, inputs, output_path):
        nonlocal calls
        calls += 1
        output_path.write_bytes(b"fake-mp3")
        return [
            {"type": "WordBoundary", "text": "你好", "start_seconds": 0.1, "end_seconds": 0.6},
            {"type": "WordBoundary", "text": "世界", "start_seconds": 0.7, "end_seconds": 1.2},
        ]

    monkeypatch.setattr(EdgeTTS, "_stream_once", fake_stream)
    monkeypatch.setattr("tools.analysis.audio_probe.probe_duration", lambda _: 1.5)
    audio = tmp_path / "narration.mp3"
    result = EdgeTTS().execute({"text": "你好，世界。", "output_path": str(audio)})

    assert result.success
    assert calls == 1
    assert audio.read_bytes() == b"fake-mp3"
    assert audio.with_suffix(".srt").read_text(encoding="utf-8").startswith("1\n00:00:00,100")
    timing = json.loads(audio.with_suffix(".timings.json").read_text(encoding="utf-8"))
    assert timing["text"] == "你好，世界。"
    assert timing["boundaries"][1]["text"] == "世界"


def test_retries_twice_then_reports_failure(tmp_path, monkeypatch):
    calls = 0

    async def fail_stream(self, inputs, output_path):
        nonlocal calls
        calls += 1
        raise TimeoutError("network timeout")

    monkeypatch.setattr(EdgeTTS, "_stream_once", fail_stream)
    monkeypatch.setattr("tools.audio.edge_tts.time.sleep", lambda _: None)
    result = EdgeTTS().execute({"text": "测试", "output_path": str(tmp_path / "failed.mp3")})

    assert not result.success
    assert calls == 3
    assert "after 3 attempts" in result.error


def test_rejects_non_mp3_output(tmp_path):
    result = EdgeTTS().execute({"text": "测试", "output_path": str(tmp_path / "audio.wav")})
    assert not result.success
    assert ".mp3" in result.error


def test_srt_time_rounding():
    assert EdgeTTS._srt_time(61.2346) == "00:01:01,235"
