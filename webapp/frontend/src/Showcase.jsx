import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { animate, stagger } from 'animejs'
import AgentGraph from './AgentGraph.jsx'
import Logo from './Logo.jsx'

// a frozen "mid-run" state so the hero graph glows with energy
// Public assets have to carry the deploy base path. GitHub Pages serves this site from
// /<repo>/, so a hardcoded '/shots/x.png' resolves to the domain root and 404s. Vite fills
// import.meta.env.BASE_URL with '/' locally and '/<repo>/' in the Pages build.
const shot = (name) => `${import.meta.env.BASE_URL}shots/${name}.png`

const HERO_STATE = { reliability: 'done', supply_chain: 'done', production: 'active', quality: 'idle', compliance_safety: 'idle' }
const MARQUEE = ['CNC-07-LEI', 'VIBRATION 7.2 mm/s ▲', 'RUL 52-76 h', '€180,000 / day AT RISK', 'ROI 79.7:1', '6 AUTONOMOUS AGENTS', '5 TMC CHALLENGES', 'HUMAN GATE > €500', 'RUNS ON FREE-TIER']

const STATS = [
  { n: '6', l: 'Autonomous agents' },
  { n: '5', l: 'TMC challenges' },
  { n: <>79.7<span className="g">:1</span></>, l: 'Action ROI' },
  { n: <>€0<span className="g"></span></>, l: 'Runs on free tier' },
]

const PROJECTS = [
  {
    id: 'console', cat: 'Demo', tag: 'Live Demo', title: 'Live Operations Console', year: '2026',
    bg: 'var(--c-dark)', dark: true, feature: true, span: 2, img: shot('console'),
    blurb: 'Watch six agents perceive, reason across five domains, and converge on one costed plan, live.',
    launch: true,
  },
  {
    id: 'agents', cat: 'Architecture', tag: 'Architecture', title: 'Six-Agent Orchestrator', year: '2026',
    bg: 'var(--c-lav)', img: shot('agents'),
    blurb: 'An LLM supervisor routes autonomous ReAct specialists and lets them converse through a shared transcript.',
  },
  {
    id: 'approval', cat: 'Safety', tag: 'Human-in-the-loop', title: 'The €500 Approval Gate', year: '2026',
    bg: 'var(--c-cream)', img: shot('approval'),
    blurb: 'Any spend beyond the autonomy ceiling pauses the whole plan for a human decision.',
  },
  {
    id: 'cascade', cat: 'Demo', tag: 'Scenario', title: 'The Friday Cascade', year: '2026',
    bg: 'var(--c-mint)', img: shot('cascade'),
    blurb: 'Six agents converse through one shared transcript as the bearing-failure crisis unfolds in real time.',
  },
  {
    id: 'compliance', cat: 'Safety', tag: 'Compliance', title: 'Safety Can HALT', year: '2026',
    bg: 'var(--c-blush)', img: shot('compliance'),
    blurb: 'Every action is checked against OSHA / OEM limits and written to a full audit trail, Compliance can stop the plan outright.',
  },
  {
    id: 'feasible', cat: 'Engineering', tag: 'Feasibility', title: 'Zero-Cost Demo', year: '2026',
    bg: 'var(--c-sky)', img: shot('feasible'), span: 2,
    blurb: 'A full six-agent run is ~18k tokens, €0 on Gemini\'s free tier, with a recorded replay fallback so it can never fail.',
  },
]

const DETAILS = {
  console: ['Six agents reason live over one sensor alert', 'Supervisor routes; specialists pick their own tools', 'Ends in a costed, safety-gated action plan', 'Human approves anything over the €500 ceiling'],
  agents: ['An LLM supervisor routes between 6 agents', 'Each specialist is an autonomous ReAct agent', 'They converse through one shared transcript', 'FOLLOWUP lets an agent ask another directly'],
  approval: ['€500 autonomy ceiling on spend', 'Anything above pauses the whole plan', 'interrupt() gate → human approve / reject', 'Compliance can HALT independently of cost'],
  cascade: ['CNC-07-LEI bearing failure predicted 52-76h out', '€180,000/day of downtime on the line', 'Three paths: Cascade, Edge, Escalation', 'Each behaves differently, gate / autonomous / human review'],
  compliance: ['Every proposed action gated vs OSHA / OEM limits', 'Compliance can HALT the entire plan', 'Full audit trail assembled per run', 'Safety is a hard override, not a suggestion'],
  feasible: ['Runs on free Gemini / OpenRouter tiers', '~62% transcript token trim', 'Recorded replay = €0, can-not-fail demo', 'One-line provider swap when limits bite'],
}

