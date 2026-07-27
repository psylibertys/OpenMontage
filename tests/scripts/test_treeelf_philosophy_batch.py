from __future__ import annotations

import json
from pathlib import Path

import scripts.treeelf_philosophy_batch as batch_workflow
import scripts.treeelf_philosophy_episode as episode_workflow


def _write_source(path: Path, asset_id: str) -> None:
    path.write_text(
        "---\n"
        "type: 短视频文案\n"
        f"asset_id: {asset_id}\n"
        "status: ready\n"
        "review_status: passed\n"
        "---\n\n"
        f"# {asset_id}\n\n第一段。\n\n第二段。\n",
        encoding="utf-8",
    )


def _make_batch(tmp_path: Path) -> tuple[Path, dict, dict]:
    series = json.loads(episode_workflow.DEFAULT_SERIES_CONFIG.read_text(encoding="utf-8"))
    template = json.loads(episode_workflow.DEFAULT_EPISODE_CONFIG.read_text(encoding="utf-8"))
    config_names = []
    for index in (1, 2):
        source = tmp_path / f"source-{index}.md"
        _write_source(source, f"asset-{index}")
        config = json.loads(json.dumps(template))
        config["project_id"] = f"treeelf-test-{index}"
        config["source_script_md"] = str(source)
        config_path = tmp_path / f"episode-{index}.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        config_names.append(config_path.name)
    batch = {
        "version": "1.0",
        "batch_id": "treeelf-batch-test",
        "queue_depth": 2,
        "episode_configs": config_names,
    }
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(json.dumps(batch), encoding="utf-8")
    return batch_path, batch, series


def test_batch_validation_and_gpu_plan_use_fifteen_images_two_wan(tmp_path: Path) -> None:
    batch_path, batch, series = _make_batch(tmp_path)

    assert batch_workflow.validate_batch(batch, batch_path, series) == []
    plan = batch_workflow.gpu_plan(batch, batch_path, series)

    assert plan["totals"] == {"narration_segments": 4, "images": 30, "wan_clips": 4}
    assert plan["queue_depth"] == 2
    assert plan["estimated_effective_gpu_seconds"] == 1062.56


