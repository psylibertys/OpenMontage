from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

import scripts.treeelf_fable_batch as workflow


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def make_fixture(tmp_path: Path) -> tuple[Path, dict, dict, Path, Path]:
    source = tmp_path / "fable.md"
    source.write_text("# 寓言\n\n第一段。\n\n第二段。\n", encoding="utf-8")
    episode = {
        "version": "1.0",
        "project_id": "treeelf-fable-test-20260725",
        "title": "测试寓言",
        "cover_title": "测试",
        "source_script_md": str(source),
        "estimated_duration_seconds": 20,
        "protagonist": {"type": "物品", "description": "一只茶杯"},
        "semantic_beats": [
            {
                "id": "beat-01",
                "weight": 1,
                "workflow": "krea2_low_vram",
                "story_event": "一只茶杯在桌面上轻轻转向光源。",
                "fable_law": "被忽略的物品会在安静处自己寻找被看见的位置。",
                "art_style_logic": "克制的现代寓言绘本质感让茶杯的微小动作显得像真实事件。",
                "prompt_variants": ["vertical storybook tea cup, no text, no letters, no logo"],
            },
            {
                "id": "beat-02",
                "weight": 1,
                "workflow": "krea2_low_vram",
                "story_event": "桌面空下来，只留下茶杯移动过的浅浅圆痕。",
                "fable_law": "物品离开后，位置仍然保留它想被看见的痕迹。",
                "art_style_logic": "安静留白和纸面纹理适合表现寓言结尾的余韵。",
                "prompt_variants": ["vertical storybook empty table, no text, no letters, no logo"],
            },
        ],
        "character_reference_paths": [],
        "cover_prompt": "vertical storybook cover, no text, no letters, no logo",
        "hero_wan": {"enabled": True, "scene_id": "scene-002", "prompt": "the cup turns gently"},
        "music_source": "",
        "captions_path": "",
    }
    episode_path = tmp_path / "episode.json"
    write_json(episode_path, episode)
    batch = {
        "version": "1.0",
        "batch_id": "treeelf-fable-batch-test",
        "queue_depth": 2,
        "episode_configs": [episode_path.name],
    }
    batch_path = tmp_path / "batch.json"
    write_json(batch_path, batch)
    series = workflow.load_json(workflow.DEFAULT_SERIES)
    ledger_path = tmp_path / "ledger.json"
    write_json(
        ledger_path,
        {
            "version": "1.0",
            "series": "treeelf-fable",
            "items": [{"source": source.name, "status": "pending"}],
        },
    )
    return batch_path, batch, series, ledger_path, episode_path


def relaxed_series(series: dict) -> dict:
    series = json.loads(json.dumps(series))
    series["quality_gates"] = {
        "strict_aesthetic_prompt_review": False,
        "require_character_review": False,
        "require_visual_qc_for_stage": False,
        "require_calibrated_captions_for_stage": False,
        "require_audio_loudness_qc": False,
    }
    return series


def test_five_second_density_for_previous_episode_duration() -> None:
    assert workflow.target_image_count(167.304, 10, 5) == 34
    beats = [
        {"id": f"b{index}", "weight": 1, "prompt_variants": [f"prompt {index}"]}
        for index in range(10)
    ]
    slots = workflow.build_visual_slots(167.304, beats, target_seconds=5)
    assert len(slots) == 34
    assert max(slot["duration"] for slot in slots) < 5.6
    assert slots[0]["from"] == 0
    assert slots[-1]["to"] == 167.304


def test_adult_male_protagonist_is_rejected(tmp_path: Path) -> None:
    batch_path, batch, series, _, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    episode["protagonist"]["type"] = "成年男性"
    write_json(episode_path, episode)
    errors = workflow.validate_batch(batch, batch_path, series)
    assert any("protagonist" in error for error in errors)


def test_cover_prompt_with_human_terms_is_rejected(tmp_path: Path) -> None:
    batch_path, batch, series, _, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    episode["cover_prompt"] = "vertical cover, young woman beside a symbolic table, text-free"
    write_json(episode_path, episode)

    errors = workflow.validate_batch(batch, batch_path, series)

    assert any("cover_prompt must be human-free" in error for error in errors)