const STEPS = [
  { n: '01', t: 'Perceive', d: 'A sensor alert arrives; the orchestrator triages 22k signals to the critical asset.' },
  { n: '02', t: 'Route', d: 'A supervisor decides which specialist acts next, guided autonomy, not a fixed script.' },
  { n: '03', t: 'Reason', d: 'Each agent picks its own tools, reasons, and reports into a shared transcript.' },
  { n: '04', t: 'Converge', d: 'Findings combine into one costed, safety-gated plan across five domains.' },
  { n: '05', t: 'Decide', d: 'Compliance can HALT; spend over €500 pauses for a human. Then it acts.' },
]

// The 8 design-thinking pillars from the brief, answered for Titan Operations Sentinel.
const PILLARS = [
  { n: '01', t: 'Agent goals', d: 'Catch a failing machine early and hand the plant manager one costed, safety-gated plan. Value: €180,000/day of downtime avoided, 79.7:1 ROI.' },
  { n: '02', t: 'Input & context', d: 'Trigger: a sensor alert. Inputs: telemetry, inventory, suppliers, production, quality, compliance. Memory: shared transcript + run checkpoints.' },
  { n: '03', t: 'Tools & actions', d: '18 tools across the agents (read / write / execute). Spend over €500 or any safety action needs human approval.' },
  { n: '04', t: 'Lifecycle', d: 'Perceive the alert, reason across five domains, act on a plan, and learn: case memory, human feedback, self-critique, and outcome validation.' },
  { n: '05', t: 'Architecture', d: 'Multi-agent: an LLM orchestrator routes five autonomous ReAct specialists that converse through one shared transcript.' },
  { n: '06', t: 'Risks & guardrails', d: 'Hallucination guard (it refuses thin data), Compliance HALT, the €500 ceiling, and an interrupt() human gate.' },
  { n: '07', t: 'Example run', d: 'The Friday Cascade: bearing failure 52-76h out, parts gap, ROI math, then a human approves the expedite. Three live paths.' },
  { n: '08', t: 'Tech stack', d: 'Python + LangGraph for the graph; FastAPI + React/Vite for this console. Provider-agnostic LLM (Gemini, Groq, Azure), hosted on Azure.' },
]
const FILTERS = ['All', 'Demo', 'Architecture', 'Safety', 'Engineering']

