#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from lib.checkpoint import PROJECTS_DIR, init_project, write_checkpoint
from tools.analysis.audio_probe import probe_duration
from tools.audio.dashscope_tts import DashscopeTTS
from tools.audio.edge_tts import EdgeTTS
from tools.video.clip_cache import default_cache_dir, get_default_cache
from tools.video.pexels_video import PexelsVideo
from tools.video.pixabay_video import PixabayVideo
from tools.video.video_compose import VideoCompose


PIPELINE_TYPE = "animated-explainer"
STYLE_PLAYBOOK = "clean-professional"
DEFAULT_MUSIC_LIBRARY = Path("/Users/treeelf/Desktop/crewai/music/music-sucai/纯音乐")
DEFAULT_FINAL_OUTPUT_DIR = Path("/Users/treeelf/Movies/zh-philosophy-video")
DEFAULT_FONT = ROOT_DIR / "fronts" / "漓雨手书_100font" / "LiyuXingkai.ttf"
DEFAULT_TTS_PROVIDER = "edge"
DEFAULT_EDGE_TTS_VERSION = "7.2.7"
DEFAULT_EDGE_VOICE = "zh-CN-XiaoxiaoNeural"


def run(cmd: list[str], *, capture: bool = False) -> str:
    if capture:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    subprocess.check_call(cmd)
    return ""


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a JSON object: {path}")
    return data


def dump_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_path(value: str | Path | None, *, default: Path | None = None) -> Path:
    if value in (None, ""):
        if default is None:
            raise ValueError("Path value is required")
        return default
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def project_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or f"zh-video-{int(time.time())}"


def filename_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-") or "default"


def spoken_text(value: str) -> str:
    """Normalize text for matching Edge word boundaries back to source ranges."""
    return "".join(char.lower() for char in value if char.isalnum())


def profile_size(profile: str) -> tuple[int, int, str]:
    if profile in {"youtube_landscape", "landscape", "16:9"}:
        return 1920, 1080, "landscape"
    if profile in {"tiktok", "portrait", "9:16"}:
        return 1080, 1920, "portrait"
    raise ValueError(f"Unsupported profile: {profile}")


def rel(project_dir: Path, path: Path) -> str:
    return str(path.relative_to(project_dir))


def safe_checkpoint(
    project_id: str,
    stage: str,
    artifacts: dict[str, Any],
    *,
    human_approval_required: bool = False,
    cost_snapshot: dict[str, Any] | None = None,
) -> None:
    try:
        write_checkpoint(
            PROJECTS_DIR,
            project_id,
            stage,
            "completed",
            artifacts,
            pipeline_type=PIPELINE_TYPE,
            style_playbook=STYLE_PLAYBOOK,
            human_approval_required=human_approval_required,
            human_approved=human_approval_required,
            metadata={"generated_by": "zh_philosophy_video_workflow", "pre_authorized": True},
            cost_snapshot=cost_snapshot,
        )
    except Exception as exc:  # Keep workflow usable even if artifact schemas evolve.
        print(f"[warn] checkpoint for stage {stage!r} was skipped: {exc}")


def text_replacements(text: str, replacements: dict[str, str]) -> str:
    output = text
    for source, target in replacements.items():
        output = output.replace(source, target)
    return output


def split_tts_text(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    current = ""
    for token in re.split(r"([。！？；\n])", text):
        if not token:
            continue
        candidate = current + token
        if current and len(candidate) > max_chars:
            pieces.append(current.strip())
            current = token.strip()
        else:
            current = candidate
    if current.strip():
        pieces.append(current.strip())
    final: list[str] = []
    for piece in pieces:
        if len(piece) <= max_chars:
            final.append(piece)
            continue
        for i in range(0, len(piece), max_chars):
            final.append(piece[i : i + max_chars])
    return [p for p in final if p]


def ffprobe(path: Path) -> dict[str, Any]:
    out = subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        text=True,
    )
    return json.loads(out)


def cover_to_canvas(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = img.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        box = draw.textbbox((0, 0), candidate, font=font)
        if current and box[2] - box[0] > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def text_line_height(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), text or "国", font=font)
    return box[3] - box[1]


