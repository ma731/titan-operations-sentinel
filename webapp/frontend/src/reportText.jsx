import { useState } from 'react'

// Agents open their report with "SUMMARY:" (agents/factory.py, SHARED_FOOTER): two or
// three plain sentences for a plant manager. Show that first and keep the audit detail
// one click away. Reports without a summary (the recorded replay) render as before.
const SUMMARY_RE = /(^|\n)[#*_\s]*summary[*_]*\s*:[*_]*\s*/i

export function splitReport(text) {
  const t = String(text || '').trim()
  const m = t.match(SUMMARY_RE)
  if (!m || m.index > 400) return { summary: null, detail: t }
  const before = t.slice(0, m.index).trim()
  const rest = t.slice(m.index + m[0].length)
  const end = rest.search(/\n\s*\n/)
  const summary = (end === -1 ? rest : rest.slice(0, end)).trim()
  const after = end === -1 ? '' : rest.slice(end).trim()
  if (!summary) return { summary: null, detail: t }
  return { summary, detail: [before, after].filter(Boolean).join('\n\n') }
}

export default function ReportText({ text, className = '' }) {
  const [open, setOpen] = useState(false)
  const { summary, detail } = splitReport(text)
  if (!summary) return <div className={className}>{text}</div>
  return (
    <div className={`${className} rt`}>
      <div className="rt-sum">{summary}</div>
      {detail && (
        <>
          <button type="button" className="rt-more" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {open ? 'Hide details' : 'Show details'}
          </button>
          {open && <div className="rt-detail">{detail}</div>}
        </>
      )}
    </div>
  )
}
