// Codes like CNC-07-LEI mean nothing to a visitor, so the console shows "Machine 7"
// and keeps the code next to its first mention. Display only: the audit log and the
// exported report keep the agents' exact words.
const CODE_RE = /\b(?:(CNC|ROB)-(\d{2})(?:-[A-Z]{3})?|(RUL|OEM))\b/g
const TERMS = { RUL: 'remaining life', OEM: 'machine-maker' }

export function machineLabel(code) {
  const m = /^(CNC|ROB)-(\d+)/.exec(code || '')
  return m ? `${m[1] === 'ROB' ? 'Robot cell' : 'Machine'} ${Number(m[2])}` : code
}

export default function Plain({ text }) {
  const s = String(text ?? '')
  const seen = new Set()
  const out = []
  let last = 0
  for (const m of s.matchAll(CODE_RE)) {
    out.push(s.slice(last, m.index))
    last = m.index + m[0].length
    if (m[3]) {
      const t = TERMS[m[3]]
      const starts = m.index === 0 || /[.!?]\s+$/.test(s.slice(0, m.index))
      out.push(<span key={m.index} title={m[3]}>{starts ? t[0].toUpperCase() + t.slice(1) : t}</span>)
      continue
    }
    const key = m[1] + m[2]
    const first = !seen.has(key)
    seen.add(key)
    out.push(
      <span key={m.index} title={m[0]}>
        {machineLabel(m[0])}{first && <> <span className="code-tag">{m[0]}</span></>}
      </span>,
    )
  }
  out.push(s.slice(last))
  return <>{out}</>
}
