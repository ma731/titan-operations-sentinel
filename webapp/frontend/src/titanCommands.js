// Turns a typed or spoken request into a console action. Only short, direct orders
// become actions ("run the edge scenario", "approve"). Anything phrased as a question
// ("should I approve?", "can it run without a key?") goes to the Q&A instead.

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
  [/\b(ai act|eu ai|regulation)\b/, 'aiact', 'the EU AI Act page'],
  [/\b(compliance|safety)\b/, 'compliance_safety', 'the compliance agent'],
  [/\b(overview|home|dashboard|start page)\b/, 'dashboard', 'the overview'],
]

// The spend gate only moves on a short, unambiguous order.
const APPROVE = /^(yes[,.! ]*)?(i )?(approve|approve it|approve (the|this) (spend|order|rush order|purchase|expedite)|approved|go ahead)[.! ]*$/
const REJECT = /^(no[,.! ]*)?(i )?(reject|reject it|reject (the|this) (spend|order|rush order|purchase|expedite)|rejected|decline|decline it)[.! ]*$/
const PRESENT = /^(present|present it|present the demo|start (the )?presentation|presentation mode|hands[- ]?free( mode)?)[.! ]*$/
const STOP = /^(stop|cancel|abort)( the run| it| now| running)?[.! ]*$/
const RUN = /^(run|start|play|launch|simulate|trigger|replay)\b/
const NAV = /^(open|show( me)?|go to|take me to|see|view|display)\b/
export const CONFIRM = /^(yes|yes please|yep|yeah|confirm|confirmed|do it|yes,? (approve|reject|do it))[.! ]*$/

