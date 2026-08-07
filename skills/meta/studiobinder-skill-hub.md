# StudioBinder Skill Hub — Explicit Stage Guidance

## When to Use

Use this meta skill when a cinematic pipeline stage needs a reusable directing,
cinematography, screenplay, coverage, or production-recovery method from the 26
governed StudioBinder skills. It is a cross-stage Layer 2 adapter: OpenMontage
keeps the production decision and artifact contract; the external Skill Hub
supplies a versioned decision method.

Do not copy the governed skill bodies into OpenMontage. The source skills are read-only.

## Prerequisites

| Resource | Purpose |
|---|---|
| `config/studiobinder-stage-routing.yaml` | Explicit pipeline-stage-to-slug candidates |
| MCP server `treeelf-skill-hub` | `skills_health`, `skills_get`, and `skills_invoke` |
| Current pipeline manifest and stage director | The binding OpenMontage stage contract |
| Current canonical artifacts | Task, context, constraints, and prior approved decisions |
| `docs/treeelf-knowledge-sources.md` | Separate course evidence retrieval from method invocation |

The host Agent must expose the MCP server. This is an Agent capability, not a
Python `BaseTool`, provider, or generation runtime.

## Process

### Step 1: Check the Hub Once Per Run

Call `skills_health` before the first StudioBinder-assisted decision. Require a
healthy catalog and record its generation. Do not block unrelated pipeline work
when the hub is unavailable; follow the degraded path in Step 7.

### Step 2: Select Explicitly From the Stage Map

Read the current stage under `pipelines.cinematic` in
`config/studiobinder-stage-routing.yaml`. Select the smallest applicable set:

- normally one skill;
- only use a second or third when they govern genuinely different decisions;
- never exceed `max_skills_per_stage`;
- conditional entries require their stated real-world condition.

Do not use `skills_route` to make a production decision. Its free-text routing
quality has not passed the OpenMontage acceptance gate. `skills_search` may help
a human or Agent inspect the catalog, but the final slug still comes from the
explicit stage map.

### Step 3: Invoke One Skill at a Time

Call `skills_invoke` with the selected `skill_slug`, the concrete decision task,
and only the context needed for that decision. Use `compose=false` by default.
Do not send secrets, credentials, unpublished provider tokens, or entire source
artifacts when a focused summary is enough.

Good task:

> For scene s04, choose whether the slow dolly-in is motivated by the
> character's realization. Preserve the approved restrained tone.

Bad task:

> Make the whole video cinematic.

### Step 4: Apply the Packet Under OpenMontage Authority

Treat the returned ExecutionPacket as guidance, not as a new pipeline or a
permission to bypass stage rules. The current manifest, stage director,
approved proposal, renderer decision, provider decision, and human checkpoints
remain binding.

Translate the guidance into the stage's canonical artifact:

- research: visual rules and reference analysis in `research_brief`;
- proposal: intent and tradeoffs in `proposal_packet` and `decision_log`;
- script: observable beats and time design in `script`;
- scene plan: `shot_intent`, `shot_language`, `information_role`, and metadata;
- assets: dependency, coverage, and recovery decisions in `asset_manifest` metadata;
- edit: support-shot and timing decisions in `edit_decisions`.

### Step 5: Record Provenance

Add `metadata.studiobinder_guidance` to the canonical artifact when its schema
allows metadata, or record the same fields in the stage checkpoint metadata:

```json
{
  "mode": "explicit_stage_mapping",
  "catalog_generation": 12,
  "entries": [
    {
      "skill_slug": "motivated-camera-movement",
      "content_hash": "sha256:...",
      "applied_to": ["scene-s04"],
      "decision_summary": "Keep the dolly-in; it begins on the realization beat."
    }
  ]
}
```

Never paste the full ExecutionPacket into every scene. Preserve the identifiers,
hash, affected artifact IDs, and the decision actually adopted.

### Step 6: Retrieve Evidence Separately When Needed

Skill Hub guidance is the method and decision framework. Course Qdrant results
provide the supporting cases, evidence, and timecodes. When evidence is needed, query the controlled
retriever with `--agent openmontage-project-agent` and the appropriate
`cinematography` or `storytelling` domain as documented in
`docs/treeelf-knowledge-sources.md`.

Do not claim that a Skill Hub packet is course evidence. Do not claim visual
evidence was verified until the current Agent opens the referenced image or clip.

### Step 7: Use an Explicit Degraded Path

If the MCP server is missing, unhealthy, or the requested slug is not active:

1. record `studiobinder_guidance.status = "unavailable"` and the stable error code;
2. continue with the current OpenMontage stage director and existing Layer 2 skills;
3. optionally query the authorized course evidence source;
4. tell the user when the missing method materially reduces confidence;
5. never copy a stale skill body into this repository as a fallback.

### Step 8: Submit

Before checkpointing, validate the canonical artifact normally and include the
compact provenance record. StudioBinder guidance never changes the manifest's
human approval policy.

## Self-Evaluation

| Check | 1 | 3 | 5 |
|---|---|---|---|
| Selection | Free-text guess | Correct stage, broad choice | Explicit mapped slug with a concrete trigger |
| Scope | Whole production dumped into one call | Focused stage context | One decision with minimum sufficient context |
| Authority | Packet overrides pipeline | Pipeline mostly preserved | Manifest, approvals, and provider decisions remain binding |
| Provenance | No trace | Slug recorded | Slug, catalog_generation, content_hash, targets, and adopted decision recorded |
| Evidence | Method presented as proof | Evidence queried but weakly separated | Method and course evidence clearly separated and traceable |

Do not submit below 4/5 on selection, authority, or provenance.

## Common Pitfalls

- Calling every candidate listed for a stage instead of the smallest relevant set.
- Using `skills_route` because it is convenient despite the failed quality gate.
- Treating `skills_search` ranking as an approved production decision.
- Copying governed skill text into OpenMontage and creating two sources of truth.
- Letting guidance silently change an approved runtime, provider, budget, or checkpoint.
- Confusing a decision framework with Qdrant evidence or verified visual proof.
- Omitting `catalog_generation` or `content_hash`, making later audits ambiguous.
