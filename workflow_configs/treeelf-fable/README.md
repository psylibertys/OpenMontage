# TreeElf Fable

这是寓言视频的独立批量生产配置，不读取、不继承
`workflow_configs/zh-philosophy-video/`。

## 两段式生产

1. GPU 开机前：准备文章快照、`visual_brief`、角色约束、语义段落、提示词和批次清单。配音与心哲灵固定声线一致，正式批量使用 `qwen3_tts_voice_clone_load` 载入已审核保存的 `voice_name` 声包；`prepare` 会写出 `batch_readiness_report.json` 和 `voice_instruction_report.json`，前者用于开机前确认每篇缺项、预计图片/Wan 数和角色审核需求，后者把 `instruct` 记录为声线档案和审核说明，而不是 clone-load 阶段的强控制参数。
2. GPU 批次第一段：先集中生成旁白和每篇独立角色参考包。角色四参考图存在后，`refresh-visuals` 会生成 `character_contact_sheet.png` 和 `character_review.json` 模板；需要 Flux 人物一致性时，必须人工审核通过后才排正文图。
3. GPU 批次第二段：读取真实旁白时长并生成初版字幕/句子时间，再按字幕结束边界和语义单元把每张图绑定到明确的 `caption_range` 与 `script_excerpt`，不再简单均分画面时间。字幕校准后优先保留原有 `caption_range` 或 `beat_id` 锚点，再回退到按时长切块。随后分别运行 Krea 场景、Flux 一致性场景、无人物无字封面和每篇最多一个 Wan 镜头，避免反复切模型。
4. 单 Wan 选择：默认 `opening_fable_event_only_or_none`。只允许选择开头“寓言规则首次真实显现”的画面，且该 beat 必须显式标记 `wan_candidate: true` 或 `fable_event_stage: first_manifestation`；若开头只是铺垫、未显式标记或运动风险较高，则本篇不生成 Wan。Wan 生成时长固定 3 秒，成片停留更长时由 Remotion 慢放、尾帧保持和静帧动效延展。
5. GPU 收尾：本轮全部生成素材下载到 Mac，验证大小与 SHA-256；只清理当前批次相对远端基线新增的文件，然后关机。
6. 本地封装：Whisper、字幕修正、自动选音乐、Remotion、质检和交付均在 Mac 完成。`stage-local` 前必须有 Whisper 或人工校准后的 `captions.json`，并自动把已有图片重新同步到校准后的字幕时间段。

## 新版视觉规则

fable 不使用“具象/抽象/风格融合比例”。每张图都按三层写清：

- `story_event`：这张图发生了什么，人物、地点、动作、物件必须清楚。
- `fable_law`：本篇超现实规则如何像真实事件一样显现。
- `art_style_logic`：艺术语言为什么适合这篇寓言，风格服务故事，不单独变成抽象艺术短片。

封面由 ComfyUI 生成无人、无字、无 Logo、无水印、无伪字的象征性背景；中文标题、英文副标题和“树精灵”只由 Remotion 添加。技术护栏保留，审美类“不要/避免/no/avoid”应改成正向画面目标。

## 交付与本地存储

- `/Users/treeelf/Movies/treeelf-fable/` 只保存最终 `.mp4`，使用中文标题和 `_v2/_v3` 防覆盖命名。
- 封面不放入 Movies；封面背景和 Remotion 文字封面保留在 `projects/<project_id>/assets/images/cover/`。
- `projects/<project_id>/assets/` 是该篇唯一主素材库；正文图、角色包、Wan、旁白、封面和全部 `artifacts/` 默认保留，用于返修、复盘和跨平台版本。
- `remotion-composer/public/treeelf-fable/<project_id>/`、项目 `renders/` 和与中央音乐源一致的 `assets/music/background.mp3` 是可清理派生物。
- 本地清理必须先 dry-run，再显式 `--yes`；不得清理未交付或 Movies 成片缺失的项目。

## 硬门禁

