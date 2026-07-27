"""Contract tests for ComfyUI provider tools.

These tests verify that the tools satisfy the BaseTool contract without
requiring a running ComfyUI server.  They check class attributes,
schemas, status reporting, and cost estimates.
"""

import json
from pathlib import Path

import pytest

from tools.base_tool import (
    BaseTool,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.graphics.comfyui_image import ComfyUIImage
from tools._comfyui.first_batch import build_workflow as build_first_batch_workflow
from tools._comfyui.production import build_workflow as build_production_workflow
from tools._comfyui.tts import build_workflow as build_tts_workflow
from tools.graphics.image_selector import ImageSelector
from tools.tool_registry import ToolRegistry
from tools.video.video_selector import VideoSelector
from tools.video.comfyui_video import ComfyUIVideo
from tools.audio.comfyui_tts import ComfyUITTS

TOOLS = [ComfyUIImage, ComfyUIVideo]
WORKFLOW_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "_comfyui" / "workflows"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ------------------------------------------------------------------
# Contract compliance
# ------------------------------------------------------------------

@pytest.mark.parametrize("cls", TOOLS, ids=lambda c: c.name)
class TestContract:

    def test_inherits_base_tool(self, cls):
        assert issubclass(cls, BaseTool)

    def test_has_required_identity(self, cls):
        tool = cls()
        assert tool.name
        assert tool.version
        assert tool.capability
        assert tool.provider == "comfyui"
        assert tool.tier == ToolTier.GENERATE
        assert tool.stability == ToolStability.EXPERIMENTAL
        assert tool.runtime == ToolRuntime.LOCAL_GPU

    def test_has_input_schema(self, cls):
        tool = cls()
        schema = tool.input_schema
        assert schema.get("type") == "object"
        assert "prompt" in schema.get("properties", {})
        assert "prompt" in schema.get("required", [])

    def test_has_capabilities(self, cls):
        tool = cls()
        assert len(tool.capabilities) > 0

    def test_has_agent_skills(self, cls):
        tool = cls()
        assert tool.agent_skills
        assert "comfyui" in tool.agent_skills

    def test_comfyui_layer3_skill_exists(self, cls):
        skill_path = PROJECT_ROOT / ".agents" / "skills" / "comfyui" / "SKILL.md"
        assert skill_path.exists()
        assert "output_node" in skill_path.read_text(encoding="utf-8")

    def test_has_fallbacks(self, cls):
        tool = cls()
        assert tool.fallback or tool.fallback_tools

    def test_cost_is_zero(self, cls):
        tool = cls()
        assert tool.estimate_cost({"prompt": "test"}) == 0.0

    def test_runtime_estimate_positive(self, cls):
        tool = cls()
        assert tool.estimate_runtime({"prompt": "test"}) > 0

    def test_get_info_returns_dict(self, cls):
        tool = cls()
        info = tool.get_info()
        assert isinstance(info, dict)
        assert info["name"] == tool.name
        assert info["provider"] == "comfyui"
        assert info["runtime"] == "local_gpu"
        assert info["setup_offer"]["env_var"] == "COMFYUI_SERVER_URL"

    def test_video_resource_profile_does_not_mandate_16gb(self, cls):
        if cls is not ComfyUIVideo:
            return
        tool = ComfyUIVideo()
        info = tool.get_info()
        assert info["resource_profile"]["vram_mb"] == 8000
        assert info["resource_profiles"]["provider_floor"]["vram_mb"] == 8000
        assert info["resource_profiles"]["bundled_wan22_14b_fp8"]["vram_mb"] == 16000
        assert "not a ComfyUI provider-wide requirement" in (
            info["resource_profiles"]["bundled_wan22_14b_fp8"]["applies_to"]
        )

    def test_status_unavailable_without_server(self, cls):
        """Without a running server, status should be UNAVAILABLE."""
        tool = cls()
        # Point to a port that's almost certainly not running ComfyUI
        tool._client.server_url = "http://127.0.0.1:19999"
        assert tool.get_status() == ToolStatus.UNAVAILABLE

    def test_idempotency_key_fields(self, cls):
        tool = cls()
        assert len(tool.idempotency_key_fields) > 0
        assert "prompt" in tool.idempotency_key_fields

    def test_custom_workflow_schema_requires_output_node_contract(self, cls):
        tool = cls()
        props = tool.input_schema.get("properties", {})
        assert "workflow_json" in props
        assert "workflow_path" in props
        assert "output_node" in props

    def test_custom_workflow_requires_output_node(self, cls):
        tool = cls()
        result = tool.execute({"prompt": "test", "workflow_json": "{}"})
        assert result.success is False
        assert "output_node" in result.error


# ------------------------------------------------------------------
# Workflow files
# ------------------------------------------------------------------

EXPECTED_WORKFLOWS = [
    "flux2-txt2img.json",
    "wan22-i2v-4step.json",
    "wan22-t2v-4step.json",
]


@pytest.mark.parametrize("filename", EXPECTED_WORKFLOWS)
def test_workflow_exists_and_valid_json(filename):
    path = WORKFLOW_DIR / filename
    assert path.exists(), f"Missing workflow: {path}"
    with open(path) as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert len(data) > 0


def test_flux2_workflow_has_templated_nodes():
    with open(WORKFLOW_DIR / "flux2-txt2img.json") as f:
        w = json.load(f)
    assert "4" in w  # CLIPTextEncode (prompt)
    assert "7" in w  # RandomNoise (seed)
    assert "13" in w  # SaveImage (output)


def test_i2v_workflow_has_templated_nodes():
    with open(WORKFLOW_DIR / "wan22-i2v-4step.json") as f:
        w = json.load(f)
    assert "93" in w   # CLIPTextEncode (prompt)
    assert "97" in w   # LoadImage (reference)
    assert "86" in w   # KSamplerAdvanced (seed)
    assert "108" in w  # SaveVideo (output)


def test_t2v_workflow_has_templated_nodes():
    with open(WORKFLOW_DIR / "wan22-t2v-4step.json") as f:
        w = json.load(f)
    assert "2" in w   # CLIPTextEncode (prompt)
    assert "12" in w  # KSamplerAdvanced (seed)
    assert "16" in w  # SaveVideo (output)


def test_t2v_workflow_uses_14b_compatible_vae():
    with open(WORKFLOW_DIR / "wan22-t2v-4step.json") as f:
        w = json.load(f)
    assert w["4"]["inputs"]["vae_name"] == "wan_2.1_vae.safetensors"


def test_t2v_metadata_stack_uses_14b_compatible_vae():
    from tools._comfyui.metadata import BUNDLED_MODEL_STACKS

    vae_entry = next(item for item in BUNDLED_MODEL_STACKS["wan22-t2v-4step"] if item["role"] == "vae")
    assert vae_entry["name"] == "wan_2.1_vae.safetensors"
    assert "Wan_2.1_ComfyUI_repackaged" in vae_entry["download_url"]


# ------------------------------------------------------------------
# Client unit tests
# ------------------------------------------------------------------

class TestClientHelpers:

    def test_load_workflow(self):
        from tools._comfyui.client import ComfyUIClient
        w = ComfyUIClient.load_workflow(WORKFLOW_DIR / "flux2-txt2img.json")
        assert isinstance(w, dict)
        assert "1" in w

    def test_patch_workflow(self):
        from tools._comfyui.client import ComfyUIClient
        w = ComfyUIClient.load_workflow(WORKFLOW_DIR / "flux2-txt2img.json")
        patched = ComfyUIClient.patch_workflow(w, {
            "4": {"text": "hello world"},
            "7": {"noise_seed": 123},
        })
        assert patched["4"]["inputs"]["text"] == "hello world"
        assert patched["7"]["inputs"]["noise_seed"] == 123
        # Original unchanged
        assert w["4"]["inputs"]["text"] == ""

    def test_patch_workflow_bad_node(self):
        from tools._comfyui.client import ComfyUIClient, ComfyUIError
        w = {"1": {"inputs": {"x": 1}}}
        with pytest.raises(ComfyUIError, match="not found"):
            ComfyUIClient.patch_workflow(w, {"99": {"x": 2}})

    def test_submit_surfaces_node_errors_before_http_error(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient, ComfyUIError

        class FakeResponse:
            status_code = 400

            def json(self):
                return {
                    "error": {"message": "Prompt outputs failed validation"},
                    "node_errors": {"4": {"class_type": "MissingNode"}},
                }

            def raise_for_status(self):
                raise AssertionError("HTTPError should not hide node_errors")

        monkeypatch.setattr(
            "tools._comfyui.client.requests.post",
            lambda *args, **kwargs: FakeResponse(),
        )

        with pytest.raises(ComfyUIError, match="Node errors"):
            ComfyUIClient("http://comfy.test").submit({})

    def test_random_seed_range(self):
        from tools._comfyui.client import ComfyUIClient
        for _ in range(100):
            s = ComfyUIClient.random_seed()
            assert 0 <= s < 2**32

    def test_generate_passes_history_item_type_to_view(self, monkeypatch, tmp_path):
        from tools._comfyui.client import ComfyUIClient

        client = ComfyUIClient("http://comfy.test")
        seen = {}

        monkeypatch.setattr(client, "submit", lambda workflow: "prompt-1")
        monkeypatch.setattr(client, "poll", lambda prompt_id, **kwargs: {
            "outputs": {
                "9": {
                    "images": [{
                        "filename": "preview.png",
                        "subfolder": "previews",
                        "type": "temp",
                    }]
                }
            }
        })

        def fake_download(filename, subfolder, dest, folder_type="output"):
            seen["filename"] = filename
            seen["subfolder"] = subfolder
            seen["folder_type"] = folder_type
            return Path(dest)

        monkeypatch.setattr(client, "download", fake_download)

        client.generate({"9": {"inputs": {}}}, "9", tmp_path / "preview.png")

        assert seen == {
            "filename": "preview.png",
            "subfolder": "previews",
            "folder_type": "temp",
        }

    def test_is_default_url_when_env_not_set(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient
        monkeypatch.delenv("COMFYUI_SERVER_URL", raising=False)
        client = ComfyUIClient()
        assert client.is_default_url is True

    def test_is_not_default_url_when_env_set(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient
        monkeypatch.setenv("COMFYUI_SERVER_URL", "http://myhost:9999")
        client = ComfyUIClient()
        assert client.is_default_url is False

    def test_unavailable_reason_default_url(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient
        monkeypatch.delenv("COMFYUI_SERVER_URL", raising=False)
        client = ComfyUIClient()
        msg = client.unavailable_reason()
        assert "COMFYUI_SERVER_URL" in msg
        assert ".env" in msg

    def test_unavailable_reason_custom_url(self, monkeypatch):
        from tools._comfyui.client import ComfyUIClient
        monkeypatch.setenv("COMFYUI_SERVER_URL", "http://myhost:9999")
        client = ComfyUIClient()
        msg = client.unavailable_reason()
        assert "myhost:9999" in msg
        assert "COMFYUI_SERVER_URL" not in msg


# ------------------------------------------------------------------
# Model discovery (offline, no server needed)
# ------------------------------------------------------------------

class TestModelRequirements:

    def test_model_check_accepts_comfyui_subdirectory_paths(self):
        from tools._comfyui.client import ComfyUIClient

        client = ComfyUIClient()
        client.list_models = lambda: {
            "diffusion_models": ["krea2/krea2_turbo_fp8_scaled.safetensors"],
            "vae": ["qwen_image_vae.safetensors"],
        }

        found, missing = client.check_models([
            "krea2_turbo_fp8_scaled.safetensors",
            "qwen_image_vae.safetensors",
            "missing.safetensors",
        ])

        assert found == [
            "krea2_turbo_fp8_scaled.safetensors",
            "qwen_image_vae.safetensors",
        ]
        assert missing == ["missing.safetensors"]

    def test_image_tool_has_required_models(self):
        from tools.graphics.comfyui_image import _REQUIRED_MODELS
        assert len(_REQUIRED_MODELS) > 0
        assert any("krea2" in m.lower() for m in _REQUIRED_MODELS)

    def test_video_tool_has_required_models_i2v(self):
        from tools.video.comfyui_video import _REQUIRED_MODELS_I2V
        assert len(_REQUIRED_MODELS_I2V) > 0
        assert any("i2v" in m.lower() for m in _REQUIRED_MODELS_I2V)

    def test_video_tool_has_required_models_t2v(self):
        from tools.video.comfyui_video import _REQUIRED_MODELS_T2V
        assert len(_REQUIRED_MODELS_T2V) > 0
        assert any("t2v" in m.lower() for m in _REQUIRED_MODELS_T2V)


# ------------------------------------------------------------------
# Custom workflow contract and provenance
# ------------------------------------------------------------------

class TestCustomWorkflowContract:

    @pytest.mark.parametrize(
        ("preset", "expected"),
        [
            ("portrait_9_16", (768, 1344)),
            ("landscape_16_9", (1344, 768)),
        ],
    )
    def test_first_batch_image_aspect_presets_patch_one_canonical_graph(
        self, preset, expected
    ):
        workflow, output_node, provenance = build_first_batch_workflow(
            "z_image_turbo_gguf",
            {"prompt": "test", "aspect_preset": preset, "seed": 123},
            media="image",
        )

        assert (workflow["162"]["inputs"]["width"], workflow["162"]["inputs"]["height"]) == expected
        assert workflow["6"]["inputs"]["text"] == "test"
        assert workflow["163"]["inputs"]["seed"] == 123
        assert output_node == "171"
        assert provenance["aspect_preset"] == preset

    def test_first_batch_seedvr2_follows_uploaded_source_aspect(self):
        workflow, output_node, provenance = build_first_batch_workflow(
            "seedvr2_upscale",
            {"seed": 77, "resolution": 2048},
            media="image",
            source_image_name="uploaded.png",
        )

        assert workflow["5"]["inputs"]["image"] == "uploaded.png"
        assert workflow["4"]["inputs"]["resolution"] == 2048
        assert output_node == "6"
        assert provenance["follows_source_aspect"] is True

    def test_image_first_batch_template_needs_no_manual_output_node(self, tmp_path):
        tool = ComfyUIImage()
        tool._client.is_available = lambda: True
        tool._client.check_models = lambda required: (list(required), [])
        seen = {}

        def fake_generate(workflow, output_node, dest, **kwargs):
            seen["workflow"] = workflow
            seen["output_node"] = output_node
            return [Path(dest)]

        tool._client.generate = fake_generate
        result = tool.execute({
            "prompt": "landscape test",
            "workflow_template": "krea2_low_vram",
            "aspect_preset": "landscape_16_9",
            "seed": 456,
            "output_path": str(tmp_path / "image.png"),
        })

        assert result.success is True
        assert seen["output_node"] == "199"
        assert seen["workflow"]["162"]["inputs"]["width"] == 1344
        assert seen["workflow"]["162"]["inputs"]["height"] == 768
        assert result.data["workflow_provenance"]["source"] == "bundled_first_batch"

    def test_bundled_image_template_rejects_unmapped_guidance(self, tmp_path):
        tool = ComfyUIImage()
        result = tool.execute({
            "prompt": "do not silently ignore this",
            "workflow_template": "krea2_low_vram",
            "guidance": 3.5,
            "output_path": str(tmp_path / "image.png"),
        })

        assert result.success is False
        assert "CFG fixed at 1" in result.error
        assert "not a replaceable parameter" in result.error

    def test_video_first_batch_template_uploads_source_and_patches_preset(self, tmp_path):
        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True
        tool._client.upload_image = lambda path, name: "uploaded-source.png"
        seen = {}

        def fake_generate(workflow, output_node, dest, **kwargs):
            seen["workflow"] = workflow
            seen["output_node"] = output_node
            return [Path(dest)]

        tool._client.generate = fake_generate
        source = tmp_path / "source.png"
        source.write_bytes(b"placeholder")
        result = tool.execute({
            "prompt": "move slowly",
            "workflow_template": "wan22_i2v_q6",
            "aspect_preset": "landscape_16_9",
            "reference_image_path": str(source),
            "num_frames": 49,
            "seed": 789,
            "output_path": str(tmp_path / "video.mp4"),
        })

        assert result.success is True
        assert seen["output_node"] == "122"
        assert seen["workflow"]["203"]["inputs"]["value"] == 1024
        assert seen["workflow"]["204"]["inputs"]["value"] == 576
        assert seen["workflow"]["205"]["inputs"]["value"] == 3
        assert seen["workflow"]["113"]["inputs"]["image"] == "uploaded-source.png"
        assert result.data["workflow_provenance"]["source"] == "bundled_first_batch"

    @pytest.mark.parametrize(
        ("requested", "expected_frames", "expected_bucket"),
        [(1.0, 17, 1.0), (2.6, 49, 3.0), (4.8, 81, 5.0)],
    )
    def test_wan_i2v_duration_seconds_selects_nearest_bucket(
        self, requested, expected_frames, expected_bucket
    ):
        workflow, _, provenance = build_first_batch_workflow(
            "wan22_i2v_q6",
            {"prompt": "move", "duration_seconds": requested},
            media="video",
            source_image_name="source.png",
        )
        assert provenance["num_frames"] == expected_frames
        assert provenance["requested_duration_seconds"] == requested
        assert provenance["selected_duration_seconds"] == expected_bucket
        assert workflow["205"]["inputs"]["value"] == (expected_frames - 1) // 16

    def test_wan_i2v_rejects_ambiguous_seconds_and_frames(self):
        with pytest.raises(ValueError, match="not both"):
            build_first_batch_workflow(
                "wan22_i2v_q6",
                {"prompt": "move", "duration_seconds": 3, "num_frames": 49},
                media="video",
                source_image_name="source.png",
            )

    def test_flux_four_reference_template_uploads_all_inputs(self, tmp_path):
        tool = ComfyUIImage()
        tool._client.is_available = lambda: True
        uploaded = []
        tool._client.upload_image = lambda path, name: uploaded.append(name) or name
        seen = {}
        tool._client.generate = lambda workflow, output_node, dest, **kwargs: (
            seen.update(workflow=workflow, output_node=output_node) or [Path(dest)]
        )
        refs = []
        for index in range(4):
            path = tmp_path / f"ref-{index}.png"
            path.write_bytes(b"placeholder")
            refs.append(str(path))
        result = tool.execute({
            "prompt": "same person in a library",
            "workflow_template": "flux2_klein_4ref",
            "reference_image_paths": refs,
            "aspect_preset": "portrait_9_16",
            "seed": 0,
            "output_path": str(tmp_path / "result.png"),
        })
        assert result.success is True
        assert len(uploaded) == 4
        assert seen["output_node"] == "203"
        assert seen["workflow"]["163"]["inputs"]["seed"] == 0

    def test_infinitetalk_template_uploads_image_and_audio(self, tmp_path):
        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True
        tool._client.upload_image = lambda path, name: "person.png"
        tool._client.upload_file = lambda path, name: "voice.mp3"
        seen = {}
        tool._client.generate = lambda workflow, output_node, dest, **kwargs: (
            seen.update(workflow=workflow, output_node=output_node) or [Path(dest)]
        )
        image = tmp_path / "person.png"
        audio = tmp_path / "voice.mp3"
        image.write_bytes(b"image")
        audio.write_bytes(b"audio")
        result = tool.execute({
            "prompt": "the person speaks naturally",
            "workflow_template": "wan_infinitetalk_short",
            "reference_image_path": str(image),
            "reference_audio_path": str(audio),
            "seed": 3,
            "output_path": str(tmp_path / "talk.mp4"),
        })
        assert result.success is True
        assert seen["output_node"] == "182"
        assert seen["workflow"]["32"]["inputs"]["image"] == "person.png"
        assert seen["workflow"]["171"]["inputs"]["audio"] == "voice.mp3"

    @pytest.mark.parametrize(
        ("template", "requested", "expected_frames", "expected_duration"),
        [
            ("wan_infinitetalk_short", 3.6, 49, 3.56),
            ("wan_infinitetalk_extend", 20.0, 49, 19.56),
        ],
    )
    def test_infinitetalk_duration_seconds_selects_nearest_bucket(
        self, template, requested, expected_frames, expected_duration
    ):
        workflow, _, provenance = build_production_workflow(
            template,
            {"prompt": "talk", "duration_seconds": requested},
            media="video",
            uploads={"source_image": "person.png", "source_audio": "voice.mp3"},
        )
        assert provenance["num_frames"] == expected_frames
        assert provenance["requested_duration_seconds"] == requested
        assert provenance["selected_duration_seconds"] == pytest.approx(expected_duration)
        spec_length_nodes = (
            ("129", "130")
            if template == "wan_infinitetalk_short"
            else ("129", "130", "183", "193", "200", "206", "212", "218", "224", "228", "236", "242")
        )
        assert all(workflow[node]["inputs"]["length"] == expected_frames for node in spec_length_nodes)

    def test_comfyui_tts_template_runs_without_manual_output_node(self, tmp_path):
        tool = ComfyUITTS()
        tool._client.is_available = lambda: True
        seen = {}
        tool._client.generate = lambda workflow, output_node, dest, **kwargs: (
            seen.update(workflow=workflow, output_node=output_node) or [Path(dest)]
        )
        result = tool.execute({
            "text": "你好，世界。",
            "workflow_template": "qwen3_tts_voice_design",
            "instruct": "平静温暖的中文女声",
            "seed": 0,
            "output_path": str(tmp_path / "voice.mp3"),
        })
        assert result.success is True
        assert seen["output_node"] == "8"
        assert seen["workflow"]["4"]["inputs"]["seed"] == 0
        assert result.data["workflow_provenance"]["source"] == "bundled_production"

    def test_image_custom_workflow_uses_caller_output_node_and_provenance(self, tmp_path):
        tool = ComfyUIImage()
        tool._client.is_available = lambda: True
        seen = {}

        def fake_generate(workflow, output_node, dest, **kwargs):
            seen["workflow"] = workflow
            seen["output_node"] = output_node
            return [Path(dest)]

        tool._client.generate = fake_generate

        result = tool.execute({
            "prompt": "test",
            "workflow_json": json.dumps({"99": {"inputs": {}}}),
            "output_node": "99",
            "workflow_model": "custom-flux",
            "output_path": str(tmp_path / "image.png"),
        })

        assert result.success is True
        assert seen["output_node"] == "99"
        assert result.model == "custom-flux"
        assert result.data["model"] == "custom-flux"
        assert result.data["workflow_provenance"]["source"] == "user_supplied"
        assert result.data["workflow_provenance"]["output_node"] == "99"
        assert result.data["workflow_provenance"]["workflow_hash_sha256"]
        assert result.data["workflow_provenance"]["model_stack_source"] == (
            "unknown_custom_workflow"
        )

    def test_video_custom_workflow_uses_caller_output_node_and_provenance(self, tmp_path):
        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True
        seen = {}

        def fake_generate(workflow, output_node, dest, **kwargs):
            seen["workflow"] = workflow
            seen["output_node"] = output_node
            return [Path(dest)]

        tool._client.generate = fake_generate

        result = tool.execute({
            "prompt": "test",
            "workflow_json": json.dumps({"42": {"inputs": {}}}),
            "output_node": "42",
            "workflow_model": "custom-wan",
            "output_path": str(tmp_path / "video.mp4"),
        })

        assert result.success is True
        assert seen["output_node"] == "42"
        assert result.model == "custom-wan"
        assert result.data["model"] == "custom-wan"
        assert result.data["workflow_provenance"]["source"] == "user_supplied"
        assert result.data["workflow_provenance"]["output_node"] == "42"
        assert result.data["workflow_provenance"]["workflow_hash_sha256"]
        assert result.data["workflow_provenance"]["model_stack_source"] == (
            "unknown_custom_workflow"
        )

    def test_custom_workflow_accepts_model_stack_provenance(self, tmp_path):
        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True
        tool._client.generate = lambda workflow, output_node, dest, **kwargs: [Path(dest)]

        result = tool.execute({
            "prompt": "test",
            "workflow_json": json.dumps({"42": {"inputs": {}}}),
            "output_node": "42",
            "workflow_model_stack": [{"role": "lora", "name": "style.safetensors"}],
            "output_path": str(tmp_path / "video.mp4"),
        })

        provenance = result.data["workflow_provenance"]
        assert provenance["model_stack"] == [{"role": "lora", "name": "style.safetensors"}]
        assert provenance["model_stack_source"] == "caller_supplied"

    def test_image_missing_models_are_structured(self):
        tool = ComfyUIImage()
        tool._client.is_available = lambda: True
        tool._client.check_models = lambda required: (
            [],
            ["qwen_image_vae.safetensors"],
        )

        result = tool.execute({"prompt": "test"})

        assert result.success is False
        assert result.data["provider"] == "comfyui"
        assert result.data["missing_models"][0]["name"] == "qwen_image_vae.safetensors"
        assert result.data["missing_models"][0]["destination_hint"] == "ComfyUI/models/vae/"
        assert result.data["missing_models"][0]["download_url"]

    def test_video_missing_models_are_structured(self):
        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True
        tool._client.check_models = lambda required: (
            [],
            ["wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors"],
        )

        result = tool.execute({"prompt": "test", "operation": "text_to_video"})

        assert result.success is False
        assert result.data["operation"] == "text_to_video"
        assert result.data["missing_models"][0]["role"] == "diffusion_model_high_noise"
        assert result.data["missing_models"][0]["download_url"]

    def test_default_image_workflow_routes_to_krea(self, tmp_path):
        tool = ComfyUIImage()
        tool._client.is_available = lambda: True
        tool._client.check_models = lambda required: (list(required), [])
        tool._client.generate = lambda workflow, output_node, dest, **kwargs: [Path(dest)]

        result = tool.execute({
            "prompt": "test",
            "output_path": str(tmp_path / "image.png"),
        })

        provenance = result.data["workflow_provenance"]
        assert provenance["source"] == "bundled_first_batch"
        assert provenance["workflow_template"] == "krea2_low_vram"
        assert provenance["output_node"] == "199"
        assert provenance["workflow_hash_sha256"]
        assert result.model == "Krea 2 Turbo FP8 Low VRAM"


class TestComfyUISetupOffer:

    def test_provider_menu_summary_includes_structured_setup_offer(self):
        registry = ToolRegistry()
        tool = ComfyUIImage()
        tool._client.is_available = lambda: False
        registry.register(tool)
        registry._discovered_packages.add("tools")

        summary = registry.provider_menu_summary()

        offer = summary["setup_offers"][0]
        assert offer["tool"] == "comfyui_image"
        assert offer["env_var"] == "COMFYUI_SERVER_URL"
        assert offer["default_url"] == "http://localhost:8188"
        assert offer["health_check"] == "GET /system_stats"


# ------------------------------------------------------------------
# Operation-specific video readiness
# ------------------------------------------------------------------

class TestVideoOperationReadiness:

    def test_video_tool_reports_partial_operation_readiness(self):
        from tools.video.comfyui_video import _REQUIRED_MODELS_I2V, _REQUIRED_MODELS_T2V

        tool = ComfyUIVideo()
        tool._client.is_available = lambda: True

        def fake_check_models(required):
            if required == _REQUIRED_MODELS_T2V:
                return list(required), []
            if required == _REQUIRED_MODELS_I2V:
                return [], list(required)
            return [], list(required)

        tool._client.check_models = fake_check_models

        assert tool.get_status() == ToolStatus.AVAILABLE
        assert tool.is_operation_available("text_to_video") is True
        assert tool.is_operation_available("image_to_video") is False
        assert tool.operation_statuses() == {
            "text_to_video": "available",
            "image_to_video": "degraded",
        }

    def test_video_selector_filters_operation_unready_tools(self):
        class PartialVideoTool(BaseTool):
            name = "partial_video"
            capability = "video_generation"
            provider = "partial"
            supports = {"image_to_video": True}
            input_schema = {"type": "object", "properties": {}}

            def is_operation_available(self, operation):
                return operation == "text_to_video"

            def execute(self, inputs):
                raise AssertionError("not used")

        selector = VideoSelector()
        candidates = [PartialVideoTool()]

        assert selector._filter_candidates(
            {"operation": "image_to_video"}, candidates
        ) == []

    def test_video_selector_rank_uses_target_operation_for_readiness(self):
        class PartialVideoTool(BaseTool):
            name = "partial_video"
            capability = "video_generation"
            provider = "partial"
            supports = {"image_to_video": True}
            input_schema = {"type": "object", "properties": {}}

            def is_operation_available(self, operation):
                return operation == "text_to_video"

            def execute(self, inputs):
                raise AssertionError("not used")

        selector = VideoSelector()
        candidates = [PartialVideoTool()]
        rank_inputs = selector._rank_inputs({
            "operation": "rank",
            "target_operation": "image_to_video",
        })

        assert rank_inputs["operation"] == "image_to_video"
        assert selector._filter_candidates(rank_inputs, candidates) == []


# ------------------------------------------------------------------
# Custom-workflow selector eligibility
# ------------------------------------------------------------------

class _DegradedComfyVideo(BaseTool):
    """Server reachable, but bundled WAN models missing -> DEGRADED, no
    operation ready. Stands in for comfyui_video on a low-VRAM box."""

    name = "comfyui_video"
    capability = "video_generation"
    provider = "comfyui"
    supports = {"custom_workflow": True, "image_to_video": True}
    input_schema = {"type": "object", "properties": {"workflow_json": {"type": "string"}}}

    def get_status(self):
        return ToolStatus.DEGRADED

    def is_operation_available(self, operation):
        return False

    def execute(self, inputs):
        raise AssertionError("not used")


class _DegradedComfyImage(BaseTool):
    name = "comfyui_image"
    capability = "image_generation"
    provider = "comfyui"
    supports = {"custom_workflow": True}
    input_schema = {"type": "object", "properties": {"workflow_json": {"type": "string"}}}

    def get_status(self):
        return ToolStatus.DEGRADED

    def execute(self, inputs):
        raise AssertionError("not used")


class TestCustomWorkflowSelectorEligibility:

    def test_video_selector_passes_degraded_tool_for_custom_workflow(self):
        selector = VideoSelector()
        candidates = [_DegradedComfyVideo()]
        inputs = {
            "prompt": "x",
            "operation": "text_to_video",
            "workflow_json": "{}",
            "output_node": "14",
        }
        # Without the custom-workflow path this DEGRADED, operation-unready tool
        # would be filtered out; with it, it is eligible and selectable.
        filtered = selector._filter_candidates(inputs, candidates)
        assert [t.name for t in filtered] == ["comfyui_video"]
        assert selector._tool_selectable(candidates[0], inputs) is True

    def test_video_selector_custom_workflow_requires_output_node(self):
        selector = VideoSelector()
        candidates = [_DegradedComfyVideo()]
        inputs = {"prompt": "x", "operation": "text_to_video", "workflow_json": "{}"}
        # output_node missing -> not eligible -> filtered out.
        assert selector._filter_candidates(inputs, candidates) == []
        assert selector._tool_selectable(candidates[0], inputs) is False

    def test_video_selector_custom_workflow_needs_server(self):
        class _OfflineComfyVideo(_DegradedComfyVideo):
            def get_status(self):
                return ToolStatus.UNAVAILABLE

        selector = VideoSelector()
        candidates = [_OfflineComfyVideo()]
        inputs = {
            "prompt": "x",
            "operation": "text_to_video",
            "workflow_json": "{}",
            "output_node": "14",
        }
        assert selector._filter_candidates(inputs, candidates) == []

    def test_image_selector_passes_degraded_tool_for_custom_workflow(self):
        selector = ImageSelector()
        candidates = [_DegradedComfyImage()]
        inputs = {"prompt": "x", "workflow_json": "{}", "output_node": "13"}
        filtered = selector._filter_candidates(inputs, candidates)
        assert [t.name for t in filtered] == ["comfyui_image"]
        assert selector._tool_selectable(candidates[0], inputs) is True

    def test_image_selector_custom_workflow_requires_output_node(self):
        selector = ImageSelector()
        candidates = [_DegradedComfyImage()]
        inputs = {"prompt": "x", "workflow_json": "{}"}
        assert selector._filter_candidates(inputs, candidates) == []
        assert selector._tool_selectable(candidates[0], inputs) is False

    def test_selector_schemas_expose_custom_workflow_inputs(self):
        for selector in (VideoSelector(), ImageSelector()):
            props = selector.input_schema["properties"]
            for field in (
                "workflow_json",
                "workflow_path",
                "output_node",
                "workflow_name",
                "workflow_model",
                "workflow_model_stack",
            ):
                assert field in props, f"{selector.name} missing {field}"


class TestProductionWorkflowTemplates:

    @pytest.mark.parametrize(
        ("template", "output_node", "prompt_node", "image_node", "video_node", "size_nodes", "seed_node", "fps"),
        [
            ("wan22_animate_character", "56", "276", "55", "181", ("43", "49"), "58", 16),
            ("wan_scail_character", "139", "417", "106", "130", ("203", "204"), "348", 24),
        ],
    )
    def test_character_motion_templates_map_driver_and_follow_its_length(
        self, template, output_node, prompt_node, image_node, video_node,
        size_nodes, seed_node, fps,
    ):
        workflow, actual_output, provenance = build_production_workflow(
            template,
            {
                "prompt": "person follows the driving motion",
                "seed": 123,
                "aspect_preset": "landscape_16_9",
                "output_path": "projects/demo/assets/video/motion.mp4",
            },
            media="video",
            uploads={"source_image": "character.png", "source_video": "drive.mp4"},
        )

        assert actual_output == output_node
        assert workflow[output_node]["class_type"] == "VHS_VideoCombine"
        assert workflow[output_node]["inputs"]["save_output"] is True
        assert workflow[prompt_node]["inputs"]["positive"] == "person follows the driving motion"
        assert workflow[image_node]["inputs"]["image"] == "character.png"
        assert workflow[video_node]["inputs"]["video"] == "drive.mp4"
        assert [workflow[node]["inputs"]["value"] for node in size_nodes] == [832, 480]
        assert workflow[seed_node]["inputs"]["seed"] == 123
        assert workflow[output_node]["inputs"]["frame_rate"] == fps
        assert provenance["duration_mode"] == "driving_video"
        assert provenance["num_frames"] is None

        frame_consumers = [
            node for node in workflow.values()
            if node["class_type"] in {"WanVideoAnimateEmbeds", "WanVideoEmptyEmbeds"}
        ]
        assert len(frame_consumers) == 1
        assert frame_consumers[0]["inputs"]["num_frames"] == [video_node, 1]

    @pytest.mark.parametrize("template", ["wan22_animate_character", "wan_scail_character"])
    def test_character_motion_templates_reject_ignored_num_frames(self, template):
        with pytest.raises(ValueError, match="derives its frame count from driving_video_path"):
            build_production_workflow(
                template,
                {"prompt": "person", "num_frames": 81},
                media="video",
                uploads={"source_image": "character.png", "source_video": "drive.mp4"},
            )

    @pytest.mark.parametrize("template", ["wan22_animate_character", "wan_scail_character"])
    def test_character_motion_templates_record_requested_driver_duration(self, template):
        _, _, provenance = build_production_workflow(
            template,
            {"prompt": "person", "duration_seconds": 2.5},
            media="video",
            uploads={"source_image": "character.png", "source_video": "drive.mp4"},
        )
        assert provenance["duration_mode"] == "driving_video"
        assert provenance["requested_duration_seconds"] == 2.5
        assert provenance["selected_duration_seconds"] == 2.5

    def test_comfyui_tts_contract_and_setup_offer(self):
        tool = ComfyUITTS()
        assert tool.tier == ToolTier.VOICE
        assert tool.runtime == ToolRuntime.LOCAL_GPU
        assert tool.input_schema["required"] == ["text", "workflow_template", "output_path"]
        assert tool.get_info()["setup_offer"]["env_var"] == "COMFYUI_SERVER_URL"

    def test_image_schema_defaults_to_krea_and_keeps_gguf_as_fallback(self):
        template = ComfyUIImage.input_schema["properties"]["workflow_template"]
        assert template["default"] == "krea2_low_vram"
        assert template["enum"][0] == "krea2_low_vram"
        assert "z_image_turbo_gguf" in template["enum"]
        assert "z_image_turbo_nunchaku" not in template["enum"]

    def test_flux_four_reference_requires_exactly_four_uploads(self):
        with pytest.raises(ValueError, match="exactly four"):
            build_production_workflow(
                "flux2_klein_4ref", {"prompt": "group"}, media="image",
                uploads={"reference_images": ["a.png"]},
            )
        workflow, output_node, _ = build_production_workflow(
            "flux2_klein_4ref", {"prompt": "group", "aspect_preset": "landscape_16_9"},
            media="image", uploads={"reference_images": ["a.png", "b.png", "c.png", "d.png"]},
        )
        assert output_node == "203"
        assert workflow["216"]["inputs"]["aspect_ratio"] == "16:9 (Widescreen)"
        assert workflow["194"]["inputs"]["unet_name"] == "flux2/flux-2-klein-9b-kv-fp8.safetensors"
        assert "202" not in workflow  # unconnected rgthree comparer is UI-only

    def test_infinitetalk_uploads_and_forces_extension_output(self):
        workflow, output_node, _ = build_production_workflow(
            "wan_infinitetalk_extend",
            {"prompt": "talking", "seed": 7, "num_frames": 81},
            media="video",
            uploads={"source_image": "person.png", "source_audio": "voice.mp3"},
        )
        assert output_node == "240"
        assert workflow["240"]["inputs"]["save_output"] is True
        assert sum(node["class_type"] == "WanInfiniteTalkToVideo" for node in workflow.values()) == 12
        assert workflow["32"]["inputs"]["image"] == "person.png"
        assert workflow["171"]["inputs"]["audio"] == "voice.mp3"
        assert all("rgthree" not in node["class_type"] for node in workflow.values())

    def test_qwen_voice_clone_save_mapping(self):
        workflow, output_node, provenance = build_tts_workflow(
            "qwen3_tts_voice_clone_save",
            {
                "text": "目标句", "reference_text": "参考句", "voice_name": "角色甲",
                "seed": 99, "output_path": "projects/demo/assets/audio/line.mp3",
            },
            source_audio_name="reference.wav",
        )
        assert output_node == "8"
        assert workflow["15"]["inputs"]["audio"] == "reference.wav"
        assert workflow["18"]["inputs"]["filename"] == "角色甲"
        assert workflow["8"]["inputs"]["filename_prefix"] == "audio/line"
        assert provenance["model"].startswith("Qwen3-TTS")

    def test_inpaint_mask_is_packed_as_comfyui_alpha(self, tmp_path):
        from PIL import Image

        source = tmp_path / "source.jpg"
        mask = tmp_path / "mask.png"
        Image.new("RGB", (2, 1), "red").save(source)
        mask_image = Image.new("L", (2, 1), 0)
        mask_image.putpixel((1, 0), 255)
        mask_image.save(mask)
        packed = ComfyUIImage._prepare_inpaint_upload(
            source, mask, tmp_path / "result.png", 7
        )
        with Image.open(packed) as image:
            alpha = image.getchannel("A")
            assert alpha.getpixel((0, 0)) == 255
            assert alpha.getpixel((1, 0)) == 0
