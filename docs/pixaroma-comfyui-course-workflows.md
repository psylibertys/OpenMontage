# Pixaroma ComfyUI 课程工作流索引（37 课全）

以每节课为单位，整理该课对应的工作流文件、功能、适用场景与输入输出。

- **课程笔记**（Obsidian，只读）：`/Users/treeelf/Desktop/Psynaut/treeElfNotes/03资源/YouTube课程/pixaroma/ComfyUI_Course_-_Learn_ComfyUI_From_Scratch_Pixaroma/课次/`
- **工作流文件**：`/Users/treeelf/Desktop/other/pixaroma-comfyui-workflow/`（各课子目录 `EP01 Workflows` … `EP37 Workflows`，EP/Ep 前缀大小写混用）
- 第 3、12 课无工作流文件（纯节点演示/编程课），已注明。
- 提示词公式包（ChatGPT/Gemini/Claude 用）索引见课程档案 `课程档案.md` 的"本地工作流与提示词资源"节。

**备注列说明**（时效判断截至 2026-10）：

- 课程收获分两批：**EP01–26 为 2026-07 批（较早）**、**EP27–37 为 2026-10 批（最新）**。
- 备注标注：时效状态（最新 / 仍有效 / 已被取代 / 偏旧）、许可证限制、付费/外部依赖风险、与本项目（dance-video）的关联。

## AutoDL 实例部署状态(2026-10-14 无卡模式实测)

实例 `1vgexf3kfe`(4090D)。**生产部署以本地 19 条 API 模板(`tools/_comfyui/workflows/`)为准,远端是执行引擎**;实例 `user/default/workflows/` 另存少量人工调试版 UI 工作流。

标记:🟢 已部署(模型在位+GPU 验收) / 🟡 已部署待 GPU 验收 / 🔵 冷存(API 模板在,模型只在 duolaiduo 备份盘,用前先恢复) / ⚪ 未部署(工作流仅存 Mac 课程库) / 🔴 已废弃

各课表格最右的「AutoDL」列(2026-10-14 加)沿用同一套标记,另:`—` 表示不经实例(Mac 侧管线/付费 API/纯说明板);⚪ 括注「模型/节点在位」= 相应资产已在实例、只是没建 API 模板,需要时可现场转换。

| 课程 | API 模板(19 条) | 状态 |
|---|---|---|
| EP07 Qwen3-TTS | `qwen3_tts_custom_voice` / `voice_design` / `clone_save` / `clone_load` | 🟢 |
| EP24 Krea 2 | `krea2_low_vram` / `krea2_extra_pass` | 🟢 |
| EP09 Klein KV | `flux2_klein_4ref` | 🟢(模型在舞蹈最小集) |
| EP27 Outpaint | `flux2_klein_outpaint` | 🟢(2026-10-12 验收) |
| EP30 Krea 2 Edit | `krea2_edit_lora` / `krea2_outfit_transfer` | 🟡(欠 GPU smoke,约 5 分钟) |
| EP35 FastH3 | `minimax_fasth3_t2v` / `i2v` / `fflf` | 🟢 |
| EP29/32 H3 口型 | `minimax_h3_audio_sync` | 🟢(Speed LoRA 已入链) |
| EP06 Wan Animate | `wan22_animate_character` | 🟢 |
| EP06 SCAIL(1 代) | `wan_scail_character` | 🔵(2 代见 EP23) |
| EP06 InfiniteTalk | `wan_infinitetalk_extend` | 🔵(LongCat 转正后退役) |
| EP01 Z-Image | `z_image_turbo_gguf` | 🔵(Krea 故障备用) |
| EP05 SeedVR2 | `seedvr2_upscale` | 🔵 |

- 实例 UI 工作流目录(人工调试版,非生产):EP01 Getting Started 8 个、EP07×2、EP24×2、EP05×1、EP01 Z-Image×1、**EP06 Wan 2.2 I2V×1(🔴 废弃链路遗留,2026-10-12 只删了 runtime/input 那份,这份下次会话可清理)**;另有 2026-07-23 Windows 路径版备份子目录。
- **本轮升级将新增**(计划见 `production-planning/UPGRADE_PLAN_2026-10-13_items-1-2-4.md`,待用户确认):EP19→`stableaudio3_sfx`(音效)、LongCat-Video-Avatar-1.5(替 InfiniteTalk,课程外模型)、IndexTTS-2.5(配音表演轨,课程外)。
- 已装节点包 26 个,课程相关:ComfyUI-Pixaroma、Krea2T-Enhancer、comfyui-krea2edit、WanAnimatePreprocess、SCAIL-Pose、seedvr2_videoupscaler、fish-audio-s2(节点在、模型未下,许可证不采用)、Easy-Use、kjnodes、videohelpersuite、controlnet_aux、MelBandRoFormer 等。
- EP15 ACE-Step:本项目在用,但走 Mac 侧 `lib/treeelf_music.py` 管线,**不经 AutoDL 实例**。

## 按任务快速找课

| 你要做的事 | 去哪课 | 备注 |
|---|---|---|
| 文生图（写实/通用） | EP01 基础、EP24 Krea 2、EP25 INT8 提速 | Krea 2 是当前写实主力 |
| 文字/版式设计图（海报、UI、Logo） | EP37 Ming Image | 最新批，MIT 许可 |
| 单图编辑（换背景/加物/改色） | EP09 Klein KV（快）、EP36 Qwen 2.1（编辑强项）、EP30 Krea2 Edit | 三者互补；EP36 许可证非商业 |
| **多张图合成一张（换装/融景/多人合影）** | **EP09（2~4 图）、EP36（2~6 图）、EP04（双图）** | EP09 速度最优；EP04 已被 EP09 取代 |
| 局部重绘 Inpaint / 扩图 Outpaint | EP22、EP27、EP36、EP09 | EP27 外绘专用 LoRA 是当前最优 |
| 动作迁移/换角色跳舞 | **EP06 Wan 2.2 Animate（本项目在用）**、EP23 SCAIL 2 | 两条并行的主力路线 |
| 文生视频/图生视频 | EP29 MiniMax H3、EP32 H3 提速、EP35 FastH3、EP06 | H3 最新批；EP06 偏早但 Animate 仍主力 |
| 数字人口播/说话头像 | EP06 InfiniteTalk、EP29/EP32 H3 唱歌说话 | H3 是更新的替代路线 |
| 语音合成/克隆 | EP07 Qwen3-TTS、EP10 Fish S2 | Qwen3-TTS 免费本地；Fish 多说话人独有 |
| 音乐生成 | EP15 ACE-Step、EP19 Stable Audio 3、EP31 Music 3 | Music 3 是当前最新方案 |
| 图像放大 | EP05（本地 5 种 + 付费 API 2 种） | 路线仍有效；PAID 价格需复核 |
| 图生 3D | EP33、EP34 | 最新批，但该领域演进极快 |
| 提示词工程（扩写/反推/批量） | EP03、EP16、EP18、EP28、EP31 | EP18 Gemma 4 是当前主力封装 |
| 提示词/参数系统实验 | EP21 XY Plot、EP26 LoRA 强度扫描 | 通用方法论，长期有效 |
| 提速与量化 | EP02 Nunchaku、EP25 INT8、EP32 加速 LoRA | 各自仍有效 |

---

## 第 1 课 · ComfyUI 零基础入门（5 小时完整课）

