// The Leipzig Plant 7 fleet shown in the console. Only CNC-07-LEI has an alert; the
// recorded runs (and the demo data behind live runs) are about that machine.
export const FLEET = [
  { id: 'CNC-07-LEI', name: 'CNC Machining Center #7', status: 'critical' },
  { id: 'CNC-08-LEI', name: 'CNC Machining Center #8', status: 'idle', vib: '2.1', temp: '+1', util: '0% (idle)', note: 'Available as reroute target for CNC-07.' },
  { id: 'CNC-05-LEI', name: 'CNC Machining Center #5', status: 'ok', vib: '3.4', temp: '+3', util: '82%', note: 'Operating within all OEM limits.' },
  { id: 'CNC-03-LEI', name: 'CNC Machining Center #3', status: 'ok', vib: '2.9', temp: '+2', util: '76%', note: 'Bearing replaced Sept 2025 (INC-0312).' },
  { id: 'ROB-02-LEI', name: 'Robot Cell #2', status: 'ok', vib: '1.8', temp: '+1', util: '68%', note: 'Pick-and-place cell, nominal.' },
]

// Plain answer to "check CNC-08": what the triage gate would see, said honestly.
export function machineReport(id, alertMachine = 'CNC-07-LEI', threshold = 6.0) {
  const m = FLEET.find((x) => x.id === id)
  if (!m) return `${id} is not part of this demo plant. Titan Leipzig Plant 7 has ${FLEET.map((x) => x.id).join(', ')}.`
  if (m.id === alertMachine) return null
  const state = m.status === 'idle' ? 'idle' : `running at ${m.util} utilisation`
  return `${m.id} (${m.name}) is ${state}, with vibration ${m.vib} mm/s against a ${Number(threshold).toFixed(1)} mm/s limit and bearing temperature ${m.temp} °C. That is within limits, so the triage gate raises no alert and the agents are not woken. ${m.note} Only CNC-07-LEI has an active alert in this demo, so runs are about that machine.`
}
