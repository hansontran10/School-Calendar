from datetime import datetime

from app.dedupe import make_dedupe_key
from app.schemas import normalize


def make_course(client, code="BIO 101"):
    r = client.post("/courses", json={"code": code, "name": "Biology", "term_start": "2027-01-11", "term_end": "2027-05-07"})
    assert r.status_code == 201
    return r.json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_get_deadline(client):
    course = make_course(client)
    body = {"title": "Exam 1", "kind": "exam", "starts_at": "2027-02-18T09:30:00-05:00", "course_id": course["id"]}
    r = client.post("/deadlines", json=body)
    assert r.status_code == 201
    created = r.json()
    assert created["source"] == "manual"
    assert created["status"] == "confirmed"
    assert created["timezone"] == "America/New_York"
    assert created["dedupe_key"] == "bio 101|exam 1|2027-02-18"

    r = client.get(f"/deadlines/{created['id']}")
    assert r.status_code == 200
    assert r.json()["title"] == "Exam 1"


def test_starts_at_without_timezone_is_rejected(client):
    r = client.post("/deadlines", json={"title": "Quiz", "starts_at": "2027-02-18T09:30:00"})
    assert r.status_code == 422


def test_unknown_timezone_is_rejected(client):
    r = client.post("/deadlines", json={"title": "Quiz", "starts_at": "2027-02-18T09:30:00-05:00", "timezone": "Mars/Olympus"})
    assert r.status_code == 422


def test_unknown_kind_is_rejected(client):
    r = client.post("/deadlines", json={"title": "Quiz", "kind": "party", "starts_at": "2027-02-18T09:30:00-05:00"})
    assert r.status_code == 422


def test_filter_by_course_and_status(client):
    a = make_course(client, "BIO 101")
    b = make_course(client, "HIS 200")
    client.post("/deadlines", json={"title": "Essay", "starts_at": "2027-03-01T23:59:00-05:00", "course_id": a["id"]})
    client.post("/deadlines", json={"title": "Paper", "starts_at": "2027-03-02T23:59:00-05:00", "course_id": b["id"]})

    only_bio = client.get("/deadlines", params={"course_id": a["id"]}).json()
    assert [d["title"] for d in only_bio] == ["Essay"]
    assert len(client.get("/deadlines", params={"status": "confirmed"}).json()) == 2
    assert client.get("/deadlines", params={"status": "pending_review"}).json() == []


def test_list_is_sorted_by_start_time(client):
    client.post("/deadlines", json={"title": "Late", "starts_at": "2027-04-01T12:00:00-04:00"})
    client.post("/deadlines", json={"title": "Early", "starts_at": "2027-02-01T12:00:00-05:00"})
    titles = [d["title"] for d in client.get("/deadlines").json()]
    assert titles == ["Early", "Late"]


def test_patch_updates_fields_and_recomputes_key(client):
    course = make_course(client)
    d = client.post("/deadlines", json={"title": "Exam 1", "starts_at": "2027-02-18T09:30:00-05:00", "course_id": course["id"]}).json()
    r = client.patch(f"/deadlines/{d['id']}", json={"title": "Midterm", "starts_at": "2027-02-19T09:30:00-05:00"})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Midterm"
    assert body["dedupe_key"] == "bio 101|midterm|2027-02-19"


def test_patch_cannot_null_required_fields(client):
    d = client.post("/deadlines", json={"title": "Quiz", "starts_at": "2027-02-18T09:30:00-05:00"}).json()
    assert client.patch(f"/deadlines/{d['id']}", json={"timezone": None}).status_code == 422
    assert client.patch(f"/deadlines/{d['id']}", json={"starts_at": None}).status_code == 422
    assert client.patch(f"/deadlines/{d['id']}", json={"starts_at": "2027-02-18T09:30:00"}).status_code == 422


def test_patch_missing_course_is_404(client):
    d = client.post("/deadlines", json={"title": "Quiz", "starts_at": "2027-02-18T09:30:00-05:00"}).json()
    assert client.patch(f"/deadlines/{d['id']}", json={"course_id": 9999}).status_code == 404


def test_delete(client):
    d = client.post("/deadlines", json={"title": "Quiz", "starts_at": "2027-02-18T09:30:00-05:00"}).json()
    assert client.delete(f"/deadlines/{d['id']}").status_code == 204
    assert client.get(f"/deadlines/{d['id']}").status_code == 404


def test_missing_deadline_is_404(client):
    assert client.get("/deadlines/12345").status_code == 404


def test_term_end_before_start_is_rejected(client):
    r = client.post("/courses", json={"code": "X", "term_start": "2027-05-01", "term_end": "2027-01-01"})
    assert r.status_code == 422


def test_dedupe_key_ignores_case_punctuation_and_filler_words():
    a = make_dedupe_key("BIO-101", "Due: The Lab Report!", datetime.fromisoformat("2027-02-18T09:30:00-05:00"), "America/New_York")
    b = make_dedupe_key("bio 101", "lab report", datetime.fromisoformat("2027-02-18T23:00:00-05:00"), "America/New_York")
    assert a == b
    assert normalize("Due: The Lab Report!") == "lab report"
