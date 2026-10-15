# ComfyUI × OpenMontage 制作规划

> 状态：AutoDL 实例已创建；ComfyUI、CLI、自定义节点与第一批 workflow 已安装。当前接入 15 条核心模板；生图默认统一为 Krea，Z-Image GGUF 仅备用，Nunchaku 路线已撤销；GPU 扩展验收尚未开始。
> 更新日期：2026-07-23

> 第一批模型公共库核验结果见：`FIRST_BATCH_MODEL_AVAILABILITY.md`。当前建议已收敛为 **AutoDL.com + ComfyUI-Easy-Install**；AutoDL.Art 公共模型库对本批 15 项要求没有形成有效覆盖。
>
> 家庭服务器只读安全审计和分阶段加固方案见：`SERVER_SECURITY_HARDENING.md`。本轮仅审计和写方案，尚未修改 SSH、防火墙、Docker、用户或服务状态。

> AutoDL 官方开发者 Token 文档当前只公开“容器实例 Pro”开关机接口。2026-07-23 使用本项目 `.env` Token 调用 Pro 列表返回 0 条，说明当前普通算力市场实例不受该接口管理。`scripts/autodl_instance.py` 可用于未来 Pro 实例；当前实例关机使用 `ssh autodl-comfyui 'sync; shutdown -h now'`，已实测SSH断开且用户确认AutoDL控制台显示已关机。

## 0. AutoDL 实例配置结论（已创建并扩容）

2026-07-22 曾在 AutoDL.com 创建页完成 4090 配置核对但没有库存；随后用户已创建另一台 32GB vGPU 实例并完成部署。下表以当前实际实例为准，早期截图价格只作为历史参考。

| 项目 | 已确认配置 |
|---|---|
| GPU | vGPU 32GB × 1；GPU 验收记录显示为 RTX 4080 SUPER 32GB |
| CPU / 内存 | 16 vCPU / 62GB |
| 系统盘 | 30GB；只保存系统与少量启动配置 |
| 数据盘 | 已扩容至 250GB；模型、输入、输出和临时文件均在此盘 |
| 基础镜像 | PyTorch 2.8.0 / Python 3.12 / Ubuntu 22.04 / CUDA 12.8 |
| 实例价格 | 创建页显示约 1.68元/小时；数据盘费用与实时价格以控制台为准 |

镜像选择说明：课程作者当前 `MAC-Linux` 安装脚本会在安装目录内自行构建 Python 3.12，并安装自己的 PyTorch 2.9.1 + CUDA 13.0 运行环境，因此 AutoDL 的 PyTorch 2.8.0/CUDA 12.8 是兼容的基础镜像，不是最终 ComfyUI 环境。不要选择 JAX、TensorFlow 或 PaddlePaddle 镜像。

当前实例操作原则：

1. 下载和文件整理使用无卡模式；真实推理验收才切换 GPU 模式；
2. 切换模式前必须确认下载进程、ComfyUI 队列和文件写入均为空；
3. 已验证采用分层安装：ComfyUI、内置 Python/Torch、自定义节点、CLI 与 workflow 放在系统盘 `/root/ComfyUI-Easy-Install`，约占 11GB，可随私有镜像保存；模型、输入、输出和临时文件放在数据盘 `/root/autodl-tmp`，通过固定软链接接入，避免模型进入镜像；
4. 250GB 数据盘仍执行至少保留 50GB 的硬约束，生成资产校验下载到本地后立即清理远端副本。

## 1. 制作目标与内容类型

当前目标是把 `07产出` 中的内容接入 ComfyUI 与 OpenMontage，逐步建立可重复的内容生产链。

| 内容类型 | 第一阶段交付 | 第二阶段升级 |
|---|---|---|
| 我来介绍一下 | 正式配音、配图、少量关键动态镜头、字幕与封面 | 固定主持角色、固定声线、人物口型 |
| 寓言 | 旁白故事短视频，以静帧叙事为主，关键画面生成视频 | recurring 角色、多角度一致性、必要时人物 LoRA |
| 心哲灵短视频文案 | 正式配音、概念画面、OpenMontage 动效、字幕与封面 | 固定视觉风格；通常不强制人物 LoRA |
| 小故事 | 公众号封面、头图和章节配图 | 固定主角与多场景一致性；暂不作为视频主线 |

当前 `07产出` 中已确认存在“寓言”“心哲灵”“小故事”。尚未在该目录中定位到“我来介绍一下”，目前按用户口述的短视频定位规划。

## 2. 总体生产链

