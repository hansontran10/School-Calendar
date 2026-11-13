from datetime import date, time

from app.extraction.prompt import ExtractionContext, build_user_prompt
from app.extraction.rules import parse_no_class_dates, review_flags, to_start, weekdays_named
from app.extraction.schema import JSON_SCHEMA, ExtractedItem, ExtractionResult

CTX = ExtractionContext(term_start=date(2027, 1, 11), term_end=date(2027, 5, 7), no_class_dates=[date(2027, 3, 8)])


def item(**kw):
    base = dict(title="X", kind="assignment", due_date=date(2027, 2, 18), due_time=None,
                raw_text="Exam on Thursday", confidence="high", notes=None)
    base.update(kw)
    return ExtractedItem(**base)


def test_clean_item_has_no_flags():
    assert review_flags(item(), CTX) == []  # Feb 18 2027 is a Thursday


def test_weekday_mismatch():
    assert "weekday_mismatch" in review_flags(item(raw_text="due Friday"), CTX)


def test_two_weekdays_named_is_not_checked():
    assert "weekday_mismatch" not in review_flags(item(raw_text="Mon or Fri"), CTX)


def test_abbreviated_weekdays():
    assert weekdays_named("due Thurs.") == {3}
    assert weekdays_named("Tue/Wed lab") == {1, 2}
    assert weekdays_named("Monday") == {0}


def test_outside_term_and_no_class_date():
    assert "before_term" in review_flags(item(due_date=date(2027, 1, 1), raw_text="x"), CTX)
    assert "after_term" in review_flags(item(due_date=date(2027, 6, 1), raw_text="x"), CTX)
    assert "on_no_class_date" in review_flags(item(due_date=date(2027, 3, 8), raw_text="x"), CTX)


def test_no_date_and_low_confidence():
    flags = review_flags(item(due_date=None, confidence="low", raw_text="TBA"), CTX)
    assert flags == ["no_date", "low_confidence"]


def test_to_start():
    start, all_day = to_start(item(), "America/New_York")
    assert all_day and start.isoformat() == "2027-02-18T00:00:00-05:00"
    start, all_day = to_start(item(due_time=time(23, 59)), "America/New_York")
    assert not all_day and start.isoformat() == "2027-02-18T23:59:00-05:00"
    assert to_start(item(due_date=None), "America/New_York") == (None, True)


def test_parse_no_class_dates():
    assert parse_no_class_dates("2027-03-08, 2027-03-09") == [date(2027, 3, 8), date(2027, 3, 9)]
    assert parse_no_class_dates(None) == []


def test_prompt_includes_term_and_text():
    p = build_user_prompt("SYLLABUS BODY", CTX)
    assert "2027-01-11" in p and "2027-05-07" in p and "2027-03-08" in p and "SYLLABUS BODY" in p


def test_json_schema_matches_pydantic_fields():
    item_schema = JSON_SCHEMA["properties"]["items"]["items"]
    assert set(item_schema["required"]) == set(ExtractedItem.model_fields)
    assert set(JSON_SCHEMA["required"]) == set(ExtractionResult.model_fields)