> 地基课：安装、画布、扩散机制、模型格式、LoRA、ControlNet、批量、API、排错。工作流文件 10 个。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `0 Help and Resources.json` | 帮助与资源导航（带链接的说明板） | 入门查资料、找模型下载位 | 无 → 文档/链接 | 随课程维护，仍有效 | — 说明板 |
| `1 Juggernaut Reborn txt2img.json` | SDXL 系基础文生图 | 第一次跑通文生图；学采样器/CFG/seed | 提示词 → 图像 | SDXL/Juggernaut 已偏旧，作概念示例 | ⚪（模型冷存；UI 版在实例） |
| `2 Juggernaut Reborn img2img.json` | 图生图（Denoise 控相似度） | 以图为底改风格/重绘 | 图 + 提示词 + denoise → 新图 | denoise 概念长期通用 | ⚪ 模型冷存 |
| `3 ... txt2img + Lora.json` | 文生图挂 LoRA 风格 | 特定风格/人物/概念注入 | 提示词 + LoRA → 图像 | LoRA 挂法通用，未过时 | ⚪ 模型冷存 |
| `4 ... txt2img + ControlNet.json` | ControlNet 结构约束（Canny/Depth/Pose） | 控构图、姿势、线稿遵循 | 图（结构参考）+ 提示词 → 遵循结构的图 | 用法通用，未过时 | ⚪ 模型冷存 |
| `5a/5b/5c Z-Image Turbo（AIO/Fp8/GGUF）` | Z-Image Turbo 文生图三种格式 | 低显存快速出图（GGUF 最低门槛） | 提示词 → 图像（秒级） | 现役快速模型，未过时 | 🔵 仅 5c（`z_image_turbo_gguf`） |
| `6 Z-Image ... + Lora.json` | Z-Image 挂 LoRA | 风格化快速出图 | 提示词 + LoRA → 图像 | 仍有效 | ⚪ 模型冷存 |
| `7 Z-Image ... + ControlNet.json` | Z-Image + ControlNet | 结构约束 + 快速出图 | 结构参考 + 提示词 → 图像 | 仍有效 | ⚪ 模型冷存 |

## 第 2 课 · Nunchaku 量化加速

> 按显卡代际选 FP4/INT4 量化模型，把普通工作流换 Nunchaku Loader 提速。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `Nunchaku Flux1 Dev txt2img.json` | Flux1 Dev Nunchaku 文生图 | 40 系+ 显卡跑 Flux 提速 | 提示词 → 图像 | Nunchaku 仍是 40/50 系提速主流，未过时 | ⚪ |
| `Nunchaku Qwen Image txt2img.json` | Qwen-Image Nunchaku 文生图 | 同上，Qwen 系 | 提示词 → 图像 | 同上 | ⚪ |
| `Nunchaku Z-Image Turbo txt2img.json` | Z-Image Turbo Nunchaku 文生图 | 低显存极速出图 | 提示词 → 图像 | 同上 | ⚪ |

> AutoDL：全课未部署——Nunchaku 模型与节点均不在实例（提速本项目走 INT8/加速 LoRA 路线）。

## 第 3 课 · Qwen VL3 视觉提示词（无工作流目录）

> 用视觉语言模型把图/多图/视频转成文本提示词，再接文生图。输入=图像/视频+指令公式，输出=提示词文本。（2026-07 批）

**时效备注**：手工搭 VL 模型的做法已被 EP18（Gemma 4 节点族）、EP31（AI Prompt 节点）、EP36（Qwen 2.1 工作流内置）封装取代，实操建议直接用后续课的节点版；本课的提示词公式与"先预览再送编码器"方法论仍有效。

## 第 4 课 · FLUX.2 Klein 4B/9B 图像编辑

> Klein 编辑模型入门：文生图 → 单图编辑 → Inpaint → 双图参考。4B 快、9B 质量高，各有四件套（两个子目录共 8 文件）。（2026-07 批）

| 工作流（4B 与 9B 同构） | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `Image Generation` | Klein 文生图 | 通用生成 | 提示词 → 图像 | **整课已被 EP09 KV 版取代**（同任务约快 3 倍） | ⚪ |
| `One Image Edit` | 单图参考编辑（Reference Latent） | 换背景/改服装材质/保持角色一致性 | 1 图 + 指令 → 编辑图 | 同上 | ⚪ |
| `One Image (Inpaint)` | 蒙版局部重绘（裁切-生成-拼回） | 加首饰/帽子，只改小区域 | 1 图 + 蒙版 + 指令 → 局部改图 | 同上 | ⚪ |
| `Two Images Edit` | 双图参考合成 | 主体 + Logo/服装合成 | 2 图 + 指令 → 合成图 | 多图合成已由 EP09（2~4 图）/EP36（2~6 图）接棒 | ⚪ |

> AutoDL：全课未部署——已被 EP09 KV 链路取代，旧版 Klein 模型只在 duolaiduo 冷存。

**时效备注**：仅当显存跑不动 9B KV 时才考虑本课 4B 版；否则优先 EP09。

## 第 5 课 · 图像放大（7 条路线）

> 从纯缩放到付费 API 的放大选择路径。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `1 Upscale Simple No Model` | 无模型纯缩放 | 只改尺寸不增细节 | 图 + 倍率 → 大图 | 通用基础，长期有效 | ⚪（核心节点可跑，未建模板） |
| `2 Upscale Simple With Model` | 神经网络放大（ESRGAN 系） | 照片/插画通用放大 | 图 → 放大图 | 仍有效 | ⚪ |
| `3 Z-Image Upscaler` | Z-Image 图生图式放大（denoise 控忠实度） | 放大同时补生成式细节 | 图 + denoise → 放大图 | 仍有效 | ⚪（z-image 冷存） |
| `4 Nunchaku Fluxmania Upscaler` | Flux 扩散放大（Nunchaku 提速） | 高质量重绘式放大 | 图 → 放大图 | 仍有效 | ⚪ |
| `5 SeedVR2 Upscale` | SeedVR2 超分 | 视频帧/人像高质量超分 | 图 → 放大图 | 现役（本项目视频超分备用；节点已装、模型冷存） | 🔵（`seedvr2_upscale`） |
| `6 PAID Nano Banana Pro Upscale` | 付费 API 放大（51 credits） | 本地显存不足/要顶级质量 | 图 → 放大图（收费） | credits 价格可能已变动，用前核实 | — 付费 API |
| `7 PAID Recraft Creative Upscale` | 付费 API 创意放大（53 credits） | 同上 | 图 → 放大图（收费） | 同上 | — 付费 API |

## 第 6 课 · 视频模型大全（InfiniteTalk / Wan 2.2 / SCAIL / LTX-2）

> 视频生成主力课。（2026-07 批，但 Wan 2.2 Animate 至今仍是动作迁移主力）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `Wan 2.2/Wan 2.2 Image to Video.json` | Wan2.2 图生视频 | 静图动起来 | 首帧图 + 提示词 → 视频 | 仍有效；通用文生视频已有更新的 H3（EP29/35） | ❌ 旧链路 `wan22_i2v_q6` 2026-10-12 已从注册表删除（静帧动态化改走 FastH3） |
| `Wan 2.2 Image to Video + Lora.json` | 同上挂 LoRA | 特定动作/风格稳定化 | 图 + LoRA + 提示词 → 视频 | 同上 | ❌ 同上 |
| `Wan 2.2 Animate ... Replace Only Character（16/24FPS）` | **动作迁移只换角色**（保留原视频背景） | 给已有视频换主角 | 角色图 + 驱动视频 → 换角色视频 | 未过时；但保留的是原视频背景，本项目舞蹈要换背景，未用此变体 | ⚪（未部署此变体） |
| `Wan 2.2 Animate ... Replace Character and Background（16/24FPS，含 HD 版）` | **动作迁移角色背景全换** | 换装舞蹈、动作复刻 | 角色图 + 驱动视频 → 全替换视频 | **A 方案（现役）**——本项目舞蹈链路模板源头；已实测 1577s/5s 片（4090D，720×1280） | 🟢（`wan22_animate_character`） |
| `Wan InfiniteTalk - Duration 4~11 Seconds` | 说话头像（按时长分档） | 口播、数字人 | 人物图 + 音频 → 对口型视频 | 仍有效；H3 说话（EP29/32）是更新的替代 | ❌ 短口型链路 2026-10-12 已删（改 `minimax_h3_audio_sync`） |
| `Wan InfiniteTalk - Easy/Manual Extend 3→34s` | InfiniteTalk 分段延长 | 长口播视频 | 前段末帧 + 音频 → 更长视频 | 仍有效（仅显式调用，不自动路由） | 🔵（`wan_infinitetalk_extend`，模型冷存） |
| `Wan Scail - Single Character` | SCAIL 单角色图生视频 | 角色表演 | 图 + 提示词 → 视频 | SCAIL 已出 2 代，优先 EP23 | 🔵（`wan_scail_character`） |
| `Wan Scail - Multi Character 9:16` | SCAIL 多角色（仅 9:16） | 双人互动 | 多角色图 + 提示词 → 视频 | 同上 | 🔵 同链路 |
| `LTX-2 Image to Video with Audio` | LTX-2 图生视频（模型生成音频） | 快速带声视频 | 图 + 提示词 → 含音频视频 | 仍有效，小众 | ⚪（32G 显存门槛，挂起） |
| `LTX-2 ... with Custom Audio` | LTX-2 + 自定义音轨 | 配指定声音 | 图 + 音频 → 视频 | 同上 | ⚪（同上） |
| `Video Upscale SeedVR2` | 视频超分 | 视频放大增强 | 视频 → 高清视频 | 现役（本项目备用） | 🔵（`seedvr2_upscale`） |

