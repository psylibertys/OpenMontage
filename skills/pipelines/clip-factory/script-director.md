# Script Director - Clip Factory Pipeline

## When To Use

This stage converts the long-form source into a ranked candidate list and then into the final clip selections. You are mining for standout moments, not summarizing the entire source.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/script.schema.json` | Artifact validation |
| Prior artifact | `state.artifacts["idea"]["brief"]` | Batch goals and platform targets |
| Tools | `transcriber`, `scene_detect` | Transcript-first selection and visual checks |
| Density standard | `skills/pipelines/clip-factory/information-density-standard.md` | Binding candidate audit and hook rules |

## Process

### 1. Transcribe The Full Source

Use `transcriber` first. The transcript is the search surface for hooks, not an afterthought.

Use `scene_detect` only to sanity-check visual boundaries, speaker changes, or slide changes near promising moments.

### 2. Score Candidate Moments

Use the brief's ranking criteria and evaluate each moment on:

- `hook`
- `coherence`
- `value`
- `energy`
- `platform_fit`

This mirrors the way modern clipping products talk about virality and clip quality, while keeping the judgment transparent.

### 3. Apply The Standalone Test

Every approved clip must make sense to a cold viewer.

Reject or widen clips that contain:

- unresolved pronouns,
- references to earlier context,
- long lead-ins before the point lands,
- endings that stop before the payoff.

### 3b. Run The Information-Density Pass (Mandatory)

Read `information-density-standard.md` and audit every selected candidate sentence by sentence. Candidate discovery timestamps are search results, not approved edit boundaries.

- Identify the strongest spoken hook and require it to land within 0–3 seconds.
- Mark every removable range as `slow_open`, `repeat`, `filler`, `tangent`, `dead_air`, or `broken_boundary`.
- Use a 3–8 second cold open from later in the source when it materially improves the opening; record the reordered playback sequence.
- Classify each candidate `keep`, `tighten`, or `replace_or_drop`.
- Do not pad weak material to satisfy count or duration.

### 4. Select The Final Batch

Pick the smallest set that best satisfies the batch goal.

Maintain diversity across:

- source sections,
- speakers,
- clip families,
- energy levels.

### 5. Use Metadata For Ranking Truth

The script schema is small, so store the richer batch analysis in `script.metadata`.

Recommended metadata keys:

- `candidate_clips`
- `selected_clip_ids`
- `ranking_model`
- `rejected_candidates`
- `source_coverage_map`
- `platform_assignments`

Each candidate should record:

- source in/out,
- hook text,
- reason selected or rejected,
- scoring dimensions,
- likely crop viability.
- exact first spoken line and its source timestamp,
- main-body source ranges in playback order,
- removed ranges with reasons,
- density review status and expected post-edit duration.

### 6. Quality Gate

- the top-ranked clips are genuinely the strongest, not just the earliest found,
- every selected clip passes the standalone test,
- every selected clip passes the information-density standard,
- the set covers the source deliberately instead of clustering in one section,
- low-quality candidates are rejected honestly.

### Mid-Production Fact Verification

If you encounter uncertainty during script writing:
- Use `web_search` to verify factual claims before committing them to the script
- Use `web_search` to find reference images for visual accuracy
- Log verification in the decision log: `category="visual_accuracy_check"`

Every factual claim in the script should be traceable to the `research_brief`.
If you make a claim that isn't in the research, do additional research and
add the source. Do not invent statistics, dates, or attributions.

## Common Pitfalls

- Trusting first-pass candidate timestamps without transcript-level review.
- Treating broad semantic candidate windows as final EDL boundaries.
- Confusing permissive content review with permissive pacing.
- Selecting too many calm, same-energy clips.
- Preserving chronological order instead of ranking by quality.
- Treating transcript quality issues as minor when they affect selection accuracy.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
