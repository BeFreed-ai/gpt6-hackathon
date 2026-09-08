# Private life direction and continuing projects

Each citizen has an independent `AgentState.life` alongside the legacy `active_goal`.
The latter remains the current action goal, so seeking lunch does not erase a direction,
a garden project, or a commitment to repairing a neighbor's kitchen. Empty life state is
the default. No demographic attributes assign a personality, direction, project, or value.
The model chooses its own ambitions using private experience and current circumstances.

## State and turn contract

`LifeState` contains an optional direction, up to 24 retained projects, a recall request,
and a revision counter. Up to six projects can be active concurrently. Every project has
a stable ID, title, independent goal, next step, commitment, evidence memory IDs, status,
timestamps, and one to six concrete milestones. Milestones track progress from zero to
one and their supporting memories. Inspector progress is the mean milestone progress;
it is an agent's evidence-linked report, not a new physical simulator metric.

`AgentDecision.life_update` defaults to `None`. A turn may change the direction, create
one project, change at most two project records, and request personal memory recall.
Ordinary actions need no life update. Local demo decisions do not manufacture life plans.

- `advance`: update one known milestone using existing experiential evidence.
- `revise`: change the next step or strength of commitment.
- `suspend` / `resume`: pause an active project or reactivate a suspended one.
- `finish`: close an active project whose milestones are all complete.
- `abandon`: close an active or suspended project with a brief note.

Finished and abandoned projects remain inspectable and cannot be silently overwritten.
Direction changes and every accepted project update create a private `life_plan` memory
containing the explicit update, preserving prior intentions and commitments. No hidden
reasoning is requested, parsed, stored, or displayed. These records are self-reports and
are marked `inference`; they do not assert that an intended physical action occurred.

Project and milestone IDs are 1–48 letters, numbers, underscores, or hyphens. Evidence
references have the same length bound and must name distinct memories belonging to that
citizen. Each citation list has at most eight IDs. Project creation and changes require
at least one citation. A freely chosen direction may start without a citation. Most
plan text is limited to 240 characters, titles to 80, and recall queries to 120.
Unknown projects, milestones, memory IDs, duplicate IDs, invalid transitions, nonfinite
progress, regressions, and exceeded capacities reject the entire life update atomically.
An inference or plan alone cannot establish milestone progress. Testimony is still
testimony: validation verifies provenance and structure, not semantic truth of a claim.

## Exact World integration API

All helpers are in `app.life`:

```python
select_memory_context(agent: AgentState, limit: int = 40) -> dict
life_context(agent: AgentState) -> dict
apply_life_update(agent: AgentState, update: LifeUpdate | None, now: float) -> list[Memory]
restore_life_from_memories(agent: AgentState) -> None
```

In `World.context_for`, replace the unbounded `recent_memories` assignment with
`**select_memory_context(agent)` and add `"life": life_context(agent)` if desired.
The brain also supplies `life` at the top level of its private payload. Bound `new_events`
independently so the inbox cannot bypass the selected-memory budget.

After known-target validation in `World.apply_decision`, apply the optional update:

```python
try:
    audit_memories = apply_life_update(agent, decision.life_update, self.time)
except ValueError:
    audit_memories = []  # Reject the private update; keep a legal physical action usable.
for memory in audit_memories:
    self.store.append_memory(agent.id, memory)
```

The helper already appends each audit memory to `agent.memories`; do not append twice.
The owner can record a concise validation status to help the model correct an invalid
update. Never broadcast private plan updates. Keep existing `active_goal` handling for
compatibility, and exclude `life` from public snapshots, nearby-agent observations and
other citizens' context. Expose it only in the selected citizen's private inspector.

## Raw history, bounded prompts, and recall

Raw memory objects and durable memory records are never truncated or summarized in place.
Context selection reserves space for recent events, recall results, project evidence,
autobiographic anchors (including `personal_background`), and important experiences.
It fills spare capacity by recency and returns selected memories in time order. Default
capacity is 40 records; callers can choose 8–80. Prompt copies cap `content` at 1,200
characters and `message` at 500 with explicit truncation flags. This is a memory-context
bound, not a cap on all other world observations or background fields.

The companion `memory_context` reports total, selected and omitted record counts,
truncated memory IDs, recall match count, and selected recall IDs. Omission means
selection, not deletion. The inspector and durable archive can retain full text.
Autobiography also remains in the private identity background.

`life_update.recall` accepts a short query and/or up to eight already known memory IDs.
Matching personal records appear in the next ordinary decision context, without an
extra model request or external data access. Keyword matching is case-insensitive;
recall can remain active until the agent replaces it or submits an empty recall object.
Many matches remain bounded and their counts are disclosed. Long recalled records are
still subject to prompt-copy text caps; arbitrary text paging is not implemented.

Checkpoint persistence should serialize every `AgentState` field and all raw memories.
Pydantic JSON round trips preserve life state and timestamps. Where an owner has loaded
the complete ordered personal memory archive instead, `restore_life_from_memories`
replays our explicit audit entries atomically and retains their original IDs. It does
not reseed, append memories, or write storage. Process startup, loading archives,
checkpoint atomicity, and private/public API boundaries belong to World integration.

## Compatibility and limits

The local `ACTION_SCHEMA` accepts older decisions without `life_update`; the provider
schema requires the nullable field and all nested keys for strict structured output.
Novita V4 Pro continues using JSON-object mode plus the explicit schema in its system
prompt and local validation. Other supported model routes retain JSON-schema mode.
Only final response content is parsed. Model configuration and existing credential
selection are unchanged; validation uses fakes and makes no paid API calls.

Plans are not a scheduler or a guarantee of long-horizon competence. The simulator does
not infer arbitrary real-world project completion, prove that a cited memory justifies
a claim, or grant tools beyond existing actions. The fixed 24-project ledger can fill;
it deliberately preserves closed projects instead of evicting history. New milestones
cannot be inserted into an existing project in this version; a revised next step can
adapt execution, and a genuinely different goal can become another project. Lexical
recall has no semantic index and context selection scans the in-memory personal history.
These bounded, explicit mechanisms favor reviewable updates over a rewritten life plan.

Validation covers backward-compatible decisions, strict provider schemas, concurrent
projects, hunger detours, lifecycle transitions, evidence validation, atomic rejection,
JSON persistence, audit replay, selected memory diversity, omission disclosure, long-text
preservation, and internal recall. Runtime World/checkpoint/UI tests belong to integration.
