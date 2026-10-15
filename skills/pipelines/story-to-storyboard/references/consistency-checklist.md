# Consistency Checklist — story-to-storyboard

> **absorbed_from:**
> - `~/.claude/skills/script-team-orchestrator/SKILL.md`（跨场景一致性规则、局部重试策略）
> - `~/.claude/skills/copy-to-storyboard-json/SKILL.md`（t2i→i2v 连续性、拆分原则）
> **snapshot:** 2026-10 · 本文件是 OpenMontage 生产权威版；用户级本体保留独立可用。

## 1. 跨镜头角色/主体一致性

以下要素是**共享上下文**，在每个相关镜头的 t2i_prompt 中保持同一表述（从 story_brief `characters[].appearance` 逐字继承）：

- 角色身份与名字
- 外观（年龄、发型、体型、显著特征）
- 服装
- 时代与文明背景
- 场景风格

角色状态变化（湿了、受伤、换装）必须写成「**同一角色基础上的状态变化**」，即在保留身份锚点描述的前提下追加状态词，而不是重写一份新外观。

## 2. t2i → i2v 连续性（相邻层，强约束）

- 不换主体；不跳轴；延续光线；近景延续近景（镜头距离只允许渐变或场景明确要求的变化）。
- i2v_prompt 是让 t2i 图像动起来，不是重写新镜头（详见 `i2v-prompt-rules.md`）。

## 3. 相邻镜头检查（export director 逐对检查）

对每对相邻 shot：

| 检查项 | 通过标准 |
|---|---|
| 主体身份 | 同一角色外观锚点出现且一致 |
| 场景连续 | 同场景 shot 的环境要素延续；换场景时 narration 有明确转折 |
| 光线基调 | 连续 shot 的 lighting 关键词族一致（golden hour 不接 neon，除非剧情转折） |
| 镜头距离 | 渐变或有意跳切；无意外的大跳 |
| 色调 | mood 关键词族延续 |

## 4. 拆分原则（scene → ≤5s shots）

- **语义转折优先**：在情绪转变、动作完成、新信息出现处切分。
- 不机械按字数或秒数平均切。
- 拆分后每个 shot 的 narration 必须在其 duration 内可自然读完（中文约 3.5-4.5 字/秒）。

## 5. 局部重试策略（生产纪律）

- 下游某镜头的提示词/校验失败时，**只重做该镜头**。
- 重试时 scene_id、时长、顺序、主题、角色外观锚点一律不变。
- 不因单镜头失败重写整段或整篇。
