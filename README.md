# Deadline Sync

Work in progress. Course deadlines from syllabi, Moodle, and manual entry in one place.

## Backend (FastAPI)

```bash
cd backend
python -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload     # http://localhost:8000/docs
pytest -q
```

Data is stored in SQLite by default (`DATABASE_URL` to change it).

## Status

- [x] Deadline and course CRUD with validation (timezone-aware datetimes, known timezones, required fields)
- [x] Dedupe key (course + title + local date)
- [ ] .ics export
- [ ] Syllabus upload and LLM extraction
- [ ] Review screen
- [ ] Google Calendar sync
- [ ] Moodle iCal import
