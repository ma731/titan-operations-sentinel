// Shared agent metadata used by both the engine (App) and the dashboard view.
export const AGENTS = [
  { id: 'reliability', name: 'Reliability', chal: 'Predictive maintenance', tint: 'blue', desc: 'Predicts the failure and remaining life' },
  { id: 'supply_chain', name: 'Supply Chain', chal: 'Sourcing and supplier risk', tint: 'green', desc: 'Sources parts by cost and ROI' },
  { id: 'production', name: 'Production', chal: 'Rerouting and shift scheduling', tint: 'purple', desc: 'Reroutes jobs around the downtime' },
  { id: 'quality', name: 'Quality', chal: 'Defects and traceability', tint: 'orange', desc: 'Guards traceability and defect risk' },
  { id: 'compliance_safety', name: 'Compliance', chal: 'Safety gate (OSHA / OEM limits)', tint: 'red', desc: 'Gates every action vs OSHA / OEM limits' },
]
export const AGENT_MAP = Object.fromEntries(AGENTS.map((a) => [a.id, a]))
