# ComfyUI 最全生产套件差距与路线图

日期：2026-07-23

## 结论

“最全版”不应做成一张超大的 ComfyUI 图，而应是一组可组合、可单独回退的 API workflow。当前 7 条已经覆盖配音、生图、重点图增强、图生视频和放大；下一步优先补“无 LoRA 人物一致性”，再补声音克隆、口型和人物动作。人物 LoRA 放在确实出现规模化复用需求之后。

## 当前已完成：7 条

1. Qwen3-TTS CustomVoice；
2. Qwen3-TTS VoiceDesign；
3. Z-Image Turbo GGUF；
4. Krea 2 Low VRAM；
5. Krea 2 Extra Pass；
6. Wan 2.2 I2V Q6；
7. SeedVR2 7B FP8 Upscale。

5 条视觉 workflow 已支持 `portrait_9_16` / `landscape_16_9` API 预设并完成 GPU 实测。

## 立即新增：无 LoRA 人物一致性，增加 2 条

课程：EP09

1. `4. Flux 2 Klein 9B KV FP8 - 4 Images Edit.json`
2. `1i. Flux 2 Klein 9B KV FP8 - 1 Image Edit Inpaint.json`

用途分工：

- 4 Images Edit：使用批准的人物正面、3/4 侧面、半身/全身、固定服装参考，生成新场景中的同一人物；
- 1 Image Edit Inpaint：修复脸、手、服装标志和局部身份漂移，不重新生成整张图。

建议生产链：

```text
人物设定图包
  → Flux 2 Klein 四参考图编辑
  → 人工检查身份、服装、发型、年龄和体型
  → Flux 2 Klein Inpaint 局部修复
  → 批准的角色静帧
  → Wan 2.2 I2V
```

当前 AutoDL 核验状态：

- 所需自定义节点均已安装并可被 ComfyUI 识别：`FluxKVCache`、`ResolutionSelector`、`InpaintCropImproved`、`InpaintStitchImproved`、`EmptyFlux2LatentImage`、`ImageScaleToTotalPixels`；
- 3 个 Flux 2 必需模型已按官方精确字节数下载并校验：`flux-2-klein-9b-kv-fp8.safetensors`、`qwen_3_8b_fp8mixed.safetensors`、`flux2-vae.safetensors`；
- 扩展模型整包共 24 个主体文件，另含 NLF 姿态模型；下载脚本逐文件续传并执行精确大小校验，可选启用完整 SHA-256；
- AutoDL 数据盘已扩容至 250GB。2026-07-23 12:44 下载进行中时剩余约 120GB，脚本会在每一项开始前强制预留至少 50GB。

加入这两条后，无 LoRA 正式生产套件共有 9 条 ComfyUI workflow。

## 最全但不堆冗余的固定角色套件：核心共 15 条

在上述 9 条基础上，再增加：

### 固定声线：2 条

- `4. Qwen3-TTS VoiceClone + SaveVoice.json`
- `6. Qwen3-TTS VoiceClone + Load A Previous Saved Voice.json`

### 人物口型：2 条

- `Wan InfiniteTalk - Duration 4, 5, 6 Seconds.json`
- `Wan InfiniteTalk- Easy Extend from 3 to 34 Seconds.json`

### 人物动作：两条均保留，按角色类型调用

- 写实人物：`Wan 2.2 Animate 16FPS - Replace Only Character.json`
- 卡通/非写实人物：`Wan Scail Image to Video - Single Character.json`

因此核心正式套件为：当前 7 + 无 LoRA 一致性 2 + 声音克隆 2 + 口型 2 + 动作 2 = **15 条**。写实角色调用 Animate，卡通/非写实角色调用 SCAIL；这不是同一作品重复跑两条。

生图默认统一使用 Krea 2 Low VRAM，重点主视觉显式使用 Krea 2 Extra Pass；现有 Z-Image GGUF 只作为故障或资源受限时的备用。Nunchaku 候选已撤销，不再作为第 16 条模板，也不再执行速度 A/B。

## 2026-07-23 实施状态

- 11 条新增课程 UI workflow 已转换为 API-format JSON，保存于 `tools/_comfyui/workflows/production/`；
- 现有 5 条视觉模板继续保存于 `tools/_comfyui/workflows/first_batch/`；
- OpenMontage 已增加 `comfyui_tts`，并把 Flux 2、InfiniteTalk、Animate、SCAIL 注册为参数化模板；
- 图片模板支持 `portrait_9_16` / `landscape_16_9`，视频模板支持横竖尺寸参数；
- 远端输入、输出、临时文件已迁移到数据盘；成品下载采用临时文件、SHA-256 校验、原子落盘，校验后才请求远端删除；
- 清理失败会写入项目资产目录下的 `.comfyui-cleanup-pending.jsonl`，不会误删，也不会触发自动关机；
- Nunchaku 下载与模板已撤销，Mac 与 AutoDL 运行环境已清理完毕；扩展 GPU 验收尚未开始；
- 15/15 活动模板已通过无卡结构预检，Krea、Flux、InfiniteTalk、Animate、SCAIL 与备用 Z-Image GGUF 模型均在位；验收夹具已统一保存到本地项目目录；
- InfiniteTalk 延长版已从课程 UI 时长选择器激活完整 12 段链路，重新导出为 83 节点 API 图，唯一成品输出为节点 240；结构校验通过，34 秒生成质量仍待 GPU 实跑验收。

## 可选 LoRA 扩展：再增加 4 条，核心能力总计 19 条

只有当同一人物跨大量作品、角度、服装和场景长期复用时再加入：

- `Krea 2 Lora Converter.json`
- `Krea 2 Text to Image - Simple + Lora XY Plot.json`
- `Krea 2 Text to Image - Simple + Lora.json`
- `Krea 2 Text to Image + Extra Pass + Lora.json`

这 4 条不属于当前阻塞项。训练数据授权、FAL 付费训练、LoRA 强度验收均需单独批准。

## 不需要重复建设的课程 workflow

- Remove Background、Image Combiner：OpenMontage 已能完成抠图后的排版、合成和中文标题；只有特殊封面需求才导入；
- Fish S2：仅作为 Qwen3-TTS 音质或许可证不合适时的备选；
- 横竖版复制：继续使用一个 API workflow 加两个参数预设，不复制两份图；
- 全量画面视频化：仍只对 2–4 个关键镜头使用 Wan，其余由 OpenMontage 动效完成。

## ComfyUI 之外仍缺的生产能力

即使达到 15 条核心 workflow，完整流水线仍需要：

1. Qwen3-TTS 音频强制对齐/转写，恢复精确字幕时间轴；
2. 人物参考图包和版本管理；
3. 自动记录人物、服装、场景、seed 和 workflow hash；
4. 图片身份一致性人工验收；
5. 视频身份漂移、口型和动作质量验收；
6. OpenMontage 最终裁切、字幕、声音混合、封面和成片交付。

## 推荐实施顺序

1. 立即建设 Flux 2 Klein 四参考图编辑；
2. 建设 Flux 2 Klein Inpaint；
3. 制作第一个固定人物参考图包并完成横竖版 GPU 实测；
4. 将两条 workflow 固化为 OpenMontage 参数化 API 模板；
5. 再建设 Qwen VoiceClone；
6. 然后建设 4–6 秒 InfiniteTalk；
7. 最后根据人物风格选择 Wan Animate 或 SCAIL；
8. 只有无 LoRA 方案达到瓶颈后才启动 LoRA。
