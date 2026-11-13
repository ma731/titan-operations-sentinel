# Titan Operations Sentinel

**An AI team for a factory. When a machine starts to fail, six AI agents work out what is
wrong, what it costs, how to keep production going and whether the fix is safe, then ask a
manager to approve anything that spends real money.**

[![tests](https://github.com/ma731/titan-operations-sentinel/actions/workflows/tests.yml/badge.svg)](https://github.com/ma731/titan-operations-sentinel/actions/workflows/tests.yml)
[![nightly evaluation](https://github.com/ma731/titan-operations-sentinel/actions/workflows/eval-nightly.yml/badge.svg)](https://github.com/ma731/titan-operations-sentinel/actions/workflows/eval-nightly.yml)
[![scorecard](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ma731/titan-operations-sentinel/eval-results/badge.json)](eval/results/scorecard.md)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**[Open the live demo](https://ma731.github.io/titan-operations-sentinel/)** (runs in the browser, nothing to install)
· [Glossary](#glossary) · [Technical reference](docs/TECHNICAL.md)

![One alert, six agents, a costed and safety-gated plan](docs/demo.gif)

---

## The story in 30 seconds

Titan is a (fictional) manufacturer with plants in Leipzig and Amsterdam
(Amsterdam also holds the central parts warehouse). The Leipzig plant
has a cutting machine, **Machine 7**, that makes metal parts worth about **180,000 EUR a day**.

On a Friday afternoon, the bearing that the machine's cutting head spins on starts to wear
out. Left alone, the machine breaks in roughly two to three days and production stops.

Today, fixing that takes five teams talking to each other: maintenance, purchasing,
production planning, quality and safety. Each sees only its own part of the picture, and on
a Friday afternoon they are hard to get in one room.

Titan does that coordination in about a minute:

| Step | Who | What happens |
|---|---|---|
| 1 | **Alert filter** (plain code, no AI) | Out of ~22,000 sensor alerts a day, it picks the one that matters |
| 2 | **Maintenance agent** | "The bearing on Machine 7 will fail in about 52 to 76 hours" |
| 3 | **Purchasing agent** | "We have no spare bearing here. Amsterdam has three. A rush delivery costs 3,200 EUR" |
| 4 | **Production agent** | "Move Machine 7's jobs to Machines 5 and 8, without clashing with shifts or robots" |
| 5 | **Quality agent** | "Is the failing bearing already causing defects? Can the backup machines hold quality?" |
| 6 | **Safety agent** | "Every step is safe and within the rules" (it can stop the whole plan if not) |
| 7 | **A person** | The plant manager approves the 3,200 EUR, because anything over **500 EUR** needs a human |

**Result:** about 116 hours of unplanned downtime avoided for a 3,200 EUR rush order, with a
full record of who decided what and why.

## Try it

Open the **[live demo](https://ma731.github.io/titan-operations-sentinel/)** and press
**Run**. It plays back a recorded run, so there is no cost and nothing to set up. Press
**Ask Titan** (bottom right) and the built-in assistant explains any screen, by text or voice.

To run it on your own machine with a real AI model, see [Run it yourself](#run-it-yourself).

---

## How it works, in plain words

```
 22,000 alerts a day
        |
        v
 Alert filter (rules, free) ---- ignores the noise
        |
        v
 Coordinator agent ------------- decides which specialist goes next
        |
        +--> Maintenance   what is failing, and when
        +--> Purchasing    parts, suppliers, cost of each option
        +--> Production    who makes the parts in the meantime
        +--> Quality       is the backup safe for quality
        +--> Safety        is all of this safe and legal (can stop everything)
        |
        v
 Human approval -------------- anything over 500 EUR, anything touching safety
        |
        v
 Action plan: do now / needs approval / keep watching, with costs, saved to memory
```

The key design idea is **who decides what**:

- **The AI decides** the judgement calls: which specialist to ask next, what each one
  concludes, which data to look at, how the plan reads.
- **Plain code decides** the rules that must never break: spending over 500 EUR always
  goes to a person, the safety agent can always stop the plan, every important specialist
  is always consulted, and if the data is missing the system says "I don't know" and calls
  a person instead of guessing.

Rules written in code can be tested without any AI and cannot be talked out of by a clever
prompt. That is why the system can act on its own and still be trusted.

### What the agents use

| Ingredient | In plain words |
|---|---|
| **Tools** | Small programs the agents call: check stock, read sensors, compare suppliers, draft a work order. Tools fetch data and do sums; they never make the decision. |
| **Document search** | 12 technical manuals and safety standards. Agents must quote the section they relied on. |
| **Memory of past cases** | Similar past failures: what was predicted, what really happened, what was done. |
| **Supplier map** | Who supplies whom, so a problem at a supplier's supplier is spotted early. |
| **Prediction model** | Estimates how long a part has left. Trained on NASA's public jet-engine failure data, because no public data exists for these machines. |

---

## How we know it works

Everything is tested without spending money on AI calls, on every change to the code.

| What we checked | Result | In plain words |
|---|---|---|
| 34 realistic test situations | **100%** of 208 checks pass | Normal days, missing data, safety problems, expensive fixes |
| Safety stops | **0 missed, 0 false** in testing | It stops when it must, and only then |
| Attacks on the AI | **19 of 19** blocked | Fake instructions hidden in emails or notes ("this is pre-approved") do not get through |
| A simulated month of a real plant | **3 of 3** failures caught, 2 to 6 days ahead | And no false alarms on the 11 quiet days |
| Life prediction | **2.5x** more accurate than a simple average | On 707 engines the model had never seen |
| Automated tests | **471** pass | Run on every change |

**What is not proven yet,** said plainly:

- The factory data is **simulated**. It is realistic, but it is not a real plant.
- In a live run on a strong model (November 2026), the safety agent stopped a plan that was
  actually safe, because a keyword rule read "do **not** bypass guards" as "bypass guards".
  It failed in the safe direction, but it was still a false stop. It is written up, with
  the fix, as finding [F-12](eval/FINDINGS.md).
- Using a cheaper model for routine steps cut cost by 10% in one live test; it is too early
  to say whether quality held.

Every problem the tests found is listed in the [findings register](eval/FINDINGS.md). None
were hidden by changing the test to match the code.

**It watches itself.** Every night the free tests run again and the scores are compared with
the night before. If any score goes down, the project opens an issue saying which score,
what it was, what it is now, and which code changes happened in between. When the score
comes back, it says so and closes the issue. No AI calls, so it costs nothing.

---

## My contribution

This was a five-person course project, so here is what I built and can explain in detail:

- **The coordination** (`graph.py`, `policy.py`): how the agents take turns, the 500 EUR
  rule in code, and the "stop and call a person" path when data cannot be trusted.
- **The testing** (`eval/`): the 34 test situations, the scorecard, the attack tests.
- **The document search** (`rag/`), the **web console** (`webapp/`), the **model layer**
  that works with any AI provider (`llm.py`), cost tracking, the alert stream, Slack and
  email approvals, CI and Docker.
- The life-prediction model (`ml/`) came later, after the course ended.

The rest of the team: Marian Garabana set up the project and wrote the case study. David
Carrillo built the first tools and the scenario data. Nuria Diaz rewrote the agents'
instructions. Ignacio Moreno prepared the presentation and the demo.

---

## Glossary

The demo and the code use short codes and engineering terms. Here is what they mean.

**The scenario**

| Term | Meaning |
|---|---|
| **CNC-07-LEI** | Machine 7 at the Leipzig plant. Codes read *machine type, number, plant*. |
| **CNC machine** | A computer-controlled cutting machine that shapes metal parts. |
| **LEI, AMS** | Leipzig; Amsterdam, which also holds the central parts warehouse. |
| **Spindle bearing** | The bearing the cutting head spins on. When it wears out, the machine stops. |
| **P-4421, P-7803** | Part numbers: the spindle bearing kit, and a hydraulic seal set. |
| **Friday Cascade** | The demo story: a failure on a Friday afternoon that touches every team. |
| **Expedite** | Paying extra for a rush delivery. |
| **Tier-2 supplier** | Your supplier's supplier. A fire at their plant can still stop yours. |
| **OEM limits** | The machine maker's safe operating limits. |
| **Downtime** | Hours a machine cannot produce. |

**How the system works**

| Term | Meaning |
|---|---|
| **Agent** | An AI model with a job, a set of tools and rules. It decides its own next step. |
| **Orchestrator / supervisor** | The coordinator agent that decides which specialist goes next. |
| **Triage gate** | The free alert filter that decides which alerts are worth waking the agents for. |
| **RUL** | Remaining useful life: how long until a part fails. |
| **HALT** | The safety agent's stop. It overrides everything, including an approved purchase. |
| **AUTO / APPROVE / ESCALATE** | Do it now / a manager approves / the safety officer decides. |
| **Abstain** | The system says "I don't know" and hands over to a person, instead of guessing. |
| **Audit trail** | A log of every step, tool call and decision, so anyone can check why. |
| **Replay / Live** | Replay plays back a recorded run (free). Live uses a real AI model. |
| **RAG** | Retrieval: the AI looks up documents and quotes them, instead of answering from memory. |
| **MCP, A2A** | Two open standards. MCP lets other AI tools use Titan's tools; A2A lets other agents hand Titan a task. |
| **Red team** | Deliberately attacking your own system to find weaknesses before others do. |
| **F-01 to F-13** | Numbered findings: problems the tests found, in [eval/FINDINGS.md](eval/FINDINGS.md). |
| **C-MAPSS** | NASA's public data set of jet engines run until failure, used to train the life model. |

---

## Run it yourself

```bash
docker compose up --build       # console on localhost:5173, no AI key needed
```

Or without Docker:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/                 # the automated tests (free, offline)
python -m eval.run_eval                 # rebuild the scorecard (free, offline)
python scripts/run_demo.py              # a live run: needs an AI key in .env
```

The specialist agents need an AI model that can call tools. Put a key in `.env` (Gemini and
Groq have free tiers, Azure OpenAI and others work too) or use a local Ollama model. Without
a key, the demo, the tests, the document search and the scorecard all still work.

---

## Going deeper

- **[Technical reference](docs/TECHNICAL.md):** architecture, evaluation method, safety
  rules, the simulated month, approvals over Slack and email, cost tracking, model routing,
  MCP and A2A, the knowledge graph, the full repository layout and every known limitation.
- **[Decision records](docs/decisions/):** why it is built this way, including a change we
  measured and rejected.
- **[Findings register](eval/FINDINGS.md):** every problem the tests surfaced.
- **[Web console guide](webapp/README.md)** and the **[evaluation scorecard](eval/results/scorecard.md)**.

## Team

IE University, MBDS, Agentic AI for IT, Team 3. Presented 24 June 2026.
Marco Ortiz Togashi, David Carrillo Aguilera, Nuria Diaz Jimenez, Marian Garabana Garrido,
Ignacio Agustin Moreno.

Licensed MIT.
