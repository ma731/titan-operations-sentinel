"""Small, explicit metric helpers. No sklearn: the arithmetic should be readable."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Tally:
    """Correct-out-of-total for a single-label metric."""

    name: str
    correct: int = 0
    total: int = 0
    misses: list[dict] = field(default_factory=list)

    def add(self, ok: bool, case_id: str = "", expected=None, actual=None, note: str = "") -> None:
        self.total += 1
        if ok:
            self.correct += 1
        else:
            self.misses.append({"case": case_id, "expected": expected, "actual": actual,
                                **({"note": note} if note else {})})

    @property
    def accuracy(self) -> float | None:
        return (self.correct / self.total) if self.total else None

    def to_dict(self) -> dict:
        return {"metric": self.name, "correct": self.correct, "total": self.total,
                "accuracy": round(self.accuracy, 4) if self.accuracy is not None else None,
                "misses": self.misses}


@dataclass
class BinaryConfusion:
    """Precision, recall and F1 for one positive class.

    Used for the safety HALT class, where the two error types are not equally bad: a
    missed HALT (false negative) is a safety failure, a spurious HALT (false positive) is
    an availability cost. Reporting a single accuracy number would hide that asymmetry,
    which is exactly the number a reviewer will ask about."""

    name: str
    positive_label: str = "positive"
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    errors: list[dict] = field(default_factory=list)

    def add(self, expected_positive: bool, actual_positive: bool, case_id: str = "",
            note: str = "") -> None:
        if expected_positive and actual_positive:
            self.tp += 1
        elif expected_positive and not actual_positive:
            self.fn += 1
            self.errors.append({"case": case_id, "error": "false_negative", "note": note})
        elif not expected_positive and actual_positive:
            self.fp += 1
            self.errors.append({"case": case_id, "error": "false_positive", "note": note})
        else:
            self.tn += 1

    @property
    def precision(self) -> float | None:
        d = self.tp + self.fp
        return (self.tp / d) if d else None

    @property
    def recall(self) -> float | None:
        d = self.tp + self.fn
        return (self.tp / d) if d else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p and r) else (0.0 if (p is not None and r is not None) else None)

    def to_dict(self) -> dict:
        rnd = lambda v: round(v, 4) if v is not None else None  # noqa: E731
        return {"metric": self.name, "positive_class": self.positive_label,
                "tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn,
                "precision": rnd(self.precision), "recall": rnd(self.recall),
                "f1": rnd(self.f1), "errors": self.errors}


@dataclass
class SetScore:
    """Micro-averaged precision/recall/F1 over set-valued predictions.

    Used for tool-call correctness: the expected tools for an agent are a set, the agent
    called a set, and both a missed required tool and a pile of irrelevant calls are worth
    knowing about. Micro-averaging (pooling counts across cases) rather than macro keeps a
    case with one expected tool from outweighing a case with five."""

    name: str
    matched: int = 0
    expected_total: int = 0
    predicted_total: int = 0
    per_case: list[dict] = field(default_factory=list)

    def add(self, expected: set[str], predicted: set[str], case_id: str = "") -> None:
        hit = expected & predicted
        self.matched += len(hit)
        self.expected_total += len(expected)
        self.predicted_total += len(predicted)
        self.per_case.append({
            "case": case_id,
            "expected": sorted(expected),
            "called": sorted(predicted),
            "missing": sorted(expected - predicted),
            "extra": sorted(predicted - expected),
        })

    @property
    def recall(self) -> float | None:
        return (self.matched / self.expected_total) if self.expected_total else None

    @property
    def precision(self) -> float | None:
        return (self.matched / self.predicted_total) if self.predicted_total else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p and r) else None

    def to_dict(self, include_cases: bool = True) -> dict:
        rnd = lambda v: round(v, 4) if v is not None else None  # noqa: E731
        d = {"metric": self.name, "matched": self.matched,
             "expected_total": self.expected_total, "predicted_total": self.predicted_total,
             "precision": rnd(self.precision), "recall": rnd(self.recall), "f1": rnd(self.f1)}
        if include_cases:
            d["per_case"] = self.per_case
        return d


def recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """1.0 if any labelled-relevant item appears in the top k, else 0.0.

    This is the "did it find an answer at all" definition, which is the right one here:
    a passage list is handed to an agent, and one correct passage in it is enough for the
    agent to ground its claim. A set-coverage definition would punish the retriever for
    not returning every paraphrase of the same rule."""
    return 1.0 if set(retrieved[:k]) & set(relevant) else 0.0


def precision_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """Fraction of the top k that are labelled relevant. Low values are expected and fine
    here: with k=4 and one relevant section, the ceiling is 0.25."""
    top = retrieved[:k]
    if not top:
        return 0.0
    return len([r for r in top if r in set(relevant)]) / len(top)


def reciprocal_rank(retrieved: list[str], relevant: list[str]) -> float:
    """1/rank of the first relevant item, 0 if none. Averaged, this is MRR."""
    rel = set(relevant)
    for i, item in enumerate(retrieved, start=1):
        if item in rel:
            return 1.0 / i
    return 0.0


def mean(values: list[float]) -> float | None:
    return (sum(values) / len(values)) if values else None
