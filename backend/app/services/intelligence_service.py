"""Lightweight CPU-friendly intelligence services trained on reproducible demo datasets."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "service_data"
MODEL_DIR = ROOT / "model_store" / "intelligence"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

def _datasets():
    rng = np.random.default_rng(42)
    n = 1200
    days = pd.date_range("2022-01-01", periods=n, freq="D")
    weather = pd.DataFrame({"day": days, "day_of_year": days.dayofyear,
        "humidity": rng.uniform(20, 95, n), "rainfall": rng.gamma(1.4, 2, n),
        "wind_speed": rng.uniform(0, 35, n)})
    weather["temperature"] = 27 + 7*np.sin(2*np.pi*weather.day_of_year/365.25) - .045*(weather.humidity-55) - .08*weather.rainfall + rng.normal(0,2,n)
    sales = pd.DataFrame({"day": days, "price": rng.uniform(5, 100, n),
        "promotion": rng.integers(0,2,n), "ad_spend": rng.uniform(0,500,n),
        "season": np.sin(2*np.pi*days.dayofyear/365.25)})
    sales["sales"] = np.maximum(0, 120 + 2.4*sales.ad_spend + 32*sales.promotion - 1.1*sales.price + 45*sales.season + rng.normal(0,35,n))
    m = 1000
    customers = pd.DataFrame({"annual_spend": rng.gamma(4, 180, m),
        "orders_per_year": rng.poisson(12,m)+1, "avg_order_value": rng.gamma(3,25,m),
        "days_since_last_order": rng.integers(1,365,m)})
    for name, frame in (("weather.csv",weather),("sales.csv",sales),("customers.csv",customers)):
        frame.to_csv(DATA_DIR/name,index=False)
    return weather,sales,customers

def train_all():
    weather,sales,customers = _datasets()
    report={}
    # Weather: hold out the latest 20% to respect chronology.
    wx=["day_of_year","humidity","rainfall","wind_speed"]
    cut=int(len(weather)*.8)
    wm=RandomForestRegressor(n_estimators=100,max_depth=10,random_state=42,n_jobs=1)
    wm.fit(weather.iloc[:cut][wx],weather.iloc[:cut].temperature)
    wp=wm.predict(weather.iloc[cut:][wx])
    report["weather"]={"model":"RandomForestRegressor","mae":float(mean_absolute_error(weather.iloc[cut:].temperature,wp)),"test_rows":len(wp)}
    # Sales forecasting regression with chronological holdout.
    sx=["price","promotion","ad_spend","season"]
    sm=RandomForestRegressor(n_estimators=100,max_depth=12,random_state=42,n_jobs=1)
    sm.fit(sales.iloc[:cut][sx],sales.iloc[:cut].sales)
    sp=sm.predict(sales.iloc[cut:][sx])
    report["sales"]={"model":"RandomForestRegressor","mae":float(mean_absolute_error(sales.iloc[cut:].sales,sp)),"rmse":float(mean_squared_error(sales.iloc[cut:].sales,sp)**.5),"test_rows":len(sp)}
    cx=["annual_spend","orders_per_year","avg_order_value","days_since_last_order"]
    scaler=StandardScaler().fit(customers[cx])
    km=KMeans(n_clusters=4,n_init=10,random_state=42).fit(scaler.transform(customers[cx]))
    report["customers"]={"model":"KMeans","clusters":4,"inertia":float(km.inertia_),"rows":len(customers)}
    # Persist fitted models using JSON-compatible model parameters, avoiding pickle loading risks.
    artifacts={
      "weather.json":{"kind":"random_forest_regressor","features":wx,"estimators":[{"features":tree.tree_.feature.tolist(),"thresholds":tree.tree_.threshold.tolist(),"children_left":tree.tree_.children_left.tolist(),"children_right":tree.tree_.children_right.tolist(),"values":tree.tree_.value.reshape(-1).tolist()} for tree in wm.estimators_]},
      "sales.json":{"kind":"random_forest_regressor","features":sx,"estimators":[{"features":tree.tree_.feature.tolist(),"thresholds":tree.tree_.threshold.tolist(),"children_left":tree.tree_.children_left.tolist(),"children_right":tree.tree_.children_right.tolist(),"values":tree.tree_.value.reshape(-1).tolist()} for tree in sm.estimators_]},
      "customers.json":{"kind":"kmeans","features":cx,"mean":scaler.mean_.tolist(),"scale":scaler.scale_.tolist(),"centers":km.cluster_centers_.tolist()}
    }
    for name,obj in artifacts.items():
        (MODEL_DIR/name).write_text(json.dumps(obj),encoding="utf-8")
    (MODEL_DIR/"metrics.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

def _predict_tree_forest(artifact, values):
    x=[float(values[k]) for k in artifact["features"]]
    preds=[]
    for t in artifact["estimators"]:
        node=0
        while t["children_left"][node] != -1:
            node=t["children_left"][node] if x[t["features"][node]] <= t["thresholds"][node] else t["children_right"][node]
        preds.append(t["values"][node])
    return float(np.mean(preds))

def run_service(service:str, values:dict):
    if not list(MODEL_DIR.glob("*.json")) or not (MODEL_DIR/"metrics.json").exists():
        train_all()
    if service in ("weather","sales"):
        artifact=json.loads((MODEL_DIR/f"{service}.json").read_text())
        prediction=_predict_tree_forest(artifact,values)
        return {"service":service,"prediction":round(prediction,3),"unit":"°C" if service=="weather" else "sales units","model":artifact["kind"]}
    if service=="customers":
        a=json.loads((MODEL_DIR/"customers.json").read_text())
        x=np.array([float(values[k]) for k in a["features"]])
        z=(x-np.array(a["mean"]))/np.where(np.array(a["scale"])==0,1,np.array(a["scale"]))
        d=np.linalg.norm(np.array(a["centers"])-z,axis=1)
        return {"service":"customers","cluster":int(np.argmin(d))+1,"distance":round(float(np.min(d)),3),"clusters":len(a["centers"]),"model":"KMeans"}
    raise ValueError("Unknown service")
