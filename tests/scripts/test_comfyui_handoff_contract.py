import json
from pathlib import Path

from tools._comfyui.first_batch import FIRST_BATCH_WORKFLOWS
from tools._comfyui.production import PRODUCTION_WORKFLOWS
from tools._comfyui.tts import TTS_WORKFLOWS


ROOT = Path(__file__).resolve().parents[2]


def test_new_agent_entrypoint_routes_to_complete_comfyui_context():
    guide = (ROOT / "AGENT_GUIDE.md").read_text(encoding="utf-8")
    context = (
        ROOT / "production-planning" / "COMFYUI_AGENT_CONTEXT.md"
    ).read_text(encoding="utf-8")
    assert "production-planning/COMFYUI_AGENT_CONTEXT.md" in guide
    assert "新对话执行速查" in context
    assert "start-autodl-comfyui-session.sh" in context
    assert "finalize_autodl_comfyui_batch.py" in context
    assert "duration_seconds" in context


def test_all_registered_templates_have_api_graphs_outputs_and_documentation():
    context = (
        ROOT / "production-planning" / "COMFYUI_AGENT_CONTEXT.md"
    ).read_text(encoding="utf-8")
    registries = [
        (FIRST_BATCH_WORKFLOWS, ROOT / "tools" / "_comfyui" / "workflows" / "first_batch"),
        (PRODUCTION_WORKFLOWS, ROOT / "tools" / "_comfyui" / "workflows" / "production"),
        (TTS_WORKFLOWS, ROOT / "tools" / "_comfyui" / "workflows" / "production"),
    ]
    count = 0
    for registry, directory in registries:
        for name, spec in registry.items():
            graph = json.loads((directory / spec["file"]).read_text(encoding="utf-8"))
            assert graph
            assert all("class_type" in node and "inputs" in node for node in graph.values())
            assert str(spec["output_node"]) in graph
            assert f"`{name}`" in context
            count += 1
    assert count == 15


def test_startup_and_preflight_share_private_tunnel_port():
    startup = (
        ROOT / "production-planning" / "scripts" / "start-autodl-comfyui-session.sh"
    ).read_text(encoding="utf-8")
    preflight = (ROOT / "scripts" / "comfyui_workflow_preflight.py").read_text(
        encoding="utf-8"
    )
    assert 'COMFYUI_LOCAL_PORT:-18188' in startup
    assert "nvidia-smi -L" in startup
    assert "http://127.0.0.1:18188" in preflight