第一阶段目标链路：

```text
文案
  → ComfyUI Qwen3-TTS 正式配音
  → 音频强制对齐/转写，获得字幕时间轴
  → Krea 2 批量分镜图、封面与重点主视觉
  → Z-Image GGUF 仅在 Krea 不可用时备用
  → Wan 2.2 I2V 生成少量关键动态镜头
  → OpenMontage 完成字幕、动效、音乐、封面与成片
```

第二阶段目标链路：

```text
批准的人物设定图
  → Flux 2 Klein KV 多参考一致性
  → 必要时训练人物 LoRA
  → Qwen3-TTS 固定/克隆声线
  → InfiniteTalk 人物口型
  → Wan Animate 或 SCAIL 人物动作
  → OpenMontage 合成与交付
```

## 3. OpenMontage 当前承担的能力

以下能力已有基础，不需要用课程 workflow 重复建设：

- 文案拆分、scene plan 和素材规划；
- Remotion/FFmpeg 合成；
- 中文字幕渲染与中文标题卡；
- 音乐混合、封面排版；
- 横版、竖版输出；
- 素材清单、checkpoint 和项目归档；
- 可拆分 SVG/2D rig 角色的确定性动画能力。

2026-07-22 本地能力核对结果：

- FFmpeg、Remotion 可用；HyperFrames 当前未确认可用；
- TTS 已有 DashScope、Edge、OpenAI，但用户明确要求正式配音改用课程中的 ComfyUI TTS；
- `comfyui_image`、`comfyui_video` 与 `comfyui_tts` 已通过专用 SSH 隧道连通；AutoDL 的 8188 端口仍只监听 `127.0.0.1`；
- SadTalker、Wav2Lip 当前未配置；
- Edge-TTS 仅保留为免费应急兜底，不作为正式配音主线。

### 配音替换的关键集成问题

现有 `zh-philosophy-video` 工作流依赖 Edge-TTS 的 `WordBoundary` 事件驱动字幕和镜头时序。换用 Qwen3-TTS 后，必须增加音频强制对齐或转写环节，重新得到准确的字幕时间轴。这是第一批的必要适配任务。

## 4. 第一批 workflow：打通正式生产链

### 4.1 正式配音主线：Qwen3-TTS

课程：EP07

- `1. Qwen3-TTS CustomVoice.json`
- `2. Qwen3-TTS VoiceDesign.json`

用途：

- `CustomVoice` 用于验证稳定的中文预设音色；
- `VoiceDesign` 用于建立栏目声线：
  - 寓言：温柔、克制、有叙事感；
  - 心哲灵：平静、清醒、有思辨感；
  - 我来介绍一下：亲切、自然、有主持感。

自动化前验证：

- 30 秒与 90 秒中文长文本；
- 标点停顿、数字、英文名和专有名词；
- 固定参数/seed 后的声线稳定性；
- 音频采样率、最终保存节点；
- API 格式导出；
- Qwen 音频进入 OpenMontage 后的字幕强制对齐。

备选课程：EP10

- `Fish S2 TTS.json`

Fish S2 只做单人旁白 A/B 音质比较，不与 Qwen 同时建设完整链路。课程资料称其显存需求接近 20GB；正式使用前必须重新核对具体模型的商业使用许可证。

### 4.2 备用分镜生图：Z-Image Turbo GGUF

课程：EP01

- `5c Z-Image Turbo GGUF txt2img.json`

备用用途：

- 心哲灵概念插画；
- 寓言的大部分场景图；
- 小故事的普通章节插图；
- 每条短视频 6–21 张画面的批量生产。

保留原因：已有模型可用、量化版本显存压力较低、seed 和参数可复现。2026-07-23 起它不再承担默认批量生产，仅在 Krea 模型、节点或显存路径不可用时由调用方显式选择。

### 4.3 封面与重点主视觉：Krea 2

课程：EP24

- `1d. Krea 2 Text to Image - Simple Low Vram.json`
- `2a. Krea 2 Text to Image + Extra Pass.json`

使用原则：

- Low VRAM 版本先验证稳定性；
- `krea2_low_vram` 是 OpenMontage 默认生图模板，用于普通分镜和常规配图；
- Extra Pass 只用于封面和少量重点图，由调用方显式选择；
- AI 只生成无字底图，中文标题由 OpenMontage 的 Remotion/PIL 精确叠加，避免乱码并保留可编辑性。

### 4.4 关键镜头生视频：Wan 2.2 I2V

课程：EP06

- `Wan 2.2 Image to Video.json`

