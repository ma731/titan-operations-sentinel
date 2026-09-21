# Tool Catalog — Titan Operations Sentinel

Pre-submission deliverable (assignment brief §8). 20 tools across 5 specialist agents
(one agent per TMC challenge). Each tool is a pure Python function in `tools/`, exposed to
the agents as a LangChain `@tool` in `tools/lc.py`. The **agents decide** which tool to call
(autonomous ReAct); the **tools act** (fetch data / compute / draft). Tools never make
decisions and never commit irreversible actions — drafts only.

Per-agent tool map (`tools/lc.py` groups):

| Agent | Challenge | Tools |
|---|---|---|
| Reliability | 1 Predictive maintenance | alert_triage, sensor_query, rul_predictor, recall_similar_cases, asset_profile, maintenance_schedule, search_technical_docs |
| Supply Chain | 2 Supply volatility | parts_inventory, supplier_catalog, expedite_cost, tier2_supplier_risk, work_order_draft, notify |
| Production & Human-Robot | 3 Coordination | job_reroute, robot_cell_status, shift_conflict_check |
| Quality & Traceability | 4 Quality | quality_history, telemetry_correlate |
| Compliance & Safety | 5 Safety/audit | safety_gate, audit_assemble, search_technical_docs |
| (shared) | — | `search_technical_docs` is bound to Reliability and Compliance; `maintenance_schedule`, `work_order_draft` and `notify` are bound to the agents listed above |

---

## Reliability Agent (challenge 1)

### `alert_triage`
- **What it does:** Triages the raw plant alert stream (22k/day) down to the few deduplicated critical alerts.
- **Inputs:** `plant_id: str` · **Outputs:** counts by severity + ranked critical alerts
- **Use when:** First, to find which machine actually needs attention. **Do NOT use:** to assess a specific machine. **Auth:** READ.

### `sensor_query`
- **What it does:** Returns 72h time-series (vibration, bearing temp, spindle current) + summary for a machine.
- **Inputs:** `machine_id: str`, `window: "24h"|"48h"|"72h"|"dropout"`, `sensors: list[str]`
- **Outputs:** `readings`, `summary`, `data_timestamp`, `sensor_status` (`OK`|`INTERRUPTED`)
- **Use when:** First step of any assessment — establish the failure pattern.
- **Do NOT use:** To predict failure (that is `rul_predictor`).
- **Risk if misused:** Acting on stale/partial telemetry → wrong urgency.
- **Fallback:** Missing file → `{"error": "data_unavailable"}`; interrupted feed → `sensor_status: INTERRUPTED` → escalation path.
- **Auth:** READ (autonomous).

### 2. `rul_predictor`
- **What it does:** Estimates Remaining Useful Life (hours) + confidence from real readings; matches historical failure pattern.
- **Inputs:** `machine_id: str`, `current_readings: dict`
- **Outputs:** `rul_hours{min,max}`, `confidence`, `failure_mode`, `matched_historical_event`, `low_confidence_flag`
- **Use when:** After `sensor_query` confirms an anomaly.
- **Do NOT use:** With assumed/default readings — only real sensor output.
- **Risk if misused:** Hallucinated timeline drives a bad decision.
- **Fallback:** `confidence < 0.6` → `low_confidence_flag: true` → escalate.
- **Auth:** READ (autonomous). *Heuristic model in MVP — not a trained ML model (be honest in Q&A).*

### 2b. `recall_similar_cases` *(Learning: case memory)*
- **What it does:** Retrieves the most similar PAST incidents from case memory (`data/memory/case_library.json`): match %, predicted vs actual RUL, the human decision, and the outcome.
- **Inputs:** `machine_id: str`, `sensor: str`, `signature: str` · **Outputs:** `matches[]`, `library_size`, `rul_accuracy_pct`
- **Use when:** After `sensor_query`, to ground the assessment in precedent rather than only the live reading.
- **Why it matters:** This is the recall step of the Learning loop — the system reasons from experience and validates predicted-vs-actual RUL over time. The audit log appends new closed cases.
- **Auth:** READ (autonomous).

