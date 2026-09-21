# Technical reference corpus

The documents in this folder are what the Reliability and Compliance agents retrieve
from at run time via the `search_technical_docs` tool. They are chunked by section and
indexed by `rag/index.py`.

## Provenance (read this before citing anything here)

Two kinds of document live here, and both are labelled in their own front matter:

| `provenance` | Meaning |
|---|---|
| `internal-synthetic` | A Titan Manufacturing engineering standard written for this project. It is realistic and internally consistent, but it is not a real company document. |
| `public-standard-paraphrase` | A plain-language paraphrase of a publicly available standard or regulation (OSHA, ISO, IATF). It is a summary written for retrieval, not the regulatory text. Always defer to the published source for compliance decisions. |

Nothing here is copied from a copyrighted publication, and no document is attributed to
a real company as if it were that company's own manual.

## Section anchors

Every retrievable chunk is a `## S<n> ...` section. A citation is `doc_id#S<n>`, for
example `osha-1910-147-loto#S3`. The retriever returns that anchor with every passage so
an agent can cite the exact section it relied on, and a human can check it.
