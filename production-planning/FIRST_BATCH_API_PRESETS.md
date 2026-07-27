# 第一批 ComfyUI API Workflow 与比例预设

日期：2026-07-23

## 设计结论

第一批视觉能力保留 5 个唯一的 API workflow，不复制成 10 个横竖版 JSON。OpenMontage 在提交前根据 `aspect_preset` 给同一张 API 图注入宽、高、提示词、种子、源图、时长和输出前缀。

两条 Qwen3-TTS workflow 不涉及画面比例，仍各保留一个版本。因此第一批总数仍为 7 个标准 workflow。

## 可调用模板

| `workflow_template` | 工具 | 输出节点 | 比例行为 |
|---|---|---:|---|
| `z_image_turbo_gguf` | `comfyui_image` | `171` | 注入横竖尺寸 |
| `krea2_low_vram` | `comfyui_image` | `199` | 注入横竖尺寸 |
| `krea2_extra_pass` | `comfyui_image` | `199` | 注入横竖尺寸，输出自动 1.5× |
| `wan22_i2v_q6` | `comfyui_video` | `122` | 注入横竖尺寸并自动上传源图 |
| `seedvr2_upscale` | `comfyui_image` | `6` | 跟随源图比例，只设置目标分辨率 |

## 比例预设

| 预设 | 图片生成尺寸 | Wan 2.2 尺寸 | 最终交付 |
|---|---:|---:|---:|
| `portrait_9_16` | 768×1344 | 576×1024 | OpenMontage 居中裁切/缩放到 1080×1920 |
| `landscape_16_9` | 1344×768 | 1024×576 | OpenMontage 居中裁切/缩放到 1920×1080 |

图片尺寸优先使用模型友好的 64 倍数，因此 768×1344 / 1344×768 是接近 9:16 / 16:9 的 4:7 / 7:4。最终精确比例由 OpenMontage 构图阶段完成。Wan 使用精确 9:16 / 16:9。

## 调用示例

### Krea 2 横版

```json
{
  "prompt": "Wide cinematic reading room at golden hour",
  "workflow_template": "krea2_extra_pass",
  "aspect_preset": "landscape_16_9",
  "seed": 2002,
  "output_path": "projects/example/assets/images/reading-room.png"
}
```

调用方不需要提供 `workflow_path` 或 `output_node`。

### Wan 2.2 竖版

```json
{
  "prompt": "The character gives a gentle wave, subtle natural motion",
  "workflow_template": "wan22_i2v_q6",
  "aspect_preset": "portrait_9_16",
  "reference_image_path": "projects/example/assets/images/character.png",
  "num_frames": 49,
  "seed": 3001,
  "output_path": "projects/example/assets/video/character-wave.mp4"
}
```

`num_frames` 支持 17、33、49、65、81，对应约 1–5 秒。工具会自动上传源图，不需要调用方预先把图片放进 ComfyUI input。

### SeedVR2

```json
{
  "prompt": "upscale",
  "workflow_template": "seedvr2_upscale",
  "reference_image_path": "projects/example/assets/images/source.png",
  "resolution": 2048,
  "seed": 4001,
  "output_path": "projects/example/assets/images/source-upscaled.png"
}
```

SeedVR2 不强制横版或竖版，会保持源图比例。

## GPU 实测

AutoDL RTX 4080 SUPER 32GB 上的比例预设 smoke test：

| 测试 | 输出 | 用时 | 结果 |
|---|---:|---:|---|
| Z-Image 竖版 | 768×1344 PNG | 42.24 秒 | 通过 |
| Z-Image 横版 | 1344×768 PNG | 20.52 秒 | 通过 |
| Krea Low VRAM 横版 | 1344×768 PNG | 17.23 秒 | 通过 |
| Krea Extra Pass 横版 | 2016×1152 PNG | 24.02 秒 | 通过 |
| Wan 2.2 竖版 | 576×1024、49 帧、3.063 秒 MP4 | 135.74 秒 | 通过 |
| Wan 2.2 横版 | 1024×576、49 帧、3.063 秒 MP4 | 125.00 秒 | 通过 |
| SeedVR2 横版 | 2016×1152 → 3584×2048 PNG | 35.53 秒 | 通过 |

Krea 两个竖版、SeedVR2 4096 方图与两条 TTS 已在上一轮 GPU 验收通过。

## 实现位置

- 参数化定义：`tools/_comfyui/first_batch.py`
- API workflow：`tools/_comfyui/workflows/first_batch/`
- 图片工具入口：`tools/graphics/comfyui_image.py`
- 视频工具入口：`tools/video/comfyui_video.py`
- 合同测试：`tests/contracts/test_comfyui_tools.py`

本地合同测试结果：`72 passed`。