def test_semantic_beat_requires_fable_visual_fields(tmp_path: Path) -> None:
    batch_path, batch, series, _, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    episode["semantic_beats"][0].pop("fable_law")
    write_json(episode_path, episode)

    errors = workflow.validate_batch(batch, batch_path, series)

    assert any("missing fable visual field:fable_law" in error for error in errors)


def test_prepare_is_independent_and_reserves_ledger(tmp_path: Path) -> None:
    batch_path, batch, series, ledger_path, episode_path = make_fixture(tmp_path)
    projects = tmp_path / "projects"
    result = workflow.prepare_batch(
        batch,
        batch_path,
        series,
        projects_root=projects,
        ledger_path=ledger_path,
    )
    manifest = workflow.load_json(Path(result["manifest"]))
    policy = workflow.load_json(projects / batch["batch_id"] / "artifacts" / "retention_policy.json")
    ledger = workflow.load_json(ledger_path)
    assert manifest["workflow"] == "treeelf_fable_independent_batch"
    assert manifest["status"] == "gpu_queued"
    assert "zh-philosophy-video" not in json.dumps(manifest)
    assert policy["decision"] == "current_fable_batch_only"
    assert policy["concurrency_rule"].startswith("no other project")
    assert ledger["items"][0]["status"] == "gpu_queued"
    episode = workflow.load_json(episode_path)
    episode_root = projects / episode["project_id"]
    assert (episode_root / "artifacts" / "visual_brief.json").is_file()
    assert (episode_root / "artifacts" / "prompt_review_warnings.json").is_file()
    readiness = workflow.load_json(projects / batch["batch_id"] / "artifacts" / "batch_readiness_report.json")
    assert readiness["ready_for_prepare"] is True
    assert readiness["totals"]["episodes"] == 1
    assert readiness["episodes"][0]["fable_visual_fields_complete"] is True
    assert readiness["episodes"][0]["estimated_images"] > 0
    narration_job = manifest["gpu_groups"][0]["jobs"][0]
    assert "instruct" not in narration_job["inputs"]
    assert narration_job["voice_instruction"]["instruct_present"] is True
    assert narration_job["voice_instruction"]["instruct_effective_in_current_workflow"] is False


def capture_baseline(
    batch: dict,
    projects: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workflow, "_require_empty_queue", lambda _host: None)
    monkeypatch.setattr(
        workflow,
        "remote_runtime_manifest",
        lambda _host: [
            {
                "path": "/root/autodl-tmp/comfyui-runtime/output/historical.png",
                "size": 10,
                "sha256": "old",
            }
        ],
    )
    result = workflow.capture_gpu_baseline(batch, projects_root=projects, ssh_host="gpu-test")
    assert result["retained_preexisting_files"] == 1


def test_capture_baseline_protects_preexisting_remote_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch_path, batch, series, ledger_path, _ = make_fixture(tmp_path)
    projects = tmp_path / "projects"
    workflow.prepare_batch(batch, batch_path, series, projects_root=projects, ledger_path=ledger_path)
    capture_baseline(batch, projects, monkeypatch)
    policy = workflow.load_json(projects / batch["batch_id"] / "artifacts" / "retention_policy.json")
    assert policy["retain_project_assets"] == [
        "/root/autodl-tmp/comfyui-runtime/output/historical.png"
    ]


def test_refresh_uses_actual_audio_duration_and_builds_one_wan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch_path, batch, series, ledger_path, _ = make_fixture(tmp_path)
    projects = tmp_path / "projects"
    workflow.prepare_batch(batch, batch_path, series, projects_root=projects, ledger_path=ledger_path)
    capture_baseline(batch, projects, monkeypatch)
    narration = projects / "treeelf-fable-test-20260725" / "assets" / "audio" / "narration.mp3"
    narration.write_bytes(b"audio")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 20.2)
    result = workflow.refresh_visuals(batch, batch_path, series, projects_root=projects)
    assert result["scene_jobs"] == 5
    assert result["cover_jobs"] == 1
    assert result["wan_jobs"] == 1
    refreshed_manifest = workflow.load_json(projects / batch["batch_id"] / "artifacts" / "gpu_batch_manifest.json")
    cover_prompt = refreshed_manifest["gpu_groups"][4]["jobs"][0]["inputs"]["prompt"]
    assert "object/environment-only cover background" in cover_prompt
    assert "no character or portrait" not in cover_prompt
    plan = workflow.load_json(projects / "treeelf-fable-test-20260725" / "artifacts" / "visual_plan.json")
    assert plan["duration_seconds"] == 20.2
    assert plan["image_count"] == 5
    assert plan["wan_selection"]["scene_id"] == "scene-002"
    assert plan["wan_selection"]["generation_duration_seconds"] == 3
    assert all(slot["caption_range"] for slot in plan["slots"])
    assert all(slot["script_excerpt"] for slot in plan["slots"])
    captions = workflow.load_json(projects / "treeelf-fable-test-20260725" / "artifacts" / "captions.json")
    assert captions["captions"]


