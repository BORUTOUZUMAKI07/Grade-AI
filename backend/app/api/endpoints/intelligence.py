from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.intelligence_service import run_service, train_all, train_service, get_metrics, FEATURES

router=APIRouter()
class WeatherInput(BaseModel):
 day_of_year:int=Field(180,ge=1,le=366); humidity:float=Field(55,ge=0,le=100); rainfall:float=Field(0,ge=0,le=500); wind_speed:float=Field(5,ge=0,le=250); model:str="Linear Regression"
class SalesInput(BaseModel):
 price:float=Field(30,ge=0); promotion:int=Field(0,ge=0,le=1); ad_spend:float=Field(100,ge=0); season:float=Field(0,ge=-1,le=1); model:str="Linear Regression"
class CustomerInput(BaseModel):
 annual_spend:float=Field(...,ge=0); orders_per_year:float=Field(...,ge=0); avg_order_value:float=Field(...,ge=0); days_since_last_order:float=Field(...,ge=0,le=3650); model:str="K-Means"
def _train(service):
 try:return train_service(service)
 except Exception as exc:raise HTTPException(status_code=500,detail=f"{service} training failed: {exc}") from exc
def _predict(service,payload):
 try:
  data=payload.model_dump(); model=data.pop("model","Linear Regression"); return run_service(service,data,model)
 except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
 except Exception as exc:raise HTTPException(status_code=500,detail=f"{service} inference failed: {exc}") from exc
@router.get("/status")
def status():return {"available":True,"services":list(FEATURES),"metrics":get_metrics()}
@router.get("/{service}/analytics")
def analytics(service:str):
 if service not in FEATURES:raise HTTPException(404,"Unknown service")
 return get_metrics(service)
@router.post("/train")
def train_everything():
 try:return {"status":"trained","services":train_all()}
 except Exception as exc:raise HTTPException(500,detail=f"Training failed: {exc}") from exc
@router.post("/train/{service}")
def train_one(service:str):
 if service not in FEATURES:raise HTTPException(404,"Unknown service")
 return _train(service)
@router.post("/weather/predict")
def weather(payload:WeatherInput):return _predict("weather",payload)
@router.post("/sales/predict")
def sales(payload:SalesInput):return _predict("sales",payload)
@router.post("/customers/segment")
def customers(payload:CustomerInput):return _predict("customers",payload)
