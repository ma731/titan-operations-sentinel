import { useState, useRef, useEffect, useCallback } from 'react'
import { flushSync } from 'react-dom'
import { ALERT, SCENARIOS, RESOLUTIONS } from './cascade.js'
import Showcase from './Showcase.jsx'
import Dashboard from './Dashboard.jsx'
import SignIn from './SignIn.jsx'
import { AGENTS, AGENT_MAP } from './agentsMeta.js'

const RATE_PER_S = 180000 / 86400
const FRESH_STATUS = () => Object.fromEntries(AGENTS.map((a) => [a.id, 'idle']))

const TICKER = [
  'TITAN LEIPZIG · PLANT 7', 'CNC-07-LEI', 'VIBRATION 7.2 mm/s ▲', 'RUL 52-76 h',
  'DOWNTIME €180,000 / day', '€870k DOWNTIME AVOIDED', '5 TMC CHALLENGES',
  'HUMAN GATE > €500', 'RUNS ON FREE-TIER GEMINI',
]

const CHIPS = [
  'CNC-07 vibration spiking, handle it',
  'Sensor feed on CNC-07 dropped out',
  'Cross-plant supply disruption today',
]
const scenarioFor = (text) => {
  const t = (text || '').toLowerCase()
  if (/drop|interrupt|sensor.*(down|lost|out)|no data|offline/.test(t)) return 'escalation'
  if (/cross-plant|supply|disrupt|edge/.test(t)) return 'edge'
  return 'happy'
}

