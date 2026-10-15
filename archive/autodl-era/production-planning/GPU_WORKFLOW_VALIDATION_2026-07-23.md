# AutoDL 第一批 ComfyUI Workflow GPU 验收记录

日期：2026-07-23
实例：AutoDL.com，单卡 NVIDIA GeForce RTX 4080 SUPER 32GB
运行环境：ComfyUI 0.28.0、Python 3.12.10、PyTorch 2.10.0+cu130、Comfy CLI 1.12.0

## 结论

第一批 7 个 workflow 已全部在 GPU 模式下完成真实推理并生成有效文件。模型文件、自定义节点、系统盘/数据盘软链接以及 ComfyUI 服务均可正常工作。

| 序号 | Workflow | 实测参数 | 用时 | 结果 |
|---:|---|---|---:|---|
| 1 | Qwen3-TTS CustomVoice | 1.7B、bf16、Ryan | 22.96 秒 | MP3 成功 |
| 2 | Z-Image Turbo GGUF txt2img | 768×768、5 steps | 35.83 秒 | PNG 成功 |
| 3 | Krea 2 Simple Low VRAM | 768×768、8 steps、Enhancer 0.1 | 17.93 秒 | PNG 成功 |
| 4 | Krea 2 Extra Pass | 768×1344 起步、1.5× latent upscale、8+4 steps、Enhancer 0.5 | 21.06 秒 | 1152×2016 PNG 成功 |
| 5 | Wan 2.2 Image to Video | 480×832、49 帧、16fps、6 steps | 99.33 秒 | 3.063 秒 H.264 MP4 成功 |
| 6 | Qwen3-TTS VoiceDesign | 1.7B、bf16 | 46.70 秒 | MP3 成功 |
| 7 | SeedVR2 Upscale | 768×768 → 4096×4096、7B FP8 | 69.71 秒 | PNG 成功 |

## 兼容修正

### 1. Windows 模型路径改为 Linux 路径

课程 JSON 中 Z-Image、Krea 2、Wan 2.2 的 loader 使用了反斜杠，例如 `z-image\\model.gguf`。Linux ComfyUI 的模型枚举值使用 `/`，因此已把已导入 workflow 中相应 loader 的路径改为：

- `z-image/z-image-turbo-q4_k_s.gguf`
- `krea2/krea2_turbo_fp8_scaled.safetensors`
- `wan2.2/wan2.2_i2v_A14b_high_noise_lightx2v_4step-Q6_K.gguf`
- `wan2.2/wan2.2_i2v_A14b_low_noise_lightx2v_4step-Q6_K.gguf`

修改前的 7 个 JSON 已备份在实例 workflow 目录下的 `.backup-before-linux-paths-20260723-092508/`。

### 2. Krea2T Enhancer 适配 ComfyUI 0.28

课程增强节点使用旧版 Krea 2 wrapper 函数签名；ComfyUI 0.28 的 Krea 2 模型新增 `ref_latents` 参数，原节点会报 `7 were given`。已做最小兼容补丁：接收并向下传递 `ref_latents`，增强器仍然启用，没有绕过。

原节点文件备份：

`/root/ComfyUI-Easy-Install/ComfyUI/custom_nodes/ComfyUI-Krea2T-Enhancer/__init__.py.pre-comfy-028`

### 3. UI workflow 与 API workflow

Qwen TTS、Z-Image 和 Wan 的主要节点可由 Comfy CLI 正常转换。Krea workflow 的 `PixaromaResolution`、`PixaromaSeed`、`PixaromaPreview` 属于前端辅助节点，CLI 转换不会完整携带它们的界面状态。GPU 验收时使用等价 API 副本，把尺寸、种子和保存节点写成标准 API 输入；Krea 模型、采样器、增强器、VAE 和参数不变。

自动化接入 OpenMontage 时应使用验收目录中的 API 副本，而不是直接提交原始 UI JSON。

## 实例路径

- ComfyUI：`/root/ComfyUI-Easy-Install/ComfyUI`
- 模型根目录：`/root/autodl-tmp/comfyui-models`
- 输入：`/root/autodl-tmp/comfyui-runtime/input`
- 输出：`/root/autodl-tmp/comfyui-runtime/output`
- 验收日志与 API 副本：`/root/autodl-tmp/comfyui-runtime/validation`
- 已导入 UI workflow：`/root/ComfyUI-Easy-Install/ComfyUI/user/default/workflows`

## 验收后的资源状态

- 系统盘：11GB / 30GB，约 20GB 可用；
- 数据盘：83GB / 150GB，约 68GB 可用；
- ComfyUI 健康检查：通过；
- 验收结束时 ComfyUI 保持运行，实例未关机。

## 下一步

1. 在浏览器中人工试听两段配音，并检查五个视觉输出的内容质量；
2. 将 7 个验收用 API workflow 固化为 OpenMontage 的参数化模板；
3. 参数化文案、提示词、种子、尺寸、时长、源图和输出前缀；
4. 给每条模板补齐 `output_node`、模型栈、workflow hash 和失败恢复策略；
5. 人工验收完成后再删除数据盘上的旧版 ComfyUI 副本，释放约 11GB。
