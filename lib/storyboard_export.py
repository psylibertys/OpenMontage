"""Storyboard export validation and assembly.

Production-authoritative port of the t2i/i2v/voice lint rules from the
user-level copy-to-storyboard-json skill
(~/.claude/skills/copy-to-storyboard-json/scripts/build_storyboard_json.py,
snapshot 2026-10). The user-level skill stays independently usable; this
module is the version OpenMontage pipelines gate on.

Layering:
- schemas/artifacts/storyboard_export.schema.json validates STRUCTURE
  (required fields, 7-emotion enum, 5s render cap).
- This module adds SEMANTIC lint the schema cannot express with useful
  messages: forbidden prompt chars, single-sentence prompts, i2v anchor
  classes, pause markers, vocal tags, narration/emotion line alignment,
  sequential scene_ids, narration_all concatenation, and scene_plan
  traceability.

Pure library — no CLI, no filesystem writes. See
scripts/export_storyboard_json.py for the CLI wrapper.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Rule constants — ported verbatim from copy-to-storyboard-json (2026-10)
# ---------------------------------------------------------------------------

FORBIDDEN_PROMPT_CHARS = [":", "/", "[", "]"]

ALLOWED_EMOTIONS = {
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgusted",
    "surprised",
    "calm",
}

ALLOWED_SPEECH_MODELS_WITH_VOCAL_TAGS = {"speech-2.8-hd", "speech-2.8-turbo"}

ALLOWED_VOCAL_TAGS = {
    "(laughs)",
    "(chuckle)",
    "(coughs)",
    "(clear-throat)",
    "(groans)",
    "(breath)",
    "(pant)",
    "(inhale)",
    "(exhale)",
    "(gasps)",
    "(sniffs)",
    "(sighs)",
    "(snorts)",
    "(burps)",
    "(lip-smacking)",
    "(humming)",
    "(hissing)",
    "(emm)",
    "(sneezes)",
}

PAUSE_PATTERN = re.compile(r"<#(\d{1,2}(?:\.\d{1,2})?)#>")
ALL_ANGLE_MARKER_PATTERN = re.compile(r"<#.*?#>")

I2V_ALIGNMENT_HINTS = (
    "based on the provided image",
    "based on the original image",
    "the same character",
    "the same scene",
    "the same composition",
    "remains consistent",
    "remain consistent",
)
I2V_CAMERA_HINTS = (
    "camera performs",
    "camera slowly",
    "slow push-in",
    "slight camera drift",
    "slow zoom in",
    "cinematic orbit",
    "smooth and cinematic",
)
I2V_PHYSICS_HINTS = (
    "realistic motion",
    "natural physics",
    "no distortion",
    "no morphing",
    "consistent structure",
)
I2V_ACTION_HINTS = (
    "slowly ",
    "gently ",
    "slightly ",
    "then ",
)

#: Render cap. The schema hard-codes 5s; callers may tighten (not loosen)
#: via max_shot_seconds, e.g. to match a provider's generation limit.
MAX_SHOT_SECONDS = 5.0


class StoryboardExportError(ValueError):
    """Raised when a storyboard export fails schema or semantic lint."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _split_paragraphs(value: str) -> list[str]:
    return [part for part in (p.strip() for p in value.split("\n")) if part]


def _check_prompt_rules(prompt: Any, field: str, errors: list[str]) -> None:
    """Single-sentence + forbidden-character lint shared by t2i/i2v prompts."""
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append(f"{field} must be a non-empty string.")
        return
    for char in FORBIDDEN_PROMPT_CHARS:
        if char in prompt:
            errors.append(f"{field} cannot contain '{char}'.")
    if "\n" in prompt:
        errors.append(f"{field} must be a single sentence.")