def test_fable_auto_wan_prefers_opening_fable_event() -> None:
    series = workflow.load_json(workflow.DEFAULT_SERIES)
    hero = {
        "enabled": True,
        "selection_policy": "opening_fable_event_only_or_none",
        "prompt": "stable motion",
    }
    slots = [
        {
            "id": "scene-001",
            "from": 0,
            "to": 4,
            "story_event": "主角第一次被看见",
            "fable_law": "身体开始透明，礼貌外壳仍然清晰。",
            "wan_candidate": True,
            "script_excerpt": "她第一次变透明。",
            "prompt": "stable calm camera drift",
        },
        {
            "id": "scene-002",
            "from": 4,
            "to": 14,
            "story_event": "她坐在房间里",
            "fable_law": "",
            "script_excerpt": "房间很安静。",
            "prompt": "stable room",
        },
    ]

    selected = workflow.select_fable_wan_slot(slots, hero, series)

    assert selected["id"] == "scene-001"
    assert selected["wan_selection_reason"] == "opening_fable_event"


def test_fable_auto_wan_requires_explicit_opening_candidate() -> None:
    series = workflow.load_json(workflow.DEFAULT_SERIES)
    hero = {
        "enabled": True,
        "selection_policy": "opening_fable_event_only_or_none",
        "prompt": "stable motion",
    }
    slots = [
        {
            "id": "scene-001",
            "from": 0,
            "to": 4,
            "story_event": "主角第一次被看见",
            "fable_law": "身体开始透明，礼貌外壳仍然清晰。",
            "script_excerpt": "她第一次变透明。",
            "prompt": "stable calm camera drift",
        }
    ]

    selected = workflow.select_fable_wan_slot(slots, hero, series)

    assert selected is None


def test_fable_auto_wan_skips_when_opening_is_setup() -> None:
    series = workflow.load_json(workflow.DEFAULT_SERIES)
    hero = {
        "enabled": True,
        "selection_policy": "opening_fable_event_only_or_none",
        "prompt": "stable motion",
    }
    slots = [
        {
            "id": "scene-001",
            "from": 0,
            "to": 4,
            "story_event": "清晨的房间",
            "fable_law": "",
            "script_excerpt": "清晨很安静。",
            "prompt": "quiet room",
        },
        {
            "id": "scene-002",
            "from": 4,
            "to": 13,
            "story_event": "墙纸开始吞掉家具",
            "fable_law": "被说出口的家具真的从墙纸里长出来。",
            "script_excerpt": "但是，墙纸开始变化。",
            "prompt": "stable wall, calm camera drift",
        },
    ]

    selected = workflow.select_fable_wan_slot(slots, hero, series)

    assert selected is None


def test_caption_sync_preserves_existing_caption_ranges() -> None:
    plan = {
        "duration_seconds": 10,
        "slots": [
            {
                "id": "scene-001",
                "from": 0,
                "to": 5,
                "caption_range": {"start_index": 0, "end_index": 0, "startMs": 0, "endMs": 5000},
            },
            {
                "id": "scene-002",
                "from": 5,
                "to": 10,
                "caption_range": {"start_index": 1, "end_index": 1, "startMs": 5000, "endMs": 10000},
            },
        ],
    }
    captions = [
        {"text": "第一句。", "startMs": 0, "endMs": 3600},
        {"text": "第二句。", "startMs": 3600, "endMs": 9200},
    ]

    synced = workflow.sync_visual_plan_to_captions(plan, captions)

    assert synced["caption_sync_strategy"] == "existing_caption_ranges"
    assert synced["slots"][0]["to"] == 3.6
    assert synced["slots"][1]["from"] == 3.6
    assert synced["slots"][1]["script_excerpt"] == "第二句。"