### 动作驱动视频方案对比（2026-10-14 整理，本项目舞蹈链路）

> 输入口架构事实：动作迁移类工作流只有 **角色图 + 驱动视频** 两个输入口，**没有独立背景图输入口**。背景靠三种落法：进定妆图（推荐）/ prompt 文字描述 / 双参考图（但后者不吃驱动视频）。

| 方案 | 来源 | 背景怎么换 | 速度（4090D，5s 片） | 身份保持 | 状态 |
|---|---|---|---|---|---|
| **A：EP06 Wan 2.2 Animate · Replace Character and Background** | 课程工作流，生产模板 `wan22_animate_character` | 背景合成进定妆图，Animate 重画（非像素级保留） | **已实测 1577s（约 26 分钟）** | 已达可用水准（换脸相似度 0.888） | 🟢 现役，模型在实例 |
| **B：Wan-Animate-2** | **非课程**——Wan 官方下一代，ComfyUI 官方蓝图 "Motion Transfer (Wan Animate 2).json" | **prompt 文字描述锚定背景**（端到端，无 pose 中间表示，官方卖点） | 预估 45–50 分钟（比 A 约慢一倍） | 理论上强于 A（官方迭代重点） | 🟢 **权重四件全部在实例且 SHA-256 校验通过（2026-10-14）**：主模型 16G + umt5_scaled 6.3G + Wan2_1_VAE 243M + lightx2v LoRA 704M，随时可测 |
| C：EP23 SCAIL 2 | 课程工作流，生产模板 `wan_scail_character` | prompt 描述 | 长时长友好（Loop 分段累积帧） | 卡通/非写实更强 | ⚪ 第三备选，模型只在 duolaiduo 冷备份 |

**决策（2026-10-14 当日更新）**：原计划 A/B 同批测试后择一；**用户当日直接拍板选定 B 方案（Wan-Animate-2），不做对比测试**（理由：官方新一代、能力迭代优先）。A 方案整个链路转为删除候选（duolaiduo 7 月权威备份已全含、带 .verified 校验标记）；SCAIL 2 仍留第三备选（模型冷备份在 duolaiduo）。

## 第 7 课 · Qwen3-TTS 免费语音

> 免费本地语音合成全家桶。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `1 CustomVoice` | 预设说话人合成 | 快速配音 | 文本 + speaker → 语音 | 仍是课程内最新免费 TTS 方案 | 🟢（`qwen3_tts_custom_voice`） |
| `2 VoiceDesign` | 声音方向设计（从零造声线） | 独特声线、无参考音频 | 文本 + 声音描述 → 语音 | 未过时 | 🟢（`qwen3_tts_voice_design`） |
| `3 VoiceClone` | 声音克隆 | 克隆自己的声音 | 10-20s 参考音频 + 文本 → 克隆语音 | 未过时 | 🟢（`qwen3_tts_clone_save`） |
| `4/5 ... SaveVoice` | 克隆/设计结果存库复用 | 建声音库 | 声音 → voices 库文件 | 未过时 | 🟢（`qwen3_tts_clone_save`） |
| `6 ... Load A Previous Saved Voice` | 加载已存声音 | 复用角色声线 | 库文件 + 文本 → 语音 | 未过时 | 🟢（`qwen3_tts_clone_load`） |
| `7 ... Multi Voice + Dialogue` | 多声音对话 | 双人/多人对话原型 | 多声音 + 角色文本 → 对话音频 | 未过时 | ⚪（模型在位，未建模板） |
| `8 VoiceDesign + Dialogue` | 设计声音 + 对话 | 定制声线对话 | 声音描述 + 对话文本 → 音频 | 未过时 | ⚪（模型在位，未建模板） |

## 第 8 课 · 图像处理流水线（去背景/合成/调色）

> 节点式图像处理工具课。（2026-07 批，通用工具长期有效）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `01 Remove Background` | 去背景 | 抠主体 | 图 → 前景/蒙版 | 通用，长期有效 | ⚪ |
| `02 Remove Background with Sam3` | SAM3 语义抠图 | 指定对象精确抠 | 图 + 文本 → 前景/蒙版 | 通用；**本项目 v3 所用**（程序式拼装链路将弃用） | 🟢（SAM3 在实例，抠像链路在用） |
| `03 ... Transparent Items` | 透明物去背 | 玻璃/纱类 | 图 → 蒙版 | 通用 | ⚪ |
| `04 Image Combiner` | 多图拼接合成 | 确定性排版 | 多图 → 合成图 | 通用 | ⚪ |
| `05 ... for Transparent Items` | 透明物合成 | 带透明通道素材 | 多图 → 合成图 | 通用 | ⚪ |
| `06 Image Blend` | 图层混合（位置/缩放/模式） | 精确摆放后交 AI 融合 | 多图 + 参数 → 合成图 | 通用；EP09 工作流 5 的基础 | ⚪ |
| `07 Image Compare` | 前后对比图 | 质检对照 | 2 图 → 并排对比图 | 通用 | ⚪ |
| `08 Image Stitch` | 图像拼接 | 全景/长图 | 多图 → 拼接图 | 通用 | ⚪ |
| `09/10 Image Filters（含 Example）` | 色彩/滤镜调整 | 调色流水线 | 图 → 调整图 | 通用 | ⚪ |
| `11 Image Transformation` | 几何变换 | 旋转/翻转/裁切 | 图 → 变换图 | 通用 | ⚪ |
| `12 Image Scale` | 尺寸缩放 | 适配目标分辨率 | 图 → 缩放图 | 通用 | ⚪ |
| `13 Lama Remover` | LaMa 物体移除 | 抹掉杂物 | 图 + 蒙版 → 修复图 | 通用 | ⚪ |
| `14 Flux 2 Klein Multi Steps Workflow` | 多步编辑链（合成→AI 融合→调色，带检查点） | 产品图多轮可复现编辑 | 素材图组 → 成品图 | 思路=生成式融合，与 EP09 互补，仍有效 | ⚪ |

> AutoDL：仅 02 在产；其余工具型未建模板（节点大多随已装节点包，需要时可现场搭）。

## 第 9 课 · FLUX.2 Klein 9B KV（速度+一致性，**多图合成主力**）

> KV 缓存版：参考图只编码一次，4090 单图编辑约 3 秒。所需模型：`flux-2-klein-9b-kv-fp8`(9.82G) + `qwen_3_8b_fp8mixed`(8.66G) + `flux2-vae`(0.34G)，全原生节点。（2026-07 批，但为 Klein 家族**当前最优版**）

