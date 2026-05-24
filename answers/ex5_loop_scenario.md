# Ex5 — Edinburgh research loop scenario

## Your answer

In session `sess_0bfc9f84ffdd` the planner produced two subgoals: `sg_1`
(research Edinburgh venues near Haymarket for a party of 6, assigned to
loop) and `sg_2` (produce an HTML flyer with the chosen venue, weather,
and cost, also loop). Both ran in the same executor session.

The executor issued three tool calls in parallel for `sg_1` —
`venue_search`, `get_weather`, and `calculate_cost` — because all three
read fixtures and are registered with `parallel_safe=True`. `sg_2` then
called `generate_flyer` (registered with `parallel_safe=False` because
it writes `workspace/flyer.html`) and finally `complete_task`.

The integrity check was the highest-leverage piece. The shipped
`integrity.py` had two compounding bugs (Marat issue #10): a money
regex that missed `£ 540` (space after £), and `fact_appears_in_log`
scanning generate_flyer's own arguments, so fabricated values would
"verify" against themselves. The fix scans only tool *outputs* and
explicitly skips generate_flyer records. Multi-word phrases (e.g.
"Dalry Rd", "Castle Royal Grand Inn") use substring match against the
output tree so legitimate address fragments verify but fabricated venue
names don't.

## Citations

- `sessions/examples/ex5-edinburgh-research/sess_0bfc9f84ffdd/logs/trace.jsonl` — tool-call sequence
- `sessions/examples/ex5-edinburgh-research/sess_0bfc9f84ffdd/workspace/flyer.html` — produced flyer
- `starter/edinburgh_research/integrity.py` — `fact_appears_in_log` fix
- `grader/dataflow_probe.py` — scored 6/6 catching the planted £9999, Castle Royal Grand Inn, and "scorching 35C"