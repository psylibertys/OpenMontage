# Voice Rules — story-to-storyboard

> **absorbed_from:** `~/.claude/skills/copy-to-storyboard-json/references/voice_rules.md`
> **snapshot:** 2026-10 · 本文件是 OpenMontage 生产权威版；用户级本体保留独立可用。

## Purpose

`narration` 和 `emotion` 的唯一生成标准。narration 面向 TTS 使用，不是普通口播文案：允许有限的停顿标记和语气词标签，且 `emotion` 与段落结构保持一致。

## Emotion Labels（仅 7 个）

happy / sad / angry / fearful / disgusted / surprised / calm

## Emotion Paragraph Mapping

- narration 只有一段 → emotion 一个标签。
- narration 多段（`\n` 分隔）→ emotion 用 `\n` 分隔多个标签，**行数与 narration 段落数完全一致**。

```json
{
  "emotion": "calm\nsurprised",
  "narration": "夜色很安静。\n忽然，一道灯光从远处扫来。"
}
```

## Pause Marker Rules

- 语法 `<#x#>`，x 为停顿秒数，范围 `0.01`–`99.99`，最多两位小数。
- 合法：`他抬起头<#0.35#>看向夜空。`
- 非法：
  - `<#0.5#>他抬起头。`（不能在开头）
  - `他抬起头。<#0.5#>`（不能在结尾）
  - `他<#0.5#><#0.3#>看向远处。`（不能连续）
  - `他<#120#>看向远处。`（超出范围）
- 停顿标记必须位于可发音文本之间。

## Vocal Tags

仅当 `speech_model` 为以下之一时，narration 才允许语气词标签：

- `speech-2.8-hd`
- `speech-2.8-turbo`

受支持标签（19 个）：

`(laughs)` `(chuckle)` `(coughs)` `(clear-throat)` `(groans)` `(breath)` `(pant)` `(inhale)` `(exhale)` `(gasps)` `(sniffs)` `(sighs)` `(snorts)` `(burps)` `(lip-smacking)` `(humming)` `(hissing)` `(emm)` `(sneezes)`

## Narration Writing Guidance

- narration 优先保持自然、可发音、节奏稳定。
- 停顿标记和语气词标签只在确实提升语音表现时使用，不要滥用。
- 情绪变化主要靠段落切换时，优先换行 + emotion 对应，而不是一段里堆标签。
- 已用大量停顿标记时，不要再堆叠语气词标签。

## Enforcement

`lib/storyboard_export.py` 强制全部上述规则（枚举、行对齐、停顿位置/范围/连续性、标签模型门控、非法格式残留）。
