# Deadline Sync

Work in progress. Course deadlines from syllabi, Moodle, and manual entry in one place.

Upload a syllabus PDF and an LLM (Claude, OpenAI, or Gemini) pulls out the due dates and exams.
Every item goes to a review screen first: nothing reaches your calendar until you confirm it.

## How extraction works

1. The PDF is read in memory with pypdf. It is never saved; only its SHA-256 hash is stored.
   Scanned (image-only) PDFs are rejected for now.
2. The text, the course's term dates, and any no-class dates go to the first provider in `LLM_PROVIDERS`.
   All three providers share one JSON Schema and are called in their structured-output mode
   (Claude: forced tool call, OpenAI: strict `json_schema`, Gemini: `response_json_schema`).
3. The reply is validated with Pydantic. Invalid JSON gets one retry, then the next provider is tried.
4. The server checks every item itself and flags it for review when:
   the date is missing, outside the term, on a no-class date, on a different weekday than the
   syllabus says, or the model marked it low confidence.
5. Items that match an existing deadline (same course, title, and date, including ones you rejected)
   are skipped, so uploading the same syllabus twice adds nothing.

## Setup

### Backend (FastAPI)

```bash
cd backend
python -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # add API keys and model names
uvicorn app.main:app --reload     # http://localhost:8000/docs
pytest -q                         # no API keys needed: tests use fake providers
```

Data is stored in SQLite by default (`DATABASE_URL` to change it). There are no migrations yet:
if you pulled a schema change, delete `backend/deadline_sync.db` and restart.

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies API calls to :8000
```

## Measuring accuracy

`backend/eval/` compares providers on hand-labeled syllabi.

1. Put a syllabus in `eval/syllabi/<name>.pdf` (gitignored, so real syllabi are never committed).
2. Write the correct answers in `eval/gold/<name>.json` (see `eval/gold/example.json`).
3. Run `python -m eval.run_eval --providers claude,openai,gemini` from `backend/`.

It reports recall, precision, and date accuracy per provider, and writes the full results to
`eval/results/`. This calls the real APIs and costs a little money.

## Status

- [x] Deadline and course CRUD with validation
- [x] Dedupe key (course + title + local date)
- [x] .ics export (confirmed items; stable UIDs; all-day and timed events)
- [x] Syllabus upload and extraction with Claude, OpenAI, and Gemini, with fallback
- [x] Review screen: confirm, set a date, or reject each extracted item
- [x] Eval script for comparing providers
- [ ] Accuracy numbers on real syllabi
- [ ] Google Calendar sync
- [ ] Moodle iCal import
