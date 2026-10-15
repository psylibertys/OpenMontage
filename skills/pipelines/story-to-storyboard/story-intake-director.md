# Story Intake Director — Story-to-Storyboard Pipeline

## When To Use

Stage 1 of 4. Normalize whatever story material the user brought into one `story_brief` artifact. Two branches:

- **story mode** — a story blueprint (07产出), SC story card, fable draft, or free text.
- **reference mode (reverse)** — a reference video URL/file; derive the brief from local analysis.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/story_brief.schema.json` | Artifact validation |
| Reverse | `skills/meta/video-reference-analyst.md`, analysis tools | Reference analysis |
| Reverse | `skills/meta/brief-to-beat-bridge.md` | Deterministic brief → skeleton mapping |
| Method | `config/studiobinder-stage-routing.yaml` → `story-to-storyboard.story_intake` | Skill Hub slugs |
| Evidence | Qdrant retriever, `--domain storytelling` | Story craft evidence |

## Process — Story Mode

### 1. Read The Source, Snapshot It

- Source dirs are READ-ONLY. Copy the adopted text verbatim into
  `projects/<id>/artifacts/story_source_snapshot.md` and record both paths in
  `source.document_path` / `source.snapshot_path`.
- Declare `source.mode`: `story_blueprint` | `story_card` | `fable_draft` | `free_text`.

### 2. Normalize Into story_brief

Map the source onto the schema. For a TreeElf story blueprint, the eight
blueprint fields map directly:

| Blueprint field (07产出) | story_brief field |
|---|---|
| 主题 | `theme` |
| 整体风格 | `tone` |
| 目标情绪曲线 | `emotional_arc[]` (ordered phases) |
| 开头钩子设计 | `structure.hook` |
| 转折点设计 | `structure.turning_points[]` |
| 结尾落点 | `structure.landing` |
| 分场景内容 | input material for the script stage — do NOT pre-digest into final copy here |
| 建议时长 | `target_duration_seconds` |

Characters need stable visual identities (`appearance`: age, clothing, features) — downstream consistency checks and prompt writing reuse this string verbatim.

Fable drafts additionally fill `fable_extension` (moral / protagonist_type / art_style).

### 3. Quality Gate

- Premise states who wants what and what blocks it (one sentence).
- Emotional arc phases are ordered and distinct.
- Structure spine present (hook / turning points / landing).
- No camera vocabulary, no prompt text, no editing instructions — those belong to later stages (blueprint discipline: the brief is story truth, not production truth).

## Process — Reference Mode (Reverse, Local)

### 1. Analyze First

Run the full `video-reference-analyst.md` workflow with the local stack
(`video_analyzer`/`video_downloader`/`transcript_fetcher`/`scene_detect`/`frame_sampler`)
and produce a schema-valid `video_analysis_brief`. Record its path in
`source.video_analysis_brief_path` and the URL in `source.reference_video_url`.
Set `source.mode: reference_video`.

### 2. Bridge The Brief Into A Skeleton

Apply `skills/meta/brief-to-beat-bridge.md` — the deterministic mapping from
analysis fields to brief/beat skeleton (transcript segments → sections, pacing →
duration strategy, hook_technique → first beat, shot_language → scene_plan
subset). The bridge produces:

- a story_brief skeleton with `structure`, `emotional_arc`, `tone` derived from
  `content_analysis` + `pacing_profile` + energy levels;
- a `structure_template` distilled from the reference (energy sequence +
  narrative function sequence + pacing style), recorded in
  `structure_template_ref` and stored under `projects/<id>/artifacts/structure_templates/`.

### 3. Evidence Discipline (Binding)

- Every derived field must be traceable to a video_analysis_brief field.
- Where the analysis is silent, mark `metadata.bridge_gaps[]` — the script
  director fills gaps with original writing, never invented "references".
- Do not copy the reference's narration verbatim into the brief; the brief
  describes structure and function, the script stage writes new words.

### 4. Quality Gate (Reverse)

- Derived skeleton stays faithful to the analyzed structure.
- structure_template is reusable: a second video of the same genre would fit it.
- Bridge gaps are explicitly listed, not silently smoothed over.

## Common Pitfalls

- Treating a fable/blueprint as footage requirements — the brief is story truth.
- Reverse mode without a video_analysis_brief on disk (the sub-stage condition
  `video_analysis_brief_exists` must be genuinely true).
- Over-specifying: the brief constrains, the script stage creates.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review:
checkpoint `status="awaiting_human"`, present the story_brief summary (premise,
arc, spine, mode), and **END YOUR TURN**.