> ✅ **已确认保留为本项目定妆主力（2026-10-14）**：模型三件套**已在实例** `/autodl-fs/data/comfyui-models/`（带 .verified 标记，**0 下载**）；`flux2_klein_4ref` 模板 GPU smoke 5/5 通过（2026-10-12）；许可证可商用。定妆四参考 = 头像 + 衣服 + 背景（+ 第 4 图强化身份）。

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `1a 1 Image Edit (Same Ratio)` | 单图编辑保持原比例 | 通用编辑（最快） | 1 图 + 指令 → 编辑图 | 家族当前最优，未过时 | ⚪（KV 模型在位，未建单图模板） |
| `1c 1 Image Edit (Custom Ratio)` | 单图编辑自定义输出比例 | 原图转竖版/横版 | 1 图 + 比例 + 指令 → 编辑图 | 未过时 | ⚪（同上） |
| `1i 1 Image Edit Inpaint` | 蒙版局部重绘（Extend Factor 带上下文） | 加项链等局部增删 | 1 图 + 蒙版 + 指令 → 局部改图 | 未过时 | ⚪（同上） |
| `1o 1 Image Edit Outpaint` | 灰条扩图 | 改画幅、加背景空间 | 1 图 + 目标比例 → 扩展图 | 可用；EP27 专用外绘 LoRA（原图像素级不动）更强 | ⚪（外绘走 EP27 模板） |
| `2 2 Images Edit` | **双图合成**（虚拟试衣/Logo 融合） | 人物图+服装图、主体+标志 | 2 图 + 指令 → 合成图 | 多图合成主力之一 | 🟢（`flux2_klein_4ref`） |
| `3 3 Images Edit` | **三图合成** | 多素材融合定妆 | 3 图 + 指令 → 合成图 | **定妆主力（2026-10-14 已确认保留）**——头像+衣服+背景；模型已在实例，0 下载 | 🟢（`flux2_klein_4ref`） |
| `4 4 Images Edit` | 四图合成 | 多人/多物组合 | 4 图 + 指令 → 合成图 | 图越多错误越多（手部尤甚） | 🟢（`flux2_klein_4ref`） |
| `5 Image Blend` | 预合成+环境统一（先摆位，AI 统一光影） | 产品融景、多主体精确排布 | 多图 + 布局 → 融合成品图 | 未过时 | ⚪（模型在位，未建模板） |

## 第 10 课 · Fish Audio S2 文本转语音

> 本地 FP8 语音模型。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `Fish S2 TTS` | 基础 TTS（带标签控制情绪/停顿） | 通用配音 | 文本 → 语音 | 仍有效 | ⚪ |
| `Fish S2 Voice Clone TTS` | 声音克隆 | 10-30s 参考克隆声线 | 参考音频 + 文本 → 克隆语音 | 仍有效 | ⚪ |
| `Fish S2 Multi-Speaker TTS` | 最多 10 人多说话人 | 有声书、多人剧 | 多参考 + speaker 标签文本 → 对话音频 | 10 人多说话人为其独有能力 | ⚪ |

> AutoDL：节点包已装、模型未下；许可证不允许商用，项目已决定不采用。

## 第 11 课 · Pixaroma Nodes 自定义节点（第一代）

> 迷你图层编辑器/画笔/3D 构图集成进 ComfyUI。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `Image Composer Pixaroma Workflow` | 迷你图层编辑器（去背/摆位/旋转/擦除） | 精确排版后交 AI 融合 | 多图 → 排版合成图 | 节点已多轮迭代（至 EP37 时代），UI 与演示或有出入，思路不变 | ⚪ |
| `Paint Pixaroma Workflow` | 画笔/形状占位标记 | 指定新增物位置尺度 | 图 + 涂画 → 带占位图 | 同上 | ⚪ |
| `Flux 2 Klein ... with Paint Pixaroma Node` | Paint 占位 + Klein 编辑联动 | 空间受控的加物编辑 | 1 图 + 占位 + 指令 → 编辑图 | 同上；编辑底座建议换 EP09 KV 版 | ⚪ |
| `3D Builder Pixaroma Workflow` | 内置 3D 构图（相机/比例/网格） | 建筑/道具构图预演 | 3D 场景 → 参考渲染图 | 同上 | ⚪ |
| `Crop / Labels / Image Compare` | 裁剪 / 标注 / 对比工具节点 | 辅助处理 | 图 → 处理图 | 工具节点持续可用 | ⚪ |

> AutoDL：Pixaroma 节点包已装（v1.4.206），工作流未部署；Klein 联动底座实例上是 KV 版。

## 第 12 课 · Vibe Code 自定义节点（无工作流目录）

> 用 Claude Desktop 在节点包目录内生成 Python+JS 自定义节点的编程课。产物是节点包本身，无分发工作流。（2026-07 批）

**时效备注**：方法论不过时——用编码 Agent 写自定义节点仍是当前做法（与本项目的 agent 工作流同思路）。

## 第 13 课 · Pixaroma Nodes 更新 2

> Composer/Paint/3D Builder 与 Klein 9B 联动。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `1 Image Composer - Flux Klein 9B` | Composer 排版 + Klein 融合 | 多对象精确摆放合成 | 多图 + 布局 → 融合图 | 节点 UI 已继续演进，工作流文件仍可加载 | ⚪ |
| `2 Paint - Flux Klein 9B` | 草图引导编辑（新版 Paint） | 局部加物/构图控制 | 图 + 草图 + 指令 → 编辑图 | 同上 | ⚪ |
| `3 3D Builder - Flux Klein 9B` | 3D 构图 + Klein 材质化 | 透视匹配的场景加物 | 3D 参考 + 背景图 → 成品图 | 同上 | ⚪ |
| `Crop / Labels / Image Compare / 3D Builder / Image Composer / Paint`（基础版） | 同第 11 课工具节点更新版 | 辅助处理 | 图 → 处理图 | 工具节点持续可用 | ⚪ |

> AutoDL：同第 11 课——节点包已装，工作流未部署。

## 第 14 课 · Ernie 模型 + 新节点

> Ernie Turbo 评测 + Note 富文本节点。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `Ernie Image Turbo GGUF t2i` | Ernie Turbo 文生图（GGUF 低显存） | 含文字版式生成尝试 | 提示词 → 图像 | Ernie 影响力有限，非主力；文字设计已有 EP37 Ming 更优 | ⚪（Ernie 未部署） |
| `Note Pixaroma Workflow` | 富文本工作流内笔记（模型清单/参数/链接） | 复杂工作流自说明 | 无 → 文档 | Note 节点仍在用，未过时 | ⚪（Note 节点随 Pixaroma 包可用） |
| 附 `prompts.txt` | 图像提示词完整示例集 | 提示词参考 | — | 静态资料 | — |

**时效备注**：本课最有价值的遗产是"先查分辨率甜点区再改提示词"的诊断思路，对任何新模型通用。

## 第 15 课 · 图像随音乐动（ACE-Step）

> 音乐生成 + 图像节奏动画。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `Acestep v1.5 xl Turbo Text to Music` | ACE-Step 文生音乐 | 免费本地配乐 | 描述文本 → 音乐 | 音乐生成已有更新方案（EP31 Music 3） | —（Mac 侧管线） |
| `AudioReact Workflow` | 单图随音频节拍做 2D 变换 | 静态图转节奏短视频 | 1 图 + 音频 → 音乐反应视频 | 2D 变换用途受限（无角色动作）；不适合舞蹈类内容 | ⚪ |

> AutoDL：不经实例——本项目音乐生成走 Mac 侧 ACE-Step 管线（`lib/treeelf_music.py`）。

## 第 16 课 · Qwen 3.5 提示词 + Align Tool

> 文本扩写/图像反推 + 画布对齐工具。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `Qwen 3.5 - Text 2 Prompt` | 文本扩写为详细提示词 | 短想法→长提示词 | 短文本 → 提示词 | 提示词链路已被 EP18 Gemma 4 节点族扩展 | ⚪ |
| `Qwen 3.5 - Image 2 Prompt` | 图像反推提示词 | 从参考图取提示词 | 图 → 提示词 | 同上 | ⚪ |
| `Flux Klein 9b txt2img` | Klein 文生图（接受上述提示词） | 生成 | 提示词 → 图像 | 编辑底座建议换 EP09 KV 版 | ⚪ |
| `Flux Klein 9b + Qwen 3.5 - txt2prompt2img` | 文本→提示词→图 一条龙 | 自动扩写生成 | 短文本 → 图像 | 同上 | ⚪ |
| `Flux Klein 9b + Qwen 3.5 - img2prompt2img` | 图→提示词→新图 | 图像变体 | 图 → 相似新图 | 同上 | ⚪ |

> AutoDL：未部署——Qwen3.5 LLM 不在实例，提示词扩写由 Agent 承担；Klein 生成底座实例为 KV 版。

**时效备注**：Align Tool 画布吸附功能与课程无关模型演进，仍有效。

## 第 17 课 · 新版 Load Image + 实用节点

