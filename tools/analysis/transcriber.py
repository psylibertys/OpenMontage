"""Transcription tool wrapping Qwen3-ASR or faster-whisper / WhisperX.

Provides speech-to-text with word-level timestamps and optional speaker
diarization. Falls back gracefully when GPU or diarization dependencies
are not available.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ResumeSupport,
    ToolResult,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class Transcriber(BaseTool):
    name = "transcriber"
    version = "0.2.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "qwen3-asr/whisperx"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = []
    install_instructions = (
        "conda create -n qwen3-asr python=3.12 && conda run -n qwen3-asr pip install mlx-audio\n"
        "pip install faster-whisper  # Legacy CPU backend\n"
        "pip install faster-whisper[gpu]  # GPU mode (requires CUDA)\n"
        "pip install whisperx  # For diarization support"
    )
    agent_skills = ["speech-to-text"]

    capabilities = [
        "transcribe",
        "word_timestamps",
        "diarization",
        "language_detection",
        "qwen3_asr",
        "forced_alignment",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string", "description": "Path to audio or video file"},
            "backend": {
                "type": "string",
                "enum": ["auto", "qwen3-asr", "faster-whisper"],
                "default": "auto",
            },
            "model_size": {
                "type": "string",
                "enum": ["tiny", "base", "small", "medium", "large-v2", "large-v3"],
                "default": "base",
            },
            "language": {"type": "string", "description": "ISO 639-1 language code, or null for auto-detect"},
            "diarize": {"type": "boolean", "default": False},
            "qwen_model_path": {"type": "string"},
            "qwen_aligner_path": {"type": "string"},
            "qwen_python": {"type": "string", "description": "Python executable containing mlx-audio"},
            "qwen_conda_env": {"type": "string", "default": "qwen3-asr"},
            "align_timestamps": {"type": "boolean", "default": True},
            "timeout_seconds": {"type": "integer", "default": 7200},
            "output_dir": {"type": "string", "description": "Directory for output files"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "segments": {"type": "array"},
            "word_timestamps": {"type": "array"},
            "language": {"type": "string"},
            "duration_seconds": {"type": "number"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2,
        ram_mb=2048,
        vram_mb=0,  # CPU by default; GPU optional
        disk_mb=500,
        network_required=False,
    )

    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["MemoryError"])
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = ["input_path", "backend", "model_size", "language"]
    side_effects = ["writes transcript JSON to output_dir"]
    fallback = None
    user_visible_verification = [
        "Check transcript text against source audio",
        "Verify word timestamps align with speech",
    ]

    def get_status(self) -> ToolStatus:
        if self._qwen_runtime_available():
            return ToolStatus.AVAILABLE
        try:
            import faster_whisper  # noqa: F401
            return ToolStatus.AVAILABLE
        except ImportError:
            return ToolStatus.UNAVAILABLE

    def _qwen_runtime_available(self) -> bool:
        python = os.environ.get("QWEN3_ASR_PYTHON")
        if python and Path(python).is_file():
            return True
        conda = shutil.which("conda")
        if not conda:
            return False
        env_python = Path(conda).resolve().parent.parent / "envs" / "qwen3-asr" / "bin" / "python"
        return env_python.is_file()

    def _has_diarization(self) -> bool:
        try:
            import whisperx  # noqa: F401
            return True
        except ImportError:
            return False

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Rough estimate: ~0.5x real-time on CPU for 'base' model."""
        return 60.0  # conservative default

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        backend = inputs.get("backend", "auto")
        model_size = inputs.get("model_size", "base")
        language = inputs.get("language")
        diarize = inputs.get("diarize", False)
        output_dir = Path(inputs.get("output_dir", input_path.parent))

        if not input_path.exists():
            return ToolResult(success=False, error=f"Input file not found: {input_path}")

        if backend not in {"auto", "qwen3-asr", "faster-whisper"}:
            return ToolResult(success=False, error=f"Unknown transcription backend: {backend}")

        output_dir.mkdir(parents=True, exist_ok=True)

        if backend in {"auto", "qwen3-asr"}:
            qwen_result = self._execute_qwen(input_path, output_dir, inputs)
            if qwen_result.success or backend == "qwen3-asr":
                return qwen_result

        return self._execute_whisper(input_path, output_dir, inputs)

    def _execute_qwen(
        self,
        input_path: Path,
        output_dir: Path,
        inputs: dict[str, Any],
    ) -> ToolResult:
        from tools.analysis.qwen3_asr_runner import DEFAULT_ALIGNER_MODEL, DEFAULT_ASR_MODEL

        model_path = Path(inputs.get("qwen_model_path") or os.environ.get("QWEN3_ASR_MODEL_DIR") or DEFAULT_ASR_MODEL)
        aligner_path = Path(inputs.get("qwen_aligner_path") or os.environ.get("QWEN3_ALIGNER_MODEL_DIR") or DEFAULT_ALIGNER_MODEL)
        if not model_path.is_dir():
            return ToolResult(success=False, error=f"Qwen3-ASR model not found: {model_path}")
        if inputs.get("align_timestamps", True) and not aligner_path.is_dir():
            return ToolResult(success=False, error=f"Qwen3-ForcedAligner model not found: {aligner_path}")

        runner = Path(__file__).with_name("qwen3_asr_runner.py")
        explicit_python = inputs.get("qwen_python") or os.environ.get("QWEN3_ASR_PYTHON")
        if explicit_python:
            command = [str(explicit_python), str(runner)]
        else:
            conda = shutil.which("conda")
            if not conda:
                return ToolResult(success=False, error="Qwen runtime unavailable: set QWEN3_ASR_PYTHON or install conda")
            command = [conda, "run", "--no-capture-output", "-n", inputs.get("qwen_conda_env", "qwen3-asr"), "python", str(runner)]

        output_path = output_dir / f"{input_path.stem}_transcript.json"
        command.extend([
            "--input", str(input_path),
            "--output", str(output_path),
            "--model", str(model_path),
            "--language", str(inputs.get("language") or "auto"),
        ])
        if inputs.get("align_timestamps", True):
            command.extend(["--aligner", str(aligner_path)])
        else:
            command.append("--no-aligner")

        started = time.time()
        try:
            completed = subprocess.run(
                command,
                cwd=Path(__file__).resolve().parents[2],
                capture_output=True,
                text=True,
                timeout=int(inputs.get("timeout_seconds", 7200)),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ToolResult(success=False, error=f"Qwen3-ASR execution failed: {exc}")
        if completed.returncode != 0 or not output_path.is_file():
            detail = (completed.stderr or completed.stdout or "unknown error").strip()[-3000:]
            return ToolResult(success=False, error=f"Qwen3-ASR execution failed: {detail}")
        try:
            data = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ToolResult(success=False, error=f"Invalid Qwen3-ASR output: {exc}")
        data["source_file"] = str(input_path.resolve())
        data["source_start"] = 0.0
        data["source_end"] = float(data.get("duration_seconds") or 0.0)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return ToolResult(
            success=True,
            data=data,
            artifacts=[str(output_path)],
            duration_seconds=round(time.time() - started, 2),
            model=str(model_path),
        )

    def _execute_whisper(
        self,
        input_path: Path,
        output_dir: Path,
        inputs: dict[str, Any],
    ) -> ToolResult:
        model_size = inputs.get("model_size", "base")
        language = inputs.get("language")
        diarize = inputs.get("diarize", False)
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            return ToolResult(
                success=False,
                error="faster-whisper is not installed. Run: pip install faster-whisper",
            )

        start = time.time()

        # Load model (CPU by default, CUDA if available)
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
        except ImportError:
            device = "cpu"
            compute_type = "int8"

        model = WhisperModel(model_size, device=device, compute_type=compute_type)

        # Transcribe
        segments_iter, info = model.transcribe(
            str(input_path),
            language=language,
            word_timestamps=True,
            vad_filter=True,
        )

        segments = []
        word_timestamps = []

        for seg in segments_iter:
            seg_data = {
                "id": seg.id,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
            }

            if seg.words:
                words = []
                for w in seg.words:
                    word_entry = {
                        "word": w.word,
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "probability": round(w.probability, 3),
                    }
                    words.append(word_entry)
                    word_timestamps.append(word_entry)
                seg_data["words"] = words

            segments.append(seg_data)

        detected_language = language or info.language
        duration = info.duration

        # Optional diarization pass
        if diarize and self._has_diarization():
            segments = self._apply_diarization(
                str(input_path), segments, detected_language
            )

        elapsed = time.time() - start

        result_data = {
            "segments": segments,
            "word_timestamps": word_timestamps,
            "language": detected_language,
            "duration_seconds": round(duration, 3),
            "model_size": model_size,
            "device": device,
            "backend": "faster-whisper",
            "source_file": str(input_path.resolve()),
            "source_start": 0.0,
            "source_end": round(duration, 3),
        }

        # Write transcript JSON
        output_path = output_dir / f"{input_path.stem}_transcript.json"
        output_path.write_text(json.dumps(result_data, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data=result_data,
            artifacts=[str(output_path)],
            duration_seconds=round(elapsed, 2),
        )

    def _apply_diarization(
        self,
        audio_path: str,
        segments: list[dict],
        language: str,
    ) -> list[dict]:
        """Apply WhisperX diarization to assign speaker labels."""
        try:
            import whisperx

            # Load audio for alignment
            audio = whisperx.load_audio(audio_path)

            # Align segments with word timestamps
            align_model, align_metadata = whisperx.load_align_model(
                language_code=language, device="cpu"
            )
            aligned = whisperx.align(
                segments, align_model, align_metadata, audio, device="cpu"
            )

            # Diarize
            import os
            hf_token = os.environ.get("HF_TOKEN")
            if not hf_token:
                # Can't diarize without HuggingFace token for pyannote
                return segments

            diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=hf_token, device="cpu"
            )
            diarize_segments = diarize_model(audio)
            result = whisperx.assign_word_speakers(diarize_segments, aligned)

            return result.get("segments", segments)
        except Exception:
            # Diarization is best-effort; return original segments on failure
            return segments