### 3. `asset_profile`
- **What it does:** Returns specs, BOM per failure mode, technicians, safe speed limits, equivalent machines.
- **Inputs:** `machine_id: str` · **Outputs:** profile dict (incl. `failure_modes[mode].bom`)
- **Use when:** Need the exact parts a repair requires.
- **Do NOT use:** For real-time data. **Fallback:** `{"error": "asset_not_found"}`. **Auth:** READ.

### 4. `maintenance_schedule`
- **What it does:** Returns plant maintenance windows, next available slot, and emergency slots.
- **Inputs:** `plant_id: str`, `horizon: str` · **Outputs:** `existing_windows`, `next_available_slot`, `emergency_window_slots`
- **Use when:** Comparing the RUL window against available downtime.
- **Do NOT use:** To commit a schedule change (WRITE = APPROVE tier). **Fallback:** staleness flag. **Auth:** READ.

---

## Supply Chain Agent

### 5. `parts_inventory`
- **What it does:** On-site + warehouse stock for parts at a plant (also used for cross-plant checks).
- **Inputs:** `parts: list[str]`, `plant_id: str` · **Outputs:** per-part `on_site_qty`, `warehouse_qty`, transit
- **Use when:** Before any supplier lookup — parts may already be on hand.
- **Risk if misused:** Ordering parts that are already in stock. **Fallback:** stale flag if >4h. **Auth:** READ.

### 6. `supplier_catalog`
- **What it does:** Supplier options, standard/expedite lead times and costs; pre-built combined options.
- **Inputs:** `part_ids: list[str]`, `scenario: "default"|"edge"` · **Outputs:** `parts`, `combined_options`
- **Use when:** On-site + warehouse cannot cover the gap in time.
- **Do NOT use:** Before confirming the gap via `parts_inventory`. **Fallback:** stale caveat. **Auth:** READ.

### 7. `expedite_cost`
- **What it does:** Ranks procurement options by fit-to-window, risk, then ROI vs downtime cost.
- **Inputs:** `options: list`, `downtime_cost_per_hour: float`, `failure_window_hours: int`
- **Outputs:** `options_ranked` (with `roi_ratio`, `fits_failure_window`), `recommendation`
- **Use when:** Parts gap and failure timeline are both known.
- **Risk if misused:** Recommending an option that misses the window. **Fallback:** unranked + `data_missing`. **Auth:** READ.

### 8. `work_order_draft`
- **What it does:** Generates a structured draft WO. **Not committed** until a human releases it.
- **Inputs:** machine/plant/failure_mode/parts/window/technicians/duration/actions
- **Outputs:** WO dict, `status: DRAFT_PENDING_APPROVAL`, `incomplete_flag`
- **Use when:** Parts plan confirmed. **Do NOT use:** Before the plan exists. **Auth:** APPROVE (human releases).

### 9. `notify`
- **What it does:** Drafts the approval request to the decision-maker. **Not sent** until reviewed.
- **Inputs:** recipient/subject/summary/actions/costs/deadline/WO id · **Outputs:** draft notification, `status: DRAFT_PENDING_SEND`
- **Use when:** Plan needs cost authority. **Do NOT use:** For routine status. **Auth:** APPROVE.

### `tier2_supplier_risk`
- **What it does:** Reveals a Tier-1 supplier's own (Tier-2) dependencies and their risk — the visibility gap in challenge 2.
- **Inputs:** `supplier_ids: list[str]` · **Outputs:** per-supplier Tier-2 deps, single-source flags, overall risk
- **Use when:** Sanity-checking a chosen sourcing option for hidden upstream risk. **Auth:** READ.

---

## Production & Human-Robot Agent (challenge 3)

### `job_reroute`
- **What it does:** Proposes rerouting a down machine's jobs onto equivalent machines with spare capacity.
- **Inputs:** `machine_id: str`, `jobs: list[str]` · **Outputs:** candidates + proposed assignment + `capacity_shortfall`
- **Use when:** A machine will be offline and its jobs must be covered. **Auth:** AUTO (within equivalent machines).

