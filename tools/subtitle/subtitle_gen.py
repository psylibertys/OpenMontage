"""Subtitle generation tool.

Converts word-level timestamps from the transcriber into SRT, VTT,
or caption JSON formats. Pure Python — no external dependencies beyond
the standard library.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
)


class SubtitleGen(BaseTool):
    name = "subtitle_gen"
    version = "0.2.0"
    tier = ToolTier.CORE
    capability = "subtitle"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = []  # pure Python
    install_instructions = "No external dependencies required."
    agent_skills = ["remotion-best-practices"]

    capabilities = [
        "generate_srt",
        "generate_vtt",
        "generate_caption_json",
        "generate_remotion_word_json",
        "rebase_edl",
    ]

    input_schema = {
        "type": "object",
        "required": ["segments"],
        "properties": {
            "segments": {
                "type": "array",
                "description": "Transcript segments from transcriber (with words and timestamps)",
            },
            "format": {
                "type": "string",
                "enum": ["srt", "vtt", "json", "remotion_json"],
                "default": "srt",
            },
            "output_path": {"type": "string"},
            "max_chars_per_line": {"type": "integer", "default": 42},
            "max_words_per_cue": {"type": "integer", "default": 8},
            "highlight_style": {
                "type": "string",
                "enum": ["none", "word_by_word", "karaoke"],
                "default": "none",
            },
            "corrections": {
                "type": "object",
                "description": (
                    "Dictionary of word corrections for common ASR misrecognitions. "
                    "Keys are the wrong word (case-insensitive), values are the "
                    "correct replacement. Applied before generating subtitles. "
                    "Example: {\"cloud\": \"Claude\", \"co-pilot\": \"Copilot\"}."
                ),
            },
            "edl_operations": {
                "type": "array",
                "description": "KEEP/CUT/BLEEP operations in source timebase.",
            },
            "preserve_keep_order": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Preserve KEEP operations in declared playback order. Use for "
                    "cold opens and other intentional non-chronological EDLs."
                ),
            },
            "allow_overlapping_keeps": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Allow ordered KEEP ranges to replay overlapping source time. "
                    "Keep false for normal cold opens; enable only for an audited, "
                    "intentional repetition."
                ),
            },
            "bleep_replacement": {"type": "string", "default": "[哔]"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=10)
    idempotency_key_fields = ["segments", "format", "max_words_per_cue"]
    side_effects = ["writes subtitle file to output_path"]
    user_visible_verification = [
        "Play video with generated subtitles and verify timing",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        segments = inputs["segments"]
        fmt = inputs.get("format", "srt")
        max_words = inputs.get("max_words_per_cue", 8)
        max_chars = inputs.get("max_chars_per_line", 42)
        highlight_style = inputs.get("highlight_style", "none")
        output_path = inputs.get("output_path")
        corrections = inputs.get("corrections")
        edl_operations = inputs.get("edl_operations")
        preserve_keep_order = inputs.get("preserve_keep_order", False)
        allow_overlapping_keeps = inputs.get("allow_overlapping_keeps", False)
        bleep_replacement = inputs.get("bleep_replacement", "[哔]")

        start = time.time()

        # Apply word corrections if provided
        if corrections:
            segments = self._apply_corrections(segments, corrections)

        edit_metadata: dict[str, Any] = {}
        if edl_operations:
            segments, edit_metadata = self._rebase_segments_to_edl(
                segments, edl_operations, bleep_replacement, preserve_keep_order,
                allow_overlapping_keeps,
            )

        # Build cues from word-level timestamps
        cues = self._build_cues(segments, max_words, max_chars)

        if fmt == "srt":
            content = self._render_srt(cues, highlight_style)
            ext = ".srt"
        elif fmt == "vtt":
            content = self._render_vtt(cues, highlight_style)
            ext = ".vtt"
        elif fmt == "json":
            content = json.dumps(
                {
                    "cues": cues,
                    "highlight_style": highlight_style,
                    **edit_metadata,
                },
                ensure_ascii=False,
                indent=2,
            )
            ext = ".caption.json"
        elif fmt == "remotion_json":
            words = [
                {
                    "word": word["word"].strip(),
                    "startMs": round(word["start"] * 1000),
                    "endMs": round(word["end"] * 1000),
                }
                for cue in cues
                for word in cue.get("words", [])
            ]
            content = json.dumps(
                {
                    "words": words,
                    "captions": [
                        {
                            "text": word["word"],
                            "startMs": word["startMs"],
                            "endMs": word["endMs"],
                            "timestampMs": word["startMs"],
                            "confidence": 1.0,
                        }
                        for word in words
                    ],
                    "durationMs": round(edit_metadata.get("duration_seconds", 0) * 1000)
                    if edit_metadata
                    else (words[-1]["endMs"] if words else 0),
                    **edit_metadata,
                },
                ensure_ascii=False,
                indent=2,
            )
            ext = ".captions.json"
        else:
            return ToolResult(success=False, error=f"Unknown format: {fmt}")

        if output_path is None:
            output_path = f"subtitles{ext}"
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")

        elapsed = time.time() - start

        return ToolResult(
            success=True,
            data={
                "format": fmt,
                "cue_count": len(cues),
                "output": str(out),
                **edit_metadata,
            },
            artifacts=[str(out)],
            duration_seconds=round(elapsed, 2),
        )

    @staticmethod
    def _apply_corrections(
        segments: list[dict], corrections: dict[str, str]
    ) -> list[dict]:
        """Apply word-level corrections to transcript segments.

        Handles case-insensitive matching and preserves punctuation.
        """
        import copy

        corr = {k.lower(): v for k, v in corrections.items()}
        result = copy.deepcopy(segments)

        for seg in result:
            words = seg.get("words", [])
            for w in words:
                raw = w.get("word", "").strip()
                # Strip punctuation for lookup, preserve it
                stripped = raw.lower().rstrip(".,!?;:'\"")
                if stripped in corr:
                    trailing = raw[len(stripped):]
                    w["word"] = corr[stripped] + trailing
            # Also fix segment-level text
            if "text" in seg and words:
                seg["text"] = " ".join(w["word"] for w in words)
            elif "text" in seg:
                for wrong, right in corr.items():
                    import re as _re
                    seg["text"] = _re.sub(
                        r"\b" + _re.escape(wrong) + r"\b",
                        right,
                        seg["text"],
                        flags=_re.IGNORECASE,
                    )

        return result

    def _build_cues(
        self, segments: list[dict], max_words: int, max_chars: int
    ) -> list[dict]:
        """Group words into display cues respecting max_words and max_chars."""
        # Collect all words with timestamps
        all_words = []
        for seg in segments:
            words = seg.get("words", [])
            if words:
                all_words.extend(words)
            elif "text" in seg:
                # Fallback: segment-level only (no word timestamps)
                all_words.append({
                    "word": seg["text"],
                    "start": seg["start"],
                    "end": seg["end"],
                })

        if not all_words:
            return []

        cues = []
        buf: list[dict] = []
        buf_text = ""

        for w in all_words:
            word_text = w["word"].strip()
            candidate = self._join_word_text([*buf, w])

            if buf and (len(buf) >= max_words or len(candidate) > max_chars):
                cues.append({
                    "index": len(cues) + 1,
                    "start": buf[0]["start"],
                    "end": buf[-1]["end"],
                    "text": buf_text,
                    "words": [
                        {"word": b["word"].strip(), "start": b["start"], "end": b["end"]}
                        for b in buf
                    ],
                })
                buf = []
                buf_text = ""

            buf.append(w)
            buf_text = self._join_word_text(buf)

        # Flush remaining
        if buf:
            cues.append({
                "index": len(cues) + 1,
                "start": buf[0]["start"],
                "end": buf[-1]["end"],
                "text": buf_text,
                "words": [
                    {"word": b["word"].strip(), "start": b["start"], "end": b["end"]}
                    for b in buf
                ],
            })

        return cues

    @staticmethod
    def _join_word_text(words: list[dict]) -> str:
        """Join ASR tokens without inserting spaces between Chinese characters."""
        result = ""
        for item in words:
            token = str(item.get("word", "")).strip()
            if not token:
                continue
            if result and re.search(r"[A-Za-z0-9]$", result) and re.match(r"^[A-Za-z0-9]", token):
                result += " "
            result += token
        return result

    @classmethod
    def _rebase_segments_to_edl(
        cls,
        segments: list[dict],
        operations: list[dict],
        bleep_replacement: str,
        preserve_keep_order: bool = False,
        allow_overlapping_keeps: bool = False,
    ) -> tuple[list[dict], dict[str, Any]]:
        """Apply an EDL and convert source timestamps to a contiguous clip timebase."""
        keep_intervals = [
            (float(op["start"]), float(op["end"]))
            for op in operations
            if op.get("action") == "KEEP" and float(op["end"]) > float(op["start"])
        ]
        if preserve_keep_order and not allow_overlapping_keeps:
            for index, (start, end) in enumerate(keep_intervals):
                for later_start, later_end in keep_intervals[index + 1:]:
                    if min(end, later_end) - max(start, later_start) > 0.001:
                        raise ValueError(
                            "Ordered KEEP ranges overlap and would replay source speech; "
                            "subtract the cold-open interval from the main body or set "
                            "allow_overlapping_keeps=true for audited intentional repetition"
                        )
        keep = keep_intervals if preserve_keep_order else cls._merge_intervals(keep_intervals)
        cuts = cls._merge_intervals(
            (float(op["start"]), float(op["end"]))
            for op in operations
            if op.get("action") == "CUT" and float(op["end"]) > float(op["start"])
        )
        timeline = cls._subtract_intervals(keep, cuts)
        source_words = [word for seg in segments for word in seg.get("words", [])]

        bleep_sources = [
            (float(op["start"]), float(op["end"]), op.get("subtitle", bleep_replacement))
            for op in operations
            if op.get("action") == "BLEEP" and float(op["end"]) > float(op["start"])
        ]
        rebased_words: list[dict[str, Any]] = []
        rebased_bleeps: list[dict[str, Any]] = []
        cursor = 0.0

        for interval_start, interval_end in timeline:
            duration = interval_end - interval_start
            active_bleeps: list[tuple[float, float, str]] = []
            for bleep_start, bleep_end, replacement in bleep_sources:
                start = max(interval_start, bleep_start)
                end = min(interval_end, bleep_end)
                if end > start:
                    active_bleeps.append((start, end, replacement))
                    rebased_bleeps.append({
                        "startMs": round((cursor + start - interval_start) * 1000),
                        "endMs": round((cursor + end - interval_start) * 1000),
                        "replacement": replacement,
                    })

            for word in source_words:
                word_start = float(word["start"])
                word_end = float(word["end"])
                midpoint = (word_start + word_end) / 2
                if not interval_start <= midpoint < interval_end:
                    continue
                if any(start <= midpoint < end for start, end, _ in active_bleeps):
                    continue
                rebased_words.append({
                    "word": word.get("word", ""),
                    "start": cursor + max(word_start, interval_start) - interval_start,
                    "end": cursor + min(word_end, interval_end) - interval_start,
                })

            for start, end, replacement in active_bleeps:
                rebased_words.append({
                    "word": replacement,
                    "start": cursor + start - interval_start,
                    "end": cursor + end - interval_start,
                })
            cursor += duration

        rebased_words.sort(key=lambda word: (word["start"], word["end"]))
        result = []
        if rebased_words:
            result = [{
                "start": rebased_words[0]["start"],
                "end": rebased_words[-1]["end"],
                "text": cls._join_word_text(rebased_words),
                "words": rebased_words,
            }]
        return result, {
            "duration_seconds": round(cursor, 6),
            "bleeps": rebased_bleeps,
            "timebase": "clip_relative",
        }

    @staticmethod
    def _merge_intervals(intervals: Any) -> list[tuple[float, float]]:
        merged: list[list[float]] = []
        for start, end in sorted(intervals):
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        return [(start, end) for start, end in merged]

    @staticmethod
    def _subtract_intervals(
        keep: list[tuple[float, float]], cuts: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        result: list[tuple[float, float]] = []
        for keep_start, keep_end in keep:
            pieces = [(keep_start, keep_end)]
            for cut_start, cut_end in cuts:
                next_pieces = []
                for start, end in pieces:
                    if cut_end <= start or cut_start >= end:
                        next_pieces.append((start, end))
                    else:
                        if cut_start > start:
                            next_pieces.append((start, min(cut_start, end)))
                        if cut_end < end:
                            next_pieces.append((max(cut_end, start), end))
                pieces = next_pieces
            result.extend(pieces)
        return result

    def _render_srt(self, cues: list[dict], highlight_style: str = "none") -> str:
        lines = []
        if highlight_style == "word_by_word":
            # Emit one cue per word for word-by-word reveal
            idx = 1
            for cue in cues:
                for word_info in cue.get("words", []):
                    lines.append(str(idx))
                    lines.append(
                        f"{self._ts_srt(word_info['start'])} --> {self._ts_srt(word_info['end'])}"
                    )
                    lines.append(word_info["word"])
                    lines.append("")
                    idx += 1
        elif highlight_style == "karaoke":
            # Show full cue text but bold the active word using SRT HTML tags
            for cue in cues:
                words = cue.get("words", [])
                if not words:
                    lines.append(str(cue["index"]))
                    lines.append(f"{self._ts_srt(cue['start'])} --> {self._ts_srt(cue['end'])}")
                    lines.append(cue["text"])
                    lines.append("")
                    continue
                for wi, word_info in enumerate(words):
                    lines.append(str(cue["index"] * 100 + wi))
                    lines.append(
                        f"{self._ts_srt(word_info['start'])} --> {self._ts_srt(word_info['end'])}"
                    )
                    parts = []
                    for wj, w in enumerate(words):
                        if wj == wi:
                            parts.append(f"<b>{w['word']}</b>")
                        else:
                            parts.append(w["word"])
                    lines.append(" ".join(parts))
                    lines.append("")
        else:
            for cue in cues:
                lines.append(str(cue["index"]))
                lines.append(f"{self._ts_srt(cue['start'])} --> {self._ts_srt(cue['end'])}")
                lines.append(cue["text"])
                lines.append("")
        return "\n".join(lines)

    def _render_vtt(self, cues: list[dict], highlight_style: str = "none") -> str:
        lines = ["WEBVTT", ""]
        if highlight_style == "word_by_word":
            for cue in cues:
                for word_info in cue.get("words", []):
                    lines.append(
                        f"{self._ts_vtt(word_info['start'])} --> {self._ts_vtt(word_info['end'])}"
                    )
                    lines.append(word_info["word"])
                    lines.append("")
        elif highlight_style == "karaoke":
            for cue in cues:
                words = cue.get("words", [])
                if not words:
                    lines.append(f"{self._ts_vtt(cue['start'])} --> {self._ts_vtt(cue['end'])}")
                    lines.append(cue["text"])
                    lines.append("")
                    continue
                for wi, word_info in enumerate(words):
                    lines.append(
                        f"{self._ts_vtt(word_info['start'])} --> {self._ts_vtt(word_info['end'])}"
                    )
                    parts = []
                    for wj, w in enumerate(words):
                        if wj == wi:
                            parts.append(f"<b>{w['word']}</b>")
                        else:
                            parts.append(w["word"])
                    lines.append(" ".join(parts))
                    lines.append("")
        else:
            for cue in cues:
                lines.append(f"{self._ts_vtt(cue['start'])} --> {self._ts_vtt(cue['end'])}")
                lines.append(cue["text"])
                lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _hmsms(seconds: float) -> tuple[int, int, int, int]:
        """Decompose seconds into (h, m, s, ms), rounding to whole ms first.

        Rounding to total milliseconds before splitting the fields lets the
        carry propagate: 0.9995s+ must become the next second (…,000), not a
        malformed 4-digit …,1000 with the seconds field left unincremented.
        """
        total_ms = int(round(max(0.0, seconds) * 1000))
        h, rem = divmod(total_ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        s, ms = divmod(rem, 1_000)
        return h, m, s, ms

    @classmethod
    def _ts_srt(cls, seconds: float) -> str:
        """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
        h, m, s, ms = cls._hmsms(seconds)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @classmethod
    def _ts_vtt(cls, seconds: float) -> str:
        """Format seconds as VTT timestamp: HH:MM:SS.mmm"""
        h, m, s, ms = cls._hmsms(seconds)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
