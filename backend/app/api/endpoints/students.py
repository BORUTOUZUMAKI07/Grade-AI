from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.core.pagination import PageParams, make_page, paginate
from app.db.models import Prediction, SchoolClass, Student, User
from app.db.session import get_db
from app.dependencies.auth import owned_or_404, staff_only
from app.schemas.common import Page
from app.schemas.school import ImportRequest, ImportResult, StudentCreate, StudentOut, StudentUpdate

router = APIRouter()


def _latest_by_student(db: Session, ids: list[int]) -> dict[int, Prediction]:
    if not ids:
        return {}
    latest: dict[int, Prediction] = {}
    for p in db.scalars(select(Prediction).where(Prediction.student_id.in_(ids))
                        .order_by(Prediction.created_at.desc(), Prediction.id.desc())):
        latest.setdefault(p.student_id, p)
    return latest


def _out(s: Student, class_name: str | None, last: Prediction | None) -> StudentOut:
    return StudentOut(id=s.id, full_name=s.full_name, roll_no=s.roll_no, class_id=s.class_id, class_name=class_name,
                      last_result=last.result if last else None,
                      last_pass_probability=last.pass_probability if last else None,
                      last_checked=last.created_at if last else None, created_at=s.created_at)


def _clean_roll(roll: str | None) -> str | None:
    return roll.strip() or None if roll else None


def _check_roll_free(db: Session, user: User, roll: str | None, ignore_id: int | None = None) -> None:
    if not roll:
        return
    found = db.scalar(select(Student.id).where(Student.owner_id == user.id, Student.roll_no == roll))
    if found is not None and found != ignore_id:
        raise ConflictError(f"Roll number {roll} is already used by another student.")


def _class_name(db: Session, user: User, class_id: int | None) -> str | None:
    return owned_or_404(db, SchoolClass, class_id, user, "Class").name if class_id is not None else None


@router.get("", response_model=Page[StudentOut])
def list_students(
    q: str | None = Query(None, max_length=100),
    class_id: int | None = Query(None),
    params: PageParams = Depends(),
    user: User = Depends(staff_only),
    db: Session = Depends(get_db),
):
    stmt = (select(Student, SchoolClass.name)
            .outerjoin(SchoolClass, Student.class_id == SchoolClass.id).where(Student.owner_id == user.id))
    if class_id is not None:
        stmt = stmt.where(Student.class_id == class_id)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Student.full_name.ilike(like), Student.roll_no.ilike(like)))
    rows, total = paginate(db, stmt.order_by(Student.full_name, Student.id), params, scalars=False)
    latest = _latest_by_student(db, [s.id for s, _ in rows])
    return make_page([_out(s, cn, latest.get(s.id)) for s, cn in rows], total, params)


@router.post("", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    roll = _clean_roll(payload.roll_no)
    _check_roll_free(db, user, roll)
    class_name = _class_name(db, user, payload.class_id)
    s = Student(owner_id=user.id, full_name=payload.full_name.strip(), roll_no=roll, class_id=payload.class_id)
    db.add(s)
    db.commit()
    return _out(s, class_name, None)


@router.post("/import", response_model=ImportResult)
def import_students(payload: ImportRequest, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    _class_name(db, user, payload.class_id)
    taken = set(db.scalars(select(Student.roll_no).where(Student.owner_id == user.id, Student.roll_no.is_not(None))))
    created = skipped = 0
    for row in payload.rows:
        roll = _clean_roll(row.roll_no)
        if roll and roll in taken:
            skipped += 1
            continue
        db.add(Student(owner_id=user.id, full_name=row.full_name.strip(), roll_no=roll, class_id=payload.class_id))
        if roll:
            taken.add(roll)
        created += 1
    db.commit()
    return ImportResult(created=created, skipped=skipped)


@router.patch("/{student_id}", response_model=StudentOut)
def update_student(student_id: int, payload: StudentUpdate, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    s = owned_or_404(db, Student, student_id, user, "Student")
    data = payload.model_dump(exclude_unset=True)
    if "roll_no" in data:
        data["roll_no"] = _clean_roll(data["roll_no"])
        _check_roll_free(db, user, data["roll_no"], ignore_id=s.id)
    if "class_id" in data:
        _class_name(db, user, data["class_id"])
    if data.get("full_name") is not None:
        data["full_name"] = data["full_name"].strip()
    for k, v in data.items():
        if k == "full_name" and v is None:
            continue
        setattr(s, k, v)
    db.commit()
    latest = _latest_by_student(db, [s.id]).get(s.id)
    return _out(s, _class_name(db, user, s.class_id), latest)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: int, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    s = owned_or_404(db, Student, student_id, user, "Student")
    db.execute(update(Prediction).where(Prediction.student_id == s.id).values(student_id=None))  # keep the history rows
    db.delete(s)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
