def expedite_cost(
    options: list[dict],
    downtime_cost_per_hour: float,
    failure_window_hours: int,
) -> dict:
    """
    Calculates ROI for each procurement/logistics option against downtime cost.

    Tool catalog:
      Input:  options (list of {label, cost_eur, lead_time_hours, risk_level})
              downtime_cost_per_hour (float, EUR)
              failure_window_hours (int) — predicted RUL max
      Output: ranked options with roi_ratio, recommendation, risk assessment
      Use when: multiple sourcing options exist, need cost justification for action plan
      Do NOT use: before parts gap is confirmed and failure timeline is known
      Fallback: if cost data missing, return options unranked with data_missing flag
      Risk tier: READ (autonomous)
    """
    results = []
    any_missing = False
    for opt in options:
        lead = opt.get("lead_time_hours")
        cost = opt.get("cost_eur")
        # A quote that has not landed yet is a real state in a disruption, and it is not
        # the same as a cheap option. Carry it through with data_missing set rather than
        # crashing on the arithmetic or silently treating an unknown cost as zero: the
        # approval gate in policy.py reads a missing cost as "a human decides".
        missing = cost is None or lead is None
        any_missing = any_missing or missing

        fits_window = (lead < failure_window_hours) if lead is not None else False
        hours_saved = max(failure_window_hours - lead, 0) if lead is not None else 0
        downtime_avoided_cost = hours_saved * downtime_cost_per_hour
        roi_ratio = round(downtime_avoided_cost / cost, 1) if (cost or 0) > 0 else None

        entry = {
            "label": opt.get("label", "unlabelled option"),
            "cost_eur": cost,
            "lead_time_hours": lead,
            "fits_failure_window": fits_window,
            "downtime_cost_avoided_eur": round(downtime_avoided_cost, 2),
            "roi_ratio": roi_ratio,
            "risk_level": opt.get("risk_level", "unknown"),
        }
        if missing:
            entry["data_missing"] = True
        results.append(entry)

    risk_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "unknown": 3}
    results.sort(key=lambda x: (
        not x["fits_failure_window"],
        bool(x.get("data_missing")),      # a costed option outranks an uncosted one
        risk_rank.get(x["risk_level"], 3),
        -(x["roi_ratio"] or 0),
    ))
    out = {
        "options_ranked": results,
        "downtime_cost_per_hour_eur": downtime_cost_per_hour,
        "recommendation": results[0]["label"] if results else None,
    }
    if any_missing:
        out["data_missing"] = True
        out["note"] = ("At least one option is missing cost or lead time. Options with "
                       "missing data are ranked last and cannot be committed autonomously.")
    return out
