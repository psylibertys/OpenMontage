---
name: speech-to-text
description: Transcribe audio/video with local Qwen3-ASR + ForcedAligner or ElevenLabs Scribe. Use for accurate transcripts, word timestamps, subtitles, and video cutting.
license: MIT
metadata: {"openclaw": {}}
---

# Speech-to-Text

## OpenMontage 默认：本地 Qwen3-ASR + ForcedAligner

涉及视频切片、字幕或逐字时间码时，优先调用注册工具 `transcriber`，并使用 `backend: qwen3-asr`。本机默认模型：

- `/Users/treeelf/AI_Models/Qwen3-ASR-1.7B`
- `/Users/treeelf/AI_Models/Qwen3-ForcedAligner-0.6B`

运行时隔离在 Conda 环境 `qwen3-asr`，依赖由 `requirements-qwen-asr.txt` 固定。输出 JSON 包含 `text`、`segments`、`word_timestamps`、`language` 和 `duration_seconds`，可直接交给字幕与切片阶段。

```python
from tools.analysis.transcriber import Transcriber

result = Transcriber().execute({
    "input_path": "/absolute/path/video.mp4",
    "backend": "qwen3-asr",
    "language": "zh",  # 省略或 auto 时自动识别
    "align_timestamps": True,
    "output_dir": "/absolute/path/transcripts",
})
if not result.success:
    raise RuntimeError(result.error)
```

强制对齐单块上限为 5 分钟；运行器会把长音频切成最多 280 秒的小块后分别对齐并回填全局时间。`backend: auto` 会先尝试 Qwen，再回退 `faster-whisper`；只有明确需要旧模型时才指定 `backend: faster-whisper`。说话人分离仍属于 WhisperX 路径，不应把 Qwen 字级时间戳误当成 speaker diarization。

## 云端可选：ElevenLabs Speech-to-Text

Transcribe audio to text with Scribe v2 - supports 90+ languages, speaker diarization, and word-level timestamps.

> **Setup:** See [Installation Guide](references/installation.md). For JavaScript, use `@elevenlabs/*` packages only.

## Quick Start

### Python

```python
from elevenlabs import ElevenLabs

client = ElevenLabs()

with open("audio.mp3", "rb") as audio_file:
    result = client.speech_to_text.convert(file=audio_file, model_id="scribe_v2")

print(result.text)
```

### JavaScript

```javascript
import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";
import { createReadStream } from "fs";

const client = new ElevenLabsClient();
const result = await client.speechToText.convert({
  file: createReadStream("audio.mp3"),
  modelId: "scribe_v2",
});
console.log(result.text);
```

### cURL

```bash
curl -X POST "https://api.elevenlabs.io/v1/speech-to-text" \
  -H "xi-api-key: $ELEVENLABS_API_KEY" -F "file=@audio.mp3" -F "model_id=scribe_v2"
```

## Models

| Model ID | Description | Best For |
|----------|-------------|----------|
| `scribe_v2` | State-of-the-art accuracy, 90+ languages | Batch transcription, subtitles, long-form audio |
| `scribe_v2_realtime` | Low latency (~150ms) | Live transcription, voice agents |

## Transcription with Timestamps

Word-level timestamps include type classification and speaker identification:

```python
result = client.speech_to_text.convert(
    file=audio_file, model_id="scribe_v2", timestamps_granularity="word"
)

for word in result.words:
    print(f"{word.text}: {word.start}s - {word.end}s (type: {word.type})")

```

## Speaker Diarization

Identify WHO said WHAT - the model labels each word with a speaker ID, useful for meetings, interviews, or any multi-speaker audio:

```python
result = client.speech_to_text.convert(
    file=audio_file,
    model_id="scribe_v2",
    diarize=True
)

for word in result.words:
    print(f"[{word.speaker_id}] {word.text}")
```

## Keyterm Prompting

Help the model recognize specific words it might otherwise mishear - product names, technical jargon, or unusual spellings (up to 100 terms):

```python
result = client.speech_to_text.convert(
    file=audio_file,
    model_id="scribe_v2",
    keyterms=["ElevenLabs", "Scribe", "API"]
)
```

## Language Detection

Automatic detection with optional language hint:

```python
result = client.speech_to_text.convert(
    file=audio_file,
    model_id="scribe_v2",
    language_code="eng"  # ISO 639-1 or ISO 639-3 code
)

print(f"Detected: {result.language_code} ({result.language_probability:.0%})")
```

## Supported Formats

**Audio:** MP3, WAV, M4A, FLAC, OGG, WebM, AAC, AIFF, Opus
**Video:** MP4, AVI, MKV, MOV, WMV, FLV, WebM, MPEG, 3GPP

