# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

In `sess_91e93aaf3832` (Ex7 round-trip), the handoff to structured half
was not because planner wrote `assigned_half: "structured"` in subgoal.
In both plans, round 1 and round 2, there was only one subgoal `sg_1`,
and it was assigned to loop.

So the real decision was made later by executor. In round 1, turn 2, it
called tool `handoff_to_structured` with arguments like
`{"reason": "loop half identified a candidate venue; passing to
structured half for confirmation under policy rules", "context":
"party of 12 near Haymarket on 2026-04-25 19:30; chosen venue
haymarket_tap", "data": {...booking...}}` (from `logs/trace.jsonl`).

For me the main signal is phrase "under policy rules" in the task
description. Executor reads it not like normal search task, but like
"now we must confirm this candidate using rules". This is exactly the
meaning of `handoff_to_structured`. Planner only planned to find
candidate venue. It did not decide who must confirm it. This part was
left for loop half and then appeared as tool call.

I think this handoff path is more clean than planner assigning structured
too early. If planner assigns structured before any tool result, it
commits without knowing if useful venue was found. Here executor already
found something useful, and sends it forward in `data`. The failure mode
is also clear: if loop half used `complete_task` instead of
`handoff_to_structured`, structured half would not run at all. Then
booking would be only researched, not really confirmed.

### Citation

- `sessions/examples/ex7-handoff-bridge/sess_91e93aaf3832/logs/trace.jsonl`
- `sessions/examples/ex7-handoff-bridge/sess_91e93aaf3832/logs/tickets/` — `executor.run_subgoal/sg_1` raw outputs
- `starter/handoff_bridge/run.py:69-88` — scripted executor call, as reference for expected LLM shape

---

## Q2 — Dataflow integrity catch

### Your answer

The grader dataflow probe (`grader/dataflow_probe.py`) puts three fake
facts into fresh copy of my flyer and runs my `verify_dataflow` again:
`£9999`, `Castle Royal Grand Inn`, and `scorching 35C`.

First version of my code caught only `£9999` (2/6). It happened because
money extractor found just bare digits, but probe checks by substring
against full planted string. My extractors returned too small pieces,
not the whole fake phrase. This partial result was still useful, because
it showed there are two different problems. One problem is not catching
fabrication. Another problem is catching right value, but reporting it
in form that next code cannot match.

The bigger problem was in shipped `fact_appears_in_log` function (Marat
issue #10). It checked both `r.output` and `r.arguments` for every tool
record. But `generate_flyer` arguments include
`event_details = {"total_gbp": 9999, ...}` exactly. So if flyer has fake
`£9999`, validator can match it against arguments of the same
`generate_flyer` call. It means flyer was almost verifying itself, which
is wrong.

The fix is simple in idea: check only `r.output`, and skip
`generate_flyer` records completely. The invariant is that all true
facts in flyer must come from tools before `generate_flyer`: from
`venue_search`, `get_weather`, or `calculate_cost` outputs. Flyer step
should only pass these values, not invent new facts. After this change,
and after more phrase-aware extraction (multi-word match for venue names
and small context window for atomic facts), probe became 6/6.

General lesson: if validator can read from same place as thing it is
validating, then self-verification path can appear. Better remove this
read path than add more small heuristics on top.

### Citation

- `sessions/examples/ex5-edinburgh-research/sess_0bfc9f84ffdd/workspace/flyer.html`
- `sessions/examples/ex5-edinburgh-research/sess_0bfc9f84ffdd/logs/trace.jsonl`
- `starter/edinburgh_research/integrity.py:99-138` — fixed `fact_appears_in_log` and comment with invariant
- `grader/dataflow_probe.py:27-31` — the three planted fake facts

---

## Q3 — Shipping to a real pub-booking business

### Your answer

*(This answers ASSIGNMENT.md §Ex9 Q3 — "first production failure and
which sovereign-agent primitive would surface it. One specific primitive,
one specific failure mode." Per the Friday May 22 Zoom decision the
ASSIGNMENT.md wording supersedes the older `Removing one framework
primitive` template heading.)*

**First production failure I'd expect:** **tool-fixture drift between
the agent's worldview and reality.** For example, real pub closes for
renovation, changes capacity, or removes vegan food from menu, but our
`venues.json`-like data is not refreshed for several days. Agent still
recommends Haymarket Tap for 12 people on Friday evening, but pub is
closed. Customer comes there and it is locked. Pub is angry, customer is
angry, and we maybe know only when support ticket comes.

**Primitive that surfaces it: manifest discipline.** Every tool has
discovery manifest: versioned schema for arguments, return shape, and
also contract about how fresh data should be. This manifest is like
contract between agent and reality. If `venue_search` says
`data_freshness: "polled_every_24h"`, then stale `last_refreshed_at` in
manifest is a machine-readable warning. It tells that booking advice may
be based on data which operator did not validate today.

This can surface before booking, not after, because each agent run reads
manifest when registering tools. Sovereign-agent `_RegisteredTool`
already has metadata. Missing part is what manifest promises and what
system does when promise is expired. Stale manifest is not always hard
error. It can mean degrade answer with caveat like "verify opening
hours", or refuse and escalate to human.

Without this discipline, agent cannot see difference between "I know
this venue exists" and "I know this venue is open tonight". Both look
like confident answer, but only one is safe for real customer.

### Citation

- `starter/edinburgh_research/tools.py:137-269` — `build_tool_registry`
  wires `_RegisteredTool` for each tool with `parameters_schema`,
  `returns_schema`, and `examples`; freshness contract would extend these
  manifest fields
- `sessions/examples/ex5-edinburgh-research/sess_0bfc9f84ffdd/logs/trace.jsonl`
  — discovery events