def test_prepare_batch_creates_reservation_and_retention_gate(tmp_path: Path) -> None:
    batch_path, batch, series = _make_batch(tmp_path)
    projects = tmp_path / "projects"

    result = batch_workflow.prepare_batch(
        batch,
        batch_path,
        series,
        projects_dir=projects,
    )

    manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    policy = json.loads(Path(result["retention_policy"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "prepared"
    assert [item["status"] for item in manifest["episodes"]] == ["prepared", "prepared"]
    assert manifest["model_group_order"] == [
        "qwen3_tts_voice_clone_load",
        "krea2_low_vram",
        "wan22_i2v_q6",
    ]
    assert policy["backup_then_delete_runtime_types"] == ["input", "output", "temp"]
    assert policy["backup_then_delete_voice_files"] == []
    assert all(Path(item["source_path"]).is_file() for item in manifest["episodes"])


def test_finalize_refuses_batch_without_verified_inventory(tmp_path: Path) -> None:
    batch_path, batch, series = _make_batch(tmp_path)
    projects = tmp_path / "projects"
    batch_workflow.prepare_batch(batch, batch_path, series, projects_dir=projects)

    try:
        batch_workflow.finalize_command(
            batch,
            projects_dir=projects,
            dry_run=True,
            yes=False,
            shutdown=False,
        )
    except FileNotFoundError as exc:
        assert "inventory is incomplete" in str(exc)
    else:
        raise AssertionError("finalize must require a verified GPU asset inventory")


def test_generate_gpu_batch_groups_models_and_freezes_remote_baseline(
    tmp_path: Path,
    monkeypatch,
) -> None:
    batch_path, batch, series = _make_batch(tmp_path)
    projects = tmp_path / "projects"
    batch_workflow.prepare_batch(batch, batch_path, series, projects_dir=projects)
    calls: list[str] = []
    baseline_path = "/root/autodl-tmp/comfyui-runtime/output/existing.png"
    monkeypatch.setattr(batch_workflow, "ensure_gpu_preflight", lambda _path: None)
    monkeypatch.setattr(
        batch_workflow,
        "remote_runtime_manifest",
        lambda host: [{"path": baseline_path, "size": 1, "sha256": "old"}],
    )

    def fake_narration(config, _series, *, projects_dir, run_preflight):
        calls.append("narration")
        path = projects_dir / config["project_id"] / "assets" / "audio" / "narration.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"narration")
        return {"path": str(path)}

    def fake_visuals(
        config,
        *,
        projects_dir,
        include_images,
        include_videos,
        run_preflight,
    ):
        stage = "images" if include_images else "wan"
        calls.append(stage)
        target = projects_dir / config["project_id"] / "assets"
        if include_images:
            image_dir = target / "images" / "article"
            image_dir.mkdir(parents=True, exist_ok=True)
            for item in config["article_visual_assets"]["images"]:
                (image_dir / f"{item['id']}.png").write_bytes(item["id"].encode())
        if include_videos:
            video_dir = target / "video" / "article"
            video_dir.mkdir(parents=True, exist_ok=True)
            for item in config["article_visual_assets"]["videos"]:
                (video_dir / f"{item['id']}.mp4").write_bytes(item["id"].encode())
        return {"stage": stage}

    monkeypatch.setattr(batch_workflow, "generate_narration", fake_narration)
    monkeypatch.setattr(batch_workflow, "generate_article_visual_assets", fake_visuals)
    monkeypatch.setattr(batch_workflow, "build_exact_captions", lambda config, *, projects_dir: {"path": str(projects_dir / config["project_id"] / "artifacts" / "exact_captions.json")})

    result = batch_workflow.generate_gpu_batch(
        batch,
        batch_path,
        series,
        projects_dir=projects,
        ssh_host="gpu-host",
    )

    assert calls == ["narration", "narration", "images", "images", "wan", "wan"]
    assert "captions" in result["stages"]
    assert result["status"] == "local_pending"
    policy = json.loads(
        (projects / batch["batch_id"] / "artifacts" / "retention_policy.json").read_text(
            encoding="utf-8"
        )
    )
    assert policy["retain_project_assets"] == [baseline_path]
    assert policy["runtime_baseline_file_count"] == 1


def test_batch_backup_cleanup_requires_delivery_and_supports_dry_run(tmp_path: Path) -> None:
    batch_path, batch, series = _make_batch(tmp_path)
    projects = tmp_path / "projects"
    batch_workflow.prepare_batch(batch, batch_path, series, projects_dir=projects)
    batch_dir = projects / batch["batch_id"]
    manifest_path = batch_dir / "artifacts" / "batch_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "delivered"
    for episode in manifest["episodes"]:
        episode["status"] = "delivered"
        output = tmp_path / "Movies" / f"{episode['project_id']}.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"final")
        report = projects / episode["project_id"] / "artifacts" / "delivery_report.json"
        report.write_text(json.dumps({"output": str(output)}), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    backup = batch_dir / "assets" / "remote-final-backup" / "20260725T000000Z"
    backup.mkdir(parents=True)
    (backup / "remote.png").write_bytes(b"duplicate")

    preview = batch_workflow.cleanup_batch_local_storage(
        batch,
        series,
        projects_dir=projects,
        dry_run=True,
        retention_days=0,
    )

    assert preview["targets"][0]["path"] == str(backup)
    assert backup.is_dir()
    applied = batch_workflow.cleanup_batch_local_storage(
        batch,
        series,
        projects_dir=projects,
        dry_run=False,
        yes=True,
        retention_days=0,
    )
    assert applied["deleted"]
    assert not backup.exists()
