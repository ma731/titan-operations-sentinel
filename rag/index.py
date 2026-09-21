"""
Corpus loading, chunking and the lexical (BM25) half of the retriever.

The corpus lives in rag/corpus/*.md. Every retrievable chunk is one `## S<n> Title`
section, so a citation is always `doc_id#S<n>` and a human can open the exact section the
agent relied on. Section-level chunking is deliberate: these documents are already
written as self-contained clauses, so a fixed-size sliding window would cut a severity
table in half for no benefit.

BM25 is implemented here rather than pulled in as a dependency for two reasons: it is
about sixty lines, and it must run in CI with no network, no API key and no model
download so the retrieval evaluation is free and reproducible.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

CORPUS_DIR = Path(__file__).parent / "corpus"
INDEX_DIR = Path(__file__).parent / "index"

# BM25 parameters. k1 controls term-frequency saturation, b the length normalisation.
# These are the standard defaults and we have not tuned them; the eval reports what they
# achieve so any tuning later is measurable rather than asserted.
BM25_K1 = 1.5
BM25_B = 0.75

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can", "do", "does",
    "for", "from", "had", "has", "have", "how", "in", "into", "is", "it", "its", "may",
    "must", "no", "not", "of", "on", "or", "own", "so", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "to", "was", "were", "what", "when",
    "where", "which", "who", "why", "will", "with", "you", "your",
}


def _stem(word: str) -> str:
    """A deliberately small suffix stemmer. Enough to make 'bearings'/'bearing' and
    'lubricated'/'lubrication' collide, without pulling in a stemming dependency or the
    over-aggressive truncation a full Porter stemmer would apply to short domain terms."""
    for suffix in ("ations", "ation", "ingly", "ings", "ing", "edly", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords, stem. Numbers are kept:
    '1910.147' and '6.0' are meaningful query terms in this corpus."""
    raw = re.findall(r"[a-z0-9]+(?:\.[0-9]+)*", (text or "").lower())
    return [_stem(t) for t in raw if t not in _STOPWORDS and len(t) > 1]


@dataclass
class Chunk:
    """One retrievable section of one document."""

    doc_id: str
    doc_title: str
    section: str          # "S3"
    section_title: str    # "Severity bands and required response"
    text: str
    provenance: str
    tokens: list[str] = field(default_factory=list, repr=False)

    @property
    def citation(self) -> str:
        return f"{self.doc_id}#{self.section}"

    def to_passage(self, score: float | None = None) -> dict:
        p = {
            "citation": self.citation,
            "document": self.doc_title,
            "section": f"{self.section} {self.section_title}".strip(),
            "provenance": self.provenance,
            "text": self.text,
        }
        if score is not None:
            p["score"] = round(float(score), 4)
        return p


_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_SECTION = re.compile(r"^##\s+(S\d+)\s+(.*)$", re.MULTILINE)


def _front_matter(raw: str) -> tuple[dict, str]:
    """Parse the small YAML-ish header without a YAML dependency. Only flat
    `key: value` pairs are used in this corpus, so a line split is sufficient."""
    m = _FRONT_MATTER.match(raw)
    if not m:
        return {}, raw
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, raw[m.end():]


def load_chunks(corpus_dir: Path | str = CORPUS_DIR) -> list[Chunk]:
    """Read every corpus document and split it into `## S<n>` section chunks."""
    corpus_dir = Path(corpus_dir)
    chunks: list[Chunk] = []
    for path in sorted(corpus_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        meta, body = _front_matter(path.read_text(encoding="utf-8"))
        doc_id = meta.get("doc_id") or path.stem
        doc_title = meta.get("title") or doc_id
        provenance = meta.get("provenance", "unspecified")

        marks = list(_SECTION.finditer(body))
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
            section_body = body[m.end():end].strip()
            if not section_body:
                continue
            section_title = m.group(2).strip()
            # The document and section titles carry most of the topical signal, so they
            # are part of the indexed text as well as the returned passage header.
            indexed = f"{doc_title}\n{section_title}\n{section_body}"
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    doc_title=doc_title,
                    section=m.group(1),
                    section_title=section_title,
                    text=section_body,
                    provenance=provenance,
                    tokens=tokenize(indexed),
                )
            )
    return chunks


class BM25Index:
    """Okapi BM25 over the corpus chunks. Pure Python, no dependencies, no network."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.n = len(chunks)
        self.doc_len = [len(c.tokens) for c in chunks]
        self.avg_len = (sum(self.doc_len) / self.n) if self.n else 0.0
        self.tf: list[dict[str, int]] = []
        df: dict[str, int] = {}
        for c in chunks:
            counts: dict[str, int] = {}
            for t in c.tokens:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            for t in counts:
                df[t] = df.get(t, 0) + 1
        # Standard BM25 idf with the +1 inside the log so it can never go negative for a
        # term that appears in most documents (this corpus is small, so that matters).
        self.idf = {t: math.log(1 + (self.n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def score(self, query: str) -> list[float]:
        q = tokenize(query)
        scores = [0.0] * self.n
        for i in range(self.n):
            counts = self.tf[i]
            if not counts:
                continue
            norm = BM25_K1 * (1 - BM25_B + BM25_B * (self.doc_len[i] / (self.avg_len or 1)))
            s = 0.0
            for term in q:
                f = counts.get(term)
                if not f:
                    continue
                s += self.idf.get(term, 0.0) * (f * (BM25_K1 + 1)) / (f + norm)
            scores[i] = s
        return scores

    def search(self, query: str, k: int = 5) -> list[tuple[int, float]]:
        scored = list(enumerate(self.score(query)))
        scored.sort(key=lambda x: -x[1])
        return [(i, s) for i, s in scored[:k] if s > 0]


@lru_cache(maxsize=1)
def get_index() -> BM25Index:
    """Build (and cache for the process) the lexical index over the corpus."""
    return BM25Index(load_chunks())


def corpus_stats() -> dict:
    idx = get_index()
    docs = {c.doc_id for c in idx.chunks}
    return {
        "documents": len(docs),
        "chunks": idx.n,
        "avg_chunk_tokens": round(idx.avg_len, 1),
        "vocabulary": len(idx.idf),
    }


def write_manifest(path: Path | str = INDEX_DIR / "manifest.json") -> dict:
    """Persist a human-readable manifest of what is indexed. Used by the eval report and
    by anyone who wants to see the corpus contents without reading ten files."""
    idx = get_index()
    manifest = {
        "stats": corpus_stats(),
        "chunks": [
            {"citation": c.citation, "document": c.doc_title,
             "section": f"{c.section} {c.section_title}", "provenance": c.provenance,
             "tokens": len(c.tokens)}
            for c in idx.chunks
        ],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = write_manifest()
    print(json.dumps(m["stats"], indent=2))
