import { useEffect, useRef, useState } from 'react'
import { GUIDE, STARTERS, matchAnswer } from './guideKnowledge.js'
import { parseCommand, stripWake, REPLIES, HELLO } from './titanCommands.js'
import { speak as say, stopSpeaking, canSpeak } from './titanVoice.js'
import './guide.css'

const BY_ID = Object.fromEntries(GUIDE.map((g) => [g.id, g]))
const SR = typeof window !== 'undefined' ? (window.SpeechRecognition || window.webkitSpeechRecognition) : null
const CAN_SPEAK = canSpeak()
const DO_CHIPS = ['Run the Cascade', 'Run the Edge scenario', 'Open the action plan']

// Titan: the console's assistant. It explains the project and runs it on request.
//  - Requests ("run the edge scenario", "approve", "open the audit log") are parsed
//    locally and handed to onCommand, which returns the reply to show.
//  - Questions get a written answer (always works, no key). In live mode the configured
//    model answers via /api/guide, grounded in prompts/guide.md.
//  - Voice is push-to-talk (browser speech recognition, where supported). Replies are
//    read aloud when you asked by voice.
export default function Guide({ mode = 'replay', onCommand, onAction, actionLabel }) {
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState([])
  const [val, setVal] = useState('')
  const [busy, setBusy] = useState(false)
  const [listening, setListening] = useState(false)
  const [muted, setMuted] = useState(false)
  const [micNote, setMicNote] = useState('')
  const endRef = useRef(null)
  const inputRef = useRef(null)
  const recRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }) }, [msgs, busy])
  useEffect(() => { if (open) inputRef.current?.focus() }, [open])
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); recRef.current?.abort?.(); stopSpeaking() }
  }, [])

  const speak = (text, voice) => {
    if (!voice || muted || !CAN_SPEAK || !text) return
    say(text)
  }

  const bot = (m, voice) => { setMsgs((x) => [...x, { who: 'bot', ...m }]); speak(m.text, voice) }
  const written = (item) => ({ text: item.a, src: 'written', show: item.show, label: item.label, follow: nextIds(item.id) })

  const askId = (id) => {
    const item = BY_ID[id]
    setMsgs((m) => [...m, { who: 'me', text: item.q }, { who: 'bot', ...written(item) }])
  }

  const ask = async (raw, voice = false) => {
    const text = raw.trim()
    if (!text || busy) return
    setVal('')
    const history = msgs.slice(-6).map((m) => ({ role: m.who === 'me' ? 'user' : 'assistant', text: m.text }))
    setMsgs((m) => [...m, { who: 'me', text, voice }])

    const cmd = parseCommand(text)
    if (cmd && onCommand) {
      const reply = onCommand(cmd)
      if (reply) { bot({ text: reply, src: 'action', follow: cmd.cmd === 'run' ? ['gate', 'value'] : null }, voice); return }
    }

    const q = stripWake(text) || text
    const hit = matchAnswer(q)
    if (mode === 'live') {
      setBusy(true)
      try {
        const r = await fetch('/api/guide', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, history }) })
        const d = await r.json()
        if (d.ok && d.answer) {
          setBusy(false)
          bot({ text: d.answer, src: 'model', model: d.model, show: hit?.show, label: hit?.label, follow: hit ? nextIds(hit.id) : STARTERS.slice(0, 3) }, voice)
          return
        }
      } catch { /* backend not reachable: use the written answers */ }
      setBusy(false)
    }
    if (hit) { bot(written(hit), voice); return }
    bot({
      src: 'written', follow: STARTERS,
      text: mode === 'live' ? REPLIES.fallbackLive : REPLIES.fallbackReplay,
    }, voice)
  }

  const toggleMic = () => {
    if (!SR) return
    if (listening) { recRef.current?.stop(); return }
    stopSpeaking()
    const rec = new SR()
    rec.lang = 'en-US'; rec.interimResults = true; rec.maxAlternatives = 1
    let finalText = ''
    rec.onresult = (e) => {
      let interim = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i]
        if (r.isFinal) finalText += r[0].transcript; else interim += r[0].transcript
      }
      setVal((finalText + interim).trim())
    }
    rec.onerror = (e) => setMicNote(e.error === 'not-allowed' || e.error === 'service-not-allowed'
      ? 'Microphone is blocked for this site. Allow it in the browser, or type instead.'
      : e.error === 'no-speech' ? 'I did not catch that. Tap the mic and try again.' : 'Voice input stopped. You can type instead.')
    rec.onend = () => { setListening(false); if (finalText.trim()) ask(finalText, true) }
    recRef.current = rec
    setMicNote(''); setListening(true)
    try { rec.start() } catch { setListening(false) }
  }

  return (
    <>
      <button className={`guide-fab ${open ? 'on' : ''}`} onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls="guide-panel">
        <span className="guide-fab-ic">{open ? '✕' : 'T'}</span>{open ? 'Close' : 'Ask Titan'}
      </button>

      {open && (
        <div className="guide" id="guide-panel" role="dialog" aria-label="Titan assistant">
          <div className="guide-h">
            <span className={`guide-orb ${listening ? 'on' : ''} ${busy ? 'busy' : ''}`} aria-hidden="true" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="guide-t">Titan</div>
              <div className="guide-s">{listening ? 'Listening…' : mode === 'live' ? 'Live: your model answers, using the project facts' : 'Explains the project and runs it for you'}</div>
            </div>
            {CAN_SPEAK && SR && (
              <button className="guide-mute" onClick={() => { setMuted((m) => !m); stopSpeaking() }} title={muted ? 'Turn spoken replies on' : 'Turn spoken replies off'} aria-pressed={!muted}>
                {muted ? '🔇' : '🔊'}
              </button>
            )}
          </div>

          <div className="guide-body">
            {msgs.length === 0 && (
              <div className="guide-hello">
                <b>Hi, I'm Titan.</b>
                <span>{HELLO.replace("Hi, I'm Titan. ", '')} {SR ? 'Tap the mic and say "Run the edge scenario", or type.' : 'Try "Run the edge scenario", or pick a question.'}</span>
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`guide-msg ${m.who}`}>
                <div className={`guide-bubble ${m.src === 'action' ? 'act' : ''}`}>{m.voice && <span className="guide-said">🎙 </span>}{m.text}</div>
                {m.who === 'bot' && (
                  <div className="guide-meta">
                    {CAN_SPEAK && <button className="guide-play" onClick={() => say(m.text)} title="Read aloud" aria-label="Read aloud">▶</button>}
                    <span className="guide-src">{m.src === 'model' ? `Answered by ${m.model || 'your model'}` : m.src === 'action' ? 'Done by Titan' : 'Written answer'}</span>
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
              <>
                <div className="guide-chips-l">Ask</div>
                <div className="guide-chips">{STARTERS.map((id) => <button key={id} className="guide-chip" onClick={() => askId(id)}>{BY_ID[id].q}</button>)}</div>
                {onCommand && <>
                  <div className="guide-chips-l">Or tell Titan to</div>
                  <div className="guide-chips">{DO_CHIPS.map((c) => <button key={c} className="guide-chip do" onClick={() => ask(c)}>{c}</button>)}</div>
                </>}
              </>
            )}
            <div ref={endRef} />
          </div>

          {micNote && <div className="guide-note">{micNote}</div>}
          <form className="guide-in" onSubmit={(e) => { e.preventDefault(); ask(val) }}>
            {SR && (
              <button type="button" className={`guide-mic ${listening ? 'on' : ''}`} onClick={toggleMic} aria-pressed={listening} title={listening ? 'Stop listening' : 'Speak to Titan'}>
                <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-2.08A7 7 0 0 0 19 12h-2Z" /></svg>
              </button>
            )}
            <input ref={inputRef} value={val} onChange={(e) => setVal(e.target.value)} placeholder={listening ? 'Listening…' : 'Ask Titan, or tell it what to do…'} maxLength={400} aria-label="Message Titan" />
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
