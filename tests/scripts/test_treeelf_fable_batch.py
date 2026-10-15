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
        "narration_text": "第一段。第二段。",
        "protagonist": {"type": "物品", "description": "一只茶杯"},
        "semantic_beats": [
            {
                "id": "beat-01",
                "subject_mode": "object",
                "script_anchor": "第一段",
                "weight": 1,
                "workflow": "krea2_low_vram",
                "story_event": "一只茶杯在桌面上轻轻转向光源。",
                "fable_law": "被忽略的物品会在安静处自己寻找被看见的位置。",
                "art_style_logic": "克制的现代寓言绘本质感让茶杯的微小动作显得像真实事件。",
                "prompt_variants": ["vertical storybook tea cup, no text, no letters, no logo"],
            },
            {
                "id": "beat-02",
                "subject_mode": "environment",
                "script_anchor": "第二段",
                "weight": 1,
                "workflow": "krea2_low_vram",
                "story_event": "桌面空下来，只留下茶杯移动过的浅浅圆痕。",
                "fable_law": "物品离开后，位置仍然保留它想被看见的痕迹。",
                "art_style_logic": "安静留白和纸面纹理适合表现寓言结尾的余韵。",
                "prompt_variants": ["vertical storybook empty table, no text, no letters, no logo"],
            },
        ],
        "character_reference_paths": [],
        "cover_prompt": "vertical symbolic still life artwork, quiet open upper field, no text, no letters, no logo",
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
        "require_cover_ocr": False,
        "require_script_anchors": True,
    }
    return series


def test_sync_ledger_ignores_review_status_and_deduplicates_short_versions(tmp_path: Path) -> None:
    source_dir = tmp_path / "fables"
    source_dir.mkdir()
    original = source_dir / "2026-07-27_新寓言.md"
    original.write_text("---\nstatus: draft\nreview_status: pending\n---\n# 新寓言\n", encoding="utf-8")
    short = source_dir / "2026-07-28_新寓言_精简版.md"
    short.write_text("---\nstatus: ready\nreview_status: passed\n---\n# 新寓言\n", encoding="utf-8")
    done = source_dir / "2026-07-27_旧寓言.md"
    done.write_text("---\nreview_status: pending\n---\n# 旧寓言\n", encoding="utf-8")
    ledger_path = tmp_path / "ledger.json"
    write_json(ledger_path, {
        "version": "1.0",
        "series": "treeelf-fable",
        "items": [{"source": done.name, "status": "completed", "output": "/missing/history.mp4"}],
    })
    series = workflow.load_json(workflow.DEFAULT_SERIES)

    report = workflow.sync_fable_source_ledger(
        series,
        source_dir=source_dir,
        ledger_path=ledger_path,
    )

    assert report["editorial_status_ignored"] is True
    assert report["added"] == [str(original)]
    ledger = workflow.load_json(ledger_path)
    sources = [item["source"] for item in ledger["items"]]
    assert original.name in sources
    assert short.name not in sources
    assert done.name in sources


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


def test_adult_male_protagonist_is_allowed_with_story_rationale(tmp_path: Path) -> None:
    batch_path, batch, series, _, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    episode["protagonist"] = {
        "type": "成年男性",
        "description": "一位年长的男性父亲",
        "selection_rationale": "父子关系是本篇冲突成立的关键，男性角色更贴合故事关系。",
        "appearance": {
            "age_band": "五十岁左右",
            "hair": "灰黑短直发",
            "silhouette": "宽肩旧外套与磨损皮鞋构成沉稳轮廓",
        },
    }
    write_json(episode_path, episode)
    errors = workflow.validate_batch(batch, batch_path, series)
    assert not any("protagonist" in error for error in errors)


def test_human_protagonist_requires_selection_rationale(tmp_path: Path) -> None:
    batch_path, batch, series, _, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    episode["protagonist"] = {
        "type": "成年女性",
        "description": "一位成年女性",
        "appearance": {"age_band": "三十岁", "hair": "黑色短直发", "silhouette": "深色长外套"},
    }
    write_json(episode_path, episode)
    errors = workflow.validate_batch(batch, batch_path, series)
    assert any("selection_rationale" in error for error in errors)


