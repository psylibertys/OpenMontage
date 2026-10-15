# Compose Director - Clip Factory Pipeline

## When To Use

Render each clip and platform variant independently. The important behaviors here are consistency, batch resilience, and clear reporting of partial failures.

## Runtime Routing (HARD CONSTRAINT — Remotion or FFmpeg only)

This pipeline is Phase 1 deferred from the HyperFrames adoption schedule. `edit_decisions.render_runtime` must be `"remotion"` (default) or `"ffmpeg"` (pure-concat clip jobs with no composition). HyperFrames is NOT a valid runtime here — clip-factory depends on Remotion word-level caption burn, and HyperFrames caption parity is deferred work.

- If `edit_decisions.render_runtime == "hyperframes"`, stop. Re-open the idea stage so the user can be presented the real constraint and lock `remotion` with a `render_runtime_selection` decision that records `hyperframes` as `rejected_because: "caption-burn parity deferred on clip-factory"`.
- Per AGENT_GUIDE.md → "Present Both Composition Runtimes (HARD RULE)": the constraint is NOT an excuse to skip the conversation. The user still gets to see that HyperFrames exists and why it isn't viable here.
- Pass `proposal_packet`/`brief` to `video_compose.execute()` so the in-tool runtime-swap check runs end-to-end.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | Clip edits and assets |
| Tools | `video_trimmer`, `video_compose`, `audio_mixer`, `color_grade` | Render pipeline |
| Hard QA tool | `clip_delivery_audit` | Exact frame-zero cover + final-MP4 word-timing audit |
| Media profiles | `lib/media_profiles.py` | Platform targets |
| Density standard | `skills/pipelines/clip-factory/information-density-standard.md` | Binding semantic checks on rendered outputs |

## Process

### 1. Treat Each Output As Its Own Job

One clip across three platforms is three render jobs. Name and track them explicitly.

### 2. Reuse What Can Be Shared

- shared audio mix where possible,
- shared subtitle styling,
- shared overlay assets,
- shared grading if the source needs it.

### 3. Fail Softly

If one clip or one platform variant fails:

- log it clearly,
- continue the rest of the batch,
- do not block successful exports.

### 4. Verify Every Output

Per render:

- correct duration,
- correct resolution/aspect ratio,
- no black opening frame,
- frame zero is a usable cover with the approved persistent hook/title already at full opacity,
- a matching standalone cover image is exported alongside the batch,
- subtitles render correctly,
- audio is present and consistent.

Inspect frame `n=0` explicitly. Sampling at one or two seconds is not a cover
check. A persistent hook must not use an entrance animation whose frame-zero
opacity is zero; entrance animation is allowed only for an intro-only hook.

Use this binding order for every batch:

1. Render the final MP4.
2. Extract exact video frame `n=0`; do not seek to `1s` or use a master/intermediate.
3. Open that image and compare it with `expected_hook_title`. Record
   `frame_zero_title_visible=true` only after direct visual inspection.
4. Run `clip_delivery_audit` against the final MP4 and the caption JSON. Use
   `backend="qwen3-asr"`, alignment enabled, matched-word ratio `>= 0.70`, and
   p90 absolute start-time error `<= 0.30s`.
5. Export the approved exact frame-zero image as the standalone cover.
6. Validate `clip_delivery_audit` against its schema and require `status=pass`.

Mirror the measured evidence into `final_review`:

- set `visual_spotcheck.exact_frame_zero_reviewed=true`,
- record all `frame_zero_paths` and `standalone_cover_paths`,
- set `visual_spotcheck.frame_zero_title_visible=true` only when every clip passed,
- set `subtitle_check.verification_method="final_audio_retranscription_word_alignment"`,
- record the batch minimum matched-word ratio, maximum p90 error, and
  `audit_artifact` path.

Do not create a compose checkpoint marked completed when the audit is absent,
has fewer outputs than the render report, or contains any failed clip. A
visual subtitle spotcheck, matching durations, or inspecting the pre-render
WAV does not substitute for final-MP4 re-transcription.

After rendering, re-transcribe the actual final audio and match those word
timestamps against the subtitle JSON.  Static frames and ffprobe cannot prove
synchronization.  Require at least 70% matched subtitle words and a p90
absolute start-time error no greater than 0.3 seconds for every clip; any
failure requires rebuilding the media-time mapping, EDL, and captions before
delivery.

For every clip, inspect the actual rendered first 3 seconds, one midpoint sample, and the ending. Verify:

- the first spoken line is the approved hook and lands by 3 seconds,
- no administrative or contextless speech precedes it,
- non-contiguous EDL joins form complete sentences,
- the midpoint still advances the title promise,
- the ending stops immediately after a complete payoff,
- no non-essential pause longer than 1.2 seconds remains.

Any semantic failure requires an EDL revision and re-render. Do not pass it as a warning merely because ffprobe succeeds.

### 5. Use Render Report Metadata

Recommended metadata keys:

- `job_index`
- `failed_jobs`
- `shared_intermediates`
- `platform_groupings`

## Common Pitfalls

- Rendering sequentially without reason when jobs are independent.
- Treating a failed clip as a reason to stop the batch.
- Letting one platform variant quietly use the wrong framing or subtitle zone.
- Treating technical probe success as proof that the content edit is good.
- Reviewing still frames without listening to the opening and joined cuts.
- Sampling at one second and calling it a cover review.
- Auditing the source WAV or Remotion master instead of the delivered MP4.
- Marking `timing_drift_detected=false` without measured word-alignment evidence.