def _check_i2v_prompt(prompt: Any, field: str, errors: list[str]) -> None:
    _check_prompt_rules(prompt, field, errors)
    if not isinstance(prompt, str) or not prompt.strip():
        return
    lower = prompt.lower()
    if not any(hint in lower for hint in I2V_ALIGNMENT_HINTS):
        errors.append(
            f"{field} must include an image-consistency anchor such as "
            "'Based on the provided image' or 'remains consistent'."
        )
    if not any(hint in lower for hint in I2V_CAMERA_HINTS):
        errors.append(f"{field} must include explicit camera movement language.")
    if not any(hint in lower for hint in I2V_PHYSICS_HINTS):
        errors.append(
            f"{field} must include physical constraint language such as "
            "realistic motion or no morphing."
        )
    if not any(hint in lower for hint in I2V_ACTION_HINTS):
        errors.append(
            f"{field} must include continuous subject action language such as "
            "slowly/gently/slightly/then."
        )


def _check_pause_markers(narration: str, field: str, errors: list[str]) -> None:
    if narration.startswith("<#") or narration.endswith("#>"):
        errors.append(f"{field} cannot start or end with a pause marker.")

    stripped = re.sub(r"\s+", "", narration)
    if re.search(
        r"<#\d{1,2}(?:\.\d{1,2})?#><#\d{1,2}(?:\.\d{1,2})?#>", stripped
    ):
        errors.append(f"{field} cannot contain consecutive pause markers.")

    for match in PAUSE_PATTERN.finditer(narration):
        seconds = float(match.group(1))
        if seconds < 0.01 or seconds > 99.99:
            errors.append(f"{field} contains a pause marker outside [0.01, 99.99].")
        left = narration[: match.start()].strip()
        right = narration[match.end() :].strip()
        if not left or not right:
            errors.append(
                f"{field} pause markers must appear between pronounceable text."
            )

    remaining = ALL_ANGLE_MARKER_PATTERN.sub("", narration)
    if re.search(r"<#|#>", remaining):
        errors.append(f"{field} contains an invalid pause marker format.")


def _check_vocal_tags(narration: str, speech_model: str, field: str, errors: list[str]) -> None:
    tags = re.findall(r"\([a-z-]+\)", narration)
    invalid = [tag for tag in tags if tag not in ALLOWED_VOCAL_TAGS]
    if invalid:
        errors.append(
            f"{field} contains unsupported vocal tags: {', '.join(sorted(set(invalid)))}"
        )
    if tags and speech_model not in ALLOWED_SPEECH_MODELS_WITH_VOCAL_TAGS:
        errors.append(
            f"{field} uses vocal tags, but speech_model '{speech_model}' does not support them."
        )


def _check_emotion(emotion: Any, narration: str, field: str, errors: list[str]) -> None:
    if not isinstance(emotion, str) or not emotion.strip():
        errors.append(f"{field} must be a non-empty string.")
        return
    emotion_lines = _split_paragraphs(emotion)
    narration_lines = _split_paragraphs(narration)
    if len(emotion_lines) != len(narration_lines):
        errors.append(
            f"{field} line count must match narration paragraph count "
            f"(expected {len(narration_lines)}, got {len(emotion_lines)})."
        )
    for item in emotion_lines:
        if item not in ALLOWED_EMOTIONS:
            errors.append(
                f"{field} contains unsupported emotion '{item}'. Allowed: "
                f"{', '.join(sorted(ALLOWED_EMOTIONS))}."
            )


# ---------------------------------------------------------------------------
# Semantic lint over the whole export
# ---------------------------------------------------------------------------


