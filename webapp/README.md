# Titan Operations Sentinel, Web Console

A premium, projector-ready web UI that visualizes the multi-agent run in real time: the
supervisor routing between six agents, each agent's tool calls and reasoning, the human
approval gate, and the final costed action plan.

> **Built to demo with zero cost.** The frontend ships with a baked "Friday Cascade" event
> stream, so **Replay mode needs no backend, no API key, and spends nothing.** Use it for the
> live presentation. *Live mode* runs the real graph on a provider you choose, for when you
> want to show it end to end.

---

## Quick start, Replay (recommended for the pitch)

```bash
cd webapp/frontend
npm install
npm run dev          # open http://localhost:5173
```

Sign in (pick a presenter), **Launch console**, choose a scenario (**Cascade / Edge / Escalation**),
press **▶ Run**, and approve/reject at the gate. No key, no backend, no spend. It always works on a
projector. Or hit **▶ Present** for a hands-free, auto-narrated run.

## Live mode (real agents on a real model)

One terminal, the backend:
```bash
# from the repo root
pip install -r requirements.txt
python -m uvicorn main:app --app-dir webapp/backend --port 8000
```
Another terminal, the frontend:
```bash
cd webapp/frontend && npm run dev
```
Then open the **provider picker** (top bar), pick a provider, paste your key, and **Connect**. No
`.env` editing required, though you can tick **Save to .env** to persist it.

**Supported providers** (all swappable live from the picker):

| Provider | Notes |
|---|---|
| **Gemini** | free tier, most token headroom for a full run |
| **Groq** | free, very fast (use `llama-3.3-70b-versatile`; `8b-instant` is too small) |
| **OpenRouter** | one key, many free models, best when a tier rate-limits |
| **Azure OpenAI** | paid-tier limits (great with student credits); needs endpoint + deployment + version |
| **OpenAI / Anthropic / Mistral** | paid / free tiers |

> A full 6-agent run is ~40 model calls. Free tiers can rate-limit mid-run, so **rehearse and
> present on Replay**; keep Live as the "yes, it's real" proof.

### Ports
The backend defaults to **`:8000`**. If that port is taken on your machine, set a different one and
tell the frontend proxy about it:
```bash
python -m uvicorn main:app --app-dir webapp/backend --port 8009
# webapp/frontend/.env.local  (gitignored)
VITE_API_PORT=8009
```

---

## What's in the console

- **Live orchestration graph**, the supervisor routing six agents, with energy-pulse edges and
  hover tooltips explaining each agent.
- **Agent Chat**, a type-a-crisis chatbot: describe a situation in plain language and it routes to
  the right scenario and dispatches the agents.
- **Run History**, every completed run saved (localStorage), with one-click **Markdown report export**.
- **Cost & Feasibility**, token/cost breakdown per agent.
- **Audit Log** and **Action Plan** with an autonomy-tier legend (AUTO / APPROVE / ESCALATE).
- **Plant Fleet** panel and a full **asset profile** for CNC-07-LEI.
- **Per-presenter sign-in** with accent theming and an in-console switcher.
- **⌘K command palette**, **Presenter** auto-play, and a first-load "what am I looking at?" coachmark.

## How it works

- **Backend** (`backend/main.py`): wraps `graph.py`, iterates `graph.stream(...)`, and emits each
  trace event (`route`, `tool_call`, `agent_report`, `approval_request`, `plan`, ...) as SSE. The
  human approval `interrupt()` is resolved via `POST /api/decision`. `GET /api/providers` and
  `POST /api/config` drive the live provider picker.

### Every endpoint

| Endpoint | What it does |
|---|---|
| `GET /api/run?scenario=` | streams the live trace as Server-Sent Events |
| `POST /api/decision` | resolves a paused approval gate (the console's Approve / Reject) |
| `GET /api/decision/link` | resolves the same gate from a link in an approval email |
| `POST /api/slack/interactions` | resolves the same gate from the Slack buttons, signature verified with a five minute replay window |
| `GET /api/providers` | provider catalog and which keys are present |
| `POST /api/config` | switch provider, model or key at runtime, optionally persisting to `.env` |
| `GET /api/health` | liveness plus what is actually wired up: active provider, approval channel, retrieval corpus size and mode, and the policy constants |

All three approval routes funnel into one internal `_resolve()`, so a run has exactly one
resume path and one audit record however the decision arrived.

`GET /api/health` is worth pointing a reviewer at during a demo: it reports the live
configuration rather than a description of it.
- **Frontend** (`frontend/src/`): one event reducer (`App.jsx`) drives the whole UI from that event
  shape, identical for replay (`cascade.js`) and live, so what you rehearse is what you demo.
- **Design**: light editorial showcase + light console; Schibsted Grotesk / Fira Sans / JetBrains
  Mono; motion via CSS + anime.js, all reduced-motion aware.

## Demo-day tip
Rehearse and present on **Replay**. Keep **Live** as the "yes, it's real" proof, ideally after
you've recorded a golden run so even Live is backed by something you've already seen succeed.
