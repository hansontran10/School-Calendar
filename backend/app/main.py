import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import Response as RawResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import Base, engine, get_db
from app.dedupe import make_dedupe_key
from app.extraction.pdf import PdfError, pdf_to_text
from app.extraction.prompt import ExtractionContext
from app.extraction.providers import PROVIDERS, ProviderError, extract
from app.extraction.rules import parse_no_class_dates, review_flags, to_start
from app.ics import build_ics
from app.schemas import (
    CourseCreate,
    CourseOut,
    DeadlineCreate,
    DeadlineOut,
    DeadlineUpdate,
    SyllabusOut,
    check_timezone,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Deadline Sync", version="0.1.0")


def now() -> datetime:
    return datetime.now(UTC)


def get_course_or_404(db: Session, course_id: int) -> models.Course:
    course = db.get(models.Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")
    return course


def get_deadline_or_404(db: Session, deadline_id: int) -> models.Deadline:
    deadline = db.get(models.Deadline, deadline_id)
    if deadline is None:
        raise HTTPException(status_code=404, detail="deadline not found")
    return deadline


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/courses", response_model=CourseOut, status_code=201)
def create_course(body: CourseCreate, db: Session = Depends(get_db)) -> models.Course:
    if body.term_start and body.term_end and body.term_end < body.term_start:
        raise HTTPException(status_code=422, detail="term_end is before term_start")
    course = models.Course(**body.model_dump(), created_at=now())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@app.get("/courses", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db)) -> list[models.Course]:
    return list(db.scalars(select(models.Course).order_by(models.Course.code)))


@app.post("/deadlines", response_model=DeadlineOut, status_code=201)
def create_deadline(body: DeadlineCreate, db: Session = Depends(get_db)) -> models.Deadline:
    course = get_course_or_404(db, body.course_id) if body.course_id else None
    data = body.model_dump()
    deadline = models.Deadline(
        **data,
        source="manual",
        status="confirmed",
        dedupe_key=make_dedupe_key(course.code if course else None, body.title, body.starts_at, body.timezone),
        created_at=now(),
        updated_at=now(),
    )
    db.add(deadline)
    db.commit()
    db.refresh(deadline)
    return deadline


@app.get("/deadlines", response_model=list[DeadlineOut])
def list_deadlines(
    course_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[models.Deadline]:
    query = select(models.Deadline).order_by(models.Deadline.starts_at)
    if course_id is not None:
        query = query.where(models.Deadline.course_id == course_id)
    if status is not None:
        query = query.where(models.Deadline.status == status)
    return list(db.scalars(query))


@app.get("/deadlines/{deadline_id}", response_model=DeadlineOut)
def get_deadline(deadline_id: int, db: Session = Depends(get_db)) -> models.Deadline:
    return get_deadline_or_404(db, deadline_id)


@app.patch("/deadlines/{deadline_id}", response_model=DeadlineOut)
def update_deadline(
    deadline_id: int, body: DeadlineUpdate, db: Session = Depends(get_db)
) -> models.Deadline:
    deadline = get_deadline_or_404(db, deadline_id)
    changes = body.model_dump(exclude_unset=True)
    required = ("title", "kind", "starts_at", "all_day", "timezone")
    if any(field in changes and changes[field] is None for field in required):
        raise HTTPException(status_code=422, detail="required fields cannot be null")
    if "course_id" in changes and changes["course_id"] is not None:
        get_course_or_404(db, changes["course_id"])
    for field, value in changes.items():
        setattr(deadline, field, value)
    if changes.get("starts_at") is not None and "no_date" in (deadline.review_flags or []):
        deadline.review_flags = [f for f in deadline.review_flags if f != "no_date"]

    course = db.get(models.Course, deadline.course_id) if deadline.course_id else None
    deadline.dedupe_key = make_dedupe_key(
        course.code if course else None, deadline.title, deadline.starts_at, deadline.timezone
    )
    deadline.updated_at = now()
    db.commit()
    db.refresh(deadline)
    return deadline


@app.delete("/deadlines/{deadline_id}", status_code=204)
def delete_deadline(deadline_id: int, db: Session = Depends(get_db)) -> Response:
    deadline = get_deadline_or_404(db, deadline_id)
    db.delete(deadline)
    db.commit()
    return Response(status_code=204)


@app.get("/export/ics")
def export_ics(
    course_id: int | None = None,
    db: Session = Depends(get_db),
) -> RawResponse:
    """Confirmed deadlines as an .ics file. Pending and rejected items are left out."""
    query = select(models.Deadline).where(
        models.Deadline.status == "confirmed", models.Deadline.starts_at.is_not(None)
    )
    if course_id is not None:
        query = query.where(models.Deadline.course_id == course_id)
    deadlines = list(db.scalars(query.order_by(models.Deadline.starts_at)))
    return RawResponse(
        content=build_ics(deadlines),
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="deadlines.ics"'},
    )


@app.post("/deadlines/{deadline_id}/confirm", response_model=DeadlineOut)
def confirm_deadline(deadline_id: int, db: Session = Depends(get_db)) -> models.Deadline:
    deadline = get_deadline_or_404(db, deadline_id)
    if deadline.starts_at is None:
        raise HTTPException(status_code=422, detail="set a date before confirming")
    deadline.status = "confirmed"
    deadline.updated_at = now()
    db.commit()
    db.refresh(deadline)
    return deadline


@app.post("/deadlines/{deadline_id}/reject", response_model=DeadlineOut)
def reject_deadline(deadline_id: int, db: Session = Depends(get_db)) -> models.Deadline:
    """Rejected items are kept (not deleted) so re-uploading the same syllabus does not bring them back."""
    deadline = get_deadline_or_404(db, deadline_id)
    deadline.status = "rejected"
    deadline.updated_at = now()
    db.commit()
    db.refresh(deadline)
    return deadline


def get_extractor() -> Callable:
    """Overridden in tests so no real API is called."""
    return extract


@app.post("/syllabi", response_model=SyllabusOut, status_code=201)
async def upload_syllabus(
    course_id: int = Form(...),
    file: UploadFile = File(...),
    timezone: str = Form("America/New_York"),
    no_class_dates: str | None = Form(None, description="Comma-separated YYYY-MM-DD dates"),
    provider: str | None = Form(None, description="claude, openai, or gemini; others are fallbacks"),
    db: Session = Depends(get_db),
    extractor: Callable = Depends(get_extractor),
) -> SyllabusOut:
    course = get_course_or_404(db, course_id)
    try:
        check_timezone(timezone)
        no_class = parse_no_class_dates(no_class_dates)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if provider is not None and provider not in PROVIDERS:
        raise HTTPException(status_code=422, detail=f"provider must be one of {sorted(PROVIDERS)}")

    # The PDF is read into memory and never written to disk or the database.
    data = await file.read()
    try:
        text = pdf_to_text(data)
    except PdfError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    ctx = ExtractionContext(
        term_start=course.term_start,
        term_end=course.term_end,
        course_code=course.code,
        no_class_dates=no_class,
    )
    try:
        result, used = extractor(text, ctx, preferred=provider)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    syllabus = models.Syllabus(
        course_id=course.id,
        sha256=hashlib.sha256(data).hexdigest(),
        provider=used,
        items_found=len(result.items),
        created_at=now(),
    )
    db.add(syllabus)
    db.flush()

    existing_keys = set(db.scalars(select(models.Deadline.dedupe_key).where(models.Deadline.course_id == course.id)))
    created: list[models.Deadline] = []
    skipped: list[str] = []
    for item in result.items:
        starts_at, all_day = to_start(item, timezone)
        key = make_dedupe_key(course.code, item.title, starts_at, timezone)
        if key in existing_keys:
            skipped.append(item.title)
            continue
        existing_keys.add(key)
        deadline = models.Deadline(
            course_id=course.id,
            syllabus_id=syllabus.id,
            title=item.title,
            kind=item.kind,
            starts_at=starts_at,
            all_day=all_day,
            timezone=timezone,
            source="syllabus",
            source_ref=str(syllabus.id),
            status="pending_review",
            confidence=item.confidence,
            raw_text=item.raw_text,
            review_flags=review_flags(item, ctx),
            dedupe_key=key,
            created_at=now(),
            updated_at=now(),
        )
        db.add(deadline)
        created.append(deadline)

    db.commit()
    for d in created:
        db.refresh(d)
    return SyllabusOut(
        id=syllabus.id,
        course_id=course.id,
        provider=used,
        items_found=len(result.items),
        created=[DeadlineOut.model_validate(d) for d in created],
        skipped_duplicates=skipped,
    )
