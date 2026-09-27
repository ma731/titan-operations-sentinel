def _avoided_hours(baseline_lead: float, lead: float, failure_at: float) -> float:
    """Unplanned downtime hours an option avoids, if the machine fails at `failure_at`.

    Without the option the part arrives at `baseline_lead` (the standard, non-expedited
    route: what happens if nobody acts), so the machine stands for
    max(baseline_lead - failure_at, 0) hours before the repair can start. With the option
    it stands for max(lead - failure_at, 0). The repair itself takes the same time either
    way and cancels out. What an option buys is the difference.

    Simplifies to baseline_lead - max(failure_at, lead), floored at zero.
    """
    return max(max(baseline_lead - failure_at, 0.0) - max(lead - failure_at, 0.0), 0.0)


VALUE_BASIS_UPPER = (
    "production value at risk: revenue rather than margin, and before any output recovered "
    "by rerouting jobs to equivalent machines, so it is an upper bound on the money saved"
)


def expedite_cost(
    options: list[dict],
    downtime_cost_per_hour: float,
    failure_window_hours: int,
    baseline_lead_time_hours: float | None = None,
    failure_window_max_hours: float | None = None,
    margin_share: float = 1.0,
    rerouted_share: float = 0.0,
) -> dict:
    """
    Values each procurement/logistics option by the unplanned downtime it avoids against
    doing nothing, and ranks them.

    Tool catalog:
      Input:  options (list of {label, cost_eur, lead_time_hours, risk_level})
              downtime_cost_per_hour (float, EUR)
              failure_window_hours (int): predicted RUL minimum, the feasibility test
              baseline_lead_time_hours (float): the standard, non-expedited lead time,
                i.e. when the part arrives if nobody acts. The counterfactual.
              failure_window_max_hours (float, optional): predicted RUL maximum. Value is
                costed here, at the latest predicted failure, which is the conservative
                end: a later failure leaves less of the do-nothing outage to avoid.
              margin_share, rerouted_share (optional): turn production value into money
                actually lost. Defaults (1.0, 0.0) keep the upper bound and say so.
      Output: ranked options with downtime avoided, roi_ratio (avoided cost / option
              cost), the premium over the cheapest option that fits, and the break-even
              probability that justifies paying that premium
      Use when: multiple sourcing options exist, need cost justification for action plan
      Do NOT use: before parts gap is confirmed and failure timeline is known
      Fallback: if cost data missing, return options unranked with data_missing flag;
                if no baseline is given, value is not computed rather than guessed
      Risk tier: READ (autonomous)

    Until 2026-09 this tool valued an option at (failure window - lead time) x downtime
    cost: the hours of slack a part arrives with, not the downtime it prevents. See F-09.
    """
    w_min = float(failure_window_hours)
    w_max = float(failure_window_max_hours) if failure_window_max_hours is not None else w_min
    w_max = max(w_max, w_min)
    loss_per_hour = downtime_cost_per_hour * margin_share * (1.0 - rerouted_share)
    has_baseline = baseline_lead_time_hours is not None

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

        fits_window = (lead < w_min) if lead is not None else False
        entry = {
            "label": opt.get("label", "unlabelled option"),
            "cost_eur": cost,
            "lead_time_hours": lead,
            "fits_failure_window": fits_window,
            "buffer_hours": round(w_min - lead, 1) if lead is not None else None,
            "risk_level": opt.get("risk_level", "unknown"),
        }

        if has_baseline and lead is not None:
            base = float(baseline_lead_time_hours)
            conservative_h = _avoided_hours(base, lead, w_max)
            upper_h = _avoided_hours(base, lead, w_min)
            avoided_eur = conservative_h * loss_per_hour
            entry.update({
                "unplanned_downtime_hours": [round(max(lead - w_max, 0.0), 1),
                                             round(max(lead - w_min, 0.0), 1)],
                "downtime_avoided_hours": round(conservative_h, 1),
                "downtime_avoided_hours_if_early_failure": round(upper_h, 1),
                "downtime_cost_avoided_eur": round(avoided_eur, 2),
                "roi_ratio": round(avoided_eur / cost, 1) if (cost or 0) > 0 else None,
            })
        else:
            entry.update({"downtime_cost_avoided_eur": None, "roi_ratio": None})
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

    # The decision between two options that both fit the window is not "which avoids more
    # downtime": they avoid the same. It is whether the extra buffer is worth its premium.
    # Paying P more to protect value V is worth it if the cheaper route fails to arrive in
    # time with probability above P / V. That number is the one to put to a manager.
    fitting = [r for r in results
               if r["fits_failure_window"] and not r.get("data_missing")]
    cheapest = min(fitting, key=lambda r: r["cost_eur"]) if fitting else None
    for r in results:
        if cheapest is None or not r["fits_failure_window"] or r.get("data_missing"):
            continue
        premium = r["cost_eur"] - cheapest["cost_eur"]
        r["premium_over_cheapest_fitting_eur"] = round(premium, 2)
        protected = cheapest.get("downtime_cost_avoided_eur")
        if premium > 0 and protected:
            r["break_even_probability_cheapest_is_late"] = round(premium / protected, 4)

    out = {
        "options_ranked": results,
        "downtime_cost_per_hour_eur": downtime_cost_per_hour,
        "recommendation": results[0]["label"] if results else None,
        "failure_window_hours": [w_min, w_max],
        "baseline_lead_time_hours": baseline_lead_time_hours,
        "value_basis": (VALUE_BASIS_UPPER if margin_share == 1.0 and rerouted_share == 0.0
                        else f"lost margin after rerouting: {margin_share:.0%} margin, "
                             f"{rerouted_share:.0%} of output rerouted"),
        "roi_definition": ("downtime cost avoided against doing nothing, divided by the "
                           "option's cost, for this one incident. It is not the return "
                           "on building or running the system."),
    }
    if not has_baseline:
        out["note_value"] = ("No baseline_lead_time_hours given, so avoided downtime is not "
                             "computed. Pass the standard lead time: what happens if nobody "
                             "acts.")
    if any_missing:
        out["data_missing"] = True
        out["note"] = ("At least one option is missing cost or lead time. Options with "
                       "missing data are ranked last and cannot be committed autonomously.")
    return out
