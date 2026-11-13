from dataclasses import dataclass, field
from datetime import date

SYSTEM_PROMPT = """You extract graded deadlines and exams from a college course syllabus.

Rules:
- Include assignments, exams, quizzes, projects, and readings that have a due date.
- One item per deliverable. If one line lists two deliverables, return two items.
- Resolve relative dates ("Week 6 Thursday", "the Friday after Exam 1") using the term dates given.
  Week 1 is the week containing the term start date, and weeks start on Monday.
- Skip dates that fall on the listed no-class dates unless the syllabus clearly says the item is still due.
- If no date can be determined (for example "TBA"), set due_date to null. Never guess a date.
- Dates written like 3/4 are month/day unless the syllabus clearly uses day/month.
- raw_text must be copied exactly from the syllabus.
- confidence is "high" only when the date is written explicitly; "medium" when you resolved it
  from a relative description; "low" when you are unsure.
- Do not include class meetings, office hours, or holidays as items."""


@dataclass
class ExtractionContext:
    term_start: date | None = None
    term_end: date | None = None
    course_code: str | None = None
    no_class_dates: list[date] = field(default_factory=list)


def build_user_prompt(syllabus_text: str, ctx: ExtractionContext) -> str:
    lines = ["Term information:"]
    lines.append(f"- Term start: {ctx.term_start.isoformat() if ctx.term_start else 'unknown'}")
    lines.append(f"- Term end: {ctx.term_end.isoformat() if ctx.term_end else 'unknown'}")
    if ctx.course_code:
        lines.append(f"- Course code given by the student: {ctx.course_code}")
    if ctx.no_class_dates:
        lines.append("- No-class dates: " + ", ".join(d.isoformat() for d in ctx.no_class_dates))
    lines.append("")
    lines.append("Syllabus text:")
    lines.append('"""')
    lines.append(syllabus_text)
    lines.append('"""')
    return "\n".join(lines)
