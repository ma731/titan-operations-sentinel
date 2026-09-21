"""
Numeric groundedness: did the agent get that number from a tool, or invent it?

The citation metric catches an agent that invents a source. It does not catch the more
common and more expensive failure: an agent that cites nothing and simply states a
number. "ROI 94:1", "the bearing has 40 hours left", "the expedite costs 2,800 euros" all
read as authoritative, and a plant manager approving a spend has no way to tell which of
them came from a tool.

So every number in an agent's report is checked against the numbers its tools actually
returned. A number is grounded if it appears in a tool result, or is derivable from them
by the arithmetic the agents are expected to do (a ratio, a sum, a unit conversion).

Deliberate design choices, because a groundedness metric that cries wolf gets ignored:

- Small integers, years, percentages of the form "60%" and anything that appears in the
  task prompt are excluded. An agent writing "two technicians" or "the 6h trend window"
  is not hallucinating; it is reading its own instructions.
- Matching is tolerant of formatting. 3200, 3,200, 3200.0 and "EUR 3,200" are the same
  number, and 79.7 matches a computed 79.68.
- Derived values are accepted. An agent that multiplies 52 hours by 7,500 EUR/hour and
  writes 390,000 is doing its job, so sums, differences, products, ratios and round
  numbers built from tool values all count as grounded.

The metric is reported as a rate with the offending numbers listed, not as a pass/fail.
Some ungrounded numbers are legitimate rounding or restatement, and the list is there to
be read rather than to gate a build.
"""
from __future__ import annotations

import re

# A number with optional thousands separators and decimals. Currency symbols and units
# are stripped by the caller, so this matches the bare figure.
NUMBER_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:[, ]\d{3})+|\d+)(?:\.(\d+))?(?![\w])")

# Numbers this small are almost always counts, list indices, or the agent restating its
# own instructions ("two technicians", "5 jobs"). Flagging them produces noise.
MIN_INTERESTING = 10

# Tolerance for a derived figure, as a fraction. Agents round, so 79.7 has to match a
# computed 79.68 (0.03% apart). It is deliberately far tighter than that: at 1% an
# invented ROI of 94.3 was accepted because two unrelated tool values, 76 and 18, happen
# to sum to 94. Tolerance and combinatorics multiply, and the failure they cause is
# silent under-reporting of hallucination.
RELATIVE_TOLERANCE = 0.001


def _numbers_in(text: str) -> list[float]:
    out = []
    for m in NUMBER_RE.finditer(text or ""):
        whole = m.group(1).replace(",", "").replace(" ", "")
        frac = m.group(2)
        try:
            out.append(float(f"{whole}.{frac}") if frac else float(whole))
        except ValueError:
            continue
    return out


def _numbers_in_obj(obj) -> set[float]:
    """Every number anywhere in a tool result, at any nesting depth."""
    found: set[float] = set()
    if isinstance(obj, bool):
        return found
    if isinstance(obj, (int, float)):
        found.add(float(obj))
    elif isinstance(obj, str):
        found.update(_numbers_in(obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            found.update(_numbers_in(str(k)))
            found.update(_numbers_in_obj(v))
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            found.update(_numbers_in_obj(v))
    return found


def derivable(value: float, sources: set[float]) -> bool:
    """Is `value` reachable from the tool numbers by the arithmetic agents actually do?

    Division between arbitrary pairs is deliberately NOT allowed, and that restriction is
    the whole reason this function is trustworthy. With n source numbers there are n^2
    pairs; admitting ratios as well as products meant an invented ROI of 94.3 was accepted
    because 7500/79.7 happens to be 94.1. A derivation rule permissive enough to explain
    any number reports no hallucination at all, which is worse than having no metric.

    It is not needed anyway: the tools already compute the ratios. `expedite_cost` returns
    `roi_ratio` and `downtime_cost_avoided_eur`, so an agent quoting an ROI is restating a
    tool value, not dividing. What agents genuinely do by hand is scale a figure (per day
    to per hour) and multiply a rate by a duration, so those are what is allowed.

    The cost of the restriction is some false positives: an agent doing an unusual but
    legitimate division gets flagged. That is the right direction for this metric to err.
    """
    if _close(value, sources):
        return True

    # Unit and scale conversions: per-day to per-hour, thousands, percentages, minutes.
    for s in sources:
        for candidate in (s / 24, s * 24, s / 1000, s * 1000, s / 100, s * 100, s / 60):
            if _close_one(value, candidate):
                return True

    # One operation between two source values. Sums, differences and products only.
    ordered = sorted(sources)
    for i, a in enumerate(ordered):
        for b in ordered[i:]:
            if any(_close_one(value, c) for c in (a + b, b - a, a * b)):
                return True
    return False


def _close_one(value: float, candidate: float) -> bool:
    if candidate is None:
        return False
    if value == candidate:
        return True
    scale = max(abs(value), abs(candidate), 1.0)
    return abs(value - candidate) / scale <= RELATIVE_TOLERANCE


def _close(value: float, sources: set[float]) -> bool:
    return any(_close_one(value, s) for s in sources)


def score_report(report: str, tool_results: list, prompt: str = "") -> dict:
    """Check one agent report against the tool results that agent saw.

    `prompt` is the task text the agent was given; numbers quoted from it are grounded by
    definition, because the agent was told them."""
    given = set()
    for obj in tool_results:
        given |= _numbers_in_obj(obj)
    given |= set(_numbers_in(prompt))

    checked, ungrounded = 0, []
    for value in _numbers_in(report):
        if abs(value) < MIN_INTERESTING:
            continue
        if 1900 <= value <= 2100 and float(value).is_integer():
            continue                                  # a year, not a claim
        checked += 1
        if not derivable(value, given):
            ungrounded.append(value)

    return {
        "numbers_checked": checked,
        "ungrounded": sorted(set(ungrounded)),
        "grounded_rate": round((checked - len(ungrounded)) / checked, 4) if checked else None,
        "tool_numbers_available": len(given),
    }


def score_run(reports: dict[str, str], tool_results_by_agent: dict[str, list],
              prompts: dict[str, str] | None = None) -> dict:
    """Aggregate groundedness across every agent in one run."""
    prompts = prompts or {}
    per_agent, checked, ungrounded = {}, 0, 0
    for agent, report in reports.items():
        result = score_report(report, tool_results_by_agent.get(agent, []),
                              prompts.get(agent, ""))
        per_agent[agent] = result
        checked += result["numbers_checked"]
        ungrounded += len(result["ungrounded"])
    return {
        "numbers_checked": checked,
        "ungrounded_numbers": ungrounded,
        "grounded_rate": round((checked - ungrounded) / checked, 4) if checked else None,
        "by_agent": per_agent,
    }
