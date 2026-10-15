# Storyboard Export Director — Story-to-Storyboard Pipeline

## When To Use

Stage 4 of 4. Down-transform the approved `scene_plan` (canonical) into the
`storyboard_export` artifact and the `storyboard.json` deliverable that feeds
generation chains (ComfyUI t2i/i2v). One-way: never write creative truth back
into this layer.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/storyboard_export.schema.json` | Structure + enum validation |
| Library | `lib/storyboard_export.py` | Semantic lint + traceability (production-authoritative) |
| CLI | `scripts/export_storyboard_json.py` | Writes the deliverable file |
| Rules | `references/prompt-rules.md`, `references/i2v-prompt-rules.md`, `references/voice-rules.md`, `references/consistency-checklist.md` | Absorbed generation rules |
| Prior artifact | `state.artifacts["scene_plan"]["scene_plan"]` | The storyboard being transformed |

## Render Constraints (This Layer ONLY)

- `duration_seconds`: >0 and ≤5 per shot.
- `emotion`: exactly the 7-enum, line-aligned with narration paragraphs.
- `t2i_prompt` / `i2v_prompt`: single-sentence English, no `:` `/` `[` `]`.
- `i2v_prompt` carries all four anchor classes (image-alignment / action / camera / physics).

## Process

### 1. Split Scenes Into ≤5s Shots

- Iterate scene_plan scenes; a scene longer than 5s splits at **semantic turns**
  (the split principle from the absorbed rules: 語義转折优先，不机械按字数/秒数切).
  Each split shot keeps `scene_plan_scene_id` pointing at its parent scene.
- `scene_id` runs 1..N continuous over the whole export.
- Distribute the scene's narration across its shots by semantic turn; a shot's
  narration should be speakable in its duration (Chinese narration ≈ 3.5-4.5 chars/sec;
  verify and rebalance if a shot's text cannot fit).

### 2. Map Emotions Down

Section/scene free-text emotion → the 7-enum. Default role mapping:

| narrative_role / direction | emotion |
|---|---|
| establish_context, transition, evidence | calm |
| build_tension (threat) | fearful |
| build_tension (conflict) | angry |
| introduce_subject (wonder) | surprised |
| deliver_payload, comparison | surprised |
| emotional_beat (loss) | sad |
| emotional_beat (aversion) | disgusted |
| resolution, call_to_action | happy or calm |

Overrides allowed; log material ones (`category: emotion_mapping`) in decision_log.
Multi-paragraph narration gets one emotion label per line (\n-aligned).

### 3. Write t2i Prompts

Follow `references/prompt-rules.md` (absorbed from copy-to-storyboard-json):
opening pattern, subject+action+angle, environment, color grading, lighting,
camera, style — single sentence, comma-separated, `8k, highly detailed` tail.
When the user specified an art style (e.g. fable art_style), that style phrase
is locked verbatim across shots.

### 4. Write i2v Prompts

Follow `references/i2v-prompt-rules.md`: based-on-image anchor + continuous
subject actions + local detail dynamics + environment change + camera movement +
lighting + style + physics constraints. The i2v prompt animates the t2i image —
it never redefines the shot.

### 5. Narration & Voice

Follow `references/voice-rules.md`: pause markers `<#x#>` legal positions/range,
vocal tags only for `speech-2.8-hd` / `speech-2.8-turbo`, paragraph↔emotion
line alignment. Record `speech_model` when known.

### 6. Cross-Shot Continuity

Check every adjacent pair against `references/consistency-checklist.md`:
same subject identity, no axis jumps, lighting continuity, shot-distance
continuity (close stays close unless the scene_plan says otherwise).

### 7. Validate, Trace, Export (Binding Order)

1. `validate_artifact("storyboard_export", data)` — schema.
2. `lint_storyboard(data)` — zero errors (or stop and fix).
3. `check_traceability(data, scene_plan)` — every shot resolves; every scene covered.
4. Write the artifact to `projects/<id>/artifacts/storyboard_export.json`, then run
   `python scripts/export_storyboard_json.py projects/<id>/artifacts/storyboard_export.json --scene-plan projects/<id>/artifacts/scene_plan.json`
   to produce `projects/<id>/exports/storyboard/<theme>/<theme>.json`.
5. The exported file IS the validated artifact (with metadata) — never hand-edit the export afterward.

If a scene cannot be honestly split (a true single 7s beat), do NOT silently
merge — surface the blocker: options are re-cut at scene_plan, tighten
`--max-shot-seconds`, or split with a pause marker in narration.

## Quality Gate

- All three validations green before checkpoint.
- Spot-check three shots (first, hero, last) against every rule set.
- Total duration ≈ script total; shot count reasonable for the pacing style.

## Common Pitfalls

- Mechanically splitting by seconds instead of semantic turns.
- Writing i2v prompts as new video prompts instead of animating the t2i image.
- Hand-editing the exported JSON after validation.
- Letting the 7-enum leak back into scene_plan revisions.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review:
checkpoint `status="awaiting_human"`, present the export summary (shot count,
total duration, theme path, lint/traceability results), and **END YOUR TURN**.
