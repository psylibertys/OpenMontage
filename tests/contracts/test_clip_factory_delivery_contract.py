from __future__ import annotations

from pathlib import Path

from lib.pipeline_loader import load_pipeline_readonly
from schemas.artifacts import list_schemas


ROOT = Path(__file__).resolve().parents[2]


def test_clip_factory_requires_hard_delivery_audit_before_publish() -> None:
    pipeline = load_pipeline_readonly("clip-factory")
    compose = next(stage for stage in pipeline["stages"] if stage["name"] == "compose")
    publish = next(stage for stage in pipeline["stages"] if stage["name"] == "publish")

    assert "clip_delivery_audit" in compose["required_tools"]
    assert "clip_delivery_audit" in compose["produces"]
    assert "clip_delivery_audit" in publish["required_artifacts_in"]
    assert "clip_delivery_audit" in list_schemas()


def test_clip_factory_skills_name_exact_frame_and_final_mp4_gates() -> None:
    compose = (ROOT / "skills/pipelines/clip-factory/compose-director.md").read_text(
        encoding="utf-8"
    )
    assets = (ROOT / "skills/pipelines/clip-factory/asset-director.md").read_text(
        encoding="utf-8"
    )
    publish = (ROOT / "skills/pipelines/clip-factory/publish-director.md").read_text(
        encoding="utf-8"
    )

    assert "frame `n=0`" in compose
    assert "final MP4" in compose
    assert "p90 absolute start-time error `<= 0.30s`" in compose
    assert "one canonical media-time mapping" in assets
    assert "clip_delivery_audit.status" in publish
