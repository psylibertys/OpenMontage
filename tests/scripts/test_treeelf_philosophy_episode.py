from __future__ import annotations

import json
from pathlib import Path

import scripts.treeelf_philosophy_episode as workflow
from scripts import treeelf_philosophy_timeline as timeline


def series_profile() -> dict:
    return json.loads(workflow.DEFAULT_SERIES_CONFIG.read_text(encoding="utf-8"))


def episode_config(source: Path) -> dict:
    config = json.loads(workflow.DEFAULT_EPISODE_CONFIG.read_text(encoding="utf-8"))
    config["project_id"] = "treeelf-test-episode"
    config["source_script_md"] = str(source)
    config["remotion_public_root"] = str(source.parent / "remotion-public")
    return config


def make_source(path: Path) -> None:
    path.write_text(
        "---\n"
        "type: 短视频文案\n"
        "asset_id: test-asset\n"
        "status: ready\n"
        "review_status: passed\n"
        "created: 2026-07-22\n"
        "---\n\n"
        "# 测试文章\n\n第一段。\n\n第二段。\n",
        encoding="utf-8",
    )


def test_template_and_locked_series_profile_are_valid(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    make_source(source)

    config = episode_config(source)

    assert workflow.validate_episode(config, series_profile()) == []
    assert series_profile()["music"]["selected_mix_profile"] == "B3-narration-first-quieter"
    assert series_profile()["music"]["remotion_volume"] == 0.3
    assert series_profile()["caption"]["safe_bottom"] >= 330
    assert series_profile()["production_defaults"]["wan_max_generation_seconds"] == 5
    assert config["article_visual_assets"]["wan_policy"]["enabled"] is True
    assert len(config["article_visual_assets"]["images"]) == 15
    assert len(config["article_visual_assets"]["videos"]) == 2


def test_music_selection_penalizes_already_used_track(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    config["music_source"] = ""
    first = tmp_path / "a-ambient-纯音乐.mp3"
    second = tmp_path / "b-ambient-纯音乐.mp3"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    series = series_profile()
    series["music"]["library_dir"] = str(tmp_path)

    selected = workflow.select_music_source(
        config,
        series,
        script_body="一篇关于夜晚和孤独的文章。",
        used_music_paths=[str(first)],
    )

    assert selected["path"] == str(second)
    assert str(first) in selected["used_music_paths_penalized"]


def test_validation_rejects_missing_text_guardrail_and_repeated_motion(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    config["article_visual_assets"]["technical_guardrails"] = []
    config["edit"]["scenes"][2]["motion"] = config["edit"]["scenes"][1]["motion"]

    errors = workflow.validate_episode(config, series_profile())

    assert any("technical_guardrails must cover text-free media" in error for error in errors)
    assert "adjacent still scenes must not repeat the same motion" in errors


def test_validation_rejects_image_reuse_between_still_and_wan(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    config["edit"]["scenes"][1]["src"] = "images/P00.png"

    errors = workflow.validate_episode(config, series_profile())

    assert "Wan reference images must not also be reused as ordinary still scenes" in errors
    assert "every content image must be used exactly once: either as one still scene or one Wan reference" in errors


def test_validation_rejects_repeated_still_image(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    config["edit"]["scenes"][2]["src"] = config["edit"]["scenes"][1]["src"]

    errors = workflow.validate_episode(config, series_profile())

    assert "edit.scenes must not reuse a still-image src" in errors


def test_validation_rejects_overlong_wan_generation(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    config["article_visual_assets"]["videos"][0]["duration_seconds"] = 8

    errors = workflow.validate_episode(config, series_profile())

    assert any("Wan duration_seconds must be <= 5" in error for error in errors)


def test_wan_policy_selects_opening_and_longest_safe_scene(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    scenes = [
        {"id": "S01", "kind": "video", "src": "video/W01.mp4", "from": 0, "to": 6},
        {"id": "S02", "kind": "still", "src": "images/P01.png", "from": 6, "to": 10, "motion": "push-left"},
        {"id": "S03", "kind": "still", "src": "images/P02.png", "from": 10, "to": 21, "motion": "drift-up", "script_excerpt": "最长的核心隐喻"},
        {"id": "S04", "kind": "video", "src": "video/W02.mp4", "from": 21, "to": 26},
    ]

    jobs, policy = timeline.resolve_wan_generation_plan(config, scenes)
    updated = timeline.apply_wan_scene_policy(config, scenes, jobs)

    assert policy["opening_reference"] == "P00"
    assert policy["longest_reference"] == "P02"
    assert {job["id"]: job["reference"] for job in jobs} == {"W01": "P00", "W02": "P02"}
    assert max(job["duration_seconds"] for job in jobs) <= 5
    assert updated[2]["kind"] == "video"
    assert updated[2]["src"] == "video/W02.mp4"
    assert updated[2]["wan_reference"] == "P02"
    assert updated[3]["kind"] == "still"
    assert updated[3]["src"] == "images/P06.png"


def test_validation_rejects_text_bearing_prompt_without_mitigation(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    config["article_visual_assets"]["images"][3]["prompt"] = (
        "Vertical 9:16 symbolic still life, glass jar holding a phrase, "
        "folded dream note, refined craft, text-free visual field"
    )

    errors = workflow.validate_episode(config, series_profile())

    assert any("prompt uses text-bearing visual terms" in error for error in errors)
    assert any("text_risk_mitigation" in error for error in errors)


def test_validation_allows_text_risk_when_review_documents_visual_substitute(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    config["article_visual_assets"]["images"][3]["prompt_review"] += (
        " text_risk_mitigation: 用色块、无字折形和光斑替代句子内容，所有表面保持纯材质。"
    )
    config["article_visual_assets"]["images"][3]["prompt"] = (
        "Vertical 9:16 symbolic still life, plain cards and glass objects arranged as memory fragments, "
        "soft color clouds, tactile surfaces, text-free visual field"
    )

    assert workflow.validate_episode(config, series_profile()) == []


def test_validation_allows_more_than_fourteen_content_images(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    extra = dict(config["article_visual_assets"]["images"][-1])
    extra.update({"id": "P14", "seed": 91016})
    config["article_visual_assets"]["images"].append(extra)
    config["edit"]["scenes"].append({
        "id": "S15",
        "kind": "still",
        "src": "images/P14.png",
        "from": 80,
        "to": 85,
        "motion": "pull-back",
    })

    assert workflow.validate_episode(config, series_profile()) == []


def test_prepare_snapshots_source_without_marking_it_complete(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)

    result = workflow.prepare_episode(config, series_profile(), projects_dir=tmp_path / "projects")

    project = Path(result["project_dir"])
    assert (project / "artifacts" / "source_script.md").read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    assert "production_status" not in source.read_text(encoding="utf-8")
    assert (project / "artifacts" / "gpu_usage_report.json").is_file()
    script = json.loads((project / "artifacts" / "script.json").read_text(encoding="utf-8"))
    assert script["source_metadata"]["created"] == "2026-07-22"


def test_narration_extraction_does_not_include_markdown_heading(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    projects = tmp_path / "projects"
    workflow.prepare_episode(config, series_profile(), projects_dir=projects)
    submitted: list[str] = []

    monkeypatch.setattr(workflow, "ensure_gpu_preflight", lambda _path: None)

    def fake_execute_candidate(**kwargs):
        submitted.append(kwargs["inputs"]["text"])
        output = Path(kwargs["inputs"]["output_path"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"mp3")
        return {"path": str(output)}

    monkeypatch.setattr(workflow, "_execute_candidate", fake_execute_candidate)
    monkeypatch.setattr(workflow.subprocess, "run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 12.0)

    workflow.generate_narration(config, series_profile(), projects_dir=projects)

    assert submitted == ["第一段。", "第二段。"]


def test_exact_captions_keep_reviewed_text_and_use_segment_durations(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    projects = tmp_path / "projects"
    workflow.prepare_episode(config, series_profile(), projects_dir=projects)
    segment_dir = projects / config["project_id"] / "assets" / "audio" / "voice02_segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    (segment_dir / "s01.mp3").write_bytes(b"one")
    (segment_dir / "s02.mp3").write_bytes(b"two")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 3.0)

    result = workflow.build_exact_captions(config, projects_dir=projects)
    payload = json.loads(Path(result["path"]).read_text(encoding="utf-8"))

    assert "".join(item["text"] for item in payload["segments"]) == "第一段。第二段。"
    assert payload["duration_seconds"] == 6.0
    assert payload["segments"][-1]["end"] == 5.94


def test_delivery_copies_then_marks_source_completed(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    config["final_output_dir"] = str(tmp_path / "Movies")
    projects = tmp_path / "projects"
    workflow.prepare_episode(config, series_profile(), projects_dir=projects)
    render = tmp_path / "final.mp4"
    render.write_bytes(b"verified-render-content")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 72.5)

    result = workflow.deliver(config, render, projects_dir=projects)

    output = Path(result["output"])
    assert output.read_bytes() == render.read_bytes()
    updated = source.read_text(encoding="utf-8")
    assert 'production_status: "completed"' in updated
    assert 'video_project_id: "treeelf-test-episode"' in updated
    assert str(output) in updated


def test_delivery_refuses_source_changed_after_prepare(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    projects = tmp_path / "projects"
    workflow.prepare_episode(config, series_profile(), projects_dir=projects)
    source.write_text(source.read_text(encoding="utf-8") + "\n修订。\n", encoding="utf-8")
    render = tmp_path / "final.mp4"
    render.write_bytes(b"render")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 72.5)

    try:
        workflow.deliver(config, render, projects_dir=projects)
    except ValueError as exc:
        assert "Source changed after prepare" in str(exc)
    else:
        raise AssertionError("delivery should refuse a changed source")


def test_stage_and_delivery_use_hardlinks_then_remove_derivative_copies(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    config["final_output_dir"] = str(tmp_path / "Movies")
    music = tmp_path / "central-music.mp3"
    music.write_bytes(b"central-music")
    config["music_source"] = str(music)
    projects = tmp_path / "projects"
    workflow.prepare_episode(config, series_profile(), projects_dir=projects)
    target = projects / config["project_id"]
    image = target / "assets" / "images" / "article" / "C01.png"
    image.write_bytes(b"cover")
    video = target / "assets" / "video" / "article" / "W01.mp4"
    video.write_bytes(b"wan")
    narration = target / "assets" / "audio" / "narration.wav"
    narration.write_bytes(b"narration")
    raw = target / "assets" / "audio" / "narration_raw.mp3"
    raw.write_bytes(b"raw")

    staged = workflow.stage_remotion(config, series_profile(), projects_dir=projects)
    staged_cover = Path(staged["public_dir"]) / "images" / "C01.png"
    props = json.loads(Path(staged["props"]).read_text(encoding="utf-8"))
    assert props["musicVolume"] == 0.3
    assert staged["staged"]["hardlink"] >= 3
    assert staged_cover.stat().st_ino == image.stat().st_ino

    render = target / "renders" / "final.mp4"
    render.write_bytes(b"verified-render")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 72.5)
    result = workflow.deliver(
        config,
        render,
        projects_dir=projects,
        series=series_profile(),
    )

    output = Path(result["output"])
    assert result["delivery_mode"] == "hardlink"
    assert output.is_file()
    assert not Path(staged["public_dir"]).exists()
    assert (target / "renders").is_dir()
    assert not any((target / "renders").iterdir())
    assert image.is_file()
    assert narration.is_file()
    assert not raw.exists()
    assert not (target / "assets" / "audio" / "background.mp3").exists()
    cleanup = json.loads(
        (target / "artifacts" / "local_storage_cleanup_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert cleanup["deleted"]


def test_stage_remotion_retimes_scenes_to_caption_semantic_boundaries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    music = tmp_path / "central-music.mp3"
    music.write_bytes(b"central-music")
    config["music_source"] = str(music)
    projects = tmp_path / "projects"
    workflow.prepare_episode(config, series_profile(), projects_dir=projects)
    target = projects / config["project_id"]
    (target / "assets" / "images" / "article" / "C01.png").write_bytes(b"cover")
    (target / "assets" / "video" / "article" / "W01.mp4").write_bytes(b"wan")
    (target / "assets" / "audio" / "narration.wav").write_bytes(b"narration")
    captions = {
        "segments": [
            {"start": 0.0, "end": 1.8, "text": "第一句"},
            {"start": 1.86, "end": 4.3, "text": "第二句"},
            {"start": 4.36, "end": 6.9, "text": "第三句"},
            {"start": 6.96, "end": 9.7, "text": "开场语义落下"},
            {"start": 9.76, "end": 13.9, "text": "进入下一层"},
            {"start": 13.96, "end": 18.2, "text": "新的视觉段落"},
            {"start": 18.26, "end": 24.0, "text": "结尾"},
        ]
    }
    captions_path = target / "artifacts" / "exact_captions.json"
    captions_path.write_text(json.dumps(captions, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(workflow, "media_duration_seconds", lambda _path: 24.0)

    staged = workflow.stage_remotion(config, series_profile(), projects_dir=projects)
    props = json.loads(Path(staged["props"]).read_text(encoding="utf-8"))

    assert props["timelinePolicy"]["scene_timing"] == "caption_boundaries"
    assert props["scenes"][0]["from"] == 0.0
    assert props["scenes"][0]["to"] == 9.7
    assert props["scenes"][0]["caption_range"]["start_index"] == 0
    assert "开场语义落下" in props["scenes"][0]["script_excerpt"]
    assert props["scenes"][-1]["to"] == props["durationSeconds"]


def test_stage_remotion_requires_background_music(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    make_source(source)
    config = episode_config(source)
    config["music_source"] = ""
    series = series_profile()
    series["music"]["library_dir"] = str(tmp_path / "empty-music")
    projects = tmp_path / "projects"
    workflow.prepare_episode(config, series, projects_dir=projects)
    target = projects / config["project_id"]
    (target / "assets" / "images" / "article" / "C01.png").write_bytes(b"cover")
    (target / "assets" / "video" / "article" / "W01.mp4").write_bytes(b"wan")
    (target / "assets" / "audio" / "narration.wav").write_bytes(b"narration")

    try:
        workflow.stage_remotion(config, series, projects_dir=projects)
    except FileNotFoundError as exc:
        assert "requires background music" in str(exc)
    else:
        raise AssertionError("stage_remotion should refuse to render without background music")
