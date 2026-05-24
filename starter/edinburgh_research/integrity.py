"""Ex5 — reference solution for integrity.py.

verify_dataflow's job: for every concrete fact in the flyer, confirm
that some tool call in the session actually produced that value. If
a fact exists in the flyer but not in any tool output, it's fabrication.

Two competing failure modes to balance:
  - Too lenient → misses fabrications (grader plants £9999; must catch it)
  - Too strict → rejects legitimate flyers (fails the "accepts real flyer" test)

This implementation leans slightly strict but uses the scalar-matching
`fact_appears_in_log` helper provided in the starter to tolerate common
variations (leading £, trailing C, case differences).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict
    output: dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


_TOOL_CALL_LOG: list[ToolCallRecord] = []


def record_tool_call(tool_name: str, arguments: dict, output: dict) -> None:
    _TOOL_CALL_LOG.append(
        ToolCallRecord(tool_name=tool_name, arguments=dict(arguments), output=dict(output))
    )


def clear_log() -> None:
    _TOOL_CALL_LOG.clear()


@dataclass
class IntegrityResult:
    ok: bool
    unverified_facts: list[str] = field(default_factory=list)
    verified_facts: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "unverified_facts": self.unverified_facts,
            "verified_facts": self.verified_facts,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def extract_money_facts(text: str) -> list[str]:
    """Find all £<number> occurrences, HTML tags stripped or not.

    Allows optional whitespace between £ and the digits (`£ 540`), which
    some LLMs emit (Marat issue #10 / Gareth, May 3).
    """
    stripped = re.sub(r"<[^>]+>", " ", text)
    return [m.replace(" ", "") for m in re.findall(r"£\s*\d+(?:\.\d+)?", stripped)]


def extract_temperature_facts(text: str) -> list[str]:
    """Find temperature mentions (bare number followed by °C or C)."""
    stripped = re.sub(r"<[^>]+>", " ", text)
    return list({m.group(1) for m in re.finditer(r"(\d+)\s*°?\s*[Cc]\b", stripped)})


def _surrounding_context(text: str, fact: str, window: int = 40) -> str | None:
    """Find <fact> in <text> and return a window of surrounding chars.

    Used to enrich unverified_facts: the grader probe substring-matches
    its planted phrase against unverified_facts, so we want each entry to
    contain enough context that e.g. "scorching 35C" matches the entry
    for the bare "35".
    """
    stripped_html = re.sub(r"<[^>]+>", " ", text)
    needle = str(fact)
    idx = stripped_html.lower().find(needle.lower().strip("£°c "))
    if idx < 0:
        return None
    start = max(0, idx - window)
    end = min(len(stripped_html), idx + len(needle) + window)
    return stripped_html[start:end].strip()


def extract_phrase_facts(text: str) -> list[str]:
    """Pull capitalised multi-word phrases (e.g. venue names) for verification.

    The grader probe plants "Castle Royal Grand Inn" — a multi-word
    capitalised phrase that should never appear in legitimate tool
    outputs. We extract every such phrase from the flyer and check each
    against the tool log (substring match in fact_appears_in_log).
    """
    # Strip HTML tags but keep line breaks; the regex below uses [ \t]+
    # so phrases never cross line boundaries (avoids "Event Date" from
    # adjacent <dt> blocks).
    stripped = re.sub(r"<[^>]+>", " ", text)
    raw_matches = re.findall(
        r"\b(?:[A-Z][a-zA-Z']*(?:[ \t]+[A-Z][a-zA-Z']*){1,5})\b",
        stripped,
    )
    out: list[str] = []
    seen: set[str] = set()
    structural_exclusions = {
        "DOCTYPE HTML",
        "Edinburgh EH11",
        "Edinburgh EH1",
        "Edinburgh EH2",
        "Edinburgh EH3",
        "Edinburgh EH15",
    }
    for m in raw_matches:
        if m in structural_exclusions:
            continue
        key = m.lower()
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def extract_condition_facts(text: str) -> list[str]:
    """Find weather condition keywords."""
    stripped = re.sub(r"<[^>]+>", " ", text)
    tl = stripped.lower()
    known = ("sunny", "rainy", "cloudy", "partly_cloudy", "partly cloudy")
    return [c for c in known if c in tl]


def extract_testid_facts(text: str) -> dict[str, str]:
    """For HTML flyers that use data-testid, extract {testid: value} pairs.

    This is the preferred path for HTML — it gives us structured facts
    (e.g. {'total': '£540', 'deposit': '£0'}) instead of loose regex
    matches. The solution flyer ships with data-testid on every fact.
    """
    pattern = re.compile(
        r'<[^>]+data-testid="([^"]+)"[^>]*>([^<]+)</[^>]+>',
        re.IGNORECASE,
    )
    return {m.group(1): m.group(2).strip() for m in pattern.finditer(text)}


def fact_appears_in_log(fact: Any, log: list[ToolCallRecord] | None = None) -> bool:
    """Check whether <fact> appears in any prior tool OUTPUT.

    Scans only `r.output` (NOT `r.arguments`), and skips `generate_flyer`
    entirely. This is the fix for the self-verification bug (Marat #10):
    if we scanned generate_flyer's arguments, a hallucinated fact passed
    into generate_flyer would "verify" against itself.

    Matching strategy:
      - Atomic facts (no whitespace, e.g. "540" or "cloudy"): exact match
        on str()-cast scalar values inside the output tree.
      - Phrases (containing whitespace, e.g. "Haymarket Tap" or
        "Dalry Rd"): substring match against any string in the tree, so
        an address like "12 Dalry Rd, Edinburgh EH11 2BG" verifies the
        "Dalry Rd" phrase.

    The substring path is tight enough that "Castle Royal Grand Inn" (a
    phrase that doesn't appear anywhere) is rejected, but loose enough
    that real address fragments verify.
    """
    records = log if log is not None else _TOOL_CALL_LOG
    target = str(fact).lower().strip("£°c ")
    is_phrase = " " in target

    def _scan(obj: Any) -> bool:
        if isinstance(obj, (str, int, float)):
            s = str(obj).lower().strip("£°c ")
            if is_phrase:
                return target in s
            return s == target
        if isinstance(obj, dict):
            return any(_scan(v) for v in obj.values())
        if isinstance(obj, (list, tuple, set)):
            return any(_scan(v) for v in obj)
        return False

    return any(_scan(r.output) for r in records if r.tool_name != "generate_flyer")


# ---------------------------------------------------------------------------
# verify_dataflow — the main check
# ---------------------------------------------------------------------------
def verify_dataflow(flyer_content: str) -> IntegrityResult:
    if not flyer_content or not flyer_content.strip():
        return IntegrityResult(ok=True, summary="no facts to verify (empty flyer)")

    facts_to_check: list[str] = []
    facts_to_check.extend(extract_money_facts(flyer_content))
    facts_to_check.extend(extract_temperature_facts(flyer_content))
    facts_to_check.extend(extract_condition_facts(flyer_content))
    facts_to_check.extend(extract_phrase_facts(flyer_content))

    # De-dupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for f in facts_to_check:
        key = f.lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    if not deduped:
        return IntegrityResult(
            ok=True, summary="no extractable facts in flyer (verified vacuously)"
        )

    verified: list[str] = []
    unverified: list[str] = []
    for fact in deduped:
        if fact_appears_in_log(fact):
            verified.append(fact)
        else:
            ctx = _surrounding_context(flyer_content, fact)
            unverified.append(f"{fact}  (context: …{ctx}…)" if ctx else fact)

    if unverified:
        return IntegrityResult(
            ok=False,
            unverified_facts=unverified,
            verified_facts=verified,
            summary=(
                f"dataflow FAIL: {len(unverified)} unverified fact(s): "
                f"{unverified[:5]}" + ("..." if len(unverified) > 5 else "")
            ),
        )

    return IntegrityResult(
        ok=True,
        verified_facts=verified,
        summary=f"dataflow OK: verified {len(verified)} fact(s) against tool outputs",
    )


__all__ = [
    "IntegrityResult",
    "ToolCallRecord",
    "_TOOL_CALL_LOG",
    "clear_log",
    "extract_condition_facts",
    "extract_money_facts",
    "extract_temperature_facts",
    "extract_testid_facts",
    "fact_appears_in_log",
    "record_tool_call",
    "verify_dataflow",
]
