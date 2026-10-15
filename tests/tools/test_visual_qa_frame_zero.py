from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tools.analysis.visual_qa import VisualQA


def test_default_visual_review_extracts_exact_frame_zero_and_one_second(
    tmp_path: Path, monkeypatch
) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"mp4")
    tool = VisualQA()
    monkeypatch.setattr(tool, "_get_duration", lambda _path: 20.0)

    def fake_run(command, **_kwargs):
        Path(command[-1]).write_bytes(b"jpg")
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(tool, "run_command", fake_run)
    result = tool.execute(
        {"operation": "review", "input_path": str(video), "output_dir": str(tmp_path / "frames")}
    )

    assert result.success
    timestamps = [item["timestamp"] for item in result.data["frames"]]
    assert timestamps[:2] == [0.0, 1.0]
    assert (tmp_path / "frames" / "frame_0_0s.jpg").is_file()
