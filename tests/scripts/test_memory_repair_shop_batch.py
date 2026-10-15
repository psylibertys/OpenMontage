from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

import scripts.memory_repair_shop_batch as batch

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_CONFIG = REPO_ROOT / "workflow_configs" / "memory-repair-shop" / "batch-3.json"
REAL_CONFIG_B4 = REPO_ROOT / "workflow_configs" / "memory-repair-shop" / "batch-4.json"
STORYBOARD_EXPORT = REPO_ROOT / "projects/memory-repair-shop/exports/storyboard/memory-repair-shop/memory-repair-shop.json"

REUSED_KEYFRAMES = [
    "scene-1", "scene-2", "scene-6", "scene-9", "scene-10",
    "scene-15", "scene-20", "scene-22", "scene-23",
]


@pytest.fixture()
def project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect PROJECTS_ROOT so prepare never touches the real project."""
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(batch, "PROJECTS_ROOT", root)
    scenes_root = root / "memory-repair-shop" / "assets" / "images" / "scenes"
    scenes_root.mkdir(parents=True)
    for key in REUSED_KEYFRAMES:
        index = int(key.rsplit("-", 1)[-1])
        placeholder = scenes_root / f"scene-{index:02d}.png"
        placeholder.write_bytes(b"v1-keyframe-placeholder")
    return root


def load_manifest(root: Path, batch_id: str = "memory-repair-shop-b3") -> dict:
    return json.loads((root / "memory-repair-shop" / "artifacts" / f"gpu_batch_manifest_{batch_id}.json").read_text(encoding="utf-8"))


def test_prepare_builds_dialogue_driven_manifest(project_root: Path) -> None:
    result = batch.prepare(REAL_CONFIG)
    assert result["jobs"] == {
        "dialogue_tts": 5,
        "character_pack": 2,
        "scene_images_krea": 9,
        "scene_images_flux": 7,
    }
    assert set(result["keyframes_reused"]) == set(REUSED_KEYFRAMES)

    manifest = load_manifest(project_root)
    assert manifest["status"] == "prepared"
    groups = {group["id"]: group for group in manifest["gpu_groups"]}
    assert set(groups) == {"dialogue_tts", "character_pack", "scene_images_krea", "scene_images_flux"}

    export = json.loads(STORYBOARD_EXPORT.read_text(encoding="utf-8"))
    # First line per character uses VoiceDesign; the old man's second line
    # clones his first take so one character keeps one voice.
    dialogue_jobs = {job["job_id"]: job for job in groups["dialogue_tts"]["jobs"]}
    assert set(dialogue_jobs) == {
        "dialogue:scene-09", "dialogue:scene-14",
        "dialogue:scene-17", "dialogue:scene-20", "dialogue:scene-21",
    }
    s9 = dialogue_jobs["dialogue:scene-09"]
    assert s9["workflow_template"] == "qwen3_tts_voice_design"
    assert s9["inputs"]["text"] == "我想忘掉我的妻子。"
    assert "六十多岁中国老人" in s9["inputs"]["instruct"]
    assert "低哑" in s9["inputs"]["instruct"]
    assert s9["inputs"]["output_path"].endswith("audio/dialogue/scene-09.mp3")
    s21 = dialogue_jobs["dialogue:scene-21"]
    assert s21["workflow_template"] == "qwen3_tts_voice_clone_save"
    assert s21["depends_on"] == "dialogue:scene-09"
    assert s21["inputs"]["reference_audio_path"].endswith("scene-09.mp3")
    assert s21["inputs"]["reference_text"] == "我想忘掉我的妻子。"
    assert s21["inputs"]["voice_name"] == "old_man_v2"

    # Chinese-cast prompt rework: regenerating shots only, reused stills skipped.
    keyframe_keys = {job["scene_key"] for group in ("scene_images_krea", "scene_images_flux") for job in groups[group]["jobs"]}
    assert keyframe_keys == {str(scene["scene_plan_scene_id"]) for scene in export["scenes"]} - set(REUSED_KEYFRAMES)
    flux_keys = {job["scene_key"] for job in groups["scene_images_flux"]["jobs"]}
    assert flux_keys == {"scene-4", "scene-7", "scene-8", "scene-16", "scene-17", "scene-18", "scene-21"}
    assert all(job["status"] == "blocked_character_review" for job in groups["scene_images_flux"]["jobs"])
    assert all("East Asian" in job["inputs"]["prompt"] or "Chinese" in job["inputs"]["prompt"]
               for job in groups["character_pack"]["jobs"])


def test_prepare_rejects_lip_sync_without_dialogue_mode(project_root: Path) -> None:
    export = json.loads(STORYBOARD_EXPORT.read_text(encoding="utf-8"))
    export["scenes"][8]["dialogue"]["mode"] = "mumbled"
    broken = project_root.parent / "broken-export.json"
    broken.write_text(json.dumps(export, ensure_ascii=False), encoding="utf-8")
    config = json.loads(REAL_CONFIG.read_text(encoding="utf-8"))
    config["storyboard_export"] = str(broken)
    config_path = project_root.parent / "broken-batch.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit, match="dialogue.mode"):
        batch.prepare(config_path)


def test_prepare_rejects_routing_without_pack_binding(project_root: Path, tmp_path: Path) -> None:
    config = json.loads(REAL_CONFIG.read_text(encoding="utf-8"))
    config["scene_routing"]["scene-1"] = "flux2_klein_4ref"
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit, match="no character pack binding"):
        batch.prepare(broken)


def test_prompt_adaptation_must_match_storyboard(project_root: Path, tmp_path: Path) -> None:
    config = json.loads(REAL_CONFIG.read_text(encoding="utf-8"))
    config["prompt_adaptations"]["scene-3"] = {"from": "not in the prompt", "to": "anything"}
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="no longer matches"):
        batch.prepare(broken)


def test_character_gate_blocks_until_review_approved(project_root: Path) -> None:
    batch.prepare(REAL_CONFIG)
    manifest_path = project_root / "memory-repair-shop" / "artifacts" / "gpu_batch_manifest_memory-repair-shop-b3.json"
    manifest = load_manifest(project_root)
    for job in manifest["gpu_groups"][1]["jobs"]:
        job["status"] = "complete"
    batch.dump_json(manifest_path, manifest)

    config = batch.load_json(REAL_CONFIG)
    waiting = batch.refresh_character_gates(config)
    assert waiting == ["lin_wan", "old_man"]

    lin_wan_root = project_root / "memory-repair-shop" / "assets" / "images" / "character" / "lin_wan"
    lin_wan_root.mkdir(parents=True)
    (lin_wan_root / "character_review.json").write_text(
        json.dumps({"approved": True, "checks": {key: True for key in batch.CHARACTER_CHECK_KEYS}}),
        encoding="utf-8",
    )
    waiting = batch.refresh_character_gates(config)
    assert waiting == ["old_man"]
    manifest = load_manifest(project_root)
    flux = manifest["gpu_groups"][3]["jobs"]
    assert all(job["status"] == "queued" for job in flux if job["character_id"] == "lin_wan")
    assert all(job["status"] == "blocked_character_review" for job in flux if job["character_id"] == "old_man")


def test_cut_refs_and_approve_release_gate(project_root: Path) -> None:
    batch.prepare(REAL_CONFIG)
    config = json.loads(REAL_CONFIG.read_text(encoding="utf-8"))
    for pack in config["character_packs"]:
        pack_root = project_root / "memory-repair-shop" / "assets" / "images" / "character" / pack["character_id"]
        pack_root.mkdir(parents=True)
        sheet = Image.new("RGB", (1024, 1820), (60, 50, 40))
        sheet.save(pack_root / "turnaround-sheet.png")

    result = batch.cut_refs(REAL_CONFIG)
    assert set(result) == {"lin_wan", "old_man"}
    for pack in config["character_packs"]:
        pack_root = project_root / "memory-repair-shop" / "assets" / "images" / "character" / pack["character_id"]
        refs = sorted(pack_root.glob("ref-*.png"))
        assert len(refs) == 4
        assert all(path.stat().st_size > 0 for path in refs)

    approved = batch.approve_review(REAL_CONFIG, "lin_wan", reviewer="user", notes="中国面孔一致")
    assert approved["approved"] is True
    again = batch.approve_review(REAL_CONFIG, "lin_wan", reviewer="user", notes="")
    assert again["already_approved"] is True


def test_verify_gpu_assets_reports_missing_outputs(project_root: Path) -> None:
    batch.prepare(REAL_CONFIG)
    result = batch.verify_gpu_assets(REAL_CONFIG)
    assert result["checked"] == 23
    assert result["problems"], "empty project must report missing outputs"
    report_path = project_root / "memory-repair-shop" / "artifacts" / "gpu_asset_verification.json"
    assert report_path.is_file()


def _place_dialogue_audio(root: Path) -> None:
    audio_root = root / "memory-repair-shop" / "assets" / "audio" / "dialogue"
    audio_root.mkdir(parents=True, exist_ok=True)
    for index in (14, 17, 21):
        (audio_root / f"scene-{index:02d}.mp3").write_bytes(b"dialogue-take")


def test_prepare_video_batch_two_stage_and_lip_sync(project_root: Path) -> None:
    _place_dialogue_audio(project_root)
    result = batch.prepare(REAL_CONFIG_B4)
    assert result["jobs"] == {"video_seed": 22, "video_hd": 22, "dialogue_video": 3, "enhancements": 1}

    manifest = load_manifest(project_root, "memory-repair-shop-b4")
    assert manifest["batch_kind"] == "video"
    groups = {group["id"]: group for group in manifest["gpu_groups"]}
    seed_by_key = {job["scene_key"]: job for job in groups["video_seed"]["jobs"]}
    hd_by_key = {job["scene_key"]: job for job in groups["video_hd"]["jobs"]}
    assert set(seed_by_key) == set(hd_by_key)
    assert not {"scene-14", "scene-17", "scene-21"} & set(seed_by_key), "lip-sync shots leave the two-stage pool"
    for key, seed_job in seed_by_key.items():
        assert seed_job["inputs"]["longest_side"] == 480
        hd_job = hd_by_key[key]
        assert hd_job["status"] == "blocked_seed_review"
        assert hd_job["depends_on"] == seed_job["job_id"]
        assert hd_job["inputs"]["seed"] == seed_job["inputs"]["seed"]
        # Design duration is >=4s everywhere (H3 minimum) and drives generation.
        assert seed_job["inputs"]["duration_seconds"] >= 4
        assert hd_job["inputs"]["duration_seconds"] == seed_job["inputs"]["duration_seconds"]
    assert seed_by_key["scene-1"]["inputs"]["duration_seconds"] == 5.0
    assert hd_by_key["scene-25"]["inputs"]["duration_seconds"] == 6.0
    assert seed_by_key["scene-1"]["inputs"]["prompt"].startswith(
        "For the target video, at 0.00 seconds into the target video"
    ), "i2v prompts must follow the H3 formula alignment line"
    assert "remain consistent" not in seed_by_key["scene-1"]["inputs"]["prompt"]

    lip = {job["scene_key"]: job for job in groups["dialogue_video"]["jobs"]}
    assert set(lip) == {"scene-14", "scene-17", "scene-21"}
    assert all(job["workflow_template"] == "minimax_h3_audio_sync" for job in lip.values())
    assert lip["scene-14"]["inputs"]["reference_audio_path"].endswith("dialogue/scene-14.mp3")
    assert lip["scene-14"]["inputs"]["duration_seconds"] == 5.0  # 4s design + 1s margin
    assert lip["scene-17"]["inputs"]["duration_seconds"] == 6.0  # 5s design + 1s margin
    assert all(job["inputs"]["longest_side"] == 1920 for job in lip.values())

    enh = {job["job_id"]: job for job in groups["enhancements"]["jobs"]}
    assert set(enh) == {"enh:fflf-21-22"}
    assert enh["enh:fflf-21-22"]["inputs"]["reference_image_path"].endswith("scene-21.png")
    assert enh["enh:fflf-21-22"]["inputs"]["last_image_path"].endswith("scene-22.png")


def test_prepare_video_requires_batch3_dialogue_audio(project_root: Path) -> None:
    with pytest.raises(SystemExit, match="missing dialogue audio"):
        batch.prepare(REAL_CONFIG_B4)


def test_star_releases_only_selected_hd_jobs(project_root: Path) -> None:
    _place_dialogue_audio(project_root)
    batch.prepare(REAL_CONFIG_B4)
    manifest_path = project_root / "memory-repair-shop" / "artifacts" / "gpu_batch_manifest_memory-repair-shop-b4.json"
    manifest = load_manifest(project_root, "memory-repair-shop-b4")
    for job in manifest["gpu_groups"][0]["jobs"]:
        job["status"] = "complete"
    batch.dump_json(manifest_path, manifest)

    config = batch.load_json(REAL_CONFIG_B4)
    waiting = batch.refresh_seed_gates(config)
    assert len(waiting) == 22

    batch.star_scenes(REAL_CONFIG_B4, ["scene-1", "scene-2"])
    manifest = load_manifest(project_root, "memory-repair-shop-b4")
    hd = {job["scene_key"]: job for job in manifest["gpu_groups"][1]["jobs"]}
    assert hd["scene-1"]["status"] == "queued"
    assert hd["scene-2"]["status"] == "queued"
    assert hd["scene-3"]["status"] == "blocked_seed_review"
