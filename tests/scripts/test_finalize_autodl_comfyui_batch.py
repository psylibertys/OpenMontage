import hashlib
import json
from pathlib import Path

import pytest

from scripts.finalize_autodl_comfyui_batch import (
    _inventory_rows,
    _retention_payload,
    _verify_local_inventory,
    remote_runtime_manifest,
)
import scripts.finalize_autodl_comfyui_batch as workflow


def test_inventory_rows_supports_batch_and_flat_schemas():
    assert _inventory_rows({"assets": [{"path": "flat"}]}) == [
        {"path": "flat"}
    ]
    assert _inventory_rows({
        "episodes": [
            {"assets": [{"path": "one"}]},
            {"assets": [{"path": "two"}]},
        ]
    }) == [{"path": "one"}, {"path": "two"}]


def test_verify_local_inventory_accepts_project_owned_asset(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setattr(workflow, "PROJECT_ROOT", tmp_path)
    asset = tmp_path / "projects" / "episode" / "assets" / "image.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"current-batch-asset")
    inventory = tmp_path / "projects" / "batch" / "artifacts" / "gpu_asset_inventory.json"
    inventory.parent.mkdir(parents=True)
    inventory.write_text(json.dumps({
        "assets": [{
            "path": str(asset),
            "size": asset.stat().st_size,
            "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
        }]
    }))

    verified = _verify_local_inventory(inventory)

    assert verified == [{
        "path": str(asset.resolve()),
        "size": asset.stat().st_size,
        "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
        "verified": True,
    }]


def test_verify_local_inventory_rejects_hash_mismatch(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setattr(workflow, "PROJECT_ROOT", tmp_path)
    asset = tmp_path / "projects" / "episode" / "assets" / "image.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"changed")
    inventory = tmp_path / "projects" / "batch" / "artifacts" / "gpu_asset_inventory.json"
    inventory.parent.mkdir(parents=True)
    inventory.write_text(json.dumps({
        "assets": [{
            "path": str(asset),
            "size": asset.stat().st_size,
            "sha256": "0" * 64,
        }]
    }))

    with pytest.raises(SystemExit, match="verification failed"):
        _verify_local_inventory(inventory)


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
