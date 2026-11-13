"""Checks run on every extracted item, whichever model produced it. The model is not trusted."""

import re
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.extraction.prompt import ExtractionContext
from app.extraction.schema import ExtractedItem

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_WEEKDAY_RE = re.compile(r"\b(" + "|".join(WEEKDAYS) + r"|mon|tues?|wed|thur?s?|fri|sat|sun)\b", re.I)
_ABBREV = {"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3, "fri": 4, "sat": 5, "sun": 6}


def weekdays_named(text: str) -> set[int]:
    found = set()
    for match in _WEEKDAY_RE.findall(text):
        word = match.lower()
        found.add(WEEKDAYS.index(word) if word in WEEKDAYS else _ABBREV[word])
    return found


def review_flags(item: ExtractedItem, ctx: ExtractionContext) -> list[str]:
    flags: list[str] = []
    if item.due_date is None:
        flags.append("no_date")
    else:
        if ctx.term_start and item.due_date < ctx.term_start:
            flags.append("before_term")
        if ctx.term_end and item.due_date > ctx.term_end:
            flags.append("after_term")
        named = weekdays_named(item.raw_text)
        if len(named) == 1 and item.due_date.weekday() not in named:
            flags.append("weekday_mismatch")
        if item.due_date in ctx.no_class_dates:
            flags.append("on_no_class_date")
    if item.confidence == "low":
        flags.append("low_confidence")
    return flags


def to_start(item: ExtractedItem, timezone: str) -> tuple[datetime | None, bool]:
    """(starts_at, all_day). Items with no time become all-day events at local midnight."""
    if item.due_date is None:
        return None, True
    tz = ZoneInfo(timezone)
    if item.due_time is None:
        return datetime.combine(item.due_date, time(0, 0), tzinfo=tz), True
    return datetime.combine(item.due_date, item.due_time, tzinfo=tz), False


def parse_no_class_dates(raw: str | None) -> list[date]:
    if not raw:
        return []
    return [date.fromisoformat(part.strip()) for part in raw.split(",") if part.strip()]
