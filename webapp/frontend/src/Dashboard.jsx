import { useState, useEffect, useRef } from 'react'
import { AGENTS, AGENT_MAP } from './agentsMeta.js'
import AgentGraph from './AgentGraph.jsx'
import ProviderBar from './ProviderBar.jsx'
import Logo from './Logo.jsx'
import AnimatedNumber from './AnimatedNumber.jsx'
import CommandPalette from './CommandPalette.jsx'
import Guide from './Guide.jsx'
import { REPLIES } from './titanCommands.js'
import { TEAM, GUEST } from './team.js'

const TINT = { blue: '#3b82f6', green: '#16b364', purple: '#8b5cf6', orange: '#f59e0b', red: '#ef4444' }
// Sidebar in story order: watch the run, read what the agents said, check the proof.
const NAV_GROUPS = [
  { label: null, items: [{ id: 'dashboard', ic: '▦', label: 'Overview' }] },
  { label: 'The run', items: [
    { id: 'chat', ic: '⇆', label: 'Agent conversation' },
    { id: 'plan', ic: '◈', label: 'Action plan' },
    { id: 'cost', ic: '€', label: 'Cost and value' },
    { id: 'scenarios', ic: '◇', label: 'Scenarios' },
  ] },
  { label: 'Each agent', items: [
    { id: 'reliability', ic: '◔', label: 'Reliability' },
    { id: 'supply_chain', ic: '⇄', label: 'Supply chain' },
    { id: 'production', ic: '⚙', label: 'Production' },
    { id: 'quality', ic: '✓', label: 'Quality' },
    { id: 'compliance_safety', ic: '⚠', label: 'Compliance' },
  ] },
  { label: 'Proof', items: [
    { id: 'audit', ic: '≣', label: 'Audit log' },
    { id: 'report', ic: '▤', label: 'Run history' },
    { id: 'learning', ic: '✦', label: 'Learning' },
  ] },
]
const ALL_NAV = NAV_GROUPS.flatMap((g) => g.items)
const FLEET = [
  { id: 'CNC-07-LEI', name: 'CNC Machining Center #7', status: 'critical' },
  { id: 'CNC-08-LEI', name: 'CNC Machining Center #8', status: 'idle', vib: '2.1', temp: '+1', util: '0% (idle)', note: 'Available as reroute target for CNC-07.' },
  { id: 'CNC-05-LEI', name: 'CNC Machining Center #5', status: 'ok', vib: '3.4', temp: '+3', util: '82%', note: 'Operating within all OEM limits.' },
  { id: 'CNC-03-LEI', name: 'CNC Machining Center #3', status: 'ok', vib: '2.9', temp: '+2', util: '76%', note: 'Bearing replaced Sept 2025 (INC-0312).' },
  { id: 'ROB-02-LEI', name: 'Robot Cell #2', status: 'ok', vib: '1.8', temp: '+1', util: '68%', note: 'Pick-and-place cell, nominal.' },
]
const SCENARIOS = [
  { id: 'happy', label: 'Cascade', desc: 'Full team → costed plan → human approval' },
  { id: 'edge', label: 'Edge', desc: 'Cross-plant adaptation when local supply is disrupted' },
  { id: 'escalation', label: 'Escalation', desc: 'Telemetry dropout → insufficient data → human review' },
]

