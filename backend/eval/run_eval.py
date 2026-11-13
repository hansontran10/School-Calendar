"""Run extraction with each provider on every labeled syllabus and report accuracy.

Layout:
  eval/syllabi/<name>.pdf or <name>.txt   the syllabus (gitignored: do not commit real ones)
  eval/gold/<name>.json                   hand-labeled answers (committed)

Gold file format:
  {"term_start": "2027-01-11", "term_end": "2027-05-07", "no_class_dates": ["2027-03-08"],
   "items": [{"title": "Exam 1", "due_date": "2027-02-18"}, {"title": "Final exam", "due_date": null}]}

Usage (from backend/):
  python -m eval.run_eval --providers claude,openai,gemini
  python -m eval.run_eval --providers claude --only bio101

Calls real APIs and costs money. Needs the API key and model env vars for each provider.
"""

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

from app.extraction.pdf import pdf_to_text
from app.extraction.prompt import ExtractionContext
from app.extraction.providers import extract, make_provider
from app.extraction.rules import review_flags
from eval.scoring import Score, score

ROOT = Path(__file__).parent


def load_cases(only: str | None) -> list[tuple[str, str, dict]]:
    cases = []
    for gold_path in sorted((ROOT / "gold").glob("*.json")):
        name = gold_path.stem
        if only and name != only:
            continue
        pdf, txt = ROOT / "syllabi" / f"{name}.pdf", ROOT / "syllabi" / f"{name}.txt"
        if pdf.exists():
            text = pdf_to_text(pdf.read_bytes())
        elif txt.exists():
            text = txt.read_text()
        else:
            print(f"skip {name}: no syllabus file in eval/syllabi/", file=sys.stderr)
            continue
        cases.append((name, text, json.loads(gold_path.read_text())))
    return cases


def context(gold: dict) -> ExtractionContext:
    def d(v):
        return date.fromisoformat(v) if v else None

    return ExtractionContext(
        term_start=d(gold.get("term_start")),
        term_end=d(gold.get("term_end")),
        no_class_dates=[date.fromisoformat(x) for x in gold.get("no_class_dates", [])],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--providers", default="claude,openai,gemini")
    parser.add_argument("--only", help="run a single syllabus by name")
    args = parser.parse_args()

    cases = load_cases(args.only)
    if not cases:
        print("no cases found: add eval/gold/<name>.json and eval/syllabi/<name>.pdf", file=sys.stderr)
        return 1

    report = {"run_at": datetime.now(UTC).isoformat(), "cases": len(cases), "providers": {}}
    for name in [p.strip() for p in args.providers.split(",") if p.strip()]:
        provider = make_provider(name)
        totals = Score(0, 0, 0, 0, 0)
        flagged = errors = 0
        seconds = 0.0
        per_case = {}
        for case_name, text, gold in cases:
            ctx = context(gold)
            started = time.perf_counter()
            try:
                result, _ = extract(text, ctx, providers=[provider])
            except Exception as exc:
                errors += 1
                per_case[case_name] = {"error": str(exc)}
                result = None
            seconds += time.perf_counter() - started
            predicted = [] if result is None else [
                {"title": i.title, "due_date": i.due_date} for i in result.items
            ]
            s = score(gold["items"], predicted)
            flagged += 0 if result is None else sum(1 for i in result.items if review_flags(i, ctx))
            for field in ("gold", "predicted", "matched", "dates_correct", "gold_with_date"):
                setattr(totals, field, getattr(totals, field) + getattr(s, field))
            per_case.setdefault(case_name, {}).update(recall=s.recall, precision=s.precision, date_accuracy=s.date_accuracy)

        report["providers"][name] = {
            "model": provider.model,
            "recall": round(totals.recall, 3),
            "precision": round(totals.precision, 3),
            "date_accuracy": round(totals.date_accuracy, 3),
            "items_flagged_for_review": flagged,
            "errors": errors,
            "avg_seconds_per_syllabus": round(seconds / len(cases), 2),
            "per_case": per_case,
        }

    print(f"{'provider':10} {'model':28} {'recall':>7} {'prec':>7} {'dates':>7} {'flagged':>8} {'errors':>7} {'sec/doc':>8}")
    for name, r in report["providers"].items():
        print(f"{name:10} {r['model'][:28]:28} {r['recall']:7.1%} {r['precision']:7.1%} {r['date_accuracy']:7.1%}"
              f" {r['items_flagged_for_review']:8d} {r['errors']:7d} {r['avg_seconds_per_syllabus']:8.2f}")

    out = ROOT / "results" / f"{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(f"\nwrote {out.relative_to(ROOT.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
