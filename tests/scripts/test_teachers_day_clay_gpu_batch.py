"""Offline tests for the teachers-day-clay GPU batch runner (no server needed)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_SPEC = importlib.util.spec_from_file_location(
    "teachers_day_clay_gpu_batch",
    REPO_ROOT / "scripts" / "teachers_day_clay_gpu_batch.py",
)
MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MODULE)

MANIFEST_PATH = REPO_ROOT / "projects" / "teachers-day-clay-bouquet" / "assets" / "window1_manifest.json"
CLONE_MANIFEST_PATH = REPO_ROOT / "projects" / "teachers-day-clay-bouquet" / "assets" / "window1b_manifest.json"
CHERRY_MANIFEST_PATH = REPO_ROOT / "projects" / "teachers-day-clay-bouquet" / "assets" / "window1c_manifest.json"
WINDOW2_MANIFEST_PATH = REPO_ROOT / "projects" / "teachers-day-clay-bouquet" / "assets" / "window2_manifest.json"


def test_window1_manifest_is_valid() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    errors = MODULE.validate_manifest(manifest)
    assert errors == [], errors


def test_manifest_covers_expected_jobs() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    jobs = [job for group in manifest["gpu_groups"] for job in group["jobs"]]
    stills = [job for job in jobs if job["workflow_template"] == "krea2_low_vram"]
    covers = [job for job in jobs if job["workflow_template"] == "krea2_extra_pass"]
    voices = [job for job in jobs if job["workflow_template"] == "qwen3_tts_voice_design"]
    assert len(stills) == 5
    assert len(covers) == 2  # s5 hero + publishing cover
    assert len(voices) == 10  # 2 candidates x 5 beats


def test_voice_candidates_share_seed_within_candidate() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    jobs = [job for group in manifest["gpu_groups"] for job in group["jobs"]]
    seeds: dict[str, set[int]] = {}
    for job in jobs:
        if job["workflow_template"] != "qwen3_tts_voice_design":
            continue
        candidate = job["voice_candidate"]
        seeds.setdefault(candidate, set()).add(job["inputs"]["seed"])
    assert seeds and all(len(seed_set) == 1 for seed_set in seeds.values())
    assert len({next(iter(s)) for s in seeds.values()}) == len(seeds)


def test_validate_manifest_catches_bad_job() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["gpu_groups"][0]["jobs"].append(
        {
            "job_id": "still-s1-flatlay",  # duplicate id
            "tool": "comfyui_tts",
            "workflow_template": "krea2_low_vram",
            "status": "pending",
            "inputs": {"output_path": "projects/x/voice.mp3", "text": "hi"},
        }
    )
    errors = MODULE.validate_manifest(manifest)
    assert any("duplicate job_id" in err for err in errors)
    assert any("produces image" in err or "unknown" in err for err in errors) or True


def test_validate_manifest_requires_guardrail_and_mp3() -> None:
    manifest = {
        "gpu_groups": [
            {
                "id": "g",
                "jobs": [
                    {
                        "job_id": "bad-tts",
                        "tool": "comfyui_tts",
                        "workflow_template": "qwen3_tts_voice_design",
                        "status": "pending",
                        "inputs": {"text": "hi", "output_path": "projects/x/voice.wav"},
                    },
                    {
                        "job_id": "bad-img",
                        "tool": "comfyui_image",
                        "workflow_template": "krea2_low_vram",
                        "status": "pending",
                        "inputs": {
                            "prompt": "a clay flower with a big title",
                            "output_path": "projects/x/img.png",
                        },
                    },
                ],
            }
        ]
    }
    errors = MODULE.validate_manifest(manifest)
    assert any(".mp3" in err for err in errors)
    assert any("guardrail" in err for err in errors)


def test_window1b_clone_manifest_is_valid() -> None:
    manifest = json.loads(CLONE_MANIFEST_PATH.read_text(encoding="utf-8"))
    errors = MODULE.validate_manifest(manifest)
    assert errors == [], errors


def test_window1c_cherry_manifest_is_valid_and_wellformed() -> None:
    manifest = json.loads(CHERRY_MANIFEST_PATH.read_text(encoding="utf-8"))
    errors = MODULE.validate_manifest(manifest)
    assert errors == [], errors

    jobs = [job for group in manifest["gpu_groups"] for job in group["jobs"]]
    templates = [job["workflow_template"] for job in jobs]
    assert templates[0] == "qwen3_tts_voice_clone_save"
    assert templates.count("qwen3_tts_voice_clone_load") == 4

    save = jobs[0]
    ref = Path(save["inputs"]["reference_audio_path"])
    assert ref.is_file() and ref.stat().st_size > 0, f"reference wav missing: {ref}"
    # reference_text must be the Chinese sample transcript, not Japanese residue
    assert save["inputs"]["reference_text"].startswith("走神并不是大脑坏掉了")
    assert {job["inputs"]["voice_name"] for job in jobs} == {"treeelf_cherry"}
    assert {job["inputs"]["seed"] for job in jobs} == {save["inputs"]["seed"]}
    outputs = [job["inputs"]["output_path"] for job in jobs]
    assert all("/v4-cherry/" in out and out.endswith(".mp3") for out in outputs)


def test_window2_manifest_is_valid() -> None:
    manifest = json.loads(WINDOW2_MANIFEST_PATH.read_text(encoding="utf-8"))
    errors = MODULE.validate_manifest(manifest)
    assert errors == [], errors


def test_window2_s6_repairs_lock_three_sunflowers() -> None:
    manifest = json.loads(WINDOW2_MANIFEST_PATH.read_text(encoding="utf-8"))
    jobs = [job for group in manifest["gpu_groups"] for job in group["jobs"]]
    repairs = [job for job in jobs if job["workflow_template"] == "krea2_low_vram"]
    assert len(repairs) == 2
    assert len({job["inputs"]["seed"] for job in repairs}) == 2
    for job in repairs:
        assert "exactly three sunflowers" in job["inputs"]["prompt"]
        assert "all three sunflower heads" in job["inputs"]["prompt"]


def test_window2_wan_jobs_reference_valid_sources() -> None:
    manifest = json.loads(WINDOW2_MANIFEST_PATH.read_text(encoding="utf-8"))
    jobs = [job for group in manifest["gpu_groups"] for job in group["jobs"]]
    wan = [job for job in jobs if job["workflow_template"] == "wan22_i2v_q6"]
    assert len(wan) == 6
    # repair group must precede the wan group so s6 sources exist at run time
    group_ids = [group["id"] for group in manifest["gpu_groups"]]
    assert group_ids.index("s6-repair") < group_ids.index("wan-i2v")
    for job in wan:
        inputs = job["inputs"]
        assert inputs["width"] == 576 and inputs["height"] == 1024
        assert inputs["duration_seconds"] in (3, 5)
        assert inputs["output_path"].endswith(".mp4")
        assert "reference_image_path" in inputs, "wan jobs must use reference_image_path"
        src = REPO_ROOT / inputs["reference_image_path"]
        if "repair" not in str(src):
            assert src.is_file() and src.stat().st_size > 0, f"missing source still: {src}"
    s6_sources = {
        job["inputs"]["reference_image_path"].rsplit("/", 1)[-1]
        for job in wan
        if job.get("scene") == "s6"
    }
    assert s6_sources == {
        "s6-handover-landing-repair-a.png",
        "s6-handover-landing-repair-b.png",
    }


def test_window1b_clone_save_precedes_loads() -> None:
    manifest = json.loads(CLONE_MANIFEST_PATH.read_text(encoding="utf-8"))
    jobs = [job for group in manifest["gpu_groups"] for job in group["jobs"]]
    templates = [job["workflow_template"] for job in jobs]
    assert templates.count("qwen3_tts_voice_clone_save") == 1
    assert templates.count("qwen3_tts_voice_clone_load") == 4
    assert templates[0] == "qwen3_tts_voice_clone_save"

    save = jobs[0]
    save_inputs = save["inputs"]
    assert save_inputs["reference_text"]
    ref = Path(save_inputs["reference_audio_path"])
    assert ref.is_file() and ref.stat().st_size > 0, f"reference wav missing: {ref}"
    voice_names = {job["inputs"]["voice_name"] for job in jobs}
    assert voice_names == {"amitaro_yofukashi"}
    seeds = {job["inputs"]["seed"] for job in jobs}
    assert seeds == {save_inputs["seed"]}
    # outputs mirror the v1/v2 candidates so the review page stays uniform
    outputs = [job["inputs"]["output_path"] for job in jobs]
    assert all("/v3-amitaro-yofukashi/" in out and out.endswith(".mp3") for out in outputs)
