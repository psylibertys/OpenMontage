---
name: zh-philosophy-video
description: Produce and maintain the reusable TreeElf Chinese philosophy/psychology vertical-video series from reviewed Markdown copy. Use when scanning the 心哲灵短视频文案 inbox, preparing the next unproduced article, generating narration with the saved 配音02 Qwen3-TTS clone, creating one text-free Krea cover plus realistic/abstract/style-fusion media and Wan motion, composing animated stills, exact Remotion information cards, outlined captions and audible music, delivering to Movies, or updating the source production status only after verified delivery.
---

# 树精灵中文哲思短视频

使用“稳定栏目配置 + 单篇配置 + 数据驱动 Remotion 组件”的持续生产链，不要为每篇重新发明流程。

## 唯一默认入口

稳定栏目配置：

`workflow_configs/zh-philosophy-video/treeelf-continuing-series-v1.json`

单篇模板：

`workflow_configs/zh-philosophy-video/treeelf-episode-template.json`

执行程序：

`scripts/treeelf_philosophy_episode.py`

批量 GPU 编排程序：

`scripts/treeelf_philosophy_batch.py`

通用合成组件：

`remotion-composer/src/TreeElfPhilosophyEpisode.tsx`

先验证、扫描、准备：

```bash
.venv/bin/python scripts/treeelf_philosophy_episode.py validate --config <episode.json>
.venv/bin/python scripts/treeelf_philosophy_episode.py scan --config <episode.json>
.venv/bin/python scripts/treeelf_philosophy_episode.py prepare --config <episode.json>
```

`prepare` 只快照原文，不修改原文状态。若原文已经是 `production_status: completed`，必须拒绝重复生产。`prepare` 同时生成 `artifacts/visual_brief.json`，记录本篇的情绪核心、隐喻候选、关键短句、三类视觉模式比例、风格来源和技术护栏；后续图片 prompt 必须能追溯到这份 brief 或 episode JSON 中更具体的人工覆盖。

## 锁定的栏目规范

- 画幅 1080×1920、30 fps、60–90 秒。
- 旁白使用服务器持久声包 `treeelf_voice02_v1`，模板 `qwen3_tts_voice_clone_load`。
- 按自然段生成旁白片段，再本地拼接、标准化；不要把整篇长文强塞进一次 TTS 请求。
- 每篇仅生成一张新的 Krea 无字封面背景；Remotion 添加中文标题、英文副标题和“树精灵”。
- 每篇至少生成 15 张图：1 张封面和 14 张正文图；正文图中 2 张只作为 Wan 参考帧，至少 12 张只作为动态静帧。
- 14 张正文图是最低基准而不是上限。根据审核后的旁白、Wan 和全屏信息页时间检查静态图有效可见时长；平均超过 6 秒时继续增加图片，短篇也不因时长较短自动减到 14 张以下。
- 每篇固定生成 2 个 Wan 镜头。选择策略为“开头钩子 + 最长且语义安全的核心画面”：W01 优先服务开头，W02 在精确字幕/scene 重排后，从可见时间最长、语义关键、运动安全的正文画面中选择。正文图不得重复作为多个静帧；启用 `wan_policy` 后，Remotion 会把被选中的静帧段替换为对应 Wan，并把旧 Wan 占位还原为普通静帧。
- Wan 生成时长默认 4 秒，上限 5 秒。即使一个画面在成片中停留 8–10 秒，也不按完整停留时长生成 Wan；由 Remotion 通过慢放、尾帧保持和轻微静帧动效延展。
- `canvas-design` 只负责艺术指导，Krea 负责无字执行，Remotion 负责准确文字。
- `cover-image-generator` 不参与。
- ComfyUI 图片和视频只负责无字主视觉；中文标题、英文副标题、Logo/栏目标识、字幕和其他可读信息由 Remotion 添加。无字、无 Logo、无水印、无伪字是技术护栏，不写进创意意象主体。
- 视觉目标按语义表达方式规划：叙事具象 10–20%、抽象意象 35–45%、风格融合转译 40–50%、Remotion 信息页 15–20%。比例是默认倾向，允许根据文案语义微调。
- 叙事具象：用具体场景表达句子，包括人物、地点、动作和物件。重点是“这件事像真实发生过”。
- 抽象意象：用象征物、空间关系、材质和光线表达句子。重点是“这句话在心理层面像什么”。硬规则：每个抽象元素必须对应一个文案概念。
- 风格融合转译：用一种或多种艺术语言，把文案中的情绪、隐喻、认知动作转译成几个风格相融合的画面。重点是“这篇文章如果变成一组艺术镜头，会长什么样”。硬规则：每个风格选择必须说明它和文案的关系。
- 抽象意象和风格融合转译不是完全互斥：很多风格融合图本身也会抽象。分类的意义在于生成时的主目标不同：抽象意象先想象征物，再想画面；风格融合先想艺术语言，再把语义转译进去。
- 每篇优先从 `art-Styles.md` 选择 2–3 个主风格语言并在镜头间变化组合；最多 4 个，第四个必须有清楚语义理由。风格多样性应服务文案，不做纯风格展示。
- 跨作品通过重新提取文案意象来减少醒目标志物的机械重复；某个元素是否出现，只由它和当前文案意象的匹配度决定。创意 prompt 用正向画面目标替代审美禁令。
- 每条片有 2–3 个 Remotion 动态信息页，总时长约 15–25%，用于比较、因果、步骤、提问或关键词。
- 静态图必须有可见而克制的推、移、纵向漂移或视差；连续静态镜头不得使用相同运动。
- 字幕为较小白字、黑色描边、透明底，不用黑色字幕框；默认使用较高的短视频平台安全区，`safe_bottom >= 360`，避免被底部标题、进度条和互动按钮干扰。
- 背景音乐锁定旁白优先的 B3 混音基准：Remotion `musicVolume = 0.30`，并按讲话状态更强 ducking；讲话时音乐应退到低氛围层，不压旁白。
- 背景音乐不再长期固定同一首。`stage-remotion` 通过 `workflow_configs/treeelf-music/catalog-v1.json` 按标题、正文情绪和意象关键词从中央本地纯音乐库自动选曲；心哲灵与 fable 共用跨批次使用账本，同批与近期曲目会降权。项目音乐副本标准化到 -18 LUFS / -2 dBTP，中央原曲不修改；选择、匹配原因、SHA、标准化结果写入 `artifacts/music_selection.json`。
- 音乐是否可听，以导出文件的人耳试听和响度结果判断，不以时间线参数代替。
- 独立平台封面与成片首帧使用同一封面；首帧只有 1 帧，不形成可感知片头。

