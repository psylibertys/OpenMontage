"""Contracts for the StudioBinder Skill Hub adapter.

OpenMontage consumes the governed skills through the host MCP client.  It does
not copy their bodies into this repository and it does not trust free-text
automatic routing for production decisions.
"""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent.parent
ROUTING_PATH = ROOT / "config" / "studiobinder-stage-routing.yaml"
ADAPTER_SKILL = ROOT / "skills" / "meta" / "studiobinder-skill-hub.md"

EXPECTED_SKILLS = {
    "cinematic-intent-system",
    "viewer-attention-relay",
    "visual-motif-arc",
    "character-pressure-map",
    "complex-scene-information",
    "motivated-camera-movement",
    "constraint-driven-rewrite",
    "shotlist-location-loop",
    "production-dependency-recovery",
    "essential-coverage-triage",
    "prepared-improvisation",
    "film-proof-of-concept",
    "subjective-visual-state-map",
    "lens-distance-viewer-position",
    "spatial-motivated-lighting",
    "darkness-information-budget",
    "locked-frame-event-design",
    "simultaneous-channel-attention",
    "narrative-time-scaling",
    "supporting-shot-value-budget",
    "capture-format-benefit-audit",
    "minimum-camera-rig",
    "long-take-value-gate",
    "visual-world-grammar",
    "visual-reference-decomposition",
    "screenplay-observable-interface",
}

EXPECTED_STAGES = {
    "research",
    "proposal",
    "script",
    "scene_plan",
    "assets",
    "edit",
}


def _load_routing() -> dict:
    return yaml.safe_load(ROUTING_PATH.read_text(encoding="utf-8"))


def test_explicit_routing_covers_exact_governed_catalog_once():
    routing = _load_routing()

    assert routing["version"] == "1.0"
    assert routing["mcp_server"] == "treeelf-skill-hub"
    assert routing["selection_mode"] == "explicit_stage_mapping"
    assert routing["automatic_route_enabled"] is False
    assert routing["source_skills_read_only"] is True
    assert routing["max_skills_per_stage"] == 3

    stages = routing["pipelines"]["cinematic"]
    assert set(stages) == EXPECTED_STAGES

    slugs = [entry["slug"] for entries in stages.values() for entry in entries]
    assert len(slugs) == len(set(slugs)), "Each skill needs one canonical primary stage"
    assert set(slugs) == EXPECTED_SKILLS

    for stage, entries in stages.items():
        assert entries, f"{stage} has no StudioBinder candidates"
        for entry in entries:
            assert set(entry) == {"slug", "applicability", "when"}, (
                "Routing config may store identifiers and trigger conditions only; "
                "never copy governed instructions into OpenMontage"
            )
            assert entry["applicability"] in {"core", "conditional"}
            assert entry["when"].strip()


def test_layer2_adapter_enforces_explicit_invoke_and_provenance():
    body = ADAPTER_SKILL.read_text(encoding="utf-8")

    for heading in (
        "## When to Use",
        "## Prerequisites",
        "## Process",
        "## Self-Evaluation",
        "## Common Pitfalls",
    ):
        assert heading in body

    required_tokens = (
        "skills_health",
        "skills_invoke",
        "compose=false",
        "Do not use `skills_route`",
        "openmontage-project-agent",
        "catalog_generation",
        "content_hash",
        "source skills are read-only",
        "config/studiobinder-stage-routing.yaml",
    )
    for token in required_tokens:
        assert token in body


def test_cinematic_stage_directors_reference_adapter_at_decision_stages():
    manifest = yaml.safe_load(
        (ROOT / "pipeline_defs" / "cinematic.yaml").read_text(encoding="utf-8")
    )
    assert "meta/studiobinder-skill-hub" in manifest["required_skills"]

    director_files = {
        "research": "research-director.md",
        "proposal": "proposal-director.md",
        "script": "script-director.md",
        "scene_plan": "scene-director.md",
        "assets": "asset-director.md",
        "edit": "edit-director.md",
    }

    for stage, filename in director_files.items():
        body = (
            ROOT / "skills" / "pipelines" / "cinematic" / filename
        ).read_text(encoding="utf-8")
        assert "meta/studiobinder-skill-hub.md" in body, stage
        assert f"cinematic.{stage}" in body, stage


def test_adapter_is_discoverable_and_knowledge_sources_separate_method_from_evidence():
    index = (ROOT / "skills" / "INDEX.md").read_text(encoding="utf-8")
    assert "StudioBinder Skill Hub" in index
    assert "meta/studiobinder-skill-hub.md" in index

    guide = (ROOT / "AGENT_GUIDE.md").read_text(encoding="utf-8")
    assert "studiobinder-skill-hub.md" in guide
    assert "explicit stage mapping" in guide

    knowledge_map = (
        ROOT / "docs" / "treeelf-knowledge-sources.md"
    ).read_text(encoding="utf-8")
    assert "Skill Hub" in knowledge_map
    assert "方法与决策框架" in knowledge_map
    assert "案例、证据和时间码" in knowledge_map
    assert "不复制" in knowledge_map
