from datetime import datetime
from zoneinfo import ZoneInfo

from app.schemas import normalize


def make_dedupe_key(course_code: str | None, title: str, starts_at: datetime, timezone: str) -> str:
    """Course + title + local calendar date. Same key means probably the same deadline."""
    local_date = starts_at.astimezone(ZoneInfo(timezone)).date().isoformat()
    return f"{normalize(course_code or '')}|{normalize(title)}|{local_date}"