export default function Dashboard(props) {
  const {
    scenario, setScenario, mode, setMode, running, completed, timeline, agentStatus, runStatus, risk,
    plan, exposure, doneCount, onRun, onStop, onBack, alert: ALERT, user, onSignOut, onSwitchUser, onCommand,
    history = [], onClearHistory, presenting, onPresent, approvalPending = false, onDecide = () => {},
  } = props
  const [nav, setNav] = useState('dashboard')
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [assetOpen, setAssetOpen] = useState(false)
  const [selectedMachine, setSelectedMachine] = useState(FLEET[0])
  const sel = selectedMachine || FLEET[0]
  const selCritical = sel.id === ALERT.machine_id
  const [coach, setCoach] = useState(() => { try { return !localStorage.getItem('tos.coach') } catch { return false } })
  const closeCoach = () => { setCoach(false); try { localStorage.setItem('tos.coach', '1') } catch { /* ignore */ } }
  const me = user || { name: 'Guest', initials: 'G', color: '#f97316' }
  const firstName = me.name.split(' ')[0]

  const blocks = timeline.filter((t) => t.kind === 'block')
  const focusAgent = AGENT_MAP[nav] ? nav : null
  const shownBlocks = focusAgent ? blocks.filter((b) => b.agent === focusAgent) : blocks

  return (
    <div className="dash" style={{ '--accent': me.color }}>
      <header className="dash-top">
        <div className="dash-brand"><span className="logo-svg" onClick={onBack} title="Back to home" style={{ cursor: 'pointer', display: 'flex' }}><Logo size={28} accent={me.color} /></span> Operations Sentinel</div>
        <button className="dash-home" onClick={onBack} title="Back to home page"><span className="ic">←</span> Home</button>
        <span className="sp" />
        <ProviderBar mode={mode} setMode={setMode} />
        <button className="present-btn" onClick={onPresent} disabled={running} title="Hands-free guided demo">▶ Present</button>
        <button className="help-btn" onClick={() => setCoach(true)} title="What am I looking at?">?</button>
        <button className="cmdk-trigger" onClick={() => setPaletteOpen(true)} title="Command palette">
          <span className="ic">⌘</span>K
        </button>
        <UserMenu me={me} firstName={firstName} onSwitchUser={onSwitchUser} onSignOut={onSignOut} />
      </header>

      {presenting && (
        <div className="present-bar">
          <span className="present-dot" />
          <span className="present-tag">Presenting</span>
          <span className="present-status">{runStatus}</span>
        </div>
      )}

      <div className="dash-body">
        {/* ---------------- sidebar ---------------- */}
        <aside className="dash-side">
          {NAV_GROUPS.map((g, gi) => (
            <div key={gi}>
              {g.label && <div className="nav-label">{g.label}</div>}
              {g.items.map((n) => (
                <button key={n.id} className={`nav-item ${nav === n.id ? 'on' : ''}`} onClick={() => setNav(n.id)}>
                  <span className="ic">{n.ic}</span>{n.label}
                  {AGENT_MAP[n.id] && agentStatus[n.id] === 'done' && <span style={{ marginLeft: 'auto', color: '#16b364' }}>●</span>}
                  {AGENT_MAP[n.id] && agentStatus[n.id] === 'active' && <span style={{ marginLeft: 'auto', color: '#f59e0b' }}>●</span>}
                </button>
              ))}
            </div>
          ))}

          <div className="side-foot">
            <div className="op-card">
              <span className="av" style={{ background: me.color, display: 'grid', placeItems: 'center', color: '#06140e', fontWeight: 700, fontSize: 11 }}>{me.initials}</span>
              <div>
                <div className="who">{me.name}</div>
                <div className="st"><span className="d" />{running ? 'Run active' : 'Signed in'}</div>
              </div>
            </div>
            <div className="run-ctrls">
              {running
                ? <button className="stop wide" onClick={onStop} title="Stop the run">■ Stop run</button>
                : <button className="go" onClick={() => onRun(scenario)}>▶ Run {SCENARIOS.find((s) => s.id === scenario)?.label}</button>}
            </div>
          </div>
        </aside>

        {/* ---------------- center ---------------- */}
        <main className="dash-main">
          {nav === 'scenarios' ? (
            <ScenariosView scenario={scenario} setScenario={setScenario} onRun={onRun} running={running} />
          ) : nav === 'chat' ? (
            <ChatView timeline={timeline} running={running} onCommand={onCommand} runStatus={runStatus} doneCount={doneCount} mode={mode} />
          ) : nav === 'cost' ? (
            <CostView mode={mode} />
          ) : nav === 'audit' ? (
            <AuditView timeline={timeline} />
          ) : nav === 'plan' ? (
            <PlanView plan={plan} />
          ) : nav === 'learning' ? (
            <LearningView history={history} alert={ALERT} />
          ) : nav === 'report' ? (
            <ReportView history={history} onClearHistory={onClearHistory} alert={ALERT} />
          ) : (
            <>
              <div className="dash-h">{focusAgent ? `${AGENT_MAP[focusAgent].name} · ${AGENT_MAP[focusAgent].chal}` : 'Overview'}</div>
              {!focusAgent && (
                <div className="story-head">
                  <p className="dash-explain">
                    A sensor on <b>CNC-07-LEI</b> just crossed its vibration limit. Press run and watch five AI agents check it, one domain at a time, and agree on <b>one costed plan</b>. Anything over <b>€500</b> stops for a person.
                  </p>
                  {running
                    ? <button className="story-run stop" onClick={onStop}>■ Stop</button>
                    : <button className="story-run" onClick={() => onRun(scenario)}>▶ {completed ? 'Run again' : `Run ${SCENARIOS.find((s) => s.id === scenario)?.label}`}</button>}
                </div>
              )}
              {!focusAgent && (
                <div className="dash-tabs" role="group" aria-label="Scenario">
                  {SCENARIOS.map((s) => (
                    <button key={s.id} className={`dash-tab ${scenario === s.id ? 'on' : ''}`} disabled={running} onClick={() => setScenario(s.id)} title={s.desc}>{s.label}</button>
                  ))}
                </div>
              )}
              {!focusAgent && <StoryStrip timeline={timeline} running={running} doneCount={doneCount} runStatus={runStatus} plan={plan} />}
              {!focusAgent && plan?.roi && (
                <div className={`story-result ${plan.status}`}>
                  <span className="story-result-k">{plan.status === 'complete' ? 'Result' : plan.status === 'halted' ? 'Halted' : 'Handed to a person'}</span>
                  <span className="story-result-v">{plan.roi}</span>
                </div>
              )}

              {!focusAgent && <AgentGraph agentStatus={agentStatus} running={running} risk={risk} />}

              <div className="stat-row">
                <Stat lbl="Active Alert" chip="blue" ic="◉" val={<AnimatedNumber value={1} format={(n) => Math.round(n)} />} sub="ALT-22847 · CNC-07-LEI" />
                <Stat lbl="Failure Risk" chip="red" ic="⚠" val={risk} valClass={`risk-${risk}`} sub="from reliability triage" />
                <Stat lbl="Domains checked" chip="green" ic="✓" val={<AnimatedNumber value={doneCount} format={(n) => `${Math.round(n)}/5`} />} sub="agents that reported" deltaUp />
                <Stat lbl="Downtime Exposure" chip="orange" ic="€" val={<AnimatedNumber value={exposure || 0} format={(n) => `€${Math.round(n).toLocaleString()}`} />} sub="€7,500 / h accruing" />
              </div>

              <div className="panel">
                <div className="panel-h"><span className="t">Agent Activity</span><span className="sub">{runStatus}</span></div>
                {shownBlocks.length === 0
                  ? <div className="empty-note">Press “Run {SCENARIOS.find((s) => s.id === scenario)?.label}” to dispatch the agents.</div>
                  : shownBlocks.map((b, i) => <ActivityRow key={i} b={b} />)}
              </div>

              {plan && (
                <div className="panel">
                  <div className="panel-h"><span className="t">Action Plan</span><span className="sub">{plan.status}</span></div>
                  {(plan.lines || []).map((l, i) => (
                    <div className="pl" key={i}><span className={`tier ${l.tier}`}>{l.tier}</span><span className="tx">{l.txt}</span></div>
                  ))}
                  {plan.text && !plan.lines?.length && <div className="tx" style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{plan.text}</div>}
                  {plan.roi && <div className="pl"><span className="tier AUTO">VALUE</span><span className="tx" style={{ fontWeight: 700 }}>{plan.roi}</span></div>}
                  <TierLegend />
                </div>
              )}
            </>
          )}
        </main>

        {/* ---------------- right info ---------------- */}
        <aside className="dash-info">
          <div className="info-h">Plant Fleet <span className="info-h-note">Titan Leipzig · 1 alert · 4 nominal</span></div>
          <div className="fleet">
            {FLEET.map((m) => (
              <button key={m.id} className={`fleet-row ${m.status} ${m.id === ALERT.machine_id ? 'active' : ''} ${sel.id === m.id ? 'sel' : ''}`}
                onClick={() => { setSelectedMachine(m); setAssetOpen(true) }}
                title={m.id === ALERT.machine_id ? 'Open full asset profile' : 'Inspect this machine'}>
                <span className="fleet-dot" />
                <div className="fleet-bd"><div className="fleet-id">{m.id}</div><div className="fleet-nm">{m.name}</div></div>
                <span className="fleet-st">{m.status === 'critical' ? 'ALERT' : m.status === 'idle' ? 'idle' : 'nominal'}</span>
              </button>
            ))}
          </div>

          <div className="info-h mt">Asset Information</div>
          <div className="asset">
            <span className="ic">{sel.id.startsWith('ROB') ? '🦾' : '⚙'}</span>
            <div><div className="nm">{sel.id}</div><div className="sub">{selCritical ? ALERT.plant_name : sel.name}</div></div>
          </div>
          {selCritical ? (
            <div className="kv">
              <div><div className="k">Sensor</div><div className="v">{ALERT.sensor} {ALERT.value} {ALERT.unit}</div></div>
              <div><div className="k">Threshold</div><div className="v">{ALERT.threshold} {ALERT.unit}</div></div>
              <div><div className="k">Trend</div><div className="v">{ALERT.trend} (from {ALERT.baseline})</div></div>
              <div><div className="k">Window</div><div className="v">{ALERT.trend_window}</div></div>
            </div>
          ) : (
            <div className="kv">
              <div><div className="k">Vibration</div><div className="v">{sel.vib} mm/s</div></div>
              <div><div className="k">Bearing temp</div><div className="v">{sel.temp} °C</div></div>
              <div><div className="k">Status</div><div className="v">{sel.status === 'idle' ? 'Idle' : 'Nominal'}</div></div>
              <div><div className="k">Utilisation</div><div className="v">{sel.util}</div></div>
            </div>
          )}
          <button className="info-btn" onClick={() => setAssetOpen(true)}>View Full Asset Profile</button>

          <div className="info-h mt">Run History</div>
          {timeline.filter((t) => t.kind === 'human' || (t.kind === 'block' && t.status === 'done')).slice(-4).map((t, i) => (
            <div className="hist" key={i}>
              <span className="ic" style={{ background: '#e9f1fe', color: '#3b82f6' }}>{t.kind === 'human' ? '✓' : '◉'}</span>
              <div><div className="t">{t.kind === 'human' ? 'Human decision' : AGENT_MAP[t.agent]?.name || t.agent}</div><div className="s">{t.kind === 'human' ? t.text : 'Assessment reported'}</div></div>
            </div>
          ))}
          {timeline.length === 0 && <div className="s" style={{ color: 'var(--muted)', fontSize: 12 }}>No activity yet.</div>}

          <div className="info-h mt">AI Suggestions</div>
          {plan
            ? <>
                <div className="sugg amber"><span className="si">💡</span><span>{plan.status === 'escalated' ? 'Insufficient data, route to on-call reliability engineer for manual inspection.' : 'Emergency Schaeffler expedite recommended, €3,200, inside the 52h window.'}</span></div>
                <div className="sugg green"><span className="si">✅</span><span>{plan.status === 'complete' ? 'Plan signed off by Compliance. Throttle + reroute can execute automatically.' : 'Keep the alert open and re-run once clean telemetry is available.'}</span></div>
              </>
            : <>
                <div className="sugg amber"><span className="si">💡</span><span>Run a scenario to generate costed, safety-gated recommendations.</span></div>
                <div className="sugg green"><span className="si">✅</span><span>Compliance gates every action; spend over €500 routes to you.</span></div>
              </>}
        </aside>
      </div>

      <CommandPalette
        open={paletteOpen} setOpen={setPaletteOpen}
        navItems={ALL_NAV} setNav={setNav}
        scenarios={SCENARIOS} onRun={onRun}
        me={me} onSwitchUser={onSwitchUser} onSignOut={onSignOut}
      />

      <Guide mode={mode}
        onAction={(a) => {
          if (a.run) { setNav('dashboard'); if (!running) onRun(scenario) }
          else if (a.nav) setNav(a.nav)
        }}
        onCommand={(c) => {
          if (c.cmd === 'run') {
            if (running) return REPLIES.runBusy
            const sc = c.scenario || scenario
            setScenario(sc); setNav('dashboard'); onRun(sc)
            return REPLIES.run(sc)
          }
          if (c.cmd === 'approve' || c.cmd === 'reject') {
            if (!approvalPending) return REPLIES.noApproval
            onDecide(c.cmd)
            return c.cmd === 'approve' ? REPLIES.approved : REPLIES.rejected
          }
          if (c.cmd === 'stop') { if (!running) return REPLIES.notRunning; onStop(); return REPLIES.stopped }
          if (c.cmd === 'present') { if (running) return REPLIES.presentBusy; setNav('dashboard'); onPresent(); return REPLIES.present(scenario) }
          if (c.cmd === 'nav') { setNav(c.nav); return REPLIES.open(c.name) }
          return null
        }} />

      {assetOpen && <AssetModal machine={selectedMachine} alert={ALERT} risk={risk} onClose={() => setAssetOpen(false)} />}
      {coach && <Coachmark onClose={closeCoach} />}
    </div>
  )
}

