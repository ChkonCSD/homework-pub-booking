# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

In `sess_91e93aaf3832` (the Ex7 round-trip), the handoff to the
structured half did NOT come from the planner naming
`assigned_half: "structured"` on a subgoal. Both plans (round 1 + round
2) had a single subgoal `sg_1` assigned to loop. The handoff was the
executor's choice: turn 2 of round 1 issued the tool call
`handoff_to_structured` with arguments
`{"reason": "loop half identified a candidate venue; passing to
structured half for confirmation under policy rules",
"context": "party of 12 near Haymarket on 2026-04-25 19:30; chosen
venue haymarket_tap", "data": {...booking...}}` (see
`logs/trace.jsonl`).

The signal that drove the call was the task description containing
"under policy rules". The executor LLM reads this and decides
"this is a confirmation-against-rules step, not an open-ended
research step", which is the trained semantics of
`handoff_to_structured`. The planner's role was scoped to
"find a candidate venue"; the architectural decision of *who confirms*
was deferred to the loop and surfaced as a tool call.

This is actually the cleaner of the two handoff paths: a planner that
pre-assigns structured commits to a half before seeing tool results,
while an executor that calls `handoff_to_structured` mid-loop has
already verified that *something useful was found* — and the
forward-handoff `data` carries that something. Failure mode: if the
loop half exited via `complete_task` instead of `handoff_to_structured`,
the structured half would never run and the booking would only be
"researched", not "confirmed".

### Citation

- `sessions/examples/ex7-handoff-bridge/sess_91e93aaf3832/logs/trace.jsonl`
- `sessions/examples/ex7-handoff-bridge/sess_91e93aaf3832/logs/tickets/` — `executor.run_subgoal/sg_1` raw outputs
- `starter/handoff_bridge/run.py:69-88` — the scripted executor call (reference for the LLM's expected shape)

---

## Q2 — Dataflow integrity catch

### Your answer

The grader's dataflow probe (`grader/dataflow_probe.py`) plants three
fabrications into a fresh copy of my flyer and re-runs my
`verify_dataflow`: `£9999`, `Castle Royal Grand Inn`, `scorching 35C`.
The first run of my implementation caught only `£9999` (2/6 — the money
extractor found the bare digits, but the probe substring-matches the
full planted string, and my extractors only returned atomic fragments).
That partial result was itself a real catch worth recording: it forced
me to discover that the integrity check has TWO failure modes, not one
— missing the fabrication (under-strict), and catching the right value
but reporting it in a form the consumer can't pattern-match on.

The deeper catch was a self-verification bug in the shipped
`fact_appears_in_log` (Marat issue #10). It scanned both `r.output` AND
`r.arguments` of every tool record. `generate_flyer`'s arguments
contain `event_details = {"total_gbp": 9999, ...}` exactly — so a
hallucinated `£9999` in the flyer would match against `generate_flyer`'s
*own* log entry and verify cleanly. The flyer was effectively grading
itself.

The fix is one line in semantics: scan only `r.output`, and skip
`generate_flyer` records entirely. The invariant we now rely on: every
legitimate fact in the flyer originates upstream of `generate_flyer`
(in `venue_search` / `get_weather` / `calculate_cost` outputs). The
agent only passes those values through; it never introduces new ones at
the flyer step. With that fix plus phrase-aware extraction (multi-word
substring match for venue names, surrounding-context window for atomic
unverified facts), the probe scored 6/6.

Generalisation: anytime a validator can read from the same source as
the thing it validates, it has a self-verification path. Removing that
read is more robust than adding heuristics on top of it.

### Citation

- `sessions/examples/ex5-edinburgh-research/sess_0bfc9f84ffdd/workspace/flyer.html`
- `sessions/examples/ex5-edinburgh-research/sess_0bfc9f84ffdd/logs/trace.jsonl`
- `starter/edinburgh_research/integrity.py:99-138` — fixed `fact_appears_in_log` + comment explaining the invariant
- `grader/dataflow_probe.py:27-31` — the three plants

---

## Q3 — Shipping to a real pub-booking business

### Your answer

*(This answers ASSIGNMENT.md §Ex9 Q3 — "first production failure and
which sovereign-agent primitive would surface it. One specific primitive,
one specific failure mode." Per the Friday May 22 Zoom decision the
ASSIGNMENT.md wording supersedes the older `Removing one framework
primitive` template heading.)*

**First production failure I'd expect:** **tool-fixture drift between
the agent's worldview and reality.** A real pub closes for
renovation, changes its capacity, or removes vegan options from its
menu, and our `venues.json`-equivalent isn't refreshed for a week. The
agent confidently recommends Haymarket Tap for 12 people on a Friday
the pub is shut. The customer shows up to a locked door. The pub is
furious. We don't notice until the support ticket lands on Monday.

**Primitive that surfaces it: manifest discipline.** Each tool ships a
discovery manifest — a versioned schema describing its arguments,
return shape, and (importantly) the freshness contract of its data.
The manifest is the agent's contract with reality. If `venue_search`
declares `data_freshness: "polled_every_24h"`, then a manifest with a
stale `last_refreshed_at` is a loud, machine-readable signal that the
booking advice the agent is about to give is based on data the
operator hasn't validated today.

The failure surfaces *before* the booking, not after, because every
agent invocation reads the manifest as part of tool registration —
sovereign-agent's `_RegisteredTool` already carries the metadata; the
discipline is in WHAT the manifest declares and HOW we react when its
guarantees lapse. A manifest with stale data isn't an error — it's
permission to either degrade gracefully (recommend with a "verify
opening hours" caveat) or refuse (escalate to a human). Without that
discipline, the agent has no way to distinguish "I know about this
venue" from "I know this venue is open tonight"; both surface as
identical-looking confident answers, and the customer's evening is the
debug log.

### Citation

- `starter/edinburgh_research/tools.py:137-269` — `build_tool_registry`
  wiring `_RegisteredTool` per tool with `parameters_schema`,
  `returns_schema`, and `examples` (the existing manifest fields a
  freshness contract would extend)
- `sessions/examples/ex5-edinburgh-research/sess_0bfc9f84ffdd/logs/trace.jsonl`
  — discovery events