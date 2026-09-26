from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.intelligence_service import run_service, train_all, MODEL_DIR

router = APIRouter()

class WeatherInput(BaseModel):
    day_of_year: int = Field(180, ge=1, le=366)
    humidity: float = Field(55, ge=0, le=100)
    rainfall: float = Field(0, ge=0, le=500)
    wind_speed: float = Field(5, ge=0, le=250)

class SalesInput(BaseModel):
    price: float = Field(30, ge=0)
    promotion: int = Field(0, ge=0, le=1)
    ad_spend: float = Field(100, ge=0)
    season: float = Field(0, ge=-1, le=1)

class CustomerInput(BaseModel):
    annual_spend: float = Field(..., ge=0)
    orders_per_year: float = Field(..., ge=0)
    avg_order_value: float = Field(..., ge=0)
    days_since_last_order: float = Field(..., ge=0, le=3650)

@router.get("/status")
def status():
    metrics_path = MODEL_DIR / "metrics.json"
    return {"available": metrics_path.exists(), "services": ["grade", "weather", "sales", "customers"]}

@router.post("/train")
def train():
    try:
        return {"status":"trained","metrics":train_all()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Training failed: {exc}") from exc

@router.post("/weather/predict")
def weather(payload: WeatherInput):
    try: return run_service("weather",payload.model_dump())
    except Exception as exc: raise HTTPException(status_code=500,detail=str(exc)) from exc

@router.post("/sales/predict")
def sales(payload: SalesInput):
    try: return run_service("sales",payload.model_dump())
    except Exception as exc: raise HTTPException(status_code=500,detail=str(exc)) from exc

@router.post("/customers/segment")
def customers(payload: CustomerInput):
    try: return run_service("customers",payload.model_dump())
    except Exception as exc: raise HTTPException(status_code=500,detail=str(exc)) from exc
