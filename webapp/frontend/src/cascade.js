// ===========================================================================
// Baked demo streams, the "Friday Cascade" and its edge/escalation variants.
// Each item is a trace event matching the backend contract (CLAUDE.md §7), plus
// `t` = ms to wait before emitting it, so the console plays like a real run with
// ZERO backend / API key / cost. The live SSE path emits the same event shapes.
// ===========================================================================

export const ALERT = {
  alert_id: 'ALT-22847',
  machine_id: 'CNC-07-LEI',
  plant_name: 'Titan Leipzig · Plant 7',
  sensor: 'vibration',
  value: 7.2,
  unit: 'mm/s RMS',
  threshold: 6.0,
  baseline: 3.1,
  trend: 'rising',
  trend_window: '6h',
  production_impact_per_day_eur: 180000,
}

const happy = [
  { t: 350, type: 'perception', message: 'Alert ALT-22847 received, CNC-07-LEI vibration 7.2 mm/s (threshold 6.0). Orchestrator engaging the specialist team.' },

  { t: 650, type: 'route', to: 'reliability', allowed: ['reliability'], how: 'forced' },
  { t: 600, type: 'tool_call', agent: 'reliability', tool: 'alert_triage', input: { plant: 'LEI', stream: '22k alerts' }, result: { critical: 'CNC-07-LEI' } },
  { t: 550, type: 'tool_call', agent: 'reliability', tool: 'sensor_query', input: { machine: 'CNC-07-LEI', window: '72h' }, result: { vibration: 7.2, bearing_temp: '+14°C' } },
  { t: 550, type: 'tool_call', agent: 'reliability', tool: 'recall_similar_cases', input: { signature: 'spindle-bearing vibration' }, result: { top: 'INC-0288 (93%)', outcome: 'failed at 58h, expedite approved, succeeded' } },
  { t: 650, type: 'tool_call', agent: 'reliability', tool: 'rul_predictor', input: { match: 'INC-0288 precedent' }, result: { rul: '52-76h', conf: 0.95 } },
  { t: 500, type: 'tool_call', agent: 'reliability', tool: 'asset_profile', input: { machine: 'CNC-07-LEI' }, result: { parts: ['P-4421', 'P-7803'] } },
  { t: 950, type: 'agent_report', agent: 'reliability', risk: 'HIGH', report: 'CNC-07-LEI confirmed as the critical asset from 22k alerts. Vibration rising 3.1 → 7.2 mm/s over 6h with a +14°C bearing-temp climb, signature of spindle-bearing failure. Recalled precedent INC-0288 (93% match): the same signature failed at 58h and the expedite was approved and succeeded. RUL 52-76h (95% conf). Parts required: P-4421 (bearing kit), P-7803 ×2 (seal set). No maintenance window for 9 days → schedule gap CRITICAL.' },

  { t: 700, type: 'route', to: 'supply_chain', allowed: ['supply_chain', 'production', 'quality'], how: 'LLM-picked' },
  { t: 600, type: 'tool_call', agent: 'supply_chain', tool: 'parts_inventory', input: { parts: ['P-4421', 'P-7803'] }, result: { 'P-4421': '0 on-site', 'P-7803': '1/2 on-site' } },
  { t: 600, type: 'tool_call', agent: 'supply_chain', tool: 'supplier_catalog', input: { part: 'P-4421' }, result: { Schaeffler: '18h €3200' } },
  { t: 550, type: 'tool_call', agent: 'supply_chain', tool: 'expedite_cost', input: { downtime_h: 7500, window_h: '52-76', baseline_h: 192 }, result: { avoided: '116h · €870k', roi: '271.9:1', break_even: '0.32%' } },
  { t: 550, type: 'tool_call', agent: 'supply_chain', tool: 'tier2_supplier_risk', input: { supplier: 'Schaeffler' }, result: { tier2: 'LOW' } },
  { t: 900, type: 'agent_report', agent: 'supply_chain', report: 'Parts gap confirmed: P-4421 zero on-site, P-7803 short one unit. Best option: Schaeffler expedite, 18h, €3,200 (LOW Tier-2 risk), 34h of buffer inside the 52h window. Against the 192h standard lead time, acting now avoids at least 116h of unplanned downtime (€870k at production value, an upper bound). The €420 Amsterdam transfer avoids the same, so the €2,780 premium buys buffer: worth it if the transfer has more than a 0.32% chance of arriving late. Spend exceeds the €500 autonomy ceiling → flag for human approval.' },

  { t: 650, type: 'route', to: 'production', allowed: ['production', 'quality'], how: 'LLM-picked' },
  { t: 600, type: 'tool_call', agent: 'production', tool: 'robot_cell_status', input: { plant: 'LEI' }, result: { 'CNC-08': 'idle' } },
  { t: 550, type: 'tool_call', agent: 'production', tool: 'shift_conflict_check', input: { target: 'CNC-08' }, result: { conflict: 'op_Keller' } },
  { t: 600, type: 'tool_call', agent: 'production', tool: 'job_reroute', input: { from: 'CNC-07', to: 'CNC-08' }, result: { rerouted: 5 } },
  { t: 900, type: 'agent_report', agent: 'production', report: 'Rerouted jobs J4421-J4425 off CNC-07. First-choice CNC-05 hit an operator conflict (op_Keller, overlapping shift), so adapted to CNC-08, idle, no human-robot conflict. Throughput preserved during the maintenance window.' },

  { t: 600, type: 'decision', agent: 'production', message: 'Production → Quality: are CNC-05/CNC-08 reroute targets quality-safe for the extra load before I commit the reroute?' },
  { t: 650, type: 'route', to: 'quality', allowed: ['quality'], how: 'forced' },
  { t: 600, type: 'tool_call', agent: 'quality', tool: 'telemetry_correlate', input: { machine: 'CNC-07-LEI' }, result: { corr: 'vibration↔defect 0.82' } },
  { t: 550, type: 'tool_call', agent: 'quality', tool: 'quality_history', input: { target: 'CNC-08-LEI' }, result: { ppm: 'within spec' } },
  { t: 850, type: 'agent_report', agent: 'quality', report: 'Vibration strongly correlates with recent micro-defects on CNC-07 (r=0.82), reinforces the failure call. CNC-08 quality history is within spec and safe to absorb the extra load. No traceability concerns on the reroute.' },

  { t: 650, type: 'route', to: 'compliance_safety', allowed: ['compliance_safety'], how: 'forced' },
  { t: 600, type: 'tool_call', agent: 'compliance_safety', tool: 'safety_gate', input: { actions: 4 }, result: { verdict: 'SIGN-OFF' } },
  { t: 550, type: 'tool_call', agent: 'compliance_safety', tool: 'audit_assemble', input: { run: 'ALT-22847' }, result: { events: 'logged' } },
  { t: 900, type: 'agent_report', agent: 'compliance_safety', report: 'Gated all four proposed actions against OSHA / OEM limits: spindle throttle within safe band ✓, reroute compliant ✓, Saturday emergency window permitted with sign-off ✓, procurement within policy ✓. VERDICT: SIGN-OFF. Full audit trail assembled for run ALT-22847.' },

  { t: 800, type: 'approval_request', ceiling_eur: 500, amount_eur: 3200, question: 'Authorize €3,200 emergency Schaeffler expedite + Saturday maintenance window?' },
  // player pauses here until the human decides; human_decision + plan are appended on click.
]

