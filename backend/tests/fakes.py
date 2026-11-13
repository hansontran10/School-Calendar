import json

from app.extraction.schema import ExtractionResult

SAMPLE_RESULT = {
    "course": {"code": "BIO 101", "name": "Introduction to Biology"},
    "items": [
        {"title": "Lab Report 1", "kind": "assignment", "due_date": "2027-01-22", "due_time": "23:59",
         "raw_text": "Lab Report 1 due Friday, January 22 at 11:59pm on Moodle.", "confidence": "high", "notes": None},
        {"title": "Exam 1", "kind": "exam", "due_date": "2027-02-18", "due_time": None,
         "raw_text": "Exam 1 in class on Thursday, February 18.", "confidence": "high", "notes": None},
        {"title": "Project proposal", "kind": "project", "due_date": "2027-03-02", "due_time": None,
         "raw_text": "Group project proposal due Week 8 Monday.", "confidence": "medium", "notes": "resolved from Week 8"},
        {"title": "Final exam", "kind": "exam", "due_date": None, "due_time": None,
         "raw_text": "Final exam: date TBA by the registrar.", "confidence": "low", "notes": None},
    ],
}


class FakeProvider:
    """Returns queued replies in order. Records every call."""

    def __init__(self, name: str, replies: list):
        self.name = name
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str, schema: dict) -> str:
        self.calls.append((system, user))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)


def fake_extractor(result: dict = SAMPLE_RESULT, name: str = "fake"):
    def run(text, ctx, preferred=None):
        return ExtractionResult.model_validate(result), name

    return run
