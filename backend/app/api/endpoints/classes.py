from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.core.pagination import PageParams, make_page, paginate
from app.db.models import SchoolClass, Student, User
from app.db.session import get_db
from app.dependencies.auth import owned_or_404, staff_only
from app.schemas.common import Page
from app.schemas.school import ClassCreate, ClassOut

router = APIRouter()


def _out(c: SchoolClass, n: int) -> ClassOut:
    return ClassOut(id=c.id, name=c.name, student_count=n, created_at=c.created_at)


def _name_free(db: Session, user: User, name: str, ignore_id: int | None = None) -> None:
    stmt = select(SchoolClass.id).where(SchoolClass.owner_id == user.id, func.lower(SchoolClass.name) == name.lower())
    found = db.scalar(stmt)
    if found is not None and found != ignore_id:
        raise ConflictError("You already have a class with this name.")


@router.get("", response_model=Page[ClassOut])
def list_classes(params: PageParams = Depends(), user: User = Depends(staff_only), db: Session = Depends(get_db)):
    counts = select(Student.class_id, func.count().label("n")).group_by(Student.class_id).subquery()
    stmt = (select(SchoolClass, func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.class_id == SchoolClass.id)
            .where(SchoolClass.owner_id == user.id).order_by(SchoolClass.name))
    rows, total = paginate(db, stmt, params, scalars=False)
    return make_page([_out(c, n) for c, n in rows], total, params)


@router.post("", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassCreate, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    name = payload.name.strip()
    _name_free(db, user, name)
    c = SchoolClass(owner_id=user.id, name=name)
    db.add(c)
    db.commit()
    return _out(c, 0)


@router.patch("/{class_id}", response_model=ClassOut)
def rename_class(class_id: int, payload: ClassCreate, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    c = owned_or_404(db, SchoolClass, class_id, user, "Class")
    name = payload.name.strip()
    _name_free(db, user, name, ignore_id=c.id)
    c.name = name
    db.commit()
    n = db.scalar(select(func.count()).select_from(Student).where(Student.class_id == c.id)) or 0
    return _out(c, n)


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(class_id: int, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    c = owned_or_404(db, SchoolClass, class_id, user, "Class")
    db.execute(update(Student).where(Student.class_id == c.id).values(class_id=None))  # students are kept
    db.delete(c)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