def test_caption_sync_falls_back_to_beat_anchors() -> None:
    plan = {
        "duration_seconds": 20,
        "slots": [
            {"id": "scene-001", "beat_id": "beat-01", "from": 0, "to": 5},
            {"id": "scene-002", "beat_id": "beat-02", "from": 5, "to": 12},
            {"id": "scene-003", "beat_id": "beat-02", "from": 12, "to": 20},
        ],
    }
    captions = [
        {"text": "开头寓言事件。", "startMs": 0, "endMs": 3000},
        {"text": "第二段。", "startMs": 3000, "endMs": 7000},
        {"text": "第三段。", "startMs": 7000, "endMs": 13000},
        {"text": "第四段。", "startMs": 13000, "endMs": 20000},
    ]

    synced = workflow.sync_visual_plan_to_captions(plan, captions)

    assert synced["caption_sync_strategy"] == "beat_anchor_ranges"
    assert synced["slots"][0]["script_excerpt"] == "开头寓言事件。"
    assert synced["slots"][1]["script_excerpt"] == "第二段。"
    assert synced["slots"][2]["script_excerpt"] == "第三段。第四段。"


def test_refresh_requires_generated_character_references_for_flux(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch_path, batch, series, ledger_path, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    episode["character_pack"] = {
        "enabled": True,
        "master_prompt": "character key art",
        "reference_prompts": ["front", "left", "right", "back"],
    }
    episode["semantic_beats"][0]["workflow"] = "flux2_klein_4ref"
    write_json(episode_path, episode)
    projects = tmp_path / "projects"
    workflow.prepare_batch(batch, batch_path, series, projects_root=projects, ledger_path=ledger_path)
    capture_baseline(batch, projects, monkeypatch)
    narration = projects / "treeelf-fable-test-20260725" / "assets" / "audio" / "narration.mp3"
    narration.write_bytes(b"audio")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 10.0)
    with pytest.raises(FileNotFoundError, match="character reference gate failed"):
        workflow.refresh_visuals(batch, batch_path, series, projects_root=projects)


def test_stage_local_selects_music_and_preserves_scene_timing(
    tmp_path: Path,
) -> None:
    _, _, series, _, episode_path = make_fixture(tmp_path)
    series = relaxed_series(series)
    projects = tmp_path / "projects"
    episode = workflow.load_json(episode_path)
    music = tmp_path / "warm-fable-纯音乐-ambient.mp3"
    music.write_bytes(b"music")
    episode["music_source"] = str(music)
    series = json.loads(json.dumps(series))
    series["music"]["library_dir"] = str(tmp_path)
    root = projects / episode["project_id"]
    (root / "assets" / "images" / "scenes").mkdir(parents=True)
    (root / "assets" / "images" / "cover").mkdir(parents=True)
    (root / "assets" / "audio").mkdir(parents=True)
    (root / "assets" / "images" / "scenes" / "scene-001.png").write_bytes(b"image")
    (root / "assets" / "images" / "cover" / "cover-background.png").write_bytes(b"cover")
    (root / "assets" / "audio" / "narration.mp3").write_bytes(b"audio")
    workflow.dump_json(
        root / "artifacts" / "visual_plan.json",
        {
            "duration_seconds": 4,
            "slots": [
                {
                    "id": "scene-001",
                    "from": 0,
                    "to": 4,
                    "motion": "push-in",
                    "output_name": "scene-001.png",
                    "script_excerpt": "第一段。",
                    "caption_range": {"start_index": 0, "end_index": 0, "startMs": 0, "endMs": 4000},
                    "story_event": "茶杯出现",
                }
            ],
        },
    )
    workflow.dump_json(root / "artifacts" / "captions.json", {"captions": [{"text": "第一段。", "startMs": 0, "endMs": 5000}]})
    result = workflow.stage_local_episode(episode, series, projects_root=projects)
    props = workflow.load_json(Path(result["props"]))
    synced_plan = workflow.load_json(root / "artifacts" / "visual_plan.json")
    assert props["musicSrc"] == "music/background.mp3"
    assert props["musicVolume"] == 0.3
    assert props["totalSeconds"] == 5
    assert synced_plan["duration_source"] == "calibrated_captions"
    assert synced_plan["duration_delta_seconds"] == 1
    assert (root / "artifacts" / "wan_retarget_report.json").is_file()
    assert props["captionStyle"]["safeBottom"] == 360
    assert props["coverSrc"] == "images/cover/cover-final.png"
    assert props["scenes"][0]["scriptExcerpt"] == "第一段。"
    assert (root / "artifacts" / "music_selection.json").is_file()