> Load Image 集成导入/裁剪/缩放/日期目录。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `Flux 2 Klein 9B - One Image Edit V1` | 基准单图编辑 | 对照基准 | 1 图 + 指令 → 编辑图 | 编辑底座建议换 EP09 KV 版 | ⚪（KV 模型在位） |
| `V2 + Notify and Switch` | 编辑完成系统通知 + 尺寸分支切换 | 无人值守时提醒 | 同上 + 通知 | 实用节点仍有效 | ⚪（同上） |
| `V3 + Get filename and Export in Today Folder` | 按原文件名存入日期目录 | 批量处理归档 | 图 → 日期目录文件 | 实用节点仍有效 | ⚪（同上） |

> AutoDL：未建模板——KV 模型在位，需要时可现场转；通知/归档节点随已装节点包。

## 第 18 课 · Gemma 4 提示词节点全家桶

> 提示词工程节点化。（2026-07 批后期）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 | AutoDL |
|---|---|---|---|---|---|
| `01a Prompt Enhancer`（+01b 接 Z-Image） | Gemma 扩写提示词（可接生图） | 提示词增强 | 短文本 → 长提示词（→图） | **当前提示词主力封装**，未过时 | ⚪ |
| `02a Image to Prompt`（+02b 接生图） | 图像反推 | 参考图取词 | 图 → 提示词（→图） | 未过时 | ⚪ |
| `03 Audio to Text` | 音频转写 | 语音取文本 | 音频 → 文本 | 未过时 | ⚪ |
| `04a Video to Prompt / 04b Video to Description` | 视频反推提示词/描述 | 视频拆解 | 视频 → 提示词/描述 | 未过时 | ⚪ |
| `05 Switch Node` | 条件切换 | 流程分支 | 值 A/B → 选定值 | 工具节点 | ⚪ |
| `06 Prompt Stack`（+06b 接生图） | 模块化提示词堆栈 | 反复组合提示词元素 | 多段文本 → 组合提示词 | 未过时 | ⚪ |
| `07 Prompt Pack Line/Paragraph`（+接生图版） | 按行/空行批量排队提示词 | 批量生成任务 | 多行文本 → 逐条执行 | 未过时 | ⚪ |
| `08 Prompt Multi From List / Queue Text`（+接生图版） | 列表/队列多提示词路由 | 分步编辑路由 | 列表文本 → 索引取值 | 未过时 | ⚪ |
| `09 Read Prompt From Image` | 读图像内嵌提示词元数据 | 复用历史提示词 | 图 → 提示词 | 未过时 | ⚪ |
| `10 Text Overlay`（+10b 接生图） | 图上叠字 | 标注/封面 | 图 + 文本 → 叠字图 | 未过时 | ⚪ |
| `11 Remove Image Background` | 去背景（轻量） | 抠图 | 图 → 去背图 | 未过时 | ⚪ |
| `12 Change Node Color / Z-Image txt2img` | 节点着色工具 / 基准生图 | 辅助 | — | 工具节点 | ⚪ |

> AutoDL：未部署——Gemma 4 模型不在实例；提示词扩写/反推由 Agent 侧完成（SA3 方案同此取舍）。

## 第 19 课 · Stable Audio 3 音乐音效

> 本地音乐/音效生成。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `txt2audio` | 文本→音频（1-380s） | 音效/短乐 | 描述 → 音频 | 仍有效 |
| `txt2music with Gemma 4` | Gemma 扩写→音乐 | 详细配乐 | 短文本 → 音乐 | 仍有效；最新音乐方案为 EP31 Music 3 |
| `txt2sound with Gemma 4` | Gemma 扩写→音效 | 详细音效 | 短文本 → 音效 | 仍有效 |
| `img2music with Gemma 4` | 图像→音乐描述→音乐 | 插画配乐 | 图 → 音乐 | 仍有效 |

## 第 20 课 · Anima Base / Microsoft Lens / Pause Image

> Anime 标签生成 + Lens 模型 + 人工检查点。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `Anima Base v1.0 txt2img` | Anime 标签化生成 | 二次元图 | 标签提示词 → 图像 | 小众；二次元需求时用 |
| `+ Gemma 4 Anima Prompt Enhancer` | Gemma 自动打标签 | 不熟 anime 标签 | 文本 → 标签提示词 | 未过时 |
| `+ SeedVR2 Upscale` | 生成+超分一条龙 | 高清出图 | 提示词 → 高清图 | 未过时 |
| `Lens txt2img` | Microsoft Lens 模型生成（1440 甜点区） | 干净少伪影多样化 | 提示词 → 图像 | 小众 |

**时效备注**：本课的 Pause Image"人在回路检查点"思路被后续课（EP20 Pause Text、EP28）广泛复用，长期有效。

## 第 21 课 · XY Plot 参数实验

> 双轴网格系统调参。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `Z-Image txt2img + XY Plot` | 双轴网格遍历（提示词/尺寸/采样器/步数…） | 系统找最优参数组合 | 2 组变量值 → m×n 网格图 | 通用方法论，长期有效、调参必备 |
| `+ Gemma 4 + Find and Replace` | 提示词扩写+查找替换派生变体 | 变体批量生成 | 文本 → 变体网格图 | 未过时 |

## 第 22 课 · Inpaint 与文件夹批处理

> 局部重绘流程化 + 批量遍历。（2026-07 批）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `Flux Klein 9b Inpaint` | 裁切-生成-拼回局部重绘（Color Match/Softness 接缝控制） | 换帽子/服饰局部替换 | 图 + 蒙版 + 指令 → 局部改图 | 仍有效；EP36 也有 Inpaint（Turbo 约 3s）可对比 |
| `Flux Klein 9b + Load Images from Folder` | 文件夹遍历逐图跑同一工作流 | 批量编辑 | 文件夹 → 批量结果 | 批处理思路长期有效 |
| `Load Images from Folder + Crop` | 批量裁剪 | 尺寸归一化 | 文件夹 → 批量裁剪图 | 同上 |

## 第 23 课 · SCAIL 2 动作迁移 + 循环节点

> SCAIL 2 代 + Group/Loop 工程化。（2026-07 批后期）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `Scail 2 Video - Compact / Long` | SCAIL 2 动作迁移视频（紧凑版/可延长版） | 角色模仿参考动作（更长时长的舞蹈/表演） | 角色图 + 动作参考视频 → 视频 | **动作迁移备选路线**（与 EP06 Wan Animate 并行）；适合长时长 |
| `Loop Pixaroma - Build a List / Image Batch / Carry Two Values` | 多值循环节点（配合分段生成累积帧） | 短片段模型产出长视频 | 迭代值 → 累积结果 | 通用工程化节点，长期有效 |
| `Combine Pixaroma - Join Two Images` | 图像合并节点 | 辅助 | 2 图 → 合并图 | 工具节点 |
| `Group Compare - ComfyUI vs Pixaroma` | 折叠分组对比演示 | 画布管理 | — | 工具演示 |

## 第 24 课 · Krea 2 文生图（质量提升）

> Krea 2 FP8 全家桶。（2026-07 批后期）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `1a Text to Image - Simple`（+1b LoRA / 1c Enhancer / 1d Low Vram） | Krea 2 FP8 基础文生图及变体 | 高质量写实生成 | 提示词 → 图像 | **课程时最新写实模型，仍为文生图主力**（本项目定妆 lookA 用的同系） |
| `2a + Extra Pass`（+2b LoRA / 2c Enhancer） | 双 KSampler：首采后 latent 放大二次采样 | 2K 细节增强 | 提示词 → 高细节大图 | 未过时 |
| `2d - 2K` | 直接 2K 输出 | 大尺寸需求 | 提示词 → 2K 图 | 未过时 |
| `3u ... (Uncensored)` 三件 | 无审查版（Simple/2K/Extra Pass+Enhancer） | 规避内容过滤 | 提示词 → 图像 | 未过时 |

## 第 25 课 · INT8 提速（Boogu/Krea2/Z-Image）