const HUMAN_APPROVED = [
  { t: 250, type: 'human_decision', decision: 'APPROVED', by: 'Plant Manager' },
  { t: 700, type: 'plan', status: 'complete', roi: '€870k avoided · 271.9:1', lines: [
    { tier: 'AUTO', txt: 'Throttle CNC-07-LEI spindle to 60% within OEM safe limits (buys runway to the window).' },
    { tier: 'AUTO', txt: 'Reroute jobs J4421-J4425 to CNC-08-LEI; notify shift lead.' },
    { tier: 'APPROVE', txt: '✓ Authorized, Schaeffler P-4421 expedite, 18h, €3,200.' },
    { tier: 'APPROVE', txt: '✓ Authorized, Saturday 06:00 emergency bearing replacement window.' },
    { tier: 'MONITOR', txt: 'Watch vibration + bearing temp hourly until parts land; re-trigger if RUL shortens.' },
  ] },
]

const HUMAN_REJECTED = [
  { t: 250, type: 'human_decision', decision: 'REJECTED', by: 'Plant Manager' },
  { t: 700, type: 'plan', status: 'escalated', lines: [
    { tier: 'ESCALATE', txt: 'Procurement rejected, escalating to operations director with the costed trade-off (€3,200 expedite vs €180k/day exposure).' },
    { tier: 'AUTO', txt: 'Throttle CNC-07-LEI to 60% to extend runway while the decision is reviewed.' },
    { tier: 'MONITOR', txt: 'Hold reroute ready; re-present once a sourcing decision is made.' },
  ] },
]

// --- Escalation variant: telemetry dropout → insufficient data → human review ---
const escalation = [
  { t: 350, type: 'perception', message: 'Alert ALT-22847 received, CNC-07-LEI. Orchestrator engaging Reliability first.' },
  { t: 650, type: 'route', to: 'reliability', allowed: ['reliability'], how: 'forced' },
  { t: 600, type: 'tool_call', agent: 'reliability', tool: 'alert_triage', input: { plant: 'LEI' }, result: { critical: 'CNC-07-LEI' } },
  { t: 600, type: 'tool_call', agent: 'reliability', tool: 'sensor_query', input: { window: 'dropout' }, result: { sensor_status: 'INTERRUPTED' } },
  { t: 900, type: 'agent_report', agent: 'reliability', risk: 'ESCALATE', report: 'Telemetry feed interrupted mid-window, cannot establish a confident RUL or failure mode. Per guardrails, refusing to fabricate an assessment from unreliable data.' },
  { t: 700, type: 'decision', agent: 'orchestrator', message: 'Low-confidence perception → halting before any action plan. Routing to human review.' },
  { t: 700, type: 'plan', status: 'escalated', lines: [
    { tier: 'ESCALATE', txt: 'INSUFFICIENT DATA: route to on-call reliability engineer for manual inspection of CNC-07-LEI.' },
    { tier: 'MONITOR', txt: 'Keep the alert open; auto-re-run once a clean sensor window is available.' },
  ] },
]