def test_fable_music_selection_penalizes_already_used_track(tmp_path: Path) -> None:
    _, _, series, _, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    first = tmp_path / "a-ambient-纯音乐.mp3"
    second = tmp_path / "b-ambient-纯音乐.mp3"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    series = json.loads(json.dumps(series))
    series["music"]["library_dir"] = str(tmp_path)

    selected = workflow.select_music_source(
        episode,
        series,
        used_music_paths=[str(first)],
    )

    assert selected["path"] == str(second)
    assert str(first) in selected["used_music_paths_penalized"]


def test_stage_local_requires_calibrated_captions_when_gate_enabled(tmp_path: Path) -> None:
    _, _, series, _, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    root = tmp_path / "projects" / episode["project_id"]
    (root / "assets" / "images" / "scenes").mkdir(parents=True)
    (root / "assets" / "images" / "cover").mkdir(parents=True)
    (root / "assets" / "audio").mkdir(parents=True)
    (root / "assets" / "images" / "scenes" / "scene-001.png").write_bytes(b"image")
    (root / "assets" / "images" / "cover" / "cover-background.png").write_bytes(b"cover")
    (root / "assets" / "audio" / "narration.mp3").write_bytes(b"audio")
    workflow.dump_json(
        root / "artifacts" / "visual_plan.json",
        {
            "duration_seconds": 4,
            "slots": [
                {
                    "id": "scene-001",
                    "from": 0,
                    "to": 4,
                    "duration": 4,
                    "motion": "push-in",
                    "output_name": "scene-001.png",
                }
            ],
        },
    )
    workflow.dump_json(root / "artifacts" / "captions.json", {"source": "proportional", "captions": [{"text": "第一段。", "startMs": 0, "endMs": 4000}]})
    with pytest.raises(PermissionError, match="calibrated captions"):
        workflow.stage_local_episode(episode, series, projects_root=tmp_path / "projects")


def test_stage_local_requires_visual_qc_when_gate_enabled(tmp_path: Path) -> None:
    _, _, series, _, episode_path = make_fixture(tmp_path)
    series = json.loads(json.dumps(series))
    series["quality_gates"]["require_audio_loudness_qc"] = False
    episode = workflow.load_json(episode_path)
    root = tmp_path / "projects" / episode["project_id"]
    (root / "assets" / "images" / "scenes").mkdir(parents=True)
    (root / "assets" / "images" / "cover").mkdir(parents=True)
    (root / "assets" / "audio").mkdir(parents=True)
    (root / "assets" / "images" / "scenes" / "scene-001.png").write_bytes(b"image")
    (root / "assets" / "images" / "cover" / "cover-background.png").write_bytes(b"cover")
    (root / "assets" / "audio" / "narration.mp3").write_bytes(b"audio")
    workflow.dump_json(
        root / "artifacts" / "visual_plan.json",
        {
            "duration_seconds": 4,
            "slots": [
                {
                    "id": "scene-001",
                    "from": 0,
                    "to": 4,
                    "duration": 4,
                    "motion": "push-in",
                    "output_name": "scene-001.png",
                }
            ],
        },
    )
    workflow.dump_json(
        root / "artifacts" / "captions.json",
        {"source": "whisper large-v3", "whisper_corrected": True, "captions": [{"text": "第一段。", "startMs": 0, "endMs": 4000}]},
    )
    with pytest.raises(PermissionError, match="visual_qc"):
        workflow.stage_local_episode(episode, series, projects_root=tmp_path / "projects")
    visual_qc = workflow.load_json(root / "artifacts" / "visual_qc.json")
    assert visual_qc["scenes"]["scene-001"]["image_path"].endswith("scene-001.png")
    assert visual_qc["cover"]["background_path"].endswith("cover-background.png")


