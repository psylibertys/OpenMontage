"""Microsoft Edge online text-to-speech provider with word timestamps."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class EdgeTTS(BaseTool):
    name = "edge_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "edge"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["python:edge_tts"]
    install_instructions = "Install the locked provider with: .venv/bin/pip install edge-tts==7.2.7"
    capabilities = [
        "text_to_speech",
        "voice_selection",
        "multilingual",
        "word_timestamps",
        "single_pass_audio_and_timing",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "word_timestamps": True,
        "single_pass": True,
    }
    best_for = [
        "free natural Mandarin narration",
        "single-pass narration with provider word boundaries",
        "punctuation-led pacing without an API key",
    ]
    not_good_for = [
        "offline production",
        "voice cloning",
        "provider-level emotional instructions",
    ]
    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "voice": {"type": "string", "default": "zh-CN-XiaoxiaoNeural"},
            "rate": {"type": "string", "default": "+0%"},
            "pitch": {"type": "string", "default": "+0Hz"},
            "volume": {"type": "string", "default": "+0%"},
            "boundary": {
                "type": "string",
                "enum": ["WordBoundary", "SentenceBoundary"],
                "default": "WordBoundary",
            },
            "output_path": {"type": "string"},
            "subtitles_path": {"type": "string"},
            "timings_path": {"type": "string"},
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=256,
        vram_mb=0,
        disk_mb=50,
        network_required=True,
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=1.0,
        retryable_errors=["timeout", "connection", "websocket"],
    )
    idempotency_key_fields = ["text", "voice", "rate", "pitch", "volume", "boundary"]
    side_effects = [
        "writes MP3, SRT, and timing JSON files",
        "calls the Microsoft Edge online TTS service",
    ]
    user_visible_verification = [
        "Listen for natural punctuation-led pauses",
        "Confirm generated captions align with the narration",
    ]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if importlib.util.find_spec("edge_tts") else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="Edge-TTS is not installed. " + self.install_instructions)

        text = str(inputs.get("text", ""))
        if not text.strip():
            return ToolResult(success=False, error="Edge-TTS text must not be empty.")

        output_path = Path(inputs.get("output_path", "edge_tts.mp3"))
        if output_path.suffix.lower() != ".mp3":
            return ToolResult(success=False, error="Edge-TTS output_path must use the .mp3 extension.")
        subtitles_path = Path(inputs.get("subtitles_path", output_path.with_suffix(".srt")))
        timings_path = Path(inputs.get("timings_path", output_path.with_suffix(".timings.json")))
        for path in (output_path, subtitles_path, timings_path):
            path.parent.mkdir(parents=True, exist_ok=True)

        started_at = time.time()
        last_error: Exception | None = None
        boundaries: list[dict[str, Any]] = []
        attempts = self.retry_policy.max_retries + 1
        for attempt in range(attempts):
            try:
                boundaries = asyncio.run(self._stream_once(inputs, output_path))
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                output_path.unlink(missing_ok=True)
                if attempt < attempts - 1:
                    time.sleep(self.retry_policy.backoff_seconds * (2**attempt))

        if last_error is not None:
            return ToolResult(
                success=False,
                error=f"Edge-TTS failed after {attempts} attempts: {last_error}",
                duration_seconds=round(time.time() - started_at, 2),
            )
        if not output_path.exists() or output_path.stat().st_size == 0:
            return ToolResult(success=False, error=f"Edge-TTS produced no audio: {output_path}")

        self._write_srt(subtitles_path, boundaries)
        timings_path.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "provider": self.provider,
                    "voice": inputs.get("voice", "zh-CN-XiaoxiaoNeural"),
                    "rate": inputs.get("rate", "+0%"),
                    "pitch": inputs.get("pitch", "+0Hz"),
                    "volume": inputs.get("volume", "+0%"),
                    "text": text,
                    "boundaries": boundaries,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        from tools.analysis.audio_probe import probe_duration

        duration = float(probe_duration(output_path) or 0)
        try:
            import edge_tts

            provider_version = edge_tts.__version__
        except Exception:
            provider_version = "unknown"

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "provider_version": provider_version,
                "model": f"edge-tts-{provider_version}",
                "voice": inputs.get("voice", "zh-CN-XiaoxiaoNeural"),
                "rate": inputs.get("rate", "+0%"),
                "pitch": inputs.get("pitch", "+0Hz"),
                "volume": inputs.get("volume", "+0%"),
                "text_length": len(text),
                "audio_duration_seconds": round(duration, 3),
                "output": str(output_path),
                "subtitles": str(subtitles_path),
                "timings": str(timings_path),
                "boundaries": boundaries,
                "attempts": attempt + 1,
            },
            artifacts=[str(output_path), str(subtitles_path), str(timings_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - started_at, 2),
            model=f"edge-tts-{provider_version}",
        )

    async def _stream_once(self, inputs: dict[str, Any], output_path: Path) -> list[dict[str, Any]]:
        import edge_tts

        communicate = edge_tts.Communicate(
            inputs["text"],
            inputs.get("voice", "zh-CN-XiaoxiaoNeural"),
            rate=inputs.get("rate", "+0%"),
            pitch=inputs.get("pitch", "+0Hz"),
            volume=inputs.get("volume", "+0%"),
            boundary=inputs.get("boundary", "WordBoundary"),
        )
        temporary = output_path.with_suffix(output_path.suffix + ".part")
        temporary.unlink(missing_ok=True)
        boundaries: list[dict[str, Any]] = []
        try:
            with temporary.open("wb") as audio:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio.write(chunk["data"])
                    elif chunk["type"] in {"WordBoundary", "SentenceBoundary"}:
                        start = float(chunk["offset"]) / 10_000_000
                        duration = float(chunk["duration"]) / 10_000_000
                        boundaries.append(
                            {
                                "type": chunk["type"],
                                "text": chunk["text"],
                                "start_seconds": round(start, 6),
                                "end_seconds": round(start + duration, 6),
                            }
                        )
            temporary.replace(output_path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return boundaries

    @classmethod
    def _write_srt(cls, path: Path, boundaries: list[dict[str, Any]]) -> None:
        lines: list[str] = []
        for index, boundary in enumerate(boundaries, start=1):
            lines.extend(
                [
                    str(index),
                    f"{cls._srt_time(boundary['start_seconds'])} --> {cls._srt_time(boundary['end_seconds'])}",
                    str(boundary["text"]),
                    "",
                ]
            )
        path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _srt_time(seconds: float) -> str:
        milliseconds = max(0, round(float(seconds) * 1000))
        hours, remainder = divmod(milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, millis = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
