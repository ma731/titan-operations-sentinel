import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "compliance"

# Most restrictive first, so a HALT always outranks an ESCALATE and an ESCALATE an OK.
SEVERITY = {"HALT": 0, "ESCALATE": 1, "OK": 2}


def _matches(rule: dict, text: str) -> bool:
    """Does this rule fire on the action text?

    Two rule shapes are supported, and the reason is worth stating because it is the
    whole point of this function.

    `keywords` is a flat OR: the rule fires if any term appears. That is fine for rules
    whose subject matter IS the keyword ("emergency maintenance", "reroute").

    `match` carries `all_of` (a list of groups, every group must hit) and/or `any_of` (a
    flat OR). SAFE-01 needs this: its own wording is "disables, bypasses, or modifies a
    safety interlock or guard", which is a conjunction of an ACTION and a HAZARD CONTROL.
    Expressed as a flat OR it had to include the bare token "safety", which halted
    "record the safety officer sign-off" while completely missing "jumper the light
    curtain". Both failure directions came from the same modelling error.
    """
    spec = rule.get("match")
    if spec:
        any_of = spec.get("any_of") or []
        if any_of and any(k in text for k in any_of):
            return True
        groups = spec.get("all_of") or []
        if groups and all(any(k in text for k in group) for group in groups):
            return True
        return False
    return any(k in text for k in rule.get("keywords", []))


def safety_gate(action_description: str) -> dict:
    """
    Classifies a proposed action against OSHA / machine-safety rules and returns a gate verdict.

    Tool catalog:
      Input:  action_description (str — plain text of the action being considered)
      Output: verdict (OK | ESCALATE | HALT), matched rule, authority, basis
      Use when: ANY action is about to be committed — the Compliance & Safety agent gates it (challenge 5)
      Do NOT use: to assess production capacity or quality — different agents
      Fallback: defaults to ESCALATE (fail safe) if rules unavailable
      Risk tier: this tool IS the safety control; its HALT verdict overrides other agents
    """
    f = DATA_DIR / "safety_rules.json"
    if not f.exists():
        return {"verdict": "ESCALATE", "reason": "safety_rules_unavailable — failing safe"}
    with open(f, encoding="utf-8") as fh:
        rules = json.load(fh).get("rules", [])

    text = (action_description or "").lower()
    matched = sorted(
        (r for r in rules if _matches(r, text)),
        key=lambda r: SEVERITY.get(r["verdict"], 3),
    )
    if not matched:
        return {"verdict": "OK", "action": action_description,
                "reason": "No safety rule matched; no incremental safety risk."}
    r = matched[0]
    return {
        "verdict": r["verdict"],
        "action": action_description,
        "matched_rule": r["rule_id"],
        "authority": r["authority"],
        "basis": r["basis"],
        "detail": r["detail"],
    }
