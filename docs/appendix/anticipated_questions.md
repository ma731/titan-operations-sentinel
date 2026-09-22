# Anticipated Q&A — Titan Operations Sentinel

Likely investor / professor questions with crisp, honest answers. Any team member should be able
to field any of these. Honesty is the strategy: where something is a stub or a design, say so.

---

## Architecture & autonomy

**Is this actually agentic, or a fixed script?**
Both, by design. The five specialists are real LangGraph `create_react_agent` agents — each LLM
chooses *which of its own tools* to call and loops until done. The orchestrator is an LLM that picks
the *order* of agents. What's deterministic is a thin policy (`_allowed_next()`) that *guarantees*
coverage on a high-risk event and always finishes through the safety gate. So judgement is the
model's; the guarantees are code. We call it **guided autonomy**.

**Then how much does the LLM really decide on the demo path?**
On a HIGH-risk alert it must engage all five domains (that's a deliberate guarantee — we *want* every
challenge covered), but the LLM picks the order, each agent picks its own tools, and an agent can
raise a `FOLLOWUP` to another. The console tags each routing step **LLM-routed** vs **auto-routed**
so you can see it live. Skipping agents would undermine "all 5 challenges covered," which is the point.

**Why multi-agent instead of one big agent?**
Five focused agents (~3 tools each) make better tool choices than one juggling 19, and they mirror
the real org silos the case study is about uniting. It also localises failure and makes the trace
legible.

**What's your memory model?**
Three layers: the **shared transcript** (agents read each other), the LangGraph **`MemorySaver`
checkpointer** (per-run state, powers the interrupt/resume — persistent within a session), and the
**case library** on disk (cross-run episodic memory for the learning loop). Be precise: the
checkpointer is session-scoped; the durable memory is the case library.

---

## Tools & feasibility

**Agent decides, tools act — show me.**
Tools are pure functions; writes are **drafts** (`work_order_draft` → `DRAFT_PENDING_APPROVAL`,
`notify` → `DRAFT_PENDING_SEND`); `safety_gate` is a hard control that can HALT. No tool commits an
irreversible action. The catalog (`docs/tool_catalog.md`) lists when / when-NOT / fallback for each.

**Your data is simulated — is this feasible?**
The *agent loop* is fully real; the *integrations* are stubbed. Tools read production-shaped JSON, so
behaviour is representative. Real SCADA/SAP wiring is OT access + pipelines — next step, not a
research risk. We're honest about this rather than faking integrations.

**Is any of it backtested?**
The RUL model is, on real data: NASA C-MAPSS, 707 held-out engines, test RMSE 17.0 cycles
against a mean-predictor baseline of 41.8, with a conformalised lower bound whose coverage
is measured rather than asserted. The CNC demo asset is **not** backtested, because no
public run-to-failure dataset exists for spindle bearings, and every prediction it makes is
labelled `declared_thresholds` in the tool output, the transcript and the audit log. The
honest answer is "the model is, that asset is not, and the system tells you which you are
looking at". See `eval/results/rul_backtest.md` and decision 008.

---

## Risk, safety & security

**Can the agent self-approve a €400 spend?**
Precisely: €500 is the **delegated-authority ceiling**, not "never spends." A sourcing option runs
autonomously only if it's **under €500 *and* fits the failure window** (e.g. the Edge path's €420
cross-plant transfer); anything over €500, or that misses the window, routes to a human via
`interrupt()`. It's **code-enforced** with a unit test for both branches (€420 autonomous vs €3,200
gated). So say "below the €500 ceiling *and* in-window = within delegated authority," not "it can
never spend without approval" — the Edge demo would contradict that.

**What stops a poisoned tool output or FOLLOWUP line from hijacking the agents?**
Routing **can't** be hijacked: the next agent comes from the `_allowed_next()` policy (the LLM only
orders an allow-listed set), FOLLOWUP targets are validated against `AGENT_NAMES` and capped by
`MAX_VISITS`, tools are pure (no shell/eval/open web), and agents draft rather than execute. Content
trust on the transcript is the documented next mitigation (output filtering / signed returns).

