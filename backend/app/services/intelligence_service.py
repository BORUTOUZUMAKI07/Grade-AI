"""Per-service CPU model suite: Linear Regression, Decision Tree, PCA and K-Means.
Each domain is trained and persisted independently. Synthetic data is explicitly demo-only.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.tree import DecisionTreeRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT=Path(__file__).resolve().parents[2]
DATA_DIR=ROOT/"service_data"; MODEL_DIR=ROOT/"model_store"/"intelligence"
DATA_DIR.mkdir(parents=True,exist_ok=True); MODEL_DIR.mkdir(parents=True,exist_ok=True)
FEATURES={
 "weather":["day_of_year","humidity","rainfall","wind_speed"],
 "sales":["price","promotion","ad_spend","season"],
 "customers":["annual_spend","orders_per_year","avg_order_value","days_since_last_order"]}
def _datasets():
 rng=np.random.default_rng(42); n=1200; days=pd.date_range("2022-01-01",periods=n,freq="D")
 w=pd.DataFrame({"day_of_year":days.dayofyear,"humidity":rng.uniform(20,95,n),"rainfall":rng.gamma(1.4,2,n),"wind_speed":rng.uniform(0,35,n)})
 w["target"]=27+7*np.sin(2*np.pi*w.day_of_year/365.25)-.045*(w.humidity-55)-.08*w.rainfall+rng.normal(0,2,n)
 s=pd.DataFrame({"price":rng.uniform(5,100,n),"promotion":rng.integers(0,2,n),"ad_spend":rng.uniform(0,500,n),"season":np.sin(2*np.pi*days.dayofyear/365.25)})
 s["target"]=np.maximum(0,120+2.4*s.ad_spend+32*s.promotion-1.1*s.price+45*s.season+rng.normal(0,35,n))
 m=1000
 c=pd.DataFrame({"annual_spend":rng.gamma(4,180,m),"orders_per_year":rng.poisson(12,m)+1,"avg_order_value":rng.gamma(3,25,m),"days_since_last_order":rng.integers(1,365,m)})
 for key,df in (("weather",w),("sales",s),("customers",c)): df.to_csv(DATA_DIR/f"{key}.csv",index=False)
 return {"weather":w,"sales":s,"customers":c}
def train_service(service):
 if service not in FEATURES: raise ValueError("Unknown service")
 data=_datasets()[service]; feats=FEATURES[service]; x=data[feats].to_numpy(float); n=len(data)
 scaler=StandardScaler().fit(x); z=scaler.transform(x)
 report={"service":service,"dataset_rows":n,"features":feats,"dataset":"reproducible synthetic demonstration data","models":{}}
 artifacts={"service":service,"features":feats,"scaler_mean":scaler.mean_.tolist(),"scaler_scale":scaler.scale_.tolist()}
 # Four models are trained separately for this service. PCA/KMeans are unsupervised analyses, not target predictors.
 pca=PCA(n_components=2,random_state=42).fit(z)
 km=KMeans(n_clusters=4,n_init=10,random_state=42).fit(z)
 artifacts["pca"]={"mean":pca.mean_.tolist(),"components":pca.components_.tolist(),"explained_variance_ratio":pca.explained_variance_ratio_.tolist()}
 artifacts["kmeans"]={"centers":km.cluster_centers_.tolist(),"inertia":float(km.inertia_),"clusters":4}
 report["models"]["PCA"]={"type":"dimensionality_reduction","components":2,"explained_variance_ratio":pca.explained_variance_ratio_.tolist()}
 report["models"]["K-Means"]={"type":"clustering","clusters":4,"inertia":float(km.inertia_)}
 if service=="customers":
  # Unsupervised-only customer domain; use deterministic business proxy target only to train demos, never label as observed truth.
  y=(.001*data.annual_spend+.8*data.orders_per_year+.02*data.avg_order_value-.01*data.days_since_last_order).to_numpy()
 else: y=data["target"].to_numpy()
 cut=int(n*.8); xt=x[:cut]; xv=x[cut:]; yt=y[:cut]; yv=y[cut:]
 lr=LinearRegression().fit(xt,yt); dt=DecisionTreeRegressor(max_depth=8,min_samples_leaf=5,random_state=42).fit(xt,yt)
 for name,model in (("Linear Regression",lr),("Decision Tree",dt)):
  pred=model.predict(xv); report["models"][name]={"type":"supervised_regression","mae":float(mean_absolute_error(yv,pred)),"rmse":float(mean_squared_error(yv,pred)**.5),"r2":float(r2_score(yv,pred)),"test_rows":len(yv)}
  artifacts[name.lower().replace(" ","_")]={"coef":np.asarray(getattr(model,"coef_",[])).reshape(-1).tolist(),"intercept":float(getattr(model,"intercept_",0)),"tree":None}
  if name=="Decision Tree":
   t=model.tree_; artifacts["decision_tree"]["tree"]={"feature":t.feature.tolist(),"threshold":t.threshold.tolist(),"left":t.children_left.tolist(),"right":t.children_right.tolist(),"value":t.value.reshape(-1).tolist()}
 (MODEL_DIR/f"{service}.json").write_text(json.dumps(artifacts),encoding="utf-8")
 (MODEL_DIR/f"{service}_metrics.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
 return report
def train_all():
 return {s:train_service(s) for s in FEATURES}
def _tree_predict(tree,x):
 out=[]
 for row in x:
  node=0
  while tree["left"][node]!=-1:
   j=tree["feature"][node]; node=tree["left"][node] if row[j]<=tree["threshold"][node] else tree["right"][node]
  out.append(tree["value"][node])
 return float(np.mean(out))
def run_service(service,values,model="Linear Regression"):
 if service not in FEATURES: raise ValueError("Unknown service")
 path=MODEL_DIR/f"{service}.json"
 if not path.exists(): train_service(service)
 a=json.loads(path.read_text()); x=np.array([float(values[k]) for k in a["features"]]); z=(x-np.array(a["scaler_mean"]))/np.where(np.array(a["scaler_scale"])==0,1,np.array(a["scaler_scale"]))
 if model=="PCA":
  result=(z-np.array(a["pca"]["mean"]))@np.array(a["pca"]["components"]).T
  return {"service":service,"model":"PCA","projection":[round(float(v),5) for v in result],"explained_variance_ratio":a["pca"]["explained_variance_ratio"],"note":"2D projection; not a supervised prediction"}
 if model=="K-Means":
  centers=np.array(a["kmeans"]["centers"]); d=np.linalg.norm(centers-z,axis=1)
  return {"service":service,"model":"K-Means","cluster":int(np.argmin(d))+1,"clusters":len(centers),"distance":round(float(np.min(d)),5)}
 if model=="Decision Tree":
  pred=_tree_predict(a["decision_tree"]["tree"],x)
 elif model=="Linear Regression":
  pred=float(np.dot(np.array(a["linear_regression"]["coef"]),x)+a["linear_regression"]["intercept"])
 else: raise ValueError("Unsupported model. Choose Linear Regression, Decision Tree, PCA, or K-Means.")
 return {"service":service,"model":model,"prediction":round(pred,4),"unit":"°C" if service=="weather" else ("sales units" if service=="sales" else "demo score"),"note":"Synthetic demonstration data; not a live forecast or operational estimate"}
def get_metrics(service=None):
 if service:
  p=MODEL_DIR/f"{service}_metrics.json"
  return json.loads(p.read_text()) if p.exists() else {"service":service,"status":"not_trained"}
 return {s:(json.loads((MODEL_DIR/f"{s}_metrics.json").read_text()) if (MODEL_DIR/f"{s}_metrics.json").exists() else {"status":"not_trained"}) for s in FEATURES}