> INT8 量化提速对照。（2026-07 批后期）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `Boogu/1 Text to Image`（+2 Enhancer） | Boogu INT8 文生图（保构图加物强） | 提速生成 | 提示词 → 图像 | 提速路线仍有效 |
| `Boogu/3 Edit - One Image` | Boogu 单图编辑 | 保持位置的原位编辑 | 1 图 + 指令 → 编辑图 | 编辑主力建议 EP09/EP36 |
| `Flux 2/1 txt2img / 2 One Image Edit / 3 Inpaint` | Klein INT8 三件套 | 编辑提速对照组 | 同 Klein 对应工作流 | 同上 |
| `Krea 2/1-6`（Simple/Enhancer/FromImage/ExtraPass 组合） | Krea 2 INT8 六件套 | 质量速度权衡 | 提示词（或图）→ 图像 | 仍有效 |
| `Z-Image/1 txt2img` | Z-Image INT8 | 极速生成 | 提示词 → 图像 | 仍有效 |

## 第 26 课 · 在线训练 Krea 2 LoRA

> FAL.ai 在线训练 + 本地使用。（2026-07 批后期）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `Krea 2 Lora Converter` | FAL 训练 LoRA → ComfyUI 兼容格式转换 | 在线训练产物本地化 | LoRA 文件 → 兼容 LoRA | 依赖 FAL.ai 生态，仍可用 |
| `Text to Image - Simple + Lora`（+ XY Plot 版） | Krea 2 挂自训 LoRA / 强度网格扫描 | 人物/风格 LoRA 验收 | 提示词 + LoRA → 图像/网格图 | 未过时 |
| `+ Extra Pass + Lora` | 二次采样 + LoRA | 高细节风格化 | 同上 → 大图 | 未过时 |

**时效备注**：FAL.ai 为付费在线训练服务，价格与界面可能随时变动，用前核实；本项目**任何付费训练需先获用户批准**。

## 第 27 课 · Outpaint 外绘

> 专用外绘 LoRA。（**2026-10 新批**）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `Flux 2 Klein 9B Outpaint` | 专用外绘 LoRA + 灰条扩展 + 原图贴回 | 改画幅且原图像素级不动 | 1 图 + 目标比例（+提示词）→ 扩展图 | **当前最优外绘方案**（优于 EP09 的 1o）；可提示词控制新增内容、feather/color match 修接缝 |

## 第 28 课 · 提示词标签库 + Pause Text