**Limits:** Up to 3GB file size, 10 hours duration

## Response Format

```json
{
  "text": "The full transcription text",
  "language_code": "eng",
  "language_probability": 0.98,
  "words": [
    {"text": "The", "start": 0.0, "end": 0.15, "type": "word", "speaker_id": "speaker_0"},
    {"text": " ", "start": 0.15, "end": 0.16, "type": "spacing", "speaker_id": "speaker_0"}
  ]
}
```

**Word types:**
- `word` - An actual spoken word
- `spacing` - Whitespace between words (useful for precise timing)
- `audio_event` - Non-speech sounds the model detected (laughter, applause, music, etc.)

## Error Handling

```python
try:
    result = client.speech_to_text.convert(file=audio_file, model_id="scribe_v2")
except Exception as e:
    print(f"Transcription failed: {e}")
```

Common errors:
- **401**: Invalid API key
- **422**: Invalid parameters
- **429**: Rate limit exceeded

## Tracking Costs

Monitor usage via `request-id` response header:

```python
response = client.speech_to_text.convert.with_raw_response(file=audio_file, model_id="scribe_v2")
result = response.parse()
print(f"Request ID: {response.headers.get('request-id')}")
```

## Real-Time Streaming

For live transcription with ultra-low latency (~150ms), use the real-time API. The real-time API produces two types of transcripts:

- **Partial transcripts**: Interim results that update frequently as audio is processed - use these for live feedback (e.g., showing text as the user speaks)
- **Committed transcripts**: Final, stable results after you "commit" - use these as the source of truth for your application

A "commit" tells the model to finalize the current segment. You can commit manually (e.g., when the user pauses) or use Voice Activity Detection (VAD) to auto-commit on silence.

### Python (Server-Side)

```python
import asyncio
from elevenlabs import ElevenLabs

client = ElevenLabs()

async def transcribe_realtime():
    async with client.speech_to_text.realtime.connect(
        model_id="scribe_v2_realtime",
        include_timestamps=True,
    ) as connection:
        await connection.stream_url("https://example.com/audio.mp3")

        async for event in connection:
            if event.type == "partial_transcript":
                print(f"Partial: {event.text}")
            elif event.type == "committed_transcript":
                print(f"Final: {event.text}")

asyncio.run(transcribe_realtime())
```

### JavaScript (Client-Side with React)

```typescript
import { useScribe, CommitStrategy } from "@elevenlabs/react";

function TranscriptionComponent() {
  const [transcript, setTranscript] = useState("");

  const scribe = useScribe({
    modelId: "scribe_v2_realtime",
    commitStrategy: CommitStrategy.VAD, // Auto-commit on silence for mic input
    onPartialTranscript: (data) => console.log("Partial:", data.text),
    onCommittedTranscript: (data) => setTranscript((prev) => prev + data.text),
  });

  const start = async () => {
    // Get token from your backend (never expose API key to client)
    const { token } = await fetch("/scribe-token").then((r) => r.json());

    await scribe.connect({
      token,
      microphone: { echoCancellation: true, noiseSuppression: true },
    });
  };

  return <button onClick={start}>Start Recording</button>;
}
```

### Commit Strategies

| Strategy | Description |
|----------|-------------|
| **Manual** | You call `commit()` when ready - use for file processing or when you control the audio segments |
| **VAD** | Voice Activity Detection auto-commits when silence is detected - use for live microphone input |

```typescript
// React: set commitStrategy on the hook (recommended for mic input)
import { useScribe, CommitStrategy } from "@elevenlabs/react";

const scribe = useScribe({
  modelId: "scribe_v2_realtime",
  commitStrategy: CommitStrategy.VAD,
  // Optional VAD tuning:
  vadSilenceThresholdSecs: 1.5,
  vadThreshold: 0.4,
});
```

```javascript
// JavaScript client: pass vad config on connect
const connection = await client.speechToText.realtime.connect({
  modelId: "scribe_v2_realtime",
  vad: {
    silenceThresholdSecs: 1.5,
    threshold: 0.4,
  },
});
```

### Event Types

| Event | Description |
|-------|-------------|
| `partial_transcript` | Live interim results |
| `committed_transcript` | Final results after commit |
| `committed_transcript_with_timestamps` | Final with word timing |
| `error` | Error occurred |

See real-time references for complete documentation.

## References

- [Installation Guide](references/installation.md)
- [Transcription Options](references/transcription-options.md)
- [Real-Time Client-Side Streaming](references/realtime-client-side.md)
- [Real-Time Server-Side Streaming](references/realtime-server-side.md)
- [Commit Strategies](references/realtime-commit-strategies.md)
- [Real-Time Event Reference](references/realtime-events.md)