export default function App() {
  const [view, setView] = useState('signin')   // 'signin' | 'showcase' | 'console'
  const [user, setUser] = useState(null)       // signed-in presenter (name, initials, color)
  const [history, setHistory] = useState(() => {
    try { return JSON.parse(localStorage.getItem('tos.history') || '[]') } catch { return [] }
  })
  const runMetaRef = useRef(null)
  const savedRunRef = useRef(0)

  // morph between surfaces instead of a hard cut, when the browser supports it
  const goView = useCallback((next) => {
    if (document.startViewTransition) document.startViewTransition(() => flushSync(() => setView(next)))
    else setView(next)
  }, [])
  const signOut = () => { flushSync(() => setUser(null)); goView('signin') }
  const [scenario, setScenario] = useState('happy')
  const [mode, setMode] = useState('replay')
  const [running, setRunning] = useState(false)
  const [completed, setCompleted] = useState(false)
  const [presenting, setPresenting] = useState(false)

  const [timeline, setTimeline] = useState([])
  const [agentStatus, setAgentStatus] = useState(FRESH_STATUS)
  const [runStatus, setRunStatus] = useState('Standing by')
  const [risk, setRisk] = useState('PENDING')
  const [approval, setApproval] = useState(null)
  const [plan, setPlan] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const [clock, setClock] = useState('')

  const queueRef = useRef([])
  const timerRef = useRef(null)
  const esRef = useRef(null)
  const idRef = useRef(0)
  const streamEndRef = useRef(null)
  const nextId = () => ++idRef.current

  useEffect(() => {
    const id = setInterval(() => setClock(new Date().toLocaleTimeString('en-GB')), 1000)
    setClock(new Date().toLocaleTimeString('en-GB'))
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (!running) return
    const id = setInterval(() => setElapsed((e) => e + 0.2), 200)
    return () => clearInterval(id)
  }, [running])

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [timeline, plan, approval])

  const pushItem = useCallback((item) => setTimeline((p) => [...p, { id: nextId(), ...item }]), [])

  const updateActiveBlock = (prev, agent, fn) => {
    let idx = -1
    for (let i = prev.length - 1; i >= 0; i--) {
      if (prev[i].kind === 'block' && prev[i].agent === agent && prev[i].status === 'active') { idx = i; break }
    }
    if (idx === -1) return prev
    const copy = prev.slice()
    copy[idx] = fn(copy[idx])
    return copy
  }

  const applyEvent = useCallback((ev) => {
    switch (ev.type) {
      case 'perception':
        pushItem({ kind: 'system', text: ev.message }); setRunStatus('Perceiving alert'); break
      case 'route':
        setAgentStatus((s) => ({ ...s, [ev.to]: 'active' }))
        setRunStatus(`Routing → ${AGENT_MAP[ev.to]?.name || ev.to}${ev.how ? ` · ${ev.how}` : ''}`)
        pushItem({ kind: 'block', agent: ev.to, tools: [], report: null, status: 'active', how: ev.how }); break
      case 'tool_call':
        setTimeline((prev) => updateActiveBlock(prev, ev.agent, (b) => ({ ...b, tools: [...b.tools, ev] }))); break
      case 'agent_report':
        setTimeline((prev) => updateActiveBlock(prev, ev.agent, (b) => ({ ...b, report: ev.report, status: 'done' })))
        setAgentStatus((s) => ({ ...s, [ev.agent]: 'done' }))
        if (ev.risk) setRisk(ev.risk)
        setRunStatus(`${AGENT_MAP[ev.agent]?.name || ev.agent} reported`); break
      case 'agent_error':
        setTimeline((prev) => updateActiveBlock(prev, ev.agent, (b) => ({ ...b, report: ev.error, status: 'error' })))
        setAgentStatus((s) => ({ ...s, [ev.agent]: 'error' })); break
      case 'decision':
      case 'escalation':
        pushItem({ kind: 'note', text: ev.message }); break
      case 'approval_request':
        setApproval(ev); setRunStatus('Awaiting human approval'); break
      case 'human_decision':
        pushItem({ kind: 'human', text: `Human decision, ${ev.decision}${ev.by ? ' · ' + ev.by : ''}` }); setApproval(null); break
      case 'plan':
        setPlan({ status: ev.status || 'complete', lines: ev.lines || [], roi: ev.roi, text: ev.text })
        if (ev.status === 'escalated') setRisk((r) => (r === 'PENDING' ? 'ESCALATE' : r))
        setRunStatus(ev.status === 'complete' ? 'Plan complete' : ev.status === 'halted' ? 'Plan halted' : 'Escalated to human')
        setRunning(false); setCompleted(true); break
      default: break
    }
  }, [pushItem])

  const reset = useCallback(() => {
    clearTimeout(timerRef.current); esRef.current?.close()
    queueRef.current = []; idRef.current = 0
    setTimeline([]); setAgentStatus(FRESH_STATUS()); setRisk('PENDING')
    setApproval(null); setPlan(null); setElapsed(0); setCompleted(false)
  }, [])

  // hard kill: halt replay timers AND the live SSE, re-enable the UI, keep the
  // partial transcript visible so you can see where it stopped.
  const stopRun = useCallback(() => {
    clearTimeout(timerRef.current)
    esRef.current?.close()
    queueRef.current = []
    setRunning(false)
    setPresenting(false)
    setApproval(null)
    setAgentStatus((s) => Object.fromEntries(Object.entries(s).map(([k, v]) => [k, v === 'active' ? 'idle' : v])))
    setRunStatus('Stopped')
  }, [])

  const pump = useCallback(() => {
    if (!queueRef.current.length) return
    const ev = queueRef.current.shift()
    timerRef.current = setTimeout(() => {
      applyEvent(ev)
      if (ev.type === 'approval_request') return
      pump()
    }, ev.t ?? 400)
  }, [applyEvent])

  const runLive = useCallback((scen) => {
    const es = new EventSource(`/api/run?scenario=${scen}`)
    esRef.current = es
    es.onmessage = (e) => {
      try { const ev = JSON.parse(e.data); applyEvent(ev); if (ev.type === 'plan') es.close() } catch { /* keep-alive */ }
    }
    es.onerror = () => { es.close(); setRunStatus('Live backend unavailable, use Replay'); setRunning(false) }
  }, [applyEvent])

  const run = (scen = scenario, command = null) => {
    reset(); setRunning(true)
    runMetaRef.current = { id: Date.now(), scenario: scen, mode, command }
    if (command) pushItem({ kind: 'human', text: `Operator, ${command}` })
    if (mode === 'live') runLive(scen)
    else { queueRef.current = SCENARIOS[scen].map((e) => ({ ...e })); pump() }
  }

  const submitCommand = (text) => {
    const scen = scenarioFor(text)
    setScenario(scen)
    run(scen, text)
  }

  const resolve = (choice) => {
    if (mode === 'live') {
      setApproval(null)
      fetch('/api/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision: choice }) }).catch(() => {})
      return
    }
    queueRef.current = RESOLUTIONS[choice].map((e) => ({ ...e })); setApproval(null); pump()
  }

  // ---- presenter (hands-free) mode ----
  const present = (scen = scenario) => { setPresenting(true); run(scen) }
  useEffect(() => {                         // auto-approve the human gate while presenting
    if (!presenting || !approval) return
    const id = setTimeout(() => resolve('approve'), 3800)
    return () => clearTimeout(id)
  }, [presenting, approval])               // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (completed) setPresenting(false) }, [completed])

  useEffect(() => () => { clearTimeout(timerRef.current); esRef.current?.close() }, [])

  const clearHistory = useCallback(() => {
    setHistory([]); try { localStorage.removeItem('tos.history') } catch { /* ignore */ }
  }, [])

  const doneCount = AGENTS.filter((a) => agentStatus[a.id] === 'done').length
  const exposure = Math.round(elapsed * RATE_PER_S)
  const neutralized = completed && plan?.status === 'complete'
  const showStream = timeline.length > 0 || running

  // snapshot each finished run into the Run History (persisted to localStorage).
  // declared after doneCount/exposure so they're initialized before the dep array reads them.
  useEffect(() => {
    if (!completed || !plan) return
    const meta = runMetaRef.current
    if (!meta || savedRunRef.current === meta.id) return
    savedRunRef.current = meta.id
    const entry = {
      id: meta.id,
      scenario: meta.scenario,
      mode: meta.mode,
      command: meta.command || null,
      ts: new Date().toISOString(),
      by: user?.name || 'Guest',
      risk, status: plan.status, doneCount, exposure,
      plan,
      reports: timeline.filter((t) => t.kind === 'block').map((t) => ({
        agent: t.agent, report: t.report, status: t.status, tools: (t.tools || []).map((x) => x.tool),
      })),
      followups: timeline.filter((t) => t.kind === 'note').map((t) => t.text),
      decisions: timeline.filter((t) => t.kind === 'human').map((t) => t.text),
    }
    setHistory((h) => {
      const next = [entry, ...h].slice(0, 25)
      try { localStorage.setItem('tos.history', JSON.stringify(next)) } catch { /* quota */ }
      return next
    })
  }, [completed, plan, risk, doneCount, exposure, timeline, user])

  if (view === 'signin') return <SignIn onEnter={(m) => { setUser(m); goView('showcase') }} />
  if (view === 'showcase') return <Showcase onLaunch={() => goView('console')} user={user} onSignOut={signOut} />

  return (
    <>
      <Dashboard
        scenario={scenario} setScenario={setScenario}
        mode={mode} setMode={setMode}
        running={running} completed={completed}
        timeline={timeline} agentStatus={agentStatus} runStatus={runStatus} risk={risk}
        plan={plan} exposure={exposure} doneCount={doneCount}
        onRun={(scen) => run(scen)} onStop={stopRun}
        onBack={() => goView('showcase')} alert={ALERT}
        user={user} onSignOut={signOut} onSwitchUser={setUser}
        onCommand={submitCommand}
        history={history} onClearHistory={clearHistory}
        presenting={presenting} onPresent={() => present(scenario)}
      />
      {approval && <ApprovalModal req={approval} onApprove={() => resolve('approve')} onReject={() => resolve('reject')} />}
    </>
  )
}

