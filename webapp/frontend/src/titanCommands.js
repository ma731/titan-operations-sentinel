// Turns a typed or spoken request into a console action. Questions ("why did it
// stop?") are left to the Q&A; only requests ("run the edge scenario") become actions.

const PAGES = [
  [/\b(conversation|chat|transcript|talk)/, 'chat', 'the agent conversation'],
  [/\b(action )?plan\b/, 'plan', 'the action plan'],
  [/\b(cost|value|money|roi)\b/, 'cost', 'cost and value'],
  [/\bscenarios?\b/, 'scenarios', 'the scenarios'],
  [/\b(audit|log)\b/, 'audit', 'the audit log'],
  [/\b(run )?history\b/, 'report', 'run history'],
  [/\b(learning|memory|past incidents?)\b/, 'learning', 'learning'],
  [/\breliability\b/, 'reliability', 'the reliability agent'],
  [/\bsupply( chain)?\b/, 'supply_chain', 'the supply chain agent'],
  [/\bproduction\b/, 'production', 'the production agent'],
  [/\bquality\b/, 'quality', 'the quality agent'],
  [/\b(compliance|safety)\b/, 'compliance_safety', 'the compliance agent'],
  [/\b(overview|home|dashboard|start page)\b/, 'dashboard', 'the overview'],
]

const QUESTION = /^(why|what|how|is|are|does|do|who|when|where|which|explain|tell me about)\b/

export const HELLO = "Hi, I'm Titan. I can explain what this project does, or run it for you."

export const SCENARIO_NAMES = { happy: 'Cascade', edge: 'Edge', escalation: 'Escalation' }

// Strip "hey titan," / "titan" so the request reads the same with or without it.
export const stripWake = (t) => t.replace(/^\s*(hey|hi|ok|okay)?[\s,]*titan[\s,.!:]*/i, '').trim()

export function parseCommand(raw) {
  const t = stripWake(raw).toLowerCase()
  if (!t || QUESTION.test(t)) return null

  if (/\b(approve|accept|authori[sz]e|go ahead|sign off)\b/.test(t)) return { cmd: 'approve' }
  if (/\b(reject|decline|deny|refuse)\b/.test(t)) return { cmd: 'reject' }
  if (/\b(stop|cancel|abort)\b/.test(t)) return { cmd: 'stop' }
  if (/\b(present|hands[- ]?free|presentation)\b/.test(t)) return { cmd: 'present' }

  if (/\b(run|start|play|launch|simulate|trigger|demo)\b/.test(t)) {
    const scenario = /\b(edge|supplier|disrupt|cross[- ]?plant|munich|transfer)/.test(t) ? 'edge'
      : /\b(escalat|dropout|drop out|sensor (is )?(down|out|lost)|bad data|no data)/.test(t) ? 'escalation'
      : /\b(cascade|friday|bearing|main|default|normal|happy)\b/.test(t) ? 'happy'
      : null
    return { cmd: 'run', scenario }
  }

  if (/\b(open|show|go to|take me|see|view|display)\b/.test(t)) {
    for (const [re, nav, name] of PAGES) if (re.test(t)) return { cmd: 'nav', nav, name }
  }
  return null
}

// Every sentence Titan says for an action lives here, so scripts/build_titan_voice.py
// can pre-record exactly these lines with a natural neural voice.
const LABEL = SCENARIO_NAMES
export const REPLIES = {
  runBusy: 'A run is already going. Say "stop" first if you want to start another.',
  run: (sc) => `Running the ${LABEL[sc]} scenario. Watch the four steps above the graph.${sc === 'happy' ? ' It will stop at the €500 gate: tell me "approve" or "reject".' : ''}`,
  noApproval: 'Nothing is waiting for approval right now.',
  approved: 'Approved. The €3,200 rush order goes ahead and the agents finish the plan.',
  rejected: 'Rejected. The agents will escalate with the costed trade-off instead.',
  notRunning: 'Nothing is running.',
  stopped: 'Stopped. What happened so far stays on screen.',
  presentBusy: 'A run is already going.',
  present: (sc) => `Presenting the ${LABEL[sc]} scenario hands-free. I will approve the gate automatically.`,
  open: (name) => `Opening ${name}.`,
  showcaseOpen: 'Opening the console. Press Run there, or ask me again from inside.',
  showcaseFirst: 'Open the console first. That is where runs and approvals happen.',
  fallbackLive: 'The model could not answer just now, and I have no written answer for that. Try one of these:',
  fallbackReplay: 'I only have written answers in Replay mode, and none fits that. Try one of these, ask me to run a scenario, or connect a model in the top bar to ask anything.',
}
export const PAGE_NAMES = PAGES.map((p) => p[2])

export function allReplyTexts() {
  const out = []
  for (const v of Object.values(REPLIES)) {
    if (typeof v === 'string') out.push(v)
  }
  for (const sc of Object.keys(LABEL)) out.push(REPLIES.run(sc), REPLIES.present(sc))
  for (const n of PAGE_NAMES) out.push(REPLIES.open(n))
  return out
}
