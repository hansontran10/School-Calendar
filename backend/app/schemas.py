import re
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

Kind = Literal["assignment", "exam", "quiz", "project", "reading", "other"]


def check_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown timezone: {value}") from exc
    return value


class CourseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=200)
    term_start: date | None = None
    term_end: date | None = None


class CourseOut(CourseCreate):
    id: int
    model_config = {"from_attributes": True}


class DeadlineCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: Kind = "other"
    starts_at: datetime
    all_day: bool = False
    timezone: str = "America/New_York"
    course_id: int | None = None
    raw_text: str | None = None

    @field_validator("starts_at")
    @classmethod
    def must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("starts_at must include a timezone offset")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        return check_timezone(value)


class DeadlineUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Kind | None = None
    starts_at: datetime | None = None
    all_day: bool | None = None
    timezone: str | None = None
    course_id: int | None = None

    @field_validator("starts_at")
    @classmethod
    def must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("starts_at must include a timezone offset")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        return check_timezone(value) if value is not None else None


class DeadlineOut(BaseModel):
    id: int
    course_id: int | None
    title: str
    kind: str
    starts_at: datetime | None
    all_day: bool
    timezone: str
    source: str
    status: str
    confidence: str | None
    raw_text: str | None
    review_flags: list[str]
    dedupe_key: str
    model_config = {"from_attributes": True}


class SyllabusOut(BaseModel):
    id: int
    course_id: int
    provider: str
    items_found: int
    created: list[DeadlineOut]
    skipped_duplicates: list[str]


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, drop filler words. Used for dedupe keys."""
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    words = [w for w in text.split() if w not in {"due", "the", "a", "an"}]
    return " ".join(words)