function Ticker() {
  const row = [...TICKER, ...TICKER]
  return (
    <div className="ticker" aria-hidden="true">
      <div className="ticker-track">
        {row.map((t, i) => <span className="tk" key={i}>{t}</span>)}
      </div>
    </div>
  )
}

function Topbar({ scenario, setScenario, mode, setMode, running, onRun, clock, onBack }) {
  return (
    <div className="topbar">
      <div className="brand">
        <div className="mark" onClick={onBack} title="Back to showcase" style={{ cursor: 'pointer' }}>T</div>
        <div>
          <div className="title">Titan Operations Sentinel</div>
          <div className="sub">Multi-agent operations brain</div>
        </div>
      </div>
      <div className="spacer" />
      <div className="controls">
        <div className="seg">
          {[['happy', 'Cascade'], ['edge', 'Edge'], ['escalation', 'Escalation']].map(([k, l]) => (
            <button key={k} className={scenario === k ? 'on' : ''} disabled={running} onClick={() => setScenario(k)}>{l}</button>
          ))}
        </div>
        <div className="seg">
          {[['replay', 'Replay'], ['live', 'Live']].map(([k, l]) => (
            <button key={k} className={mode === k ? 'on' : ''} disabled={running} onClick={() => setMode(k)}>{l}</button>
          ))}
        </div>
      </div>
      <span className="clock">{clock}</span>
      <button className="run-btn" onClick={onRun} disabled={running}>{running ? 'Running…' : '▶ Run Scenario'}</button>
    </div>
  )
}

function AgentNode({ agent, status }) {
  return (
    <div className={`agent-node ${status}`} style={{ '--ac': `var(--c-${agent.id})` }}>
      <span className="agent-dot" />
      <div className="agent-meta">
        <div className="agent-name">{agent.name}</div>
        <div className="agent-chal">{agent.chal}</div>
      </div>
      <span className="agent-state">{status}</span>
    </div>
  )
}

