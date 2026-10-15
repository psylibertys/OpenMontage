# TreeElf Fable

这是寓言视频的独立批量生产配置，不读取、不继承
`workflow_configs/zh-philosophy-video/`。

## 文案候选规则

候选只判断作品是否已经生成过视频，不使用 Markdown 中的 `status`、
`review_status`、`passed`、`passed_with_warnings` 作为筛选或生产门禁。已有完成成片记录，
或正被活动批次预约的作品仍然排除，防止重复生成和并发撞车。同题的原文、`精简版`、
`短版` 和 `30秒版` 视为同一作品，默认只建立一条生产记录。

同步寓言目录并查看全部未生产候选：

```bash
.venv/bin/python scripts/treeelf_fable_batch.py sync-ledger
```

## 连续GPU生产

1. GPU 开机前：准备文章快照、`visual_brief`、角色约束、语义段落、提示词和批次清单，并写出 `gpu_visual_blueprint.json` 预编译预计时长对应的全部视觉槽位。GPU阶段只根据真实旁白时长机械调整槽位数量和字幕区间，不在线改变已经批准的 beat 提示词与视觉逻辑。配音与心哲灵固定声线一致，正式批量使用 `qwen3_tts_voice_clone_load` 载入已审核保存的 `voice_name` 声包；`voice_instruction_report.json` 会明确说明 `instruct` 是声线档案，不是 clone-load 的有效控制输入。
2. GPU 通过统一的 `run-gpu-batch` 命令连续推进：全部旁白 → 全部角色转面表 → 读取真实旁白时长并规划视觉任务 → Krea 环境/物件图 → 封面 → 已通过角色门禁的 Flux 图 → 可选 Wan。执行器最多保持两个工作线程，对应一个运行任务和一个待执行任务，并每 15 秒记录一次队列状态。
3. 新角色包只允许 `single_turnaround_sheet`：一次生成同一角色的 2×2 四视图，再裁成四张 Flux 参考图；禁止用四次互不关联的文生图冒充同一角色，也禁止把同一张图复制四份。角色门禁只阻断该篇 Flux 人物图；Krea 环境图、物件图和封面继续生成。`refresh-visuals` 会生成联系表和审核模板，批准后重新运行同一条 `run-gpu-batch` 命令即可释放相关 Flux 任务，不需要手工逐组执行。
4. 每个 beat 必须写 `script_anchor`，编译器按锚点绑定 `caption_range` 与 `script_excerpt`。字幕校准后优先保留原有语义绑定，再按相同 beat 范围调整边界。
5. 在线返修只接受明确严重问题，并集中追加到 `repairs` 尾组。每个原资产必须记录 `repair_of` 且只能有 `repair_attempt: 1`；一般审美偏好不进入该组。
6. 单 Wan 选择：默认 `opening_fable_event_only_or_none`。Wan 固定 3 秒且属于可选增强资产；生成失败、文件缺失或运动审核未通过时，Remotion 自动使用对应静帧，不补一个“幽灵 Wan”阻断成片。
7. GPU 收尾：本轮全部生成素材下载到 Mac，验证大小与 SHA-256；只清理当前批次相对远端基线新增的文件，然后关机。
8. 本地封装：Whisper、字幕修正、视觉联系表检查、自动选音乐、Remotion、质检和交付均在 Mac 完成。

## 新版视觉规则

fable 不使用“具象/抽象/风格融合比例”。每张图都按三层写清：

- `story_event`：这张图发生了什么，人物、地点、动作、物件必须清楚。
- `fable_law`：本篇超现实规则如何像真实事件一样显现。
- `art_style_logic`：艺术语言为什么适合这篇寓言，风格服务故事，不单独变成抽象艺术短片。

角色性别不按原文中的“他/她”等代词机械映射。两种性别都能自然承担角色时优先女性；人物关系、身份或叙事情境明显更适合男性时使用男性，并在 `protagonist.selection_rationale` 说明原因。男性不是禁用项。每篇还必须明确 `age_band`、`hair` 和 `silhouette`；发型、年龄、脸型和服装从本篇身份出发。同批至少 3 个真人角色时，如果同一发型家族达到 3 人且占比不低于 75%，校验会停止批次，防止连续复用卷发等默认人物；它不禁止某一种发型，也不因两篇偶然相似而阻断生产。

提示词在提交 GPU 前会先编译为最终版本并写入 `compiled_prompt_report.json`。环境、物件和微距场景不会再自动拼接主角身份或人物镜头语言；只有 `protagonist/group` 场景才附加角色描述。这样可以在生成前发现“无人画面却被代码塞进主角”等系统性冲突。

封面由 ComfyUI 生成无人、无字、无 Logo、无水印、无伪字的象征性画面；中文标题、英文副标题和“树精灵”只由 Remotion 添加。中文封面标题在未特别指定时统一使用项目根目录 `fronts/漓雨手书_100font/LiyuXingkai.ttf`。封面绘图 prompt 只描述可见物、材质、光线与自然留白，不能出现 typography、title-safe、editorial、poster、TreeElf 等版式或品牌提示。OCR 与审美否定词扫描只作预警；技术护栏继续集中附加。

