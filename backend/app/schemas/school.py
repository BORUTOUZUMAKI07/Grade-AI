from pydantic import BaseModel, Field

from app.schemas.common import UtcDatetime


class ClassCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class ClassOut(BaseModel):
    id: int
    name: str
    student_count: int
    created_at: UtcDatetime


class StudentCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=120)
    roll_no: str | None = Field(None, max_length=40)
    class_id: int | None = None


class StudentUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=120)
    roll_no: str | None = Field(None, max_length=40)
    class_id: int | None = None


class StudentOut(BaseModel):
    id: int
    full_name: str
    roll_no: str | None
    class_id: int | None
    class_name: str | None
    last_result: str | None = None
    last_pass_probability: float | None = None
    last_checked: UtcDatetime | None = None
    created_at: UtcDatetime


class ImportRow(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=120)
    roll_no: str | None = Field(None, max_length=40)


class ImportRequest(BaseModel):
    class_id: int | None = None
    rows: list[ImportRow] = Field(..., min_length=1, max_length=500)


class ImportResult(BaseModel):
    created: int
    skipped: int
