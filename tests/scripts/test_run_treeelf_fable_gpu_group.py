from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.run_treeelf_fable_gpu_group as runner


def write_manifest(path: Path, output: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "version": "1.0",
        "batch_id": "treeelf-fable-batch-test",
        "gpu_groups": [{
            "id": "narration",
            "workflow": "qwen3_tts_voice_clone_load",
            "jobs": [{
                "job_id": "episode:narration",
                "tool": "comfyui_tts",
                "workflow_template": "qwen3_tts_voice_clone_load",
                "inputs": {"text": "测试", "output_path": str(output)},
                "status": "queued",
            }],
        }],
    }), encoding="utf-8")


def test_run_group_records_success_and_resumes_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "artifacts" / "gpu_batch_manifest.json"
    output = tmp_path / "narration.mp3"
    write_manifest(manifest, output)

    class FakeTool:
        def execute(self, inputs: dict) -> SimpleNamespace:
            output.write_bytes(b"audio")
            assert inputs["workflow_template"] == "qwen3_tts_voice_clone_load"
            return SimpleNamespace(
                success=True,
                duration_seconds=1.25,
                artifacts=[str(output)],
                error=None,
                data={"output": str(output)},
                seed=7,
                model="fake",
            )

    monkeypatch.setattr(runner, "_tool", lambda _name: FakeTool())
    first = runner.run_group(manifest, "narration", workers=1)
    second = runner.run_group(manifest, "narration", workers=1)

    assert first["completed"] == 1
    assert second["completed"] == 0
    assert second["skipped_existing"] == 1
    payload = runner.load_json(manifest)
    assert payload["gpu_groups"][0]["jobs"][0]["status"] == "complete"


def test_run_group_fails_closed_and_records_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "artifacts" / "gpu_batch_manifest.json"
    output = tmp_path / "narration.mp3"
    write_manifest(manifest, output)

    class FakeTool:
        def execute(self, _inputs: dict) -> SimpleNamespace:
            return SimpleNamespace(
                success=False,
                duration_seconds=0.2,
                artifacts=[],
                error="unreachable",
                data={},
                seed=None,
                model="fake",
            )

    monkeypatch.setattr(runner, "_tool", lambda _name: FakeTool())

    with pytest.raises(RuntimeError, match="unreachable"):
        runner.run_group(manifest, "narration", workers=1)

    payload = runner.load_json(manifest)
    assert payload["gpu_groups"][0]["jobs"][0]["status"] == "failed"
    report = runner.load_json(manifest.parent / "gpu_usage_report.json")
    assert report["jobs"][-1]["error"] == "unreachable"


