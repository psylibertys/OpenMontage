"""Parameter mapping for the four course Qwen3-TTS API workflows."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


WORKFLOW_DIR = Path(__file__).resolve().parent / "workflows" / "production"

TTS_WORKFLOWS: dict[str, dict[str, Any]] = {
    "qwen3_tts_custom_voice": {
        "file": "qwen3-tts-custom-voice.json", "output_node": "8", "engine": "14",
        "text": ("5", "positive"), "instruct": ("6", "positive"),
        "speaker": ("14", "speaker"), "model": "Qwen3-TTS 1.7B CustomVoice",
    },
    "qwen3_tts_voice_design": {
        "file": "qwen3-tts-voice-design.json", "output_node": "8", "engine": "4",
        "text": ("5", "positive"), "instruct": ("6", "positive"),
        "model": "Qwen3-TTS 1.7B VoiceDesign",
    },
    "qwen3_tts_voice_clone_save": {
        "file": "qwen3-tts-voice-clone-save.json", "output_node": "8", "engine": "14",
        "text": ("5", "positive"), "ref_text": ("6", "positive"),
        "source_audio": ("15", "audio"), "voice_name": ("18", "filename"),
        "model": "Qwen3-TTS 1.7B VoiceClone save",
    },
    "qwen3_tts_voice_clone_load": {
        "file": "qwen3-tts-voice-clone-load.json", "output_node": "8", "engine": "14",
        "text": ("18", "positive"), "voice_name": ("19", "filename"),
        "model": "Qwen3-TTS 1.7B VoiceClone load",
    },
}


def get_spec(template: str) -> dict[str, Any]:
    try:
        return TTS_WORKFLOWS[template]
    except KeyError as exc:
        raise ValueError(
            f"Unknown Qwen3-TTS workflow {template!r}; choose: {', '.join(sorted(TTS_WORKFLOWS))}"
        ) from exc


def _set(workflow: dict[str, Any], target: tuple[str, str], value: Any) -> None:
    workflow[target[0]]["inputs"][target[1]] = value


def build_workflow(
    template: str,
    inputs: dict[str, Any],
    *,
    source_audio_name: str | None = None,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    spec = get_spec(template)
    with open(WORKFLOW_DIR / spec["file"], encoding="utf-8") as handle:
        workflow = copy.deepcopy(json.load(handle))
    _set(workflow, spec["text"], inputs["text"])
    if spec.get("instruct") and inputs.get("instruct") is not None:
        _set(workflow, spec["instruct"], inputs["instruct"])
    if spec.get("ref_text"):
        if not inputs.get("reference_text"):
            raise ValueError(f"Workflow {template!r} requires reference_text")
        _set(workflow, spec["ref_text"], inputs["reference_text"])
    if spec.get("source_audio"):
        if not source_audio_name:
            raise ValueError(f"Workflow {template!r} requires reference_audio_path")
        _set(workflow, spec["source_audio"], source_audio_name)
    if spec.get("speaker") and inputs.get("speaker"):
        _set(workflow, spec["speaker"], inputs["speaker"])
    if spec.get("voice_name") and inputs.get("voice_name"):
        voice_name = inputs["voice_name"]
        if template.endswith("_load") and not str(voice_name).lower().endswith(".wav"):
            voice_name = f"{voice_name}.wav"
        _set(workflow, spec["voice_name"], voice_name)
    engine = workflow[spec["engine"]]["inputs"]
    for field in ("language", "temperature", "top_p", "top_k", "max_new_tokens"):
        if inputs.get(field) is not None and field in engine:
            engine[field] = inputs[field]
    if inputs.get("seed") is not None and "seed" in engine:
        engine["seed"] = int(inputs["seed"])
    if inputs.get("output_path"):
        workflow[spec["output_node"]]["inputs"]["filename_prefix"] = (
            f"audio/{Path(inputs['output_path']).stem}"
        )
    provenance = {
        "source": "bundled_production",
        "workflow_template": template,
        "workflow_file": spec["file"],
        "model": spec["model"],
    }
    return workflow, spec["output_node"], provenance
