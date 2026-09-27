from datetime import datetime, timezone


def notify(
    recipient_role: str,
    subject: str,
    situation_summary: str,
    recommended_actions: list[dict],
    cost_of_inaction_eur: float,
    cost_of_recommended_plan_eur: float,
    decision_deadline_utc: str,
    work_order_id: str | None = None,
) -> dict:
    """
    Drafts an approval request notification to the appropriate decision-maker.

    Tool catalog:
      Input:  recipient_role, subject, situation_summary, recommended_actions,
              cost_of_inaction_eur (the recommended option's downtime_cost_avoided_eur
              from expedite_cost, so both tools report the same ratio),
              cost_of_recommended_plan_eur,
              decision_deadline_utc, work_order_id (optional)
      Output: draft notification dict — NOT sent until human reviews
      Use when: action plan requires human cost authority or schedule approval
      Do NOT use: for routine status updates or AUTO-tier actions
      Fallback: if recipient_role unknown, escalate to plant_manager by default
      Risk tier: APPROVE (human sends or rejects)
    """
    return {
        "notification_id": f"NOTIF-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "status": "DRAFT_PENDING_SEND",
        "recipient_role": recipient_role,
        "subject": subject,
        "body": {
            "situation": situation_summary,
            "recommended_actions": recommended_actions,
            "cost_of_inaction_eur": cost_of_inaction_eur,
            "cost_of_plan_eur": cost_of_recommended_plan_eur,
            "roi_ratio": round(cost_of_inaction_eur / cost_of_recommended_plan_eur, 1)
            if cost_of_recommended_plan_eur > 0 else None,
            "decision_required_by_utc": decision_deadline_utc,
            "linked_work_order": work_order_id,
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