第一批暂不使用带 LoRA 的版本。

用途：把审核通过的关键静帧转换为 1–5 秒动态镜头。每条短视频建议只生成约 2–4 个关键动镜，其余画面由 OpenMontage 完成推拉、景深、字幕、图形和转场，以减少 GPU 成本与生成失败率。

OpenMontage 已有 Wan 2.2 API workflow，课程版本是另一条 UI/低显存路线。部署时应比较两者，最终只保留一条正式 I2V 主路径。

### 4.5 重点图片增强：SeedVR2

课程：EP05

- `5 SeedVR2 Upscale.json`

只用于封面、公众号头图、重点人物图及确实需要的动态镜头，不默认处理全部素材。起步建议使用 3B FP8 或 Q4、固定 2× 放大。

### 4.6 可选封面支持

课程：EP08

- `01. Remove Background.json`
- `04. Image Combiner.json`

仅在封面需要主体抠图时纳入。简单图层合成继续交给 OpenMontage，避免重复建设。

### 第一批最终清单

1. Qwen3-TTS CustomVoice；
2. Qwen3-TTS VoiceDesign；
3. Qwen 音频到字幕的强制对齐适配；
4. Krea 2 Low VRAM 默认批量生图、封面/主视觉；
5. Z-Image Turbo GGUF 显式备用；
6. Krea 2 Extra Pass 重点图增强；
7. Wan 2.2 I2V 关键动态镜头；
8. SeedVR2 重点素材放大；
9. OpenMontage 成片与封面合成。

Fish S2 只作为配音备选，不阻塞第一批。

## 5. 第一阶段增强批与第二批：固定角色和人物表演

### 5.1 第一阶段增强批：无 LoRA 的人物一致性基线

课程：EP09

- `4. Flux 2 Klein 9B KV FP8 - 4 Images Edit.json`
- `1i. Flux 2 Klein 9B KV FP8 - 1 Image Edit Inpaint.json`

先制作并批准人物正面、侧面、半身、全身设定图，再通过多参考编辑生成新场景，使用 Inpaint 修复脸、手、服装。少量作品和有限镜头通常不需要立即训练 LoRA。

该能力现已提升为下一项优先建设内容，不再等待人物 LoRA 阶段。AutoDL 已具备所需自定义节点以及 `flux-2-klein-9b-kv-fp8.safetensors`、`qwen_3_8b_fp8mixed.safetensors` 和 `flux2-vae.safetensors` 三个模型文件；无卡结构预检通过，下一步只需完成 GPU 实测。验收后，第一阶段即可生产有固定人物的短视频而无需训练 LoRA。

### 5.2 人物 LoRA

课程：EP26

- `Krea 2 Lora Converter.json`
- `Krea 2 Text to Image - Simple + Lora XY Plot.json`
- `Krea 2 Text to Image - Simple + Lora.json`
- `Krea 2 Text to Image + Extra Pass + Lora.json`

只有当人物需要跨大量作品、换景、换装和多角度长期复用时才训练。建议准备 10–30 张经过授权和筛选的训练图。

课程中的训练走 FAL，是外部付费步骤；执行前必须单独获得用户批准。训练后还需固定 seed、使用 XY Plot 验收 LoRA 强度，并记录 base model、LoRA、trigger、strength 和版本。

### 5.3 固定声线与声音克隆

课程：EP07

- `4. Qwen3-TTS VoiceClone + SaveVoice.json`
- `6. Qwen3-TTS VoiceClone + Load A Previous Saved Voice.json`

用于固定旁白人格或角色声线，让视觉身份与声音身份长期绑定。

#### 是否需要提前准备声音样本

- `CustomVoice`：不需要参考录音，先从模型内置音色中挑选稳定候选；
- `VoiceDesign`：不需要参考录音，用自然语言描述年龄感、音色、情绪、语速与叙事风格；
- `VoiceClone + SaveVoice`：需要一段干净参考录音，并提供与录音逐字一致的参考文本；
- `VoiceClone + Load Voice`：不再需要每次上传样本，直接复用已经验收并保存的角色声音包。

第一阶段先用 `CustomVoice` 与 `VoiceDesign` 完成栏目声线 A/B；只有当预设或设计音色无法稳定形成品牌辨识度时，再进入声音克隆。

#### 参考录音准备规范

每个候选角色准备 3 段 WAV，每段约 10–20 秒：

