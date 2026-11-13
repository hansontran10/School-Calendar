from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

from app.models import Deadline

PRODID = "-//Deadline Sync//EN"
DEFAULT_DURATION = timedelta(hours=1)


def _uid(deadline_id: int) -> str:
    # Stable across exports so calendar apps update events instead of duplicating them.
    return f"deadline-{deadline_id}@deadline-sync"


def build_ics(deadlines: list[Deadline]) -> bytes:
    cal = Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", "Deadline Sync")

    for d in deadlines:
        event = Event()
        event.add("uid", _uid(d.id))
        event.add("summary", d.title)
        event.add("dtstamp", d.updated_at.astimezone(UTC))
        if d.raw_text:
            event.add("description", d.raw_text)

        local_start = d.starts_at.astimezone(ZoneInfo(d.timezone))
        if d.all_day:
            # All-day events use a DATE value. The end date is exclusive, so add one day.
            event.add("dtstart", local_start.date())
            event.add("dtend", local_start.date() + timedelta(days=1))
        else:
            event.add("dtstart", d.starts_at.astimezone(UTC))
            event.add("dtend", (d.starts_at + DEFAULT_DURATION).astimezone(UTC))
        cal.add_component(event)

    return cal.to_ical()
