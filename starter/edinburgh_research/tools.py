"""Ex5 tools. Four tools the agent uses to research an Edinburgh booking.

Each tool:
  1. Reads its fixture from sample_data/ (DO NOT modify the fixtures).
  2. Logs its arguments and output into _TOOL_CALL_LOG (see integrity.py).
  3. Returns a ToolResult with success=True/False, output=dict, summary=str.

The grader checks for:
  * Correct parallel_safe flags (reads True, generate_flyer False).
  * Every tool's results appear in _TOOL_CALL_LOG.
  * Tools fail gracefully on missing fixtures or bad inputs (ToolError,
    not RuntimeError).
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from sovereign_agent.errors import ToolError
from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import ToolRegistry, ToolResult, _RegisteredTool

from starter.edinburgh_research.integrity import _TOOL_CALL_LOG, record_tool_call

_SAMPLE_DATA = Path(__file__).parent / "sample_data"

_SPIRAL_THRESHOLD = 3


def _spiral_count(tool_name: str) -> int:
    return sum(1 for r in _TOOL_CALL_LOG if r.tool_name == tool_name)


def _load_json(path: Path, tool_name: str) -> object:
    if not path.exists():
        raise ToolError(
            code="SA_TOOL_DEPENDENCY_MISSING",
            message=f"{tool_name}: fixture {path.name} not found at {path}",
        )
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# venue_search
# ---------------------------------------------------------------------------
def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    """Search for Edinburgh venues near <near> that can seat the party.

    Reads sample_data/venues.json. Filters by:
      * open_now == True
      * area contains <near> (case-insensitive substring match)
      * seats_available_evening >= party_size
      * hire_fee_gbp + min_spend_gbp <= budget_max_gbp

    Returns a ToolResult with:
      output: {"near": ..., "party_size": ..., "results": [<venue dicts>], "count": int}
      summary: "venue_search(<near>, party=<N>): <count> result(s)"
    """
    args = {"near": near, "party_size": party_size, "budget_max_gbp": budget_max_gbp}

    venues = _load_json(_SAMPLE_DATA / "venues.json", "venue_search")
    near_lc = (near or "").lower()
    matches = [
        v
        for v in venues
        if v.get("open_now")
        and near_lc in (v.get("area") or "").lower()
        and v.get("seats_available_evening", 0) >= party_size
        and (v.get("hire_fee_gbp", 0) + v.get("min_spend_gbp", 0)) <= budget_max_gbp
    ]

    output = {"near": near, "party_size": party_size, "results": matches, "count": len(matches)}
    summary = f"venue_search({near}, party={party_size}): {len(matches)} result(s)"

    # Spiral guard for ex5-real (MainNotMaster recipe §7.3).
    record_tool_call("venue_search", args, output)
    if _spiral_count("venue_search") > _SPIRAL_THRESHOLD:
        seen = {
            v["id"]: v["name"]
            for r in _TOOL_CALL_LOG
            if r.tool_name == "venue_search"
            for v in r.output.get("results", [])
        }
        return ToolResult(
            success=True,
            output=output,
            summary=(
                f"{summary}. STOP calling venue_search — already found: "
                f"{', '.join(seen.values()) or '(none)'}. Pick one and call calculate_cost."
            ),
        )
    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# get_weather
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> ToolResult:
    """Look up the scripted weather for <city> on <date> (YYYY-MM-DD).

    Reads sample_data/weather.json. Returns:
      output: {"city": str, "date": str, "condition": str, "temperature_c": int, ...}
      summary: "get_weather(<city>, <date>): <condition>, <temp>C"
    """
    args = {"city": city, "date": date}
    data = _load_json(_SAMPLE_DATA / "weather.json", "get_weather")
    city_key = (city or "").lower()
    city_data = data.get(city_key)
    if not city_data or date not in city_data:
        err_output = {"city": city, "date": date, "error": "not_found"}
        record_tool_call("get_weather", args, err_output)
        return ToolResult(
            success=False,
            output=err_output,
            summary=f"get_weather({city}, {date}): no fixture entry",
            error=ToolError(
                code="SA_TOOL_INVALID_INPUT",
                message=f"No weather for city={city!r} on date={date!r}",
            ),
        )

    entry = city_data[date]
    output = {"city": city, "date": date, **entry}
    summary = f"get_weather({city}, {date}): {entry['condition']}, {entry['temperature_c']}C"
    record_tool_call("get_weather", args, output)
    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# calculate_cost
# ---------------------------------------------------------------------------
def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    """Compute the total cost for a booking. See docstring in shipped skeleton."""
    args = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
    }
    catering = _load_json(_SAMPLE_DATA / "catering.json", "calculate_cost")
    venues = _load_json(_SAMPLE_DATA / "venues.json", "calculate_cost")

    base_rates = catering["base_rates_gbp_per_head"]
    venue_mods = catering["venue_modifiers"]
    service_pct = catering["service_charge_percent"]
    deposit_policy = catering["deposit_policy"]

    if catering_tier not in base_rates:
        err_output = {**args, "error": "unknown_catering_tier"}
        record_tool_call("calculate_cost", args, err_output)
        return ToolResult(
            success=False,
            output=err_output,
            summary=f"calculate_cost: unknown catering_tier={catering_tier!r}",
            error=ToolError(
                code="SA_TOOL_INVALID_INPUT",
                message=f"catering_tier {catering_tier!r} not in {sorted(base_rates)}",
            ),
        )
    if venue_id not in venue_mods:
        err_output = {**args, "error": "unknown_venue_id"}
        record_tool_call("calculate_cost", args, err_output)
        return ToolResult(
            success=False,
            output=err_output,
            summary=f"calculate_cost: unknown venue_id={venue_id!r}",
            error=ToolError(
                code="SA_TOOL_INVALID_INPUT",
                message=f"venue_id {venue_id!r} not in {sorted(venue_mods)}",
            ),
        )

    venue = next((v for v in venues if v["id"] == venue_id), None)
    base = base_rates[catering_tier]
    mult = venue_mods[venue_id]
    hours = max(1, duration_hours)

    subtotal = int(round(base * mult * party_size * hours))
    service = int(round(subtotal * service_pct / 100))
    venue_fees = (venue["hire_fee_gbp"] + venue["min_spend_gbp"]) if venue else 0
    total = subtotal + service + venue_fees

    if total < 300:
        deposit_gbp = 0
        deposit_rule = deposit_policy["under_gbp_300"]
    elif total <= 1000:
        deposit_gbp = int(round(total * 0.20))
        deposit_rule = deposit_policy["gbp_300_to_1000"]
    else:
        deposit_gbp = int(round(total * 0.30))
        deposit_rule = deposit_policy["over_gbp_1000"]

    output = {
        **args,
        "subtotal_gbp": subtotal,
        "service_gbp": service,
        "total_gbp": total,
        "deposit_required_gbp": deposit_gbp,
        "deposit_rule": deposit_rule,
    }
    summary = (
        f"calculate_cost({venue_id}, party={party_size}): total £{total}, deposit £{deposit_gbp}"
    )
    record_tool_call("calculate_cost", args, output)
    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# generate_flyer
# ---------------------------------------------------------------------------
def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    """Produce an HTML flyer and write it to workspace/flyer.html.

    Tags every key fact with data-testid="<n>" so the integrity check can
    parse it as structured facts. parallel_safe=False (writes a file).
    """
    venue = event_details.get("venue_name", "(unknown venue)")
    address = event_details.get("venue_address", "")
    date = event_details.get("date", "")
    time = event_details.get("time", "")
    party = event_details.get("party_size", 0)
    condition = event_details.get("condition", "")
    temp_c = event_details.get("temperature_c", "")
    total = event_details.get("total_gbp", 0)
    deposit = event_details.get("deposit_required_gbp", 0)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(str(venue))} — {escape(str(date))}</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 600px; margin: 2em auto; color: #222; line-height: 1.5; }}
  h1 {{ color: #5a2d0c; border-bottom: 2px solid #5a2d0c; padding-bottom: 0.3em; }}
  h2 {{ color: #5a2d0c; margin-top: 1.5em; }}
  dl {{ display: grid; grid-template-columns: max-content auto; gap: 0.4em 1em; }}
  dt {{ font-weight: bold; }}
  .cost {{ background: #f4ead8; padding: 1em; border-radius: 4px; margin-top: 1em; }}
</style>
</head>
<body>
  <h1 data-testid="venue_name">{escape(str(venue))}</h1>
  <p data-testid="venue_address">{escape(str(address))}</p>

  <h2>Event</h2>
  <dl>
    <dt>Date</dt><dd data-testid="date">{escape(str(date))}</dd>
    <dt>Time</dt><dd data-testid="time">{escape(str(time))}</dd>
    <dt>Party size</dt><dd data-testid="party_size">{party}</dd>
  </dl>

  <h2>Weather forecast</h2>
  <dl>
    <dt>Condition</dt><dd data-testid="condition">{escape(str(condition))}</dd>
    <dt>Temperature</dt><dd data-testid="temperature_c">{temp_c}°C</dd>
  </dl>

  <h2>Cost</h2>
  <div class="cost">
    <dl>
      <dt>Total</dt><dd data-testid="total">£{total}</dd>
      <dt>Deposit required</dt><dd data-testid="deposit">£{deposit}</dd>
    </dl>
  </div>
</body>
</html>
"""
    path = session.workspace_dir / "flyer.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")

    output = {"path": "workspace/flyer.html", "bytes_written": len(html.encode("utf-8"))}
    summary = (
        f"generate_flyer: wrote workspace/flyer.html ({len(html)} chars). "
        f"Now call complete_task — flyer is done."
    )
    # Record AFTER the file is written but BEFORE returning so integrity sees it.
    # The integrity check intentionally ignores generate_flyer's args to prevent
    # self-verification of fabricated facts (§7.4).
    record_tool_call("generate_flyer", {"event_details": event_details}, output)
    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# Registry builder — DO NOT MODIFY the name, signature, or registration calls.