// "can you run...", "please open..." are orders; other can/should/would openings are questions.
const POLITE = /^((can|could|would|will) you (please )?|please |let'?s |i want to |i'd like to )/
const QUESTION = /(\?$)|^(why|what|how|is|are|does|do|did|who|when|where|which|explain|tell me|should|shall|will|would|could|can|may|might|if|i|i'm|im)\b/

export const HELLO = "Hi, I'm Titan, an AI assistant. I can explain what this project does, or run it for you."

export const SCENARIO_NAMES = { happy: 'Cascade', edge: 'Edge', escalation: 'Escalation' }

// Strip "hey titan," / "titan" so the request reads the same with or without it.
export const stripWake = (t) => t.replace(/^\s*(hey|hi|hello|hola|ok|okay)?[\s,]*titan[\s,.!:?]*/i, '').trim()

// Greetings and small talk get a short, friendly reply instead of a fact sheet.
export function smallTalk(raw) {
  const full = raw.toLowerCase().trim()
  const t = stripWake(raw).toLowerCase().replace(/[!.?, ]+$/g, '').trim()
  if (!t || /^(hi|hello|hey|hola|hiya|yo|good (morning|afternoon|evening)|hey there|hi there)( titan)?$/.test(t)) return 'greet'
  if (/^(thanks|thank you|thanks a lot|cheers|great|perfect|nice|cool|awesome|ok|okay|got it)( titan)?$/.test(t)) return 'thanks'
  if (/^(who|what) are you\b|^what can you do\b|^help$|^what can i (ask|say)\b/.test(t) || /^(who|what) is titan\b/.test(full)) return 'whoami'
  return null
}

// Requests that only Titan itself handles (no console action needed).
export function parseLocal(raw) {
  const t = stripWake(raw).toLowerCase().replace(/[!.?, ]+$/g, '').trim()
  if (/^(repeat( that)?|say (that|it) again|again|pardon|come again|sorry|what)$/.test(t)) return 'repeat'
  if (/^(stop talking|be quiet|quiet|shush|silence|enough|shut up)$/.test(t)) return 'quiet'
  if (/\b(go live|live mode|switch to live|use (my|a|your) (own )?(key|model|api)|connect (a |my |your )?(model|key|api)|add (a |my )?key|api key)\b/.test(t)) return 'howLive'
  return null
}

// Questions about the current run or page. The console answers these from its state;
// when there is nothing to report, they fall through to the written answers.
export function parseContext(raw) {
  const t = stripWake(raw).toLowerCase().replace(/[!.?, ]+$/g, '').trim()
  const ag = t.match(/what did (the )?(reliability|supply( chain)?|production|quality|compliance)( agent)? (find|say|conclude|decide|do|recommend|report)/)
  if (ag) {
    const id = { reliability: 'reliability', supply: 'supply_chain', 'supply chain': 'supply_chain', production: 'production', quality: 'quality', compliance: 'compliance_safety' }[ag[2]]
    return { ctx: 'finding', agent: id }
  }
  const m = t.match(/\b(cnc)[- ]?0?(\d)\b|\brob(?:ot)?[- ]?(?:cell[- ]?)?0?(\d)\b/)
  if (m) return { ctx: 'machine', id: m[1] ? `CNC-0${m[2]}-LEI` : `ROB-0${m[3]}-LEI` }
  // "summarize the project" or "status of the project" want the overview, not this run.
  if (/\b(project|demo|system|idea)\b/.test(t)) return null
  if (/\b(status|where are we|progress)\b|what('?s| is) (happening|going on) (now|right now)|^is it (done|finished|over|still running)|what('?s| is) it doing( now)?/.test(t)) return { ctx: 'status' }
  if (/\bresults?\b|what did (they|it|the agents|the team) (decide|recommend|conclude|come up with)|^what('?s| is) the (plan|decision|recommendation)$/.test(t)) return { ctx: 'result' }
  if (/\b(this|the current) (page|screen|view|tab)\b|what am i (looking at|seeing)|where am i/.test(t)) return { ctx: 'page' }
  return null
}

export function parseCommand(raw) {
  let t = stripWake(raw).toLowerCase().trim()
  if (!t) return null
  if (/^(go )?(back|home)( to (the )?(overview|start))?[.! ]*$/.test(t)) return { cmd: 'nav', nav: 'dashboard', name: 'the overview' }
  if (POLITE.test(t)) t = t.replace(POLITE, '').replace(/\?+$/, '').trim()
  else if (QUESTION.test(t)) return null

  if (APPROVE.test(t)) return { cmd: 'approve' }
  if (REJECT.test(t)) return { cmd: 'reject' }
  if (STOP.test(t)) return { cmd: 'stop' }
  if (PRESENT.test(t)) return { cmd: 'present' }

  if (RUN.test(t)) {
    const scenario = /\b(edge|supplier|disrupt|cross[- ]?plant|munich|transfer)/.test(t) ? 'edge'
      : /\b(escalat|dropout|drop out|sensor (is )?(down|out|lost)|bad data|no data)/.test(t) ? 'escalation'
      : /\b(cascade|friday|bearing|main|default|normal|happy)\b/.test(t) ? 'happy'
      : null
    return { cmd: 'run', scenario }
  }

  if (NAV.test(t)) {
    for (const [re, nav, name] of PAGES) if (re.test(t)) return { cmd: 'nav', nav, name }
  }
  return null
}

// Every sentence Titan says for an action lives here, so scripts/build_titan_voice.py
// can pre-record exactly these lines with a natural neural voice.
const LABEL = SCENARIO_NAMES
export const REPLIES = {
  greet: "Hi! I'm Titan. I can give you a quick tour, run the demo for you, or answer your questions. Where would you like to start?",
  thanks: 'You are welcome. Ask me anything else, or say "run the demo".',
  whoami: 'I am Titan, an AI assistant for this console. I can run a scenario, approve or reject the spend, stop a run, open any page, tell you the status or the result, explain the page you are on or any agent, and answer questions about the project. Try "run the cascade".',
  howLive: 'Open the model menu in the top bar, where it says Replay. Pick a provider, paste your API key there and press Connect. Never paste a key into this chat: I do not need it, and I will not ask for it.',
  quiet: 'Okay, I will stop talking.',
  nothingToRepeat: 'There is nothing to repeat yet. Ask me something first.',
  gateReached: 'The agents want to spend €3,200 on a rush order, which is over their €500 limit. Approve or reject?',
  noResult: 'There is no result yet. Say "run the cascade" to start a run.',
  noFinding: 'That agent has not reported yet in this run. Say "run the cascade" first.',
  notStarted: 'Nothing has run yet. Say "run the cascade" and I will tell you how it goes.',
  runBusy: 'A run is already going. Say "stop" first if you want to start another.',
  run: (sc) => `Running the ${LABEL[sc]} scenario. Watch the four steps above the graph.${sc === 'happy' ? ' It will stop at the €500 gate: tell me "approve" or "reject".' : ''}`,
  noApproval: 'Nothing is waiting for approval right now.',
  approved: 'Approved. The €3,200 rush order goes ahead and the agents finish the plan.',
  rejected: 'Rejected. The agents will escalate with the costed trade-off instead.',
  confirmApprove: 'You said approve the €3,200 rush order. Say yes to confirm, or press Approve.',
  confirmReject: 'You said reject the €3,200 rush order. Say yes to confirm, or press Reject.',
  cancelled: 'Okay, I did nothing. The decision is still waiting for you.',
  notRunning: 'Nothing is running.',
  stopped: 'Stopped. What happened so far stays on screen.',
  presentBusy: 'A run is already going.',
  presentLive: 'Presenting hands-free approves the gate automatically, so I only do that in Replay. Say "run the cascade" and decide yourself.',
  present: (sc) => `Presenting the ${LABEL[sc]} scenario hands-free. I will approve the gate automatically.`,
  open: (name) => `Opening ${name}.`,
  showcaseOpen: 'Opening the console. Press Run there, or ask me again from inside.',
  showcaseFirst: 'Open the console first. That is where runs and approvals happen.',
  fallbackLive: 'The model could not answer just now, and I have no written answer for that. Try one of these:',
  fallbackReplay: 'I am not sure about that one, but I know this project well. Try one of these, or ask me to run a scenario. With a model connected in the top bar, I can answer anything.',
}
// "What is this page?" for every page except the overview (which has its own answer).
export const PAGE_HELP = {
  chat: 'This is the agent conversation: each agent\'s report in order, and the questions they ask each other. You can also describe a situation here to start a run.',
  plan: 'This is the action plan. Each line has a tier: AUTO is allowed without asking, APPROVE needs a person, MONITOR means keep watching, ESCALATE goes to a safety officer.',
  cost: 'This page shows what a run costs in tokens and money, and what the decision is worth against doing nothing.',
  scenarios: 'These are the three scenarios: Cascade, where the spend waits for a person; Edge, where a cheaper transfer needs no approval; and Escalation, where bad data makes the system hand over to a person.',
  audit: 'This is the audit log: every step of the last run in order, including every human decision and how it was made. It is the record you would show an auditor.',
  report: 'This is the run history: every finished run saved in this browser, with what each agent concluded. You can export a report from here.',
  learning: 'This page shows how Titan uses past incidents. Recalling similar cases runs today; using decisions and outcomes to improve is designed, not built yet.',
  aiact: 'This page maps Titan to the EU AI Act: the likely risk class, what would change it, and where oversight, logging and transparency live in the console. It is a reading, not legal advice.',
  reliability: 'This is the reliability agent\'s page: what it is for, the tools it can call, the rule it cannot break, and what it found in this run.',
  supply_chain: 'This is the supply chain agent\'s page: what it is for, the tools it can call, the rule it cannot break, and what it found in this run.',
  production: 'This is the production agent\'s page: what it is for, the tools it can call, the rule it cannot break, and what it found in this run.',
  quality: 'This is the quality agent\'s page: what it is for, the tools it can call, the rule it cannot break, and what it found in this run.',
  compliance_safety: 'This is the compliance agent\'s page: what it is for, the tools it can call, the rule it cannot break, and what it found in this run.',
}

export const PAGE_NAMES = PAGES.map((p) => p[2])

export function allReplyTexts() {
  const out = []
  for (const v of Object.values(REPLIES)) {
    if (typeof v === 'string') out.push(v)
  }
  for (const sc of Object.keys(LABEL)) out.push(REPLIES.run(sc), REPLIES.present(sc))
  for (const n of PAGE_NAMES) out.push(REPLIES.open(n))
  out.push(...Object.values(PAGE_HELP))
  return out
}
