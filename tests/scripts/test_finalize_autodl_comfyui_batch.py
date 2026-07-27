from pathlib import Path

import pytest

from scripts.finalize_autodl_comfyui_batch import (
    _backup_path,
    _retention_payload,
    remote_runtime_manifest,
)
import scripts.finalize_autodl_comfyui_batch as workflow


def test_backup_path_preserves_runtime_subtree(tmp_path: Path):
    result = _backup_path(
        tmp_path,
        "/root/autodl-tmp/comfyui-runtime/output/video/final.mp4",
    )
    assert result == tmp_path / "runtime" / "output" / "video" / "final.mp4"


def test_backup_path_places_explicit_extra_file_separately(tmp_path: Path):
    result = _backup_path(
        tmp_path,
        "/root/autodl-tmp/comfyui-models/qwen-tts/voices/voice.qvp",
    )
    assert result == tmp_path / "extra" / "voice.qvp"


def test_retention_payload_only_selects_declared_cleanup_roots():
    payload = _retention_payload({
        "backup_then_delete_runtime_types": ["input", "output", "temp"],
        "backup_then_delete_voice_files": [
            "/root/autodl-tmp/comfyui-models/qwen-tts/voices/test.qvp"
        ],
        "retain_project_assets": ["/runtime/input/reusable.png"],
    })
    assert payload["roots"] == [
        "/root/autodl-tmp/comfyui-runtime/input",
        "/root/autodl-tmp/comfyui-runtime/output",
        "/root/autodl-tmp/comfyui-runtime/temp",
    ]
    assert payload["extra_files"] == [
        "/root/autodl-tmp/comfyui-models/qwen-tts/voices/test.qvp"
    ]
    assert payload["retain"] == ["/runtime/input/reusable.png"]


def test_retention_payload_rejects_unknown_runtime_root():
    with pytest.raises(ValueError, match="Unsupported runtime cleanup"):
        _retention_payload({
            "backup_then_delete_runtime_types": ["../models"],
            "backup_then_delete_voice_files": [],
            "retain_project_assets": [],
        })


def test_retention_payload_rejects_arbitrary_extra_file():
    with pytest.raises(ValueError, match="Unsafe voice cleanup target"):
        _retention_payload({
            "backup_then_delete_runtime_types": [],
            "backup_then_delete_voice_files": ["/root/important.txt"],
            "retain_project_assets": [],
        })


def test_remote_runtime_manifest_captures_all_three_runtime_roots(monkeypatch):
    captured = {}

    def fake_ssh_json(host, code, payload):
        captured.update({"host": host, "code": code, "payload": payload})
        return [{"path": "/root/autodl-tmp/comfyui-runtime/output/existing.png"}]

    monkeypatch.setattr(workflow, "_ssh_json", fake_ssh_json)

    rows = remote_runtime_manifest("gpu-host")

    assert rows[0]["path"].endswith("existing.png")
    assert captured["host"] == "gpu-host"
    assert captured["payload"]["roots"] == [
        "/root/autodl-tmp/comfyui-runtime/input",
        "/root/autodl-tmp/comfyui-runtime/output",
        "/root/autodl-tmp/comfyui-runtime/temp",
    ]
