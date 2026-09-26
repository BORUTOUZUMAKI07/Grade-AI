from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UtcDatetime

PredictiveModel = Literal["decision_tree", "logistic_regression"]

class PredictionRequest(BaseModel):
    study_hours: float = Field(..., ge=0.0, le=24.0)
    attendance: float = Field(..., ge=0.0, le=100.0)
    previous_marks: float = Field(..., ge=0.0, le=100.0)
    student_id: int | None = None
    model: PredictiveModel = "decision_tree"

class StudentRecord(BaseModel):
    study_hours: float
    attendance: float
    previous_marks: float
    result: str

class SimilarStudent(StudentRecord):
    distance: float

class PredictionResponse(BaseModel):
    predicted_result: str
    confidence_score: float
    confidence_kind: str = "unspecified"
    confidence_note: str = "Confidence score semantics depend on the selected model."
    pass_probability: float
    similar_students: list[SimilarStudent]
    explanation: list[str]
    model_source: str
    metadata: dict
    raw_records: list[StudentRecord]
    selected_model: str = "decision_tree"
    engine_status: str = "COMPLETED"

class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: int | None = None
    student_name: str | None = None
    study_hours: float
    attendance: float
    previous_marks: float
    result: str
    confidence: float
    pass_probability: float
    model_name: str = "decision_tree"
    created_at: UtcDatetime

class BatchRow(BaseModel):
    label: str | None = Field(None, max_length=120)
    study_hours: float = Field(..., ge=0.0, le=24.0)
    attendance: float = Field(..., ge=0.0, le=100.0)
    previous_marks: float = Field(..., ge=0.0, le=100.0)
    student_id: int | None = None

class BatchRequest(BaseModel):
    rows: list[BatchRow] = Field(..., min_length=1, max_length=500)
    model: PredictiveModel = "decision_tree"

class BatchResult(BaseModel):
    label: str | None
    study_hours: float
    attendance: float
    previous_marks: float
    predicted_result: str
    confidence_score: float
    pass_probability: float
    selected_model: str = "decision_tree"

class BatchResponse(BaseModel):
    results: list[BatchResult]
    passed: int
    failed: int
