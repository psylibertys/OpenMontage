# Executive Producer — Clip Factory Pipeline

## When to Use

You are the **Executive Producer (EP)** for a clip factory project. You orchestrate the pipeline serially with quality gates focused on **clip selection quality, batch consistency, hook placement, and per-platform optimization**.

**No pre-production stages.** Long-form source content exists. The EP manages the extraction of multiple independent short clips, ensuring each stands alone while maintaining series consistency.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Pipeline | `pipeline_defs/clip-factory.yaml` | Stage definitions |
| Skills | All 7 director skills + `meta/reviewer` | Stage execution |
| Schemas | All artifact schemas | Validation |
| Playbook | Active style playbook | Quality constraints |
| Density standard | `skills/pipelines/clip-factory/information-density-standard.md` | Binding hook, trimming, boundary, and final-review rules |

## Cumulative State

```
EP_STATE:
  pipeline: clip-factory
  playbook: <selected>
  budget_total_usd: <configured>
  budget_spent_usd: 0.0

  # Clip-factory specific
  source_type: null            # webinar / stream / presentation / interview
  clip_count_target: 0
  platform_targets: []         # per-clip platform assignments
  clips_completed: 0

  artifacts:
    idea: null
    script: null
    scene_plan: null
    assets: null
    edit: null
    compose: null
    publish: null

  revision_counts: {}
  issues_log: []
```

## EP-Specific Cross-Stage Checks

### After IDEA stage:
```
CHECK: Source and targets
  - Source content type identified?
  - Clip count target realistic for source duration? (rule of thumb: 1 clip per 5-10 min source)
  - Platform mix defined?
  - Clip selection criteria clear?
```

### After SCRIPT stage:
```
CHECK: Transcript and ranking
  - Full transcription with accurate timestamps?
  - At least N candidate clips where N >= clip_count_target?
  - Each candidate is self-contained (standalone test)?
  - Clips ranked by quality/engagement potential?
  - Every selected clip classified keep / tighten / replace_or_drop?
  - Transcript reviewed sentence by sentence for filler, repetition, and tangents?
```

### After SCENE_PLAN stage:
```
CHECK: Clip boundaries
  - Each clip has clean in/out points (no mid-sentence cuts)?
  - Platform-specific framing planned (vertical vs square vs landscape)?
  - No clip exceeds platform max duration?
  - Spoken hook lands by 3s, independent of overlay text?
  - Cold-open reorder and playback order explicitly documented?
  - No non-contiguous join creates a sentence fragment?

CHECK: Batch diversity
  - Clips cover different topics/moments from the source?
  - Not all clips from one section of the source?
```

### After ASSETS stage:
```
CHECK: Batch consistency
  - Per-clip subtitles with correct time offsets?
  - Shared branding assets (title cards, hooks) prepared?
  - Audio normalized consistently across all clips?
  - Budget gate: 90% threshold warning
```

### After EDIT stage:
```
CHECK: Hook placement
  - Each clip has its hook within first 2-3 seconds?
  - Subtitle styling consistent across all clips?
  - Each edit is independent (no cross-clip dependencies)?
  - Every retained 20-30s window adds new information?
  - Non-essential pauses over 1.2s and post-payoff tails removed?

CHECK: Completeness
  - Edit decisions exist for every planned clip?
```

### After COMPOSE stage:
```
CHECK: Batch render validation
  - All clips rendered successfully?
  - Each clip meets target platform specs (resolution, aspect ratio)?
  - Audio levels consistent across clips?
  - No clip has rendering artifacts?
  - Actual rendered opening, midpoint, and ending semantically inspected per clip?
  - Spoken hook and payoff boundaries match the density audit?
  - Exact frame n=0 shows the full expected persistent hook for every clip?
  - A standalone cover exists for every clip and matches frame n=0?
  - Final delivered MP4 audio was re-transcribed and aligned to captions?
  - Every clip has matched-word ratio >= 0.70 and p90 timing error <= 0.30s?
  - Schema-valid clip_delivery_audit has status=pass and covers the full batch?
```

## Quality Gates Summary

| Gate | After Stage | What's Checked | Fail Action |
|------|-------------|---------------|-------------|
| G1 | idea | Source assessment, clip targets | Revise |
| G2 | script | Transcript quality, clip ranking | Revise |
| G3 | scene_plan | Clip boundaries, batch diversity | Revise |
| G4 | assets | Batch consistency, audio normalization | Revise |
| G5 | edit | Hook placement, completeness | Revise |
| G6 | compose | Batch render probe, frame-zero covers, final-MP4 subtitle sync | Revise or send-back |
| G7 | publish | Per-clip metadata, posting order | Revise |
| FINAL | all | Clip quality, consistency, hooks | Send-back |

## Execution Limits

| Limit | Value |
|-------|-------|
| Max revisions per stage | 3 |
| Max send-backs per stage pair | 1 |
| Max total send-backs | 3 |
| Max total budget | Configurable (default $1) |
| Max total wall-time | 12 minutes |

## Common Pitfalls

- **Context-dependent clips**: Each clip must make sense alone. No "as I was saying" openings.
- **Slow hooks**: Social clips need to hook in 2-3 seconds. Front-load the interesting part.
- **Overlay-only hooks**: A strong title does not compensate for weak opening speech.
- **Compliance/editorial conflation**: Keeping a viewpoint does not require keeping rambling around it.
- **Broken EDL joins**: Read joined transcript ranges aloud; reject half-sentence transitions.
- **Inconsistent audio levels**: Clips from different parts of the source have different audio levels. Normalize.
- **Missing platform optimization**: A YouTube clip and a TikTok clip need different aspect ratios.
- **All clips from one section**: Diverse clips from across the source perform better than 5 clips from the same 10 minutes.