def test_batch_rejects_three_default_curly_hair_characters(tmp_path: Path) -> None:
    batch_path, batch, series, _, episode_path = make_fixture(tmp_path)
    base = workflow.load_json(episode_path)
    paths = []
    for index in range(3):
        source = tmp_path / f"fable-{index}.md"
        source.write_text("第一段。第二段。", encoding="utf-8")
        episode = json.loads(json.dumps(base))
        episode["project_id"] = f"treeelf-fable-curl-{index}"
        episode["source_script_md"] = str(source)
        episode["protagonist"] = {
            "type": "成年女性",
            "description": f"第{index}位成年女性角色",
            "selection_rationale": "这个中性角色由女性承担自然成立。",
            "appearance": {
                "age_band": f"{25 + index}岁左右",
                "hair": "深色短卷发",
                "silhouette": f"第{index}种不同服装轮廓",
            },
        }
        path = tmp_path / f"episode-{index}.json"
        write_json(path, episode)
        paths.append(path.name)
    batch["episode_configs"] = paths
    write_json(batch_path, batch)

    errors = workflow.validate_batch(batch, batch_path, series)

    assert any("overuse one hair family:curly" in error for error in errors)


def test_cover_prompt_with_human_terms_is_rejected(tmp_path: Path) -> None:
    batch_path, batch, series, _, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    episode["cover_prompt"] = "vertical cover, young woman beside a symbolic table, text-free"
    write_json(episode_path, episode)

    errors = workflow.validate_batch(batch, batch_path, series)

    assert any("cover_prompt must be human-free" in error for error in errors)


def test_cover_prompt_with_layout_cues_is_rejected(tmp_path: Path) -> None:
    batch_path, batch, series, _, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    episode["cover_prompt"] = "symbolic empty room, editorial composition with space for title"
    write_json(episode_path, episode)

    errors = workflow.validate_batch(batch, batch_path, series)

    assert any("remove layout/typography cues" in error for error in errors)


def test_human_free_compiled_prompt_does_not_receive_protagonist_or_human_camera() -> None:
    beat = {
        "id": "beat-01",
        "subject_mode": "environment",
        "prompt": "human-free midnight street with one open window",
    }

    prompt = workflow.compile_scene_prompt(
        beat,
        0,
        protagonist_identity="a woman with short hair",
        guardrails=list(workflow.TECHNICAL_GUARDRAILS),
    )

    assert "Episode protagonist identity" not in prompt
    assert "protagonist's action" not in prompt
    assert workflow.compiled_prompt_contract_errors(prompt, "environment") == []


def test_script_anchors_bind_beats_to_matching_caption_semantics() -> None:
    captions = [
        {"text": "杯子先朝向窗边。", "startMs": 0, "endMs": 4000},
        {"text": "后来桌面只剩一个圆痕。", "startMs": 4000, "endMs": 9000},
    ]
    beats = [
        {
            "id": "beat-01",
            "subject_mode": "object",
            "script_anchor": "杯子先朝向窗边",
            "prompt": "a cup turns toward a window",
        },
        {
            "id": "beat-02",
            "subject_mode": "environment",
            "script_anchor": "后来桌面只剩",
            "prompt": "an empty table with a circular trace",
        },
    ]

    slots = workflow.build_visual_slots(9, beats, target_seconds=5, captions=captions)

    assert [slot["beat_id"] for slot in slots] == ["beat-01", "beat-02"]
    assert all(slot["caption_binding"] == "script_anchor" for slot in slots)
    assert "杯子" in slots[0]["script_excerpt"]
    assert "圆痕" in slots[1]["script_excerpt"]


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
    blueprint = workflow.load_json(episode_root / "artifacts" / "gpu_visual_blueprint.json")
    assert blueprint["compiled_before_gpu"] is True
    assert blueprint["slots"]
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
    compiled = workflow.load_json(episode_root / "artifacts" / "compiled_prompt_report.json")
    assert compiled["scenes"][0]["subject_mode"] == "object"
    assert compiled["scenes"][0]["errors"] == []


def test_prepare_queues_one_turnaround_sheet_instead_of_independent_views(tmp_path: Path) -> None:
    batch_path, batch, series, ledger_path, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    episode["character_pack"] = {
        "enabled": True,
        "mode": "single_turnaround_sheet",
        "turnaround_prompt": "one 2x2 turnaround image of the exact same cup in four distinct views",
    }
    episode["semantic_beats"][0]["workflow"] = "flux2_klein_4ref"
    write_json(episode_path, episode)

    result = workflow.prepare_batch(
        batch,
        batch_path,
        series,
        projects_root=tmp_path / "projects",
        ledger_path=ledger_path,
    )
    manifest = workflow.load_json(Path(result["manifest"]))
    jobs = manifest["gpu_groups"][1]["jobs"]

    assert len(jobs) == 1
    assert jobs[0]["job_id"].endswith(":character-turnaround-sheet")
    assert jobs[0]["inputs"]["output_path"].endswith("turnaround-sheet.png")


