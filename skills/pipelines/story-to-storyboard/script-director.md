# Script Director — Story-to-Storyboard Pipeline

## When To Use

Stage 2 of 4. Turn the approved `story_brief` into a director's `script` using the
additive schema fields: `beat_map` (top level), and per-section `visual_intent`,
`emotion`, `character_dialogue`.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/script.schema.json` (additive fields) | Artifact validation |
| Prior artifact | `state.artifacts["story_intake"]["story_brief"]` | Story truth |
| Method | `config/studiobinder-stage-routing.yaml` → `story-to-storyboard.script` | Skill Hub slugs |
| Evidence | Qdrant retriever, `--domain storytelling` | Story-craft evidence (Dan Harmon story circle, Master Scene elements) |

## Process

### 1. Beat Map First

Lay the story spine over a beat skeleton before writing any section text:

- `beat_map[]` entries: `beat_id`, `label`, time span, `section_ids`, `narrative_function`.
- Standard shape: hook → build → turn → landing; longer pieces add a midpoint turn.
- `narrative_function` should reuse the scene_plan `narrative_role` vocabulary
  (`establish_context` / `build_tension` / `deliver_payload` / `resolution` …)
  so the scene director can inherit roles instead of re-deriving them.
- In reverse mode, the bridge's beat skeleton from `metadata.bridge_gaps` /
  structure_template is the starting point; fill gaps with original writing.

### 2. Sections: Narration + Visual Intent + Emotion

**Rewrite, never compress (HARD RULE).** Derive each section by restating,
not by deleting words from the source. First list what a first-time listener
MUST receive in this section (information points), then write complete
sentences delivering them. Word-deletion compression systematically produces
three defects: dropped setups (a prop or concept used before it is
introduced), dangling subjects, and untranslated setting jargon. A sentence
that only makes sense to someone who has read the source is a failed
sentence — narration is a linear, listen-once medium.

Each section carries:

- `text` — speakable narration. Natural, rhythm-stable, TTS-friendly. Paragraph
  breaks are semantic turns, not word-count averages.
- `visual_intent` — what the viewer SEES (scene imagery, not camera parameters;
  camera language belongs to scene_plan).
- `emotion` — free-text emotional direction of this section (e.g. "quiet
  unease building to dread"). The 7-emotion enum is NOT enforced here; it is a
  storyboard_export concern.
- `character_dialogue[]` — only when characters speak. Sparse and purposeful;
  the narrator carries the piece.

### 3. Timing Discipline

- Section timings sum to `story_brief.target_duration_seconds` (±10%).
- `beat_map` spans cover their `section_ids` exactly; no orphan sections.
- Leave breathing room: a section that will become multiple ≤5s shots should
  not cram three turns into four seconds.

### 4. Consistency Anchors

- Reuse `story_brief.characters[].appearance` verbatim when a character appears
  in `visual_intent` or dialogue — downstream prompts inherit identity from here.
- Emotional phases of the sections should walk the `story_brief.emotional_arc`
  in order; deviations are decision_log material.

### 5. Quality Gate

- beat_map escalates cleanly; hook and landing land distinctly.
- Every section has visual_intent (the scene director cannot invent missing vision).
- Narration reads aloud well at the planned pacing; no essay-shaped sections.
- **First-listen audit passed and recorded in `metadata`**: read the full
  narration once as a first-time listener, then check (a) every prop/concept
  is introduced before it is used; (b) every clause has an explicit or
  locally-clear subject; (c) setting jargon is translated into listener
  language; (d) every time jump carries an explicit transition. Fix before
  checkpoint, not after user feedback.
- Reverse mode: gap-filling is original writing, marked as such, never attributed to the reference.

## Common Pitfalls

- Compressing the source by deletion — restatement is the only legal path.
  Deletion drops setups, subjects, and translations (the rev1→rev3 failure
  mode of the memory-repair-shop acceptance run, 2026-10: thermos appearing
  mid-story, dangling subject, untranslated setting jargon, missing
  winter-to-spring transition).
- Writing shot-level detail (shot sizes, lens, movement) into the script — that is scene_plan's job.
- Emotion labels from the 7-enum here — too coarse for the creative layer; the export director maps down.
- Beat map that describes topics instead of dramatic functions.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review:
checkpoint `status="awaiting_human"`, present the beat map and section summary,
and **END YOUR TURN**.
