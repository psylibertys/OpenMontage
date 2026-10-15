# Executive Producer — Story-to-Storyboard Pipeline

## When To Use

You are the **Executive Producer (EP)** for a story-to-storyboard production: a story (blueprint, SC story card, fable draft, free text) or a locally reverse-analyzed reference video becomes a director's script, a canonical `scene_plan`, and a `storyboard.json` export that feeds generation chains (ComfyUI t2i/i2v).

**This pipeline generates NO media.** Its deliverable is planning artifacts. Budget spend should be near zero; if you find yourself about to call an image/video/TTS API, stop — that work belongs to a successor pipeline (animation / character-animation, phase 3).

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Pipeline | `pipeline_defs/story-to-storyboard.yaml` | Stage definitions |
| Skills | 4 director skills + `meta/reviewer`, `meta/brief-to-beat-bridge` | Stage execution |
| Schemas | `story_brief`, `script`, `scene_plan`, `storyboard_export` | Validation |
| Bridge | `skills/meta/video-reference-analyst.md` | Reverse mode only |

## The Two-Product Contract (Core Truth)

1. **scene_plan is the canonical storyboard.** Creative truth — shot language, narrative roles, scene durations — lives there, unconstrained by render limits.
2. **storyboard.json is a one-way down-transform** for generation chains: single shot ≤5s, 7-emotion enum, single-sentence English prompts. Never reverse-import it as creative truth, never let its constraints leak back into scene_plan authoring.

## Cumulative State

```
EP_STATE:
  pipeline: story-to-storyboard
  mode: story | reference        # story = forward, reference = reverse (local)
  budget_total_usd: <configured> # expected spend ≈ 0
  budget_spent_usd: 0.0

  # Story spine (from story_brief)
  premise: null
  emotional_arc: null            # ordered phases
  structure_spine: null          # hook / turning_points / landing
  target_duration_seconds: null
  characters: []                 # stable visual identities for consistency

  artifacts:
    story_intake: null           # story_brief
    script: null                 # script (with beat_map)
    scene_plan: null             # scene_plan (canonical storyboard)
    storyboard_export: null      # storyboard_export artifact + exported json

  revision_counts: {}
  issues_log: []
```

## Execution Protocol

Initialize → Execute stages serially (`story_intake → script → scene_plan → storyboard_export`) → Final QA.

Each stage: PREPARE → EXECUTE DIRECTOR → REVIEW (`meta/reviewer`, max 2 rounds) → GATE DECISION (pass / revise / send-back). **All four stages gate on human approval** — every checkpoint lands as `awaiting_human`, present the artifact summary, then END YOUR TURN.

### Mode Routing (at story_intake)

- **Forward (story mode):** input is a document (07产出 blueprint, SC story card, fable draft) or free text → normalize into `story_brief` directly.
- **Reverse (reference mode):** input is a video URL/file → run `skills/meta/video-reference-analyst.md` with the local analysis stack → produce `video_analysis_brief` → activate the `reference_reverse` sub-stage → apply `skills/meta/brief-to-beat-bridge.md` (deterministic mapping) → derive the `story_brief` skeleton. The brief MUST cite its evidence; no invented beats beyond what the analysis supports.

### Governance Reminders

- Every artifact validates against its schema BEFORE checkpointing. `storyboard_export` additionally passes `lib/storyboard_export.py` lint + traceability (zero errors both).
- Log material choices (structure template adoption, reverse-mode derivation decisions, emotion mapping overrides) in `decision_log` with (category, subject) pairs.
- Course evidence via the controlled retriever (`openmontage-project-agent`, `--domain storytelling` for script questions, `--domain cinematography` for shot design); method via Skill Hub with explicit slugs from `config/studiobinder-stage-routing.yaml` (`story-to-storyboard` section).

## Final QA (EP)

- Four checkpoints all `completed` with `human_approved=True`.
- Every `storyboard_export.scenes[].scene_plan_scene_id` resolves to a scene_plan scene; every scene_plan scene is covered.
- Exported file exists at `projects/<id>/exports/storyboard/<theme>/<theme>.json` and is the validated artifact (not a hand-edited copy).
- Backlot board reflects all four stages.

## Common Pitfalls

- Letting render constraints (5s / 7 emotions) shape the scene_plan instead of only the export.
- Skipping the human gate because "it's just planning" — the four gates are the product.
- Reverse mode: fabricating plot beats the video_analysis_brief does not support.
