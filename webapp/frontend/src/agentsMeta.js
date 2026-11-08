// Shared agent metadata used by the engine (App), the dashboard and Titan.
// what / tools / limit are the plain-English explanation shown on each agent's page.
// Tool lists mirror tools/lc.py (RELIABILITY_TOOLS etc.).
export const AGENTS = [
  {
    id: 'reliability', name: 'Reliability', chal: 'Predictive maintenance', tint: 'blue', desc: 'Predicts the failure and remaining life',
    what: 'Works out what is failing and how long the machine has left. It reads the sensors, compares them with past incidents and estimates the remaining life.',
    tools: [
      ['alert_triage', 'picks the critical alert out of the flood'],
      ['sensor_query', 'reads recent vibration and temperature'],
      ['rul_predictor', 'estimates the hours left, labelled with where the number comes from'],
      ['recall_similar_cases', 'finds past incidents with the same signature'],
      ['asset_profile', 'machine details and the parts a repair needs'],
      ['maintenance_schedule', 'finds the next maintenance window'],
      ['search_technical_docs', 'looks up manuals and limits, with citations'],
    ],
    limit: 'Fails toward caution: if the data is missing or broken, it rates the risk high or hands over to a person instead of guessing.',
  },
  {
    id: 'supply_chain', name: 'Supply Chain', chal: 'Sourcing and supplier risk', tint: 'green', desc: 'Sources parts by cost and value',
    what: 'Gets the parts in time at a sensible cost. It checks stock, compares suppliers and values each option against doing nothing.',
    tools: [
      ['parts_inventory', 'stock on site and at the central warehouse'],
      ['supplier_catalog', 'suppliers, lead times and prices'],
      ['expedite_cost', 'downtime each option avoids, and what it costs'],
      ['tier2_supplier_risk', "checks the supplier's own suppliers"],
      ['supplier_impact', 'knowledge graph: everything a risky supplier reaches, in euros per day'],
      ['trace_dependency', 'knowledge graph: how an upstream risk reaches this machine'],
      ['work_order_draft', 'drafts the maintenance work order'],
      ['notify', 'prepares the message for the plant manager'],
    ],
    limit: 'Cannot spend on its own above €500. Anything more goes to the plant manager.',
  },
  {
    id: 'production', name: 'Production', chal: 'Rerouting and shift scheduling', tint: 'purple', desc: 'Reroutes jobs around the downtime',
    what: 'Keeps the line running while the machine is down. It moves jobs to other machines after checking operator shifts and robot cells.',
    tools: [
      ['robot_cell_status', 'which machines and robot cells are free'],
      ['shift_conflict_check', 'checks operator shifts for clashes'],
      ['job_reroute', 'moves jobs to another machine'],
    ],
    limit: "Will not assign work that clashes with an operator's shift or a robot cell in use.",
  },
  {
    id: 'quality', name: 'Quality', chal: 'Defects and traceability', tint: 'orange', desc: 'Guards traceability and defect risk',
    what: 'Makes sure the fix does not create defects. It links the vibration to recent defects and checks that the backup machine is within spec.',
    tools: [
      ['telemetry_correlate', 'links sensor readings to defects'],
      ['quality_history', 'defect record of a machine'],
    ],
    limit: 'Only reads records. It can flag a reroute as unsafe, but it cannot change production itself.',
  },
  {
    id: 'compliance_safety', name: 'Compliance', chal: 'Safety gate (OSHA / OEM limits)', tint: 'red', desc: 'Gates every action vs OSHA / OEM limits',
    what: 'Checks that every proposed action is safe and allowed, then assembles the audit trail for the run.',
    tools: [
      ['safety_gate', 'checks each action against safety and machine-maker limits'],
      ['audit_assemble', 'builds the audit trail of the run'],
      ['search_technical_docs', 'looks up the rule behind each check, with citations'],
    ],
    limit: 'Has the last word on safety: it can stop the whole plan, and anything touching a safety system goes to a safety officer.',
  },
]
export const AGENT_MAP = Object.fromEntries(AGENTS.map((a) => [a.id, a]))
