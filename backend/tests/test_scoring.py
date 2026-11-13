from eval.run_eval import load_cases
from eval.scoring import score


def test_perfect_match():
    gold = [{"title": "Exam 1", "due_date": "2027-02-18"}, {"title": "Final", "due_date": None}]
    s = score(gold, [{"title": "exam 1", "due_date": "2027-02-18"}, {"title": "Final", "due_date": None}])
    assert (s.recall, s.precision, s.date_accuracy) == (1.0, 1.0, 1.0)


def test_wrong_date_missing_item_and_extra_item():
    gold = [
        {"title": "Problem Set 1", "due_date": "2027-01-20"},
        {"title": "Quiz 1", "due_date": "2027-01-29"},
        {"title": "Midterm exam", "due_date": "2027-02-24"},
    ]
    predicted = [
        {"title": "Problem set 1", "due_date": "2027-01-20"},
        {"title": "Midterm", "due_date": "2027-02-17"},  # matched, wrong date
        {"title": "Office hours", "due_date": "2027-01-12"},  # not a real item
    ]
    s = score(gold, predicted)
    assert s.matched == 2
    assert s.recall == 2 / 3
    assert s.precision == 2 / 3
    assert s.date_accuracy == 1 / 3  # only Problem Set 1 is right; Quiz 1 was missed


def test_each_item_matches_once():
    gold = [{"title": "Lab 1", "due_date": "2027-01-20"}, {"title": "Lab 2", "due_date": "2027-01-27"}]
    predicted = [{"title": "Lab 1", "due_date": "2027-01-20"}, {"title": "Lab 1", "due_date": "2027-01-20"}]
    s = score(gold, predicted)
    assert s.matched == 2 and s.dates_correct == 1


def test_example_case_loads():
    cases = load_cases("example")
    assert len(cases) == 1
    name, text, gold = cases[0]
    assert "Midterm exam: Week 7 Wednesday." in text
    assert len(gold["items"]) == 6
