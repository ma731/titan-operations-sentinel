from . import sim_clock


def work_order_draft(
    machine_id: str,
    plant_id: str,
    failure_mode: str,
    parts_required: list[dict],
    proposed_window: dict,
    technicians_required: list[str],
    estimated_duration_hours: int,
    actions: list[dict],
) -> dict:
    """
    Generates a structured draft work order for human review and approval.

    Tool catalog:
      Input:  machine_id, plant_id, failure_mode, parts_required, proposed_window,
              technicians_required, estimated_duration_hours, actions (AUTO/APPROVE list)
      Output: draft WO dict — NOT committed until human releases it
      Use when: repair plan is confirmed and ready for manager approval
      Do NOT use: before parts plan is finalized and RUL assessment is complete
      Fallback: if any required field missing, return partial WO with INCOMPLETE flag
      Risk tier: APPROVE (human must release before execution)
    """
    wo_id = f"WO-{machine_id}-{sim_clock.now().strftime('%Y%m%d%H%M')}"
    incomplete = not all([machine_id, plant_id, parts_required, proposed_window])

    return {
        "work_order_id": wo_id,
        "status": "DRAFT_PENDING_APPROVAL",
        "incomplete_flag": incomplete,
        "machine_id": machine_id,
        "plant_id": plant_id,
        "failure_mode": failure_mode,
        "parts_required": parts_required,
        "proposed_window": proposed_window,
        "technicians_required": technicians_required,
        "estimated_duration_hours": estimated_duration_hours,
        "actions": actions,
        "generated_at_utc": sim_clock.now().isoformat(),
        "time_basis": sim_clock.basis(),
        "approval_required_from": "plant_manager",
    }
