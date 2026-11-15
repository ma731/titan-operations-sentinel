import { useCallback, useEffect, useRef, useState } from 'react'
import Guide from './Guide.jsx'
import Logo from './Logo.jsx'
import { REPLIES } from './titanCommands.js'
import './story.css'

// The home page. Four screens of words over one continuous 3D scene: the film up front,
// what is failing, a decision you can try, and the proof. Between screens the 3D scene
// plays the rest of the story on its own (the alert, the specialists, the repair).
const SCENES = ['The story in 13 seconds', 'Inside Machine 7', 'The decision', 'The proof']
const STEP = 2   // the 3D scene has two beats for every screen of words
const asset = (name) => `${import.meta.env.BASE_URL}${name}`

const OPTIONS = {
  rush: { label: 'Rush delivery', price: '€3,200', over: true, text: 'A new bearing from the supplier, here in 18 hours. It is over the €500 limit, so it waits for Anna Weber, the plant manager.' },
  transfer: { label: 'From another plant', price: '€420', over: false, text: 'A bearing from a sister plant, here in 36 hours. It is under the €500 limit, so the agents go ahead on their own.' },
}

const canWebGL = () => {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')) } catch { return false }
}
const calm = () => !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export default function Home({ onLaunch, onSignIn }) {
  const rootRef = useRef(null)
  const canvasRef = useRef(null)
  const videoRef = useRef(null)
  const sectionRefs = useRef([])
  const fillRefs = useRef([])
  const sceneApi = useRef(null)
  const [scene, setScene] = useState(0)
  const [still, setStill] = useState(false)       // no 3D: reduced motion, or no WebGL
  const [muted, setMuted] = useState(true)
  const [option, setOption] = useState('rush')
  const [verdict, setVerdict] = useState(null)    // null | 'approved' | 'rejected'

  const opt = OPTIONS[option]
  const gate = !opt.over || verdict === 'approved' ? 'open' : verdict === 'rejected' ? 'reject' : 'wait'

  // where the reader is: 0 when the first screen is centred, 1 when the second is, fractions between
  const measure = useCallback(() => {
    const root = rootRef.current
    const els = sectionRefs.current
    if (!root || !els.length) return
    const mid = root.scrollTop + root.clientHeight / 2
    const centres = els.map((el) => el.offsetTop + el.offsetHeight / 2)
    let s = 0
    for (let i = 0; i < centres.length - 1; i++) {
      if (mid >= centres[i]) s = i + Math.min(1, (mid - centres[i]) / Math.max(1, centres[i + 1] - centres[i]))
    }
    if (!Number.isFinite(s)) s = 0
    sceneApi.current?.setProgress(s * STEP)
    fillRefs.current.forEach((el, i) => { if (el) el.style.transform = `scaleX(${Math.min(1, Math.max(0, s - i + 0.5))})` })
    setScene(Math.abs(s - Math.round(s)) < 0.3 ? Math.round(s) : -1)   // between screens the words step back and the picture plays
  }, [])

  useEffect(() => {
    const root = rootRef.current
    measure()
    root.addEventListener('scroll', measure, { passive: true })
    window.addEventListener('resize', measure)
    return () => { root.removeEventListener('scroll', measure); window.removeEventListener('resize', measure) }
  }, [measure])

  // the 3D scene loads on its own, so the words and the film are there before it arrives
  useEffect(() => {
    if (calm() || !canWebGL()) { setStill(true); return }
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

  useEffect(() => { sceneApi.current?.setDecision(gate) }, [gate])

  // the film plays silently on a loop; with reduced motion it waits for a tap instead
  useEffect(() => {
    const v = videoRef.current
    if (!v) return
    v.muted = true   // set on the element itself: browsers only allow silent films to start on their own
    if (calm()) { v.pause(); v.controls = true } else v.play().catch(() => { v.controls = true })
  }, [])
  const toggleSound = () => {
    const v = videoRef.current
    if (!v) return
    if (v.muted) { v.muted = false; v.currentTime = 0; v.play().catch(() => {}) } else v.muted = true
    setMuted(v.muted)
  }

  const go = useCallback((i) => {
    const el = sectionRefs.current[Math.min(SCENES.length - 1, Math.max(0, i))]
    const root = rootRef.current
    if (!el || !root) return
    root.scrollTo({ top: el.offsetTop + el.offsetHeight / 2 - root.clientHeight / 2, behavior: calm() ? 'auto' : 'smooth' })
  }, [])

  // stories on a keyboard: arrows move one screen
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.closest?.('input, textarea, [contenteditable]')) return
      const at = scene < 0 ? 0 : scene
      if (e.key === 'ArrowRight') go(at + 1)
      if (e.key === 'ArrowLeft') go(at - 1)
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
        <nav className="st-segs" aria-label="Sections">
          {SCENES.map((name, i) => (
            <button key={name} className="st-seg" onClick={() => go(i)} aria-label={`${i + 1}: ${name}`} aria-current={scene === i ? 'step' : undefined} title={name}>
              <span className="st-seg-fill" ref={(el) => { fillRefs.current[i] = el }} />
            </button>
          ))}
        </nav>
        <div className="st-bar-end">
          <button className="st-signin" onClick={onSignIn}>Sign in</button>
          <button className="st-open" onClick={onLaunch}>Open the console</button>
        </div>
      </header>

      <main>
        <section ref={ref(0)} className={cls(0, 'hero')}>
          <div className="st-panel">
            <p className="st-when">Friday, 16:32 · Leipzig</p>
            <h1>Machine 7 will break this weekend. An AI team is about to notice.</h1>
            <p className="st-lead">Titan is six AI agents for a factory. One sensor alert goes in, one costed plan comes out, and a person approves anything over €500.</p>
            <div className="st-actions">
              <button className="st-btn" onClick={onLaunch}>Run it yourself</button>
              <button className="st-btn ghost" onClick={toggleSound}>{muted ? 'Watch with sound' : 'Mute the film'}</button>
            </div>
          </div>
          <figure className="st-film">
            <video ref={videoRef} src={asset('titan-factory-line.mp4')} poster={asset('titan-factory-line.jpg')} muted loop playsInline preload="metadata"
              aria-label="Animation: a work order for Machine 7 rides a belt past five stations, Reliability, Supply Chain, Production, Quality and Safety, stops at a gate where a person approves it, and comes out as the finished plan." />
            <figcaption>The whole story in 13 seconds. Scroll for the detail.</figcaption>
          </figure>
        </section>

        <section ref={ref(1)} className={cls(1, 'low')}>
          <div className="st-panel">
            <p className="st-when">Inside Machine 7</p>
            <h2>This is the part that is failing.</h2>
            <p className="st-lead">The cutting tool spins thousands of times a minute on rings of steel balls called bearings. One ring is worn. That is what the sensor felt, and when it goes, the machine stops.</p>
          </div>
        </section>

        <section ref={ref(2)} className={cls(2, 'centre')}>
          <div className={`st-slip ${gate === 'open' ? 'done' : gate === 'reject' ? 'rejected' : ''}`}>
            <div className="st-slip-bar" />
            <p className="st-when">Friday, 16:33 · try it yourself</p>
            <h2>Who is allowed to spend this?</h2>
            <div className="st-opts" role="group" aria-label="Choose how to get the bearing">
              {Object.entries(OPTIONS).map(([k, o]) => (
                <button key={k} className={option === k ? 'on' : ''} aria-pressed={option === k} onClick={() => { setOption(k); setVerdict(null) }}>
                  <span>{o.label}</span><b>{o.price}</b>
                </button>
              ))}
            </div>
            <p>{opt.text}</p>
            {!opt.over && <p className="st-verdict ok">No approval needed. The plan goes ahead.</p>}
            {opt.over && !verdict && (
              <div className="st-two">
                <button className="st-approve" onClick={() => setVerdict('approved')}>Approve €3,200</button>
                <button className="st-reject" onClick={() => setVerdict('rejected')}>Reject</button>
              </div>
            )}
            {opt.over && verdict === 'approved' && <p className="st-verdict ok">Approved by Anna Weber, Friday 16:33. The order goes out and the gate opens.</p>}
            {opt.over && verdict === 'rejected' && <p className="st-verdict no">Rejected. The agents slow Machine 7 down to buy time and pass the decision up to the operations director.</p>}
            {opt.over && verdict && <button className="st-again" onClick={() => setVerdict(null)}>Decide again</button>}
            <p className="st-rule">The €500 rule is written in code, not in a prompt, so the AI cannot talk its way past it.</p>
          </div>
        </section>

        <section ref={ref(3)} className={cls(3, 'centre last')}>
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
              <li><b>Every night</b> it re-runs its tests and reports any score that drops</li>
            </ul>
            <p className="st-fine">The factory data is simulated: realistic, but not a real plant. IE University, Agentic AI for IT, 2026. Presenting? <button className="st-again" onClick={onSignIn}>Sign in with your name</button></p>
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