export default function Showcase({ onLaunch, user, onSignOut }) {
  const [filter, setFilter] = useState('All')
  const [detail, setDetail] = useState(null)
  const shown = PROJECTS.filter((p) => filter === 'All' || p.cat === filter)

  // anime.js choreography: a sequenced hero entrance + staggered scroll reveals.
  // Elements are visible by default, anime only animates if it loads, so a failure
  // never leaves the page blank. Skipped entirely under prefers-reduced-motion.
  useLayoutEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    const cleanups = []
    try {
      const ease = 'outExpo'
      // hero plays in sequence after the headline starts resolving
      animate('.sc-eyebrow', { opacity: [0, 1], translateY: [-10, 0], duration: 600, ease, delay: 120 })
      animate('.sc-hero p', { opacity: [0, 1], translateY: [16, 0], duration: 700, ease, delay: 360 })
      animate('.sc-hero .actions > *', { opacity: [0, 1], translateY: [14, 0], scale: [0.96, 1], duration: 650, ease, delay: stagger(90, { start: 560 }) })

      // staggered reveals when a band scrolls into view
      const reveal = (containerSel, itemSel, opts = {}) => {
        const el = document.querySelector(containerSel)
        if (!el) return
        const io = new IntersectionObserver((entries) => {
          entries.forEach((e) => {
            if (!e.isIntersecting) return
            animate(e.target.querySelectorAll(itemSel), {
              opacity: [0, 1], translateY: [22, 0], duration: 720, ease, delay: stagger(70), ...opts,
            })
            io.unobserve(e.target)
          })
        }, { threshold: 0.25 })
        io.observe(el)
        cleanups.push(() => io.disconnect())
      }
      reveal('.sc-stats', '.sc-stat')
      reveal('.sc-steps', '.sc-step', { scale: [0.97, 1] })
    } catch { /* anime unavailable → elements just stay visible */ }
    return () => cleanups.forEach((fn) => fn())
  }, [])

  return (
    <div className="showcase">
      <nav className="sc-nav">
        <div className="sc-nav-inner">
          <div className="sc-logo"><Logo size={24} accent="#0fbe85" /> Titan Operations Sentinel</div>
          <div className="links">
            <a onClick={onLaunch}>Live demo</a>
            <a href="#work">Work</a>
            <a href="#contact">Approach</a>
            {user && <a onClick={onSignOut} title="Switch user">Sign out ({user.name.split(' ')[0]})</a>}
          </div>
          <button className="sc-cta" onClick={onLaunch}>Launch console →</button>
        </div>
      </nav>

      <div className="sc-inner">
        <header className="sc-hero">
          <div className="sc-eyebrow">◈ Agentic AI · Manufacturing operations</div>
          <RevealHeadline />
          <p>Titan Operations Sentinel is an autonomous operations brain. When a machine signals failure, six agents reason across reliability, supply, production, quality and safety, and hand a human one decision.</p>
          <div className="actions">
            <button className="sc-btn-primary" onClick={onLaunch}>Launch the live console →</button>
            <a className="sc-btn-ghost" href="#work">See the system</a>
          </div>
        </header>

        {/* live orchestration graph as the hero centerpiece */}
        <div className="sc-hero-stage" onClick={onLaunch} title="Launch the live console">
          <AgentGraph agentStatus={HERO_STATE} running />
          <div className="sc-stage-badge"><span className="d" /> live · click to run</div>
        </div>

        <div className="sc-marquee" aria-hidden="true">
          <div className="sc-marquee-row">
            {[...MARQUEE, ...MARQUEE].map((m, i) => <span className="sc-mq" key={i}>{m}</span>)}
          </div>
        </div>

        <div className="sc-grid-band">
          <span className="sc-grid-cap">six agents · always watching · move your cursor</span>
          <AnimeGrid />
        </div>

        <div className="sc-stats">
          {STATS.map((s, i) => (
            <div className="sc-stat" key={i}><div className="n">{s.n}</div><div className="l">{s.l}</div></div>
          ))}
        </div>

        <div id="work">
          <div className="sc-section-label"><span className="tick" /> The system, in pieces</div>
          <div className="sc-filters">
            {FILTERS.map((f) => (
              <button key={f} className={`sc-pill ${filter === f ? 'on' : ''}`} onClick={() => setFilter(f)}>{f}</button>
            ))}
          </div>

          <div className="sc-grid">
            {shown.map((p, i) => (
              <Card key={p.id} p={p} index={i} onLaunch={onLaunch} onOpen={setDetail} />
            ))}
          </div>
        </div>

        {/* how it works */}
        <div className="sc-section-label"><span className="tick" /> How it works</div>
        <div className="sc-steps">
          {STEPS.map((s) => (
            <div className="sc-step" key={s.n}>
              <div className="sc-step-n">{s.n}</div>
              <div className="sc-step-t">{s.t}</div>
              <div className="sc-step-d">{s.d}</div>
            </div>
          ))}
        </div>

        {/* the 8 design decisions (maps to the assignment's design-thinking pillars) */}
        <div className="sc-section-label"><span className="tick" /> The design, in eight decisions</div>
        <div className="sc-pillars">
          {PILLARS.map((p) => (
            <div className="sc-pillar" key={p.n}>
              <div className="sc-pillar-n">{p.n}</div>
              <div className="sc-pillar-t">{p.t}</div>
              <div className="sc-pillar-d">{p.d}</div>
            </div>
          ))}
        </div>

        {/* why an agent */}
        <div className="sc-section-label"><span className="tick" /> Why an agent, not a dashboard</div>
        <div className="sc-why">
          <div className="sc-why-col"><div className="sc-why-h">A dashboard</div><p>Shows you six panels and waits. The human does the cross-domain reasoning under time pressure.</p></div>
          <div className="sc-why-col"><div className="sc-why-h">An automation</div><p>Fires a fixed rule. It can't weigh ROI vs risk, adapt a reroute, or know when to ask a human.</p></div>
          <div className="sc-why-col on"><div className="sc-why-h">Our agent</div><p>Reasons across five domains, decides, and hands you <b>one costed, safety-gated plan</b>, and escalates when the data is thin.</p></div>
        </div>

        <footer className="sc-footer" id="contact">
          <h2>See it think. <span className="g">Then judge it.</span></h2>
          <div className="sub">The whole point is the demo. Launch the console and watch one alert become a safety-gated, costed action plan in under two minutes.</div>
          <button className="sc-btn-primary" onClick={onLaunch}>Launch the live console →</button>
          <div className="fine">Titan Operations Sentinel · IE Agentic AI · 2026</div>
        </footer>

        {detail && <DetailModal p={detail} onClose={() => setDetail(null)} onLaunch={onLaunch} />}
      </div>
    </div>
  )
}