## 交付与本地存储

- `/Users/treeelf/Movies/treeelf-fable/` 只保存最终 `.mp4`，使用中文标题和 `_v2/_v3` 防覆盖命名。
- 封面不放入 Movies；封面背景和 Remotion 文字封面保留在 `projects/<project_id>/assets/images/cover/`。
- `projects/<project_id>/assets/` 是该篇唯一主素材库；正文图、角色包、Wan、旁白、封面和全部 `artifacts/` 默认保留，用于返修、复盘和跨平台版本。
- `remotion-composer/public/treeelf-fable/<project_id>/`、项目 `renders/` 和与中央音乐源一致的 `assets/music/background.mp3` 是可清理派生物。
- 本地清理必须先 dry-run，再显式 `--yes`；不得清理未交付或 Movies 成片缺失的项目。

## 门禁与警告

- 角色硬门禁：只检查同一身份、四个不同有效视角、严重人体错误和可读文字；只阻断相应 Flux 场景。
- 字幕门禁：正式本地封装必须使用 Whisper 或人工校准的 `captions.json`；GPU 阶段可用初版时间线先生成图片，本地封装前再同步。
- 字幕位置：默认白字黑边透明底，`safe_bottom` 使用 460，进一步上移字幕并避开短视频平台底部标题、进度条和互动区。
- 画面硬门禁：`visual_qc.json` 只通过 `blocking_findings` 阻止 Remotion，内容限于严重人体错误、可读错误文字、主角身份严重漂移和核心情节冲突。旧文件中明确的 `blocking_issue/severity=blocking` 继续兼容；旧的逐项 approved、story、anatomy、text、identity 复选框不再各自阻断。
- 画面警告：风格偏差、无害动物、额外环境物件和一般构图偏好写入 `warnings`，不触发在线GPU返修。
- Wan 回退：Wan 不随 Whisper 校准重生；缺失、失败、未审核或运动风险较高时写出 `wan_static_fallback.json` 并使用静帧。
- 音乐门禁：fable 必须有背景音乐，并写出 `music_selection.json` 与 `audio_mix_qc.json`。选曲读取共享目录、人工覆盖和 `reserved / committed / failed` 使用账本；同项目默认复用原曲，同批与近期已提交音乐降权，`纯音乐/instrumental` 不算语义命中。项目副本必须成功标准化到 -18 LUFS / -2 dBTP，中央原曲保持不变。默认采用旁白优先 B3 混音基准：Remotion `musicVolume = 0.30`；Remotion 讲话段 duck 到更低氛围层。交付前还必须通过 `final_audio_mix_qc.json` 的片尾覆盖、综合 LUFS 和真实峰值门禁，最终仍以试听确认“有氛围但不压旁白”。
- 封面门禁：ComfyUI 只出无人无字画面；绘图 prompt 禁止版式、标题和品牌提示。OCR 只作预警，因为砖纹、木纹和笔触容易产生误报；最终以人工确认无人、无真实可读文字、无 Logo、无水印为准。中文标题、英文副标题和“树精灵”由 Remotion 添加。
- 本地封装以实际资产、字幕、视觉和音频检查为准；批次状态字段不一致只记录警告，不单独阻止 Remotion。
- 音乐标准化允许目标响度上下 2 LU 的误差，最终仍以旁白优先的成片混音 QC 为准。某曲在同一项目中标准化失败后立即排除，自动选择下一候选，不再重复撞同一错误。
- 提示词警告：创意提示词里的审美类“不要/避免/no/avoid”写入 `prompt_review_warnings.json`，不阻止 `prepare`；技术护栏如无字、无 logo、无水印保留为集中规则。
- 状态对账：`gpu_assets_complete/local_packaging/completed` 以实际资产和SHA门禁为准，可从陈旧状态直接幂等修复；重复执行 `complete-local` 会复用已验证Movies成片，不生成无意义的 `_v2`。

## 常用命令

```bash
.venv/bin/python scripts/treeelf_fable_batch.py validate --config workflow_configs/treeelf-fable/batch.json
.venv/bin/python scripts/treeelf_fable_batch.py prepare --config workflow_configs/treeelf-fable/batch.json
.venv/bin/python scripts/treeelf_fable_batch.py capture-gpu-baseline --config workflow_configs/treeelf-fable/batch.json
.venv/bin/python scripts/treeelf_fable_batch.py run-gpu-batch --config workflow_configs/treeelf-fable/batch.json
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

统一调度命令必须通过 `with-autodl-comfyui-tunnel.sh` 运行，以保证 18188 隧道覆盖整个生成生命周期。若命令返回 `waiting_character_review`，审核列出的 `character_review.json` 后原样重跑同一命令；已完成任务会跳过。GPU报告会记录首任务延迟、有效生成时间、组间空档、队列采样、60秒空队列告警和可避免空闲比例。
