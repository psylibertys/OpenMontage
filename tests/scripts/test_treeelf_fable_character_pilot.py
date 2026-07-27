from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.treeelf_fable_character_pilot import (
    DEFAULT_CONFIG,
    candidate_prompt,
    load_json,
    prepare_project,
    select_candidate,
    status_report,
    validate_config,
    visual_style_markdown,
)


def test_reviewed_fable_character_config_is_valid() -> None:
    config = load_json(DEFAULT_CONFIG)

    assert validate_config(config) == []
    assert [item["id"] for item in config["candidate_selection"]["candidates"]] == [
        "A01",
        "A02",
        "A03",
    ]
    assert "女性" in config["character_bible"]["identity"]
    assert config["gpu_policy"]["automatic_follow_on_generation"] is False
    assert config["gpu_policy"]["lora_allowed"] is False


def test_candidate_prompts_share_comparison_conditions_but_keep_distinct_identity() -> None:
    config = load_json(DEFAULT_CONFIG)
    prompts = [candidate_prompt(config, item) for item in config["candidate_selection"]["candidates"]]

    assert len(set(prompts)) == 3
    assert all(config["candidate_selection"]["shared_prompt"] in prompt for prompt in prompts)
    assert all("short" in prompt.lower() and "curly" in prompt.lower() for prompt in prompts)
    assert all("woman" in prompt.lower() for prompt in prompts)


def test_visual_style_explicitly_excludes_tired_look() -> None:
    style = visual_style_markdown(load_json(DEFAULT_CONFIG))

    assert "柔和" in style
    assert "乐观" in style
    assert "under-eye shadows" in style
    assert 'aspect_ratio: "9:16"' in style
    assert 'render_runtime: "remotion"' in style


def test_prepare_writes_cpu_artifacts_and_three_source_snapshots(tmp_path: Path) -> None:
    config = load_json(DEFAULT_CONFIG)
    sources = []
    for index in range(3):
        source = tmp_path / f"source-{index}.md"
        source.write_text(f"---\ntype: 旁白寓言\n---\n# 测试{index}\n\n正文", encoding="utf-8")
        sources.append(str(source))
    config["source_scripts"] = sources
    config["project_id"] = "fable-character-test"
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"project_id": config["project_id"]}), encoding="utf-8")
    config["retention_policy"] = str(policy)

    result = prepare_project(config, projects_dir=tmp_path / "projects")
    project = Path(result["project_dir"])

    assert result["cpu_preparation_complete"] is True
    assert len(list((project / "artifacts" / "source_scripts").glob("*.md"))) == 3
    assert (project / "artifacts" / "character_bible.json").is_file()
    assert (project / "artifacts" / "visual-style.md").is_file()
    tasks = json.loads((project / "artifacts" / "gpu_task_plan.json").read_text(encoding="utf-8"))
    assert len(tasks["phase_one"]) == 3
    assert tasks["automatic_follow_on_generation"] is False
    checkpoint = json.loads((project / "checkpoint_proposal.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "completed"
    assert checkpoint["human_approved"] is True


def test_selection_requires_generated_candidate_file(tmp_path: Path) -> None:
    config = load_json(DEFAULT_CONFIG)
    config["project_id"] = "fable-character-select-test"

    with pytest.raises(FileNotFoundError):
        select_candidate(config, "A01", projects_dir=tmp_path / "projects")


def test_status_reports_cpu_ready_without_gpu_assets(tmp_path: Path) -> None:
    config = load_json(DEFAULT_CONFIG)
    config["project_id"] = "fable-character-status-test"
    target = tmp_path / "projects" / config["project_id"]
    (target / "artifacts").mkdir(parents=True)
    (target / "project.json").write_text("{}", encoding="utf-8")
    (target / "artifacts" / "gpu_task_plan.json").write_text("{}", encoding="utf-8")

    status = status_report(config, projects_dir=tmp_path / "projects")

    assert status["prepared"] is True
    assert status["cpu_preparation_complete"] is True
    assert status["candidate_count"] == 0
    assert status["follow_on_generation_blocked"] is True
