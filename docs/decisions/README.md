# Decision records

Short notes on the calls that shaped this system, including the ones we reversed and the
one we measured and rejected. One page each: what the situation was, what we chose, and
what it cost us.

Written for the next person who asks "why is it like this", and for us in six months.

| | Decision | Status |
|---|---|---|
| [001](001-split-decisions-between-model-and-code.md) | Split the decisions between the model and code | Accepted |
| [002](002-chunk-the-corpus-by-section.md) | Chunk the corpus by section, not by fixed window | Accepted |
| [003](003-safety-rule-as-a-conjunction.md) | Express the safety rule as a conjunction | Accepted, replaces a keyword list |
| [004](004-reject-query-expansion.md) | Do not make query expansion the default | Rejected on measurement |
| [005](005-publish-eval-results-to-a-branch.md) | Publish evaluation results to a branch | Accepted |
| [006](006-count-tokens-in-process.md) | Count tokens in process, not via the tracing SaaS | Accepted |
| [007](007-approval-gate-is-write-once.md) | Make the approval gate write-once | Accepted, fixes a real bug |
