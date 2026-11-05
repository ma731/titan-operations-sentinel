import { useEffect, useRef, useState } from 'react'
import { GUIDE, STARTERS, matchAnswer } from './guideKnowledge.js'
import './guide.css'

const BY_ID = Object.fromEntries(GUIDE.map((g) => [g.id, g]))

// Help chat. Written answers always work (no key, no cost). When the console is
// connected live, free-text questions go to the configured model via /api/guide,
// grounded in prompts/guide.md, and fall back to the written answers if that fails.
export default function Guide({ mode = 'replay', onAction, actionLabel }) {
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState([])
  const [val, setVal] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }) }, [msgs, busy])
  useEffect(() => { if (open) inputRef.current?.focus() }, [open])
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  const written = (item) => ({ who: 'bot', text: item.a, src: 'written', show: item.show, label: item.label, follow: nextIds(item.id) })

  const askId = (id) => {
    const item = BY_ID[id]
    setMsgs((m) => [...m, { who: 'me', text: item.q }, written(item)])
  }

  const askText = async (raw) => {
    const text = raw.trim()
    if (!text || busy) return
    setVal('')
    const history = msgs.slice(-6).map((m) => ({ role: m.who === 'me' ? 'user' : 'assistant', text: m.text }))
    setMsgs((m) => [...m, { who: 'me', text }])
    const hit = matchAnswer(text)
    if (mode === 'live') {
      setBusy(true)
      try {
        const r = await fetch('/api/guide', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: text, history }) })
        const d = await r.json()
        if (d.ok && d.answer) {
          setMsgs((m) => [...m, { who: 'bot', text: d.answer, src: 'model', model: d.model, show: hit?.show, label: hit?.label, follow: hit ? nextIds(hit.id) : STARTERS.slice(0, 3) }])
          setBusy(false); return
        }
      } catch { /* backend not reachable: use the written answers */ }
      setBusy(false)
    }
    if (hit) setMsgs((m) => [...m, written(hit)])
    else setMsgs((m) => [...m, {
      who: 'bot', src: 'written', follow: STARTERS,
      text: mode === 'live'
        ? 'The model could not answer just now, and I have no written answer for that. Try one of these:'
        : 'I only have written answers in Replay mode, and none fits that question. Try one of these, or connect a model in the top bar to ask anything.',
    }])
  }

  return (
    <>
      <button className={`guide-fab ${open ? 'on' : ''}`} onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls="guide-panel">
        <span className="guide-fab-ic">{open ? '✕' : '?'}</span>{open ? 'Close' : 'Guide'}
      </button>

      {open && (
        <div className="guide" id="guide-panel" role="dialog" aria-label="Guide">
          <div className="guide-h">
            <div>
              <div className="guide-t">Guide</div>
              <div className="guide-s">{mode === 'live' ? 'Live: your model answers, using the project facts' : 'Written answers · connect a model to ask anything'}</div>
            </div>
          </div>

          <div className="guide-body">
            {msgs.length === 0 && (
              <div className="guide-hello">
                <b>Hi. I can explain what this does and walk you through it.</b>
                <span>Pick a question, or type your own.</span>
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`guide-msg ${m.who}`}>
                <div className="guide-bubble">{m.text}</div>
                {m.who === 'bot' && (
                  <div className="guide-meta">
                    <span className="guide-src">{m.src === 'model' ? `Answered by ${m.model || 'your model'}` : 'Written answer'}</span>
                    {m.show && onAction && (
                      <button className="guide-show" onClick={() => { onAction(m.show); if (m.show.run) setOpen(false) }}>
                        {actionLabel || m.label || 'Show me'} →
                      </button>
                    )}
                  </div>
                )}
                {m.who === 'bot' && i === msgs.length - 1 && m.follow && (
                  <div className="guide-chips">{m.follow.map((id) => <button key={id} className="guide-chip" onClick={() => askId(id)}>{BY_ID[id].q}</button>)}</div>
                )}
              </div>
            ))}
            {busy && <div className="guide-msg bot"><div className="guide-bubble guide-typing"><i /><i /><i /></div></div>}
            {msgs.length === 0 && (
              <div className="guide-chips">{STARTERS.map((id) => <button key={id} className="guide-chip" onClick={() => askId(id)}>{BY_ID[id].q}</button>)}</div>
            )}
            <div ref={endRef} />
          </div>

          <form className="guide-in" onSubmit={(e) => { e.preventDefault(); askText(val) }}>
            <input ref={inputRef} value={val} onChange={(e) => setVal(e.target.value)} placeholder="Ask about the project…" maxLength={400} aria-label="Ask the guide" />
            <button type="submit" disabled={busy || !val.trim()} aria-label="Send">→</button>
          </form>
        </div>
      )}
    </>
  )
}

// Two or three sensible next questions after each answer.
const NEXT = {
  what: ['run', 'agents', 'value'], run: ['gate', 'scenarios', 'live'], live: ['run', 'tech'],
  agents: ['gate', 'safety', 'memory'], gate: ['tiers', 'safety', 'value'], value: ['data', 'limits'],
  scenarios: ['run', 'gate'], trust: ['limits', 'data'], data: ['trust', 'limits'], safety: ['gate', 'trust'],
  tiers: ['gate', 'value'], limits: ['trust', 'why'], memory: ['agents', 'trust'], why: ['agents', 'value'], tech: ['live', 'agents'],
}
function nextIds(id) { return NEXT[id] || STARTERS.slice(0, 3) }
