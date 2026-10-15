"""Local Qwen3-ASR + ForcedAligner runner for Apple Silicon.

The module deliberately imports MLX-Audio lazily so OpenMontage can keep its
main environment lightweight.  It can be executed from a dedicated Python
environment and communicates with callers through a JSON file.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Iterator


DEFAULT_ASR_MODEL = "/Users/treeelf/AI_Models/Qwen3-ASR-1.7B"
DEFAULT_ALIGNER_MODEL = "/Users/treeelf/AI_Models/Qwen3-ForcedAligner-0.6B"

LANGUAGE_NAMES = {
    "ar": "Arabic",
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "ru": "Russian",
    "yue": "Cantonese",
    "zh": "Chinese",
}
LANGUAGE_CODES = {value.lower(): key for key, value in LANGUAGE_NAMES.items()}
NO_SPACE_LANGUAGES = {"zh", "yue", "ja", "ko"}
SENTENCE_END = re.compile(r"[。！？!?；;]$")
NATIVE_AUDIO_SUFFIXES = {".wav", ".wave"}


@contextmanager
def prepare_audio_input(input_path: Path) -> Iterator[Path]:
    """Yield a MLX-decodable WAV, extracting audio from media containers.

    MLX-Audio's miniaudio decoder does not accept every container that the
    public Transcriber contract supports (notably MP4/MOV).  Keep native WAV
    inputs untouched and use FFmpeg for every other container so callers can
    continue passing audio or video paths transparently.
    """
    input_path = input_path.resolve()
    if input_path.suffix.lower() in NATIVE_AUDIO_SUFFIXES:
        yield input_path
        return

    ffmpeg = os.environ.get("FFMPEG_BINARY") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg is required to decode non-WAV input for Qwen3-ASR, but it was not found"
        )

    with tempfile.TemporaryDirectory(prefix="qwen3-asr-audio-") as temp_dir:
        wav_path = Path(temp_dir) / "input-16khz-mono.wav"
        command = [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-map",
            "0:a:0",
            "-vn",
            "-af",
            "aresample=16000:async=1000:first_pts=0",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True)
        except OSError as exc:
            raise RuntimeError(f"FFmpeg audio extraction could not start: {exc}") from exc
        if completed.returncode != 0 or not wav_path.is_file():
            detail = (completed.stderr or completed.stdout or "unknown FFmpeg error").strip()
            raise RuntimeError(f"FFmpeg audio extraction failed: {detail[-2000:]}")
        yield wav_path


def normalize_language(language: str | None) -> str | None:
    """Convert ISO codes to Qwen language names; None/auto enables detection."""
    if language is None or str(language).strip().lower() in {"", "auto", "none"}:
        return None
    value = str(language).strip()
    return LANGUAGE_NAMES.get(value.lower(), value)


def language_code(language: Any) -> str:
    """Return a compact language code from Qwen/MLX result values."""
    if isinstance(language, (list, tuple)):
        values = [language_code(item) for item in language if item]
        return values[0] if values and len(set(values)) == 1 else ",".join(dict.fromkeys(values))
    value = str(language or "").strip()
    if not value:
        return "unknown"
    lowered = value.lower()
    return LANGUAGE_CODES.get(lowered, lowered)


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _timestamp_items(result: Any) -> list[Any]:
    stamps = _get(result, "time_stamps") or _get(result, "timestamps") or []
    if hasattr(stamps, "items") and not isinstance(stamps, dict):
        return list(stamps.items)
    if isinstance(stamps, dict):
        return list(stamps.get("items") or [])
    return list(stamps)


def _join_units(units: Iterable[str], lang: str) -> str:
    values = [str(unit).strip() for unit in units if str(unit).strip()]
    if lang in NO_SPACE_LANGUAGES:
        return "".join(values)
    text = " ".join(values)
    return re.sub(r"\s+([,.;:!?])", r"\1", text)


def _segments_from_words(words: list[dict[str, Any]], lang: str) -> list[dict[str, Any]]:
    if not words:
        return []
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        previous = current[-1] if current else None
        gap = word["start"] - previous["end"] if previous else 0.0
        if current and gap >= 0.8:
            groups.append(current)
            current = []
        current.append(word)
        text = _join_units((item["word"] for item in current), lang)
        duration = word["end"] - current[0]["start"]
        max_chars = 26 if lang in NO_SPACE_LANGUAGES else 70
        if duration >= 6.0 or len(text) >= max_chars or SENTENCE_END.search(word["word"]):
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    return [
        {
            "id": index,
            "start": group[0]["start"],
            "end": group[-1]["end"],
            "text": _join_units((item["word"] for item in group), lang),
            "words": group,
        }
        for index, group in enumerate(groups)
    ]


def build_transcript_payload(
    result: Any,
    *,
    model_path: str,
    aligner_path: str | None,
    device: str,
    audio_duration: float | None = None,
) -> dict[str, Any]:
    """Normalize official qwen-asr or MLX-Audio results for OpenMontage."""
    text = str(_get(result, "text", "") or "").strip()
    lang = language_code(_get(result, "language", ""))
    words = []
    for item in _timestamp_items(result):
        unit = str(_get(item, "text", _get(item, "word", "")) or "").strip()
        if not unit:
            continue
        words.append(
            {
                "word": unit,
                "start": round(float(_get(item, "start_time", _get(item, "start", 0.0))), 3),
                "end": round(float(_get(item, "end_time", _get(item, "end", 0.0))), 3),
                "probability": 1.0,
            }
        )

    segments = _segments_from_words(words, lang)
    if not segments:
        source_segments = list(_get(result, "segments", []) or [])
        for index, segment in enumerate(source_segments):
            segment_text = str(_get(segment, "text", "") or "").strip()
            if segment_text:
                segments.append(
                    {
                        "id": index,
                        "start": round(float(_get(segment, "start", 0.0)), 3),
                        "end": round(float(_get(segment, "end", audio_duration or 0.0)), 3),
                        "text": segment_text,
                    }
                )
        if not segments and text:
            segments = [{"id": 0, "start": 0.0, "end": round(float(audio_duration or 0.0), 3), "text": text}]

    duration = max((word["end"] for word in words), default=0.0)
    duration = max(duration, max((segment["end"] for segment in segments), default=0.0), float(audio_duration or 0.0))
    return {
        "segments": segments,
        "word_timestamps": words,
        "language": lang,
        "duration_seconds": round(duration, 3),
        "text": text,
        "backend": "qwen3-asr",
        "runtime": "mlx-audio",
        "model_path": str(model_path),
        "aligner_path": str(aligner_path) if aligner_path else None,
        "device": device,
    }


def transcribe_mlx(
    audio_path: Path,
    model_path: Path,
    aligner_path: Path | None,
    language: str | None,
    *,
    chunk_seconds: float = 280.0,
    max_tokens: int = 8192,
) -> dict[str, Any]:
    """Run Qwen ASR and align every <=5 minute chunk with native MLX."""
    with prepare_audio_input(audio_path) as prepared_audio_path:
        return _transcribe_mlx_audio(
            prepared_audio_path,
            model_path,
            aligner_path,
            language,
            chunk_seconds=chunk_seconds,
            max_tokens=max_tokens,
        )


def _transcribe_mlx_audio(
    audio_path: Path,
    model_path: Path,
    aligner_path: Path | None,
    language: str | None,
    *,
    chunk_seconds: float = 280.0,
    max_tokens: int = 8192,
) -> dict[str, Any]:
    """Transcribe a WAV path already prepared for MLX-Audio.

    Split long inputs by exact PCM frame counts before calling MLX-Audio.  Its
    internal long-file chunk timestamps can lose a small amount at every chunk
    boundary; trusting those offsets causes an accumulating subtitle drift.
    """
    from mlx_audio.stt import load
    from mlx_audio.stt.utils import load_audio

    started = time.monotonic()
    qwen_language = normalize_language(language)
    asr_model = load(str(model_path))
    aligner = load(str(aligner_path)) if aligner_path else None
    detected_languages: list[Any] = []
    transcript_parts: list[str] = []
    raw_segments: list[Any] = []
    aligned_items: list[Any] = []
    chunk_limit = min(max(float(chunk_seconds), 1.0), 280.0)

    with wave.open(str(audio_path), "rb") as source_wave:
        sample_rate = source_wave.getframerate()
        total_frames = source_wave.getnframes()
        frames_per_chunk = max(1, int(round(chunk_limit * sample_rate)))
        params = source_wave.getparams()
        with tempfile.TemporaryDirectory(prefix="qwen3-asr-chunks-") as temp_dir:
            frame_offset = 0
            chunk_index = 0
            while frame_offset < total_frames:
                frame_count = min(frames_per_chunk, total_frames - frame_offset)
                pcm = source_wave.readframes(frame_count)
                chunk_path = Path(temp_dir) / f"chunk-{chunk_index:05d}.wav"
                with wave.open(str(chunk_path), "wb") as chunk_wave:
                    chunk_wave.setparams(params)
                    chunk_wave.writeframes(pcm)

                chunk_offset = frame_offset / sample_rate
                result = asr_model.generate(
                    str(chunk_path),
                    language=qwen_language,
                    chunk_duration=chunk_limit,
                    max_tokens=max_tokens,
                    temperature=0.0,
                )
                text = str(_get(result, "text", "") or "").strip()
                if text:
                    transcript_parts.append(text)
                detected = _get(result, "language", qwen_language)
                if isinstance(detected, (list, tuple)):
                    detected = next((item for item in detected if item), qwen_language)
                detected_languages.append(detected)
                align_language = normalize_language(str(detected)) or qwen_language
                chunk_waveform = load_audio(str(chunk_path))

                for segment in list(_get(result, "segments", []) or []):
                    segment_text = str(_get(segment, "text", "") or "").strip()
                    if not segment_text:
                        continue
                    start = float(_get(segment, "start", 0.0))
                    end = float(_get(segment, "end", start))
                    raw_segments.append(SimpleNamespace(
                        text=segment_text,
                        start=round(chunk_offset + start, 3),
                        end=round(chunk_offset + end, 3),
                    ))
                    if not aligner:
                        continue
                    if not align_language:
                        raise RuntimeError(
                            "Qwen3-ASR did not return a language required by ForcedAligner"
                        )
                    audio_slice = chunk_waveform[
                        int(start * 16000) : int(end * 16000)
                    ]
                    segment_language = (
                        normalize_language(_get(segment, "language")) or align_language
                    )
                    aligned = aligner.generate(
                        audio=audio_slice, text=segment_text, language=segment_language
                    )
                    items = list(getattr(aligned, "items", aligned))
                    aligned_items.extend(
                        SimpleNamespace(
                            text=_get(item, "text", ""),
                            start_time=round(
                                float(_get(item, "start_time", 0.0))
                                + chunk_offset + start,
                                3,
                            ),
                            end_time=round(
                                float(_get(item, "end_time", 0.0))
                                + chunk_offset + start,
                                3,
                            ),
                        )
                        for item in items
                    )

                frame_offset += frame_count
                chunk_index += 1

    detected = next((item for item in detected_languages if item), qwen_language)
    audio_duration = total_frames / sample_rate
    normalized = SimpleNamespace(
        text=" ".join(transcript_parts),
        language=detected,
        segments=raw_segments,
        time_stamps=aligned_items,
    )
    payload = build_transcript_payload(
        normalized,
        model_path=str(model_path),
        aligner_path=str(aligner_path) if aligner_path else None,
        device="mlx",
        audio_duration=audio_duration,
    )
    payload["inference_seconds"] = round(time.monotonic() - started, 3)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local Qwen3-ASR with optional ForcedAligner")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", type=Path, default=Path(DEFAULT_ASR_MODEL))
    parser.add_argument("--aligner", type=Path, default=Path(DEFAULT_ALIGNER_MODEL))
    parser.add_argument("--no-aligner", action="store_true")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--chunk-seconds", type=float, default=280.0)
    parser.add_argument("--max-tokens", type=int, default=8192)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file not found: {args.input}")
    if not args.model.is_dir():
        raise SystemExit(f"Qwen3-ASR model not found: {args.model}")
    aligner = None if args.no_aligner else args.aligner
    if aligner and not aligner.is_dir():
        raise SystemExit(f"Qwen3-ForcedAligner model not found: {aligner}")
    payload = transcribe_mlx(
        args.input,
        args.model,
        aligner,
        args.language,
        chunk_seconds=args.chunk_seconds,
        max_tokens=args.max_tokens,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
