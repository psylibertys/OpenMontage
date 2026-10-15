# I2V Prompt Rules — story-to-storyboard

> **absorbed_from:** `~/.claude/skills/copy-to-storyboard-json/references/i2v_prompt_rules.md`
> **snapshot:** 2026-10 · 本文件是 OpenMontage 生产权威版；用户级本体保留独立可用。

## Purpose

`i2v_prompt` 面向图生视频。它必须在尊重原图一致性的前提下，补充主体连续动作、局部动态、环境微变化、镜头运动、光影氛围、风格质感和物理约束。前提：图像已由 `t2i_prompt` 生成，因此 `i2v_prompt` 必须延续那张图确定的镜头语言。

## Universal Structure

`图像对齐描述 + 主体动作（连续） + 局部细节动态 + 环境变化 + 镜头运动 + 光影氛围 + 风格质感 + 物理约束`

## T2I To I2V Continuity Principle

`i2v_prompt` 的职责不是重新定义画面，而是让 `t2i_prompt` 生成的画面动起来。

必须：延续同一主体、同一场景、同一构图逻辑、同一镜头距离与视觉重心、同一光影基调（只允许轻微变化）。

禁止：

- 突然更换角色身份、服装、年龄或物种
- 突然切换到不同地点、不同时间、不同文明背景
- 从近景肖像直接改成大全景史诗画面
- 加入原图中不存在的大型新元素作为主角

## Layer 1: Image Alignment Description

- `Based on the provided image,`
- `the same character, same scene, same composition`
- `the character remains consistent, no change in identity or clothing`

无人物镜头改为主体/场景一致表达。

## Layer 2: Subject Actions

- 至少 2 个连续动作，必要时用 `then` 连接（`slowly turns head` / `slightly breathes` / `eyes gently blink`）。
- 不凭空增加新事件或新角色。
- 动作幅度与 `t2i_prompt` 的镜头距离匹配：近景微动作，中景肢体细节，大全景才适合大幅运动。

## Layer 3-4: Local Detail & Environment

让画面变活但不破坏主体、不创造新元素：

- `hair gently swaying` / `fabric softly fluttering` / `subtle facial movement` / `fingers slightly moving`
- `dust floating in the air` / `light shifting slightly` / `leaves gently moving` / `raindrops sliding down the window`

## Layer 5: Camera Movement（必须写）

- `slow push-in` / `slight camera drift` / `slow zoom in` / `cinematic orbit`
- 写法要稳，不过于夸张；默认强调 `smooth and cinematic`；是对原镜头的延续而非重新取景。

## Layer 6-7: Lighting / Style

- `soft cinematic lighting` / `rim light` / `volumetric light` / `warm golden hour` / `melancholic mood` / `poetic atmosphere`
- `cinematic` / `realistic` / `poetic` / `film grain` / `depth of field` / `highly detailed` / `4k`

## Layer 8: Physical Constraints（防崩坏，必须保留）

- `realistic motion` / `natural physics` / `no distortion` / `no morphing` / `consistent structure`

## Reference Template

`Based on the provided image, the scene and character remain consistent, the subject slowly [动作1], then gently [动作2], with subtle [局部细节变化], environment elements such as [已有元素] slightly moving, camera performs a [镜头运动], smooth and cinematic, soft [光影] lighting, [氛围], highly detailed, cinematic, depth of field, 4k, realistic motion, natural physics, no distortion, no morphing`

## Enforcement

`lib/storyboard_export.py` 强制四类锚点各命中至少一个：

| 锚点类 | 命中词（小写匹配） |
|---|---|
| 图像对齐 | based on the provided image / based on the original image / the same character / the same scene / the same composition / remains consistent / remain consistent |
| 镜头运动 | camera performs / camera slowly / slow push-in / slight camera drift / slow zoom in / cinematic orbit / smooth and cinematic |
| 物理约束 | realistic motion / natural physics / no distortion / no morphing / consistent structure |
| 连续动作 | "slowly " / "gently " / "slightly " / "then " |

另有：单句、无禁字符（`:` `/` `[` `]`）。
