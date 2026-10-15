# Brief-to-Beat Bridge — Reverse Mode Mapping Protocol

## Purpose

Deterministic, evidence-preserving mapping from a `video_analysis_brief`
(produced by `skills/meta/video-reference-analyst.md` with the local analysis
stack) to the skeleton artifacts of the story-to-storyboard pipeline:

```
video_analysis_brief
  ├─ narration_transcript.segments ──────► script.sections skeleton
  ├─ structure_analysis.scenes ──────────► scene_plan.scenes skeleton (subset mapping)
  ├─ structure_analysis.pacing_profile ──► duration / shot-split strategy
  ├─ content_analysis.hook_technique ────► script.beat_map[0]
  ├─ energy sequence + functions ────────► story_brief.emotional_arc skeleton
  │                                          + structure_template (reusable)
  └─ content_analysis.tone/summary ───────► story_brief.tone / premise draft
```

Rules of engagement:

- **Deterministic means no invention.** Every derived field names its source
  field. Gaps go to `metadata.bridge_gaps[]` for the script director to fill
  with original writing — never smoothed over with plausible-sounding filler.
- **Enum values are never forged.** If an analyzed value does not match a
  target-enum value, it is dropped (and logged as a gap), not coerced.
- The bridge produces SKELETONS. The script/scene stages create; this only
  carries structure forward.

## 1. Transcript Segments → script.sections Skeleton

For each `narration_transcript.segments[i]` (skip empty text):

| target | source |
|---|---|
| `id` | `sec-{i+1}` |
| `text` | `segment.text` (verbatim — reference text is structure evidence, script stage rewrites) |
| `start_seconds` / `end_seconds` | `segment.start` / `segment.end` |
| `speaker_directions` | `segment.speaker` |

If `segments` is empty but scenes carry `narration_text`, derive sections from
scenes instead (`text=narration_text`, times from scene bounds). Scenes with no
narration at all → `bridge_gaps` entry `visual_only_section:scene-{index}`.

## 2. Analysis Scenes → scene_plan.scenes Skeleton

| target | source / rule |
|---|---|
| `id` | `scene-{scene_index}` (renumber continuous from 1) |
| `type` | `visual_type` via the table below |
| `description` | `scenes[].description` |
| `start_seconds` / `end_seconds` | `start_time` / `end_time` |
| `shot_language` | field-by-field subset copy — see §2.1 |
| `narrative_role` | inferred from `energy_level` + position — see §2.2 |

### 2.1 visual_type → scene.type (complete coverage of the analysis enum)

| analysis visual_type | scene_plan type |
|---|---|
| talking_head | talking_head |
| b_roll | broll |
| screen_recording | screen_recording |
| animation | animation |
| text_card | text_card |
| stock_footage | generated |
| diagram | diagram |
| chart | diagram |
| product_shot | generated |
| transition | transition |
| other | generated |

### 2.2 shot_language subset mapping (no enum forging)

Copy `shot_size`, `camera_movement`, `lighting_key`, `depth_of_field`
field-by-field, ONLY when the value matches the corresponding scene_plan enum
(analysis values are free strings). Non-matching values → drop + gap entry
`shot_language_gap:scene-{index}.{field}={value}`. Fields absent from the
analysis schema (`lens_mm`, `color_temperature`) are never invented here.

### 2.3 energy_level + position → narrative_role

| energy | first scene | last scene | middle |
|---|---|---|---|
| low | establish_context | resolution | transition |
| medium | introduce_subject | resolution | build_tension |
| high | introduce_subject | call_to_action | deliver_payload |
| peak | deliver_payload | call_to_action | deliver_payload or emotional_beat |

Peak-energy scenes whose description reads as an emotional turn map to
`emotional_beat` — this is the one judgment call; log it.

## 3. pacing_profile → Duration / Shot-Split Strategy

Derive `target_avg_shot_seconds` for the export stage:

| pacing_style | default avg shot |
|---|---|
| slow_contemplative | 4.5 |
| steady_educational | 4.0 |
| dynamic_social | 3.0 |
| rapid_fire | 2.0 |
| variable | clamp(avg_scene_duration_seconds, 1.5, 5) |

All styles additionally clamp to (0, 5]. Record `cuts_per_minute` in metadata —
the export director uses it as a cross-check on shot count.

## 4. hook_technique → beat_map[0]

```
beat_map[0] = {
  beat_id: "beat-1",
  label: content_analysis.hook_technique (or "hook"),
  start_seconds: first section start,
  end_seconds: first energy jump (low→medium/high boundary in scenes)
                or 15% of total duration, whichever is a real scene boundary,
  section_ids: sections inside that span,
  narrative_function: "establish_context"
}
```

Later beats derive from the scene skeleton's narrative_role sequence (§2.3);
the full beat_map is finalized by the script stage.

## 5. Energy Sequence → emotional_arc Skeleton + structure_template

- `emotional_arc[i] = {phase: <function from §2.3>, feeling: <energy word>}`
  with energy words low→"quiet, steady" / medium→"building" / high→"intense" /
  peak→"climactic". Marked as skeleton — script stage refines wording.
- `structure_template` (stored at
  `projects/<id>/artifacts/structure_templates/<template_id>.json`):

```json
{
  "template_id": "<kebab-from-source-title>",
  "source_ref": "<video_analysis_brief path>",
  "pacing_style": "<from analysis>",
  "cuts_per_minute": 0.0,
  "target_avg_shot_seconds": 0.0,
  "beat_sequence": [
    {"function": "establish_context", "energy": "low", "approx_share": 0.15}
  ],
  "notes": ["<anything the template assumes, e.g. on-screen-text-heavy hook>"]
}
```

`approx_share` = the beat's scene time / total duration. A template is reusable
when a second genre-mate video would fit its beat_sequence — otherwise it is
scene notes, not a template; say so instead of forcing it.

## 6. tone / summary → story_brief Fields

- `story_brief.tone` ← `content_analysis.tone` (verbatim).
- `story_brief.premise` ← drafted from `content_analysis.summary` in one
  sentence; flagged as draft (the summary describes a video, not yet a premise).
- `story_brief.target_duration_seconds` ← `source.duration_seconds`.
- `story_brief.source.mode: "reference_video"` + paths, per the schema.

## Failure Path

If the video_analysis_brief is too thin (no transcript AND <3 scenes), the
bridge refuses: fall back to asking the user for an oral reference description
(standard creative-intake), per the roadmap's risk mitigation. Never stretch a
two-scene analysis into a full skeleton.