function Entry({ item }) {
  if (item.kind === 'system') return <div className="entry system">▸ {item.text}</div>
  if (item.kind === 'note') return <div className="entry note">◈ {item.text}</div>
  if (item.kind === 'human') return <div className="entry human">✓ {item.text}</div>
  const a = AGENT_MAP[item.agent] || { name: item.agent }
  const tag = item.status === 'active' ? 'reasoning…' : item.status === 'error' ? 'degraded' : 'reported'
  return (
    <div className={`entry block ${item.status === 'active' ? 'active' : ''}`} style={{ '--ac': `var(--c-${item.agent})` }}>
      <div className="block-head">
        <span className="ico" /><span className="who">{a.name}</span>
        <span className={`tag ${item.status === 'active' ? 'live' : ''}`}>{tag}</span>
      </div>
      {item.tools.length > 0 && (
        <div className="tools">{item.tools.map((t, i) => <span className="tool-chip" key={i}><span className="dot" /><b>{t.tool}</b></span>)}</div>
      )}
      {item.report
        ? <div className={`report ${item.status === 'error' ? 'err' : ''}`}>{item.report}</div>
        : item.status === 'active' && <div className="report" style={{ color: 'var(--text-mute)' }}>analyzing<span className="cursor" /></div>}
    </div>
  )
}

function CommandBar({ idle, running, onSubmit }) {
  const [val, setVal] = useState('')
  const submit = () => { onSubmit(val.trim() || CHIPS[0]); setVal('') }
  return (
    <div className="cmd-wrap">
      {idle && <div className="cmd-chips">{CHIPS.map((c) => <button key={c} className="cmd-chip" onClick={() => onSubmit(c)}>{c}</button>)}</div>}
      <div className="cmd-bar">
        <span className="prompt-glyph">$</span>
        <input value={val} onChange={(e) => setVal(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') submit() }}
          placeholder="Describe the situation…  e.g. CNC-07 vibration spiking, handle it" disabled={running} />
        <button className="cmd-send" onClick={submit} disabled={running} aria-label="Dispatch agents">→</button>
      </div>
    </div>
  )
}

function IdleHero() {
  return (
    <div className="console-hero">
      <div className="eyebrow">◈ Standing by · Titan Leipzig Plant 7</div>
      <h1>One alert. Five domains. <em>One costed plan.</em></h1>
      <p className="lead">Titan Operations Sentinel is an autonomous operations brain. When a machine signals failure, six agents perceive, reason across every domain, and converge on a safety-gated action plan, with a human in the loop on every euro.</p>
      <div className="alert-card">
        <span className="pulse" />
        <div className="ac-body">
          <b>ALT-22847</b> · CNC-07-LEI · vibration <b>7.2 mm/s</b> (thr 6.0), rising from 3.1 over 6h.<br />
          Type a command below, or pick a scenario, to dispatch the agents.
        </div>
      </div>
    </div>
  )
}

function ApprovalModal({ req, onApprove, onReject }) {
  return (
    <div className="scrim">
      <div className="modal">
        <div className="bar" />
        <div className="body">
          <div className="kicker">◈ Human-in-the-loop · approval required</div>
          <h2>{req.question}</h2>
          <p>This spend exceeds the agent's autonomous authority. It cannot self-approve, a human must decide.</p>
          <div className="figure">€{(req.amount_eur ?? 0).toLocaleString()}</div>
          <div className="ceiling">€{req.ceiling_eur} autonomous ceiling · routed to Plant Manager</div>
          <div className="actions">
            <button className="btn approve" onClick={onApprove}>✓ Approve</button>
            <button className="btn reject" onClick={onReject}>✕ Reject</button>
          </div>
        </div>
      </div>
    </div>
  )
}

function ActionPlan({ plan }) {
  return (
    <div className="plan-wrap">
      <div className="plan">
        <div className="ph"><span className="t">Action Plan</span><span className={`v ${plan.status}`}>{plan.status}</span></div>
        <div>
          {plan.lines.length > 0
            ? plan.lines.map((l, i) => (
                <div className="plan-line" key={i}><span className={`tier ${l.tier}`}>{l.tier}</span><span className="txt">{l.txt}</span></div>
              ))
            : <div className="report" style={{ whiteSpace: 'pre-wrap' }}>{plan.text}</div>}
        </div>
        {plan.roi && <div className="plan-foot"><span className="roi-l">Return on action</span><span className="roi">{plan.roi}</span></div>}
      </div>
    </div>
  )
}
