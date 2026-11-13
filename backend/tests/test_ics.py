from icalendar import Calendar


def parse(response_bytes):
    return Calendar.from_ical(response_bytes)


def test_export_contains_confirmed_timed_and_all_day_events(client):
    course = client.post("/courses", json={"code": "BIO 101"}).json()
    client.post("/deadlines", json={"title": "Exam 1", "kind": "exam", "starts_at": "2027-02-18T09:30:00-05:00", "course_id": course["id"], "raw_text": "Exam 1, Feb 18"})
    client.post("/deadlines", json={"title": "Reading", "starts_at": "2027-02-20T00:00:00-05:00", "all_day": True})

    r = client.get("/export/ics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    cal = parse(r.content)
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(events) == 2
    by_summary = {str(e["SUMMARY"]): e for e in events}

    exam = by_summary["Exam 1"]
    assert str(exam["UID"]).startswith("deadline-")
    assert exam["DTSTART"].dt.isoformat() == "2027-02-18T14:30:00+00:00"  # 9:30 EST in UTC
    assert str(exam["DESCRIPTION"]) == "Exam 1, Feb 18"

    reading = by_summary["Reading"]
    assert reading["DTSTART"].dt.isoformat() == "2027-02-20"
    assert reading["DTEND"].dt.isoformat() == "2027-02-21"


def test_uids_are_stable_across_exports(client):
    client.post("/deadlines", json={"title": "Quiz", "starts_at": "2027-02-18T09:30:00-05:00"})
    first = [str(c["UID"]) for c in parse(client.get("/export/ics").content).walk() if c.name == "VEVENT"]
    second = [str(c["UID"]) for c in parse(client.get("/export/ics").content).walk() if c.name == "VEVENT"]
    assert first == second


def test_pending_and_rejected_items_are_excluded(client):
    from app.db import SessionLocal
    from app import models
    from app.main import now

    client.post("/deadlines", json={"title": "Confirmed", "starts_at": "2027-02-18T09:30:00-05:00"})
    db = SessionLocal()
    db.add(models.Deadline(title="Draft", kind="other", starts_at=now(), all_day=False, timezone="America/New_York",
                           source="syllabus", status="pending_review", dedupe_key="d", created_at=now(), updated_at=now()))
    db.commit()
    db.close()

    cal = parse(client.get("/export/ics").content)
    summaries = [str(c["SUMMARY"]) for c in cal.walk() if c.name == "VEVENT"]
    assert summaries == ["Confirmed"]


def test_course_filter(client):
    a = client.post("/courses", json={"code": "A"}).json()
    b = client.post("/courses", json={"code": "B"}).json()
    client.post("/deadlines", json={"title": "A1", "starts_at": "2027-02-18T09:30:00-05:00", "course_id": a["id"]})
    client.post("/deadlines", json={"title": "B1", "starts_at": "2027-02-18T09:30:00-05:00", "course_id": b["id"]})
    cal = parse(client.get("/export/ics", params={"course_id": a["id"]}).content)
    assert [str(c["SUMMARY"]) for c in cal.walk() if c.name == "VEVENT"] == ["A1"]