// First-load "what am I looking at?" intro (shown once per browser; reopen via the ? button).
function Coachmark({ onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  const steps = [
    { ic: '◉', t: 'An alert just fired', d: 'A sensor on CNC-07-LEI crossed its vibration limit. This console is the team of agents that responds.' },
    { ic: '▶', t: 'Press Run', d: 'Six AI agents are dispatched. Watch the graph: the orchestrator routes them and they reason live, one domain at a time.' },
    { ic: '◈', t: 'They converge on a plan', d: 'Findings combine into one costed, safety-gated action plan. Anything over €500, or any safety risk, pauses for a human.' },
    { ic: '€', t: 'It runs free', d: 'Replay mode plays the recorded run with no API key and zero cost. Live mode uses a real model when you add a key.' },
  ]
  return (
    <div className="coach-scrim" onClick={onClose}>
      <div className="coach" onClick={(e) => e.stopPropagation()}>
        <button className="coach-close" onClick={onClose} aria-label="Close">✕</button>
        <div className="coach-eyebrow">Titan Operations Sentinel</div>
        <div className="coach-h">What am I looking at?</div>
        <div className="coach-steps">
          {steps.map((s, i) => (
            <div className="coach-step" key={i}>
              <span className="coach-ic">{s.ic}</span>
              <div><div className="coach-t">{s.t}</div><div className="coach-d">{s.d}</div></div>
            </div>
          ))}
        </div>
        <button className="coach-go" onClick={onClose}>Got it, run the demo</button>
      </div>
    </div>
  )
}

// Legend for the autonomy tiers that appear on every action-plan line.
function TierLegend() {
  return (
    <div className="tier-legend">
      <span><span className="tier AUTO">AUTO</span> agent executes on its own</span>
      <span><span className="tier APPROVE">APPROVE</span> needs a human (spend &gt; €500)</span>
      <span><span className="tier ESCALATE">ESCALATE</span> routed to a safety officer</span>
    </div>
  )
}

// Full machine dossier behind the "View Full Asset Profile" button. Static spec data
// (consistent with the Friday Cascade scenario) merged with the live alert reading.
const ASSET_SPEC = {
  type: 'CNC Machining Center #7', oem: 'DMG MORI · DMU 50', controller: 'Siemens SINUMERIK 840D sl',
  installed: 'Mar 2019', spindle: 'Motorized · 14,000 rpm · HSK-A63', criticality: 'A · line-critical',
  hoursYTD: '3,212 h', utilisation: '87%', lastService: '2026-04-02 (preventive)', nextWindow: 'in 9 days',
}
const ASSET_SENSORS = [
  { k: 'Vibration (RMS)', v: '7.2 mm/s', s: 'over', note: 'threshold 6.0 · baseline 3.1' },
  { k: 'Bearing temp', v: '+14 °C', s: 'over', note: 'rising vs 6h baseline' },
  { k: 'Spindle load', v: '78 %', s: 'ok', note: 'within OEM envelope' },
  { k: 'Coolant flow', v: '12.4 L/min', s: 'ok', note: 'nominal' },
]
const ASSET_PARTS = [
  { id: 'P-4421', name: 'Spindle bearing kit', stock: '0 on-site', note: '3 in Amsterdam (AMS)' },
  { id: 'P-7803', name: 'Hydraulic seal set', stock: '1 on-site (need 2)', note: '4 in Amsterdam (AMS)' },
]
const ASSET_HISTORY = [
  { d: '2026-06-12', t: 'Vibration alert ALT-22847 raised (7.2 mm/s)', tag: 'alert' },
  { d: '2026-04-02', t: 'Preventive service: spindle inspection, coolant flush', tag: 'service' },
  { d: '2025-11-18', t: 'Bearing micro-defect flagged by quality (r=0.61)', tag: 'quality' },
  { d: '2025-07-09', t: 'Controller firmware update SINUMERIK 4.95', tag: 'service' },
]

function NominalAssetModal({ machine: m, plant, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="asset-scrim" onClick={onClose}>
      <div className="asset-modal" onClick={(e) => e.stopPropagation()}>
        <button className="asset-close" onClick={onClose} aria-label="Close">✕</button>
        <div className="asset-head">
          <span className="asset-ic">{m.id.startsWith('ROB') ? '🦾' : '⚙'}</span>
          <div><div className="asset-id">{m.id}</div><div className="asset-sub">{m.name} · {plant}</div></div>
          <span className="asset-risk risk-LOW">{m.status === 'idle' ? 'IDLE' : 'NOMINAL'}</span>
        </div>
        <div className="asset-body">
          <div className="asset-col">
            <div className="asset-sec">Specifications</div>
            <div className="asset-kv">
              <div><span>OEM / Model</span>{m.id.startsWith('ROB') ? 'KUKA · KR 10' : 'DMG MORI · DMU 50'}</div>
              <div><span>Controller</span>{m.id.startsWith('ROB') ? 'KUKA KR C5' : 'Siemens SINUMERIK 840D sl'}</div>
              <div><span>Criticality</span>B · standard</div>
              <div><span>Utilisation</span>{m.util}</div>
            </div>
            <div className="asset-sec">Live sensors</div>
            <div className="asset-sensor"><span className="asset-dot ok" /><div className="asset-sensor-bd"><div className="asset-sensor-k">Vibration (RMS)</div><div className="asset-sensor-n">within OEM limit (6.0)</div></div><span className="asset-sensor-v ok">{m.vib} mm/s</span></div>
            <div className="asset-sensor"><span className="asset-dot ok" /><div className="asset-sensor-bd"><div className="asset-sensor-k">Bearing temp</div><div className="asset-sensor-n">nominal vs baseline</div></div><span className="asset-sensor-v ok">{m.temp} °C</span></div>
            <div className="asset-sensor"><span className="asset-dot ok" /><div className="asset-sensor-bd"><div className="asset-sensor-k">Spindle load</div><div className="asset-sensor-n">within envelope</div></div><span className="asset-sensor-v ok">nominal</span></div>
          </div>
          <div className="asset-col">
            <div className="asset-sec">Health</div>
            <div className="asset-rul" style={{ background: 'var(--green-bg)', borderColor: 'color-mix(in srgb, var(--green) 25%, transparent)' }}>
              <div className="asset-rul-big" style={{ color: '#0c6b3f' }}>No alert</div>
              <div className="asset-rul-sub">{m.note} No failure predicted; not currently routed by the orchestrator.</div>
            </div>
            <div className="asset-sec">Status</div>
            <div className="asset-part">
              <span className="asset-part-id">OK</span>
              <div className="asset-part-bd"><div className="asset-part-n">Operating within all limits</div><div className="asset-part-note">{m.status === 'idle' ? 'Idle and available' : 'In production'}</div></div>
              <span className="asset-part-stock">{m.util}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function AssetModal({ machine, alert: ALERT, risk, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  if (machine && machine.id !== ALERT.machine_id) return <NominalAssetModal machine={machine} plant={ALERT.plant_name} onClose={onClose} />
  return (
    <div className="asset-scrim" onClick={onClose}>
      <div className="asset-modal" onClick={(e) => e.stopPropagation()}>
        <button className="asset-close" onClick={onClose} aria-label="Close">✕</button>
        <div className="asset-head">
          <span className="asset-ic">⚙</span>
          <div>
            <div className="asset-id">{ALERT.machine_id}</div>
            <div className="asset-sub">{ASSET_SPEC.type} · {ALERT.plant_name}</div>
          </div>
          <span className={`asset-risk risk-${risk}`}>{risk === 'PENDING' ? 'MONITOR' : risk} RISK</span>
        </div>

        <div className="asset-body">
          <div className="asset-col">
            <div className="asset-sec">Specifications</div>
            <div className="asset-kv">
              <div><span>OEM / Model</span>{ASSET_SPEC.oem}</div>
              <div><span>Controller</span>{ASSET_SPEC.controller}</div>
              <div><span>Spindle</span>{ASSET_SPEC.spindle}</div>
              <div><span>Installed</span>{ASSET_SPEC.installed}</div>
              <div><span>Criticality</span>{ASSET_SPEC.criticality}</div>
              <div><span>Hours (YTD)</span>{ASSET_SPEC.hoursYTD} · {ASSET_SPEC.utilisation}</div>
              <div><span>Last service</span>{ASSET_SPEC.lastService}</div>
              <div><span>Next window</span>{ASSET_SPEC.nextWindow}</div>
            </div>

            <div className="asset-sec">Live sensors</div>
            {ASSET_SENSORS.map((s, i) => (
              <div className="asset-sensor" key={i}>
                <span className={`asset-dot ${s.s}`} />
                <div className="asset-sensor-bd"><div className="asset-sensor-k">{s.k}</div><div className="asset-sensor-n">{s.note}</div></div>
                <span className={`asset-sensor-v ${s.s}`}>{s.v}</span>
              </div>
            ))}
          </div>

          <div className="asset-col">
            <div className="asset-sec">Predicted failure</div>
            <div className="asset-rul">
              <div className="asset-rul-big">52-76 h</div>
              <div className="asset-rul-sub">Spindle-bearing failure · 95% confidence · €180,000/day exposure if it stops the line</div>
            </div>

            <div className="asset-sec">Required parts</div>
            {ASSET_PARTS.map((p, i) => (
              <div className="asset-part" key={i}>
                <span className="asset-part-id">{p.id}</span>
                <div className="asset-part-bd"><div className="asset-part-n">{p.name}</div><div className="asset-part-note">{p.note}</div></div>
                <span className="asset-part-stock">{p.stock}</span>
              </div>
            ))}

            <div className="asset-sec">Service history</div>
            {ASSET_HISTORY.map((h, i) => (
              <div className="asset-hist" key={i}>
                <span className={`asset-hist-tag ${h.tag}`}>{h.tag}</span>
                <div className="asset-hist-bd"><div className="asset-hist-t">{h.t}</div><div className="asset-hist-d">{h.d}</div></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function UserMenu({ me, firstName, onSwitchUser, onSignOut }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onKey) }
  }, [open])

  const pick = (m) => { onSwitchUser?.(m); setOpen(false) }

  return (
    <div className="user-menu" ref={ref}>
      <button className={`user-chip ${open ? 'open' : ''}`} onClick={() => setOpen((o) => !o)} title="Switch presenter">
        <span className="uc-ava" style={{ background: me.color }}>{me.initials}</span>
        <span className="uc-name">{firstName}</span>
        <span className="uc-caret">▾</span>
      </button>
      {open && (
        <div className="user-pop" role="menu">
          <div className="up-head">Switch presenter</div>
          {TEAM.map((m) => {
            const active = m.name === me.name
            return (
              <button key={m.name} className={`up-item ${active ? 'on' : ''}`} onClick={() => pick(m)} role="menuitem">
                <span className="up-ava" style={{ background: m.color }}>{m.initials}</span>
                <span className="up-name">{m.name}</span>
                {active && <span className="up-check" style={{ color: m.color }}>●</span>}
              </button>
            )
          })}
          <button className={`up-item ${me.name === 'Guest' ? 'on' : ''}`} onClick={() => pick(GUEST)} role="menuitem">
            <span className="up-ava" style={{ background: GUEST.color }}>G</span>
            <span className="up-name">Guest</span>
          </button>
          <div className="up-sep" />
          <button className="up-item up-out" onClick={() => { setOpen(false); onSignOut?.() }} role="menuitem">
            <span className="up-out-ic">⎋</span>
            <span className="up-name">Sign out</span>
          </button>
        </div>
      )}
    </div>
  )
}

function Stat({ lbl, chip, ic, val, valClass = '', sub, deltaUp }) {
  return (
    <div className="stat-card">
      <div className="top"><span className="lbl">{lbl}</span><span className={`chip ${chip}`}>{ic}</span></div>
      <div className={`val ${valClass}`}>{val}</div>
      <div className={`delta ${deltaUp ? 'up' : ''}`}>{sub}</div>
    </div>
  )
}

function ActivityRow({ b }) {
  const a = AGENT_MAP[b.agent] || { name: b.agent, tint: 'blue' }
  const live = b.status === 'active'
  return (
    <div className={`act ${live ? 'live' : ''}`}>
      <span className="ava" style={{ background: TINT[a.tint] || '#3b82f6' }}>{a.name[0]}</span>
      <div className="bd">
        <div className="nm">{a.name}{b.how && <span className={`route-tag ${b.how === 'LLM-picked' ? 'llm' : ''}`}>{b.how === 'LLM-picked' ? 'LLM-routed' : 'auto-routed'}</span>}{b.status === 'done' && <span className="act-dot" style={{ background: '#16b364' }} />}</div>
        <div className="msg">{b.report || 'Analyzing…'}</div>
        {b.tools?.length > 0 && <div className="tools">{b.tools.map((t, i) => <span className="tchip" key={i}>{t.tool}</span>)}</div>}
      </div>
    </div>
  )
}

function ScenariosView({ scenario, setScenario, onRun, running }) {
  return (
    <>
      <div className="dash-h">Demo Scenarios</div>
      <p style={{ color: 'var(--ink-2)', fontSize: 14, marginBottom: 18, maxWidth: '60ch' }}>Three paths, each exercising the system differently. Pick one and run it live.</p>
      {SCENARIOS.map((s) => (
        <div className="panel" key={s.id} style={{ borderColor: scenario === s.id ? 'var(--accent)' : undefined }}>
          <div className="panel-h">
            <span className="t">{s.label}</span>
            <button className="dash-tab on" disabled={running} onClick={() => { setScenario(s.id); onRun(s.id) }} style={{ background: 'var(--accent)' }}>▶ Run</button>
          </div>
          <div style={{ fontSize: 13.5, color: 'var(--ink-2)', lineHeight: 1.5 }}>{s.desc}</div>
        </div>
      ))}
    </>
  )
}

function AuditView({ timeline }) {
  return (
    <>
      <div className="dash-h">Audit Log</div>
      <div className="panel">
        {timeline.length === 0 ? <div className="empty-note">No events yet, run a scenario.</div>
          : timeline.map((t, i) => (
            <div className="pl" key={i}>
              <span className="tier MONITOR">{t.kind}</span>
              <span className="tx">{t.kind === 'block' ? `${t.agent}: ${(t.report || '…').slice(0, 120)}` : t.text}</span>
            </div>
          ))}
      </div>
    </>
  )
}

function PlanView({ plan }) {
  return (
    <>
      <div className="dash-h">Action Plan</div>
      {!plan ? <div className="panel"><div className="empty-note">No plan yet, run a scenario to completion.</div></div>
        : <div className="panel">
            <div className="panel-h"><span className="t">Final Plan</span><span className="sub">{plan.status}</span></div>
            {(plan.lines || []).map((l, i) => <div className="pl" key={i}><span className={`tier ${l.tier}`}>{l.tier}</span><span className="tx">{l.txt}</span></div>)}
            {plan.text && !plan.lines?.length && <div className="tx" style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{plan.text}</div>}
            {plan.roi && <div className="pl"><span className="tier AUTO">VALUE</span><span className="tx" style={{ fontWeight: 700 }}>{plan.roi}</span></div>}
            <TierLegend />
          </div>}
    </>
  )
}

// ---- Learning subsystem (Section 4: Perception -> Reasoning -> Action -> LEARNING) ----
// Mirrors the backend case library; in live runs recall_similar_cases reads it and
// graph.synthesize appends each closed run via append_case().
const CASE_LIBRARY = [
  { id: 'INC-0288', date: '2025-06-11', machine: 'CNC-07-LEI', signature: 'spindle-bearing, vibration 7.0 mm/s, +13C', predRul: '50-74 h', actual: 'failed at 58 h', decision: 'approved expedite', outcome: 'avoided ~€520k downtime', match: 93 },
  { id: 'INC-0312', date: '2025-09-23', machine: 'CNC-03-LEI', signature: 'spindle-bearing, vibration 6.9 mm/s', predRul: '48-70 h', actual: 'failed at 61 h', decision: 'approved expedite', outcome: 'avoided ~€410k downtime', match: 88 },
  { id: 'INC-0344', date: '2025-11-18', machine: 'CNC-07-LEI', signature: 'bearing micro-defect, vibration 6.2 mm/s', predRul: '90-140 h', actual: 'failed at 121 h', decision: 'scheduled window', outcome: 'fixed in planned downtime', match: 71 },
  { id: 'INC-0241', date: '2025-02-04', machine: 'CNC-05-LEI', signature: 'coolant temperature spike', predRul: '120-160 h', actual: 'no failure (false alarm)', decision: 'monitored, no spend', outcome: 'correctly de-prioritized', match: 34 },
]
const REFLECTIONS = [
  { date: '2026-06-12', note: 'Under-weighted Tier-2 supplier risk last run; supply_chain now surfaces it in the procurement ranking by default.' },
  { date: '2026-05-30', note: 'A reroute skipped the traceability check; quality now always validates the target machine before accepting load.' },
  { date: '2026-05-09', note: 'Plan was verbose at the gate; synthesis tightened to cost / deadline / approver / ROI only.' },
]

function LearningView({ history = [], alert: ALERT }) {
  // everything below is DERIVED from the visible case library + this session's runs,
  // so the panel never shows totals that disagree with the data it displays.
  const decided = history.flatMap((r) => r.decisions || [])
  const approvals = CASE_LIBRARY.filter((c) => /approved/i.test(c.decision)).length + decided.filter((d) => /approve/i.test(d)).length
  const rejections = decided.filter((d) => /reject/i.test(d)).length
  const totalRuns = CASE_LIBRARY.length + history.length
  // outcome validation: predicted RUL window vs actual, over the seeded library
  const closedCases = CASE_LIBRARY.filter((c) => /failed at/.test(c.actual))
  const hits = closedCases.filter((c) => {
    const m = c.actual.match(/(\d+)\s*h/); const [lo, hi] = c.predRul.split('-').map((x) => parseInt(x))
    return m && +m[1] >= lo && +m[1] <= hi
  }).length
  const closedN = closedCases.length
  const acc = closedN ? Math.round((hits / closedN) * 100) : 0
  const falseAlarms = CASE_LIBRARY.filter((c) => /false alarm/i.test(c.actual)).length
  const avgLead = closedN ? Math.round(closedCases.reduce((s, c) => s + (+c.actual.match(/(\d+)\s*h/)[1]), 0) / closedN) : 0

  return (
    <>
      <div className="dash-h">Learning <span className="learn-badge">experience + feedback</span></div>
      <p style={{ color: 'var(--ink-2)', fontSize: 14, marginBottom: 18, maxWidth: '66ch' }}>
        The system improves over time without retraining the model. Two mechanisms run today: it
        recalls precedent (case memory) and adapts to the operator's decisions (human feedback). Two
        more are built into the loop's design: self-critique (reflection) and prediction validation
        (outcome), marked "design" below.
      </p>

      {/* 1. Case memory / precedent recall */}
      <div className="panel">
        <div className="panel-h"><span className="t">Precedent recalled</span><span className="sub">for {ALERT.machine_id} · {ALERT.sensor}</span></div>
        {CASE_LIBRARY.map((c) => (
          <div className="learn-case" key={c.id}>
            <div className="learn-match"><span className="learn-match-n">{c.match}%</span><span className="learn-match-l">match</span></div>
            <div className="learn-case-bd">
              <div className="learn-case-t">{c.id} · {c.machine} <span className="learn-case-d">{c.date}</span></div>
              <div className="learn-case-s">{c.signature}</div>
              <div className="learn-case-o"><b>Predicted</b> {c.predRul} · <b>Actual</b> {c.actual} · {c.decision} → {c.outcome}</div>
            </div>
          </div>
        ))}
        <div className="learn-foot">The closest case (INC-0288) is fed into the reliability agent's context so its assessment is grounded in precedent, not just the current reading.</div>
      </div>

      {/* 2. Human-feedback / preference learning */}
      <div className="panel">
        <div className="panel-h"><span className="t">Learned from decisions</span><span className="sub">{totalRuns} run{totalRuns === 1 ? '' : 's'} on record</span></div>
        <div className="stat-row" style={{ marginBottom: 14 }}>
          <Stat lbl="Gate approvals" chip="green" ic="✓" val={`${approvals}`} sub="expedites cleared on record" deltaUp />
          <Stat lbl="Gate rejections" chip="red" ic="✕" val={`${rejections}`} sub="paths declined" />
          <Stat lbl="Runs logged" chip="blue" ic="≣" val={`${totalRuns}`} sub="library + this session" />
          <Stat lbl="Recommendation" chip="purple" ic="◈" val={approvals >= rejections ? 'EXPEDITE' : 'HOLD'} sub="biased by the record" />
        </div>
        <div className="pl"><span className="tier APPROVE">PATTERN</span><span className="tx">Emergency expedite has been approved {approvals} of {approvals + rejections} times on record. This informs the recommended path shown above (still gated).</span></div>
        <div className="learn-foot">Each closed run is appended to the case library (append_case); the approve/reject tally above biases the recommended path toward how this plant manager actually decides.</div>
      </div>

      {/* 3. Reflection (Reflexion) */}
      <div className="panel">
        <div className="panel-h"><span className="t">Self-critique (reflection) <span className="learn-concept">design</span></span><span className="sub">self_eval prompt exists today</span></div>
        {REFLECTIONS.map((r, i) => (
          <div className="learn-reflect" key={i}>
            <span className="learn-reflect-ic">✎</span>
            <div><div className="learn-reflect-n">{r.note}</div><div className="learn-reflect-d">{r.date}</div></div>
          </div>
        ))}
        <div className="learn-foot">Today the self_eval prompt scores each plan. Persisting these critiques and replaying them into the next run is the production design (shown here as worked examples).</div>
      </div>

      {/* 4. Outcome validation */}
      <div className="panel">
        <div className="panel-h"><span className="t">Prediction accuracy <span className="learn-concept">design</span></span><span className="sub">over the seeded case library</span></div>
        <div className="stat-row" style={{ marginBottom: 12 }}>
          <Stat lbl="RUL accuracy" chip="green" ic="◉" val={`${acc}%`} sub={`${hits}/${closedN} closed cases inside window`} deltaUp />
          <Stat lbl="False alarms" chip="orange" ic="⚠" val={`${falseAlarms}`} sub="caught and de-prioritized" />
          <Stat lbl="Cases closed" chip="blue" ic="✓" val={`${closedN}`} sub="with a confirmed outcome" />
          <Stat lbl="Avg lead time" chip="purple" ic="◔" val={`${avgLead} h`} sub="warning before failure" />
        </div>
        <div className="learn-foot">Each closed case validates the predicted RUL window (accuracy above is over the seeded library). Automatically down-weighting a signature that misses is the production design.</div>
      </div>
    </>
  )
}

function buildReportMd(r, ALERT) {
  const label = SCENARIOS.find((s) => s.id === r.scenario)?.label || r.scenario
  let md = `# Titan Operations Sentinel Run Report\n\n`
  md += `**Scenario:** ${label}  \n**When:** ${new Date(r.ts).toLocaleString()}  \n**Presenter:** ${r.by}  \n`
  md += `**Mode:** ${r.mode}  \n**Failure risk:** ${r.risk}  \n**Outcome:** ${r.status}  \n**Challenges covered:** ${r.doneCount}/5\n\n`
  if (r.command) md += `**Operator prompt:** “${r.command}”\n\n`
  md += `## Alert\n${ALERT.machine_id} · ${ALERT.plant_name}, ${ALERT.sensor} ${ALERT.value}${ALERT.unit} (threshold ${ALERT.threshold}, ${ALERT.trend})\n\n`
  md += `## Agent reports\n`
  r.reports.forEach((a) => {
    md += `### ${AGENT_MAP[a.agent]?.name || a.agent}\n${a.report || '(no report)'}\n`
    if (a.tools?.length) md += `\n_Tools used: ${a.tools.join(', ')}_\n`
    md += `\n`
  })
  if (r.followups?.length) md += `## Agent-to-agent follow-ups\n` + r.followups.map((f) => `- ${f}`).join('\n') + `\n\n`
  if (r.decisions?.length) md += `## Human decisions\n` + r.decisions.map((d) => `- ${d}`).join('\n') + `\n\n`
  md += `## Final action plan, ${r.plan.status}\n`
  if (r.plan.lines?.length) md += r.plan.lines.map((l) => `- **[${l.tier}]** ${l.txt}`).join('\n')
  else if (r.plan.text) md += r.plan.text
  if (r.plan.roi) md += `\n\n**Return on action:** ${r.plan.roi}`
  md += `\n\n---\n_Generated by Titan Operations Sentinel_\n`
  return md
}

function downloadReport(r, ALERT) {
  const label = (SCENARIOS.find((s) => s.id === r.scenario)?.label || r.scenario).toLowerCase()
  const blob = new Blob([buildReportMd(r, ALERT)], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `tos-report-${label}-${r.id}.md`
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url)
}

function ReportView({ history, onClearHistory, alert: ALERT }) {
  const [sel, setSel] = useState(null)
  const run = history.find((r) => r.id === sel) || history[0] || null
  return (
    <>
      <div className="dash-h">Run History</div>
      <p style={{ color: 'var(--ink-2)', fontSize: 14, marginBottom: 18, maxWidth: '62ch' }}>
        Every completed run is saved here, review what each agent concluded and export a shareable report.
      </p>
      {history.length === 0 ? (
        <div className="panel"><div className="empty-note">No runs yet. Run a scenario (or type a crisis in Agent Chat) and it'll be saved here automatically.</div></div>
      ) : (
        <div className="rep-wrap">
          <div className="rep-list">
            <div className="rep-list-h">
              <span>{history.length} run{history.length > 1 ? 's' : ''}</span>
              <button className="rep-clear" onClick={onClearHistory} title="Clear all">Clear</button>
            </div>
            {history.map((r) => {
              const label = SCENARIOS.find((s) => s.id === r.scenario)?.label || r.scenario
              return (
                <button key={r.id} className={`rep-item ${run?.id === r.id ? 'on' : ''}`} onClick={() => setSel(r.id)}>
                  <span className={`rep-dot ${r.status}`} />
                  <div className="rep-item-bd">
                    <div className="rep-item-t">{label} <span className="rep-mode">{r.mode}</span></div>
                    <div className="rep-item-s">{new Date(r.ts).toLocaleString()} · {r.by}</div>
                  </div>
                  <span className={`rep-badge ${r.status}`}>{r.status}</span>
                </button>
              )
            })}
          </div>

          {run && (
            <div className="rep-detail">
              <div className="panel">
                <div className="panel-h">
                  <span className="t">{SCENARIOS.find((s) => s.id === run.scenario)?.label || run.scenario} · report</span>
                  <button className="info-btn" style={{ width: 'auto', padding: '7px 13px', marginTop: 0 }} onClick={() => downloadReport(run, ALERT)}>↓ Export .md</button>
                </div>
                <div className="rep-meta">
                  <span><b>When</b>{new Date(run.ts).toLocaleString()}</span>
                  <span><b>Presenter</b>{run.by}</span>
                  <span><b>Risk</b>{run.risk}</span>
                  <span><b>Coverage</b>{run.doneCount}/5</span>
                </div>
                {run.command && <div className="rep-cmd">Operator: “{run.command}”</div>}
              </div>

              <div className="panel">
                <div className="panel-h"><span className="t">Agent reports</span></div>
                {run.reports.map((a, i) => (
                  <div className={`act ${a.status === 'error' ? '' : ''}`} key={i} style={{ alignItems: 'flex-start' }}>
                    <span className="ava" style={{ background: TINT[AGENT_MAP[a.agent]?.tint] || '#3b82f6' }}>{(AGENT_MAP[a.agent]?.name || a.agent)[0]}</span>
                    <div className="bd">
                      <div className="nm">{AGENT_MAP[a.agent]?.name || a.agent}</div>
                      <div className="msg">{a.report || '-'}</div>
                      {a.tools?.length > 0 && <div className="tools">{a.tools.map((t, j) => <span className="tchip" key={j}>{t}</span>)}</div>}
                    </div>
                  </div>
                ))}
                {run.followups.map((f, i) => <div className="ch-followup" key={`f${i}`} style={{ margin: '8px 0' }}><span className="ch-fu-tag">agent → agent</span> {f}</div>)}
              </div>

              {run.decisions.length > 0 && (
                <div className="panel">
                  <div className="panel-h"><span className="t">Human decisions</span></div>
                  {run.decisions.map((d, i) => <div className="pl" key={i}><span className="tier APPROVE">HUMAN</span><span className="tx">{d}</span></div>)}
                </div>
              )}

              <div className="panel">
                <div className="panel-h"><span className="t">Final action plan</span><span className="sub">{run.plan.status}</span></div>
                {(run.plan.lines || []).map((l, i) => <div className="pl" key={i}><span className={`tier ${l.tier}`}>{l.tier}</span><span className="tx">{l.txt}</span></div>)}
                {run.plan.text && !run.plan.lines?.length && <div className="tx" style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{run.plan.text}</div>}
                {run.plan.roi && <div className="pl"><span className="tier AUTO">VALUE</span><span className="tx" style={{ fontWeight: 700 }}>{run.plan.roi}</span></div>}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}

const CRISES = [
  'CNC-07 vibration spiking, handle it',
  'Sensor feed on CNC-07 just dropped out',
  'Cross-plant supply disruption today',
]

function ChatView({ timeline, running, onCommand, runStatus, doneCount = 0, mode }) {
  const [val, setVal] = useState('')
  const endRef = useRef(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [timeline, running])
  const send = (text) => {
    const t = (text ?? val).trim()
    if (!t || running) return
    onCommand?.(t)
    setVal('')
  }
  const started = timeline.length > 0 || running
  const activeAgent = [...timeline].reverse().find((t) => t.kind === 'block' && t.status === 'active')
  return (
    <>
      <div className="dash-h">Agent Conversation</div>
      <p style={{ color: 'var(--ink-2)', fontSize: 14, marginBottom: 18, maxWidth: '62ch' }}>
        Describe a situation in plain language, the orchestrator routes it to the right agents, who reason and converse through a shared transcript. Or pick an example below.
      </p>

      {/* live status bar, makes it obvious what's happening during a run */}
      {started && (
        <div className={`ch-status ${running ? 'live' : 'done'}`}>
          <span className="ch-status-dot" />
          <span className="ch-status-txt">{running ? (runStatus || 'Working…') : 'Conversation complete'}</span>
          <span className="ch-status-prog">
            {[0, 1, 2, 3, 4].map((n) => <i key={n} className={n < doneCount ? 'on' : ''} />)}
            <b>{doneCount}/5</b>
          </span>
        </div>
      )}

      <div className="panel chat">
        {timeline.length === 0 ? (
          <div className="empty-note">{running ? 'Dispatching the agents…' : 'Type a crisis below, or try an example, to dispatch the agents.'}</div>
        ) : timeline.map((t, i) => {
          if (t.kind === 'system') return <div className="ch-sys" key={i}><span className="ch-sys-ic">◈</span>{t.text}</div>
          if (t.kind === 'note') return <div className="ch-followup" key={i}><span className="ch-fu-tag">agent → agent</span> {t.text}</div>
          if (t.kind === 'human') return (
            <div className="ch-row me" key={i}>
              <div className="ch-bubble me"><div className="ch-nm">Plant Manager</div>{t.text}</div>
              <span className="ch-av" style={{ background: '#0f1115' }}>★</span>
            </div>
          )
          const a = AGENT_MAP[t.agent] || { name: t.agent, tint: 'blue' }
          const thinking = t.status === 'active'
          return (
            <div className="ch-row" key={i}>
              <span className={`ch-av ${thinking ? 'pulse' : ''}`} style={{ background: TINT[a.tint] || '#3b82f6' }}>{a.name[0]}</span>
              <div className={`ch-bubble ${thinking ? 'thinking' : ''} ${t.status === 'error' ? 'err' : ''}`}>
                <div className="ch-nm">{a.name}{thinking && <span className="ch-tag-live">reasoning</span>}</div>
                {t.tools?.length > 0 && (
                  <div className="ch-tools">{t.tools.map((x, j) => <span className="tchip" key={j}><span className="tchip-ic">⚙</span>{x.tool}</span>)}</div>
                )}
                {t.report
                  ? <div className="ch-text">{t.report}</div>
                  : thinking && <div className="ch-think">{t.tools?.length ? 'reasoning over tool results' : 'choosing tools'} <span className="ch-dots"><i /><i /><i /></span></div>}
              </div>
            </div>
          )
        })}
        <div ref={endRef} />
      </div>

      {timeline.length === 0 && (
        <div className="ch-chips">
          {CRISES.map((c) => (
            <button key={c} className="ch-chip" disabled={running} onClick={() => send(c)}>{c}</button>
          ))}
        </div>
      )}
      <div className="ch-composer">
        <span className="ch-prompt">⌘</span>
        <input
          value={val}
          onChange={(e) => setVal(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') send() }}
          placeholder={running ? 'Agents are working…' : 'Describe the situation…  e.g. CNC-07 vibration spiking, handle it'}
          disabled={running}
        />
        <button className="ch-send" onClick={() => send()} disabled={running || !val.trim()} aria-label="Dispatch agents">↑</button>
      </div>
    </>
  )
}

const COST_ROWS = [
  { who: 'Orchestrator routing', tok: '1.5k', tint: 'orange' },
  { who: 'Reliability', tok: '3.2k', tint: 'blue' },
  { who: 'Supply Chain', tok: '3.8k', tint: 'green' },
  { who: 'Production', tok: '2.9k', tint: 'purple' },
  { who: 'Quality', tok: '2.4k', tint: 'orange' },
  { who: 'Compliance', tok: '3.1k', tint: 'red' },
  { who: 'Final synthesis', tok: '1.2k', tint: 'blue' },
]
function CostView({ mode = 'replay' }) {
  const live = mode === 'live'
  return (
    <>
      <div className="dash-h">Cost & Feasibility</div>
      <p style={{ color: 'var(--ink-2)', fontSize: 14, marginBottom: 18, maxWidth: '62ch' }}>
        {live ? (
          <>A full 6-agent run is roughly <b>~18k tokens</b> — about <b>~€0.005</b> on a paid model, or <b>free quota</b> on a free tier (it still uses your daily allowance, so it isn't truly €0).</>
        ) : (
          <>A full 6-agent run is roughly <b>~18k tokens</b> (after a ~62% transcript trim). This is a <b>recorded replay</b>, so it makes <b>no API calls and costs €0</b>.</>
        )}
      </p>
      <div className="stat-row" style={{ marginBottom: 16 }}>
        <Stat lbl="Tokens / run" chip="blue" ic="◉" val="~18k" sub="after token-trim (−62%)" />
        {live ? (
          <Stat lbl="Cost this run" chip="purple" ic="€" val="~€0.005" sub="paid model · free tier uses quota" />
        ) : (
          <Stat lbl="Replay cost" chip="green" ic="€" val="€0" sub="recorded · no API calls" deltaUp />
        )}
        <Stat lbl="Pay-as-you-go" chip="purple" ic="€" val="~€0.005" sub="Flash-Lite, per full run" />
        <Stat lbl="Rehearse 50×" chip="orange" ic="↻" val="< €1" sub="a week of practice runs" />
      </div>
      <div className="panel">
        <div className="panel-h"><span className="t">Tokens by agent</span><span className="sub">representative full run</span></div>
        {COST_ROWS.map((r, i) => (
          <div className="act" key={i} style={{ alignItems: 'center' }}>
            <span className="ava" style={{ background: TINT[r.tint], width: 28, height: 28, fontSize: 11 }}>{r.who[0]}</span>
            <div className="bd"><div className="nm" style={{ fontSize: 12.5 }}>{r.who}</div></div>
            <span className="tchip">{r.tok} tok</span>
          </div>
        ))}
      </div>
      <div className="panel">
        <div className="panel-h"><span className="t">Why it's feasible</span></div>
        <div className="pl"><span className="tier AUTO">FREE</span><span className="tx">Runs end-to-end on Gemini / OpenRouter free tiers, no paid keys (assignment §14).</span></div>
        <div className="pl"><span className="tier MONITOR">TRIM</span><span className="tx">Transcript caps cut tokens ~62%, so more runs fit the daily quota.</span></div>
        <div className="pl"><span className="tier APPROVE">SWAP</span><span className="tx">One-line provider switch when a free tier rate-limits.</span></div>
        <div className="pl"><span className="tier AUTO">REPLAY</span><span className="tx">Demo day uses the recorded replay, zero API calls, can't fail.</span></div>
      </div>
    </>
  )
}

// Four-step progress strip: the story of a run, readable at a glance.
function StoryStrip({ timeline, running, doneCount, runStatus, plan }) {
  const started = running || timeline.length > 0
  const humanDone = timeline.some((t) => t.kind === 'human' && t.text.startsWith('Human decision'))
  const waiting = runStatus === 'Awaiting human approval'
  const gateText = humanDone ? 'A person approved the spend'
    : waiting ? 'Waiting for a person: over €500'
    : plan ? (plan.status === 'complete' ? 'Not needed: under €500' : 'Not reached')
    : 'Anything over €500 stops here'
  const steps = [
    { t: 'Alert', s: started ? '1 of 22k alerts woke the agents' : 'A sensor crosses its limit', st: started ? 'done' : 'todo' },
    { t: 'Agents', s: `${doneCount} of 5 domains checked`, st: plan || doneCount === 5 ? 'done' : started && !waiting ? 'now' : started ? 'done' : 'todo' },
    { t: 'Human gate', s: gateText, st: humanDone || plan ? 'done' : waiting ? 'now' : 'todo' },
    { t: 'Plan', s: plan ? (plan.status === 'complete' ? 'Costed plan ready' : plan.status === 'halted' ? 'Stopped by safety' : 'Handed to a person') : 'One costed, safety-checked plan', st: plan ? 'done' : 'todo' },
  ]
  return (
    <ol className="story-strip" aria-label="Run progress">
      {steps.map((x, i) => (
        <li key={x.t} className={`story-step ${x.st}`}>
          <span className="story-n">{x.st === 'done' ? '✓' : i + 1}</span>
          <span className="story-t">{x.t}</span>
          <span className="story-s">{x.s}</span>
        </li>
      ))}
    </ol>
  )
}