# The grader imports and calls this to pick up your tools.
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    """Build a session-scoped tool registry with all four Ex5 tools plus
    the sovereign-agent builtins (read_file, write_file, list_files,
    handoff_to_structured, complete_task).

    DO NOT change the tool names — the tests and grader call them by name.
    """
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    # venue_search
    reg.register(
        _RegisteredTool(
            name="venue_search",
            description="Search Edinburgh venues by area, party size, and max budget.",
            fn=venue_search,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "budget_max_gbp": {"type": "integer", "default": 1000},
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    # get_weather
    reg.register(
        _RegisteredTool(
            name="get_weather",
            description="Get scripted weather for a city on a YYYY-MM-DD date.",
            fn=get_weather,
            parameters_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"city": "Edinburgh", "date": "2026-04-25"},
                    "output": {"condition": "cloudy", "temperature_c": 12},
                }
            ],
        )
    )

    # calculate_cost
    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            description="Compute total cost and deposit for a booking.",
            fn=calculate_cost,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # pure compute, no shared state
            examples=[
                {
                    "input": {
                        "venue_id": "haymarket_tap",
                        "party_size": 6,
                        "duration_hours": 3,
                    },
                    "output": {"total_gbp": 540, "deposit_required_gbp": 0},
                }
            ],
        )
    )

    # generate_flyer — parallel_safe=False because it writes a file
    def _flyer_adapter(event_details: dict) -> ToolResult:
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            description="Write an HTML flyer for the event to workspace/flyer.html.",
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {"event_details": {"type": "object"}},
                "required": ["event_details"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file — MUST be False
            examples=[
                {
                    "input": {
                        "event_details": {
                            "venue_name": "Haymarket Tap",
                            "date": "2026-04-25",
                            "party_size": 6,
                        }
                    },
                    "output": {"path": "workspace/flyer.html"},
                }
            ],
        )
    )

    return reg


__all__ = [
    "build_tool_registry",
    "venue_search",
    "get_weather",
    "calculate_cost",
    "generate_flyer",
]
