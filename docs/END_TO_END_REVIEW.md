# End-to-end review — 21 September 2026

## Starting point

Both GitHub names resolved to `ma731/titan-operations-sentinel`, main commit
`204e5a1`. Claude's evaluation/RAG/observability branch was already merged in PR #21,
followed by safety, retrieval expansion, numeric-grounding and backend-test changes.
There was no existing local checkout or unfinished working-tree change in this workspace.
The initial checkout passed 190 tests, skipped 4 provider tests, passed Ruff and built
the frontend. No labelled expectations were changed during this review.

The existing implementation already included 34 policy scenarios, 52 retrieval queries,
12 source documents, BM25/PRF/optional dense retrieval, continuous simulation, approval
notifications, CI, Docker, a Pages replay and a generated demo GIF. Those were preserved.

## Concrete fixes

| Area | Finding | Result |
|---|---|---|
| Graph safety | Agent construction escaped error handling; missing safety output could clear a run | Missing reliability evidence escalates; missing/failed safety clearance halts |
| Safety aggregation | Only the last safety tool result survived | Every result is checked; earlier HALTs survive later OKs |
| Rejection | A rejected plan still entered free-form synthesis | A deterministic `rejected` handoff withholds actions |
| Risk | Historical bearing-failure text overrode current normal readings | Current structured failure mode takes precedence |
| Procurement | Instructions always used a 52-hour failure window | Instructions use the current assessed lower RUL bound |
| Spend | NaN/negative/non-numeric quotes could bypass the ceiling | Invalid cost requires human review |
| Evaluation | Live scenarios used demo sensor/supplier files | Scoped scenario inputs reach the real tools; safety instructions use labelled actions |
| Evaluation gate | Retrieval/live errors could still exit successfully | Policy and retrieval floors, missed-HALT checks, explicit live failure status |
| Citations | Any real corpus citation counted even when never retrieved | Citation-rate credit requires that agent to have retrieved the section |
| Embeddings | Queries used `embed_documents`; cache needed a client even on a hit | Separate query/document calls and cache keys; cached vectors work without a client |
| Dense fallback | Bad vector shape could crash or silently compare dimensions | Malformed responses/dimensions degrade to labelled lexical retrieval |
| Observability | Process-global tracker mixed simultaneous runs | Run-scoped context, concurrency regression test, SSE usage event |
| Simulation | Live stream reread demo data and approved by default | Uses emitted readings, rejects by default, no case-memory writes or notifications |
| Approval API | Loose strings beginning with `a` approved; ambiguous run selection | Exact decisions, run id required when ambiguous, queue registration only when paused |
| Setup | Development install omitted runtime; non-UTF-8 Windows pip failed | Complete development requirements and declared requirements encoding |
| Docker | Host log mount could be unwritable; learned memory vanished | Named volumes, localhost bindings; CI checks startup and shipped corpus |
| Frontend | Six dependency findings | Vite 6.4.3 and refreshed lockfile; build and audit pass |

## Evidence and how to reproduce it

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m ruff check .
python -m eval.run_eval --fail-under 1.0 --retrieval-fail-under 0.85
python -m stream.run
cd webapp/frontend
npm ci
npm run build
npm audit --audit-level=high
```

- Policy: 208/208 checks, including HALT precision/recall 1.0.
- Retrieval: lexical hit rate at 4 of 86.54%, MRR 0.820; direct 100%, paraphrase 41.67%.
  The legacy JSON key `recall@k` means any relevant passage found (hit rate), not
  fraction of every relevant passage retrieved. The labelled alternatives are acceptable
  evidence sources. This distinction matters when comparing external benchmarks.
- Graph integration: all 34 cases run through actual LangGraph nodes, routing,
  checkpointing and interrupts with scripted specialists and real deterministic tools.
  These checks do **not** measure language-model tool selection or prose quality.
- Default stream: seed 7, 48 ticks, 192 readings, one wake, 0.52% wake rate.
- The generated scorecard lives in `eval/results/`. Unit tests isolate audit and case memory.

## Remaining gaps

1. No model or embedding key was supplied in this workspace. Paid/live-provider quality,
   dense/hybrid retrieval relevance, provider token billing and remote Langfuse delivery
   remain unmeasured. The four provider-dependent tests stay skipped, not reported as passes.
2. Docker is unavailable on the local Windows host. Image/Compose validation must run
   in GitHub Actions or on a machine with Docker. Do not interpret a YAML parse as a boot test.
3. The live backend is a localhost demonstration: no user authentication, durable
   approval queue or distributed checkpoint store. Email links can be visited by mail
   scanners and must not be exposed as production approval authorization. Slack HMAC is
   tested locally; no real Slack or SMTP message was sent during this review.
4. Safety/RUL are demonstration heuristics. A successful test is not industrial safety
   certification. An LLM can omit a required tool or propose an inadequately checked action;
   the live harness measures this but cannot prove semantic safety.
5. Citation existence and retrieval provenance are checked, not claim entailment.
   Numeric grounding is a heuristic, and labels remain single-annotator. Paraphrase
   retrieval is still weak; do not relabel PRF's small gain as solved semantic retrieval.
6. Existing replay/GIF and contributor ownership statements were preserved. Replay shows
   a prior recorded successful run, not a freshly benchmarked live run. Team ownership
   needs to remain something each named contributor can personally substantiate.

## Reviewer presentation

Start with the replay, then show the graph's interrupt and the generated scorecard. Explain
one integration failure the original unit suite missed: a normal machine was routed HIGH
because historical case text mentioned a bearing failure. Show the new full-graph case
that catches it. Separate measured deterministic guarantees from unmeasured live quality.
This is stronger evidence than adding more agents or a vector database to a 12-document corpus.

## Complexity review

For a five-person course project, the current single-process graph and in-memory retrieval
are proportionate (requirement-to-complexity estimate: 4/10). The avoidable maintenance
burden is duplicated status claims across README/CLAUDE/docs (V1), not a missing platform.
Do not add vector infrastructure until corpus size or measured latency requires it. Keep
PRF optional until a larger held-out set demonstrates a reliable benefit. Keep live auto-
approval limited to explicit simulations. Do not publish the live backend until identity,
approval durability and deployment ownership are defined. No invented maintenance-hours
estimate or named operational owner is supplied: neither was established by the evidence.