## 正向提示词规则

- 配音提示词使用正向描述：成年女性普通话声线，中等音高，中速，清晰发音；整体活泼、温暖，有微笑语气；遇到更有趣或轻微幽默的内容时，可以自然轻笑，同时保持语义清楚和表达可信。
- 配音提示词始终围绕正向目标修正：自然分享、微笑语气、清晰发音、表达可信。
- 视觉创意 prompt 主要写“要什么”：语义锚点、情绪基调、隐喻来源、构图、材质、光线、色彩和艺术语言。
- 创意层通过语义匹配管理审美。红绳、门、裂纹、水、背影、光束等符号是否出现，取决于它们是否从本篇文案意象中自然长出，并能解释表达了什么。
- 技术层可保留最小必要护栏：无可读文字、无 Logo、无水印、无伪字；该护栏作为 `technical_guardrails` 或 workflow 级规则存在，不替代创意描述。
- 生成前必须扫描正文图和 Wan prompt 的伪文字诱因。`phrase`、`sentence`、`note`、`notebook`、`page`、`document`、`tag`、`label`、`form`、`letter`、`typography`、`editorial layout`、`idea table` 等文字容器词会提高 Krea 生成伪字的概率；如果确实需要表达“文档、笔记、标签、检索”，必须在 `prompt_review` 写明 `text_risk_mitigation:`，并在 prompt 中用空白卡片、纯材质表面、色块、光路、物件阵列、几何层级等无字视觉等价物承载语义。不要把纸张、档案、桌面整体禁掉，它们是否出现取决于文案意象。
- 每张抽象意象和风格融合转译图，必须在 `prompt_review` 或等价字段中写清 `semantic_anchor` / `style_logic`：这张图表达文案里的什么、为什么选择这些符号或风格。

## GPU 阶段

提交前必须说明本批会使用：

- Qwen3-TTS 1.7B VoiceClone Load：正式旁白；
- Krea 2 Low VRAM：一张封面和本篇无字图片；
- Wan 2.2 I2V Q6：少量关键动态镜头。

用户开启 GPU 后，先运行：

```bash
COMFYUI_SERVER_URL=http://127.0.0.1:18188 \
  .venv/bin/python scripts/treeelf_philosophy_episode.py preflight --config <episode.json>
```

预检必须满足 GPU 存在、`/system_stats` 健康、运行和等待队列均为空、15/15 工作流通过。如果队列里有别的任务，不得打断或插队。

正式生成：

```bash
COMFYUI_SERVER_URL=http://127.0.0.1:18188 \
  .venv/bin/python scripts/treeelf_philosophy_episode.py generate-gpu --config <episode.json>
```

