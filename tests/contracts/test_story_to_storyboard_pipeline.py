"""Contract tests for the story-to-storyboard pipeline."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.pipeline_loader import (  # noqa: E402
    get_required_tools,
    get_stage_order,
    get_stage_sub_stages,
    load_pipeline,
)
from lib.storyboard_export import (  # noqa: E402
    StoryboardExportError,
    build_narration_all,
    check_traceability,
    lint_storyboard,
    validate_storyboard_export,
)
from schemas.artifacts import ARTIFACT_NAMES, validate_artifact  # noqa: E402


# ---------------------------------------------------------------------------
# Manifest contract
# ---------------------------------------------------------------------------


def test_story_to_storyboard_manifest_contract():
    manifest = load_pipeline("story-to-storyboard")

    assert manifest["name"] == "story-to-storyboard"
    assert manifest["stability"] == "beta"
    assert get_stage_order(manifest) == [
        "story_intake",
        "script",
        "scene_plan",
        "storyboard_export",
    ]

    # All four stages gate on human approval — the gates ARE the product.
    for stage in manifest["stages"]:
        assert stage["human_approval_default"] is True, stage["name"]

    # Reverse-mode sub-stage activates only when an analysis brief exists.
    sub_stages = get_stage_sub_stages(manifest, "story_intake")
    assert [s["name"] for s in sub_stages] == ["reference_reverse"]
    assert sub_stages[0]["condition"] == "video_analysis_brief_exists"
    active = get_stage_sub_stages(
        manifest,
        "story_intake",
        context={"video_analysis_brief_exists": False},
        include_inactive=False,
    )
    assert active == []
    active_on = get_stage_sub_stages(
        manifest,
        "story_intake",
        context={"video_analysis_brief_exists": True},
        include_inactive=False,
    )
    assert [s["name"] for s in active_on] == ["reference_reverse"]

    # Local analysis stack is reachable via reference_input.
    assert {
        "video_analyzer",
        "transcript_fetcher",
        "scene_detect",
        "frame_sampler",
    }.issubset(get_required_tools(manifest))

    # Producer/consumer wiring between stages.
    by_name = {s["name"]: s for s in manifest["stages"]}
    assert "story_brief" in by_name["story_intake"]["produces"]
    assert by_name["script"]["required_artifacts_in"] == ["story_brief"]
    assert by_name["scene_plan"]["required_artifacts_in"] == ["script"]
    assert by_name["storyboard_export"]["required_artifacts_in"] == ["scene_plan"]


def test_story_artifacts_are_registered():
    assert {"story_brief", "storyboard_export"}.issubset(set(ARTIFACT_NAMES))


def test_studiobinder_routing_has_story_section():
    import yaml

    routing = yaml.safe_load(
        (PROJECT_ROOT / "config" / "studiobinder-stage-routing.yaml").read_text(
            encoding="utf-8"
        )
    )
    section = routing["pipelines"]["story-to-storyboard"]
    assert set(section.keys()) == {"story_intake", "script", "scene_plan"}
    for stage, entries in section.items():
        assert 1 <= len(entries) <= routing["max_skills_per_stage"]
        for entry in entries:
            assert entry["applicability"] in {"core", "conditional"}


# ---------------------------------------------------------------------------
# Script schema additive extension
# ---------------------------------------------------------------------------


def test_script_schema_still_accepts_legacy_artifacts():
    """Pre-extension scripts (no beat_map/visual_intent/emotion) must validate."""
    legacy = {
        "version": "1.0",
        "title": "Legacy Explainer",
        "total_duration_seconds": 60,
        "sections": [
            {
                "id": "sec-1",
                "text": "Opening narration.",
                "start_seconds": 0,
                "end_seconds": 12,
            }
        ],
    }
    validate_artifact("script", legacy)


def test_script_schema_accepts_additive_story_fields():
    extended = {
        "version": "1.0",
        "title": "小狐狸与灯",
        "total_duration_seconds": 45,
        "beat_map": [
            {
                "beat_id": "beat-1",
                "label": "hook",
                "start_seconds": 0,
                "end_seconds": 8,
                "section_ids": ["sec-1"],
                "narrative_function": "establish_context",
            },
            {
                "beat_id": "beat-2",
                "label": "turn",
                "start_seconds": 8,
                "end_seconds": 30,
                "section_ids": ["sec-2", "sec-3"],
                "narrative_function": "build_tension",
            },
        ],
        "sections": [
            {
                "id": "sec-1",
                "text": "夜色里，一盏灯亮着。",
                "start_seconds": 0,
                "end_seconds": 8,
                "visual_intent": "A tiny fox curls beside a paper lantern at the forest edge.",
                "emotion": "quiet, warm stillness",
                "character_dialogue": [
                    {
                        "character_id": "fox_lead",
                        "line": "还有人回来吗？",
                        "delivery_note": "hushed, hopeful",
                    }
                ],
            },
            {
                "id": "sec-2",
                "text": "风把灯吹灭了。",
                "start_seconds": 8,
                "end_seconds": 18,
                "visual_intent": "The lantern gutters out; the fox's ears prick toward the dark.",
                "emotion": "quiet unease building to dread",
            },
            {
                "id": "sec-3",
                "text": "它决定去找光。",
                "start_seconds": 18,
                "end_seconds": 30,
                "visual_intent": "The fox steps into the mist, tail low, moving toward a distant glow.",
                "emotion": "resolve forming",
            },
        ],
    }
    validate_artifact("script", extended)


# ---------------------------------------------------------------------------
# story_brief fixture
# ---------------------------------------------------------------------------


def make_story_brief():
    return {
        "version": "1.0",
        "title": "小狐狸与灯",
        "source": {
            "mode": "fable_draft",
            "document_path": "/Users/treeelf/Desktop/Psynaut/treeElfNotes/07产出/小故事/小狐狸与灯/故事蓝图.md",
            "snapshot_path": "projects/fable-fox-lamp/artifacts/story_source_snapshot.md",
        },
        "premise": "一只守灯的小狐狸必须在灯灭之后穿越迷雾，为自己找到光。",
        "theme": "守候与主动寻找的转换",
        "characters": [
            {
                "id": "fox_lead",
                "name": "小狐狸",
                "role": "protagonist",
                "description": "守灯的小狐狸，胆小但心软",
                "appearance": "small orange fox, white chest, one notched left ear, bushy tail",
                "arc_notes": "from waiting to seeking",
            }
        ],
        "emotional_arc": [
            {"phase": "hook", "feeling": "warm stillness"},
            {"phase": "build", "feeling": "unease"},
            {"phase": "turn", "feeling": "resolve"},
            {"phase": "landing", "feeling": "quiet joy"},
        ],
        "structure": {
            "hook": "深夜亮着的一盏灯",
            "turning_points": ["灯被风吹灭", "决定出发"],
            "landing": "小狐狸举着自己找到的光走回森林",
        },
        "target_duration_seconds": 45,
        "tone": "温柔的寓言",
        "fable_extension": {
            "moral": "等来的光会灭，找来的光不会",
            "protagonist_type": "single-animal fable",
            "art_style": "soft storybook watercolor",
        },
        "metadata": {},
    }


def test_story_brief_fixture_validates():
    validate_artifact("story_brief", make_story_brief())


def test_story_brief_reference_mode_validates():
    brief = make_story_brief()
    brief["source"] = {
        "mode": "reference_video",
        "reference_video_url": "https://example.com/watch?v=abc",
        "video_analysis_brief_path": "projects/ref-1/artifacts/video_analysis_brief.json",
    }
    validate_artifact("story_brief", brief)


# ---------------------------------------------------------------------------
# scene_plan / storyboard_export golden fixtures
# ---------------------------------------------------------------------------


def make_scene_plan():
    return {
        "version": "1.0",
        "scenes": [
            {
                "id": "scene-1",
                "type": "generated",
                "description": "A small orange fox with a notched left ear curls beside a glowing paper lantern at the misty forest edge, warm stillness.",
                "start_seconds": 0,
                "end_seconds": 4,
                "script_section_id": "sec-1",
                "shot_language": {
                    "shot_size": "medium_close",
                    "camera_movement": "static",
                    "lighting_key": "rim_lit",
                    "depth_of_field": "shallow",
                    "color_temperature": "warm",
                },
                "shot_intent": "Establish the守灯 intimacy before the loss",
                "narrative_role": "establish_context",
                "hero_moment": False,
            },
            {
                "id": "scene-2",
                "type": "generated",
                "description": "Wind snuffs the lantern; the same fox's ears prick toward sudden darkness, unease rising.",
                "start_seconds": 4,
                "end_seconds": 8.5,
                "script_section_id": "sec-2",
                "shot_language": {
                    "shot_size": "close_up",
                    "camera_movement": "slow_push_placeholder",
                    "lighting_key": "silhouette",
                    "depth_of_field": "shallow",
                    "color_temperature": "cool",
                },
                "shot_intent": "The loss lands physically on the fox's face",
                "narrative_role": "build_tension",
                "hero_moment": True,
            },
        ],
        "metadata": {},
    }


def make_storyboard():
    narration_1 = "夜色里，一盏灯亮着，小狐狸守在旁边。"
    narration_2 = "风把灯吹灭了<#0.4#>它竖起耳朵。"
    narration_3 = "它决定，去找光。"
    return {
        "version": "1.0",
        "video_title": "小狐狸与灯",
        "video_theme": "fox-and-lantern",
        "speech_model": "speech-2.8-hd",
        "narration_all": "\n".join([narration_1, narration_2, narration_3]),
        "scenes": [
            {
                "scene_id": 1,
                "scene_plan_scene_id": "scene-1",
                "emotion": "calm",
                "narration": narration_1,
                "t2i_prompt": (
                    "cinematic photo of a small orange fox with a notched left ear "
                    "curled beside a glowing paper lantern at the misty forest edge, "
                    "cinematic teal and orange, golden hour, shot on Contax 645, "
                    "indie film look, cinematic composition, storytelling image, "
                    "8k, highly detailed"
                ),
                "i2v_prompt": (
                    "Based on the provided image, the same character and same scene "
                    "remain consistent, the fox slowly breathes, then gently flicks "
                    "its notched ear, camera performs a slow push-in, smooth and "
                    "cinematic, soft volumetric light, highly detailed, realistic "
                    "motion, natural physics, no distortion, no morphing"
                ),
                "duration_seconds": 4,
            },
            {
                "scene_id": 2,
                "scene_plan_scene_id": "scene-2",
                "emotion": "fearful",
                "narration": narration_2,
                "t2i_prompt": (
                    "cinematic photo of the same small orange fox with a notched "
                    "left ear frozen as the paper lantern gutters out into darkness, "
                    "deep shadows, blue hour, shot on Kodak Portra 400, melancholic "
                    "palette, cinematic composition, 8k, highly detailed"
                ),
                "i2v_prompt": (
                    "Based on the provided image, the same character remains "
                    "consistent, the lantern flame slowly dies, then the fox gently "
                    "pricks its ears toward the dark, slight camera drift, smooth "
                    "and cinematic, moody lighting, 4k, realistic motion, "
                    "no morphing"
                ),
                "duration_seconds": 4.5,
            },
            {
                "scene_id": 3,
                "scene_plan_scene_id": "scene-2",
                "emotion": "surprised",
                "narration": narration_3,
                "t2i_prompt": (
                    "cinematic photo of the same small orange fox stepping into "
                    "drifting mist toward a faint distant glow, tail low but sure, "
                    "atmospheric haze, god rays, shot on Panasonic GH5, cinematic "
                    "ethereal, immersive, 8k, highly detailed"
                ),
                "i2v_prompt": (
                    "Based on the provided image, the same character and same "
                    "composition remain consistent, the fox slowly steps forward, "
                    "then slightly lifts its gaze, camera performs a cinematic "
                    "orbit, smooth and cinematic, ethereal glow, 4k, realistic "
                    "motion, natural physics, consistent structure"
                ),
                "duration_seconds": 2.5,
            },
        ],
        "metadata": {"absorbed_from": "copy-to-storyboard-json (2026-10 snapshot)"},
    }


def test_scene_plan_fixture_validates():
    plan = make_scene_plan()
    # camera_movement uses a placeholder that must be a real enum value
    plan["scenes"][1]["shot_language"]["camera_movement"] = "dolly_in"
    validate_artifact("scene_plan", plan)


def test_storyboard_export_fixture_validates_and_lints():
    storyboard = make_storyboard()
    validate_storyboard_export(storyboard)  # schema + lint, must not raise
    assert build_narration_all(storyboard) == storyboard["narration_all"]


def test_traceability_clean_and_broken():
    storyboard = make_storyboard()
    scene_plan = make_scene_plan()
    assert check_traceability(storyboard, scene_plan) == []

    # Shot pointing at a nonexistent scene.
    broken = json.loads(json.dumps(storyboard))
    broken["scenes"][0]["scene_plan_scene_id"] = "scene-99"
    assert check_traceability(broken, scene_plan)

    # Uncovered scene_plan scene.
    uncovered = json.loads(json.dumps(scene_plan))
    uncovered["scenes"].append(
        {
            "id": "scene-3",
            "type": "generated",
            "description": "Landing scene.",
            "start_seconds": 8.5,
            "end_seconds": 11,
        }
    )
    assert check_traceability(storyboard, uncovered)


# ---------------------------------------------------------------------------
# Lint rule unit tests (rules absorbed from copy-to-storyboard-json)
# ---------------------------------------------------------------------------


def mutate(storyboard, index, **fields):
    data = json.loads(json.dumps(storyboard))
    for key, value in fields.items():
        if value is None:
            data["scenes"][index].pop(key, None)
        else:
            data["scenes"][index][key] = value
    return data


@pytest.mark.parametrize(
    "mutation",
    [
        # forbidden chars in t2i prompt
        lambda sb: mutate(sb, 0, t2i_prompt="cinematic photo of: a fox, 8k, highly detailed"),
        # multi-line prompt (not a single sentence)
        lambda sb: mutate(sb, 0, t2i_prompt="line one\nline two"),
        # i2v missing physics anchor
        lambda sb: mutate(
            sb, 0,
            i2v_prompt="Based on the provided image, the fox slowly turns, camera performs a slow push-in",
        ),
        # i2v missing camera anchor
        lambda sb: mutate(
            sb, 0,
            i2v_prompt="Based on the provided image, the fox slowly turns, realistic motion, no morphing",
        ),
        # i2v missing alignment anchor
        lambda sb: mutate(
            sb, 0,
            i2v_prompt="The fox slowly turns, camera performs a slow push-in, realistic motion",
        ),
        # i2v missing action anchor
        lambda sb: mutate(
            sb, 0,
            i2v_prompt="Based on the provided image, camera performs a slow push-in, realistic motion, no morphing",
        ),
        # pause marker at start
        lambda sb: mutate(sb, 1, narration="<#0.5#>风把灯吹灭了"),
        # consecutive pause markers
        lambda sb: mutate(sb, 1, narration="风把灯吹灭了<#0.5#><#0.3#>它竖起耳朵"),
        # pause out of range
        lambda sb: mutate(sb, 1, narration="风把灯吹灭了<#120#>它竖起耳朵"),
        # unsupported emotion
        lambda sb: mutate(sb, 0, emotion="wistful"),
        # emotion/narration line mismatch
        lambda sb: mutate(sb, 1, emotion="fearful\nsurprised"),
        # duration over cap
        lambda sb: mutate(sb, 0, duration_seconds=5.5),
        # duration at zero
        lambda sb: mutate(sb, 0, duration_seconds=0),
        # scene_id not sequential
        lambda sb: mutate(sb, 2, scene_id=9),
        # vocal tag on unsupported speech model
        lambda sb: mutate(sb, 0, narration="夜色里，一盏灯亮着(laughs)，小狐狸守在旁边。"),
        # narration_all drift
        lambda sb: {**sb, "narration_all": "tampered"},
    ],
    ids=[
        "t2i-forbidden-char",
        "t2i-multiline",
        "i2v-no-physics",
        "i2v-no-camera",
        "i2v-no-alignment",
        "i2v-no-action",
        "pause-at-start",
        "pause-consecutive",
        "pause-out-of-range",
        "emotion-unsupported",
        "emotion-line-mismatch",
        "duration-over-cap",
        "duration-zero",
        "scene-id-gap",
        "vocal-tag-unsupported-model",
        "narration-all-drift",
    ],
)
def test_lint_rejects_rule_violations(mutation):
    storyboard = mutation(make_storyboard())
    errors = lint_storyboard(storyboard)
    assert errors, "expected lint errors for this mutation"


def test_vocal_tags_allowed_on_supported_speech_model():
    storyboard = make_storyboard()
    narration = "夜色里，一盏灯亮着(laughs)，小狐狸守在旁边。"
    storyboard["scenes"][0]["narration"] = narration
    storyboard["narration_all"] = build_narration_all(storyboard)
    # speech_model is speech-2.8-hd in the fixture — vocal tags allowed
    assert lint_storyboard(storyboard) == []


def test_lint_max_shot_seconds_can_tighten_not_loosen():
    storyboard = make_storyboard()  # has a 4.5s shot
    assert lint_storyboard(storyboard, max_shot_seconds=4.0)
    with pytest.raises(ValueError):
        lint_storyboard(storyboard, max_shot_seconds=6.0)


def test_validate_storyboard_export_raises_with_all_errors():
    # Schema violations are wrapped into StoryboardExportError too
    storyboard = mutate(make_storyboard(), 0, duration_seconds=7)
    with pytest.raises(StoryboardExportError) as excinfo:
        validate_storyboard_export(storyboard)
    assert "schema" in str(excinfo.value)

    # Within-schema values reach the lint layer, which aggregates every error
    storyboard = mutate(
        make_storyboard(), 0, t2i_prompt="bad: prompt", duration_seconds=5.0
    )
    storyboard["scenes"][0]["duration_seconds"] = 5.0  # schema-legal
    with pytest.raises(StoryboardExportError) as excinfo:
        validate_storyboard_export(storyboard)
    message = str(excinfo.value)
    assert "':'" in message


# ---------------------------------------------------------------------------
# Export CLI golden test
# ---------------------------------------------------------------------------


def test_export_cli_writes_validated_deliverable(tmp_path):
    artifacts = tmp_path / "projects" / "fable-fox-lamp" / "artifacts"
    artifacts.mkdir(parents=True)
    storyboard = make_storyboard()
    scene_plan = make_scene_plan()
    scene_plan["scenes"][1]["shot_language"]["camera_movement"] = "dolly_in"
    (artifacts / "storyboard_export.json").write_text(
        json.dumps(storyboard, ensure_ascii=False), encoding="utf-8"
    )
    (artifacts / "scene_plan.json").write_text(
        json.dumps(scene_plan, ensure_ascii=False), encoding="utf-8"
    )

    out_dir = tmp_path / "exports"
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "export_storyboard_json.py"),
            str(artifacts / "storyboard_export.json"),
            "--scene-plan", str(artifacts / "scene_plan.json"),
            "--output-dir", str(out_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    exported_path = out_dir / "fox-and-lantern" / "fox-and-lantern.json"
    assert exported_path.exists()
    exported = json.loads(exported_path.read_text(encoding="utf-8"))
    assert len(exported["scenes"]) == 3
    assert exported["metadata"]["absorbed_from"].startswith("copy-to-storyboard-json")
    assert exported["metadata"]["max_shot_seconds"] == 5.0
    # The exported file IS the validated artifact — scenes unchanged
    assert exported["scenes"] == storyboard["scenes"]


def test_export_cli_fails_on_lint_violation(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)
    bad = mutate(make_storyboard(), 0, duration_seconds=6)
    bad_path = artifacts / "storyboard_export.json"
    bad_path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "export_storyboard_json.py"),
            str(bad_path),
            "--output-dir", str(tmp_path / "exports"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "cannot exceed" in result.stderr


# ---------------------------------------------------------------------------
# Brief-to-beat bridge mapping consistency
# (the skill is the authority; these tests keep its tables aligned with schemas)
# ---------------------------------------------------------------------------

VISUAL_TYPE_MAP = {
    "talking_head": "talking_head",
    "b_roll": "broll",
    "screen_recording": "screen_recording",
    "animation": "animation",
    "text_card": "text_card",
    "stock_footage": "generated",
    "diagram": "diagram",
    "chart": "diagram",
    "product_shot": "generated",
    "transition": "transition",
    "other": "generated",
}

ENERGY_ROLE_MAP = {
    # (energy, position) -> narrative_role
    ("low", "first"): "establish_context",
    ("low", "middle"): "transition",
    ("low", "last"): "resolution",
    ("medium", "first"): "introduce_subject",
    ("medium", "middle"): "build_tension",
    ("medium", "last"): "resolution",
    ("high", "first"): "introduce_subject",
    ("high", "middle"): "deliver_payload",
    ("high", "last"): "call_to_action",
    ("peak", "first"): "deliver_payload",
    ("peak", "middle"): "emotional_beat",
    ("peak", "last"): "call_to_action",
}


def _schema_enum(schema_name, pointer):
    schema = json.loads(
        (PROJECT_ROOT / "schemas" / "artifacts" / f"{schema_name}.schema.json").read_text(
            encoding="utf-8"
        )
    )
    node = schema
    for key in pointer:
        node = node[key]
    return set(node["enum"])


def test_bridge_visual_type_map_covers_analysis_enum_and_stays_in_scene_plan():
    analysis_enum = _schema_enum(
        "video_analysis_brief",
        ["properties", "structure_analysis", "properties", "scenes", "items", "properties", "visual_type"],
    )
    scene_enum = _schema_enum(
        "scene_plan", ["properties", "scenes", "items", "properties", "type"]
    )
    assert set(VISUAL_TYPE_MAP.keys()) == analysis_enum, (
        "bridge table must cover every analysis visual_type (update "
        "skills/meta/brief-to-beat-bridge.md §2.1 when the schema enum changes)"
    )
    assert set(VISUAL_TYPE_MAP.values()) <= scene_enum


def test_bridge_energy_role_map_stays_in_narrative_role_enum():
    role_enum = _schema_enum(
        "scene_plan", ["properties", "scenes", "items", "properties", "narrative_role"]
    )
    assert set(ENERGY_ROLE_MAP.values()) <= role_enum


def test_bridge_energy_enum_matches_analysis_schema():
    energy_enum = _schema_enum(
        "video_analysis_brief",
        ["properties", "structure_analysis", "properties", "scenes", "items", "properties", "energy_level"],
    )
    assert {energy for energy, _ in ENERGY_ROLE_MAP} == energy_enum


def test_bridge_pacing_styles_match_analysis_schema():
    pacing_enum = _schema_enum(
        "video_analysis_brief",
        ["properties", "structure_analysis", "properties", "pacing_profile", "properties", "pacing_style"],
    )
    # avg-shot defaults per pacing style defined in the bridge skill §3
    bridge_defaults = {
        "slow_contemplative": 4.5,
        "steady_educational": 4.0,
        "dynamic_social": 3.0,
        "rapid_fire": 2.0,
        "variable": None,  # clamp(avg_scene_duration_seconds, 1.5, 5)
    }
    assert set(bridge_defaults.keys()) == pacing_enum
    for value in bridge_defaults.values():
        if value is not None:
            assert 0 < value <= 5
