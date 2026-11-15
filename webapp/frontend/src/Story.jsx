import { useCallback, useEffect, useRef, useState } from 'react'
import Guide from './Guide.jsx'
import Logo from './Logo.jsx'
import { REPLIES } from './titanCommands.js'
import { AGENTS } from './agentsMeta.js'
import './story.css'

// The home page: the Friday Cascade told in seven scenes over a 3D factory floor.
// Scroll moves the story; the bar at the top works like stories (tap a segment to jump).
const SCENES = ['Friday afternoon', 'The alert', 'Inside Machine 7', 'The specialists', 'The decision', 'The repair', 'Monday morning']

const SAID = {
  reliability: 'The bearing fails between Sunday evening and Monday evening.',
  supply_chain: 'No spare here. A rush delivery costs €3,200.',
  production: "I moved Machine 7's jobs to Machine 8.",
  quality: 'Machine 8 can take the extra work.',
  compliance_safety: 'All four steps are safe. I sign off.',
}

const canWebGL = () => {
  try {
    const c = document.createElement('canvas')
    return !!(c.getContext('webgl2') || c.getContext('webgl'))
  } catch { return false }
}

export default function Story({ onLaunch }) {
  const rootRef = useRef(null)
  const canvasRef = useRef(null)
  const sectionRefs = useRef([])
  const fillRefs = useRef([])
  const sceneApi = useRef(null)
  const [scene, setScene] = useState(0)
  const [heard, setHeard] = useState(0)        // how many specialists have spoken
  const [approved, setApproved] = useState(false)
  const [still, setStill] = useState(false)    // no 3D: reduced motion, or no WebGL

  // where the reader is: 0 when scene 0 is centred, 1 when scene 1 is, fractions between
  const measure = useCallback(() => {
    const els = sectionRefs.current
    const root = rootRef.current
    if (!root || !els.length) return
    const mid = root.scrollTop + root.clientHeight / 2
    const centres = els.map((el) => el.offsetTop + el.offsetHeight / 2)
    let s = 0
    for (let i = 0; i < centres.length - 1; i++) {
      if (mid >= centres[i]) s = i + Math.min(1, (mid - centres[i]) / Math.max(1, centres[i + 1] - centres[i]))
    }
    if (!Number.isFinite(s)) s = 0
    sceneApi.current?.setProgress(s)
    fillRefs.current.forEach((el, i) => { if (el) el.style.transform = `scaleX(${Math.min(1, Math.max(0, s - i + 0.5))})` })
    setScene(Math.round(s))
    setHeard(Math.min(5, Math.max(0, Math.floor((s - 2.45) / 0.2) + 1)))
    if (s > 4.4) setApproved(true)
  }, [])

  useEffect(() => {
    const root = rootRef.current
    measure()
    root.addEventListener('scroll', measure, { passive: true })
    window.addEventListener('resize', measure)
    return () => { root.removeEventListener('scroll', measure); window.removeEventListener('resize', measure) }
  }, [measure])

  // the 3D scene loads on its own, so the text is readable before it arrives
  useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || !canWebGL()) { setStill(true); return }
    let dead = false
    let api = null
    const size = () => api?.setSize(window.innerWidth, window.innerHeight)
    const vis = () => (document.hidden ? api?.stop() : api?.start())
    import('./scene3d.js').then(({ createScene }) => {
      if (dead || !canvasRef.current) return
      api = createScene(canvasRef.current, { mobile: window.innerWidth < 700 })
      sceneApi.current = api
      size(); measure(); api.start()
      window.addEventListener('resize', size)
      document.addEventListener('visibilitychange', vis)
    }).catch(() => setStill(true))
    return () => {
      dead = true
      window.removeEventListener('resize', size)
      document.removeEventListener('visibilitychange', vis)
      api?.dispose(); sceneApi.current = null
    }
  }, [measure])

  const go = useCallback((i) => {
    const el = sectionRefs.current[Math.min(SCENES.length - 1, Math.max(0, i))]
    if (!el) return
    const root = rootRef.current
    const top = el.offsetTop + el.offsetHeight / 2 - root.clientHeight / 2
    const calm = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    root.scrollTo({ top, behavior: calm ? 'auto' : 'smooth' })
  }, [])

  // stories on a keyboard: arrows move one scene
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.closest?.('input, textarea, [contenteditable]')) return
      if (e.key === 'ArrowRight') go(scene + 1)
      if (e.key === 'ArrowLeft') go(scene - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [go, scene])

  const ref = (i) => (el) => { sectionRefs.current[i] = el }
  const cls = (i, extra = '') => `st-scene ${extra} ${scene === i ? 'in' : ''}`

  return (
    <div ref={rootRef} className={`story ${still ? 'story-still' : ''}`}>
      {!still && <canvas ref={canvasRef} className="st-canvas" aria-hidden="true" />}

      <header className="st-bar">
        <div className="st-brand"><Logo size={22} accent="#14e8a0" /><span>Titan Operations Sentinel</span></div>
        <nav className="st-segs" aria-label="Story scenes">
          {SCENES.map((name, i) => (
            <button key={name} className="st-seg" onClick={() => go(i)} aria-label={`Scene ${i + 1}: ${name}`} aria-current={scene === i ? 'step' : undefined} title={name}>
              <span className="st-seg-fill" ref={(el) => { fillRefs.current[i] = el }} />
            </button>
          ))}
        </nav>
        <button className="st-open" onClick={onLaunch}>Open the console</button>
      </header>

      <main>
        <section ref={ref(0)} className={cls(0)}>
          <div className="st-panel">
            <p className="st-when">Friday, 16:32 · Leipzig</p>
            <h1>Machine 7 will break this weekend. An AI team is about to notice.</h1>
            <p className="st-lead">Titan is six AI agents for a factory. One sensor alert goes in, one costed plan comes out, and a person approves anything over €500.</p>
            <div className="st-actions">
              <button className="st-btn" onClick={onLaunch}>Open the console</button>
              <button className="st-btn ghost" onClick={() => go(1)}>See the story <span aria-hidden="true">↓</span></button>
            </div>
          </div>
        </section>

        <section ref={ref(1)} className={cls(1)}>
          <div className="st-panel">
            <p className="st-when">Friday, 16:32</p>
            <h2>One alert out of 22,000.</h2>
            <p className="st-lead">The plant raises about 22,000 sensor alerts a day. Every dot is one of them. A simple filter, with no AI in it, picks the one that matters.</p>
            <dl className="st-read">
              <div><dt>Vibration on Machine 7</dt><dd>7.2 <small>mm/s</small></dd></div>
              <div><dt>Safe limit</dt><dd>6.0 <small>mm/s</small></dd></div>
              <div><dt>If it stops</dt><dd>€180,000 <small>a day</small></dd></div>
            </dl>
          </div>
        </section>

        <section ref={ref(2)} className={cls(2, 'low')}>
          <div className="st-panel">
            <p className="st-when">Inside Machine 7</p>
            <h2>This is the part that is failing.</h2>
            <p className="st-lead">The cutting tool spins thousands of times a minute on rings of steel balls called bearings. One ring is worn. That is what the sensor felt, and when it goes, the machine stops.</p>
          </div>
        </section>

        <section ref={ref(3)} className={cls(3, 'tall')}>
          <div className="st-panel sticky">
            <p className="st-when">Friday, 16:32 to 16:33</p>
            <h2>Five specialists, about a minute.</h2>
            <p className="st-lead">A coordinator sends them in one at a time. Each checks one thing and says what it found.</p>
            <ol className="st-team">
              {AGENTS.map((a, i) => (
                <li key={a.id} className={i < heard ? 'on' : ''} style={{ '--c': `var(--ag-${i})` }}>
                  <span className="st-team-dot" />
                  <span className="st-team-name">{a.name}</span>
                  <span className="st-team-said">{SAID[a.id]}</span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section ref={ref(4)} className={cls(4, 'centre')}>
          <div className={`st-slip ${approved ? 'done' : ''}`}>
            <div className="st-slip-bar" />
            <p className="st-when">Friday, 16:33 · a person decides</p>
            <h2>€3,200 is over the limit.</h2>
            <p>Agents can spend up to €500 on their own. Anything more stops and waits for <b>Anna Weber</b>, the plant manager. That rule is written in code, so no prompt can talk its way past it.</p>
            <button className="st-approve" onClick={() => { setApproved(true); go(5) }} disabled={approved}>
              {approved ? 'Approved by Anna Weber, 16:33' : 'Approve €3,200'}
            </button>
          </div>
        </section>

        <section ref={ref(5)} className={cls(5)}>
          <div className="st-panel">
            <p className="st-when">Saturday, 06:00</p>
            <h2>The bearing arrives. The line keeps running.</h2>
            <p className="st-lead">The part lands 18 hours after the order. Machine 7's jobs run on Machine 8 while it is repaired on Saturday morning.</p>
          </div>
        </section>

        <section ref={ref(6)} className={cls(6, 'centre last')}>
          <div className="st-panel wide">
            <p className="st-when">Monday, 08:00</p>
            <h2>116 hours of downtime avoided, for €3,200.</h2>
            <p className="st-lead">And a full record of who decided what, and why.</p>
            <div className="st-actions">
              <button className="st-btn" onClick={onLaunch}>Run it yourself in the console</button>
              <a className="st-btn ghost" href="https://github.com/ma731/titan-operations-sentinel#readme" target="_blank" rel="noreferrer">Read how it works</a>
            </div>
            <ul className="st-proof">
              <li><b>208 of 208</b> checks pass across 34 test situations</li>
              <li><b>19 of 19</b> attacks on the AI blocked</li>
              <li><b>0</b> missed safety stops in testing</li>
            </ul>
            <p className="st-fine">The factory data is simulated: realistic, but not a real plant. IE University, Agentic AI for IT, 2026.</p>
          </div>
        </section>
      </main>

      <Guide onAction={onLaunch} actionLabel="Open the console"
        onCommand={(c) => {
          if (c.cmd === 'run' || c.cmd === 'present' || c.cmd === 'nav') { setTimeout(onLaunch, 900); return REPLIES.showcaseOpen }
          return REPLIES.showcaseFirst
        }} />
    </div>
  )
}