**What if an agent or the model fails mid-run?**
Per-agent `try/except`: a flaky call degrades to a noted error and the run continues; reliability
**fails toward caution** (error ⇒ risk = HIGH). Compliance can HALT. On thin telemetry the system
**abstains** (escalation path refuses to fabricate a plan). See `risk_matrix.md` + `failure_modes.md`.

---

## The learning loop

**What does it actually learn, with no retraining?**
It improves from experience and feedback: it **recalls** the closest past case into the reliability
agent's context, **writes** every closed run back to the case library, and a **self-closing
reconcile** step (run on `perceive`) validates predicted-vs-actual RUL as outcomes arrive. Two
further mechanisms — reflection-replay and automatic signature down-weighting — are **designed and
labelled "design"** in the console, not claimed as live.

**Where does the loop close itself? Show me the write-back.**
`graph._log_closed_case()` calls `tools.recall_cases.append_case()` on every finalize;
`reconcile_due()` (invoked in `perceive`) resolves pending cases when outcomes are known. Tests:
`test_append_case_grows_library`, `test_reconcile_closes_the_loop`.

**Quantify the improvement.**
We demonstrate the *mechanism*, not a measured magnitude — the accuracy figure is **3/3 over a
seeded case library** (labelled "design" in the console, "over the seeded case library"). Measuring
a run-1-vs-run-100 delta needs production outcome data; that's the honest framing.

**Show the loop reconcile something live.**
`reconcile_due()` runs every cycle in `perceive`, but it only acts when an outcome is known — it
reads `data/memory/outcomes.json`, which a telemetry/maintenance feed would write. With no feed
present it's a safe **no-op** (cases stay honestly pending); the mechanism is proven by
`test_reconcile_closes_the_loop` and `test_reconcile_due_resolves_known_outcomes`. Don't claim it
reconciles live unless you drop an `outcomes.json` in first.

**Why does the ROI use 52h, not 76h?**
Deliberately the **conservative** bound: we cost against the *earliest* predicted failure (RUL min =
52h), which gives the *fewest* hours saved and the *lowest, most defensible* ROI. Using 76h would
inflate it.

---

## The numbers

**Derive the 79.7:1 ROI live.**
34 hours saved (52 − 18 lead) × €7,500/h = €255,000 downtime avoided ÷ €3,200 expedite = **79.7:1**.
€7,500/h = €180,000/day, the plant's production value at risk (from the asset profile).

**Why €180,000/day?**
It's the asset's `production_value_per_day_eur` in the data; everything (graph, docs, tests, UI)
is consistent on it.

**Is the RUL a real model?**
No — a transparent **heuristic** plus a historical **pattern-match** (we openly say so). We
deliberately did *not* fake an ML model: the historical curve would imply a much shorter window, so
dressing a constant as "ML" would be dishonest. Training a real estimator on failure history is
next step #2.

---

## The demo

**Is the demo live or a recording?**
Default is **Replay** — a labelled recording that needs no key and can't fail (zero cost). We'll then
flip to **Live** on a real provider (Gemini / Groq / Azure) for one run as the "yes, it's real"
proof. The same event contract drives both, so what we rehearse is what runs.

**Why three paths?**
To show the autonomy *range*: Cascade (human gate), Edge (autonomous under the ceiling), Escalation
(abstains on thin data). One scenario can't show all three behaviours.

---

## Business

**Why an agent, not a dashboard or an RPA rule?**
A dashboard shows six panels and waits — the human does the cross-domain reasoning under €7,500/h of
pressure. An RPA rule can't weigh ROI vs risk, adapt a reroute, or know when to ask a human. The
agent reasons across five domains, decides, and hands back **one costed, safety-gated plan** —
escalating when the data is thin. (`why_agent_not_dashboard.md`.)

**What's the ROI of building this?**
On the modelled incident, €3,200 prevents up to ~€255k of avoided downtime (79.7:1), and the plan is
produced in under two minutes instead of a cross-team scramble — with a full audit trail.

**Next steps?**
Real telemetry + CMMS/ERP tools; a trained RUL model; production reconciliation + preference learning;
fleet- and plant-wide rollout. The architecture is the contribution; model, tools, and data are
swappable.