def test_crop_character_turnaround_sheet_creates_four_distinct_quadrants(tmp_path: Path) -> None:
    sheet = Image.new("RGB", (800, 1200), "white")
    colors = [(220, 20, 20), (20, 220, 20), (20, 20, 220), (220, 180, 20)]
    for index, color in enumerate(colors):
        x = (index % 2) * 400
        y = (index // 2) * 600
        Image.new("RGB", (400, 600), color).save(tmp_path / f"quadrant-{index}.png")
        sheet.paste(Image.open(tmp_path / f"quadrant-{index}.png"), (x, y))
    sheet_path = tmp_path / "turnaround-sheet.png"
    sheet.save(sheet_path)

    references = workflow.crop_character_turnaround_sheet(sheet_path, tmp_path / "character")

    assert len(references) == 4
    assert [Image.open(path).getpixel((10, 10)) for path in references] == colors


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
    assert "symbolic object and environment artwork" in cover_prompt
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


def test_refresh_blocks_only_flux_when_character_references_are_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch_path, batch, series, ledger_path, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    episode["character_pack"] = {
        "enabled": True,
        "mode": "single_turnaround_sheet",
        "turnaround_prompt": "one 2x2 sheet with the same cup character in four views",
    }
    episode["semantic_beats"][0]["workflow"] = "flux2_klein_4ref"
    write_json(episode_path, episode)
    projects = tmp_path / "projects"
    workflow.prepare_batch(batch, batch_path, series, projects_root=projects, ledger_path=ledger_path)
    capture_baseline(batch, projects, monkeypatch)
    narration = projects / "treeelf-fable-test-20260725" / "assets" / "audio" / "narration.mp3"
    narration.write_bytes(b"audio")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 10.0)
    result = workflow.refresh_visuals(batch, batch_path, series, projects_root=projects)

    assert result["blocked_flux_jobs"] > 0
    manifest = workflow.load_json(projects / batch["batch_id"] / "artifacts" / "gpu_batch_manifest.json")
    groups = {group["id"]: group for group in manifest["gpu_groups"]}
    assert groups["scene_images_krea"]["jobs"]
    assert groups["covers"]["jobs"]
    assert all(job["status"] == "blocked_character_review" for job in groups["scene_images_flux"]["jobs"])

def test_stage_local_selects_music_and_preserves_scene_timing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    def fake_normalize(source_path, target_path, **_kwargs):
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(source_path.read_bytes())
        return {"mode": "test", "verified": True, "path": str(target_path)}
    monkeypatch.setattr(workflow, "normalize_background_music", fake_normalize)
    result = workflow.stage_local_episode(episode, series, projects_root=projects)
    props = workflow.load_json(Path(result["props"]))
    synced_plan = workflow.load_json(root / "artifacts" / "visual_plan.json")
    assert props["musicSrc"] == "music/background.mp3"
    assert props["musicVolume"] == 0.3
    assert props["totalSeconds"] == 5
    assert synced_plan["duration_source"] == "calibrated_captions"
    assert synced_plan["duration_delta_seconds"] == 1
    assert (root / "artifacts" / "wan_retarget_report.json").is_file()
    assert props["captionStyle"]["safeBottom"] == 460
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


def test_missing_visual_qc_creates_nonblocking_template(tmp_path: Path) -> None:
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
    plan = workflow.load_json(root / "artifacts" / "visual_plan.json")
    visual_qc = workflow.require_visual_qc(episode, root, plan)
    assert visual_qc["scenes"]["scene-001"]["image_path"].endswith("scene-001.png")
    assert visual_qc["cover"]["background_path"].endswith("cover-background.png")
    assert visual_qc["blocking_findings"] == []


