from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PageParams, make_page, paginate
from app.db.models import Prediction, User
from app.db.session import get_db
from app.dependencies.auth import require_roles
from app.schemas.admin import DayCount, StatsOut, UserAdminOut, UserUpdate
from app.schemas.common import Page
from app.services.auth_service import AuthService

router = APIRouter()
admin_only = require_roles("admin")


@router.get("/users", response_model=Page[UserAdminOut])
def list_users(
    q: str | None = Query(None, max_length=100),
    role: str | None = Query(None, pattern="^(admin|teacher|student)$"),
    params: PageParams = Depends(),
    _: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    counts = select(Prediction.user_id, func.count().label("n")).group_by(Prediction.user_id).subquery()
    stmt = select(User, func.coalesce(counts.c.n, 0)).outerjoin(counts, counts.c.user_id == User.id)
    if role:
        stmt = stmt.where(User.role == role)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(User.email.ilike(like) | User.full_name.ilike(like))
    rows, total = paginate(db, stmt.order_by(User.id), params, scalars=False)
    items = [UserAdminOut.model_validate(u).model_copy(update={"prediction_count": n}) for u, n in rows]
    return make_page(items, total, params)


@router.patch("/users/{user_id}", response_model=UserAdminOut)
def update_user(user_id: int, payload: UserUpdate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("User")
    if target.id == admin.id:
        raise ConflictError("You cannot change your own role or status. Ask another admin.")
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in data.items():
        setattr(target, k, v)
    db.commit()
    if data.get("is_active") is False or "role" in data:
        AuthService(db).revoke_all(target.id)  # they must sign in again with their new access level
    n = db.scalar(select(func.count()).select_from(Prediction).where(Prediction.user_id == target.id)) or 0
    return UserAdminOut.model_validate(target).model_copy(update={"prediction_count": n})


@router.get("/stats", response_model=StatsOut)
def stats(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    total_predictions = db.scalar(select(func.count()).select_from(Prediction)) or 0
    passed = db.scalar(select(func.count()).select_from(Prediction).where(Prediction.result == "Pass")) or 0
    by_role = dict(db.execute(select(User.role, func.count()).group_by(User.role)).all())
    start = date.today() - timedelta(days=13)
    per_day = {str(d): n for d, n in db.execute(
        select(func.date(Prediction.created_at), func.count()).where(Prediction.created_at >= start.isoformat()).group_by(func.date(Prediction.created_at))).all()}
    days = [DayCount(day=str(start + timedelta(days=i)), count=per_day.get(str(start + timedelta(days=i)), 0)) for i in range(14)]
    return StatsOut(
        total_users=sum(by_role.values()),
        active_users=db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0,
        total_predictions=total_predictions, pass_rate=round(passed / total_predictions, 4) if total_predictions else 0.0,
        users_by_role=by_role, predictions_by_day=days,
    )
