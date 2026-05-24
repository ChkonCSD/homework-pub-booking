# Ex6 — Rasa structured half

## Your answer

`RasaStructuredHalf.run()` POSTs a normalised booking intent to Rasa's
REST webhook and interprets the response. The pipeline is: loop-half
data dict → `normalise_booking_payload()` (via `validator.py`) produces
a Rasa-shaped message with canonical types → async HTTP POST in a
thread-pool executor so the event loop isn't blocked → parse the
response's `messages` array for `custom.action` ∈ {committed, rejected}
and emit the matching `HalfResult`.

Per the Friday May 22 Zoom decision, the homework uses **one flow**
(`confirm_booking`) rather than the three flows ASSIGNMENT.md asks for
— the in-file comment in `flows.yml` explains why
(`resume_from_loop` / `request_research` were removed; the
reverse-handoff is better done in Python at the bridge level — Ex7).
The flow validates → branches on `validation_error` → utters either
`utter_booking_confirmed` (with `booking_reference`) or
`utter_booking_rejected` (with `reason`).

`ActionValidateBooking` reads the booking dict from
`tracker.latest_message.metadata.booking` (because CALM's command
generator doesn't auto-promote metadata into slots), sets slot values,
then applies the two hard rules: `party_size > 8 → "party_too_large"`,
`deposit_gbp > 300 → "deposit_too_high"`. On success it derives a
deterministic `BK-<sha1_8>` booking reference so retries within a
session are idempotent.

Three design choices worth noting: (1) `ValidationFailed` raised in
`normalise_booking_payload` is caught in `run()` and returned as a
`HalfResult(success=False, next_action=escalate)` — the StructuredHalf
contract requires a HalfResult, not an exception. (2) Network errors
return `success=False` with `error_code=SA_EXT_SERVICE_UNAVAILABLE`,
keeping the bridge in control of retry policy. (3) The sender_id is a
SHA-1 hash of `venue+date+time`, so retries within one session reuse
the Rasa tracker.

In `sess_733570bc9e0e` (mock-mode `make ex6`) the booking
`{venue_id: haymarket_tap, party_size: 6, deposit_gbp: 200}` was
confirmed with reference `BK-7D401E9E`.

## Citations

- `sessions/examples/ex6-rasa-half/sess_733570bc9e0e/logs/trace.jsonl`
- `starter/rasa_half/validator.py` — `normalise_booking_payload`, `canonicalise_venue_id`, parsers
- `starter/rasa_half/structured_half.py` — `RasaStructuredHalf.run` + mock server
- `rasa_project/actions/actions.py` — `ActionValidateBooking` rules
- `rasa_project/data/flows.yml` — `confirm_booking` flow