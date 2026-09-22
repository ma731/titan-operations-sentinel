# 🛰️ Titan Operations Sentinel — Demo Script

**IE University · Agentic AI for IT · Team 3 · June 24, 2026**
Presenters: Marco · David · Nuria · Marian · Ignacio

> The app is open at `http://localhost:5174/`.
> **Decide your mode before you start — it changes one line of what you say (see below).**
> Target: **~10–12 minutes** of demo, then Q&A.

---

## Replay or Live? (read this first)

The app runs two ways, and the only thing that changes in your script is the cost line:

| Mode | What it is | What you can say about cost |
|---|---|---|
| **Replay** *(safest for the pitch)* | A recording of a real run. No internet, no key, can't fail. | "This runs for **€0** — it's a recorded run, no API calls." ✅ |
| **Live** | The real AI agents thinking in real time, calling a real model. | "This is **real**, calling a live model. A full run is a fraction of a cent — about **half a cent**." **Do NOT say "€0" in Live** — a live run uses real tokens. |

**Our recommendation:** present on **Replay** (free tiers can slow down or rate-limit in the middle of a pitch, and you don't want that in front of the class). If you *want* to prove it's real, do **one** Live run and use the Live cost line above. The app now shows the honest number for you: in Live mode the Cost screen says **~€0.005**, not €0.

---

## 0 · Before you walk in (2-min setup, do it once)

- [ ] App open in the browser at `:5174`.
- [ ] Mode toggle (top-right) set to the one you chose — **Replay** for the safe demo.
- [ ] If presenting **Live**: a free key (Gemini or Groq) is already pasted into the provider bar and saved.
- [ ] Zoom the browser to ~110–125% so the back row can read it.
- [ ] Close Slack/mail, go full-screen (F11).
- [ ] Open the slide deck `/deck.html` in a second tab as a backup.
- [ ] **One person drives the laptop** the whole time. Don't swap mid-demo.

---

## 1 · The hook — set up the problem (Marco — 60 sec)

> "Imagine a factory that gets **22,000 alarms a day** from its machines. Most are noise.
> But when a key machine actually breaks, it costs the company **€180,000 a day** — and
> nearly 4 out of 10 of those breakdowns *could have been seen coming.*
>
> The real problem isn't missing data. It's that the people who handle **repairs, parts,
> production, quality and safety all work in separate boxes** — and when something breaks,
> nobody connects the dots fast enough.
>
> A dashboard just shows you numbers. A rules-based script only does what it's told.
> Neither one actually *thinks the problem through.* So we built a team of AI agents that
> does — they handle the whole emergency together and hand a human **one clear plan.**
> Let me show you what happens when the one alarm that matters comes in."

**On screen:** Stay on the home view with the **agent map** (the supervisor in the middle,
the six agents around it). Don't click yet — let them see the team.

---

## 2 · The main story — the Friday breakdown (David drives — 4 min)

> "It's Friday afternoon. An alarm comes in for machine **CNC-07** in our Leipzig plant.
> Its vibration just jumped past the safe limit, and it's been climbing for six hours.
> A bearing is starting to fail. Watch the agents handle it — start to finish."

**Action:** Pick the **Cascade** scenario → press **Run** (or **Present** for hands-free).

Talk through it as each agent lights up. Go slow — let each one finish before you move on:

1. **The Repair agent goes first.**
   > "It sorts through all 22,000 alarms and picks out this one. Then it checks its memory
   > and finds a **near-identical breakdown from before** — same warning signs, same machine
   > type. Based on that, it estimates the machine has **about 2 to 3 days left**, and it
   > knows exactly which two parts it'll need. **It flags this as high risk.**"
   *(Point at the 'similar past case' it found — that's the system learning from history.
   We'll come back to it.)*

2. **The Parts agent picks it up.**
   > "It checks the shelf — the main part is **out of stock**. A supplier can rush it over
   > in 18 hours for **€3,200.** It does the math: spending that €3,200 saves us roughly
   > **€255,000** in avoided downtime — about **80 times the cost.** But €3,200 is above our
   > **€500 spending limit**, so it can't just spend it. Remember that — it matters in a second."

3. **The Production agent reshuffles the work.**
   > "It tries to move the jobs to another machine — but that one has a **staffing clash.**
   > So it *adapts*: it sends the work to a different free machine instead, and **asks the
   > Quality agent a direct question** — 'is that machine safe to take the extra load?'"

4. **The Quality agent answers.**
   > "It confirms the backup machine is **within spec and safe**, and that the failing
   > machine's vibration really is linked to defects. Green light."

5. **The Safety agent has the final word.**
   > "Before anything happens, the **Safety agent checks every action against the rules.**
   > This one has a veto — it can **stop the whole plan.** Here it signs off and writes up
   > the paper trail for the auditors."

6. **The human decision.**
   > "Now the system **stops on its own.** It will *not* spend €3,200 without a person."

   **Action:** When the **approval box** appears, pause. Read it out loud (the €3,200 rush
   order + the weekend repair window), then click **Approve** as the plant manager.

   > "A human only steps in where it really matters — the spending and the weekend work —
   > not for every little thing."

7. **The final plan.**
   > "And here's the payoff: **one clear plan**, sorted into three buckets. Things the system
   > **did automatically** — slow the machine down, move the jobs. Things it **needed a yes**
   > for — the rush order, the weekend window. And what to **keep watching.** Best of all,
   > the whole thing gets **saved to memory**, so next time it's even faster. One alarm,
   > five departments, one decision for the manager instead of twenty."

> **If you're running Live:** add — *"and everything you just saw was the real AI deciding
> in real time, not a script."* Then **don't** mention €0 — say it costs about half a cent.

---

## 3 · Why you can trust it (Nuria — 90 sec)

> "Two things make this safe to actually use, instead of a black box you just hope works.
>
> **First — the AI makes the judgment calls, but the rules are locked in code.** Things
> like *'never spend over €500 without a human'* or *'safety always gets the last word'* —
> those aren't suggestions to the AI, they're hard limits it physically cannot cross. So
> it's smart and independent, but it **can't go off the rails.**
>
> **Second — the agents talk to each other in plain language**, like a real team. Each one
> writes up what it found, the others read it, and they can ask each other direct questions —
> just like you saw Production ask Quality. It mirrors how the real departments *should* work
> together, but usually don't."

**On screen:** Hover over a connection to show the **'AI chose this' vs 'rule forced this'**
label, and open the agents' written notes if that panel is visible.

---

## 4 · Second scenario — when the plan falls apart (Marian — 90 sec)

> "Agents are only impressive when things *don't* go to plan. Watch this one."

**Action:** Pick the **Edge** scenario → **Run**.

> "Same kind of breakdown, but now **no supplier can deliver in time.** A simple script
> would just give up here. Instead, the Parts agent **finds another way** — it pulls the
> part from a sister plant for only **€420.** And because that's **under our €500 limit**,
> the system just **handles it itself — no human needed.** Notice: the *same* €500 rule,
> opposite result. That limit is real, and it's built into the code, not the slides."

---

## 5 · Third scenario — when it knows to stop (Ignacio — 90 sec)

> "And the most important thing of all — knowing when **not** to act."

**Action:** Pick the **Escalation** scenario → **Run**.

> "Here the sensor data **cuts out** — the machine's only sending half its readings. The
> Repair agent **refuses to guess.** It won't make up a number it can't back up. Instead it
> **stops and calls in a human** for a manual check. No fake confidence, no made-up answer.
> A system you'd actually trust on a factory floor is one that knows the limits of what it
> knows — and this one does, on purpose."

---

## 6 · It gets smarter over time (Marco — 60 sec)

**Action:** Open the **Learning** view.

> "Last thing — it learns, without us ever retraining the model. It **remembers** past
> breakdowns — that's the matching case you saw at the start. It **saves every job it
> finishes** to that memory. And it **checks its own predictions against what actually
> happened** to get more accurate over time. A couple of the deeper learning features are
> still on the drawing board, and we **label those honestly** in the app — we're not
> pretending they're done. And every number you've seen today is backed by **automated tests.**"

---

## 7 · Wrap up (Marco — 45 sec)

> "So to recap: **six AI agents**, **five different problems**, **one clear, costed,
> safety-checked plan** — with a human stepping in only where it counts.
>
> A dashboard would have *shown* the factory the warning. This system **handled the whole
> Friday afternoon for them** — and turned twenty scattered decisions into one. Happy to
> take your questions."

---

## 8 · Quick answers for Q&A (whole team)

*(Fuller version in `docs/appendix/anticipated_questions.md`.)*

| If they ask… | Say… |
|---|---|
| **Is the data real?** | Mostly simulated, and labelled as such: same shape as real factory systems, because hooking up real machines is months of plumbing and what we're showing is the **agents' decision-making**. One asset is the exception. `TRB-01-LEI` runs on real NASA benchmark telemetry, so the fitted RUL model is exercised on data it was validated against. |
| **Is the prediction backtested?** | The model is, on 707 held-out engines. The CNC asset is not, and it says so: every RUL result carries a `source` field reading either `fitted_model` or `declared_thresholds`, and it reaches the transcript and the audit log. See `eval/results/rul_backtest.md`. |
| **Is the failure prediction a real AI model?** | No — it's a **simple stand-in**, and we say so in the app. The real work here is the **teamwork between agents**, not the predictor. It's easy to swap in a trained one later. |
| **Why a team of agents instead of one big AI?** | Five focused agents, each with a few tools, make **better choices** than one trying to juggle twenty tools — and they match how the real departments are split. |
| **What stops it doing something crazy?** | Hard-coded limits: the €500 cap, mandatory safety sign-off, and a human approval step on spending. The AI decides; **the rules guarantee.** |
| **What if an agent crashes?** | The run keeps going with a noted error, and anything safety-related defaults to **'treat as high risk.'** It fails *carefully.* |
| **Did you inflate the savings number?** | We used the **most cautious** estimate (earliest possible failure time), and it's checked by an automated test. |
| **Why show a recording (Replay)?** | Free AI tiers can slow down mid-pitch — Replay can't fail and shows the **exact same steps** as a real run. We can also run it Live with a key. |
| **Are you locked into one AI provider?** | No — it works with Gemini, Groq, OpenAI, Azure, and others, switchable from a dropdown in the app. |

---

## 9 · If something breaks (stay calm)

- **Blank screen:** hard-refresh (Ctrl+Shift+R). Still blank? The slide deck at **`/deck.html`**
  tells the whole story — just present from there.
- **A Live run stalls or errors:** flip the toggle to **Replay** and re-run. (This is exactly
  why we recommend Replay for the real thing.)
- **Server stopped:** in `webapp/frontend`, run `npm run dev` again and note the port it
  prints (might be 5173 or 5174).
- **Someone insists on Live and it's slow:** "Free tiers throttle — here's the recorded
  version of the same real run," switch to Replay, move on. Don't fight it live.

---

### Who says what, and for how long

| Part | Who | Time |
|---|---|---|
| The hook (the problem) | Marco | 1:00 |
| Friday breakdown (main story) | David | 4:00 |
| Why you can trust it | Nuria | 1:30 |
| When the plan falls apart | Marian | 1:30 |
| When it knows to stop | Ignacio | 1:30 |
| It gets smarter over time | Marco | 1:00 |
| Wrap up | Marco | 0:45 |
| **Total** | | **~11:15** + Q&A |