远端策略固定为 `retain_until_batch_end`。生成耗时逐项写入 `artifacts/gpu_usage_report.json`。单篇调试期间不清理、不关机；正式批量模式则在整批 GPU 资产下载、校验、dry-run 审核和精确清理全部通过后关机，再做本地工作。`treeelf_voice02_v1` 永远不是临时资产。

## 批量 GPU 模式

批量生产是正式默认方式，建议每批 5–8 篇。GPU 关机时先为每篇准备审核过的 episode JSON，再创建 batch JSON；`prepare` 只快照原文并写入批次预约，不修改原文完成状态。

```bash
.venv/bin/python scripts/treeelf_philosophy_batch.py validate --config <batch.json>
.venv/bin/python scripts/treeelf_philosophy_batch.py gpu-plan --config <batch.json>
.venv/bin/python scripts/treeelf_philosophy_batch.py prepare --config <batch.json>
```

GPU 开机并完成隧道后，一次预检，并在空队列状态冻结远端 `input/output/temp` 文件基线；收尾时只处理相对该基线新增的本批文件。随后按固定模型分组执行：全部 Qwen 旁白 → 全部 Krea 图片 → 全部 Wan 镜头。每阶段保持最多 2 个 episode worker，使 ComfyUI 尽量维持 1 个运行、1 个排队；阶段失败时允许已提交任务收尾，但不进入下一模型阶段。

```bash
COMFYUI_SERVER_URL=http://127.0.0.1:18188 \
  .venv/bin/python scripts/treeelf_philosophy_batch.py generate-gpu --config <batch.json>
```

只有 `gpu_asset_inventory.json` 已记录全部本地文件的大小和 SHA-256、队列为空，才允许进入收尾。必须先查看 dry-run 的精确远端清单，再执行备份、双端哈希校验、清理和关机：

```bash
.venv/bin/python scripts/treeelf_philosophy_batch.py finalize-gpu --config <batch.json> --dry-run
.venv/bin/python scripts/treeelf_philosophy_batch.py finalize-gpu --config <batch.json> --yes --shutdown
```

下载、哈希、清理或关机确认任一步失败，都保留远端资产并停止。只有批次状态进入 `gpu_finalized` 后，才逐篇执行本地 Whisper、字幕、Remotion、音频 QC 和交付。原 Markdown 仍只在最终成片校验并复制到 Movies 后标记 `completed`。

## 本地合成

1. 使用本地 MLX Whisper 模型 `/Users/treeelf/AI_Models/Whisper` 转录标准化旁白，检查首句、尾句与内容完整性。ASR 只用于 QC，不能把它识别错的专名直接当字幕。
2. 从审核原文和每个 Qwen 自然段的真实时长生成精确字幕文字；批量 GPU 模式必须在全部旁白生成后、Wan 生成前执行这一步，供 W02 选择“最长且语义安全”的画面：

```bash
.venv/bin/python scripts/treeelf_philosophy_episode.py build-captions --config <episode.json>
```

3. 根据旁白真实时长和精确字幕边界调整正文 scene 时间，不得让镜头时长只依赖模板占位值。`stage-remotion` 生成的 `remotion_props.json` 必须记录 `timelinePolicy`，并为每个 scene 写入 `caption_range` 与 `script_excerpt`；视觉切换应尽量发生在一句或一个语义单元讲完之后，尤其开场钩子不要在语义尚未落地时过早切图。信息页仍保留人工配置时间，除非 episode JSON 额外提供可审核的语义锚点。
4. 默认让 `stage-remotion` 按文案内容自动选背景音乐；若某篇需要指定音乐，再将批准的本地音乐写入 `music_source` 或 `music.preferred_keywords`。
   批量本地暂存应调用 `scripts/treeelf_philosophy_batch.py stage-local`，由批次入口顺序传递已用音乐，避免单独逐篇运行时丢失同批去重上下文。
5. 暂存 Remotion 资产和 props：

```bash
.venv/bin/python scripts/treeelf_philosophy_episode.py stage-remotion --config <episode.json>
```

6. 使用 `TreeElfPhilosophyEpisode` 和生成的 `artifacts/remotion_props.json` 渲染。

```bash
cd remotion-composer
npx remotion render src/index.tsx TreeElfPhilosophyEpisode <project-render.mp4> \
  --props <absolute-path-to-remotion_props.json>
```

## 交付与状态更新

交付前必须完成：

- ffprobe：时长、1080×1920、H.264/AAC；
- 联系表目视检查：风格、乱码、重复元素、静态动效和信息页；
- 本地 MLX Whisper：旁白完整且尾句存在；
- 音频：音乐可听、总响度和峰值合理；
- 项目成片与 Movies 副本 SHA-256 一致。

只有成片通过检查后才运行：