### `robot_cell_status`
- **What it does:** Robot-cell state: robots, assigned operators, collaborative mode, recent safety shutdowns.
- **Inputs:** `plant_id: str` · **Use when:** Checking human-robot coordination risk in a reroute. **Auth:** READ.

### `shift_conflict_check`
- **What it does:** Finds operator/technician conflicts (e.g. one operator double-booked across cells).
- **Inputs:** `plant_id: str`, `target_machines: list[str]` · **Use when:** A window/reroute may double-book staff. **Auth:** READ.

---

## Quality & Traceability Agent (challenge 4)

### `quality_history`
- **What it does:** Recent MES/QMS quality metrics (escape rate vs baseline, defects) for a machine.
- **Inputs:** `machine_id: str` · **Use when:** Is the failing machine escaping? Are reroute targets quality-healthy? **Auth:** READ.

### `telemetry_correlate`
- **What it does:** Correlates quality escapes with sensor telemetry — the MES/QMS↔OT link missing today.
- **Inputs:** `machine_id: str` · **Outputs:** correlation verdict + likely root cause. **Auth:** READ.

---

## Compliance & Safety Agent (challenge 5)

### `safety_gate`
- **What it does:** Classifies a proposed action against OSHA/machine-safety rules.
- **Inputs:** `action_description: str` · **Outputs:** verdict `OK | ESCALATE | HALT`, matched rule, authority, basis
- **Use when:** On **every** proposed action before commit. A `HALT` **overrides all other agents**. **Fallback:** ESCALATE (fail safe).

### `audit_assemble`
- **What it does:** Reconstructs the full decision timeline for a run from the audit log (incident reconstruction).
- **Inputs:** `run_id: str` · **Outputs:** chronological events + counts + OSHA-log skeleton. **Auth:** READ.

---

## Shared: retrieval over the technical corpus

### `search_technical_docs`
- **What it does:** Retrieves the most relevant passages from the technical reference corpus
  in `rag/corpus` (fleet maintenance standards, plus plain-language paraphrases of OSHA
  1910.147 and 1910.212, ISO 10218 / TS 15066, ISO 10816-3 and IATF 16949), each returned
  with a `doc_id#section` citation and a provenance label.
- **Inputs:** `query: str` (a full natural-language question), `k: int` (1-8, default 4)
  · **Outputs:** ranked passages with `citation`, `document`, `section`, `provenance`,
  `text`, `score`, plus the retrieval mode that actually ran
- **Bound to:** Reliability and Compliance & Safety. Both are instructed to put the
  returned citation inline next to the claim it supports.
- **Use when:** before asserting a severity band, a life-estimate rule, an authority limit
  or a procedural requirement. **Do NOT use:** for live machine data (`sensor_query`) or
  past incidents (`recall_similar_cases`) — this corpus is documents, not telemetry.
- **Fallback:** returns an empty passage list with an `error` field if the corpus or index
  is unavailable; retrieval never raises into a run. **Auth:** READ.
- **Measured:** recall@k, MRR and precision@k over 52 labelled queries in
  `eval/rag_eval.py`; the scorecard reports lexical, dense and hybrid separately.

> **This is not the same thing as `recall_similar_cases`.** That tool matches past
> incidents in a structured JSON library, which is case-based memory. This one is
> retrieval over documents. Both are useful and they are different; the distinction is
> kept explicit here because conflating them is an easy and expensive mistake to make in
> a write-up.

---

## Risk tier summary

| Tier | Tools | Who releases |
|---|---|---|
| READ (autonomous) | alert_triage, sensor_query, rul_predictor, recall_similar_cases, asset_profile, maintenance_schedule, search_technical_docs, parts_inventory, supplier_catalog, expedite_cost, tier2_supplier_risk, robot_cell_status, shift_conflict_check, quality_history, telemetry_correlate, audit_assemble | none |
| AUTO (autonomous action) | job_reroute (within equivalent machines) | none |
| APPROVE (human in loop) | work_order_draft, notify, + any procurement > €500 | plant manager (via `interrupt()` gate) |
| SAFETY OVERRIDE | safety_gate (HALT stops the plan) | safety officer |
