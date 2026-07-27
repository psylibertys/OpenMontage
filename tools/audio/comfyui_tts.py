"""Qwen3-TTS generation through a local or SSH-tunnelled ComfyUI server."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool, Determinism, ExecutionMode, ResourceProfile, RetryPolicy,
    ToolResult, ToolRuntime, ToolStability, ToolStatus, ToolTier,
)
from tools._comfyui.client import ComfyUIClient, ComfyUIError
from tools._comfyui.metadata import COMFYUI_SETUP_OFFER, workflow_hash
from tools._comfyui.tts import TTS_WORKFLOWS, build_workflow, get_spec


class ComfyUITTS(BaseTool):
    name = "comfyui_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "text_to_speech"
    provider = "comfyui"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU
    dependencies = []
    setup_offer = COMFYUI_SETUP_OFFER
    install_instructions = (
        "Start ComfyUI with qwen3-tts-comfyui installed and set COMFYUI_SERVER_URL."
    )
    agent_skills = ["comfyui", "text-to-speech"]
    capabilities = ["text_to_speech", "voice_design", "voice_clone"]
    supports = {"seed": True, "voice_clone": True, "offline": True}
    best_for = ["local Qwen3-TTS narration", "reusable cloned voices", "no per-call API fee"]
    not_good_for = ["CPU-only generation", "unlicensed voice cloning"]
    fallback = "doubao_tts"
    fallback_tools = ["doubao_tts", "edge_tts"]
    input_schema = {
        "type": "object",
        "required": ["text", "workflow_template", "output_path"],
        "properties": {
            "text": {"type": "string"},
            "workflow_template": {"type": "string", "enum": sorted(TTS_WORKFLOWS)},
            "output_path": {"type": "string"},
            "instruct": {"type": "string"},
            "speaker": {"type": "string", "default": "Ryan"},
            "language": {"type": "string", "default": "Chinese"},
            "seed": {"type": "integer"},
            "temperature": {"type": "number"},
            "top_p": {"type": "number"},
            "top_k": {"type": "integer"},
            "max_new_tokens": {"type": "integer"},
            "reference_audio_path": {"type": "string"},
            "reference_text": {"type": "string"},
            "voice_name": {"type": "string", "default": "openmontage_voice"},
        },
    }
    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=12000, vram_mb=8000, disk_mb=100)
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["text", "workflow_template", "seed", "voice_name"]
    side_effects = ["writes audio file to output_path"]
    user_visible_verification = ["Listen for pronunciation, pacing, clipping, and identity consistency"]

    def __init__(self) -> None:
        self._client = ComfyUIClient()

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._client.is_available() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return max(10.0, len(inputs.get("text", "")) / 4)

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["setup_offer"] = self.setup_offer
        info["workflow_templates"] = sorted(TTS_WORKFLOWS)
        return info

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not self._client.is_available():
            return ToolResult(success=False, error=self._client.unavailable_reason())
        template = inputs["workflow_template"]
        spec = get_spec(template)
        output_path = Path(inputs["output_path"])
        if output_path.suffix.lower() != ".mp3":
            return ToolResult(
                success=False,
                error="Qwen3-TTS production workflows use SaveAudioMP3; output_path must end in .mp3",
            )
        seed = inputs["seed"] if inputs.get("seed") is not None else ComfyUIClient.random_seed()
        patched = {**inputs, "seed": seed}
        started = time.time()
        self._client.begin_job()
        try:
            source_audio_name = None
            if spec.get("source_audio"):
                source = inputs.get("reference_audio_path")
                if not source:
                    raise ComfyUIError(f"Workflow {template!r} requires reference_audio_path")
                source_audio_name = self._client.upload_file(
                    Path(source), f"om_{output_path.stem}_{seed}_reference{Path(source).suffix}"
                )
            workflow, output_node, provenance = build_workflow(
                template, patched, source_audio_name=source_audio_name
            )
            provenance.update({
                "workflow_hash_sha256": workflow_hash(workflow),
                "output_node": output_node,
            })
            paths = self._client.generate(workflow, output_node, output_path, timeout=900)
        except (ComfyUIError, ValueError) as exc:
            self._client.record_pending_upload_cleanup(output_path.parent, str(exc))
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            self._client.record_pending_upload_cleanup(output_path.parent, str(exc))
            return ToolResult(success=False, error=f"ComfyUI TTS generation failed: {exc}")
        return ToolResult(
            success=True,
            data={
                "provider": "comfyui", "model": spec["model"], "text": inputs["text"],
                "output": str(paths[0]), "format": paths[0].suffix.lstrip("."),
                "workflow_provenance": provenance,
                "cleanup_failures": self._client.cleanup_failures,
            },
            artifacts=[str(path) for path in paths], cost_usd=0.0,
            duration_seconds=round(time.time() - started, 2), seed=seed, model=spec["model"],
        )
