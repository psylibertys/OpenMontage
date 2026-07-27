from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from tools.base_tool import ToolResult

import scripts.zh_philosophy_video_workflow as workflow_module


def make_config() -> dict:
    return {
        "project_id": "edge-workflow-test",
        "title": "测试",
        "tts": {
            "provider": "edge",
            "version": "7.2.7",
            "voice": "zh-CN-XiaoxiaoNeural",
            "rate": "+0%",
            "pitch": "+0Hz",
            "volume": "+0%",
            "generation_mode": "single_pass",
        },
        "sections": [
            {"id": "s1", "text": "第一句，应该停顿。", "queries": []},
            {"id": "s2", "text": "第二段为什么会这样？", "queries": []},
        ],
    }


def test_edge_input_preserves_original_sections() -> None:
    workflow = workflow_module.ZhPhilosophyVideoWorkflow(make_config())
    script = workflow.build_script()

    assert workflow.full_provider_text(script) == "第一句，应该停顿。\n\n第二段为什么会这样？"
    assert workflow.full_provider_text(script) == script["metadata"]["raw_script"]


def test_cache_fingerprint_includes_voice_rate_and_pitch() -> None:
    config = make_config()
    workflow = workflow_module.ZhPhilosophyVideoWorkflow(config)
    original = workflow.tts_cache_fingerprint("同一份文案")

    config["tts"]["rate"] = "+10%"
    changed_rate = workflow.tts_cache_fingerprint("同一份文案")
    config["tts"]["rate"] = "+0%"
    config["tts"]["pitch"] = "+5Hz"
    changed_pitch = workflow.tts_cache_fingerprint("同一份文案")

    assert len({original, changed_rate, changed_pitch}) == 3


def test_edge_generation_calls_provider_once_and_reuses_valid_cache(tmp_path: Path, monkeypatch) -> None:
    workflow = workflow_module.ZhPhilosophyVideoWorkflow(make_config())
    workflow.project_dir = tmp_path
    workflow.artifacts = tmp_path / "artifacts"
    workflow.audio_dir = tmp_path / "assets" / "audio" / workflow.tts_output_label
    script = workflow.build_script()
    calls: list[str] = []

    def fake_execute(_tool, inputs):
        calls.append(inputs["text"])
        Path(inputs["output_path"]).write_bytes(b"fake-mp3")
        Path(inputs["subtitles_path"]).write_text("1\n00:00:00,000 --> 00:00:00,500\n第一句\n", encoding="utf-8")
        Path(inputs["timings_path"]).write_text(
            json.dumps(
                {
                    "text": inputs["text"],
                    "boundaries": [
                        {"text": "第一句", "start_seconds": 0.1, "end_seconds": 0.5},
                        {"text": "应该停顿", "start_seconds": 0.7, "end_seconds": 1.2},
                        {"text": "第二段", "start_seconds": 1.5, "end_seconds": 1.9},
                        {"text": "为什么会这样", "start_seconds": 2.0, "end_seconds": 2.7},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return ToolResult(success=True, data={"provider_version": "7.2.7"}, cost_usd=0.0)

    def fake_run(cmd, *, capture=False):
        Path(cmd[-1]).write_bytes(b"fake-wav")
        return ""

    monkeypatch.setattr(workflow_module.EdgeTTS, "execute", fake_execute)
    monkeypatch.setattr(workflow_module, "run", fake_run)
    monkeypatch.setattr(workflow_module, "probe_duration", lambda _path: 3.0)

    assets, wav, duration, cost = workflow.generate_tts(script)
    workflow.generate_tts(workflow.build_script())

    assert calls == ["第一句，应该停顿。\n\n第二段为什么会这样？"]
    assert wav.name == "narration_full.wav"
    assert duration == 3.0
    assert cost == 0.0
    assert {asset["id"] for asset in assets} == {"narration-full", "narration-subtitles"}
    assert script["sections"][0]["start_seconds"] == 0.0
    assert script["sections"][0]["end_seconds"] == 1.5
    assert script["sections"][1]["end_seconds"] == 3.0
    assert script["metadata"]["timing_source"] == "edge_tts_word_boundary"


def test_fetch_stock_prefers_shared_library_before_network(tmp_path: Path, monkeypatch) -> None:
    config = make_config()
    config["stock_library"] = {"enabled": True, "min_match_score": 0.3}
    workflow = workflow_module.ZhPhilosophyVideoWorkflow(config)
    workflow.project_dir = tmp_path
    workflow.video_dir = tmp_path / "assets" / "video"

    class FakeLibrary:
        def link_best(self, query, dest, **_kwargs):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b"cached-video")
            return (
                SimpleNamespace(
                    clip_id="pexels_123",
                    source="pexels",
                    license="Pexels License",
                    source_url="https://www.pexels.com/video/example-123/",
                    creator="creator",
                ),
                0.82,
            )

    monkeypatch.setattr(workflow_module, "get_default_cache", lambda: FakeLibrary())
    monkeypatch.setattr(
        workflow_module.PexelsVideo,
        "execute",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network should not be called")),
    )
    monkeypatch.setattr(workflow_module, "probe_duration", lambda _path: 8.0)

    assets = workflow.fetch_stock(
        {
            "scenes": [
                {
                    "id": "scene-s1-b1",
                    "type": "broll",
                    "metadata": {"visual": {"query": "walking on open road sunrise"}},
                }
            ]
        }
    )

    assert len(assets) == 1
    assert assets[0]["source_tool"] == "local_stock_library"
    assert assets[0]["library_status"] == "hit"
    assert assets[0]["library_clip_id"] == "pexels_123"


def test_portrait_cover_title_layout_fits_long_title() -> None:
    config = make_config()
    config["profile"] = "tiktok"
    config["style"] = {"cover_font_size": 260}
    workflow = workflow_module.ZhPhilosophyVideoWorkflow(config)
    draw = ImageDraw.Draw(Image.new("RGB", (workflow.width, workflow.height)))
    initial_size = int(config["style"]["cover_font_size"] * 0.82)
    max_width = int(workflow.width * 0.78)
    max_height = int(workflow.height * 0.56)

    font, _gap, lines, _line_heights, total_h = workflow.fit_title_layout(
        draw,
        ["切换任务后，大脑没有立刻跟上"],
        workflow.cover_font_path,
        initial_size,
        max_width,
        max_height,
        42,
        min_size=82,
    )

    assert font.size < config["style"]["cover_font_size"]
    assert total_h <= max_height
    assert "".join(lines) == "切换任务后，大脑没有立刻跟上"
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        assert box[2] - box[0] <= max_width


def test_landscape_cover_title_keeps_large_readable_scale() -> None:
    config = make_config()
    config["profile"] = "youtube_landscape"
    config["style"] = {"cover_font_size": 260}
    workflow = workflow_module.ZhPhilosophyVideoWorkflow(config)
    draw = ImageDraw.Draw(Image.new("RGB", (workflow.width, workflow.height)))
    initial_size = int(config["style"]["cover_font_size"] * 0.98)

    font, _gap, lines, _line_heights, total_h = workflow.fit_title_layout(
        draw,
        ["切换任务后，大脑没有立刻跟上"],
        workflow.cover_font_path,
        initial_size,
        int(workflow.width * 0.82),
        int(workflow.height * 0.58),
        34,
        min_size=96,
    )

    assert font.size >= 210
    assert total_h <= int(workflow.height * 0.58)
    assert "".join(lines) == "切换任务后，大脑没有立刻跟上"
