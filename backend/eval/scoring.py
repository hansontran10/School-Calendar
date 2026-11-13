"""Compare extracted items against hand-labeled gold items."""

from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher

from app.schemas import normalize

TITLE_MATCH_THRESHOLD = 0.6


@dataclass
class Score:
    gold: int
    predicted: int
    matched: int
    dates_correct: int
    gold_with_date: int

    @property
    def recall(self) -> float:
        return self.matched / self.gold if self.gold else 1.0

    @property
    def precision(self) -> float:
        return self.matched / self.predicted if self.predicted else 1.0

    @property
    def date_accuracy(self) -> float:
        # Unmatched gold items count as wrong, so missing an item hurts this number too.
        return self.dates_correct / self.gold_with_date if self.gold_with_date else 1.0


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def score(gold: list[dict], predicted: list[dict]) -> Score:
    """gold and predicted are lists of {"title": str, "due_date": "YYYY-MM-DD" | None}.

    Items are paired greedily by title similarity, best pairs first, each used once.
    """
    pairs = sorted(
        ((_similarity(g["title"], p["title"]), gi, pi) for gi, g in enumerate(gold) for pi, p in enumerate(predicted)),
        reverse=True,
    )
    used_g, used_p, matches = set(), set(), []
    for sim, gi, pi in pairs:
        if sim < TITLE_MATCH_THRESHOLD:
            break
        if gi in used_g or pi in used_p:
            continue
        used_g.add(gi)
        used_p.add(pi)
        matches.append((gi, pi))

    def as_date(v):
        return date.fromisoformat(v) if isinstance(v, str) else v

    dates_correct = sum(
        1 for gi, pi in matches
        if gold[gi].get("due_date") and as_date(gold[gi]["due_date"]) == as_date(predicted[pi].get("due_date"))
    )
    return Score(
        gold=len(gold),
        predicted=len(predicted),
        matched=len(matches),
        dates_correct=dates_correct,
        gold_with_date=sum(1 for g in gold if g.get("due_date")),
    )