// --- Edge variant: primary supply DISRUPTED → cross-plant transfer UNDER the €500
//     ceiling → fully autonomous, NO human gate (shows the autonomy-tier logic) ---
const edge = [
  { t: 350, type: 'perception', message: 'Alert ALT-22847 received, CNC-07-LEI. Primary supplier is flagged DISRUPTED today; orchestrator engaging the team.' },

  { t: 650, type: 'route', to: 'reliability', allowed: ['reliability'], how: 'forced' },
  { t: 600, type: 'tool_call', agent: 'reliability', tool: 'alert_triage', input: { plant: 'LEI' }, result: { critical: 'CNC-07-LEI' } },
  { t: 600, type: 'tool_call', agent: 'reliability', tool: 'rul_predictor', input: {}, result: { rul: '52-76h' } },
  { t: 900, type: 'agent_report', agent: 'reliability', risk: 'HIGH', report: 'CNC-07-LEI confirmed, spindle-bearing failure, RUL 52-76h. Parts P-4421, P-7803 required. Same failure call as the base case.' },

  { t: 700, type: 'route', to: 'supply_chain', allowed: ['supply_chain', 'production', 'quality'], how: 'LLM-picked' },
  { t: 600, type: 'tool_call', agent: 'supply_chain', tool: 'supplier_catalog', input: { scenario: 'edge' }, result: { primary: 'DISRUPTED' } },
  { t: 600, type: 'tool_call', agent: 'supply_chain', tool: 'parts_inventory', input: { sister_plants: ['AMS', 'MUC'] }, result: { MUC: 'P-4421 in stock' } },
  { t: 550, type: 'tool_call', agent: 'supply_chain', tool: 'expedite_cost', input: { option: 'cross-plant MUC' }, result: { cost: 420, eta: '36h', avoided: '116h · €870k', roi: '2071.4:1' } },
  { t: 950, type: 'agent_report', agent: 'supply_chain', report: 'Primary supplier DISRUPTED today, no expedite fits the 52h window. Adapted: cross-plant transfer from sister plant MUC, P-4421 in stock, 36h, €420. That is UNDER the €500 autonomy ceiling, so no human approval is required. Against the 192h standard lead time it avoids at least 116h of unplanned downtime (€870k at production value, an upper bound).' },

  { t: 650, type: 'route', to: 'production', allowed: ['production', 'quality'], how: 'LLM-picked' },
  { t: 600, type: 'tool_call', agent: 'production', tool: 'job_reroute', input: { from: 'CNC-07', to: 'CNC-08' }, result: { rerouted: 5 } },
  { t: 900, type: 'agent_report', agent: 'production', report: 'Rerouted jobs J4421-J4425 to CNC-08-LEI (idle, no shift/robot conflict) to cover the 36h transfer window.' },

  { t: 650, type: 'route', to: 'quality', allowed: ['quality'], how: 'forced' },
  { t: 600, type: 'tool_call', agent: 'quality', tool: 'quality_history', input: { target: 'CNC-08-LEI' }, result: { ppm: 'within spec' } },
  { t: 850, type: 'agent_report', agent: 'quality', report: 'CNC-08 is quality-safe for the extra load; the MUC part is the same OEM spec, no traceability concern.' },

  { t: 650, type: 'route', to: 'compliance_safety', allowed: ['compliance_safety'], how: 'forced' },
  { t: 600, type: 'tool_call', agent: 'compliance_safety', tool: 'safety_gate', input: { actions: 3 }, result: { verdict: 'SIGN-OFF' } },
  { t: 900, type: 'agent_report', agent: 'compliance_safety', report: 'All actions within OSHA/OEM limits and under the spend ceiling. VERDICT: SIGN-OFF. No human gate needed, the plan can execute autonomously.' },

  { t: 800, type: 'plan', status: 'complete', roi: '€870k avoided · €420 spent', lines: [
    { tier: 'AUTO', txt: 'Throttle CNC-07-LEI spindle to 60% within OEM limits.' },
    { tier: 'AUTO', txt: 'Cross-plant transfer P-4421 from MUC, €420, 36h (under the €500 ceiling, no approval needed).' },
    { tier: 'AUTO', txt: 'Reroute jobs J4421-J4425 to CNC-08-LEI for the transfer window.' },
    { tier: 'MONITOR', txt: 'Track the inbound transfer + vibration hourly; escalate if RUL shortens.' },
  ] },
]

export const SCENARIOS = { happy, edge, escalation }
export const RESOLUTIONS = { approve: HUMAN_APPROVED, reject: HUMAN_REJECTED }