- 角色门禁：需要 Flux 一致性的正文图，必须先有四张参考图、`character_contact_sheet.png` 和人工通过的 `character_review.json`。
- 字幕门禁：正式本地封装必须使用 Whisper 或人工校准的 `captions.json`；GPU 阶段可用初版时间线先生成图片，本地封装前再同步。
- 字幕位置：默认白字黑边透明底，`safe_bottom` 使用 360，避开短视频平台底部标题、进度条和互动区。
- 画面门禁：`visual_qc.json` 必须确认每张正文图和封面背景通过；残肢、身份漂移、乱码字、人物封面或需要修复的图不得进入 Remotion。涉及主角或 Flux 人物一致性的 scene 必须勾选 `identity_stable_when_applicable`。
- QC 模板：`visual_qc.json` 会直接写入每张图的 `image_path`、`caption_excerpt`、`story_event`、`fable_law` 和 `art_style_logic`，审核时优先按模板逐项看图。
- Wan 门禁：Wan 是开头语义事件资产，不随 Whisper 校准自动重生；`stage-local` 会写出 `wan_retarget_report.json` 说明校准后如何重定位。若生成了 Wan，对应 scene 的 `wan_motion_safety` 必须为 `approved`。
- 音乐门禁：fable 必须有背景音乐，并写出 `music_selection.json` 与 `audio_mix_qc.json`。默认采用旁白优先 B3 混音基准：Remotion `musicVolume = 0.30`；Remotion 讲话段 duck 到更低氛围层，最终仍以试听确认“有氛围但不压旁白”。
- 封面门禁：ComfyUI 只出无人无字背景；最终中文标题、英文副标题和“树精灵”由 Remotion 添加。
- 提示词门禁：创意提示词里的审美类“不要/避免/no/avoid”会阻止新批次 `prepare`；技术护栏如无字、无 logo、无水印保留为集中规则。

## 常用命令

```bash
.venv/bin/python scripts/treeelf_fable_batch.py validate --config workflow_configs/treeelf-fable/batch.json
.venv/bin/python scripts/treeelf_fable_batch.py prepare --config workflow_configs/treeelf-fable/batch.json
.venv/bin/python scripts/treeelf_fable_batch.py capture-gpu-baseline --config workflow_configs/treeelf-fable/batch.json
.venv/bin/python scripts/treeelf_fable_batch.py refresh-visuals --config workflow_configs/treeelf-fable/batch.json
.venv/bin/python scripts/treeelf_fable_batch.py verify-gpu-assets --config workflow_configs/treeelf-fable/batch.json
.venv/bin/python scripts/treeelf_fable_batch.py create-qc-templates --config workflow_configs/treeelf-fable/batch.json
.venv/bin/python scripts/treeelf_fable_batch.py stage-local --config workflow_configs/treeelf-fable/batch.json
.venv/bin/python scripts/treeelf_fable_batch.py render-local --config workflow_configs/treeelf-fable/batch.json
.venv/bin/python scripts/treeelf_fable_batch.py complete-local --config workflow_configs/treeelf-fable/batch.json
.venv/bin/python scripts/treeelf_fable_batch.py cleanup-local --config workflow_configs/treeelf-fable/batch.json --dry-run
.venv/bin/python scripts/treeelf_fable_batch.py cleanup-local --config workflow_configs/treeelf-fable/batch.json --yes
```

远端收尾必须先预览，再执行：

```bash
.venv/bin/python scripts/treeelf_fable_batch.py finalize-gpu --config workflow_configs/treeelf-fable/batch.json --dry-run
.venv/bin/python scripts/treeelf_fable_batch.py finalize-gpu --config workflow_configs/treeelf-fable/batch.json --yes --shutdown
```

`refresh-visuals` 依赖每篇已经存在 `assets/audio/narration.mp3`。如果正文图使用 Flux，则还依赖通过门禁的角色参考图。它读取音频时长并生成可替换的初版 `captions.json`；Whisper 精修可以等 GPU 关闭后再运行，但 `stage-local` 会要求精修后的字幕或人工校准标记。
