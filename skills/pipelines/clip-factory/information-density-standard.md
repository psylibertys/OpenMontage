# Information Density Standard — Clip Factory

Apply this standard to every clip-factory run, including revisions of an existing batch. Content-policy permissiveness never implies editorial permissiveness: a viewpoint may be retained while rambling, repetition, and delayed setup are removed.

## Opening Contract

The first spoken line must deliver a question, conflict, counter-intuitive claim, concrete result, or clear thesis within 0–3 seconds.

- Remove greetings, stream logistics, moderation/platform commentary, topic announcements, drawing preparation, self-qualification, and searches for words or facts.
- If the strongest line occurs later, use a 3–8 second cold open from that line, then return to only the minimum context needed. Record this reorder explicitly in the EDL.
- Subtract the cold-open source range from the later main-body ranges. No source-time overlap may play twice unless deliberate repetition is explicitly justified in the audit.
- Hook text alone does not rescue a weak spoken opening. Evaluate the audio opening and the overlay separately.
- Reject openings that begin with unresolved continuations such as “所以”, “然后”, “这个”, or a clipped half-sentence unless the preceding context is restored.

## Information-Density Pass

Review the transcript sentence by sentence after candidate selection and before scene approval. Remove or compress:

- repeated claims, examples, lists, or analogies that add no new information;
- filler such as “我来讲一下”, “我想想”, “什么来着”, “反正就是”, “明白了吗”, repeated stutters, and extended self-correction;
- live-chat replies, audience management, unrelated people/animals/room events, tool or drawing setup, and self-promotion;
- tangents that do not advance the title's promise;
- conclusions repeated after the point has already landed.

Every retained 20–30 second window must add at least one new claim, example, demonstration, consequence, or conclusion. If it does not, tighten it.

## Boundary And Pause Rules

- Never start or end mid-word, mid-sentence, or on an unresolved pronoun.
- Prefer semantic boundaries over round timestamps.
- Remove dead air and non-essential internal pauses longer than 1.2 seconds. A longer pause may remain only when it preserves a visible gesture, drawing, prop action, emotional beat, or necessary comprehension time; record the exception.
- End immediately after the payoff or complete conclusion. Remove trailing chat, repeated summaries, and setup for the next topic.
- When an EDL joins non-contiguous ranges, read the joined transcript aloud as one sequence. Reject fragments created by the join.
- Run an overlap audit on the ordered KEEP ranges. Accidental overlap is a hard failure because it repeats already-played speech.

## Candidate Disposition

Use one of three outcomes:

1. `keep`: already hook-led, coherent, dense, and cleanly bounded;
2. `tighten`: the topic is strong but needs cold-open reordering or internal cuts;
3. `replace_or_drop`: the available source cannot support the promised title or a complete payoff.

Do not preserve a weak clip merely to hit a count or minimum duration. A short complete clip is preferable to a padded long clip when the user allows short outputs.

## Required Audit Metadata

For each selected clip, record:

- `spoken_hook_source_start` and the exact first spoken line;
- `main_body_source_ranges` in playback order;
- `removed_ranges` with reasons (`slow_open`, `repeat`, `filler`, `tangent`, `dead_air`, `broken_boundary`);
- `cold_open_reorder` (`true`/`false`);
- `density_review` (`pass`/`revise`/`replace_or_drop`);
- expected post-edit duration;
- any pause longer than 1.2 seconds intentionally retained and why.

## Final Review

Inspect the actual rendered opening, a midpoint, and the ending of every output. A clip fails review if:

- the spoken hook has not landed by 3 seconds;
- the opening contains contextless or administrative speech;
- a joined cut produces a sentence fragment;
- a cold-open or other KEEP range is replayed because of overlapping source ranges;
- a tangent contradicts the title promise;
- the ending trails after the payoff;
- a non-essential pause longer than 1.2 seconds remains.

When any item fails, revise the EDL and re-render that clip; do not pass it with a warning.