def test_stage_local_falls_back_to_still_when_wan_motion_is_risky(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    monkeypatch.setattr(
        workflow,
        "select_and_record_music_usage",
        lambda *_args, **_kwargs: ({"path": str(music)}, {"status": "reserved"}),
    )
    monkeypatch.setattr(
        workflow,
        "normalize_background_music",
        lambda source, target, **_kwargs: (
            target.parent.mkdir(parents=True, exist_ok=True),
            target.write_bytes(source.read_bytes()),
            {"verified": True, "path": str(target)},
        )[-1],
    )
    monkeypatch.setattr(workflow, "build_audio_mix_qc", lambda *_args, **_kwargs: {"approved_for_render": True})

    staged = workflow.stage_local_episode(episode, series, projects_root=tmp_path / "projects")
    props = workflow.load_json(Path(staged["props"]))
    assert props["scenes"][0]["kind"] == "still"
    assert props["wanPolicy"]["applied_to_render"] is False
    assert (root / "artifacts" / "wan_static_fallback.json").is_file()


def test_visual_qc_blocks_only_explicit_blocking_scene_issue(tmp_path: Path) -> None:
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
                    "severity": "blocking",
                    "blocking_issue": True,
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


def test_refresh_builds_contact_sheet_and_blocks_only_flux_until_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch_path, batch, series, ledger_path, episode_path = make_fixture(tmp_path)
    episode = workflow.load_json(episode_path)
    episode["character_pack"] = {
        "enabled": True,
        "mode": "single_turnaround_sheet",
        "turnaround_prompt": "one 2x2 sheet with the same cup character in four views",
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
    result = workflow.refresh_visuals(batch, batch_path, series, projects_root=projects)
    assert (root / "artifacts" / "character_contact_sheet.png").is_file()
    review = workflow.load_json(root / "artifacts" / "character_review.json")
    assert review["approved"] is False
    assert result["blocked_flux_jobs"] > 0
    manifest = workflow.load_json(projects / batch["batch_id"] / "artifacts" / "gpu_batch_manifest.json")
    groups = {group["id"]: group for group in manifest["gpu_groups"]}
    assert groups["scene_images_krea"]["jobs"]
    assert groups["covers"]["jobs"]
    assert all(job["status"] == "blocked_character_review" for job in groups["scene_images_flux"]["jobs"])

    review["approved"] = True
    review["checks"] = {key: True for key in review["checks"]}
    workflow.dump_json(root / "artifacts" / "character_review.json", review)
    released = workflow.refresh_visuals(batch, batch_path, series, projects_root=projects)
    assert released["blocked_flux_jobs"] == 0
    manifest = workflow.load_json(projects / batch["batch_id"] / "artifacts" / "gpu_batch_manifest.json")
    groups = {group["id"]: group for group in manifest["gpu_groups"]}
    assert all(job["status"] == "queued" for job in groups["scene_images_flux"]["jobs"])


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


def test_completed_delivery_reconciles_stale_gpu_queued_ledger_status() -> None:
    ledger = {
        "items": [{"source": "寓言.md", "status": "gpu_queued"}],
    }

    workflow.transition_ledger_item(
        ledger,
        "寓言.md",
        "completed",
        project_id="treeelf-fable-test",
        output="/Movies/寓言.mp4",
    )

    item = ledger["items"][0]
    assert item["status"] == "completed"
    assert item["status_reconciled_from"] == "gpu_queued"
    assert item["output"] == "/Movies/寓言.mp4"


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
    monkeypatch.setattr(
        workflow,
        "cover_ocr_check",
        lambda path: {"path": str(path), "available": True, "passed": True, "detected_tokens": []},
    )
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
    monkeypatch.setattr(
        workflow,
        "build_final_audio_mix_qc",
        lambda *_args, **_kwargs: {"approved_for_delivery": True},
    )

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

    repeated = workflow.complete_local_batch(
        batch,
        batch_path,
        series,
        projects_root=projects,
        ledger_path=ledger_path,
    )
    assert repeated["deliveries"][0]["video"] == result["deliveries"][0]["video"]
    assert repeated["deliveries"][0]["delivery_mode"] == "reused_verified_delivery"
    assert len(list(delivery.glob("*.mp4"))) == 1


def test_complete_local_refuses_failed_final_audio_qc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch_path, batch, series, ledger_path, episode_path = make_fixture(tmp_path)
    projects = tmp_path / "projects"
    delivery = tmp_path / "Movies" / "treeelf-fable"
    series = json.loads(json.dumps(series))
    series["delivery_dir"] = str(delivery)
    workflow.prepare_batch(
        batch, batch_path, series, projects_root=projects, ledger_path=ledger_path
    )
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
    final.write_bytes(b"bad-audio-video")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 12.0)
    monkeypatch.setattr(
        workflow,
        "build_final_audio_mix_qc",
        lambda *_args, **_kwargs: {
            "approved_for_delivery": False,
            "checks": {"integrated_loudness_in_range": False},
        },
    )

    with pytest.raises(ValueError, match="final audio mix QC failed"):
        workflow.complete_local_batch(
            batch,
            batch_path,
            series,
            projects_root=projects,
            ledger_path=ledger_path,
        )
    assert not list(delivery.glob("*.mp4"))


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
    monkeypatch.setattr(
        workflow,
        "build_final_audio_mix_qc",
        lambda *_args, **_kwargs: {"approved_for_delivery": True},
    )
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
