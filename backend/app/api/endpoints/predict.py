from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.pagination import PageParams, make_page, paginate
from app.core.rate_limit import RateLimiter
from app.db.models import Prediction, Student, User
from app.db.session import get_db
from app.dependencies.auth import get_current_user, owned_or_404, staff_only
from app.dependencies.container import get_inference_service
from app.schemas.common import Page
from app.schemas.prediction import (BatchRequest, BatchResponse, HistoryItem, PredictionRequest, PredictionResponse)
from app.services.inference_service import StudentInferenceService

router = APIRouter()
_single = RateLimiter(60, 60)
_batch = RateLimiter(10, 60)


def _history_item(p: Prediction, student_name: str | None) -> HistoryItem:
    return HistoryItem(id=p.id, student_id=p.student_id, student_name=student_name, study_hours=p.study_hours,
                       attendance=p.attendance, previous_marks=p.previous_marks, result=p.result,
                       confidence=p.confidence, pass_probability=p.pass_probability, created_at=p.created_at)


@router.get("/models")
def available_models(service: StudentInferenceService = Depends(get_inference_service),
                     user: User = Depends(get_current_user)):
    return {"models": service.available_models(),
            "analytics_available": bool(service.analytics().get("summary"))}


@router.get("/analytics")
def model_analytics(service: StudentInferenceService = Depends(get_inference_service),
                    user: User = Depends(staff_only)):
    return service.analytics()


@router.post("/", response_model=PredictionResponse, status_code=status.HTTP_200_OK)
def process_prediction(payload: PredictionRequest,
    service: StudentInferenceService = Depends(get_inference_service),
    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _single.check(f"u{user.id}")
    _single.hit(f"u{user.id}")
    if payload.student_id is not None:
        owned_or_404(db, Student, payload.student_id, user, "Student")
    result = service.execute_tree_classification(payload.study_hours, payload.attendance,
                                                 payload.previous_marks, payload.model)
    db.add(Prediction(user_id=user.id, student_id=payload.student_id,
        study_hours=payload.study_hours, attendance=payload.attendance, previous_marks=payload.previous_marks,
        result=result["predicted_result"], confidence=result["confidence_score"],
        pass_probability=result["pass_probability"]))
    db.commit()
    return result


@router.post("/batch", response_model=BatchResponse)
def batch_predict(payload: BatchRequest, service: StudentInferenceService = Depends(get_inference_service),
    user: User = Depends(staff_only), db: Session = Depends(get_db)):
    _batch.check(f"u{user.id}")
    _batch.hit(f"u{user.id}")
    ids = {r.student_id for r in payload.rows if r.student_id is not None}
    if ids:
        owned = set(db.scalars(select(Student.id).where(Student.id.in_(ids), Student.owner_id == user.id)))
        if owned != ids:
            raise NotFoundError("Student")
    results = service.execute_batch([r.model_dump() for r in payload.rows], payload.model)
    db.add_all(Prediction(user_id=user.id, student_id=r.get("student_id"),
        study_hours=r["study_hours"], attendance=r["attendance"], previous_marks=r["previous_marks"],
        result=r["predicted_result"], confidence=r["confidence_score"],
        pass_probability=r["pass_probability"]) for r in results)
    db.commit()
    passed = sum(1 for r in results if r["predicted_result"] == "Pass")
    return {"results": results, "passed": passed, "failed": len(results) - passed}


@router.get("/history", response_model=Page[HistoryItem])
def prediction_history(student_id: int | None = Query(None), params: PageParams = Depends(),
    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = (select(Prediction, Student.full_name).outerjoin(Student, Prediction.student_id == Student.id)
            .where(Prediction.user_id == user.id))
    if student_id is not None:
        stmt = stmt.where(Prediction.student_id == student_id)
    stmt = stmt.order_by(Prediction.created_at.desc(), Prediction.id.desc())
    rows, total = paginate(db, stmt, params, scalars=False)
    return make_page([_history_item(p, name) for p, name in rows], total, params)