1. 平静旁白：中性、稳定，覆盖常规说明句；
2. 温暖讲述：带轻微情绪，覆盖寓言或故事语气；
3. 强调转折：包含问句、停顿、数字或英文专名，测试韵律与发音。

录音要求：单人、无音乐、无混响、无明显底噪，不要压缩、变声或降噪过度；尽量固定麦克风、距离和房间。优先单声道 WAV，24kHz 或 48kHz 均可。参考文本必须逐字对应实际发音，包含口头停顿词；不要用剪辑后与文本不一致的录音。

#### 授权、保存与验收

- 只使用本人声音、已获得明确授权的声音，或许可证允许的声音；授权来源与使用范围随角色包记录；
- 项目素材放入 `projects/<项目>/assets/voices/<角色>/references/`，生成的候选与试听表放入同一角色目录；
- 服务器只作为运行缓存。验收后的 `.qvp`、`.wav`、`.json` 声音包下载到本地角色包，完成大小与 SHA-256 校验后再清理服务器副本；
- 用同一段 30 秒和 90 秒测试文本、相同 seed/参数进行 A/B，人工评估身份相似度、跨句稳定性、中文发音、数字/英文专名、情绪自然度与长文本漂移；
- 每个栏目最终只批准一个主声线和一个备用声线，并记录模型版本、workflow hash、语言、seed、指令文本和参考音频 hash。

### 5.4 人物口型

课程：EP06

- `Wan InfiniteTalk - Duration 4, 5, 6 Seconds.json`
- 稳定后再加入 `Wan InfiniteTalk- Easy Extend from 3 to 34 Seconds.json`

先以 4–6 秒短片检查中文口型、身份漂移、眨眼、头部动作和背景稳定性。适合固定主持人和少量角色对白，不应用于舞蹈或复杂全身动作。

### 5.5 人物动作二选一

- 写实人物动作迁移：`Wan 2.2 Animate 16FPS - Replace Only Character.json`；
- 卡通/非写实单人动作：`Wan Scail Image to Video - Single Character.json`。

动作迁移和人物口型是两个独立问题，不能互相替代。等固定角色风格确定后再二选一。

### 第二批最终清单

1. Flux 2 Klein KV 多参考人物一致性；
2. Flux Inpaint 人脸、服装和手部修复；
3. Qwen3-TTS VoiceClone＋Save/Load Voice；
4. 达到复用规模后再训练 Krea 2 人物 LoRA；
5. InfiniteTalk 固定人物口型；
6. Wan Animate 或 SCAIL 人物动作二选一。

## 6. LoRA 决策

### 6.1 固定人物是否一定需要 LoRA

不一定。建议采用以下阶梯：

1. 单条或少量视频：人物设定图＋Flux KV 多参考＋Inpaint；
2. 可拆分的 2D 卡通角色：优先使用 OpenMontage 的 SVG rig/pose library；
3. 跨大量作品、换装换景、多角度仍需保持身份：训练人物 LoRA；
4. 人物关键帧批准后，再分别处理视频动作和口型。

人物 LoRA 只增强“这个人是谁”，不能单独保证视频动作或口型一致。

### 6.2 场景是否需要 LoRA

第一阶段不需要。优先使用：

1. 批准的场景设定图；
2. Flux 2 Klein KV 多参考编辑；
3. Inpaint/Outpaint 调整局部和画幅；
4. 批准静帧进入 Wan 2.2 I2V。

只有在同一地点跨很多作品反复出现、需要多角度仍保持建筑和陈设，或者已经形成固定世界观时，才考虑训练场景 LoRA。

内容建议：

- 心哲灵：通常不需要场景 LoRA，统一画风更重要；
- 寓言：每篇世界不同，不为每篇训练；只有形成统一“寓言世界”后才考虑；
- 我来介绍一下：固定演播室可先用固定背景图，多期复用后再评估场景 LoRA；
- 小故事：单篇不需要，同一系列长期复用固定小城或场所时再考虑。

LoRA 优先级：

```text
人物 LoRA ＞ 风格 LoRA ＞ 场景 LoRA
```

不建议把人物、风格和固定场景全部训练进同一个 LoRA，避免人物与背景绑定，降低换装、换景和换构图能力。

## 7. AutoDL 配置建议

### 第一阶段推荐

| 配置项 | 建议 |
|---|---|
| GPU | 单卡 RTX 4090 24GB；价差明显时可选 RTX 3090 24GB |
| CPU | 16 vCPU |
| 内存 | 64GB |
| 系统盘 | 60–80GB |
| 数据盘 | 当前扩展模型方案使用 250GB，并强制保留至少 50GB；若继续长期叠加 LoRA 和多套大模型，再扩到 300GB 以上或迁出冷模型 |
| 系统 | Ubuntu 22.04 |
| CUDA | 成熟的 CUDA 12.x 镜像，倾向 CUDA 12.4、驱动 550+；安装前按节点兼容矩阵最终锁定 |