def lint_storyboard(
    storyboard: dict[str, Any],
    *,
    max_shot_seconds: float = MAX_SHOT_SECONDS,
) -> list[str]:
    """Run all semantic lint rules. Returns a list of human-readable errors."""
    if not 0 < max_shot_seconds <= MAX_SHOT_SECONDS:
        raise ValueError(
            f"max_shot_seconds must be in (0, {MAX_SHOT_SECONDS}] — the export "
            "format's hard render cap is 5 seconds; callers may only tighten it."
        )

    errors: list[str] = []
    speech_model = storyboard.get("speech_model") or ""
    scenes = storyboard.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return ["scenes must be a non-empty array."]

    for index, scene in enumerate(scenes, start=1):
        prefix = f"scenes[{index - 1}]"
        if not isinstance(scene, dict):
            errors.append(f"{prefix} must be an object.")
            continue

        scene_id = scene.get("scene_id")
        if scene_id != index:
            errors.append(
                f"{prefix}.scene_id must be continuous and start at 1 "
                f"(expected {index}, got {scene_id})."
            )

        narration = scene.get("narration")
        if not isinstance(narration, str) or not narration.strip():
            errors.append(f"{prefix}.narration must be a non-empty string.")
            narration = ""
        else:
            _check_pause_markers(narration, f"{prefix}.narration", errors)
            _check_vocal_tags(narration, speech_model, f"{prefix}.narration", errors)

        _check_emotion(scene.get("emotion"), narration, f"{prefix}.emotion", errors)
        _check_prompt_rules(scene.get("t2i_prompt"), f"{prefix}.t2i_prompt", errors)
        _check_i2v_prompt(scene.get("i2v_prompt"), f"{prefix}.i2v_prompt", errors)

        duration = scene.get("duration_seconds")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool):
            errors.append(f"{prefix}.duration_seconds must be a number.")
        elif duration <= 0:
            errors.append(f"{prefix}.duration_seconds must be greater than 0.")
        elif duration > max_shot_seconds:
            errors.append(
                f"{prefix}.duration_seconds cannot exceed {max_shot_seconds}."
            )

    expected = "\n".join(s.get("narration", "") for s in scenes if isinstance(s, dict))
    narration_all = storyboard.get("narration_all")
    if narration_all is not None and narration_all != expected:
        errors.append(
            "narration_all must be the scenes' narration values joined with newlines."
        )

    return errors


def validate_storyboard_export(
    storyboard: dict[str, Any],
    *,
    max_shot_seconds: float = MAX_SHOT_SECONDS,
) -> None:
    """Schema + semantic lint. Raises StoryboardExportError on any failure."""
    from schemas.artifacts import validate_artifact

    try:
        validate_artifact("storyboard_export", storyboard)
    except Exception as exc:  # jsonschema.ValidationError
        raise StoryboardExportError(
            f"storyboard_export failed schema validation: {exc}"
        ) from exc
    errors = lint_storyboard(storyboard, max_shot_seconds=max_shot_seconds)
    if errors:
        raise StoryboardExportError(
            "storyboard_export failed lint:\n- " + "\n- ".join(errors)
        )


# ---------------------------------------------------------------------------
# Traceability against the canonical scene_plan
# ---------------------------------------------------------------------------


def check_traceability(
    storyboard: dict[str, Any],
    scene_plan: dict[str, Any],
) -> list[str]:
    """Every shot must trace to a real scene_plan scene; every scene_plan
    scene must be covered by at least one shot (a long scene may be split
    into multiple <=5s shots, so one-to-many is allowed, gaps are not)."""
    errors: list[str] = []
    plan_ids = [scene.get("id") for scene in scene_plan.get("scenes", [])]
    plan_id_set = {sid for sid in plan_ids if isinstance(sid, str)}

    covered: set[str] = set()
    shots = storyboard.get("scenes", [])
    for index, shot in enumerate(shots, start=1):
        ref = shot.get("scene_plan_scene_id")
        if ref not in plan_id_set:
            errors.append(
                f"scenes[{index - 1}].scene_plan_scene_id '{ref}' does not exist "
                "in the scene_plan."
            )
        else:
            covered.add(ref)

    missing = [sid for sid in plan_ids if sid not in covered and sid is not None]
    if missing:
        errors.append(
            "scene_plan scenes not covered by any export shot: " + ", ".join(missing)
        )
    return errors


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build_narration_all(storyboard: dict[str, Any]) -> str:
    """Canonical narration_all: scenes' narration values joined by newlines."""
    return "\n".join(
        scene.get("narration", "") for scene in storyboard.get("scenes", [])
    )