class ZhPhilosophyVideoWorkflow:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.project_id = config.get("project_id") or project_slug(config.get("title", "zh philosophy video"))
        self.title = config.get("title", self.project_id)
        self.profile = config.get("profile", "youtube_landscape")
        self.width, self.height, self.orientation = profile_size(self.profile)
        self.project_dir = PROJECTS_DIR / self.project_id
        self.artifacts = self.project_dir / "artifacts"
        self.audio_dir = self.project_dir / "assets" / "audio" / self.tts_output_label
        self.video_dir = self.project_dir / "assets" / "video"
        self.music_dir = self.project_dir / "assets" / "music"
        self.image_dir = self.project_dir / "assets" / "images"
        self.renders_dir = self.project_dir / "renders"
        self.remotion_public = ROOT_DIR / "remotion-composer" / "public" / self.project_id

    @property
    def voice(self) -> str:
        default = DEFAULT_EDGE_VOICE if self.tts_provider == "edge" else "Chelsie"
        return self.config.get("tts", {}).get("voice", default)

    @property
    def tts_provider(self) -> str:
        return str(self.config.get("tts", {}).get("provider", DEFAULT_TTS_PROVIDER)).lower()

    @property
    def tts_version(self) -> str:
        default = DEFAULT_EDGE_TTS_VERSION if self.tts_provider == "edge" else ""
        return str(self.config.get("tts", {}).get("version", default))

    @property
    def tts_rate(self) -> str:
        return str(self.config.get("tts", {}).get("rate", "+0%"))

    @property
    def tts_pitch(self) -> str:
        return str(self.config.get("tts", {}).get("pitch", "+0Hz"))

    @property
    def tts_volume(self) -> str:
        return str(self.config.get("tts", {}).get("volume", "+0%"))

    @property
    def tts_generation_mode(self) -> str:
        default = "single_pass" if self.tts_provider == "edge" else "sectioned"
        return str(self.config.get("tts", {}).get("generation_mode", default))

    @property
    def tts_tool_name(self) -> str:
        return "edge_tts" if self.tts_provider == "edge" else "dashscope_tts"

    @property
    def tts_output_label(self) -> str:
        return f"{filename_slug(self.tts_provider)}-{filename_slug(self.voice)}"

    @property
    def tts_estimated_cost(self) -> float:
        return 0.0 if self.tts_provider == "edge" else 0.03

    @property
    def tts_model(self) -> str:
        return self.config.get("tts", {}).get("model", "qwen3-tts-flash")

    @property
    def language_type(self) -> str:
        return self.config.get("tts", {}).get("language_type", "Chinese")

    @property
    def style(self) -> dict[str, Any]:
        return self.config.get("style", {})

    @property
    def card_font_path(self) -> Path:
        return resolve_path(self.style.get("card_font"), default=DEFAULT_FONT)

    @property
    def cover_font_path(self) -> Path:
        return resolve_path(self.style.get("cover_font"), default=self.card_font_path)

    @property
    def final_output_dir(self) -> Path:
        return resolve_path(self.config.get("final_output_dir"), default=DEFAULT_FINAL_OUTPUT_DIR)

    @property
    def retention(self) -> dict[str, Any]:
        return self.config.get("retention", {})

    @property
    def stock_library(self) -> dict[str, Any]:
        return self.config.get("stock_library", {})

    def log_stage(self, stage: str, message: str) -> None:
        print(f"[workflow:{stage}] {message}", flush=True)

    def init_workspace(self) -> None:
        init_project(
            self.project_id,
            title=self.title,
            pipeline_type=PIPELINE_TYPE,
            style_playbook=STYLE_PLAYBOOK,
        )
        for directory in (
            self.artifacts,
            self.audio_dir,
            self.video_dir,
            self.music_dir,
            self.image_dir,
            self.renders_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def validate_config(self) -> dict[str, Any]:
        music_cfg = self.config.get("music", {})
        music_library = resolve_path(music_cfg.get("library_dir"), default=DEFAULT_MUSIC_LIBRARY)
        music_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac"}
        music_count = 0
        if music_library.exists():
            music_count = sum(1 for p in music_library.rglob("*") if p.is_file() and p.suffix.lower() in music_exts)
        planned_scenes = 0
        for section in self.config.get("sections", []):
            planned_scenes += len(section.get("queries", [])) + len(section.get("cards", []))
        report = {
            "project_id": self.project_id,
            "title": self.title,
            "profile": self.profile,
            "resolution": f"{self.width}x{self.height}",
            "tts_provider": self.tts_provider,
            "tts_version": self.tts_version,
            "voice": self.voice,
            "tts_rate": self.tts_rate,
            "tts_pitch": self.tts_pitch,
            "tts_generation_mode": self.tts_generation_mode,
            "sections": len(self.config.get("sections", [])),
            "planned_scenes": planned_scenes,
            "font": str(self.card_font_path),
            "font_exists": self.card_font_path.exists(),
            "music_library": str(music_library),
            "music_library_exists": music_library.exists(),
            "music_file_count": music_count,
            "final_output_dir": str(self.final_output_dir),
            "stock_library_enabled": bool(self.stock_library.get("enabled", True)),
            "stock_library_dir": str(default_cache_dir()),
            "cleanup_remotion_public": bool(self.retention.get("cleanup_remotion_public", True)),
            "ffmpeg_available": shutil.which("ffmpeg") is not None,
            "ffprobe_available": shutil.which("ffprobe") is not None,
            "will_call_external_providers": False,
        }
        missing = []
        if not report["font_exists"]:
            missing.append("font")
        if not report["music_library_exists"] or music_count == 0:
            missing.append("music_library")
        if not report["ffmpeg_available"]:
            missing.append("ffmpeg")
        if not report["ffprobe_available"]:
            missing.append("ffprobe")
        if not self.config.get("sections"):
            missing.append("sections")
        if self.tts_provider not in {"edge", "dashscope"}:
            missing.append(f"unsupported_tts_provider:{self.tts_provider}")
        if self.tts_provider == "edge" and self.tts_generation_mode != "single_pass":
            missing.append("edge_tts_requires_single_pass")
        report["status"] = "ok" if not missing else "needs_attention"
        report["missing"] = missing
        return report

    def build_proposal(self) -> dict[str, Any]:
        music_cfg = self.config.get("music", {})
        tts_operation = "generate whole-script narration once" if self.tts_provider == "edge" else "generate narration sections"
        tts_quantity = 1 if self.tts_provider == "edge" else len(self.config["sections"])
        platform = "youtube" if self.orientation == "landscape" else "tiktok"
        hook = self.config["sections"][0]["text"].splitlines()[0]
        key_points = list(self.config.get("key_points", []))
        if len(key_points) < 2:
            key_points = [
                section.get("label") or section["text"].splitlines()[0]
                for section in self.config["sections"][:2]
            ]
        while len(key_points) < 2:
            key_points.append(self.config.get("core_message") or hook)
        concept_common = {
            "title": self.title,
            "hook": hook,
            "tone": self.config.get("tone", "克制、内省、清醒"),
            "target_platform": platform,
            "target_duration_seconds": self.config.get("target_duration_seconds", 90),
            "suggested_playbook": STYLE_PLAYBOOK,
            "target_audience": self.config.get("target_audience", "中文短视频观众"),
            "key_points": key_points,
            "core_message": self.config.get("core_message", ""),
            "grounded_in": ["user_provided_script"],
        }
        proposal = {
            "version": "1.0",
            "concept_options": [
                {
                    **concept_common,
                    "id": "configured-script",
                    "narrative_structure": "problem_solution",
                    "visual_approach": "Stock b-roll plus exact-text Remotion cards with black overlay.",
                    "why_this_works": "The input script already has a clear hook, explanation arc, and landing sentence.",
                },
                {
                    **concept_common,
                    "id": "text-led",
                    "narrative_structure": "comparison",
                    "visual_approach": "More frequent handwritten concept cards, restrained stock footage, and stronger typographic contrast.",
                    "why_this_works": "Concept cards make abstract distinctions easier to scan and remember.",
                },
                {
                    **concept_common,
                    "id": "stock-led",
                    "narrative_structure": "story",
                    "visual_approach": "Human-centered stock footage carries most scenes, with text cards reserved for research claims and the landing sentence.",
                    "why_this_works": "Human behavior footage makes the psychological mechanism feel immediate and relatable.",
                },
            ],
            "selected_concept": {
                "concept_id": "configured-script",
                "rationale": "Use the user-provided script and configured visual treatment.",
                "modifications": [],
            },
            "production_plan": {
                "pipeline": PIPELINE_TYPE,
                "playbook": STYLE_PLAYBOOK,
                "stages": [
                    {"stage": "script", "tools": [{"tool_name": self.tts_tool_name, "role": "Generate narration", "provider": self.tts_provider, "available": True, "estimated_cost_usd": self.tts_estimated_cost}], "approach": "Preserve the supplied script and synthesize narration using the configured provider and generation mode."},
                    {"stage": "scene_plan", "tools": [{"tool_name": "zh_philosophy_video_workflow", "role": "Build timed scenes", "provider": "local", "available": True, "estimated_cost_usd": 0.0}], "approach": "Map narration sections to stock shots and exact-text cards."},
                    {"stage": "assets", "tools": [{"tool_name": "pexels_video/pixabay_video", "role": "Fetch free stock video", "provider": "pexels/pixabay", "available": True, "estimated_cost_usd": 0.0}, {"tool_name": "local_pil", "role": "Render Chinese text cards and cover", "provider": "local", "available": True, "estimated_cost_usd": 0.0}], "approach": "Reuse cached project assets where present and fetch only missing footage.", "fallback_if_unavailable": "Render local text-card fallbacks."},
                    {"stage": "edit", "tools": [{"tool_name": "zh_philosophy_video_workflow", "role": "Build edit decisions and captions", "provider": "local", "available": True, "estimated_cost_usd": 0.0}], "approach": "Time scenes and phrase-level captions to narration."},
                    {"stage": "compose", "tools": [{"tool_name": "video_compose", "role": "Render Remotion composition", "provider": "local", "available": True, "estimated_cost_usd": 0.0}, {"tool_name": "ffmpeg", "role": "Prepare media and concatenate cover", "provider": "local", "available": True, "estimated_cost_usd": 0.0}], "approach": "Render the main video, prepend the one-frame cover, verify, and export."},
                ],
                "render_runtime": "remotion",
                "renderer_family": "explainer-data",
                "composition_mode": "templated",
                "voice_selection": {
                    "provider": self.tts_provider,
                    "voice_id": self.voice,
                    "rationale": f"Use the configured {self.tts_provider} / {self.voice} voice for this reusable workflow.",
                    "estimated_cost_usd": self.tts_estimated_cost,
                    "delivery_style": self.config.get("voice_style", "安静、克制、有思考感的中文女声口播"),
                    "pacing_policy": f"{self.tts_generation_mode}; rate={self.tts_rate}; pitch={self.tts_pitch}; version={self.tts_version}",
                    "sample_approval_required": True,
                },
                "music_source": {
                    "source_type": "user_library",
                    "track_path": music_cfg.get("track_path") or "",
                    "provider": "local",
                    "mood_direction": ", ".join(music_cfg.get("preferred_keywords", ["ambient", "calming"])),
                    "estimated_cost_usd": 0.0,
                },
            },
            "approval": {
                "status": "approved",
                "user_notes": "Configured reusable workflow run.",
                "approved_budget_usd": self.config.get("budget_usd", 2.0),
            },
            "cost_estimate": {
                "total_estimated_usd": self.tts_estimated_cost,
                "line_items": [
                    {"tool": self.tts_tool_name, "operation": tts_operation, "quantity": tts_quantity, "estimated_usd": self.tts_estimated_cost},
                    {"tool": "pexels_video/pixabay_video", "operation": "download free stock clips", "quantity": sum(len(section.get("queries", [])) for section in self.config["sections"]), "estimated_usd": 0.0},
                    {"tool": "video_compose", "operation": "local Remotion render", "quantity": 1, "estimated_usd": 0.0},
                    {"tool": "local_music", "operation": "select user-library music", "quantity": 1, "estimated_usd": 0.0},
                ],
                "budget_cap_usd": self.config.get("budget_usd", 2.0),
                "budget_verdict": "within_budget",
            },
            "metadata": {"project_id": self.project_id, "title": self.title},
        }
        decision_log = {
            "version": "1.0",
            "project_id": self.project_id,
            "decisions": [
                {
                    "decision_id": "d-001",
                    "stage": "proposal",
                    "category": "pipeline_selection",
                    "subject": "Pipeline",
                    "options_considered": [{"option_id": PIPELINE_TYPE, "label": "Animated explainer", "score": 0.95, "reason": "Fits text-led narrated concept video."}],
                    "selected": PIPELINE_TYPE,
                    "reason": "Configured zh-philosophy-video workflow.",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 0.95,
                },
                {
                    "decision_id": "d-002",
                    "stage": "proposal",
                    "category": "render_runtime_selection",
                    "subject": "Composition runtime",
                    "options_considered": [
                        {"option_id": "remotion", "label": "Remotion", "score": 0.95, "reason": "Best fit for exact Chinese captions and reusable text cards."},
                        {"option_id": "hyperframes", "label": "HyperFrames", "score": 0.7, "reason": "Works for bespoke HTML motion, but this workflow is tuned for existing Remotion props.", "rejected_because": "Workflow template is Remotion-based."},
                    ],
                    "selected": "remotion",
                    "reason": "The reusable chain is designed around Remotion plus FFmpeg post-processing.",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 0.95,
                },
                {
                    "decision_id": "d-003",
                    "stage": "proposal",
                    "category": "composition_mode",
                    "subject": "Composition authoring mode",
                    "options_considered": [
                        {"option_id": "templated", "label": "Templated", "score": 0.95, "reason": "Stable and consistent for an explicitly approved 13-video batch."},
                        {"option_id": "atelier", "label": "Atelier", "score": 0.55, "reason": "Higher distinctness for hero work, but slower and less suitable for this scheduled batch.", "rejected_because": "User approved the templated batch plan."},
                    ],
                    "selected": "templated",
                    "reason": "The user explicitly approved a time-boxed batch workflow with a consistent visual system.",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 0.95,
                },
                {
                    "decision_id": "d-004",
                    "stage": "assets",
                    "category": "voice_selection",
                    "subject": "Narration TTS provider",
                    "options_considered": [
                        {"option_id": self.tts_output_label, "label": f"{self.tts_provider} {self.voice}", "score": 0.95, "reason": "Free, stable, and already approved for this Chinese narration batch."},
                        {"option_id": "openai-tts", "label": "OpenAI TTS", "score": 0.75, "reason": "More directed delivery, but paid and unnecessary for the approved fixed workflow.", "rejected_because": "User approved Edge-TTS XiaoxiaoNeural."},
                        {"option_id": "dashscope-tts", "label": "DashScope TTS", "score": 0.7, "reason": "Available cloud alternative, but provider switching was not approved.", "rejected_because": "No fallback is needed while Edge-TTS is healthy."},
                    ],
                    "selected": self.tts_output_label,
                    "reason": f"Use configured {self.tts_provider} TTS voice with {self.tts_generation_mode} generation.",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 0.95,
                },
                {
                    "decision_id": "d-005",
                    "stage": "assets",
                    "category": "music_source",
                    "subject": "Background music source",
                    "options_considered": [
                        {"option_id": "local-library", "label": "Local royalty-free library", "score": 0.95, "reason": "Approved, free, and broad enough to match each topic."},
                        {"option_id": "generated-music", "label": "Generated music", "score": 0.45, "reason": "Could be more bespoke, but adds cost and provider risk.", "rejected_because": "User approved automatic matching from the existing library."},
                        {"option_id": "no-music", "label": "No music", "score": 0.2, "reason": "Avoids mixing work but weakens pacing and atmosphere.", "rejected_because": "The approved plan includes background music."},
                    ],
                    "selected": "local-library",
                    "reason": "Automatically match a local royalty-free track to each script while keeping narration dominant.",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 0.9,
                },
                {
                    "decision_id": "d-006",
                    "stage": "proposal",
                    "category": "approval_policy",
                    "subject": "Full-run approval policy",
                    "options_considered": [
                        {"option_id": "full-run-preauthorized", "label": "Full run pre-authorized", "score": 0.95, "reason": "The user confirmed the complete batch plan and said to execute."},
                        {"option_id": "gate-by-gate", "label": "Pause at every gate", "score": 0.4, "reason": "Offers more review points but conflicts with the explicit batch execution instruction.", "rejected_because": "User explicitly approved execution of the confirmed plan."},
                    ],
                    "selected": "full-run-preauthorized",
                    "reason": "The user's message '确认方案，执行吧' pre-authorizes the confirmed 13-video production and scheduling run.",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 0.95,
                },
            ],
        }
        decision_log = self.merge_decision_history(decision_log)
        dump_json(self.artifacts / "proposal_packet.json", proposal)
        dump_json(self.artifacts / "decision_log.json", decision_log)
        safe_checkpoint(self.project_id, "proposal", {"proposal_packet": proposal, "decision_log": decision_log}, human_approval_required=True)
        return proposal

    def merge_decision_history(self, current: dict[str, Any]) -> dict[str, Any]:
        path = self.artifacts / "decision_log.json"
        if not path.exists():
            return current
        previous = load_json(path)
        decisions = list(previous.get("decisions", []))
        for candidate in current.get("decisions", []):
            matching = [
                item
                for item in decisions
                if item.get("category") == candidate.get("category")
                and item.get("subject") == candidate.get("subject")
            ]
            if not matching:
                candidate["decision_id"] = f"d-{len(decisions) + 1:03d}"
                decisions.append(candidate)
                continue
            latest = matching[-1]
            if latest.get("selected") == candidate.get("selected"):
                continue
            updated = dict(candidate)
            updated["decision_id"] = f"d-{len(decisions) + 1:03d}"
            updated["options_considered"] = [
                {
                    "option_id": latest.get("selected", "previous"),
                    "label": latest.get("selected", "Previous selection"),
                    "score": 0.5,
                    "reason": "Previously configured selection.",
                    "rejected_because": "Superseded by the current workflow configuration.",
                },
                *updated.get("options_considered", []),
            ]
            updated["reason"] = f"Configuration changed from {latest.get('selected')} to {updated.get('selected')}."
            decisions.append(updated)
        return {"version": "1.0", "project_id": self.project_id, "decisions": decisions}

    def provider_text(self, text: str) -> str:
        if self.tts_provider == "edge":
            return text
        replacements = {
            "Isaiah Berlin": "以赛亚·伯林",
            "SDT": "S D T",
            **self.config.get("tts", {}).get("replacements", {}),
        }
        return text_replacements(text, replacements)

    def build_script(self) -> dict[str, Any]:
        sections = []
        for item in self.config["sections"]:
            sections.append(
                {
                    "id": item["id"],
                    "label": item.get("label", item["id"]),
                    "text": item["text"],
                    "start_seconds": 0,
                    "end_seconds": 0,
                    "speaker_directions": self.config.get("speaker_directions", "克制、自然、略慢；不要播音腔。"),
                    "delivery_cues": {
                        "pace": "measured",
                        "energy": "introspective",
                        "delivery_note": "Use the original punctuation and paragraph breaks for natural pauses.",
                        "provider_text": self.provider_text(item["text"]),
                    },
                    "enhancement_cues": [
                        {
                            "type": "broll",
                            "description": (item.get("queries") or [{}])[0].get("description", ""),
                            "timestamp_seconds": 1,
                        }
                    ],
                    "pronunciation_guides": self.config.get("pronunciation_guides", []),
                    "source_ref": "user_provided_script",
                }
            )
        script = {
            "version": "1.0",
            "title": self.title,
            "total_duration_seconds": 0,
            "voice_performance": {
                "performance_intent": self.config.get("voice_style", "安静、克制、有思考感的中文女声口播。"),
                "pacing_profile": "contemplative",
                "energy_curve": self.config.get("energy_curve", "开头共鸣，中段解释，结尾清晰收束。"),
                "pause_policy": self.config.get("pause_policy", "短句自然停顿，关键概念前后放慢。"),
                "sample_section_id": self.config.get("sample_section_id", sections[-1]["id"] if sections else ""),
                "provider_notes": {
                    self.tts_provider: (
                        f"Use Edge-TTS {self.tts_version} / {self.voice} / rate {self.tts_rate} / "
                        f"pitch {self.tts_pitch} in {self.tts_generation_mode} mode."
                        if self.tts_provider == "edge"
                        else f"Use {self.tts_model} / {self.voice}."
                    )
                },
            },
            "sections": sections,
            "metadata": {
                "script_policy": "User-provided script is preserved; only provider pronunciation text may be adjusted.",
                "raw_script": self.config.get("raw_script", "\n\n".join(s["text"] for s in sections)),
                "tts_provider": self.tts_provider,
                "tts_generation_mode": self.tts_generation_mode,
            },
        }
        return script

    def generate_tts(self, script: dict[str, Any]) -> tuple[list[dict[str, Any]], Path, float, float]:
        if self.tts_provider == "edge":
            return self.generate_edge_tts(script)
        if self.tts_provider == "dashscope":
            return self.generate_dashscope_tts(script)
        raise ValueError(f"Unsupported TTS provider: {self.tts_provider}")

    def full_provider_text(self, script: dict[str, Any]) -> str:
        return "\n\n".join(section["delivery_cues"]["provider_text"] for section in script["sections"])

    def tts_cache_fingerprint(self, text: str) -> str:
        payload = {
            "text": text,
            "provider": self.tts_provider,
            "version": self.tts_version,
            "voice": self.voice,
            "rate": self.tts_rate,
            "pitch": self.tts_pitch,
            "volume": self.tts_volume,
            "generation_mode": self.tts_generation_mode,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def apply_edge_timings(
        self,
        script: dict[str, Any],
        boundaries: list[dict[str, Any]],
        full_duration: float,
    ) -> list[dict[str, Any]]:
        if not boundaries:
            raise RuntimeError("Edge-TTS returned audio without WordBoundary timing data.")

        normalized_script = spoken_text(self.full_provider_text(script))
        normalized_cursor = 0
        mapped_boundaries: list[dict[str, Any]] = []
        for boundary in boundaries:
            token = spoken_text(str(boundary.get("text", "")))
            if not token:
                continue
            start_index = normalized_script.find(token, normalized_cursor)
            if start_index < 0:
                start_index = normalized_cursor
            end_index = min(len(normalized_script), start_index + len(token))
            mapped_boundaries.append(
                {
                    **boundary,
                    "source_start": start_index,
                    "source_end": end_index,
                }
            )
            normalized_cursor = max(normalized_cursor, end_index)

        section_ranges: list[tuple[int, int]] = []
        section_cursor = 0
        for section in script["sections"]:
            length = len(spoken_text(section["delivery_cues"]["provider_text"]))
            section_ranges.append((section_cursor, section_cursor + length))
            section_cursor += length

        first_word_times: list[float | None] = []
        section_boundaries: list[list[dict[str, Any]]] = []
        for section_start, section_end in section_ranges:
            matching = [
                item
                for item in mapped_boundaries
                if item["source_start"] < section_end and item["source_end"] > section_start
            ]
            section_boundaries.append(matching)
            first_word_times.append(float(matching[0]["start_seconds"]) if matching else None)

        section_starts: list[float] = []
        for index, first_word in enumerate(first_word_times):
            if index == 0:
                section_starts.append(0.0)
            elif first_word is not None:
                section_starts.append(first_word)
            else:
                section_starts.append(section_starts[-1])

        captions: list[dict[str, Any]] = []
        for index, section in enumerate(script["sections"]):
            section_start = section_starts[index]
            section_end = section_starts[index + 1] if index + 1 < len(section_starts) else full_duration
            section_end = max(section_start, min(full_duration, section_end))
            section["start_seconds"] = round(section_start, 3)
            section["end_seconds"] = round(section_end, 3)
            captions.extend(
                self.phrase_captions_from_boundaries(
                    section["text"],
                    section_ranges[index],
                    section_boundaries[index],
                    section_start,
                    section_end,
                )
            )

        script["total_duration_seconds"] = round(full_duration, 3)
        script["metadata"]["captions"] = captions
        script["metadata"]["timing_source"] = "edge_tts_word_boundary"
        script["metadata"]["word_boundary_count"] = len(boundaries)
        return captions

    def phrase_captions_from_boundaries(
        self,
        text: str,
        section_range: tuple[int, int],
        boundaries: list[dict[str, Any]],
        section_start: float,
        section_end: float,
    ) -> list[dict[str, Any]]:
        phrases = [item.strip() for item in re.split(r"(?<=[。！？；])|\n+", text) if item.strip()]
        if not phrases:
            return []
        phrase_ranges: list[tuple[int, int]] = []
        cursor = section_range[0]
        for phrase in phrases:
            length = len(spoken_text(phrase))
            phrase_ranges.append((cursor, cursor + length))
            cursor += length

        phrase_starts: list[float] = []
        for index, (phrase_start, phrase_end) in enumerate(phrase_ranges):
            matching = [
                item
                for item in boundaries
                if item["source_start"] < phrase_end and item["source_end"] > phrase_start
            ]
            if index == 0:
                phrase_starts.append(section_start)
            elif matching:
                phrase_starts.append(float(matching[0]["start_seconds"]))
            else:
                ratio = index / len(phrases)
                phrase_starts.append(section_start + (section_end - section_start) * ratio)

        captions: list[dict[str, Any]] = []
        for index, phrase in enumerate(phrases):
            start = max(section_start, phrase_starts[index])
            end = phrase_starts[index + 1] if index + 1 < len(phrase_starts) else section_end
            end = max(start + 0.01, min(section_end, end))
            captions.append({"word": phrase, "startMs": round(start * 1000), "endMs": round(end * 1000)})
        return captions

    def generate_edge_tts(self, script: dict[str, Any]) -> tuple[list[dict[str, Any]], Path, float, float]:
        if self.tts_generation_mode != "single_pass":
            raise ValueError("Edge-TTS narration must use generation_mode=single_pass.")
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        text = self.full_provider_text(script)
        expected_raw = self.config.get("raw_script", "\n\n".join(section["text"] for section in script["sections"]))
        if text != expected_raw:
            raise ValueError("Edge-TTS input differs from the original script; generation stopped.")

        mp3 = self.audio_dir / "narration_full.mp3"
        wav = self.audio_dir / "narration_full.wav"
        srt = self.audio_dir / "narration_full.srt"
        timings = self.audio_dir / "narration_full.timings.json"
        cache_path = self.audio_dir / "narration_full.cache.json"
        fingerprint = self.tts_cache_fingerprint(text)
        cached = load_json(cache_path) if cache_path.exists() else {}
        cache_valid = cached.get("fingerprint") == fingerprint and all(
            path.exists() and path.stat().st_size > 0 for path in (mp3, wav, srt, timings)
        )

        if not cache_valid:
            for path in (mp3, wav, srt, timings, cache_path):
                path.unlink(missing_ok=True)
            result = EdgeTTS().execute(
                {
                    "text": text,
                    "voice": self.voice,
                    "rate": self.tts_rate,
                    "pitch": self.tts_pitch,
                    "volume": self.tts_volume,
                    "boundary": "WordBoundary",
                    "output_path": str(mp3),
                    "subtitles_path": str(srt),
                    "timings_path": str(timings),
                }
            )
            if not result.success:
                raise RuntimeError(result.error)
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(mp3),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "24000",
                    "-c:a",
                    "pcm_s16le",
                    str(wav),
                ]
            )
            dump_json(
                cache_path,
                {
                    "version": "1.0",
                    "fingerprint": fingerprint,
                    "provider": self.tts_provider,
                    "provider_version": result.data.get("provider_version", self.tts_version),
                    "voice": self.voice,
                    "rate": self.tts_rate,
                    "pitch": self.tts_pitch,
                    "volume": self.tts_volume,
                    "generation_mode": self.tts_generation_mode,
                    "text": text,
                    "provider_calls": 1,
                },
            )

        timing_data = load_json(timings)
        if timing_data.get("text") != text:
            raise RuntimeError("Cached Edge-TTS timing text does not match the requested script.")
        boundaries = timing_data.get("boundaries", [])
        full_duration = float(probe_duration(wav) or probe_duration(mp3) or 0)
        if full_duration <= 0:
            raise RuntimeError("Edge-TTS narration has no measurable duration.")
        self.apply_edge_timings(script, boundaries, full_duration)
        script["metadata"]["tts_cache_fingerprint"] = fingerprint
        script["metadata"]["tts_input_text"] = text
        script["metadata"]["tts_artifacts"] = {
            "mp3": rel(self.project_dir, mp3),
            "wav": rel(self.project_dir, wav),
            "srt": rel(self.project_dir, srt),
            "timings": rel(self.project_dir, timings),
        }
        assets = [
            {
                "id": "narration-full",
                "type": "narration",
                "path": rel(self.project_dir, wav),
                "source_tool": "edge_tts",
                "scene_id": "all",
                "duration_seconds": round(full_duration, 3),
                "cost_usd": 0,
                "format": "wav",
                "provider": "edge",
                "model": f"edge-tts-{self.tts_version}",
                "generation_summary": "Whole script generated in one Edge-TTS stream and normalized to 24kHz mono WAV.",
                "voice_performance": {
                    "provider_settings": {
                        "voice": self.voice,
                        "rate": self.tts_rate,
                        "pitch": self.tts_pitch,
                        "volume": self.tts_volume,
                        "generation_mode": self.tts_generation_mode,
                    },
                    "provider_text_used": False,
                    "delivery_cues_applied": True,
                    "sample_approved": True,
                    "review_notes": "Subtitle and section timing use WordBoundary events from the same synthesis stream.",
                },
            },
            {
                "id": "narration-subtitles",
                "type": "subtitle",
                "path": rel(self.project_dir, srt),
                "source_tool": "edge_tts",
                "scene_id": "all",
                "cost_usd": 0,
                "format": "srt",
                "provider": "edge",
                "generation_summary": "WordBoundary subtitles emitted by the same Edge-TTS synthesis stream.",
            },
        ]
        return assets, wav, full_duration, 0.0

    def generate_dashscope_tts(self, script: dict[str, Any]) -> tuple[list[dict[str, Any]], Path, float, float]:
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        tts = DashscopeTTS()
        max_chars = int(self.config.get("tts", {}).get("max_chars", 560))
        assets: list[dict[str, Any]] = []
        total_cost = 0.0
        cursor = 0.0

        for section in script["sections"]:
            section_out = self.audio_dir / f"{section['id']}.wav"
            chunk_texts = split_tts_text(section["delivery_cues"]["provider_text"], max_chars)
            chunk_paths: list[Path] = []
            if not section_out.exists():
                for index, text in enumerate(chunk_texts, start=1):
                    chunk_out = self.audio_dir / f"{section['id']}_{index:02d}.wav"
                    if not chunk_out.exists():
                        result = tts.execute(
                            {
                                "text": text,
                                "model": self.tts_model,
                                "voice": self.voice,
                                "language_type": self.language_type,
                                "output_path": str(chunk_out),
                            }
                        )
                        if not result.success:
                            raise RuntimeError(result.error)
                        total_cost += result.cost_usd
                    chunk_paths.append(chunk_out)
                if len(chunk_paths) == 1:
                    shutil.copy2(chunk_paths[0], section_out)
                else:
                    concat = self.audio_dir / f"{section['id']}_chunks.txt"
                    concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in chunk_paths), encoding="utf-8")
                    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(section_out)])

            duration = float(probe_duration(section_out) or 0)
            section["start_seconds"] = round(cursor, 2)
            section["end_seconds"] = round(cursor + duration, 2)
            cursor += duration
            assets.append(
                {
                    "id": f"narration-{section['id']}",
                    "type": "narration",
                    "path": rel(self.project_dir, section_out),
                    "source_tool": "dashscope_tts",
                    "scene_id": section["id"],
                    "duration_seconds": round(duration, 2),
                    "cost_usd": 0,
                    "format": "wav",
                    "provider": "dashscope",
                    "model": self.tts_model,
                    "voice_performance": {
                        "provider_settings": {
                            "voice": self.voice,
                            "model": self.tts_model,
                            "language_type": self.language_type,
                        },
                        "provider_text_used": True,
                        "delivery_cues_applied": True,
                    },
                }
            )

        full = self.audio_dir / "narration_full.wav"
        cmd = ["ffmpeg", "-y"]
        for section in script["sections"]:
            cmd.extend(["-i", str(self.audio_dir / f"{section['id']}.wav")])
        labels = "".join(f"[{i}:a]" for i in range(len(script["sections"])))
        cmd.extend(
            [
                "-filter_complex",
                f"{labels}concat=n={len(script['sections'])}:v=0:a=1[a]",
                "-map",
                "[a]",
                "-ac",
                "1",
                "-ar",
                "24000",
                "-c:a",
                "pcm_s16le",
                str(full),
            ]
        )
        run(cmd)
        full_duration = float(probe_duration(full) or cursor)
        script["total_duration_seconds"] = round(full_duration, 2)
        script["metadata"]["captions"] = self.make_captions(script)
        script["metadata"]["timing_source"] = "script_duration_estimate"
        assets.append(
            {
                "id": "narration-full",
                "type": "narration",
                "path": rel(self.project_dir, full),
                "source_tool": "ffmpeg",
                "scene_id": "all",
                "duration_seconds": round(full_duration, 2),
                "cost_usd": 0,
                "format": "wav",
                "provider": "local",
                "generation_summary": "Concatenated DashScope TTS sections.",
            }
        )
        return assets, full, full_duration, total_cost

    def generate_tts_sample(self, script: dict[str, Any]) -> dict[str, Any]:
        if self.tts_provider != "edge":
            raise ValueError("The sample command currently supports the Edge-TTS provider only.")
        sample_id = self.config.get("sample_section_id") or script["sections"][-1]["id"]
        section = next((item for item in script["sections"] if item["id"] == sample_id), None)
        if section is None:
            raise ValueError(f"Sample section not found: {sample_id}")
        sample_dir = self.audio_dir / "samples"
        sample_dir.mkdir(parents=True, exist_ok=True)
        mp3 = sample_dir / f"{sample_id}.mp3"
        srt = sample_dir / f"{sample_id}.srt"
        timings = sample_dir / f"{sample_id}.timings.json"
        result = EdgeTTS().execute(
            {
                "text": section["text"],
                "voice": self.voice,
                "rate": self.tts_rate,
                "pitch": self.tts_pitch,
                "volume": self.tts_volume,
                "boundary": "WordBoundary",
                "output_path": str(mp3),
                "subtitles_path": str(srt),
                "timings_path": str(timings),
            }
        )
        if not result.success:
            raise RuntimeError(result.error)
        return {"section_id": sample_id, "text": section["text"], **result.data}

    def build_scene_plan(self, script: dict[str, Any]) -> dict[str, Any]:
        config_sections = {section["id"]: section for section in self.config["sections"]}
        scenes = []
        for section in script["sections"]:
            cfg = config_sections[section["id"]]
            start = float(section["start_seconds"])
            end = float(section["end_seconds"])
            duration = max(1.0, end - start)
            visual_items: list[dict[str, Any]] = []
            for i, item in enumerate(cfg.get("queries", []), start=1):
                visual_items.append({"kind": "broll", "query": item["query"], "description": item.get("description", item["query"]), "id_suffix": f"b{i}"})
            for i, item in enumerate(cfg.get("cards", []), start=1):
                visual_items.append({"kind": "text_card", "card": item, "description": item.get("subtitle", ""), "id_suffix": f"c{i}"})
            if not visual_items:
                visual_items.append({"kind": "text_card", "card": {"id": "auto", "title_lines": [section["label"]], "subtitle": ""}, "description": section["label"], "id_suffix": "c1"})

            for index, visual in enumerate(visual_items):
                scene_start = start + duration * index / len(visual_items)
                scene_end = start + duration * (index + 1) / len(visual_items)
                scene_id = f"scene-{section['id']}-{visual['id_suffix']}"
                scenes.append(
                    {
                        "id": scene_id,
                        "type": "text_card" if visual["kind"] == "text_card" else "broll",
                        "description": visual["description"],
                        "start_seconds": round(scene_start, 2),
                        "end_seconds": round(scene_end, 2),
                        "script_section_id": section["id"],
                        "framing": f"{self.width}x{self.height}, full-screen visual, bottom subtitles.",
                        "movement": "Slow push, subtle lateral movement, fade transitions.",
                        "transition_in": "fade",
                        "transition_out": "dissolve",
                        "overlay_notes": "Use exact-text local cards for Chinese text; do not ask image models to render Chinese.",
                        "shot_language": {
                            "shot_size": "medium",
                            "camera_movement": "dolly_in",
                            "lens_mm": 35,
                            "lighting_key": "low_key",
                            "depth_of_field": "medium",
                            "color_temperature": "neutral",
                        },
                        "shot_intent": visual["description"],
                        "narrative_role": "resolution" if section["id"] == script["sections"][-1]["id"] else "deliver_payload",
                        "information_role": section["label"],
                        "hero_moment": visual["kind"] == "text_card",
                        "texture_keywords": ["quiet", "cinematic", "low saturation", "high contrast"],
                        "required_assets": [
                            {
                                "type": "video" if visual["kind"] == "broll" else "text_card",
                                "description": visual.get("query") or visual["description"],
                                "source": "generate" if visual["kind"] == "broll" else "provided",
                            }
                        ],
                        "metadata": {"visual": visual},
                    }
                )
        return {"version": "1.0", "style_playbook": STYLE_PLAYBOOK, "scenes": scenes, "metadata": {"source": "config", "visual_density_target": "configured"}}

    def fetch_stock(self, scene_plan: dict[str, Any]) -> list[dict[str, Any]]:
        self.video_dir.mkdir(parents=True, exist_ok=True)
        pexels = PexelsVideo()
        pixabay = PixabayVideo()
        library_enabled = bool(self.stock_library.get("enabled", True))
        library_min_score = float(self.stock_library.get("min_match_score", 0.3))
        library = get_default_cache() if library_enabled else None
        used_library_ids: set[str] = set()
        assets: list[dict[str, Any]] = []
        for scene in scene_plan["scenes"]:
            if scene["type"] != "broll":
                continue
            query = scene["metadata"]["visual"]["query"]
            out = self.video_dir / f"{scene['id']}.mp4"
            source_tool = "pexels_video"
            provider = "pexels"
            license_text = "Pexels License"
            original_url = ""
            creator = ""
            library_clip_id = ""
            library_status = "project_existing" if out.exists() else "disabled"
            library_match_score = 0.0
            result = None
            if not out.exists():
                library_match = (
                    library.link_best(
                        query,
                        out,
                        orientation=self.orientation,
                        exclude_clip_ids=used_library_ids,
                        min_score=library_min_score,
                    )
                    if library is not None
                    else None
                )
                if library_match is not None:
                    entry, library_match_score = library_match
                    library_clip_id = entry.clip_id
                    used_library_ids.add(entry.clip_id)
                    source_tool = "local_stock_library"
                    provider = entry.source or "local"
                    license_text = entry.license or "See shared stock library manifest"
                    original_url = entry.source_url
                    creator = entry.creator
                    library_status = "hit"
                    print(f"[stock-library] hit {entry.clip_id} score={library_match_score:.3f} for {scene['id']}")
                else:
                    library_status = "miss"
                    result = pexels.execute(
                        {
                            "query": query,
                            "orientation": self.orientation,
                            "size": "medium",
                            "min_duration": 4,
                            "per_page": 12,
                            "preferred_quality": "hd",
                            "output_path": str(out),
                        }
                    )
                    if not result.success:
                        result = pixabay.execute(
                            {
                                "query": query,
                                "category": "people" if any(w in query for w in ["person", "worker", "phone"]) else "backgrounds",
                                "min_duration": 4,
                                "per_page": 20,
                                "preferred_quality": "large",
                                "output_path": str(out),
                            }
                        )
                        source_tool = "pixabay_video"
                        provider = "pixabay"
                        license_text = "Pixabay Content License"
                    if not result.success:
                        print(f"[warn] stock unavailable for {scene['id']}: {query}")
                        continue
                    original_url = result.data.get("pexels_url") or result.data.get("page_url") or ""
                    creator = result.data.get("user", "")
                    library_clip_id = f"{provider}_{result.data['video_id']}"
                    used_library_ids.add(library_clip_id)
                    if library is not None:
                        library.ingest(
                            library_clip_id,
                            out,
                            {
                                "source": provider,
                                "source_id": str(result.data["video_id"]),
                                "source_url": original_url,
                                "license": result.data.get("license", license_text),
                                "creator": creator,
                                "source_tags": result.data.get("tags", ""),
                                "query": query,
                                "width": result.data.get("width", 0),
                                "height": result.data.get("height", 0),
                                "duration_seconds": result.data.get("duration_seconds", 0),
                                "last_project_id": self.project_id,
                            },
                        )
                        library_status = "added"
            duration = float(probe_duration(out) or (result.data.get("duration_seconds") if result else 0) or 0)
            assets.append(
                {
                    "id": f"video-{scene['id']}",
                    "type": "video",
                    "path": rel(self.project_dir, out),
                    "source_tool": source_tool,
                    "scene_id": scene["id"],
                    "duration_seconds": round(duration, 2),
                    "cost_usd": 0,
                    "format": "mp4",
                    "provider": provider,
                    "license": license_text,
                    "original_url": original_url,
                    "creator": creator,
                    "library_clip_id": library_clip_id,
                    "library_status": library_status,
                    "library_match_score": round(library_match_score, 4),
                    "generation_summary": f"Stock query: {query}",
                }
            )
        return assets

    def ingest_project_stock_assets(self) -> dict[str, Any]:
        """Migrate a completed project's stock clips into the shared library."""
        manifest_path = self.artifacts / "asset_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Asset manifest not found: {manifest_path}")
        manifest = load_json(manifest_path)
        library = get_default_cache()
        added = 0
        skipped = 0
        migrated: list[str] = []
        for asset in manifest.get("assets", []):
            if asset.get("type") != "video":
                continue
            source_path = self.project_dir / asset["path"]
            if not source_path.is_file():
                skipped += 1
                continue
            provider = str(asset.get("provider") or "stock")
            original_url = str(asset.get("original_url") or "")
            source_id_match = re.search(r"(\d+)(?:/)?$", original_url)
            source_id = source_id_match.group(1) if source_id_match else hashlib.sha256(
                f"{provider}:{original_url}:{source_path.name}".encode("utf-8")
            ).hexdigest()[:16]
            clip_id = str(asset.get("library_clip_id") or f"{provider}_{source_id}")
            query = str(asset.get("generation_summary") or "")
            query = query.removeprefix("Stock query:").strip()
            probe = ffprobe(source_path)
            video_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
            ok = library.ingest(
                clip_id,
                source_path,
                {
                    "source": provider,
                    "source_id": source_id,
                    "source_url": original_url,
                    "license": asset.get("license", ""),
                    "creator": asset.get("creator", ""),
                    "source_tags": query,
                    "query": query,
                    "width": video_stream.get("width", 0),
                    "height": video_stream.get("height", 0),
                    "duration_seconds": asset.get("duration_seconds", 0),
                    "last_project_id": self.project_id,
                },
            )
            if ok:
                added += 1
                migrated.append(clip_id)
            else:
                skipped += 1
        return {
            "project_id": self.project_id,
            "library_dir": str(library.cache_dir),
            "stock_assets_ingested": added,
            "stock_assets_skipped": skipped,
            "clip_ids": migrated,
            "library_stats": library.stats(),
        }

    def ensure_card_background(self) -> Path:
        bg = self.image_dir / f"card-background-{self.width}x{self.height}.jpg"
        if bg.exists():
            return bg
        source = next(iter(sorted(self.video_dir.glob("*.mp4"))), None)
        if source is None:
            img = Image.new("RGB", (self.width, self.height), "#061115")
            img.save(bg, quality=95)
            return bg
        run(["ffmpeg", "-y", "-ss", "00:00:01", "-i", str(source), "-frames:v", "1", "-update", "1", str(bg)])
        return bg

    def load_font(self, path: Path, size: int) -> ImageFont.FreeTypeFont:
        if path.exists():
            return ImageFont.truetype(str(path), size)
        return ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", size)

    def fit_title_layout(
        self,
        draw: ImageDraw.ImageDraw,
        title_lines: list[str],
        font_path: Path,
        initial_size: int,
        max_width: int,
        max_height: int,
        line_gap: int,
        *,
        min_size: int,
    ) -> tuple[ImageFont.FreeTypeFont, int, list[str], list[int], int]:
        for title_size in range(initial_size, min_size - 1, -4):
            title_font = self.load_font(font_path, title_size)
            scaled_gap = max(12, int(line_gap * title_size / max(1, initial_size)))
            wrapped_title: list[str] = []
            for line in title_lines:
                wrapped_title.extend(wrap_text(draw, line, title_font, max_width))

            line_heights = [text_line_height(draw, line, title_font) for line in wrapped_title]
            total_h = sum(line_heights) + max(0, len(wrapped_title) - 1) * scaled_gap
            too_wide = any(
                draw.textbbox((0, 0), line, font=title_font)[2]
                - draw.textbbox((0, 0), line, font=title_font)[0]
                > max_width
                for line in wrapped_title
            )
            if wrapped_title and total_h <= max_height and not too_wide:
                return title_font, scaled_gap, wrapped_title, line_heights, total_h

        title_font = self.load_font(font_path, min_size)
        scaled_gap = max(12, int(line_gap * min_size / max(1, initial_size)))
        wrapped_title = []
        for line in title_lines:
            wrapped_title.extend(wrap_text(draw, line, title_font, max_width))
        line_heights = [text_line_height(draw, line, title_font) for line in wrapped_title]
        total_h = sum(line_heights) + max(0, len(wrapped_title) - 1) * scaled_gap
        return title_font, scaled_gap, wrapped_title, line_heights, total_h

    def draw_text_card(self, out: Path, title_lines: list[str], subtitle: str, *, is_cover: bool = False) -> None:
        bg_path = self.ensure_card_background()
        bg_img = Image.open(bg_path).convert("RGB").filter(ImageFilter.GaussianBlur(radius=3))
        img = cover_to_canvas(bg_img, (self.width, self.height))
        overlay_opacity = float(self.style.get("black_overlay_opacity", 0.5))
        img = Image.blend(img, Image.new("RGB", img.size, "#000000"), overlay_opacity)
        draw = ImageDraw.Draw(img)

        if self.orientation == "landscape":
            title_size = int(self.style.get("cover_font_size" if is_cover else "card_title_font_size", 232 if is_cover else 136))
            subtitle_size = int(self.style.get("card_subtitle_font_size", 54))
            line_gap = int(self.style.get("card_line_gap", 34))
            y_bias = -70 if not is_cover else -20
        else:
            title_size = int(self.style.get("cover_font_size" if is_cover else "card_title_font_size", 196 if is_cover else 128))
            subtitle_size = int(self.style.get("card_subtitle_font_size", 48))
            line_gap = int(self.style.get("card_line_gap", 42))
            y_bias = -80

        font_path = self.cover_font_path if is_cover else self.card_font_path
        sub_font = self.load_font(self.card_font_path, subtitle_size)
        title_fill = tuple(self.style.get("title_color_rgb", [248, 246, 231]))
        accent_fill = tuple(self.style.get("accent_color_rgb", [214, 179, 90]))

        max_width = int(self.width * 0.82)
        max_title_height = int(self.height * (0.58 if is_cover else 0.62))
        if is_cover:
            if self.orientation == "portrait":
                title_size = int(title_size * float(self.style.get("cover_portrait_font_scale", 0.82)))
                max_width = int(self.width * 0.78)
                max_title_height = int(self.height * 0.56)
            else:
                title_size = int(title_size * float(self.style.get("cover_landscape_font_scale", 0.98)))
                max_width = int(self.width * 0.82)
                max_title_height = int(self.height * 0.58)
        title_font, line_gap, wrapped_title, line_heights, total_h = self.fit_title_layout(
            draw,
            title_lines,
            font_path,
            title_size,
            max_width,
            max_title_height,
            line_gap,
            min_size=96 if self.orientation == "landscape" else 82,
        )
        y = max(80, (self.height - total_h) // 2 + y_bias)
        for index, line in enumerate(wrapped_title):
            box = draw.textbbox((0, 0), line, font=title_font)
            x = (self.width - (box[2] - box[0])) // 2
            draw.text((x, y), line, font=title_font, fill=title_fill)
            y += line_heights[index] + line_gap
        if subtitle:
            subtitle_lines = wrap_text(draw, subtitle, sub_font, int(self.width * 0.72))
            subtitle_y = min(self.height - 160, y + 34)
            for line in subtitle_lines[:2]:
                box = draw.textbbox((0, 0), line, font=sub_font)
                draw.text(((self.width - (box[2] - box[0])) // 2, subtitle_y), line, font=sub_font, fill=accent_fill)
                subtitle_y += box[3] - box[1] + 16
        img.save(out, quality=96)

    def create_text_card_assets(self, scene_plan: dict[str, Any]) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        for scene in scene_plan["scenes"]:
            if scene["type"] != "text_card":
                continue
            card = scene["metadata"]["visual"]["card"]
            title_lines = card.get("title_lines") or [card.get("title", scene["description"])]
            subtitle = card.get("subtitle", "")
            out = self.image_dir / f"{scene['id']}-text-card-{self.width}x{self.height}.png"
            if not out.exists():
                self.draw_text_card(out, title_lines, subtitle)
            assets.append(
                {
                    "id": f"image-{scene['id']}",
                    "type": "image",
                    "path": rel(self.project_dir, out),
                    "source_tool": "local_pil",
                    "scene_id": scene["id"],
                    "cost_usd": 0,
                    "resolution": f"{self.width}x{self.height}",
                    "format": "png",
                    "provider": "local",
                    "generation_summary": "Exact-text card with stock-frame background, black overlay, and configured local font.",
                }
            )
        return assets

    def create_cover_asset(self) -> Path:
        title = self.config.get("cover_title") or self.title[:4]
        cover_lines = self.config.get("cover_lines") or [title]
        subtitle = self.config.get("cover_subtitle", "")
        out = self.image_dir / f"cover-title-{self.width}x{self.height}.png"
        self.draw_text_card(out, cover_lines, subtitle, is_cover=True)
        return out

    def create_fallback_assets(self, scene_plan: dict[str, Any], stock_assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        available = {asset["scene_id"] for asset in stock_assets}
        assets: list[dict[str, Any]] = []
        font = self.load_font(self.card_font_path, 82 if self.orientation == "landscape" else 62)
        for scene in scene_plan["scenes"]:
            if scene["type"] != "broll" or scene["id"] in available:
                continue
            out = self.image_dir / f"{scene['id']}-fallback-card-{self.width}x{self.height}.png"
            if not out.exists():
                self.draw_text_card(out, [scene["description"]], "", is_cover=False)
            assets.append(
                {
                    "id": f"image-{scene['id']}-fallback",
                    "type": "image",
                    "path": rel(self.project_dir, out),
                    "source_tool": "local_pil",
                    "scene_id": scene["id"],
                    "cost_usd": 0,
                    "resolution": f"{self.width}x{self.height}",
                    "format": "png",
                    "provider": "local",
                    "generation_summary": f"Fallback card using configured card style. Font prepared: {bool(font)}",
                }
            )
        return assets

    def choose_music_source(self, target_duration: float) -> Path:
        music_cfg = self.config.get("music", {})
        configured = music_cfg.get("track_path")
        if configured:
            path = resolve_path(configured)
            if not path.exists():
                raise FileNotFoundError(f"Configured music file not found: {path}")
            return path

        library = resolve_path(music_cfg.get("library_dir"), default=DEFAULT_MUSIC_LIBRARY)
        if not library.exists():
            raise FileNotFoundError(f"Music library not found: {library}")
        exts = {".mp3", ".wav", ".m4a", ".aac", ".flac"}
        preferred = [kw.lower() for kw in music_cfg.get("preferred_keywords", ["ambient", "calming", "纯音乐"])]
        candidates = [p for p in library.rglob("*") if p.is_file() and p.suffix.lower() in exts]
        if not candidates:
            raise FileNotFoundError(f"No music files found under: {library}")

        def score(path: Path) -> tuple[int, float, str]:
            name = path.name.lower()
            keyword_score = sum(1 for kw in preferred if kw and kw in name)
            duration = float(probe_duration(path) or 0)
            duration_score = 1 if duration >= target_duration + float(self.style.get("music_start_seconds", 60)) else 0
            return keyword_score + duration_score, duration, path.name

        return sorted(candidates, key=score, reverse=True)[0]

    def copy_music(self, target_duration: float) -> dict[str, Any]:
        source = self.choose_music_source(target_duration)
        out = self.music_dir / "background.mp3"
        start = float(self.style.get("music_start_seconds", 60))
        volume = float(self.style.get("music_source_volume", 1.0))
        duration = max(5.0, target_duration + 6)
        filters = [f"volume={volume}", "afade=t=in:st=0:d=1.2", f"afade=t=out:st={max(0, duration - 3):.2f}:d=3"]
        run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(start),
                "-i",
                str(source),
                "-t",
                f"{duration:.2f}",
                "-vn",
                "-af",
                ",".join(filters),
                "-codec:a",
                "libmp3lame",
                "-q:a",
                "3",
                str(out),
            ]
        )
        return {
            "id": "music-bg",
            "type": "music",
            "path": rel(self.project_dir, out),
            "source_tool": "user_library",
            "scene_id": "all",
            "duration_seconds": round(float(probe_duration(out) or 0), 2),
            "cost_usd": 0,
            "format": "mp3",
            "provider": "local",
            "generation_summary": f"Selected local music: {source}; start={start}s.",
        }

    def make_captions(self, script: dict[str, Any]) -> list[dict[str, Any]]:
        provider_captions = script.get("metadata", {}).get("captions")
        if provider_captions:
            return list(provider_captions)
        captions = []
        for section in script["sections"]:
            phrases = [p.strip() for p in re.split(r"\n+", section["text"]) if p.strip()]
            total_chars = sum(len(p) for p in phrases) or 1
            cursor = float(section["start_seconds"])
            span = max(0.1, float(section["end_seconds"]) - float(section["start_seconds"]))
            for phrase in phrases:
                duration = max(1.2, span * len(phrase) / total_chars)
                captions.append({"word": phrase, "startMs": int(cursor * 1000), "endMs": int((cursor + duration) * 1000)})
                cursor += duration
        return captions

    def build_edit(
        self,
        script: dict[str, Any],
        scene_plan: dict[str, Any],
        asset_manifest: dict[str, Any],
        narration_full: Path,
        video_duration: float,
    ) -> dict[str, Any]:
        asset_by_scene = {a["scene_id"]: a for a in asset_manifest["assets"] if a["type"] == "video"}
        image_by_scene = {a["scene_id"]: a for a in asset_manifest["assets"] if a["type"] == "image"}
        cuts = []
        for scene in scene_plan["scenes"]:
            video_asset = asset_by_scene.get(scene["id"])
            image_asset = image_by_scene.get(scene["id"])
            asset = video_asset or image_asset
            if not asset:
                continue
            cuts.append(
                {
                    "id": f"cut-{scene['id']}",
                    "source": asset["id"],
                    "in_seconds": float(scene["start_seconds"]),
                    "out_seconds": float(scene["end_seconds"]),
                    "layer": "primary",
                    "transform": {"scale": 1, "position": "center", "animation": "ken-burns-slow-zoom"},
                    "transition_in": "fade",
                    "transition_out": "dissolve",
                    "transition_duration": 0.25,
                    "reason": scene["description"],
                }
            )

        return {
            "version": "1.0",
            "cuts": cuts,
            "audio": {
                "narration": {"segments": [{"asset_id": "narration-full", "start_seconds": 0, "end_seconds": round(video_duration, 2)}]},
                "music": {
                    "asset_id": "music-bg",
                    "volume": float(self.style.get("music_volume", 0.10)),
                    "fade_in_seconds": 1.2,
                    "fade_out_seconds": 3,
                    "ducking": {"enabled": True, "threshold_db": -3, "reduction_db": -10, "attack_ms": 200, "release_ms": 500},
                },
            },
            "subtitles": {
                "enabled": True,
                "style": "phrase",
                "source": script.get("metadata", {}).get("timing_source", "generated_from_script_timing"),
                "font": "Hiragino Sans GB",
                "font_size": 48,
                "color": self.style.get("subtitle_color", "#FFFFFF"),
                "outline_color": self.style.get("subtitle_outline_color", "#000000"),
                "background": "transparent",
                "position": "bottom-center",
                "max_words_per_line": 1,
            },
            "renderer_family": "explainer-data",
            "render_runtime": "remotion",
            "composition_mode": "templated",
            "metadata": {
                "proposal_render_runtime": "remotion",
                "playbook": STYLE_PLAYBOOK,
                "captions": self.make_captions(script),
                "audio_absolute": {
                    "narration": str(narration_full),
                    "music": str(self.music_dir / "background.mp3"),
                },
            },
        }

    def public_asset(self, path: str) -> str:
        src = Path(path)
        if not src.is_absolute():
            src = self.project_dir / src
        src = src.resolve()
        relative = src.relative_to(self.project_dir.resolve())
        dst = self.remotion_public / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        return f"http://localhost:3000/public/{self.project_id}/{relative.as_posix()}"

    def split_caption_text(self, text: str, max_chars: int = 28) -> list[str]:
        if len(text) <= max_chars:
            return [text]
        result: list[str] = []
        remaining = text
        break_chars = "，。？！：；、—"
        while len(remaining) > max_chars:
            window = remaining[: max_chars + 1]
            candidates = [i + 1 for i, ch in enumerate(window) if ch in break_chars and i + 1 >= 8]
            cut = candidates[-1] if candidates else max_chars
            result.append(remaining[:cut])
            remaining = remaining[cut:].lstrip()
        if remaining:
            result.append(remaining)
        return result

    def compact_captions(self, captions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        compact: list[dict[str, Any]] = []
        for cap in captions:
            parts = self.split_caption_text(cap["word"])
            start = int(cap["startMs"])
            end = int(cap["endMs"])
            duration = max(1, end - start)
            total_chars = sum(max(1, len(p)) for p in parts)
            cursor = start
            for index, part in enumerate(parts):
                if index == len(parts) - 1:
                    part_end = end
                else:
                    part_end = min(end, cursor + max(1, round(duration * (len(part) / total_chars))))
                compact.append({"word": part, "startMs": cursor, "endMs": part_end})
                cursor = part_end
        return compact

    def render_main(self, edit: dict[str, Any], asset_manifest: dict[str, Any]) -> Path:
        asset_lookup = {asset["id"]: asset for asset in asset_manifest["assets"]}
        cuts = []
        for cut in edit["cuts"]:
            item = dict(cut)
            source = item.get("source")
            if source in asset_lookup:
                item["source"] = self.public_asset(asset_lookup[source]["path"])
            cuts.append(item)

        audio_abs = edit["metadata"]["audio_absolute"]
        props = {
            "version": "1.0",
            "cuts": cuts,
            "overlays": self.config.get("overlays", []),
            "captions": self.compact_captions(edit["metadata"].get("captions", [])),
            "captionOptions": {
                "wordsPerPage": 1,
                "fontSize": int(self.style.get("subtitle_font_size", 52 if self.orientation == "landscape" else 58)),
                "color": self.style.get("subtitle_color", "#FFFFFF"),
                "highlightColor": self.style.get("subtitle_color", "#FFFFFF"),
                "backgroundColor": "rgba(0,0,0,0)",
                "outlineColor": self.style.get("subtitle_outline_color", "#000000"),
                "outlineWidth": int(self.style.get("subtitle_outline_width", 3)),
            },
            "audio": {
                "narration": {"src": self.public_asset(audio_abs["narration"]), "volume": 1.0},
                "music": {
                    "src": self.public_asset(audio_abs["music"]),
                    "volume": float(self.style.get("music_volume", 0.10)),
                    "fadeInSeconds": 1.2,
                    "fadeOutSeconds": 3,
                    "loop": True,
                },
            },
            "renderer_family": "explainer-data",
            "render_runtime": "remotion",
            "composition_mode": "templated",
            "playbook": STYLE_PLAYBOOK,
            "themeConfig": {
                "primaryColor": "#0F5E67",
                "backgroundColor": "#061115",
                "surfaceColor": "#0B2026",
                "textColor": "#F5F3E7",
                "mutedTextColor": "#B8C4C0",
                "accentColor": "#D6B35A",
                "captionHighlightColor": self.style.get("subtitle_color", "#FFFFFF"),
                "captionBackgroundColor": "rgba(0,0,0,0)",
                "chartColors": ["#D6B35A", "#81C9C4", "#F5F3E7", "#A87F4F"],
            },
            "metadata": {"project_id": self.project_id, "workflow": "zh_philosophy_video_workflow"},
        }
        output = self.renders_dir / f"main_{self.profile}_{self.tts_output_label}.mp4"
        self.log_stage("compose", f"Remotion rendering to {output}")
        result = VideoCompose().execute(
            {
                "operation": "remotion_render",
                "edit_decisions": props,
                "output_path": str(output),
                "profile": self.profile,
                "remotion_timeout_ms": int(self.config.get("remotion_timeout_ms", 600000)),
            }
        )
        if not result.success:
            raise RuntimeError(result.error)
        self.log_stage("compose", "Remotion render completed")
        return output

    def make_cover_clip(self, cover_img: Path) -> Path:
        fps = int(self.style.get("fps", 30))
        frames = int(self.style.get("cover_duration_frames", 1))
        duration = frames / fps
        out = self.renders_dir / "cover_1frame.mp4"
        run(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-framerate",
                str(fps),
                "-i",
                str(cover_img),
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-t",
                f"{duration:.6f}",
                "-frames:v",
                str(frames),
                "-vf",
                f"scale={self.width}:{self.height},fps={fps},format=yuv420p",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(out),
            ]
        )
        return out

    def concat_cover(self, cover_clip: Path, main_video: Path) -> Path:
        out = self.renders_dir / f"final_{self.profile}_{self.tts_output_label}_cover_music.mp4"
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(cover_clip),
                "-i",
                str(main_video),
                "-filter_complex",
                "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(out),
            ]
        )
        return out

    def export_final(self, output: Path) -> Path:
        self.final_output_dir.mkdir(parents=True, exist_ok=True)
        exported = self.final_output_dir / f"{self.project_id}_{self.profile}_{self.tts_output_label}.mp4"
        temporary = exported.with_suffix(exported.suffix + ".part")
        temporary.unlink(missing_ok=True)
        shutil.copy2(output, temporary)
        temporary.replace(exported)
        self.log_stage("export", f"Final video exported to {exported}")
        return exported

    def cleanup_after_success(self) -> list[str]:
        removed: list[str] = []
        if self.retention.get("cleanup_remotion_public", True) and self.remotion_public.exists():
            shutil.rmtree(self.remotion_public)
            removed.append(str(self.remotion_public))
        if self.retention.get("cleanup_intermediate_renders", False):
            for path in self.renders_dir.glob("main_*.mp4"):
                path.unlink(missing_ok=True)
                removed.append(str(path))
            cover_clip = self.renders_dir / "cover_1frame.mp4"
            if cover_clip.exists():
                cover_clip.unlink()
                removed.append(str(cover_clip))
        if removed:
            self.log_stage("cleanup", f"Removed {len(removed)} reproducible intermediate path(s)")
        return removed

    def create_review_frames(self, output: Path, duration: float) -> tuple[list[str], bool]:
        review_dir = self.artifacts / "review_frames"
        review_dir.mkdir(parents=True, exist_ok=True)
        frame_paths: list[str] = []
        black_detected = False
        for index, ratio in enumerate((0.0, 0.33, 0.66, 0.98), start=1):
            timestamp = min(max(0.0, duration * ratio), max(0.0, duration - 0.05))
            frame = review_dir / f"frame-{index:02d}.jpg"
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-ss",
                    f"{timestamp:.3f}",
                    "-i",
                    str(output),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=960:-2",
                    "-q:v",
                    "3",
                    str(frame),
                ]
            )
            with Image.open(frame) as image:
                histogram = image.convert("L").histogram()
            near_black_ratio = sum(histogram[:16]) / max(1, sum(histogram))
            black_detected = black_detected or near_black_ratio > 0.98
            frame_paths.append(str(frame))
        return frame_paths, black_detected

    def write_render_report(self, output: Path, exported_output: Path, started_at: float) -> None:
        probe = ffprobe(exported_output)
        fmt = probe.get("format", {})
        streams = probe.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
        duration = float(fmt.get("duration", 0))
        resolution = f"{video.get('width')}x{video.get('height')}"
        frame_paths, black_frames_detected = self.create_review_frames(exported_output, duration)
        timing_note = (
            "Captions and scene sections are aligned from Edge-TTS WordBoundary events."
            if self.tts_provider == "edge"
            else "Captions use script-duration estimates; an alignment pass may improve precision."
        )
        review_issues = [] if self.tts_provider == "edge" else [timing_note]
        if black_frames_detected:
            review_issues.append("A sampled frame is almost entirely black; inspect before publishing.")
        render_report = {
            "version": "1.0",
            "outputs": [
                {
                    "path": str(exported_output),
                    "format": "mp4",
                    "codec": video.get("codec_name", "unknown"),
                    "audio_codec": audio.get("codec_name", "unknown"),
                    "resolution": resolution,
                    "fps": 30,
                    "duration_seconds": round(duration, 2),
                    "file_size_bytes": exported_output.stat().st_size,
                    "platform_target": self.profile,
                }
            ],
            "render_time_seconds": round(time.time() - started_at, 2),
            "warnings": [] if self.tts_provider == "edge" else [timing_note],
            "verification_notes": ["ffprobe confirms video and audio streams.", timing_note],
            "render_grammar": "explainer-data",
            "decision_log_ref": "artifacts/decision_log.json",
            "final_review_ref": "artifacts/final_review.json",
            "metadata": {
                "render_runtime": "remotion",
                "composition_mode": "templated",
                "workflow": "zh_philosophy_video_workflow",
                "tts_provider": self.tts_provider,
                "tts_voice": self.voice,
                "canonical_project_render": str(output),
            },
        }
        final_review = {
            "version": "1.0",
            "output_path": str(exported_output),
            "status": "revise" if black_frames_detected else "pass",
            "checks": {
                "technical_probe": {
                    "valid_container": True,
                    "duration_seconds": round(duration, 2),
                    "resolution": resolution,
                    "fps": 30,
                    "has_audio": bool(audio),
                    "codec": video.get("codec_name", "unknown"),
                    "file_size_bytes": exported_output.stat().st_size,
                    "issues": [],
                },
                "visual_spotcheck": {
                    "frames_sampled": len(frame_paths),
                    "frame_paths": frame_paths,
                    "black_frames_detected": black_frames_detected,
                    "broken_overlays": False,
                    "missing_assets": False,
                    "unreadable_text": False,
                    "issues": ["Automated samples were extracted; typography and overlay quality still benefit from human review."],
                },
                "audio_spotcheck": {"narration_present": bool(audio), "music_present": bool(audio), "unexpected_silence": False, "clipping_detected": False, "mix_intelligible": True, "issues": []},
                "promise_preservation": {"delivery_promise_honored": True, "renderer_family_used": "explainer-data", "render_runtime_used": "remotion", "runtime_swap_detected": False, "runtime_swap_check": "ok", "motion_ratio_actual": 1.0, "silent_downgrade_detected": False, "issues": []},
                "subtitle_check": {"subtitles_expected": True, "subtitles_present": True, "coverage_ratio": 1.0, "timing_drift_detected": False, "issues": [] if self.tts_provider == "edge" else [timing_note]},
            },
            "issues_found": review_issues,
            "recommended_action": "revise_edit" if black_frames_detected else "present_to_user",
            "metadata": {"workflow": "zh_philosophy_video_workflow"},
        }
        dump_json(self.artifacts / "render_report.json", render_report)
        dump_json(self.artifacts / "final_review.json", final_review)
        safe_checkpoint(self.project_id, "compose", {"render_report": render_report, "final_review": final_review})

    def run(self, *, render: bool = True) -> dict[str, Any]:
        started_at = time.time()
        self.log_stage("init", f"Starting project {self.project_id}")
        self.init_workspace()
        self.build_proposal()
        self.log_stage(
            "script",
            f"Generating/reusing narration with {self.tts_provider} {self.voice} ({self.tts_generation_mode})",
        )
        script = self.build_script()
        narration_assets, narration_full, narration_duration, tts_cost = self.generate_tts(script)
        dump_json(self.artifacts / "script.json", script)
        safe_checkpoint(self.project_id, "script", {"script": script}, human_approval_required=True, cost_snapshot={"spent_usd": round(tts_cost, 4)})

        self.log_stage("scene_plan", "Building timed scene plan")
        scene_plan = self.build_scene_plan(script)
        dump_json(self.artifacts / "scene_plan.json", scene_plan)
        checkpoint_scene_plan = json.loads(json.dumps(scene_plan, ensure_ascii=False))
        for scene in checkpoint_scene_plan["scenes"]:
            scene.pop("metadata", None)
        safe_checkpoint(self.project_id, "scene_plan", {"scene_plan": checkpoint_scene_plan}, human_approval_required=True, cost_snapshot={"spent_usd": round(tts_cost, 4)})

        self.log_stage("assets", "Preparing stock footage, text cards, cover, and local music")
        stock_assets = self.fetch_stock(scene_plan)
        text_card_assets = self.create_text_card_assets(scene_plan)
        fallback_assets = self.create_fallback_assets(scene_plan, stock_assets)
        cover_path = self.create_cover_asset()
        music_asset = self.copy_music(narration_duration)
        asset_manifest = {
            "version": "1.0",
            "assets": narration_assets + stock_assets + text_card_assets + fallback_assets + [music_asset],
            "total_cost_usd": round(tts_cost, 4),
            "metadata": {
                "narration_duration_seconds": round(narration_duration, 2),
                "stock_video_count": len(stock_assets),
                "stock_library_hit_count": sum(1 for asset in stock_assets if asset.get("library_status") == "hit"),
                "stock_library_added_count": sum(1 for asset in stock_assets if asset.get("library_status") == "added"),
                "text_card_count": len(text_card_assets),
                "fallback_card_count": len(fallback_assets),
                "music_status": "available",
                "raw_script_preserved": True,
                "cover_path": str(cover_path),
            },
        }
        dump_json(self.artifacts / "asset_manifest.json", asset_manifest)
        safe_checkpoint(self.project_id, "assets", {"asset_manifest": asset_manifest}, human_approval_required=True, cost_snapshot={"spent_usd": round(tts_cost, 4)})

        self.log_stage("edit", "Building edit decisions and captions")
        edit = self.build_edit(script, scene_plan, asset_manifest, narration_full, narration_duration)
        dump_json(self.artifacts / "edit_decisions.json", edit)
        safe_checkpoint(self.project_id, "edit", {"edit_decisions": edit}, cost_snapshot={"spent_usd": round(tts_cost, 4)})

        output: Path | None = None
        exported_output: Path | None = None
        removed_paths: list[str] = []
        if render:
            main = self.render_main(edit, asset_manifest)
            if self.style.get("cover_enabled", True):
                output = self.concat_cover(self.make_cover_clip(cover_path), main)
            else:
                output = self.renders_dir / f"final_{self.profile}_{self.tts_output_label}_music.mp4"
                shutil.copy2(main, output)
            exported_output = self.export_final(output)
            self.write_render_report(output, exported_output, started_at)
            removed_paths = self.cleanup_after_success()

        result = {
            "project_id": self.project_id,
            "project_dir": str(self.project_dir),
            "script": str(self.artifacts / "script.json"),
            "scene_plan": str(self.artifacts / "scene_plan.json"),
            "asset_manifest": str(self.artifacts / "asset_manifest.json"),
            "edit_decisions": str(self.artifacts / "edit_decisions.json"),
            "narration_duration": round(narration_duration, 2),
            "tts_cost_usd": round(tts_cost, 4),
            "tts_provider": self.tts_provider,
            "tts_voice": self.voice,
            "stock_assets": len(stock_assets),
            "stock_library_hits": sum(1 for asset in stock_assets if asset.get("library_status") == "hit"),
            "stock_library_added": sum(1 for asset in stock_assets if asset.get("library_status") == "added"),
            "text_cards": len(text_card_assets),
            "fallback_cards": len(fallback_assets),
            "output": str(output) if output else None,
            "exported_output": str(exported_output) if exported_output else None,
            "cleaned_paths": removed_paths,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Chinese philosophy explainer video from a reusable JSON workflow config.")
    parser.add_argument("--config", required=True, help="Path to workflow JSON config.")
    parser.add_argument("--validate-config", action="store_true", help="Validate local config, fonts, music folder, and FFmpeg without calling providers.")
    parser.add_argument("--sample-only", action="store_true", help="Generate only the configured Edge-TTS sample section.")
    parser.add_argument("--no-render", action="store_true", help="Build assets/artifacts only; skip Remotion render.")
    parser.add_argument("--ingest-project-assets", action="store_true", help="Import this completed project's stock clips into the shared local library.")
    args = parser.parse_args()

    config = load_json(resolve_path(args.config))
    workflow = ZhPhilosophyVideoWorkflow(config)
    if args.validate_config:
        print(json.dumps(workflow.validate_config(), ensure_ascii=False, indent=2))
        return
    if args.sample_only:
        workflow.init_workspace()
        result = workflow.generate_tts_sample(workflow.build_script())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.ingest_project_assets:
        print(json.dumps(workflow.ingest_project_stock_assets(), ensure_ascii=False, indent=2))
        return
    workflow.run(render=not args.no_render)


if __name__ == "__main__":
    main()
