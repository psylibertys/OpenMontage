#!/usr/bin/env python3
"""Validate every AutoDL production template against a live ComfyUI server."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools._comfyui.first_batch import FIRST_BATCH_WORKFLOWS, build_workflow as build_first
from tools._comfyui.production import PRODUCTION_WORKFLOWS, build_workflow as build_production
from tools._comfyui.tts import TTS_WORKFLOWS, build_workflow as build_tts


UPLOAD_FIELDS = {"image", "audio", "video"}
CPU_DEFERRED_NODE_TYPES = {"SeedVR2LoadDiTModel", "SeedVR2LoadVAEModel"}


def _allowed_values(field_spec: Any) -> list[Any] | None:
    if not isinstance(field_spec, list) or not field_spec:
        return None
    first = field_spec[0]
    if isinstance(first, list) and first:
        return first
    if first == "COMBO" and len(field_spec) > 1 and isinstance(field_spec[1], dict):
        options = field_spec[1].get("options")
        return options if isinstance(options, list) and options else None
    return None


def _graphs() -> dict[str, tuple[dict[str, Any], str]]:
    result: dict[str, tuple[dict[str, Any], str]] = {}
    for name, spec in FIRST_BATCH_WORKFLOWS.items():
        uploads = "source.png" if spec.get("source_image") else None
        inputs = {"prompt": "preflight", "seed": 1, "output_path": "preflight.bin"}
        graph, output, _ = build_first(name, inputs, media=spec["media"], source_image_name=uploads)
        result[name] = (graph, output)
    for name, spec in PRODUCTION_WORKFLOWS.items():
        uploads: dict[str, Any] = {}
        if spec.get("source_image"):
            uploads["source_image"] = "source.png"
        if spec.get("source_audio"):
            uploads["source_audio"] = "source.mp3"
        if spec.get("source_video"):
            uploads["source_video"] = "source.mp4"
        if spec.get("reference_images"):
            uploads["reference_images"] = [f"ref-{i}.png" for i in range(4)]
        graph, output, _ = build_production(
            name, {"prompt": "preflight", "seed": 1, "output_path": "preflight.bin"},
            media=spec["media"], uploads=uploads,
        )
        result[name] = (graph, output)
    for name, spec in TTS_WORKFLOWS.items():
        inputs = {
            "text": "预检", "reference_text": "参考", "voice_name": "preflight",
            "seed": 1, "output_path": "preflight.mp3",
        }
        graph, output, _ = build_tts(
            name, inputs, source_audio_name="reference.wav" if spec.get("source_audio") else None
        )
        result[name] = (graph, output)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server", default=os.environ.get("COMFYUI_SERVER_URL", "http://127.0.0.1:18188")
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    with urllib.request.urlopen(args.server.rstrip("/") + "/object_info", timeout=30) as response:
        object_info = json.load(response)

    report: dict[str, Any] = {}
    failed = False
    for name, (graph, output_node) in _graphs().items():
        missing_nodes = sorted({node["class_type"] for node in graph.values()} - set(object_info))
        deferred_nodes = sorted(set(missing_nodes) & CPU_DEFERRED_NODE_TYPES)
        missing_nodes = sorted(set(missing_nodes) - CPU_DEFERRED_NODE_TYPES)
        missing_choices: list[dict[str, str]] = []
        for node_id, node in graph.items():
            schema = object_info.get(node["class_type"], {}).get("input", {})
            fields = {**schema.get("required", {}), **schema.get("optional", {})}
            for field, value in node.get("inputs", {}).items():
                if field in UPLOAD_FIELDS:
                    continue
                if node["class_type"] == "FB_Qwen3TTSLoadSpeaker" and field == "filename":
                    continue
                choices = _allowed_values(fields.get(field))
                if choices is not None and isinstance(value, str) and value not in choices:
                    missing_choices.append({
                        "node": node_id, "class_type": node["class_type"],
                        "field": field, "value": value,
                    })
        ok = not missing_nodes and not missing_choices and output_node in graph
        failed |= not ok
        report[name] = {
            "ok": ok, "nodes": len(graph), "output_node": output_node,
            "missing_node_types": missing_nodes, "deferred_gpu_node_types": deferred_nodes,
            "unavailable_model_choices": missing_choices,
        }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for name, item in report.items():
            state = "OK" if item["ok"] else "WAIT"
            print(
                f"{state:4} {name:32} nodes={item['nodes']:3} "
                f"missing_nodes={len(item['missing_node_types'])} "
                f"missing_models={len(item['unavailable_model_choices'])} "
                f"gpu_deferred={len(item['deferred_gpu_node_types'])}"
            )
            for model in item["unavailable_model_choices"]:
                print(f"     {model['class_type']}.{model['field']}: {model['value']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
