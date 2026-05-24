# Session sess_4da4d366baf2

**Scenario:** edinburgh-research
**Created:** 2026-05-25T01:03:22.941049+00:00

## Your task

(The loop half reads this file on every turn. The initial task description
has been written below by the orchestrator when the session was created.
Additional per-session instructions — constraints, identity, voice — can
be added by the scenario author.)

## Task description

Research an Edinburgh pub and produce an HTML event flyer.

FIXED PARAMETERS (DO NOT CHANGE — do not invent different values):
  - party_size = 6  (six guests, exactly)
  - date = 2026-04-25  (a Saturday)
  - time = 19:30
  - area = Haymarket  (pass `near='Haymarket'` to venue_search)
  - city = edinburgh
  - duration_hours = 3
  - catering_tier = bar_snacks
  - budget_max_gbp = 800

REQUIRED tool sequence (exactly four tools, in this order, each called ONCE — do NOT re-call venue_search with different parameters, do NOT skip generate_flyer, do NOT call handoff_to_structured):
  1. venue_search(near='Haymarket', party_size=6, budget_max_gbp=800)
  2. get_weather(city='edinburgh', date='2026-04-25')
  3. calculate_cost(venue_id=<id of a venue returned by step 1>,
                    party_size=6, duration_hours=3,
                    catering_tier='bar_snacks')
  4. generate_flyer(event_details={'venue_name': ...,
                    'venue_address': ..., 'date': '2026-04-25',
                    'time': '19:30', 'party_size': 6,
                    'condition': <from step 2>,
                    'temperature_c': <from step 2>,
                    'total_gbp': <from step 3>,
                    'deposit_required_gbp': <from step 3>})
  5. complete_task(result={'flyer': 'workspace/flyer.html', ...})

RULES:
  - This is a LOOP-only scenario. DO NOT call handoff_to_structured.
  - DO NOT call complete_task until generate_flyer has run.
  - If venue_search returns zero results, do NOT retry with different parameters; the fixture is deterministic and the given parameters DO yield results. Re-read the docstring.
  - The scenario is graded by the existence of workspace/flyer.html, not by your final text response.

## Constraints

- Be honest when you do not know something.
- Prefer reading memory over guessing.
- When the task is ambiguous, ask for clarification rather than inventing an answer.
