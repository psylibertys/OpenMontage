from pathlib import Path
from types import SimpleNamespace

from tools.audio.audio_mixer import AudioMixer


def test_track_filters_add_mute_windows():
    filters = AudioMixer()._track_filters({
        "path": "speech.wav",
        "role": "speech",
        "mute_segments": [
            {"start": 1.2, "end": 1.6},
            {"start": 3, "end": 3.4},
        ],
    })
    assert "volume=0:enable='between(t,1.2,1.6)'" in filters
    assert "volume=0:enable='between(t,3.0,3.4)'" in filters


def test_extract_honors_sample_rate_and_channels(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.touch()
    output = tmp_path / "audio.wav"
    captured = []

    def fake_run(self, cmd, **kwargs):
        captured.append(cmd)
        output.touch()
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(AudioMixer, "run_command", fake_run)
    result = AudioMixer().execute({
        "operation": "extract",
        "input_path": str(source),
        "output_path": str(output),
        "sample_rate": 48000,
        "channels": 1,
    })
    assert result.success
    assert captured[0][captured[0].index("-ar") + 1] == "48000"
    assert captured[0][captured[0].index("-ac") + 1] == "1"
    assert result.data["sample_rate"] == 48000