> 提示词资产化。（**2026-10 新批**）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `prompt-tags example library` | 标签库示例（@ 插标签 /* 随机类别 / # 列表取值） | 提示词资产管理 | 标签库 → 组合提示词 | 资产化思路长期有效 |
| `Krea 2 Text to Image`（+ Enhancer / From Image） | Krea 2 生成（Enhancer 版含 Pause Text 人工审改提示词） | LLM 提示词人工把关 | 文本/图 → 图像 | 未过时 |
| `Prompt from Image` | 独立图反推提示词 | 接任意生图工作流 | 图 → 提示词 | 未过时 |

## 第 29 课 · MiniMax H3 视频全家桶

> H3 视频模型。（**2026-10 新批**）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `Text to video`（含 Low VRAM 8GB 版） | 文生视频（含音频） | 快速出片 | 长提示词 → 含音频视频 | 课程时最新视频模型；**许可证排除欧盟/英/韩/美（中国大陆可用）**；fl2va 与 ref2va 两类模型不可混用 |
| `Image to video FF / LF / FFLF` | 首帧 / 尾帧 / 首尾帧生视频 | 指定起点/终点/转场 | 1-2 图 + 提示词 → 视频 | 同上；推荐 pruned INT8 版 |
| `Reference Two/Three Images` | 多参考图生视频（不锁帧） | 角色换装/换场景新内容 | 2-3 参考图 + 提示词 → 视频 | 同上；9 图模式实测极慢，慎用 |
| `Reference Image + Audio Sync - SING / SPEAK` | 参考图 + 音频对口型（唱/说） | 数字人唱说 | 角色图 + 音频 → 对口型视频 | 同上；提速见 EP32 |
| `Text to image / Image Edit` | H3 顺带出图/小编辑 | 快速图 | 提示词/图 → 图像 | 小众用法 |

## 第 30 课 · Krea 2 Edit + 本地 H3 提示词

> Edit LoRA 编辑 + 本地提示词生成。（**2026-10 新批**）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `Krea 2 + Edit Lora`（+ Custom Ratio / Character and Background） | **Edit LoRA 实现编辑**（Reference Boost 权衡身份与自由度） | 换装/换背景保身份 | 1 图 + 指令 → 编辑图 | **过渡方案**——官方 Krea 2 编辑模型未发布；本项目定妆阶段 1a/1b 已用同源用法 |
| `Krea 2 + One Image Outfit Lora / Outfit Transfer 2` | 服装迁移（服装图+角色描述 或 双图） | 虚拟试衣 | 角色图/描述 + 服装图 → 试穿图 | 本项目已用（lookA 服装迁移）；服装图最好只含服装本身 |
| `H3 Video Prompt Generator（T2V/FF 两版）` | 本地 Qwen 8B 生成 H3 结构化长提示词 | 免 ChatGPT 批量备提示词 | 短想法 + 时长 → H3 长提示词 | 与 EP29/32 配套；不如 ChatGPT 聪明但免费本地 |

## 第 31 课 · MiniMax Music 3 + 本地提示词生成

> Music 3 音乐 + AI Prompt 节点。（**2026-10 新批**）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `Text to Music` | Music 3 文生音乐（caption+lyrics 双输入） | 完整歌曲 | caption + 歌词 + 时长 → 音乐 | **当前最新音乐方案**；时长是上限，歌词越多歌越长 |
| `Caption and Lyrics Generator` | 本地 4B 模型生成 caption+lyrics | 自动写歌 | 想法 + 时长 + mode → 两段提示词 | 与上配套 |
| `Krea 2 Text to Image + Prompt Enhance / From Image` | AI Prompt 节点版生成 | 提示词增强生图 | 文本/图 → 图像 | EP03 方法论的节点化落地，取代手工版 |
| `Z-Image Turbo + Prompt Enhance` | 同上 Z-Image 版 | 快速增强生成 | 文本 → 图像 | 同上 |

## 第 32 课 · H3 加速 LoRA + 显存监控

> H3 提速必配。（**2026-10 新批**）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `Text to Video + Speed Lora` | 加速 LoRA：20 步→8 步、shift 12→6（5s 约 55s 出片） | H3 提速 | 提示词 → 视频 | 4 步最快但音频常变差；**与 EP29/35 配套必装** |
| `Image to video FF / FFLF + Speed Lora` | 首帧/首尾帧提速版 | 同上 | 图 + 提示词 → 视频 | 同上 |
| `Audio Sync SING/SPEAK + Speed Lora` | 唱/说提速版（4 步即可） | 对口型提速 | 图 + 音频 → 视频 | 同上（不生成音频时 4 步够用） |

## 第 33 课 · 图生 3D（Trellis 2 / Pixal3D）

> 图生 3D 基础。（**2026-10 新批**）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `1 Trellis 2 - Low VRAM` | 图生 3D 基础版（带颜色，最快） | 快速占位模型（6G 卡可跑） | 1 图 → GLB 模型 | 图生 3D 领域演进极快，模型可能已有更新版，流程概念仍准 |
| `1.2 - High VRAM` | 同上高显存档 | 更快更稳 | 1 图 → GLB | 同上 |
| `2 - HQ + PBR Textures` | 高面数+PBR 纹理 | 游戏资产 | 1 图 → 带纹理 GLB | 同上；24G 卡 2 分钟+，6G 卡约 40 分钟 |
| `3 Pixal3D - Low VRAM` | **保持原图相机角度**的图生 3D | 视角必须一致 | 1 图 → GLB | 同上 |
| `4 Pixal3D - HQ + PBR` | Pixal3D 纹理版（最慢） | 角度+纹理都要 | 1 图 → 带纹理 GLB | 同上；6G 卡首次可超 2 小时 |
| `5 Flux Klein 9b - 3D Model to Image` | 3D 模型当前视角秒级渲染成图 | 换材质/背景出概念图 | GLB + 提示词 → 渲染图 | 必须方形比例 + fit to viewer 否则错位 |
| `6 - Keep the Angle` | denoise 0.7-0.8 局部细节放大 | 保角度精修 | GLB + 特写 → 渲染图 | 未过时 |

## 第 34 课 · Pixal3D 多视角重建

> 四视角精确重建。（**2026-10 新批**）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `1 Multi-View - No colours`（+2 HQ） | 正/背/双侧四视角→准确几何 | 有多视角图时的精确重建 | 4 图 → GLB | 领域演进快；网格孔洞/破边靠换 seed + Photoshop 补 |
| `3 - Model + Colours` | 带顶点色 | 带底色模型 | 4 图 → 带色 GLB | 颜色呈涂抹感（三角形填充），打底用 |
| `4/5 - PBR Textures LQ/HQ` | 带纹理（HQ 最慢最准） | 展示级外观 | 4 图 → 带纹理 GLB | HQ 版 24G 卡 2 分 41 秒 |
| `6/7 Flux Klein - 3D to Image`（+Keep Angle） | Load 3D 节点加载任意 GLB 渲染 | 自有模型出图 | GLB → 渲染图 | 方图最稳 |

## 第 35 课 · MiniMax FastH3 快速视频

> H3 快速版。（**2026-10 新批**）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `1 Text to Video` | FastH3 文生视频（5s 小尺寸 44-53s 出片） | 快速迭代 | 长提示词 → 含音频视频 | **当前最快视频方案**；分辨率对速度影响 > 秒数 |
| `2 FirstFrame to Video` | 首帧生视频 | 指定角色动起来 | 1 图 + 提示词 → 视频 | 同上；15s 以上音频会乱 |
| `3 First and Last Frame` | 首尾帧转场 | 两图间过渡/换装对照 | 2 图 + 提示词 → 转场视频 | 换装前后对照可用；转场不一定成功需实测 |

## 第 36 课 · Qwen Image 2.1（**编辑强项，多图合成另一主力**）

> 编辑与多图参考。（**2026-10 新批**）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `1/1 文生图` 7 件 | 文生图全家桶 | 生成与透明素材 | 提示词 → 图像 | 文生图不如 Krea 2；**许可证非商业** |
| `2/1 单图编辑` 11 件 | 单图编辑套件（Turbo 约 3s） | 加物/改色/多视角角色表/抠图/扩边 | 1 图（+蒙版/草图）+ 指令 → 编辑图 | **当前编辑主力之一**；编辑都是重生成相似新图，非逐像素保留 |
| `3/1 Outfit Change`（+9 Turbo） | **换装**（人物图+服装图） | 虚拟试衣 | 2 图 + 指令 → 试穿图 | 与 EP09 双图版、EP30 outfit LoRA 三选一对比 |
| `3/2 Logo on a Product` | 产品贴 Logo | 品牌样机 | 产品图 + Logo 图 → 贴标图 | 未过时 |
| `3/3 Character in a Scene` | 角色入景 | 置换背景 | 人物图 + 场景图 → 合成图 | 未过时 |
| `3/4 Pose from a Picture` | 姿势复制 | 姿势迁移 | 人物图 + 姿势图 → 迁移图 | 未过时 |
| `3/5 / 3/6 三图/四图合成` | 多图参考合成 | 多素材融合 | 3-4 图 + 指令 → 合成图 | **本项目定妆的对比方案**（与 EP09 三图版对照） |
| `3/7 Group Photo from 6 Images` | 六人合影 | 多人合成 | 6 图 + 指令 → 合影 | 图越多错误越多（比例失调、头部变大） |
| `3/8 Two Image Edit + Enhancer` | 双图编辑+提示词扩写 | 复杂双图任务 | 2 图 + 短指令 → 合成图 | 未过时 |

## 第 37 课 · Ming Image 0.1（免费设计文字模型）

> 设计文字模型。（**2026-10 新批**）

| 工作流 | 功能 | 适用场景 | 输入 → 输出 | 备注 |
|---|---|---|---|---|
| `1/1 Text to Image` | 三步文生图 | 基础设计生成 | 提示词 → 设计图 | MIT 许可、<6GB；0.1 早期版本迭代快，可能有新版 |
| `+ Prompt Enhancer` | 提示词增强版 | 长提示词 | 短文本 → 设计图 | 同上 |
| `3 Transparent PNG` | 透明背景输出 | 贴纸/图标素材 | 提示词 → 透明 PNG | 大尺寸约 9/10 成功，小尺寸去背不稳 |
| `4 YouTube Thumbnail / 9 Event Poster / 8 Infographic` | 缩略图/海报/信息图预设 | 对应设计场景 | 提示词（JSON 更准）→ 设计图 | 未过时 |
| `5 Logo Design / 11 Logo Variations` | Logo 设计/多变体 | Logo 草案探索 | 提示词 → Logo 图组 | Logo 精度作者认为 ChatGPT 更准 |
| `6 App and Website Screens / 7 Game Screens` | 界面/游戏屏生成 | UI 概念稿 | 长提示词 → 界面图 | 未过时 |
| `10 Social Media Post / 5 Social Media Pack` | 社媒图/多尺寸套图 | 一图多比例 | 提示词 → 套图 | 未过时 |
| `12 3D Lettering` | 3D 字设计 | 标题字 | 提示词 → 3D 字图 | 未过时 |
| `2/1 Image Edit / 2 Sketch to Photo / 3 Restyle 3D / 4 Product Ad Two Pictures` | 编辑/草图转照片/转 3D 风/双图产品广告 | 设计修改与合成 | 图（1-2 张）+ 指令 → 成品图 | 写实类编辑易出怪纹理——写实仍用 Krea 2 |

---

## 备注

1. **本项目（dance-video）已使用/计划使用**：Ep09 Klein 9B KV（**定妆主力，2026-10-14 确认保留**，模型已在实例 0 下载）、Ep06 Wan 2.2 Animate · Replace Character and Background（动作迁移 A 方案，已实测，**2026-10-14 B 方案直接选定后降为回退备选、模型链路转删除候选**）、**B 方案 Wan-Animate-2**（非课程，官方蓝图就绪，权重已全部在位并通过校验，**2026-10-14 用户直接选定、不做对比测试**）、Ep30 Krea 2 outfit transfer（已用于 lookA）、Ep05 SeedVR2（视频超分备用）、Ep08 SAM3（已用于抠像，因拼装感将弃用程序式链路）。
2. 付费 API 工作流（文件名含 PAID/credits、FAL/RunningHub 云端）走外部计费，**使用前需确认成本并获用户批准**。
3. 工作流 JSON 内模型路径为 Windows 反斜杠（如 `flux2\`），在 Linux 实例提交前须改正斜杠。
4. 各课视频原片、字幕与关键帧证据见课次笔记；本索引只做工作流层面导航。
5. 许可证要点：MiniMax H3 排除欧盟/英/韩/美（中国大陆可用）；Qwen Image 2.1 非商业；Ming Image MIT；Krea 2/Z-Image 常规。

---

## AutoDL 重新整理决策（2026-10-14）

> **2026-10-15 更新：用户已放弃 AutoDL 平台**（原话"我已经放弃autoDL了"）。本节转为历史记录；下表"实例"语境作废——模型底座全部转 duolaiduo 权威备份，约 100G 删除任务取消（整平台弃用后逐件删除无意义，将来控制台直接释放实例即全清）。三产线工作流清单见下一节。

**保留的工作流（舞蹈链路核心；2026-10-14 用户直接选定 B 方案，不做 A/B 对比测试）**：

| # | 工作流 | 生产模板 | 状态 |
|---|---|---|---|
| 1 | EP09 FLUX.2 Klein 9B KV 多图合成（定妆） | `flux2_klein_4ref` | 🟢 模型已在实例（0 下载），GPU smoke 通过 |
| 2 | A 方案：EP06 Wan 2.2 Animate · Replace Character and Background | `wan22_animate_character` | 🟡 降为回退备选（B 方案选定）；独占模型 ≈30G 转删除候选，duolaiduo 7 月备份全含 |
| 3 | **B 方案：Wan-Animate-2（非课程，官方蓝图）** | 待建 | 🟢 **选定**：权重四件全在实例、SHA-256 全通过（2026-10-14 无卡会话核查+补齐）；下次 GPU 会话建模板+smoke 后投产 |

**本次清理的过时 AutoDL 标注**（对照代码注册表核实，见上表 ❌ 项）：
- `wan22_i2v_q6` 旧图生视频链路——2026-10-12 已从注册表删除（改 FastH3），文档标注同步清除；
- InfiniteTalk 短口型链路——同日删除（改 `minimax_h3_audio_sync`），仅延长版 `wan_infinitetalk_extend` 保留（模型冷存、仅显式调用）；
- EP09"待批准 18.8G 下载"为旧报价错误，实际模型已在实例、0 下载，已修正。

其余 16 条注册模板（配音 4 + 生图/图片处理 8 中的 7 + 视频 5）服务其他产线（哲学/寓言视频、公众号配图），不在本次舞蹈链路整理范围内变动。

---

## 三条产线工作流清单（跳舞 / 短剧第一步 / 短剧第二步，2026-10-15）

> **与平台解绑**：工作流 JSON 与注册表全在本地 OpenMontage repo（零成本保留）；全部模型件在 duolaiduo 家庭服务器有权威备份（`production-planning/AUTODL_DUOLAIDUO_MODEL_BACKUP_2026-10-14.tsv` + 7 月暖库 153 文件）。将来在任意 GPU 平台或本地机器重装即可恢复生产，恢复优先 hf-mirror 直下（约半小时/60G），duolaiduo 兜底。
> 模型底账：`production-planning/COMFYUI_MODEL_INVENTORY.tsv`；随时算账：`python3 tools/_comfyui/model_footprint.py <预设或模板key>`（共享件自动去重、备选件不计入）。

### 产线一：跳舞（换装舞蹈视频）——12 件 / 59.8 GiB

流程：角色定妆 → 换装 B/C 造型 → 动作迁移 → 本地剪辑配乐。

| 步骤 | 工作流 | 所需模型件 | 小计 |
|---|---|---|---|
| ① 定妆（角色基准） | `flux2_klein_4ref`（四参考图合成） | klein-kv 9.1G + qwen_3_8b 8.1G + flux2-vae 0.3G | 17.5G |
| ② 换装造型 | `krea2_outfit_transfer` | krea2-int8 12.6G + heretic 4.5G + qwen_image_vae 0.2G + 换装 LoRA 1.1G | 18.4G |
| ③ 舞蹈动作迁移 | **B 方案 `wan_animate2`**（Wan-Animate-2，**模板待建**，官方蓝图已就绪；新平台落地时建模板 + smoke 后投产） | wan_animate_2 15.5G + umt5_scaled 6.3G + Wan2_1_VAE 0.2G + lightx2v 0.7G + clip_vision_h 1.2G | 23.9G |
| ④ 剪辑配乐 | 本地 Remotion + ACE-Step | —（本地 CPU） | 0 |

### 产线二：短剧第一步（图 + 配音，《怕白光的人》型 3 分钟短剧）——12 件 / 74.7 GiB

流程：定妆 → 空镜/正文生图 → 全片配音 → 本地拼接。在跳舞基础上：换装 LoRA 不需要（−1.1G），加 Qwen3-TTS 包（+16G）。

| 步骤 | 工作流 | 所需模型件 | 小计 |
|---|---|---|---|
| ① 定妆（四视图） | `flux2_klein_4ref` | 同跳舞①（**现定妆照为三视图，需改四视图**才能喂 4ref） | 17.5G |
| ② 空镜/正文生图（68 镜头） | `krea2_low_vram`（默认生图路由；生图引擎为 Krea 2——Qwen Image 2.1 因非商业许可证不进路由） | 与②跳舞共享 krea2 三件 | 0 新增 |
| ③ 全片配音 | `qwen3_tts_custom_voice`（声线 `treeelf_cherry` 三件套本地有备份，`voice_clone_load` 复用） | qwen-tts 16G 包（Base + CustomVoice + speech_tokenizer） | 16G |
| ④ 拼接 | 本地 Remotion | — | 0 |

**合计 = 59.8 − 1.1（换装 LoRA）+ 16（TTS）= 74.7 GiB**（与跳舞并行时共享 11 件）。

### 产线三：短剧第二步（爆点场视频化）——6 件 / 62.0 GiB

流程：第一步静帧 → 爆点场动态化 / 说话镜头口型。H3 全家与第一/二步**零共享**。

| 步骤 | 工作流 | 所需模型件 | 小计 |
|---|---|---|---|
| ① 爆点场静帧动态化 | `minimax_fasth3_i2v`（首帧生视频、8 步、原生音频） | fasth3 基座 20.6G + qwen3vl_32b 14.6G + video_vae 4.9G + audio_vae 0.6G | 40.7G |
| ② 说话镜头口型（≤15s） | `minimax_h3_audio_sync` | 上四件 + ref2va 19.5G + fl2v LoRA 1.8G | 62.0G |
| 可选：首尾帧转场 | `minimax_fasth3_fflf` | 共享①四件 | 0 新增 |
| 可选：画面漂移修复 | `krea2_edit_lora` | 共享产线二 krea2 三件 + identity LoRA 1.7G | +1.7G |
| 备用：长独白 >15s | `wan_infinitetalk_extend` | 模型冷存 duolaiduo；恢复前先补核 infiniteTalk_single / wav2vec2 两件哈希 | ≈24G |

### 快速算账（共享件已去重）

| 场景 | 模型量 |
|---|---|
| 只跑跳舞 | **59.8 GiB**（12 件） |
| 只跑短剧（第一步 + 第二步） | **136.7 GiB**（18 件） |
| 三条产线全开 | **136.7 GiB**（18 件——跳舞是短剧第一步的子集，仅换装 LoRA 1.1G 被其替换） |

> 短剧第二步将来若不想重下 H3 62G，爆点场也可改走 B 方案 `wan_animate2`（动作迁移产线已含其全部模型）——但口型镜头仍只有 H3 Audio Sync / InfiniteTalk 两条路。

---

## 接下来的升级点(大白话版,2026-10-13 调研结论)

> 完整技术版在 `production-planning/UPGRADE_PLAN_2026-10-13_items-1-2-4.md` 和调研报告里;这里是能直接听懂的版本。

| # | 要升什么 | 大白话解释 | 状态 |
|---|---|---|---|
| 1 | **补音效** | 现在片子里只有"人声 + 背景音乐",缺"开门声、脚步声、雨声"这些环境音。加一个专门造音效的工具(Stable Audio 3,免费商用,课程 EP19 就有现成工作流) | ✅ 本轮在做 |
| 2 | **长说话镜头换代** | 人物一讲超过 15 秒,现在用的老技术(InfiniteTalk)画面放久了会"变脸、掉色"。换新一代(LongCat),能连讲几分钟不变样 | ✅ 本轮在做(新卡 24G 显存能不能跑,装好实测,不行就先不换) |
| 3 | **卡通动作升级** | 动画角色照着参考视频做动作的能力出了第 2 代(SCAIL-2,课程 EP23 在库),更省事质量更高 | ⏸️ 以后 |
| 4 | **配音加"表演"** | 现在的配音字正腔圆但感情平淡。加一条"表演轨"(IndexTTS-2.5),它能照着一段有感情的参考录音学着说,喜怒哀乐、强弱都能控制。先做出来你盲听对比,确实更好才用 | ✅ 本轮在做 |
| 5 | **背景音乐升级** | 现在的音乐工具(ACE-Step)出了 1.5 版,质量更好 | ⏸️ 等音效落地后再说 |
| 6 | **角色一致性外挂** | 谷歌有个按张收费的"改图神器"(Nano Banana 2.1),保人脸、改姿势特别强,约 3 毛~1.7 块一张,要科学上网+付费 | ⏸️ 有重要项目再试点 |
| 7 | **重头戏外包** | 遇到特别难的重点镜头(开场钩子、高潮戏),可以按条付费买云端顶级模型(Kling 4.0 / Seedance 2.5),30~60 块一条,自己的机器照旧 | ⏸️ 按项目决定 |
| 8 | **换显卡** | 现在的卡显存 24G 已经快装满了。下次扩产换 5090 32G(每小时只贵 1 块钱),空间就宽了 | ⏸️ 扩产时 |

另外两个"查过了但决定不动"的:**LTX-2 视频**(官方要求 32G 以上显存,咱跑不动,换卡后再看)和 **Fish 语音**(许可证不允许商用,不用)。
