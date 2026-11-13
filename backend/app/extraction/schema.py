"""The shape every provider must return, as Pydantic models and as a plain JSON Schema.

The JSON Schema is written by hand (not generated) so it stays inside the subset that
OpenAI strict mode, Gemini, and Claude tool input all accept: every property required,
no extra properties, and nullable fields expressed as ["type", "null"].
"""

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

KINDS = ["assignment", "exam", "quiz", "project", "reading", "other"]
CONFIDENCE = ["high", "medium", "low"]


class ExtractedCourse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = None
    name: str | None = None


class ExtractedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["assignment", "exam", "quiz", "project", "reading", "other"]
    due_date: date | None
    due_time: time | None
    raw_text: str
    confidence: Literal["high", "medium", "low"]
    notes: str | None = None


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course: ExtractedCourse
    items: list[ExtractedItem]


def _nullable(description: str) -> dict:
    return {"type": ["string", "null"], "description": description}


JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["course", "items"],
    "properties": {
        "course": {
            "type": "object",
            "additionalProperties": False,
            "required": ["code", "name"],
            "properties": {
                "code": _nullable("Course code such as 'BIO 101', or null"),
                "name": _nullable("Course title, or null"),
            },
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "kind", "due_date", "due_time", "raw_text", "confidence", "notes"],
                "properties": {
                    "title": {"type": "string", "description": "Short name, e.g. 'Exam 1' or 'Lab Report 2'"},
                    "kind": {"type": "string", "enum": KINDS},
                    "due_date": _nullable("YYYY-MM-DD, or null if the syllabus gives no resolvable date"),
                    "due_time": _nullable("HH:MM in 24-hour time, or null if no time is stated"),
                    "raw_text": {"type": "string", "description": "The exact phrase from the syllabus this item came from"},
                    "confidence": {"type": "string", "enum": CONFIDENCE},
                    "notes": _nullable("Anything the student should double-check, or null"),
                },
            },
        },
    },
}
