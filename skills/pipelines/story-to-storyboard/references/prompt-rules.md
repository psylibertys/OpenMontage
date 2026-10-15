# Prompt Rules (t2i) — story-to-storyboard

> **absorbed_from:** `~/.claude/skills/copy-to-storyboard-json/references/prompt_rules.md`
> **snapshot:** 2026-10 · 本文件是 OpenMontage 生产权威版；用户级本体保留独立可用。
> Rule changes happen here first, then optionally back-port to the user-level skill.

## Purpose

`t2i_prompt` 的唯一生成标准，只负责静态图像提示词；图生视频提示词见
`i2v-prompt-rules.md`。

## Branch A: User Specified An Art Style

当用户明确指定艺术风格时（如 fable 的 `fable_extension.art_style`），严格按以下模板构造英文提示词：

`[主体：细节描述] + [背景环境：空间感] + [风格：用户提供的风格] + [光影：氛围关键词] + [质量控制：8k, highly detailed]`

- 保留用户提供的风格原文，不随意替换为近义词。
- 主体描述要具体，包含动作、表情、服饰、材质、状态等可视元素。
- 背景环境要体现空间感与场景信息。
- 光影部分要补充氛围，如 warm rim light、misty glow、dramatic shadows。
- 结尾必须包含 `8k, highly detailed`。
- 输出为单句英文，不加解释。

## Branch B: No Art Style Specified

严格执行以下 recipe。

### 1. Prompt Opening（三选一）

- `cinematic photo of`
- `cinematic portrait photo of`
- `cinematic macro photo of`

根据主体远近、细节尺度和镜头亲密度选择。

### 2. Subject With Action And Angle

主体后追加：一个简单动作或姿态 + 一个镜头视角或机位角度。

### 3. Environment

补充一个具体环境（可直接用文案中的空间，也可在不偏题前提下补全）。

### 4. Color Grading And Mood（选 2 个）

cinematic teal and orange / cinematic faded orange and tan tones / cinematic pastel pink and blue / warm amber hues / rustic browns / dusty rose / muted pastels / nostalgic palette / filmic warmth / analogue colors / desaturated blues / cool cinematic tones / teal and orange contrast / mysterious cool hues / melancholic palette / urban blues / rich jewel tones / dynamic color shifts / expressive palette / dreamlike hues / neon glow / cyberpunk purple / glow-in-the-dark / ultraviolet / faded matte look / soft contrast / film emulation matte / chiaroscuro lighting / deep shadows / dramatic contrast

### 5. Lighting And Atmosphere（选 1-2 个）

golden hour / blue hour / overcast lighting / soft diffused light / dappled sunlight / rim lighting / backlighting / silhouette / neon signs / street lamps / car headlights / subtle fill light / atmospheric haze / volumetric lighting / god rays / lens flare

### 6. Light Quality（可选 0-1 个）

hard light / soft light / moody lighting / ethereal glow / cinematic lighting setup

### 7. Film Emulation（可选 0-1 个）

film grain / gritty film stock / cinematic film look / expired film

### 8. Camera（选 1 个）

shot on Contax 645 / shot on Minolta SRT-101 / shot on Kodak Retina II / shot on Panasonic GH5 / shot on Kodak Portra 400

### 9. Cinematic Style（选 1 个）

Old Hollywood glamour / 1950s cinematic / 1980s cinematic / retro aesthetic / contemporary film aesthetic / indie film look / dystopian aesthetic / cinematic cyberpunk / cinematic sci-fi realism / cinematic magical realism / cinematic enchanted / cinematic ethereal / cinematic dreamscape

### 10. Cinematic Descriptor（选 2-3 个）

cinematic composition / immersive / storytelling image / visually stunning / epic shot

## Final Rules For All Prompts

- 输出单个完整英文句子，逗号分隔短语。
- 不使用冒号、斜杠或方括号（lint 强制：`:` `/` `[` `]`）。
- 语气像电影画面描述，不是关键词堆砌。
- 始终变化组合，避免多镜头使用同一套 mood 和 lighting。
- 直接输出 prompt 本身，不附带解释。

## Enforcement

`lib/storyboard_export.py` 强制：非空、单句（无换行）、无禁字符。
