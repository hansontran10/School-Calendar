import pytest
from icalendar import Calendar

from app.extraction.providers import ProviderError
from app.main import app, get_extractor
from tests.fakes import fake_extractor
from tests.pdfgen import SAMPLE_LINES, make_pdf


@pytest.fixture()
def course(client):
    return client.post("/courses", json={"code": "BIO 101", "term_start": "2027-01-11", "term_end": "2027-05-07"}).json()


@pytest.fixture(autouse=True)
def use_fake_extractor():
    app.dependency_overrides[get_extractor] = fake_extractor
    yield
    app.dependency_overrides.clear()


def upload(client, course_id, pdf=None, **form):
    files = {"file": ("syllabus.pdf", pdf or make_pdf(SAMPLE_LINES), "application/pdf")}
    return client.post("/syllabi", data={"course_id": course_id, **form}, files=files)


def test_upload_creates_pending_items_with_flags(client, course):
    r = upload(client, course["id"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["provider"] == "fake" and body["items_found"] == 4
    items = {d["title"]: d for d in body["created"]}
    assert all(d["status"] == "pending_review" and d["source"] == "syllabus" for d in items.values())
    assert items["Lab Report 1"]["review_flags"] == []
    assert items["Lab Report 1"]["all_day"] is False
    assert items["Lab Report 1"]["starts_at"].startswith("2027-01-22T")
    assert items["Exam 1"]["all_day"] is True
    assert items["Final exam"]["starts_at"] is None
    assert items["Final exam"]["review_flags"] == ["no_date", "low_confidence"]
    # Pending items are not exported.
    assert b"VEVENT" not in client.get("/export/ics").content


def test_reupload_skips_duplicates_including_rejected(client, course):
    first = upload(client, course["id"]).json()
    lab = next(d for d in first["created"] if d["title"] == "Lab Report 1")
    client.post(f"/deadlines/{lab['id']}/reject")
    second = upload(client, course["id"]).json()
    assert second["created"] == []
    assert sorted(second["skipped_duplicates"]) == ["Exam 1", "Final exam", "Lab Report 1", "Project proposal"]


def test_manual_deadline_blocks_syllabus_duplicate(client, course):
    client.post("/deadlines", json={"title": "Exam 1!", "starts_at": "2027-02-18T10:00:00-05:00", "course_id": course["id"]})
    body = upload(client, course["id"]).json()
    assert "Exam 1" in body["skipped_duplicates"]


def test_confirm_flow(client, course):
    created = upload(client, course["id"]).json()["created"]
    final = next(d for d in created if d["title"] == "Final exam")
    assert client.post(f"/deadlines/{final['id']}/confirm").status_code == 422

    patched = client.patch(f"/deadlines/{final['id']}", json={"starts_at": "2027-05-05T08:00:00-04:00"}).json()
    assert "no_date" not in patched["review_flags"]
    confirmed = client.post(f"/deadlines/{final['id']}/confirm").json()
    assert confirmed["status"] == "confirmed"

    cal = Calendar.from_ical(client.get("/export/ics").content)
    assert [str(e["SUMMARY"]) for e in cal.walk() if e.name == "VEVENT"] == ["Final exam"]


def test_bad_inputs(client, course):
    assert upload(client, course["id"], pdf=b"not a pdf").status_code == 422
    assert upload(client, course["id"], provider="llama").status_code == 422
    assert upload(client, course["id"], timezone="Nowhere/Land").status_code == 422
    assert upload(client, course["id"], no_class_dates="March 8").status_code == 422
    assert upload(client, 999).status_code == 404


def test_provider_failure_is_502(client, course):
    def failing(text, ctx, preferred=None):
        raise ProviderError("all providers failed")

    app.dependency_overrides[get_extractor] = lambda: failing
    r = upload(client, course["id"])
    assert r.status_code == 502 and "all providers failed" in r.json()["detail"]


def test_extractor_receives_term_and_preferred_provider(client, course):
    seen = {}

    def spy(text, ctx, preferred=None):
        seen.update(text=text, ctx=ctx, preferred=preferred)
        return fake_extractor()(text, ctx, preferred)

    app.dependency_overrides[get_extractor] = lambda: spy
    upload(client, course["id"], provider="gemini", no_class_dates="2027-03-08")
    assert seen["preferred"] == "gemini"
    assert str(seen["ctx"].term_start) == "2027-01-11"
    assert [str(d) for d in seen["ctx"].no_class_dates] == ["2027-03-08"]
    assert "Exam 1 in class" in seen["text"]