def test_run_group_does_not_execute_character_blocked_or_unmet_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "artifacts" / "gpu_batch_manifest.json"
    blocked_output = tmp_path / "blocked.png"
    wan_output = tmp_path / "wan.mp4"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        "batch_id": "treeelf-fable-batch-test",
        "gpu_groups": [
            {
                "id": "scene_images_flux",
                "jobs": [{
                    "job_id": "episode:scene-001",
                    "tool": "comfyui_image",
                    "workflow_template": "flux2_klein_4ref",
                    "inputs": {"output_path": str(blocked_output)},
                    "status": "blocked_character_review",
                }],
            },
            {
                "id": "wan",
                "jobs": [{
                    "job_id": "episode:wan",
                    "tool": "comfyui_video",
                    "workflow_template": "wan22_i2v_q6",
                    "depends_on": "episode:scene-001",
                    "inputs": {"output_path": str(wan_output)},
                    "status": "queued",
                }],
            },
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(runner, "_tool", lambda _name: pytest.fail("blocked job must not execute"))

    flux = runner.run_group(manifest, "scene_images_flux")
    wan = runner.run_group(manifest, "wan")

    assert flux["completed"] == 0 and flux["blocked"] == 1
    assert wan["completed"] == 0 and wan["blocked"] == 1


def test_run_gpu_batch_uses_one_continuous_stage_order_and_reports_waiting_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projects = tmp_path / "projects"
    batch_dir = projects / "treeelf-fable-batch-test"
    manifest_path = batch_dir / "artifacts" / "gpu_batch_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    groups = [
        {"id": "narration", "jobs": []},
        {"id": "character_pack", "jobs": []},
        {"id": "scene_images_krea", "jobs": []},
        {
            "id": "scene_images_flux",
            "jobs": [{
                "job_id": "episode:scene-001",
                "project_id": "episode",
                "status": "blocked_character_review",
                "inputs": {"output_path": str(tmp_path / "scene.png")},
            }],
        },
        {"id": "covers", "jobs": []},
        {"id": "wan", "jobs": []},
    ]
    manifest_path.write_text(json.dumps({
        "batch_id": "treeelf-fable-batch-test",
        "status": "baseline_captured",
        "gpu_groups": groups,
    }), encoding="utf-8")
    batch_config = tmp_path / "batch.json"
    batch_config.write_text(json.dumps({"batch_id": "treeelf-fable-batch-test"}), encoding="utf-8")
    series = tmp_path / "series.json"
    series.write_text("{}", encoding="utf-8")
    called: list[str] = []

    def fake_group(_manifest: Path, group_id: str, *, workers: int = 2) -> dict:
        called.append(group_id)
        return {"group_id": group_id, "completed": 0, "blocked": int(group_id == "scene_images_flux")}

    monkeypatch.setattr(runner, "run_group", fake_group)
    monkeypatch.setattr(runner.fable, "refresh_visuals", lambda *_args, **_kwargs: {"blocked_flux_jobs": 1})
    monkeypatch.setattr(
        runner,
        "_live_preflight",
        lambda _manifest: {"workflow_preflight": {"passed": 15, "total": 15}},
    )

    result = runner.run_gpu_batch(manifest_path, batch_config, series)

    assert called == ["narration", "character_pack", "scene_images_krea", "covers", "scene_images_flux", "repairs", "wan"]
    assert result["status"] == "waiting_character_review"
    assert result["waiting_character_projects"] == ["episode"]


def test_repair_group_allows_only_one_explicit_attempt_per_asset(tmp_path: Path) -> None:
    manifest = tmp_path / "artifacts" / "gpu_batch_manifest.json"
    manifest.parent.mkdir(parents=True)
    jobs = [
        {
            "job_id": f"repair-{index}",
            "repair_of": "episode:scene-001",
            "repair_attempt": 1,
            "tool": "comfyui_image",
            "workflow_template": "krea2_low_vram",
            "inputs": {"output_path": str(tmp_path / f"repair-{index}.png")},
            "status": "queued",
        }
        for index in range(2)
    ]
    manifest.write_text(json.dumps({
        "batch_id": "treeelf-fable-batch-test",
        "gpu_groups": [{"id": "repairs", "jobs": jobs}],
    }), encoding="utf-8")

    with pytest.raises(ValueError, match="only one online repair attempt"):
        runner.run_group(manifest, "repairs")


def test_live_preflight_requires_repeated_health_empty_queue_and_15_workflows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return b'{"system": {"os": "linux"}}'

    manifest = tmp_path / "artifacts" / "gpu_batch_manifest.json"
    manifest.parent.mkdir(parents=True)
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(
        runner,
        "_queue_snapshot",
        lambda: {"checked_at": runner.utc_now(), "reachable": True, "running": 0, "pending": 0, "depth": 0},
    )
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)
    workflows = {f"workflow-{index}": {"ok": True} for index in range(15)}
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(workflows), stderr=""),
    )

    report = runner._live_preflight(manifest)

    assert len(report["health_checks"]) == 2
    assert report["queue"]["depth"] == 0
    assert report["workflow_preflight"] == {"passed": 15, "total": 15}
    assert (manifest.parent / "gpu_live_preflight.json").is_file()
