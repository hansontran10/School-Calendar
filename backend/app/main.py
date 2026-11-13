from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import Base, engine, get_db
from app.dedupe import make_dedupe_key
from app.schemas import (
    CourseCreate,
    CourseOut,
    DeadlineCreate,
    DeadlineOut,
    DeadlineUpdate,
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
