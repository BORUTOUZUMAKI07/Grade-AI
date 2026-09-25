from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UtcDatetime


class UserAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: UtcDatetime
    prediction_count: int = 0


class UserUpdate(BaseModel):
    role: Literal["admin", "teacher", "student"] | None = None
    is_active: bool | None = None


class DayCount(BaseModel):
    day: str
    count: int


class StatsOut(BaseModel):
    total_users: int
    active_users: int
    total_predictions: int
    pass_rate: float
    users_by_role: dict[str, int]
    predictions_by_day: list[DayCount]