```bash
.venv/bin/python scripts/treeelf_philosophy_episode.py deliver \
  --config <episode.json> --render <verified-final.mp4>
```

`deliver` 先以“硬链接优先、原子复制兜底”交付到 `/Users/treeelf/Movies/zh-philosophy-video/`，验证 SHA-256，再向原 Markdown frontmatter 写入：

Movies 成片文件默认使用中文标题命名，优先从 `project_id` 提取日期作为前缀，例如 `2026-07-25_别把人生塞进同一张榜.mp4`；若重名，自动追加 `_v2`、`_v3`，不得覆盖已有成片。

```yaml
production_status: completed
video_project_id: <project_id>
video_output: <Movies absolute path>
video_generated: <UTC timestamp>
```

如果原文在 `prepare` 后发生变化，必须停止交付并重新审核修订，不能覆盖状态。

## 本地存储与复用

把 `projects/<project_id>/assets/` 作为该篇唯一主素材库，把 `/Users/treeelf/Movies/zh-philosophy-video/` 作为最终视频唯一发行档案。不要把 `remotion-composer/public/` 或批次 `remote-final-backup/` 当作长期素材库。

- Remotion 暂存优先创建硬链接；跨文件系统或硬链接失败时才复制字节。
- Movies 交付同样优先使用硬链接；即使项目路径和 Movies 路径同时存在，也只占一份实际字节。交付后项目 `renders/` 不再作为长期成片副本。
- `deliver` 通过可播放性与 SHA-256 检查后，立即清理本篇 Remotion 暂存、项目中间渲染、`narration_raw.mp3`，以及与中央音乐源哈希一致的项目音乐副本，并写入 `local_storage_cleanup_report.json`。
- 保留 `assets/images/article/`、`assets/video/article/`、`narration.wav`、平台封面和全部 `artifacts/`。图片、Wan 和旁白只复用于同一作品的修订、跨平台版本或合集，不默认跨作品复用。
- 跨作品复用 `treeelf_voice02_v1`、封面/Remotion模板、字体字幕规范、中央音乐库、风格规则和生产记录；不要因为复用流程而重复视觉素材。
- 分段配音和视觉质检抽帧保留7天作为修补窗口。到期后先查看清单，再清理：

```bash
.venv/bin/python scripts/treeelf_philosophy_episode.py cleanup-local --config <episode.json> --dry-run --include-delayed
.venv/bin/python scripts/treeelf_philosophy_episode.py cleanup-local --config <episode.json> --yes --include-delayed
```

- 批次 `remote-final-backup` 只用于关机后的短期灾备。必须等批次内每篇都已交付且Movies文件仍存在，再保留7天；到期后先dry-run再删除：

```bash
.venv/bin/python scripts/treeelf_philosophy_batch.py cleanup-local --config <batch.json> --dry-run
.venv/bin/python scripts/treeelf_philosophy_batch.py cleanup-local --config <batch.json> --yes
```

任何交付报告缺失、Movies文件缺失、保留期未到或目标路径越界，都拒绝清理。不要自动清理历史项目；先生成精确dry-run清单并确认它属于已交付作品。

## 单篇制作原则

- 保留用户审核通过的原文，除非用户明确要求改稿。
- 叙事具象镜头负责人物处境、动作和关系；抽象意象镜头负责情绪、隐喻和心理结构；风格融合转译镜头负责把文案语义转成有艺术语言支撑的连续画面。
- 不靠审美禁令避免陈词滥调；每篇先重新提取关键词、隐喻、情感基调和认知动作，再由这些语义生成对应画面。
- 风格多样性发生在作品之间和镜头之间；单篇应有 2–3 个主风格语言的清晰组合，不是把所有媒介都塞入同一张图。
- Remotion 信息页是视觉论证的一部分，不是独立 PPT，也不能完全消失。

## 首次选型批次（仅历史维护）

十声线、十二封面选型使用 `scripts/treeelf_philosophy_brand_pilot.py` 和 `treeelf-habit-door-brand-pilot.json`。栏目已定型，普通新文章不得再运行这套候选批次。选型结论已经迁移到持续栏目配置。

## 验证与故障边界

- 使用项目 `.venv`，不要向系统 Python 安装依赖。
- 配置错误、GPU 预检失败、下载/哈希失败、队列非空、源文修订、转录缺尾句，任何一项都必须停止到下一阶段。
- 课程知识检索不可用时，可以按已审核的栏目配置和 `art-Styles.md` 继续；不得为了检索修复去修改系统环境。
- 全库 TypeScript 可能含无关旧组件错误；验收本组件时必须至少完成目标 Composition 的 bundle/render 级检查，不能把旧错误误报为本篇失败。
