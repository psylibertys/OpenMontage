from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_persistent_hook_is_full_opacity_on_frame_zero() -> None:
    source = (ROOT / "remotion-composer" / "src" / "TalkingHead.tsx").read_text(encoding="utf-8")
    assert "instant?: boolean" in source
    assert '<HookTitle text={hookTitle} instant />' in source
    assert "const enter = instant" in source