def test_stage_local_requires_wan_motion_safety_when_wan_selected(tmp_path: Path) -> None:
    _, _, series, _, episode_path = make_fixture(tmp_path)
    series = json.loads(json.dumps(series))
    series["quality_gates"]["require_calibrated_captions_for_stage"] = False
    series["quality_gates"]["require_audio_loudness_qc"] = False
    episode = workflow.load_json(episode_path)
    music = tmp_path / "warm-fable-纯音乐-ambient.mp3"
    music.write_bytes(b"music")
    episode["music_source"] = str(music)
    series["music"]["library_dir"] = str(tmp_path)
    root = tmp_path / "projects" / episode["project_id"]
    (root / "assets" / "images" / "scenes").mkdir(parents=True)
    (root / "assets" / "images" / "cover").mkdir(parents=True)
    (root / "assets" / "audio").mkdir(parents=True)
    (root / "assets" / "video").mkdir(parents=True)
    (root / "assets" / "images" / "scenes" / "scene-001.png").write_bytes(b"image")
    (root / "assets" / "images" / "cover" / "cover-background.png").write_bytes(b"cover")
    (root / "assets" / "audio" / "narration.mp3").write_bytes(b"audio")
    (root / "assets" / "video" / "wan-hero.mp4").write_bytes(b"wan")
    workflow.dump_json(
        root / "artifacts" / "visual_plan.json",
        {
            "duration_seconds": 4,
            "wan_selection": {"enabled": True, "selected": True, "scene_id": "scene-001", "generation_duration_seconds": 3},
            "slots": [
                {
                    "id": "scene-001",
                    "from": 0,
                    "to": 4,
                    "duration": 4,
                    "motion": "push-in",
                    "output_name": "scene-001.png",
                    "script_excerpt": "第一段。",
                    "caption_range": {"start_index": 0, "end_index": 0, "startMs": 0, "endMs": 4000},
                }
            ],
        },
    )
    workflow.dump_json(root / "artifacts" / "captions.json", {"source": "whisper large-v3", "captions": [{"text": "第一段。", "startMs": 0, "endMs": 4000}]})
    workflow.dump_json(
        root / "artifacts" / "visual_qc.json",
        {
            "approved": True,
            "scenes": {
                "scene-001": {
                    "approved": True,
                    "story_matches_caption": True,
                    "anatomy_acceptable": True,
                    "text_free": True,
                    "wan_motion_safety": "risky",
                    "repair_needed": False,
                }
            },
            "cover": {
                "approved": True,
                "human_free": True,
                "text_free": True,
                "logo_free": True,
                "watermark_free": True,
                "title_safe_space": True,
            },
        },
    )

    with pytest.raises(PermissionError, match="visual QC"):
        workflow.stage_local_episode(episode, series, projects_root=tmp_path / "projects")


def test_visual_qc_requires_identity_stability_for_protagonist_scene(tmp_path: Path) -> None:
    _, _, _series, _, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    root = tmp_path / "projects" / episode["project_id"]
    (root / "artifacts").mkdir(parents=True)
    workflow.dump_json(
        root / "artifacts" / "visual_qc.json",
        {
            "approved": True,
            "scenes": {
                "scene-001": {
                    "approved": True,
                    "story_matches_caption": True,
                    "anatomy_acceptable": True,
                    "identity_stable_when_applicable": False,
                    "text_free": True,
                    "repair_needed": False,
                }
            },
            "cover": {
                "approved": True,
                "human_free": True,
                "text_free": True,
                "logo_free": True,
                "watermark_free": True,
                "title_safe_space": True,
            },
        },
    )
    plan = {
        "slots": [
            {
                "id": "scene-001",
                "workflow": "flux2_klein_4ref",
                "prompt": "stable protagonist identity in a room",
            }
        ]
    }

    with pytest.raises(PermissionError, match="failed_scenes"):
        workflow.require_visual_qc(episode, root, plan)


def test_refresh_builds_contact_sheet_and_requires_character_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch_path, batch, series, ledger_path, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    episode["character_pack"] = {
        "enabled": True,
        "master_prompt": "character key art",
        "reference_prompts": ["front", "left", "right", "back"],
    }
    episode["semantic_beats"][0]["workflow"] = "flux2_klein_4ref"
    write_json(episode_path, episode)
    projects = tmp_path / "projects"
    workflow.prepare_batch(batch, batch_path, series, projects_root=projects, ledger_path=ledger_path)
    capture_baseline(batch, projects, monkeypatch)
    root = projects / episode["project_id"]
    (root / "assets" / "audio" / "narration.mp3").write_bytes(b"audio")
    character_root = root / "assets" / "images" / "character"
    for index in range(1, 5):
        Image.new("RGB", (80, 120), (index * 30, index * 20, index * 10)).save(character_root / f"ref-{index:02d}.png")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 10.0)
    with pytest.raises(PermissionError, match="character contact sheet created"):
        workflow.refresh_visuals(batch, batch_path, series, projects_root=projects)
    assert (root / "artifacts" / "character_contact_sheet.png").is_file()
    review = workflow.load_json(root / "artifacts" / "character_review.json")
    assert review["approved"] is False


