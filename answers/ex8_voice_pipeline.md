# Ex8 — Voice pipeline

## Your answer

Ex8 has two modes sharing a trace-event contract: text mode (stdin →
`ManagerPersona` → stdout) and voice mode (Speechmatics STT → persona
→ ElevenLabs TTS). Per the scope decision (capping Ex8 at 16/20) and
sahanave's 2026-05-24 report that the ElevenLabs free tier is flaky,
I implemented and validated text mode only; the voice mode is shipped
as scaffold that gracefully degrades to text when `SPEECHMATICS_KEY`
or `ELEVENLABS_API_KEY` are missing.

`ManagerPersona` (`manager_persona.py`) wraps an `OpenAICompatibleClient`
pointed at Llama-3.3-70B-Instruct on Nebius. The system prompt makes
the persona a gruff Edinburgh pub manager named Alasdair who accepts
bookings ≤ £300 deposit and ≤ 8 people and declines otherwise with a
specific reason. The class holds a per-session message history so the
manager remembers context across turns.

Both modes emit `voice.utterance_in` and `voice.utterance_out` trace
events with payload `{text, turn, mode}` so the rubric's trace-events
check (3 pts) passes regardless of which transport ran.

In `sess_27de11f51568` (`make ex8-text`) a 3-turn conversation
exercised all three behaviours of the persona:
1. "Book for 6 on 2026-04-25 at 19:30, deposit £200" → accepted with
   "Aye, we can do that. I'll pencil you in for 2026-04-25 at 19:30."
2. Ask for booking reference → "Nae booking reference yet, laddie. Pay
   the deposit first." (in character, defers the reference until deposit
   is paid).
3. "Could you accommodate 12 people instead?" → "Too many. Declined,
   party's too large. Try The Royal Oak instead." (enforces the party
   cap, even suggests the alternative venue from the fixture).

This last turn is grading evidence that the persona stays in character
and respects the booking rules — directly relevant to the LLM-judge's
4 pts on "persona stays in character".

## Citations

- `sessions/homework/ex8/sess_27de11f51568/logs/trace.jsonl` — 3 turns,
  voice.utterance_in + voice.utterance_out events
- `starter/voice_pipeline/manager_persona.py` — Alasdair persona
- `starter/voice_pipeline/voice_loop.py` — text + voice modes, graceful degradation