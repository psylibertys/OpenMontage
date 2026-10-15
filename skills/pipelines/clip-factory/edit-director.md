# Edit Director - Clip Factory Pipeline

## When To Use

This stage turns the approved clips into independent mini-edits. Each clip must work alone, but the collection should still feel like a coherent series.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["assets"]["asset_manifest"]`, `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]` | Assets, layouts, transcripts |
| Playbook | Active style playbook | Transition and subtitle consistency |
| Density standard | `skills/pipelines/clip-factory/information-density-standard.md` | Binding pacing and semantic edit rules |

## Process

### 1. Build A Shared Edit Template

Lock the batch defaults first:

- subtitle style,
- hook timing,
- lower-third timing,
- watermark behavior,
- audio fade lengths.

Then apply per-clip overrides only where necessary.

### 2. Optimize The First 2-3 Seconds

For every clip:

- start on motion, face, or result,
- show hook text immediately if needed,
- let subtitles begin with the first spoken word,
- avoid intros that delay the point.
- require the spoken hook, not only the overlay, to land within 0–3 seconds,
- use a documented 3–8 second cold-open reorder when the strongest line occurs later.

### 3. Keep Boundaries Clean

- no cuts mid-word,
- no trailing silence after the point lands,
- no "setup for setup's sake" before the hook,
- no outro cards unless they earn the time.
- remove administrative speech, live-chat replies, drawing/tool setup, self-promotion, repeated claims, and unrelated tangents,
- remove non-essential pauses longer than 1.2 seconds,
- read joined transcript ranges aloud and reject half-sentence transitions,
- stop immediately after the payoff.

### 3b. Enforce Information Gain

Every retained 20–30 second window must add a claim, example, demonstration, consequence, or conclusion. Tighten any window that only restates prior material. Content-policy permissiveness is not permission to retain rambling.

### 4. Use Metadata For Multi-Variant Detail

Recommended metadata keys:

- `batch_template`
- `clip_variants`
- `hook_windows`
- `cta_windows`

Lock an immutable EDL revision identifier for each clip. When any KEEP range,
order, pause cut, bleep, speed, or audio extraction rule changes, invalidate
and regenerate all dependent video, audio, and caption assets together. Never
reuse captions from an earlier EDL revision merely because the clip title and
approximate duration still match.

### 5. Quality Gate

- each clip is self-contained,
- the first seconds hook fast,
- the spoken hook lands by 3 seconds,
- every source range and join matches the approved density audit,
- overlay stack is readable on mobile,
- the batch retains consistent styling and fades.

## Common Pitfalls

- Building one highlight reel instead of independent clips.
- Letting branding delay the hook.
- Overcrowding the screen with hook text, subtitles, watermark, and lower third simultaneously.
- Applying inconsistent transition timing across the batch.
- Assuming a persistent title can compensate for weak opening speech.
- Reusing caption or audio assets after the EDL revision changed.
- Applying a global subtitle shift to a clip whose drift grows over time.
- Preserving filler because the underlying viewpoint was approved for retention.
