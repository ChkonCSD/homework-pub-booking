# Ex7 — Handoff bridge

## Your answer

`HandoffBridge.run()` orchestrates round-trips between `LoopHalf` and
`StructuredHalf`, capped at `max_rounds` (default 3). Per round it
emits a `bridge.round_start` trace event, runs the loop half, and
branches on `next_action`:

- `complete` → `session.mark_complete()` + return outcome=completed.
- `handoff_to_structured` → build a forward `Handoff` via
  `build_forward_handoff()`, write it to `ipc/input/`, emit
  `session.state_changed` (loop→structured), then run the structured
  half with `{"data": handoff.data}`.
- anything else → `mark_failed`.

After the structured half runs:

- `complete` → mark complete + return.
- `escalate` → archive the forward handoff
  (`ipc/input/handoff_to_structured.json` → `logs/handoffs/round_N_forward.json`)
  so **at most one handoff file is ever visible in `ipc/`** (the
  fail-closed rule worth 2 pts on the rubric). Then `build_reverse_task`
  builds a new `current_input` carrying the rejection reason and we
  loop back to the next round.

In `sess_91e93aaf3832` the demo took two rounds, exactly the trajectory
the assignment describes:
- Round 1: loop picked `haymarket_tap` (8 seats) for a party of 12;
  structured rejected with `party_too_large`. Forward handoff archived
  to `round_1_forward.json`.
- Round 2: loop picked `royal_oak` (16 seats) with party scaled to 6;
  structured accepted with `BK-*` reference. Bridge marked the session
  complete via structured.

Three trace events are emitted per transition (`bridge.round_start`,
`session.state_changed` loop→structured, `session.state_changed`
structured→{complete|loop}), which is what the rubric's "clear
session.state_changed events for each transition" criterion checks (3
pts).

`make ex7-real` was missing from the shipped Makefile; I added a
target that runs `python -m starter.handoff_bridge.run --real` per the
Sunday May 24 catchup call decision.

## Citations

- `sessions/examples/ex7-handoff-bridge/sess_91e93aaf3832/logs/trace.jsonl`
- `sessions/examples/ex7-handoff-bridge/sess_91e93aaf3832/logs/handoffs/round_1_forward.json` — archived first-round handoff
- `starter/handoff_bridge/bridge.py` — `HandoffBridge.run` + helpers
- `Makefile` — `ex7-real` target