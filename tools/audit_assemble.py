import json
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "logs" / "tos_audit.jsonl"


def audit_assemble(run_id: str) -> dict:
    """
    Reconstructs the full decision timeline for a run from the audit log — automated
    incident reconstruction / audit assembly (challenge 5).

    Tool catalog:
      Input:  run_id (str)
      Output: chronological events for the run + counts by type + OSHA-log skeleton
      Use when: producing the compliance/audit trail for the actions taken this run
      Do NOT use: to make decisions — this is a read-only reconstruction
      Fallback: {"error": "audit_log_unavailable"} or empty timeline
      Risk tier: READ (autonomous)
    """
    try:                                  # the writer's path, so a sandboxed log is read too
        import audit_log
        log_file = Path(audit_log.LOG_FILE)
    except Exception:  # noqa: BLE001
        log_file = LOG_FILE
    if not log_file.exists():
        return {"error": "audit_log_unavailable", "run_id": run_id}

    events = []
    with open(log_file, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("run_id") == run_id:
                events.append({"ts": e["ts"], "type": e["type"],
                               "agent": e["agent"], "detail": e.get("detail", {})})

    by_type: dict[str, int] = {}
    for e in events:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    return {
        "run_id": run_id,
        "event_count": len(events),
        "events_by_type": by_type,
        "timeline": events,
        "osha_log_fields": ["timestamp", "machine_id", "action", "approver",
                            "lockout_tagout_ref", "operators_present"],
    }
