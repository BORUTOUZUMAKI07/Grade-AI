import re

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Prediction, SchoolClass, Student, User
from app.db.session import get_db
from app.dependencies.auth import get_current_user, owned_or_404, staff_only
from app.api.endpoints.students import _latest_by_student
from app.services.report_service import build_class_report, build_student_report

router = APIRouter()


def _pdf(content: bytes, name: str) -> Response:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "report"
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe}.pdf"'})


@router.get("/students/{student_id}")
def student_report(student_id: int, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    s = owned_or_404(db, Student, student_id, user, "Student")
    class_name = db.get(SchoolClass, s.class_id).name if s.class_id else None
    preds = list(db.scalars(select(Prediction).where(Prediction.student_id == s.id)
                            .order_by(Prediction.created_at.desc(), Prediction.id.desc()).limit(100)))
    return _pdf(build_student_report(s, class_name, preds, user.full_name), f"report-{s.full_name}")


@router.get("/classes/{class_id}")
def class_report(class_id: int, user: User = Depends(staff_only), db: Session = Depends(get_db)):
    c = owned_or_404(db, SchoolClass, class_id, user, "Class")
    students = list(db.scalars(select(Student).where(Student.class_id == c.id, Student.owner_id == user.id).order_by(Student.full_name)))
    latest = _latest_by_student(db, [s.id for s in students])
    rows = [{"name": s.full_name, "roll_no": s.roll_no,
             "result": latest[s.id].result if s.id in latest else None,
             "probability": latest[s.id].pass_probability if s.id in latest else None,
             "checked": latest[s.id].created_at if s.id in latest else None} for s in students]
    return _pdf(build_class_report(c.name, rows, user.full_name), f"class-{c.name}")


@router.get("/me")
def my_report(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """A student's own PDF report, built from their prediction history (they own no Student row)."""
    preds = list(db.scalars(select(Prediction).where(Prediction.user_id == user.id)
                            .order_by(Prediction.created_at.desc(), Prediction.id.desc()).limit(100)))
    fake_student = type("S", (), {"full_name": user.full_name, "roll_no": user.email})
    return _pdf(build_student_report(fake_student, None, preds, user.full_name), f"report-{user.full_name}")
