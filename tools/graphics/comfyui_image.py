"""ComfyUI image generation via a local or remote ComfyUI server.

Default workflow: Krea 2 Low VRAM.
Supports custom workflows via the ``workflow_json`` input.
"""

from __future__ import annotations

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
from tools._comfyui.client import ComfyUIClient, ComfyUIError
from tools._comfyui.first_batch import build_workflow as build_first_batch_workflow
from tools._comfyui.first_batch import get_spec as get_first_batch_spec
from tools._comfyui.production import build_workflow as build_production_workflow
from tools._comfyui.production import get_spec as get_production_spec
from tools._comfyui.production import PRODUCTION_WORKFLOWS
from tools._comfyui.metadata import (
    BUNDLED_MODEL_STACKS,
    COMFYUI_SETUP_OFFER,
    missing_models_payload,
    model_stack,
    workflow_hash,
)

_WORKFLOWS = Path(__file__).resolve().parent.parent / "_comfyui" / "workflows"

# Models required by the default Krea 2 Low VRAM workflow.
_REQUIRED_MODELS = [
    "krea2_turbo_fp8_scaled.safetensors",
    "qwen3vl_4b_fp8_scaled.safetensors",
    "qwen_image_vae.safetensors",
]


class ComfyUIImage(BaseTool):
    name = "comfyui_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "comfyui"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []  # checked at runtime via server health
    setup_offer = COMFYUI_SETUP_OFFER
    install_instructions = (
        "Start a ComfyUI server and set COMFYUI_SERVER_URL "
        "(default http://localhost:8188).\n"
        "See https://github.com/comfyanonymous/ComfyUI for setup."
    )
    agent_skills = ["comfyui", "flux-best-practices"]

    capabilities = ["text_to_image"]
    supports = {
        "seed": True,
        "custom_size": True,
        "custom_workflow": True,
        "custom_output_node": True,
        "offline": True,
    }
    best_for = [
        "local GPU generation without API costs",
        "Blackwell / DGX Spark hardware where diffusers is unsupported",
        "full control over sampling via custom ComfyUI workflows",
    ]
    not_good_for = [
        "setups without a running ComfyUI server",
        "CPU-only machines",
    ]
    fallback = "flux_image"
    fallback_tools = ["flux_image", "local_diffusion", "openai_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Text prompt for image generation"},
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
            "steps": {"type": "integer", "default": 20},
            "guidance": {
                "type": "number",
                "description": (
                    "Not supported by bundled templates, whose distilled CFG is fixed at 1; "
                    "passing this field with workflow_template fails closed."
                ),
            },
            "seed": {"type": "integer", "description": "Random if omitted"},
            "output_path": {"type": "string", "description": "Where to save the image"},
            "workflow_json": {
                "type": "string",
                "description": "Optional full ComfyUI workflow JSON. Requires output_node.",
            },
            "workflow_path": {
                "type": "string",
                "description": "Optional path to a ComfyUI workflow JSON file. Requires output_node.",
            },
            "workflow_template": {
                "type": "string",
                "enum": [
                    "krea2_low_vram",
                    "krea2_extra_pass",
                    "z_image_turbo_gguf",
                    "seedvr2_upscale",
                    "flux2_klein_4ref",
                    "flux2_klein_inpaint",
                ],
                "default": "krea2_low_vram",
                "description": "Bundled, parameterized first-batch API workflow.",
            },
            "aspect_preset": {
                "type": "string",
                "enum": ["portrait_9_16", "landscape_16_9"],
                "default": "portrait_9_16",
            },
            "reference_image_path": {
                "type": "string",
                "description": "Source image required by SeedVR2 templates.",
            },
            "reference_image_paths": {
                "type": "array",
                "minItems": 4,
                "maxItems": 4,
                "items": {"type": "string"},
                "description": "Exactly four local reference images for flux2_klein_4ref.",
            },
            "mask_image_path": {
                "type": "string",
                "description": (
                    "Optional white-on-black mask for flux2_klein_inpaint. "
                    "If omitted, reference_image_path must already carry a ComfyUI alpha mask."
                ),
            },
            "megapixels": {
                "type": "number",
                "default": 1.0,
                "description": "Output megapixels for FLUX.2 reference workflows.",
            },
            "resolution": {
                "type": "integer",
                "description": "Target SeedVR2 resolution; source aspect ratio is preserved.",
            },
            "output_node": {
                "type": "string",
                "description": "ComfyUI output node ID for custom workflow_json/workflow_path.",
            },
            "workflow_name": {
                "type": "string",
                "description": "Optional human-readable provenance label for a custom workflow.",
            },
            "workflow_model": {
                "type": "string",
                "description": "Optional model/provenance label for a custom workflow.",
            },
            "workflow_model_stack": {
                "type": "array",
                "description": (
                    "Optional provenance metadata for custom workflow dependencies. "
                    "Items should include name, role, quantization, and LoRA strengths when known."
                ),
                "items": {"type": "object"},
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=8000, vram_mb=8000, disk_mb=500, network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["prompt", "width", "height", "steps", "seed"]
    side_effects = ["writes image file to output_path"]
    user_visible_verification = ["Inspect generated image for quality and prompt adherence"]

    def __init__(self) -> None:
        self._client = ComfyUIClient()

    def get_status(self) -> ToolStatus:
        if not self._client.is_available():
            return ToolStatus.UNAVAILABLE
        _, missing = self._client.check_models(_REQUIRED_MODELS)
        if missing:
            return ToolStatus.DEGRADED
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return float(inputs.get("steps", 20)) * 1.5

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["setup_offer"] = self.setup_offer
        info["bundled_model_stack"] = BUNDLED_MODEL_STACKS["krea2-low-vram"]
        info["default_workflow_template"] = "krea2_low_vram"
        return info

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        workflow_template = inputs.get("workflow_template")
        if not workflow_template and not inputs.get("workflow_json") and not inputs.get("workflow_path"):
            workflow_template = "krea2_low_vram"
            inputs = {**inputs, "workflow_template": workflow_template}
        if workflow_template and "guidance" in inputs:
            return ToolResult(
                success=False,
                error=(
                    f"Workflow template {workflow_template!r} keeps its distilled CFG fixed at 1; "
                    "guidance is not a replaceable parameter. Remove guidance or use an "
                    "explicit custom API-format workflow with its own mapped guidance node."
                ),
            )
        custom_workflow = bool(
            inputs.get("workflow_json") or inputs.get("workflow_path") or workflow_template
        )
        if custom_workflow and not workflow_template and not inputs.get("output_node"):
            return ToolResult(
                success=False,
                error=(
                    "Custom ComfyUI workflows require output_node so OpenMontage "
                    "knows which ComfyUI node to download artifacts from."
                ),
            )

        if not self._client.is_available():
            return ToolResult(
                success=False,
                error=self._client.unavailable_reason(),
            )

        if workflow_template == "krea2_low_vram":
            _, missing = self._client.check_models(_REQUIRED_MODELS)
            if missing:
                return ToolResult(
                    success=False,
                    data=missing_models_payload(
                        missing,
                        workflow_key="krea2-low-vram",
                        workflow_name="krea2-low-vram.json",
                    ),
                    error=(
                        f"ComfyUI server is running but missing required models: "
                        f"{', '.join(missing)}.\n"
                        f"See data.missing_models for destination hints and download URLs."
                    ),
                )

        start = time.time()
        seed = inputs["seed"] if inputs.get("seed") is not None else ComfyUIClient.random_seed()
        width = inputs.get("width", 1024)
        height = inputs.get("height", 1024)
        steps = inputs.get("steps", 20)
        guidance = inputs.get("guidance", 3.5)
        output_path = Path(inputs.get("output_path", f"comfyui_image_{seed}.png"))
        self._client.begin_job()

        try:
            template_provenance = None
            if workflow_template:
                is_production = workflow_template in PRODUCTION_WORKFLOWS
                spec = (
                    get_production_spec(workflow_template, media="image")
                    if is_production
                    else get_first_batch_spec(workflow_template, media="image")
                )
                uploads: dict[str, Any] = {}
                source_image_name = None
                if spec.get("source_image"):
                    source_path = inputs.get("reference_image_path")
                    if not source_path:
                        raise ComfyUIError(
                            f"Workflow template {workflow_template!r} requires reference_image_path"
                        )
                    upload_path = Path(source_path)
                    temporary_masked_path = None
                    if workflow_template == "flux2_klein_inpaint" and inputs.get("mask_image_path"):
                        temporary_masked_path = self._prepare_inpaint_upload(
                            upload_path, Path(inputs["mask_image_path"]), output_path, seed
                        )
                        upload_path = temporary_masked_path
                    try:
                        source_image_name = self._client.upload_image(
                            upload_path,
                            f"om_{output_path.stem}_{seed}_source{upload_path.suffix or '.png'}",
                        )
                    finally:
                        if temporary_masked_path is not None:
                            temporary_masked_path.unlink(missing_ok=True)
                    uploads["source_image"] = source_image_name
                if spec.get("reference_images"):
                    paths = inputs.get("reference_image_paths") or []
                    if len(paths) != 4:
                        raise ComfyUIError(
                            f"Workflow template {workflow_template!r} requires exactly four "
                            "reference_image_paths"
                        )
                    uploads["reference_images"] = [
                        self._client.upload_image(
                            Path(path), f"om_{output_path.stem}_{seed}_ref_{i}{Path(path).suffix or '.png'}"
                        )
                        for i, path in enumerate(paths, start=1)
                    ]
                if is_production:
                    workflow, output_node, template_provenance = build_production_workflow(
                        workflow_template, inputs, media="image", uploads=uploads
                    )
                else:
                    workflow, output_node, template_provenance = build_first_batch_workflow(
                        workflow_template,
                        inputs,
                        media="image",
                        source_image_name=source_image_name,
                    )
                width = template_provenance.get("width") or width
                height = template_provenance.get("height") or height
            elif custom_workflow:
                workflow = self._load_custom_workflow(inputs)
                output_node = str(inputs["output_node"])
            else:
                workflow = ComfyUIClient.load_workflow(_WORKFLOWS / "flux2-txt2img.json")
                workflow = ComfyUIClient.patch_workflow(workflow, {
                    "4": {"text": inputs["prompt"]},
                    "5": {"guidance": guidance},
                    "6": {"width": width, "height": height, "batch_size": 1},
                    "7": {"noise_seed": seed},
                    "10": {"steps": steps, "width": width, "height": height},
                    "13": {"filename_prefix": output_path.stem},
                })
                output_node = "13"

            provenance = self._workflow_provenance(
                inputs, custom_workflow, output_node, workflow
            )
            if template_provenance:
                provenance = {
                    **template_provenance,
                    "workflow_hash_sha256": workflow_hash(workflow),
                    "output_node": output_node,
                }
            paths = self._client.generate(
                workflow, output_node=output_node, dest=output_path, timeout=600,
            )

        except ComfyUIError as exc:
            self._client.record_pending_upload_cleanup(output_path.parent, str(exc))
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            self._client.record_pending_upload_cleanup(output_path.parent, str(exc))
            return ToolResult(success=False, error=f"ComfyUI image generation failed: {exc}")

        model_name = self._model_name(inputs, custom_workflow)
        return ToolResult(
            success=True,
            data={
                "provider": "comfyui",
                "model": model_name,
                "prompt": inputs["prompt"],
                "width": width,
                "height": height,
                "steps": steps,
                "guidance": guidance,
                "output": str(paths[0]),
                "format": "png",
                "workflow_provenance": provenance,
                "cleanup_failures": self._client.cleanup_failures,
            },
            artifacts=[str(p) for p in paths],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model=model_name,
        )

    @staticmethod
    def _load_custom_workflow(inputs: dict[str, Any]) -> dict:
        if inputs.get("workflow_json"):
            return json.loads(inputs["workflow_json"])
        return ComfyUIClient.load_workflow(Path(inputs["workflow_path"]))

    @staticmethod
    def _prepare_inpaint_upload(
        source_path: Path, mask_path: Path, output_path: Path, seed: int
    ) -> Path:
        """Pack a white-on-black mask into the alpha convention LoadImage emits."""
        from PIL import Image, ImageOps

        output_path.parent.mkdir(parents=True, exist_ok=True)
        target = output_path.parent / f".{output_path.stem}.{seed}.inpaint-input.png"
        with Image.open(source_path) as source, Image.open(mask_path) as mask:
            rgba = source.convert("RGBA")
            white_is_edit = mask.convert("L").resize(rgba.size, Image.Resampling.LANCZOS)
            rgba.putalpha(ImageOps.invert(white_is_edit))
            rgba.save(target, format="PNG")
        return target

    @staticmethod
    def _model_name(inputs: dict[str, Any], custom_workflow: bool) -> str:
        if not custom_workflow:
            return "flux2-dev-nvfp4"
        if inputs.get("workflow_template"):
            template = inputs["workflow_template"]
            if template in PRODUCTION_WORKFLOWS:
                return get_production_spec(template, media="image")["model"]
            return get_first_batch_spec(template, media="image")["model"]
        return (
            inputs.get("workflow_model")
            or inputs.get("model")
            or inputs.get("workflow_name")
            or "custom-comfyui-workflow"
        )

    @staticmethod
    def _workflow_provenance(
        inputs: dict[str, Any],
        custom_workflow: bool,
        output_node: str,
        workflow: dict[str, Any],
    ) -> dict[str, Any]:
        if not custom_workflow:
            return {
                "source": "bundled",
                "workflow": "flux2-txt2img.json",
                "workflow_hash_sha256": workflow_hash(workflow),
                "model_stack": model_stack("flux2-txt2img", inputs),
                "output_node": output_node,
            }
        return {
            "source": "user_supplied",
            "workflow_name": inputs.get("workflow_name"),
            "workflow_path": inputs.get("workflow_path"),
            "model": inputs.get("workflow_model") or inputs.get("model"),
            "workflow_hash_sha256": workflow_hash(workflow),
            "model_stack": model_stack(None, inputs),
            "model_stack_source": (
                "caller_supplied"
                if inputs.get("workflow_model_stack")
                else "unknown_custom_workflow"
            ),
            "output_node": output_node,
        }