def test_voice_instruction_report_marks_clone_load_instruct_as_metadata() -> None:
    series = workflow.load_json(workflow.DEFAULT_SERIES)
    report = workflow.voice_instruction_report(series)
    assert report["workflow_template"] == "qwen3_tts_voice_clone_load"
    assert report["instruct_present"] is True
    assert report["instruct_effective_in_current_workflow"] is False
    assert "声包为准" in report["note"]


def test_delivery_uses_chinese_collision_safe_names(tmp_path: Path) -> None:
    episode = {"title": "测试/寓言", "project_id": "treeelf-fable-test"}
    delivery = tmp_path / "Movies"
    delivery.mkdir()
    first_video = workflow._delivery_video_path(episode, delivery)
    first_video.write_bytes(b"old")
    second_video = workflow._delivery_video_path(episode, delivery)
    assert second_video.name == "测试 寓言_v2.mp4"


def test_prompt_review_warnings_catch_aesthetic_negatives() -> None:
    episode = {
        "character_pack": {"master_prompt": "young woman, no under-eye shadows", "reference_prompts": []},
        "semantic_beats": [{"id": "b1", "prompt": "scene, no male figure visible"}],
        "cover_prompt": "symbolic room no text",
        "hero_wan": {"prompt": "stable motion no morphing"},
    }
    warnings = workflow.prompt_review_warnings(episode)
    assert {warning["pattern"] for warning in warnings} >= {"no under-eye shadows", "no male figure"}


