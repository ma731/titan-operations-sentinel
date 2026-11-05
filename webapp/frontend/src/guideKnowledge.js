// Written answers for the Guide. They work with no model and no key, so the public
// replay demo can explain itself. Keep numbers in sync with the README and the
// scorecard; prompts/guide.md carries the same facts for the live model.
//
// show: what the "Show me" button does. { nav: '<page>' } opens a console page,
// { run: true } starts the selected scenario.

export const GUIDE = [
  {
    id: 'what', q: 'What does this do?',
    k: ['purpose', 'explain', 'overview', 'project'],
    a: 'It turns one machine alert into one costed plan. A sensor on CNC-07 shows a spindle bearing about to fail. Five specialist agents each check one area (reliability, supply chain, production, quality, safety), an orchestrator decides who goes next, and the result is a plan the plant manager can act on. Anything that costs more than €500 waits for a person to approve it.',
    show: { nav: 'dashboard' }, label: 'Open the overview',
  },
  {
    id: 'run', q: 'How do I run the demo?',
    k: ['run', 'start', 'demo', 'play', 'begin', 'try'],
    a: 'Press the orange Run button on the Overview page. The four steps above the graph light up as the run moves: alert, agents, human gate, plan. When it stops at the €500 gate, approve or reject the spend. You can also press Present in the top bar for a hands-free run.',
    show: { run: true }, label: 'Run it now',
  },
  {
    id: 'live', q: 'Is this live or a recording?',
    k: ['live', 'recording', 'recorded', 'replay', 'key', 'api', 'model', 'connect', 'gemini', 'groq', 'provider'],
    a: 'By default it is Replay: a recorded run played back in your browser, with no key and no cost. For a live run, open the model menu in the top bar, pick a provider (Gemini and Groq are free), paste your API key and press Connect. Live needs the backend running on your machine (docker compose up).',
  },
  {
    id: 'agents', q: 'What does each agent do?',
    k: ['agent', 'agents', 'reliability', 'supply', 'production', 'quality', 'compliance', 'orchestrator', 'supervisor'],
    a: 'Reliability predicts the failure and how long the machine has left. Supply chain finds the parts and prices the options. Production moves jobs to other machines. Quality checks that the backup machine is safe to use. Compliance checks every action against safety limits and can stop the whole plan. The orchestrator decides which agent goes next.',
    show: { nav: 'chat' }, label: 'Read their conversation',
  },
  {
    id: 'gate', q: 'Why did it stop and ask me?',
    k: ['stop', 'stopped', 'ask', 'approve', 'approval', 'gate', 'human', 'person', '500', 'pause', 'wait', 'reject', 'should', 'decide'],
    a: 'The agents may spend up to €500 on their own. The rush order for the bearing costs €3,200, so the run pauses until a person approves or rejects it. The limit is written in code, not in a prompt, so a model cannot talk its way past it.',
  },
  {
    id: 'value', q: 'Is it worth the money?',
    k: ['worth', 'value', 'money', 'cost', 'roi', 'save', 'saving', 'benefit', 'business', 'euro', 'price', '3200', '870'],
    a: 'Doing nothing means waiting 192 hours for the standard delivery. Ordering now avoids at least 116 hours of downtime for a €3,200 rush order. At full production value that is up to €870k, but treat that as an upper bound: it is revenue, not margin, and some output is recovered by rerouting. A €420 transfer avoids the same hours, so the extra €2,780 only buys certainty. This is one purchase decision, not the return on the whole system, and it leaves out build and run cost.',
    show: { nav: 'cost' }, label: 'See cost and value',
  },
  {
    id: 'scenarios', q: 'What are the three scenarios?',
    k: ['scenario', 'scenarios', 'cascade', 'edge', 'escalation', 'three', 'paths', 'different'],
    a: 'Cascade: the full team runs and the €3,200 spend waits for a person. Edge: the main supplier is disrupted, so the agents find a cross-plant transfer from Munich that costs under €500 and needs no approval. Escalation: the sensor data drops out, so the system refuses to guess and hands the case to a person.',
    show: { nav: 'scenarios' }, label: 'Pick a scenario',
  },
  {
    id: 'trust', q: 'How do I know it works?',
    k: ['work', 'works', 'trust', 'test', 'tests', 'tested', 'eval', 'evaluation', 'accurate', 'accuracy', 'proof', 'reliable'],
    a: 'The rules enforced in code are tested like software. 208 offline checks across 34 labelled scenarios pass, the safety gate stopped every case it should and none it should not, and over 300 tests run on every change. What the model itself decides is not measured yet: the live test suite has not been run. A findings register lists what is still wrong.',
    show: { nav: 'audit' }, label: 'Open the audit log',
  },
  {
    id: 'data', q: 'Is the data real?',
    k: ['data', 'real', 'fake', 'simulated', 'nasa', 'dataset', 'rul', 'predict', 'prediction', 'model'],
    a: 'Mostly simulated, and labelled that way. The remaining-life model is trained on NASA engine data and tested on 707 engines it never saw (typical error, RMSE, of 17 cycles, against 41.8 for a simple baseline). For the CNC machines there is no public failure data, so those predictions come from declared limits, and every prediction says which kind it is.',
  },
  {
    id: 'safety', q: 'Can it do something dangerous?',
    k: ['danger', 'dangerous', 'safe', 'safety', 'halt', 'risk', 'harm', 'wrong', 'mistake', 'osha'],
    a: 'Every action is checked against safety and machine limits, and the compliance agent can stop the whole plan. Anything that touches a safety system goes to a safety officer. The agents call tools that fetch, calculate and draft, but the rules that matter are enforced in code.',
  },
  {
    id: 'tiers', q: 'What do AUTO, APPROVE and MONITOR mean?',
    k: ['auto', 'approve', 'monitor', 'escalate', 'tier', 'tiers', 'plan', 'action', 'lines'],
    a: 'AUTO: allowed without asking, like slowing the machine or moving jobs. In this demo these are recommendations, not commands sent to a real machine. APPROVE: a person must sign off, like any spend over €500. MONITOR: keep watching and trigger again if things get worse. ESCALATE: hand it to a safety officer.',
    show: { nav: 'plan' }, label: 'Open the action plan',
  },
  {
    id: 'limits', q: 'What does it not do yet?',
    k: ['limit', 'limits', 'weak', 'weakness', 'missing', 'next', 'improve', 'future', 'v2'],
    a: 'Document search finds the right page 100% of the time for direct questions but only 41.7% when the question is reworded. Live cost and speed per run are not benchmarked yet. Slack approval is built but untested with a real workspace. And there is no real failure data for the CNC machines.',
  },
  {
    id: 'memory', q: 'Does it learn from past incidents?',
    k: ['learn', 'learning', 'memory', 'past', 'history', 'similar', 'incident', 'precedent'],
    a: 'It remembers, but it does not learn yet. The reliability agent looks up similar past incidents: here INC-0288, a 93% match that failed at 58 hours, where the same rush order worked. Each finished live run is saved so the next one can use it. Learning from outcomes is designed but not built.',
    show: { nav: 'learning' }, label: 'Open learning',
  },
  {
    id: 'why', q: 'Why agents and not a dashboard?',
    k: ['dashboard', 'rules', 'automation', 'rpa', 'instead', 'agentic'],
    a: 'A dashboard shows the data and waits. A rules engine follows fixed steps. The hard part here is that maintenance, supply, production, quality and safety have to agree within hours, and each only sees its own part. The agents read each other\'s findings and adapt, for example switching to a different machine when the first choice has a shift conflict.',
  },
  {
    id: 'tech', q: 'What is it built with?',
    k: ['built', 'stack', 'tech', 'langgraph', 'react', 'python', 'fastapi', 'framework', 'code'],
    a: 'Python and LangGraph for the agents, FastAPI for the backend, React for this console. Each specialist is a ReAct agent that picks its own tools. It works with Gemini, Groq, OpenAI, Anthropic, Azure, Mistral or a local Ollama model.',
  },
]

export const STARTERS = ['what', 'run', 'gate', 'value', 'data']

const norm = (s) => s.toLowerCase().replace(/[^a-z0-9€ ]/g, ' ').split(/\s+/).filter(Boolean)

// Best written answer for free text, or null. Simple keyword overlap is enough for a
// fixed set of fifteen answers, and it can never invent anything.
export function matchAnswer(text) {
  const words = new Set(norm(text))
  let best = null, score = 0
  for (const item of GUIDE) {
    let s = 0
    for (const k of item.k) if (words.has(k)) s += 2
    for (const w of norm(item.q)) if (w.length > 3 && words.has(w)) s += 1
    if (s > score) { score = s; best = item }
  }
  return score >= 2 ? best : null
}