ComfyUI 运行时热模型、中间帧和当前产出应放在本地数据盘；长期模型权威副本放家庭服务器，AutoDL 文件存储作为云端镜像。首轮不建议双卡，因为大多数课程 workflow 不会自动跨卡叠加显存。

### 第二阶段升级条件

如果频繁运行以下重型组合，再考虑 A6000/A40 48GB：

- 20–34 秒 InfiniteTalk；
- Wan Animate；
- 多个 14B 模型组合；
- 更高分辨率、帧数或更少 offload 的持续批量生产。

## 8. 所有课程 workflow 的导入边界

课程下载的多数 JSON 是 ComfyUI UI workflow，不能直接视为 OpenMontage 可调用的 API workflow。每条 workflow 在进入自动化生产前必须完成：

1. 在目标 ComfyUI 中加载；
2. 列出并补齐模型与自定义节点；
3. 核对模型、声音、人物与训练数据许可证；
4. 手动成功运行一次；
5. 导出 API 格式；
6. 区分可模板化节点与固定节点；
7. 确认最终保存节点的 `output_node`；
8. 参数化 prompt、seed、尺寸、帧数、音频或源图；
9. 记录模型栈、版本和 workflow hash；
10. 完成低成本 smoke test 并标记 `ready`。

## 9. 当前决策与禁止事项

- 正式配音主线：Qwen3-TTS；
- Fish S2：只作为备选并先核对许可证；
- Edge-TTS：仅应急兜底；
- 第一阶段不训练人物或场景 LoRA；
- 先用多参考图解决人物/场景一致性；
- 关键动镜使用 Wan 2.2 I2V，不对全部分镜生成视频；
- 封面中文文字由 OpenMontage 本地叠加；
- 历史状态：本规划初稿阶段尚未获准创建实例；该限制已被用户后续授权替代，当前实施状态见第 10 节。
- 2026-07-22 AutoDL.Art 公共模型库核验：已明确核验的 14 项中有效命中为 0；因此第一批正式环境优先选择 AutoDL.com，采用家庭服务器权威库、AutoDL 文件存储云端镜像、本地 SSD 热缓存的分层方案。

## 10. 2026-07-23 实施与 GPU 验收更新

上述“当前只完成规划”的限制已经被用户后续明确授权替代。AutoDL.com 实例、ComfyUI、Comfy CLI、自定义节点和第一批模型均已部署；7 个第一批 workflow 已在 RTX 4080 SUPER 32GB 上完成真实推理，全部生成成功。

详细参数、用时、输出和兼容修正见：

- [`GPU_WORKFLOW_VALIDATION_2026-07-23.md`](GPU_WORKFLOW_VALIDATION_2026-07-23.md)

当前结论：这台 32GB 实例足以承担第一阶段的 Qwen3-TTS、Krea 2、备用 Z-Image GGUF、Wan 2.2 Q6 I2V 和 SeedVR2 7B FP8 工作流。进入 OpenMontage 自动化前仍需把 UI workflow 固化成参数化 API workflow，并完成人工视听质量验收。

## 11. 横竖比例 API 预设

2026-07-23 已将 5 个视觉 workflow 固化为唯一的 API 模板，并由 OpenMontage 在调用时注入 `portrait_9_16` 或 `landscape_16_9`。不复制横竖两套 workflow；两条 TTS 不涉及比例。横竖版 GPU smoke test 已全部通过。

详细调用参数与测试结果见：

- [`FIRST_BATCH_API_PRESETS.md`](FIRST_BATCH_API_PRESETS.md)

## 12. 最全生产套件差距

当前 7 条完成基础生产链；加入两条 Flux 2 Klein 无 LoRA 人物一致性 workflow 后为 9 条；再加入 VoiceClone 2 条、InfiniteTalk 2 条和人物动作 2 条，形成 **15 条**固定角色核心套件。可选 Krea 2 人物 LoRA 扩展再增加 4 条后，内容能力共 19 条。Nunchaku 已从下载、模板与验收范围中撤销。

完整差距、当前节点/模型状态和实施顺序见：

- [`FULL_WORKFLOW_ROADMAP.md`](FULL_WORKFLOW_ROADMAP.md)
