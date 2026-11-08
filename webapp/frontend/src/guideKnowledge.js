// Written answers for the Guide. They work with no model and no key, so the public
// replay demo can explain itself. Keep numbers in sync with the README and the
// scorecard; prompts/guide.md carries the same facts for the live model.
//
// show: what the "Show me" button does. { nav: '<page>' } opens a console page,
// { run: true } starts the selected scenario.

import { AGENTS } from './agentsMeta.js'

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
    k: ['agent', 'agents', 'orchestrator', 'supervisor', 'team', 'specialists'],
    a: 'Reliability predicts the failure and how long the machine has left. Supply chain finds the parts and prices the options. Production moves jobs to other machines. Quality checks that the backup machine is safe to use. Compliance checks every action against safety limits and can stop the whole plan. The orchestrator decides which agent goes next.',
    show: { nav: 'chat' }, label: 'Read their conversation',
  },
  {
    id: 'gate', q: 'Why did it stop and ask me?',
    k: ['stop', 'stopped', 'ask', 'approve', 'approval', 'gate', 'human', 'person', '500', 'pause', 'wait', 'reject', 'should', 'decide'],
    a: 'The agents may spend up to €500 on their own. The rush order for the bearing costs €3,200, so the run pauses until a person approves or rejects it. The limit is written in code, not in a prompt, so a model cannot talk its way past it. In a live run, if nobody decides within five minutes, it counts as a rejection and the log says no person decided.',
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
    a: 'Every action is checked against safety and machine limits, and the compliance agent can stop the whole plan. Anything that touches a safety system is flagged for a safety officer instead of being done automatically. The agents call tools that fetch, calculate and draft, but the rules that matter are enforced in code.',
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
  {
    id: 'patterns', q: 'What agent patterns does it use?',
    k: ['pattern', 'patterns', 'architecture', 'design', 'anthropic', 'evaluator', 'parallel', 'orchestrator-workers', 'workflow'],
    a: 'It follows Anthropic\'s Building Effective Agents. Routing: a code-only gate decides which alerts wake the agents, then the orchestrator picks who goes next. Orchestrator-workers: one orchestrator, five specialists with their own tools and document search. Evaluator-optimizer: a check in code scores the final plan against the rules and sends it back once if it fails. Parallelisation: supply chain and production can run side by side, off by default. Guarantees stay in code, judgement in the model.',
  },
  {
    id: 'mcp', q: 'What is MCP, and does Titan use it?',
    k: ['mcp', 'protocol', 'connector', 'integration', 'integrate', 'claude desktop', 'copilot'],
    a: 'MCP, the Model Context Protocol, is a standard way to plug tools into any AI agent: build the connector once and every agent can use it. Titan runs an MCP server with its read-only tools, plus one action that can only ever draft a work order. Claude Desktop or a Copilot can use them, and the €500 limit and the safety gate still apply, because those rules live in code. Titan\'s own agents still call their tools directly.',
  },
  {
    id: 'a2a', q: 'Can other agents talk to Titan?',
    k: ['a2a', 'agent to agent', 'other agents', 'delegate', 'agent card', 'interoperab'],
    a: 'Yes, two ways. Through MCP, another agent uses Titan\'s tools. Through A2A, the agent to agent protocol, another vendor\'s agent hands Titan a whole task: it finds Titan\'s agent card and asks, say, what a supplier outage puts at risk. Titan can triage a plant, list what a machine depends on, size a supplier risk, or screen an action for safety. Nothing that comes in this way can spend or approve.',
  },
  {
    id: 'graph', q: 'What is the knowledge graph?',
    k: ['graph', 'knowledge', 'intelligence layer', 'dependencies', 'tier 2', 'tier-2', 'upstream'],
    a: 'It is the intelligence layer: one connected model of plants, machines, parts, stock, suppliers and their own suppliers, technicians and robot cells. It answers questions no single file can. For example, the steel mill Ovako has a furnace outage: through Schaeffler that reaches CNC-07, about €180,000 of production a day, and the hydraulic seal set has no second supplier. Every answer shows the path it followed.',
  },
  {
    id: 'redteam', q: 'Can someone trick the agents?',
    k: ['trick', 'inject', 'injection', 'attack', 'hack', 'red team', 'security', 'jailbreak', 'manipulat'],
    a: 'They might trick the model, so the model does not hold the rules: the safety gate, the €500 limit and the approval step are code. A red team throws 19 attacks at those rules, like disguised wording, fake approvals and orders split to stay under the limit. All 19 are stopped now; the first run broke nine, and those were fixed. Two paraphrases the keyword rules still miss are listed openly, and a person still approves every work order.',
  },
  {
    id: 'routing', q: 'Does it use the most expensive model for everything?',
    k: ['expensive', 'cost', 'cheap', 'token', 'tokens', 'routing', 'small model', 'model choice'],
    a: 'It does not have to. With routing on, routine steps, like picking the next agent from a short list or summarising production and quality checks, run on a small model. Anything about money, safety or the final plan stays on the main model. Cost is tracked per agent, by the model it used. The saving has not been measured live yet: that needs two runs with an API key.',
  },
  {
    id: 'aiact', q: 'Is this compliant with the EU AI Act?',
    k: ['act', 'regulation', 'regulated', 'legal', 'law', 'compliant', 'gdpr', 'eu', 'governance', 'responsible'],
    a: 'My reading, not legal advice: as decision support that recommends maintenance actions, Titan most likely falls outside the AI Act high-risk list. That would change if it directly controlled machine safety functions, or allocated work to people based on their behaviour. It is built as if it were high-risk anyway: a person must approve spend over €500, safety-system actions are flagged for a safety officer, every step of a live run is logged, I tell you I am an AI assistant, and each prediction says where it came from.',
    show: { nav: 'aiact' }, label: 'Open the AI Act page',
  },
]