// Signature anime.js "living grid" (à la animejs.com): a field of dots that
// continuously ripples from the centre, cycles through the six agent colours, and
// ripples outward from the cursor on hover. Pure decoration, reduced-motion safe.
const GRID_COLORS = ['#4d9bff', '#14e8a0', '#a78bfa', '#ffb84d', '#ff6b81', '#0fbe85']
function AnimeGrid() {
  const ref = useRef(null)
  useEffect(() => {
    const root = ref.current
    if (!root || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    const cols = 30, rows = 7
    root.innerHTML = ''                         // guard against StrictMode double-mount
    root.style.gridTemplateColumns = `repeat(${cols}, 1fr)`
    const dots = []
    for (let i = 0; i < cols * rows; i++) {
      const d = document.createElement('span'); d.className = 'ag-dot'; root.appendChild(d); dots.push(d)
    }
    let loop
    try {
      // continuous wave: scale + colour-switch rolling out from the centre
      loop = animate(dots, {
        scale: [0.5, 1.15],
        backgroundColor: GRID_COLORS,
        delay: stagger(110, { grid: [cols, rows], from: 'center' }),
        loop: true, alternate: true, duration: 2200, ease: 'inOutSine',
      })
    } catch { /* anime down → static dots */ }
    const onMove = (e) => {
      try {
        const r = root.getBoundingClientRect()
        const col = Math.max(0, Math.min(cols - 1, Math.round(((e.clientX - r.left) / r.width) * (cols - 1))))
        const row = Math.max(0, Math.min(rows - 1, Math.round(((e.clientY - r.top) / r.height) * (rows - 1))))
        animate(dots, {
          opacity: [{ to: 0.95, duration: 200 }, { to: 0.32, duration: 700 }],
          delay: stagger(55, { grid: [cols, rows], from: row * cols + col }),
          ease: 'outQuad',
        })
      } catch { /* ignore */ }
    }
    root.addEventListener('pointermove', onMove)
    return () => { root.removeEventListener('pointermove', onMove); try { loop?.pause() } catch { /* ignore */ } root.innerHTML = '' }
  }, [])
  return <div className="anime-grid" ref={ref} aria-hidden="true" />
}

// headline whose words "materialize" (de-blur + rise) in sequence, fits the
// "agents generate the plan" story (Aceternity Text-Generate technique).
const HERO_LINES = [['One', 'sensor', 'alert.'], ['Five', 'domains.'], ['One', 'costed', 'plan.']]
function RevealHeadline() {
  let n = 0
  return (
    <h1 className="sc-reveal">
      {HERO_LINES.map((words, li) => (
        <span className={`rv-line ${li === HERO_LINES.length - 1 ? 'g' : ''}`} key={li}>
          {words.map((w, wi) => (
            <span className="rv-word" style={{ '--d': `${(n++) * 0.07 + 0.1}s` }} key={wi}>{w}</span>
          ))}
        </span>
      ))}
    </h1>
  )
}

function Card({ p, index, onLaunch, onOpen }) {
  const ref = useRef(null)
  const [seen, setSeen] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); io.disconnect() } }, { threshold: 0.15 })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  const onClick = () => { if (p.launch) onLaunch(); else onOpen(p) }
  const onMove = (e) => {
    const el = ref.current; if (!el) return
    const r = el.getBoundingClientRect()
    el.style.setProperty('--mx', `${e.clientX - r.left}px`)
    el.style.setProperty('--my', `${e.clientY - r.top}px`)
  }
  return (
    <article
      ref={ref}
      className={`sc-card ${p.dark ? 'dark' : ''} ${p.feature ? 'feature' : ''} ${p.span === 2 ? 'sc-span2' : ''} ${seen ? 'in' : ''}`}
      style={{ '--cbg': p.bg, transitionDelay: `${(index % 2) * 80}ms` }}
      onClick={onClick}
      onMouseMove={onMove}
    >
      {p.img
        ? <div className="sc-shot"><img src={p.img} alt={p.title} loading="lazy" /></div>
        : <div className="sc-figure">{p.figure}</div>}
      <div className="sc-foot">
        <div>
          <span className="sc-tag">{p.tag}</span>
          <div className="meta" style={{ marginTop: 10 }}>
            <span className="t">{p.title}</span><span className="y">· {p.year}</span>
          </div>
        </div>
        <span className="sc-arrow">→</span>
      </div>
    </article>
  )
}

function DetailModal({ p, onClose, onLaunch }) {
  const points = DETAILS[p.id] || []
  return (
    <div className="sc-scrim" onClick={onClose}>
      <div className="sc-modal" onClick={(e) => e.stopPropagation()}>
        <button className="sc-close" onClick={onClose} aria-label="Close">✕</button>
        <div className="sc-modal-tag">{p.tag} · {p.year}</div>
        <h3 className="sc-modal-h">{p.title}</h3>
        <p className="sc-modal-blurb">{p.blurb}</p>
        {p.img && <div className="sc-modal-shot"><img src={p.img} alt={p.title} /></div>}
        <ul className="sc-modal-list">
          {points.map((pt, i) => <li key={i}><span className="sc-bullet" />{pt}</li>)}
        </ul>
        <button className="sc-btn-primary" onClick={onLaunch} style={{ marginTop: 22 }}>Launch the live console →</button>
      </div>
    </div>
  )
}
