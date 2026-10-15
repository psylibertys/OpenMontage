"""Hard delivery gate for clip-factory outputs.

The audit deliberately reads the final MP4.  Intermediate audio, Remotion
props, and one-second screenshots cannot prove that the delivered file has
synchronized captions or a usable frame-zero cover.
"""

from __future__ import annotations

import difflib
import json
import math
import shutil
import statistics
import time
import unicodedata
from pathlib import Path
from typing import Any

from schemas.artifacts import validate_artifact
from tools.analysis.transcriber import Transcriber
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


def _token(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return "".join(char for char in text if not unicodedata.category(char).startswith("P"))


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return math.inf
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * ratio) - 1))
    return ordered[index]


def compare_word_timings(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    *,
    minimum_matched_ratio: float = 0.70,
    maximum_p90_error_seconds: float = 0.30,
) -> dict[str, Any]:
    """Match word sequences and measure absolute start-time error."""

    expected_rows = [item for item in expected if _token(item.get("word"))]
    actual_rows = [item for item in actual if _token(item.get("word"))]
    matcher = difflib.SequenceMatcher(
        None,
        [_token(item.get("word")) for item in expected_rows],
        [_token(item.get("word")) for item in actual_rows],
        autojunk=False,
    )
    deltas: list[float] = []
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            expected_word = expected_rows[block.a + offset]
            actual_word = actual_rows[block.b + offset]
            expected_start = (
                float(expected_word["startMs"]) / 1000
                if "startMs" in expected_word
                else float(expected_word["start"])
            )
            deltas.append(expected_start - float(actual_word["start"]))

    absolute = [abs(value) for value in deltas]
    matched_ratio = len(deltas) / max(1, len(expected_rows))
    p90 = _percentile(absolute, 0.90)
    passed = matched_ratio >= minimum_matched_ratio and p90 <= maximum_p90_error_seconds
    return {
        "status": "pass" if passed else "fail",
        "expected_words": len(expected_rows),
        "actual_words": len(actual_rows),
        "matched_words": len(deltas),
        "matched_ratio": round(matched_ratio, 4),
        "median_signed_delta_seconds": round(statistics.median(deltas), 4) if deltas else None,
        "median_absolute_error_seconds": round(statistics.median(absolute), 4) if absolute else None,
        "p90_absolute_error_seconds": round(p90, 4) if math.isfinite(p90) else None,
        "max_absolute_error_seconds": round(max(absolute), 4) if absolute else None,
    }