// One answer per agent, built from the same text as the agent pages.
for (const a of AGENTS) {
  GUIDE.push({
    id: `ag_${a.id}`, q: `What does the ${a.name.toLowerCase()} agent do?`, k: [],
    a: `${a.what} ${a.limit}`,
    show: { nav: a.id }, label: `Open the ${a.name.toLowerCase()} page`,
  })
}

export const STARTERS = ['what', 'run', 'gate', 'value', 'data']

const norm = (s) => s.toLowerCase().replace(/[^a-z0-9€ ]/g, ' ').split(/\s+/).filter(Boolean)

// Everyday phrasings people actually use, checked before the keywords.
const PHRASES = [
  [/\bmcp\b|model context protocol|claude desktop|\bcopilot\b/, 'mcp'],
  [/\ba2a\b|agent[- ]to[- ]agent|agent card|other agents|another (vendor|company)'?s? agent/, 'a2a'],
  [/knowledge graph|intelligence layer|\bgraph\b|tier[- ]?2|upstream (risk|supplier)/, 'graph'],
  [/prompt injection|red[- ]?team|\b(trick|fool|hack|jailbreak|manipulat\w*)\b|\battack/, 'redteam'],
  [/model routing|small(er)? model|cheaper model|(most )?expensive model|tokenomics|token cost/, 'routing'],
  [/\b(agent |design )?patterns?\b|building effective agents|evaluator|optimi[sz]er|parallel|orchestrator[- ]workers?|how (is|was) it (built|designed)|architecture/, 'patterns'],
  [/\bai act\b|\beu (ai )?(act|law|regulation)|\b(legal|lawful|regulat\w*|gdpr)\b|compliant with|high[- ]risk/, 'aiact'],
  [/how much|what('?s| is) it worth|does it (pay|save)|business case|return on/, 'value'],
  [/\breliability\b/, 'ag_reliability'],
  [/\bsupply( chain)?\b|\bparts?\b|\bsupplier/, 'ag_supply_chain'],
  [/\bproduction\b|\breroute|\bshift/, 'ag_production'],
  [/(?<!data )\bquality\b|\bdefect/, 'ag_quality'],
  [/\bcompliance\b/, 'ag_compliance_safety'],
  [/what('?s| is| are)? (going on|happening|this|that|all this)|what am i (looking at|seeing)|what is (this|it|here)|what('?s| is) (the )?(idea|point)|tell me (about|more)|(give me|quick|short) (a )?(tour|overview|summary|intro)|show me around|explain (this|it|everything)|in (a )?(nutshell|few words)|^(and )?(so|ok so)?\s*what now/, 'what'],
  [/where (do|should) i (start|begin)|how (do|can|should) i (use|start|try|begin|run)|get(ting)? started|what (do|should|can) i (do|click|press)|first step/, 'run'],
  [/is (it|this) (real|live|recorded)|is this a (recording|video|replay)|are (the )?agents (real|live)|use my (own )?(key|model)/, 'live'],
  [/who (does|do) what|what do (the|these|those) agents|which agents/, 'agents'],
  [/why (did|does) it (stop|pause|wait|ask)|what('?s| is) the (gate|limit|decision rule|rule)|who (approves|decides)|(nobody|no one) (approves|decides|answers)/, 'gate'],
  [/can (i|you) trust|does it (work|actually work)|how (good|accurate|reliable)/, 'trust'],
  [/what('?s| is) (missing|wrong|weak)|what (can'?t|doesn'?t) it do|limitations?/, 'limits'],
]

// The project words a vague question tends to contain. If one is there and nothing
// else matched, the overview is the most useful answer.
const ABOUT_PROJECT = /\b(this|here|it|project|demo|system|console|thing|titan|sentinel|page|app)\b/

// Best written answer for free text, or null. Phrases first, then keyword overlap.
// It picks from fifteen fixed answers, so it can never invent anything.
export function matchAnswer(text) {
  const t = text.toLowerCase().replace(/[’`]/g, "'")
  for (const [re, id] of PHRASES) if (re.test(t)) return GUIDE.find((g) => g.id === id)
  const words = new Set(norm(t))
  let best = null, score = 0
  for (const item of GUIDE) {
    let s = 0
    for (const k of item.k) if (words.has(k)) s += 2
    for (const w of norm(item.q)) if (w.length > 3 && words.has(w)) s += 1
    if (s > score) { score = s; best = item }
  }
  if (score >= 2) return best
  return ABOUT_PROJECT.test(t) ? GUIDE.find((g) => g.id === 'what') : null
}