def test_verify_inventory_tracks_every_current_batch_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch_path, batch, series, ledger_path, _ = make_fixture(tmp_path)
    projects = tmp_path / "projects"
    workflow.prepare_batch(batch, batch_path, series, projects_root=projects, ledger_path=ledger_path)
    capture_baseline(batch, projects, monkeypatch)
    narration = projects / "treeelf-fable-test-20260725" / "assets" / "audio" / "narration.mp3"
    narration.write_bytes(b"audio")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 10.0)
    workflow.refresh_visuals(batch, batch_path, series, projects_root=projects)
    manifest_path = projects / batch["batch_id"] / "artifacts" / "gpu_batch_manifest.json"
    manifest = workflow.load_json(manifest_path)
    for job in workflow._all_jobs(manifest):
        output = Path(job["inputs"]["output_path"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(job["job_id"].encode("utf-8"))
    result = workflow.verify_gpu_assets(
        batch,
        series,
        projects_root=projects,
        ledger_path=ledger_path,
    )
    assert result["assets"] == len(workflow._all_jobs(manifest))
    inventory = workflow.load_json(Path(result["inventory"]))
    assert all(row["size"] > 0 and len(row["sha256"]) == 64 for row in inventory["assets"])
    assert workflow.load_json(ledger_path)["items"][0]["status"] == "gpu_assets_complete"


def test_series_configuration_does_not_reference_philosophy_workflow() -> None:
    config_text = workflow.DEFAULT_SERIES.read_text(encoding="utf-8")
    assert "zh-philosophy-video" not in config_text
    assert '"composition_mode": "templated"' in config_text
    assert '"target_seconds_per_image": 5' in config_text


def test_complete_local_delivers_and_marks_article_completed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch_path, batch, series, ledger_path, episode_path = make_fixture(tmp_path)
    projects = tmp_path / "projects"
    delivery = tmp_path / "Movies" / "treeelf-fable"
    series = json.loads(json.dumps(series))
    series["delivery_dir"] = str(delivery)
    workflow.prepare_batch(batch, batch_path, series, projects_root=projects, ledger_path=ledger_path)
    manifest_path = projects / batch["batch_id"] / "artifacts" / "gpu_batch_manifest.json"
    manifest = workflow.load_json(manifest_path)
    manifest["status"] = "local_packaging"
    manifest["episodes"][0]["status"] = "local_packaging"
    workflow.dump_json(manifest_path, manifest)
    ledger = workflow.load_json(ledger_path)
    ledger["items"][0]["status"] = "local_packaging"
    workflow.dump_json(ledger_path, ledger)
    episode = workflow.load_json(episode_path)
    final = projects / episode["project_id"] / "renders" / "final.mp4"
    final.write_bytes(b"valid-video-placeholder")
    cover = projects / episode["project_id"] / "assets" / "images" / "cover" / "cover-final.png"
    cover.parent.mkdir(parents=True, exist_ok=True)
    cover.write_bytes(b"cover-placeholder")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 12.0)

    result = workflow.complete_local_batch(
        batch,
        batch_path,
        series,
        projects_root=projects,
        ledger_path=ledger_path,
    )

    assert Path(result["deliveries"][0]["video"]).is_file()
    assert result["deliveries"][0]["movies_contains_cover"] is False
    assert Path(result["deliveries"][0]["cover_asset"]) == cover
    assert not list(delivery.glob("*.png"))
    report = workflow.load_json(projects / episode["project_id"] / "artifacts" / "delivery_report.json")
    assert report["movies_contains_cover"] is False
    assert Path(report["cover_asset"]) == cover
    assert workflow.load_json(ledger_path)["items"][0]["status"] == "completed"
    assert workflow.load_json(manifest_path)["status"] == "completed"


def test_cleanup_local_removes_only_derivatives_after_delivery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch_path, batch, series, ledger_path, episode_path = make_fixture(tmp_path)
    projects = tmp_path / "projects"
    delivery = tmp_path / "Movies" / "treeelf-fable"
    series = json.loads(json.dumps(series))
    series["delivery_dir"] = str(delivery)
    workflow.prepare_batch(batch, batch_path, series, projects_root=projects, ledger_path=ledger_path)
    manifest_path = projects / batch["batch_id"] / "artifacts" / "gpu_batch_manifest.json"
    manifest = workflow.load_json(manifest_path)
    manifest["status"] = "local_packaging"
    manifest["episodes"][0]["status"] = "local_packaging"
    workflow.dump_json(manifest_path, manifest)
    ledger = workflow.load_json(ledger_path)
    ledger["items"][0]["status"] = "local_packaging"
    workflow.dump_json(ledger_path, ledger)
    episode = workflow.load_json(episode_path)
    project = projects / episode["project_id"]
    final = project / "renders" / "final.mp4"
    final.write_bytes(b"valid-video-placeholder")
    cover = project / "assets" / "images" / "cover" / "cover-final.png"
    cover.parent.mkdir(parents=True, exist_ok=True)
    cover.write_bytes(b"cover-placeholder")
    scene = project / "assets" / "images" / "scenes" / "scene-001.png"
    scene.parent.mkdir(parents=True, exist_ok=True)
    scene.write_bytes(b"scene-placeholder")
    central_music = tmp_path / "music" / "chosen.mp3"
    central_music.parent.mkdir(parents=True, exist_ok=True)
    central_music.write_bytes(b"music")
    background = project / "assets" / "music" / "background.mp3"
    background.parent.mkdir(parents=True, exist_ok=True)
    background.write_bytes(b"music")
    workflow.dump_json(
        project / "artifacts" / "music_selection.json",
        {"selected": {"path": str(central_music)}},
    )
    public = workflow.REMOTION_ROOT / "public" / "treeelf-fable" / episode["project_id"]
    public.mkdir(parents=True, exist_ok=True)
    (public / "duplicate.txt").write_text("duplicate", encoding="utf-8")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 12.0)
    workflow.complete_local_batch(batch, batch_path, series, projects_root=projects, ledger_path=ledger_path)

    dry_run = workflow.cleanup_local_batch(
        batch,
        batch_path,
        series,
        projects_root=projects,
        dry_run=True,
    )
    assert any(item["path"] == str(public) for item in dry_run["targets"])
    assert any(item["path"] == str(project / "renders") for item in dry_run["targets"])
    assert any(item["path"] == str(background) for item in dry_run["targets"])
    assert cover.is_file()
    assert scene.is_file()

    workflow.cleanup_local_batch(
        batch,
        batch_path,
        series,
        projects_root=projects,
        dry_run=False,
        yes=True,
    )
    assert not public.exists()
    assert not background.exists()
    assert (project / "renders").is_dir()
    assert not any((project / "renders").iterdir())
    assert cover.is_file()
    assert scene.is_file()