class ClipDeliveryAudit(BaseTool):
    """Validate final clip audio/captions and frame-zero cover evidence."""

    name = "clip_delivery_audit"
    version = "1.0.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "local"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    dependencies = ["binary:ffmpeg", "binary:ffprobe"]
    install_instructions = "Requires FFmpeg/FFprobe and the configured transcription backend."
    agent_skills = ["ffmpeg", "speech-to-text"]
    capabilities = [
        "audit_final_clip_delivery",
        "verify_frame_zero_cover",
        "verify_final_audio_subtitle_sync",
    ]
    best_for = ["blocking clip-factory delivery when covers or subtitles are wrong"]
    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=4096, disk_mb=2048)
    side_effects = ["writes exact frame-zero images, covers, ASR output, and an audit artifact"]
    user_visible_verification = [
        "Open every extracted frame-zero image and confirm the expected hook is fully visible",
        "Review matched-word ratio and p90 timing error from the final MP4 audio",
    ]

    input_schema = {
        "type": "object",
        "required": ["clips", "output_dir", "artifact_path"],
        "properties": {
            "clips": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": [
                        "clip_id",
                        "video_path",
                        "captions_path",
                        "expected_hook_title",
                        "frame_zero_title_visible",
                    ],
                    "properties": {
                        "clip_id": {"type": "string"},
                        "video_path": {"type": "string"},
                        "captions_path": {"type": "string"},
                        "expected_hook_title": {"type": "string", "minLength": 1},
                        "frame_zero_title_visible": {"type": "boolean"},
                        "cover_path": {"type": "string"},
                    },
                },
            },
            "output_dir": {"type": "string"},
            "artifact_path": {"type": "string"},
            "backend": {"type": "string", "default": "qwen3-asr"},
            "language": {"type": "string", "default": "zh"},
            "minimum_matched_ratio": {"type": "number", "default": 0.70},
            "maximum_p90_error_seconds": {"type": "number", "default": 0.30},
        },
    }

    def _transcribe(self, video: Path, output_dir: Path, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        result = Transcriber().execute(
            {
                "input_path": str(video),
                "backend": inputs.get("backend", "qwen3-asr"),
                "language": inputs.get("language", "zh"),
                "align_timestamps": True,
                "output_dir": str(output_dir),
            }
        )
        if not result.success:
            raise RuntimeError(result.error or "final MP4 transcription failed")
        return result.data["word_timestamps"]

    def _probe(self, video: Path) -> dict[str, Any]:
        result = self.run_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
                "-of",
                "json",
                str(video),
            ]
        )
        payload = json.loads(result.stdout)
        video_stream = next(item for item in payload["streams"] if item["codec_type"] == "video")
        audio_stream = next(item for item in payload["streams"] if item["codec_type"] == "audio")
        numerator, denominator = (int(value) for value in video_stream["r_frame_rate"].split("/"))
        return {
            "duration_seconds": round(float(payload["format"]["duration"]), 3),
            "width": int(video_stream["width"]),
            "height": int(video_stream["height"]),
            "fps": numerator / denominator,
            "video_codec": video_stream["codec_name"],
            "audio_codec": audio_stream["codec_name"],
            "sample_rate": int(audio_stream["sample_rate"]),
            "channels": int(audio_stream["channels"]),
        }

    def _extract_frame_zero(self, video: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.run_command(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(video),
                "-vf",
                "select=eq(n\\,0)",
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(destination),
            ]
        )
        if not destination.is_file():
            raise RuntimeError(f"frame-zero extraction produced no image: {destination}")

    @staticmethod
    def _load_expected_words(path: Path) -> list[dict[str, Any]]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        words = payload.get("words") if isinstance(payload, dict) else payload
        if not isinstance(words, list):
            raise ValueError(f"caption JSON has no words array: {path}")
        return words

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        output_dir = Path(inputs["output_dir"])
        artifact_path = Path(inputs["artifact_path"])
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        minimum_ratio = float(inputs.get("minimum_matched_ratio", 0.70))
        maximum_p90 = float(inputs.get("maximum_p90_error_seconds", 0.30))
        reports: list[dict[str, Any]] = []

        for clip in inputs["clips"]:
            clip_id = clip["clip_id"]
            video = Path(clip["video_path"])
            captions = Path(clip["captions_path"])
            issues: list[str] = []
            frame_zero = output_dir / "frame-zero" / f"{clip_id}.jpg"
            cover = Path(clip.get("cover_path") or output_dir / "covers" / f"{clip_id}.jpg")
            try:
                if not video.is_file():
                    raise FileNotFoundError(f"video not found: {video}")
                if not captions.is_file():
                    raise FileNotFoundError(f"captions not found: {captions}")
                technical = self._probe(video)
                if (technical["width"], technical["height"]) != (1080, 1920):
                    issues.append("resolution_not_1080x1920")
                if abs(technical["fps"] - 30) > 0.01:
                    issues.append("fps_not_30")
                if technical["video_codec"] != "h264" or technical["audio_codec"] != "aac":
                    issues.append("codec_not_h264_aac")
                if technical["sample_rate"] != 48000 or technical["channels"] != 1:
                    issues.append("audio_not_48khz_mono")

                self._extract_frame_zero(video, frame_zero)
                title_visible = bool(clip["frame_zero_title_visible"])
                if not title_visible:
                    issues.append("expected_hook_not_visible_at_frame_zero")
                else:
                    cover.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(frame_zero, cover)

                actual_words = self._transcribe(video, output_dir / "transcripts" / clip_id, inputs)
                timing = compare_word_timings(
                    self._load_expected_words(captions),
                    actual_words,
                    minimum_matched_ratio=minimum_ratio,
                    maximum_p90_error_seconds=maximum_p90,
                )
                if timing["status"] != "pass":
                    issues.append("final_audio_subtitle_sync_failed")
            except Exception as exc:
                technical = {}
                timing = {"status": "fail"}
                title_visible = bool(clip.get("frame_zero_title_visible", False))
                issues.append(str(exc))

            status = "pass" if not issues else "fail"
            reports.append(
                {
                    "clip_id": clip_id,
                    "video_path": str(video),
                    "cover_path": str(cover),
                    "technical": technical,
                    "frame_zero": {
                        "sample_path": str(frame_zero),
                        "expected_hook_title": clip["expected_hook_title"],
                        "title_visible": title_visible,
                        "review_method": "human_visual_exact_frame_n0",
                    },
                    "subtitle_sync": timing,
                    "status": status,
                    "issues": issues,
                }
            )

        audit = {
            "version": "1.0",
            "status": "pass" if all(item["status"] == "pass" for item in reports) else "fail",
            "acceptance": {
                "minimum_matched_ratio": minimum_ratio,
                "maximum_p90_error_seconds": maximum_p90,
                "frame_zero_requires_expected_hook": True,
                "standalone_cover_required": True,
            },
            "outputs": reports,
            "failed_clip_ids": [item["clip_id"] for item in reports if item["status"] != "pass"],
        }
        validate_artifact("clip_delivery_audit", audit)
        artifact_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts = [str(artifact_path)]
        artifacts.extend(item["frame_zero"]["sample_path"] for item in reports)
        artifacts.extend(item["cover_path"] for item in reports if item["status"] == "pass")
        success = audit["status"] == "pass"
        return ToolResult(
            success=success,
            data={"clip_delivery_audit": audit},
            artifacts=artifacts,
            error=None if success else f"clip delivery audit failed: {audit['failed_clip_ids']}",
            duration_seconds=round(time.monotonic() - started, 2),
        )
