# Agent Trace — Sequence Diagram (the Friday Cascade)

Appendix artifact (brief §16 "Elite": *sequence diagram / agent trace*). A full happy-path run,
node by node, exactly as the engine executes it. Renders on GitHub / any mermaid viewer.

```mermaid
sequenceDiagram
    autonumber
    actor Sensor as Sensor / Alert
    participant Sup as Orchestrator (Supervisor)
    participant Rel as Reliability
    participant Sup2 as Supply Chain
    participant Prod as Production
    participant Qual as Quality
    participant Comp as Compliance & Safety
    actor Human as Plant Manager

    Sensor->>Sup: ALT-22847 · CNC-07-LEI vibration 7.2 mm/s (▲ from 3.1)
    Note over Sup: perceive → triage 22k alerts → critical asset

    Sup->>Rel: route (HIGH-risk path begins)
    Rel->>Rel: alert_triage · sensor_query · rul_predictor · asset_profile
    Rel-->>Sup: RISK=HIGH · RUL 52–76h · parts P-4421, P-7803

    Sup->>Sup2: route
    Sup2->>Sup2: parts_inventory · supplier_catalog · expedite_cost · tier2_supplier_risk
    Sup2-->>Sup: Schaeffler €3,200 / 18h · 116h downtime avoided · >€500 → needs approval

    Sup->>Prod: route
    Prod->>Prod: robot_cell_status · shift_conflict_check · job_reroute
    Prod->>Qual: FOLLOWUP — are CNC-08 reroute targets quality-safe?
    Prod-->>Sup: rerouted J4421–J4425 → CNC-08 (avoided op_Keller conflict)

    Sup->>Qual: route (honours follow-up)
    Qual->>Qual: telemetry_correlate · quality_history
    Qual-->>Sup: vibration↔defect r=0.82 · CNC-08 within spec ✓

    Sup->>Comp: route (always gates before FINISH)
    Comp->>Comp: safety_gate (×4 actions) · audit_assemble
    Comp-->>Sup: VERDICT = SIGN-OFF (can HALT if violated)

    Sup->>Human: ⏸ interrupt() — approve €3,200 + Saturday window?
    Human-->>Sup: APPROVED
    Sup-->>Sensor: Action plan — [AUTO] throttle + reroute · [APPROVE] expedite + window · 116h avoided
```

**Reading it for the rubric:** steps 1–2 are *perception*; the `route` arrows are the supervisor's
*model-driven planning*; each agent's tool list is *autonomous tool selection*; the `FOLLOWUP`
is *agent-to-agent messaging*; Compliance is the *safety gate*; the `interrupt()` is the
*human-in-the-loop*. Every arrow is a real event in `logs/tos_audit.jsonl` (see `audit_log_schema.md`).
```
