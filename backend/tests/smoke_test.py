"""End-to-end API test. Run from the backend folder:   python tests/smoke_test.py
Uses a throw-away database and the real model file. A few checks assume the 50-row sample dataset
(for example the 22/23 confidence), so update those numbers if you retrain on different data."""
import datetime, os, sys, tempfile
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.update(DATABASE_URL=f"sqlite:///{tempfile.mkdtemp()}/test.db", ADMIN_EMAIL="admin@example.com",
                  MODEL_PATH=os.path.join(BACKEND, "model_store", "decision_tree_model.json"))
sys.path.insert(0, BACKEND)
from fastapi.testclient import TestClient
from app.main import app
import app.services.auth_service as auth_service
P = "/api/v1"; fails = []
def chk(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), name, extra)
    if not cond: fails.append(name)
def reg(c, email, name="User", pw="correct horse"):
    r = c.post(f"{P}/auth/register", json={"email": email, "full_name": name, "password": pw}); assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}, r.json()["user"]
PRED = lambda h, a, m, **k: {"study_hours": h, "attendance": a, "previous_marks": m, **k}

with TestClient(app) as c, TestClient(app) as c2, TestClient(app) as ca:
    H, u1 = reg(c, "t1@example.com", "Teacher One"); H2, u2 = reg(c2, "t2@example.com", "Teacher Two"); HA, adm = reg(ca, "admin@example.com", "Boss")

    # ---- real tree model; avoid brittle hard-coded predictions from a previous dataset version
    r = c.post(f"{P}/predict/", json=PRED(5, 70, 55), headers=H).json()
    chk("tree: returns a valid trained-model classification",
        r.get("predicted_result") in {"Pass", "Fail"} and "rpart" in r.get("model_source", ""),
        str(r.get("predicted_result")))
    chk("tree: confidence fields have valid model-specific semantics",
        isinstance(r.get("confidence_score"), (int, float)) and 0 <= r["confidence_score"] <= 1
        and isinstance(r.get("pass_probability"), (int, float)) and 0 <= r["pass_probability"] <= 1
        and r.get("confidence_kind") == "smoothed_training_leaf_share"
        and bool(r.get("confidence_note")) and bool(r.get("explanation")),
        r.get("confidence_kind", "missing confidence semantics"))
    r = c.post(f"{P}/predict/", json=PRED(6, 75, 60), headers=H).json()
    chk("tree: second valid input returns a bounded pass score",
        r.get("predicted_result") in {"Pass", "Fail"}
        and isinstance(r.get("pass_probability"), (int, float))
        and 0 <= r["pass_probability"] <= 1)

    # ---- selectable models and model analytics
    models = c.get(f"{P}/predict/models", headers=H)
    chk("model registry exposes both trained models", models.status_code == 200 and {m["id"] for m in models.json()["models"]} >= {"decision_tree", "linear_regression"})
    analytics = c.get(f"{P}/predict/analytics", headers=H)
    chk("analytics endpoint exposes PCA, K-Means and regression artifacts",
        analytics.status_code == 200 and analytics.json().get("pca") and analytics.json().get("clustering") and analytics.json().get("regression", {}).get("weights"))
    training_rows = ca.get(f"{P}/predict/training-predictions?model=decision_tree", headers=HA)
    training_json = training_rows.json()
    chk("training-predictions endpoint exposes every artifact row and honest source label",
        training_rows.status_code == 200 and training_json.get("is_training_data") is True
        and training_json.get("total_records") == len(training_json.get("rows", []))
        and training_json.get("source", "").startswith("model artifact raw_records")
        and "in-sample" in training_json.get("warning", "").lower(),
        str({k: training_json.get(k) for k in ("total_records", "source", "warning", "is_training_data")} | {"rows_len": len(training_json.get("rows", []))}))
    chk("training predictions include actual and model-predicted labels",
        bool(training_json.get("rows")) and
        all(row.get("actual_result") in {"Pass", "Fail"} and row.get("predicted_result") in {"Pass", "Fail"}
            for row in training_json.get("rows", [])))
    forbidden = ca.get(f"{P}/predict/training-predictions?model=not_a_model", headers=HA)
    chk("training-predictions rejects unsupported model names", forbidden.status_code == 422)

    live_curve = c.post(f"{P}/predict/sensitivity", json=PRED(6, 75, 60), headers=H)
    curve_json = live_curve.json()
    chk("live sensitivity returns all three feature curves",
        live_curve.status_code == 200 and set(curve_json.get("curves", {})) == {"study_hours", "attendance", "previous_marks"})
    chk("live sensitivity holds other inputs and tags current values",
        curve_json.get("baseline_inputs", {}).get("attendance") == 75 and
        any(point.get("is_current") for point in curve_json.get("curves", {}).get("study_hours", {}).get("points", [])))
    live_linear = c.post(f"{P}/predict/sensitivity", json=PRED(6, 75, 60, model="linear_regression"), headers=H)
    chk("live sensitivity evaluates selected Linear Regression",
        live_linear.status_code == 200 and live_linear.json().get("selected_model") == "linear_regression" and
        len(live_linear.json().get("curves", {}).get("attendance", {}).get("points", [])) == 11)
    linear = c.post(f"{P}/predict/", json=PRED(6, 75, 60, model="linear_regression"), headers=H)
    chk("linear regression selected model returns tagged prediction",
        linear.status_code == 200 and linear.json().get("selected_model") == "linear_regression" and "linear probability" in linear.json().get("model_source", "").lower())
    recent = c.get(f"{P}/predict/history?page_size=10", headers=H).json()
    chk("history persists selected model", any(item.get("model_name") == "linear_regression" for item in recent.get("items", [])))

    # ---- classes & students
    r = c.post(f"{P}/classes", json={"name": "Class 10A"}, headers=H); cid = r.json()["id"]
    chk("create class", r.status_code == 201)
    chk("duplicate class name -> 409", c.post(f"{P}/classes", json={"name": "class 10a"}, headers=H).status_code == 409)
    s = c.post(f"{P}/students", json={"full_name": "Asha", "roll_no": "R1", "class_id": cid}, headers=H); sid = s.json()["id"]
    chk("create student", s.status_code == 201 and s.json()["class_name"] == "Class 10A")
    chk("duplicate roll -> 409", c.post(f"{P}/students", json={"full_name": "X", "roll_no": "R1"}, headers=H).status_code == 409)
    imp = c.post(f"{P}/students/import", json={"class_id": cid, "rows": [{"full_name": "Ben", "roll_no": "R2"}, {"full_name": "Cara", "roll_no": "R3"}, {"full_name": "Dup", "roll_no": "R1"}]}, headers=H).json()
    chk("import: 2 created, 1 skipped", imp == {"created": 2, "skipped": 1}, str(imp))
    pg = c.get(f"{P}/students?page=1&page_size=2", headers=H).json()
    chk("pagination: 3 total, 2 per page, 2 pages", pg["total"] == 3 and len(pg["items"]) == 2 and pg["pages"] == 2, str({k: pg[k] for k in ("total","page","pages")}))
    chk("search by name", c.get(f"{P}/students?q=ben", headers=H).json()["total"] == 1)
    chk("filter by class", c.get(f"{P}/students?class_id={cid}", headers=H).json()["total"] == 3)
    chk("classes list shows student_count 3", c.get(f"{P}/classes", headers=H).json()["items"][0]["student_count"] == 3)
    chk("other teacher sees no students", c2.get(f"{P}/students", headers=H2).json()["total"] == 0)
    chk("other teacher cannot predict for my student -> 404", c2.post(f"{P}/predict/", json=PRED(5, 70, 55, student_id=sid), headers=H2).status_code == 404)
    chk("other teacher cannot patch my student -> 404", c2.patch(f"{P}/students/{sid}", json={"full_name": "Hack"}, headers=H2).status_code == 404)
    chk("predict for my student -> 200", c.post(f"{P}/predict/", json=PRED(8, 85, 70, student_id=sid), headers=H).status_code == 200)
    st = c.get(f"{P}/students?q=asha", headers=H).json()["items"][0]
    chk("student row shows latest result", st["last_result"] == "Pass" and st["last_checked"].endswith("Z") or "+" in (st["last_checked"] or ""), str(st["last_result"]))
    chk("patch: clear class", c.patch(f"{P}/students/{sid}", json={"class_id": None}, headers=H).json()["class_id"] is None)
    c.patch(f"{P}/students/{sid}", json={"class_id": cid}, headers=H)

    # ---- history pagination + filter
    h = c.get(f"{P}/predict/history?student_id={sid}", headers=H).json()
    chk("history filter by student", h["total"] == 1 and h["items"][0]["student_name"] == "Asha")
    chk("history page_size cap -> 422", c.get(f"{P}/predict/history?page_size=1000", headers=H).status_code == 422)

    # ---- batch
    b = c.post(f"{P}/predict/batch", json={"rows": [PRED(2, 50, 40, label="A"), PRED(9, 90, 75, label="B"), PRED(7, 80, 65, student_id=sid)]}, headers=H).json()
    chk("batch: 2 pass 1 fail", b["passed"] == 2 and b["failed"] == 1 and b["results"][0]["label"] == "A", str((b["passed"], b["failed"])))
    chk("batch: out-of-range row rejects request", c.post(f"{P}/predict/batch", json={"rows": [PRED(30, 50, 40)]}, headers=H).status_code == 422)
    chk("batch: >500 rows rejected", c.post(f"{P}/predict/batch", json={"rows": [PRED(5, 50, 40)] * 501}, headers=H).status_code == 422)
    chk("batch: foreign student id -> 404", c2.post(f"{P}/predict/batch", json={"rows": [PRED(5, 50, 40, student_id=sid)]}, headers=H2).status_code == 404)

    # ---- reports
    r = c.get(f"{P}/reports/students/{sid}", headers=H)
    chk("student PDF", r.status_code == 200 and r.content[:5] == b"%PDF-" and r.headers["content-type"] == "application/pdf", f"{len(r.content)} bytes")
    r = c.get(f"{P}/reports/classes/{cid}", headers=H)
    chk("class PDF", r.status_code == 200 and r.content[:5] == b"%PDF-")
    chk("other teacher PDF -> 404", c2.get(f"{P}/reports/students/{sid}", headers=H2).status_code == 404)

    # ---- delete keeps history
    chk("delete student -> 204", c.delete(f"{P}/students/{sid}", headers=H).status_code == 204)
    chk("history rows survive with no student", c.get(f"{P}/predict/history?page_size=100", headers=H).json()["total"] >= 6)
    chk("delete class -> 204, students kept", c.delete(f"{P}/classes/{cid}", headers=H).status_code == 204 and c.get(f"{P}/students", headers=H).json()["total"] == 2)

    # ---- admin
    chk("teacher blocked from admin users -> 403", c.get(f"{P}/admin/users", headers=H).status_code == 403)
    chk("teacher blocked from stats -> 403", c.get(f"{P}/admin/stats", headers=H).status_code == 403)
    us = ca.get(f"{P}/admin/users?page_size=2", headers=HA).json()
    chk("admin users paginated with prediction counts", us["total"] == 3 and len(us["items"]) == 2 and us["items"][0]["prediction_count"] >= 0, str(us["pages"]))
    chk("admin search", ca.get(f"{P}/admin/users?q=teacher two", headers=HA).json()["total"] == 1)
    chk("admin cannot edit self -> 409", ca.patch(f"{P}/admin/users/{adm['id']}", json={"role": "student"}, headers=HA).status_code == 409)
    st = ca.get(f"{P}/admin/stats", headers=HA).json()
    chk("stats", st["total_users"] == 3 and st["total_predictions"] >= 6 and len(st["predictions_by_day"]) == 14 and st["predictions_by_day"][-1]["count"] >= 6, str(st["users_by_role"]))
    chk("admin makes teacher two a student", ca.patch(f"{P}/admin/users/{u2['id']}", json={"role": "student"}, headers=HA).json()["role"] == "student")
    chk("student role blocked from students API -> 403", c2.get(f"{P}/students", headers=H2).status_code == 403)
    chk("student role can still predict", c2.post(f"{P}/predict/", json=PRED(8, 85, 70), headers=H2).status_code == 200)
    ca.patch(f"{P}/admin/users/{u2['id']}", json={"is_active": False}, headers=HA)
    chk("deactivated user's token stops working at once -> 401", c2.post(f"{P}/predict/", json=PRED(8, 85, 70), headers=H2).status_code == 401)
    chk("deactivated user cannot log in", c2.post(f"{P}/auth/login", json={"email": "t2@example.com", "password": "correct horse"}).status_code == 401)

    # ---- refresh rotation + theft detection
    old = c.cookies.get("refresh_token")
    chk("refresh rotates", c.post(f"{P}/auth/refresh").status_code == 200 and c.cookies.get("refresh_token") != old)
    new = c.cookies.get("refresh_token")
    auth_service.REUSE_GRACE = datetime.timedelta(0)
    c.cookies.clear(); c.cookies.set("refresh_token", old, path=f"{P}/auth")
    chk("reusing an old refresh token -> 401", c.post(f"{P}/auth/refresh").status_code == 401)
    c.cookies.clear(); c.cookies.set("refresh_token", new, path=f"{P}/auth")
    chk("...and the newer token is revoked too (theft response)", c.post(f"{P}/auth/refresh").status_code == 401)
    auth_service.REUSE_GRACE = datetime.timedelta(seconds=15)
    c.cookies.clear(); c.post(f"{P}/auth/login", json={"email": "t1@example.com", "password": "correct horse"})
    tok = c.cookies.get("refresh_token"); c.post(f"{P}/auth/logout"); c.cookies.clear(); c.cookies.set("refresh_token", tok, path=f"{P}/auth")
    chk("logout really revokes the refresh token", c.post(f"{P}/auth/refresh").status_code == 401)

    # ---- rate limiting
    codes = [c.post(f"{P}/auth/login", json={"email": "victim@example.com", "password": "wrong wrong"}).status_code for _ in range(6)]
    chk("login: 5 failures then 429", codes == [401] * 5 + [429], str(codes))
    r = c.post(f"{P}/auth/login", json={"email": "victim@example.com", "password": "wrong wrong"})
    chk("429 carries Retry-After", "retry-after" in r.headers, r.headers.get("retry-after", ""))
    chk("a different account is not locked out", c.post(f"{P}/auth/login", json={"email": "t1@example.com", "password": "correct horse"}).status_code == 200)

print("\nFAILED:", fails if fails else "none")
sys.exit(1 if fails else 0)
