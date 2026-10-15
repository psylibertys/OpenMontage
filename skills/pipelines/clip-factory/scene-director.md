# Scene Director - Clip Factory Pipeline

## When To Use

You are planning how each selected clip will be framed and packaged for its destination platform. This is where clip viability gets proven or disproven.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/scene_plan.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | Selected clips and platform goals |
| Tools | `frame_sampler`, `scene_detect` | Visual checks and boundary inspection |
| Playbook | Active style playbook | Layout language and safe zones |
| Density standard | `skills/pipelines/clip-factory/information-density-standard.md` | Binding spoken-hook, playback-order, and boundary rules |

## Process

### 1. Choose The Right Frame For Each Clip

Do not default every clip to `9:16`.

Use:

- `9:16` when a face-first crop works,
- `1:1` when speaker plus context both matter,
- `16:9` when slides, demos, or multi-speaker width are essential.

OpenMontage does not yet have first-class auto-reframe. If a vertical crop is weak, plan a safer aspect ratio instead of pretending the crop will work.

### 2. Plan First-Second Composition

For each clip, define:

- what the viewer sees on frame 1,
- where hook text can safely appear,
- where subtitles can live,
- whether the speaker needs a punch-in or whether the original framing is already good.

Also define the audio opening. Hook text alone is insufficient: record the exact first spoken line, its source time, and whether a cold-open reorder is used.

### 2b. Prove The Edit Boundaries

For every clip:

- list source ranges in playback order,
- list removed ranges and reasons,
- read all non-contiguous joins as a single transcript,
- reject starts/ends on fragments or unresolved references,
- record any intentionally retained pause over 1.2 seconds and its visual reason,
- confirm the ending stops immediately after the payoff.

### 3. Standardize The Batch

Use the scene plan to lock series consistency:

- same top hook zone,
- same subtitle zone,
- same watermark / brand area,
- same lower-third logic.

### 4. Store Reframe Detail In Metadata

The schema is generic, so store richer layout notes in `scene_plan.metadata`.

Recommended metadata keys:

- `clip_layouts`
- `safe_zones`
- `crop_variants`
- `speaker_positions`
- `platform_variants`

### 5. Use Scenes To Represent Deliverables

Each scene should map to one clip variant or one clip family deliverable. Keep `description` human-readable and use `required_assets` for hook overlays, lower thirds, or branded frames.

### 6. Quality Gate

- every clip has a platform-aware framing plan,
- hook and subtitle zones do not collide,
- weak vertical crops are downgraded honestly,
- the batch will feel visually consistent when rendered together.
- spoken hooks land by 3 seconds and every clip passes the density review,
- no EDL join creates a broken sentence.

## Common Pitfalls

- Center-cropping a wide shot and calling it vertical optimization.
- Ignoring slide or screen-share content while focusing only on faces.
- Letting each clip invent its own layout.
- Forgetting that the first frame determines whether a viewer keeps watching.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
