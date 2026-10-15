# Scene Director — Story-to-Storyboard Pipeline

## When To Use

Stage 3 of 4. Turn the approved `script` into the **canonical storyboard**:
a `scene_plan` where creative truth lives, unconstrained by render limits.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/scene_plan.schema.json` | Artifact validation (shared with other pipelines) |
| Prior artifact | `state.artifacts["script"]["script"]` | Beat map + sections with visual_intent |
| Optional | `state.artifacts["story_intake"]["story_brief"]` | Character appearances, tone |
| Method | `config/studiobinder-stage-routing.yaml` → `story-to-storyboard.scene_plan` | Skill Hub slugs |
| Evidence | Qdrant retriever, `--domain cinematography` | Shot design evidence |

## Process

### 1. One Section → At Least One Scene

- Every script section maps to ≥1 scene via `script_section_id` (required for traceability).
- Scenes are ordered; `start_seconds`/`end_seconds` are continuous and sum to the script duration.
- Scene ids: `scene-1`, `scene-2`, … (the export stage renumbers shots separately).

### 2. Shot Language From The Beat's Function

For each scene choose `shot_language` (shot_size / camera_movement / lens_mm /
lighting_key / depth_of_field / color_temperature) and `narrative_role`,
motivated by the section's `emotion` and `visual_intent` — not decoration:

- establish_context favors establishing/wide, static or slow movement;
- build_tension favors closer sizes, handheld or slow push;
- deliver_payload/hero moments favor close_up + deliberate movement + distinctive lighting;
- resolution favors medium/wide, calm movement.

When uncertain between treatments, query the `cinematography` domain
(e.g. "亲密对话场景 景别与镜头距离 选择依据") — cite what the evidence says,
including when the courses are silent on a case.

### 3. Duration Freedom — With Export In Mind

- Scene durations are creative choices (a scene MAY exceed 5s; the export stage
  splits it later). But design sensibly: each semantic sub-beat ≥2s, and mark
  split points by giving sub-beats their own description sentence when a scene
  clearly contains two visual ideas.
- `hero_moment: true` on the visual peak (usually the deliver_payload beat).

### 4. Character Consistency (Binding)

- When a `story_brief` character appears, the scene's description or
  `character_actions[].notes` must reuse their `appearance` string verbatim.
- `character_actions[].emotion` is free text here (creative layer); the export
  maps to the 7-enum.

### 5. Required Assets

- `required_assets[]` per scene with `source` hints (`generate` for t2i/i2v shots —
  the default in this pipeline; `provided` for user-supplied references).

### 6. Quality Gate

- Every scene references a real section id; no section uncovered.
- Every shot_language choice has a WHY (`shot_intent` filled).
- narrative_role vocabulary used where applicable — the export stage maps roles to emotions.
- Reverse mode: bridge-provided shot_language subset values were carried over
  where the analysis supported them, and enriched (lens_mm, color_temperature)
  only as new creative choices.

## Common Pitfalls

- Importing render constraints here (≤5s scenes, 7 emotions) — scene_plan is the creative layer.
- Shot language as decoration — every choice needs a motivated reason.
- Character identity drift between scenes.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review:
checkpoint `status="awaiting_human"`, present the scene list (ids, roles, durations,
hero moments), and **END YOUR TURN**.
