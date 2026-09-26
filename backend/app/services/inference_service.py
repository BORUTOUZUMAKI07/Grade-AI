import json
import logging
import math
import os
from functools import lru_cache
from pathlib import Path

from app.repositories.base import BaseRepository

logger = logging.getLogger("app")

K_NEIGHBOURS = 5
_COLUMNS = ("study_hours", "attendance", "previous_marks")
_LABELS = {"study_hours": "Study hours", "attendance": "Attendance", "previous_marks": "Previous marks"}
MODEL_DIR = Path(__file__).resolve().parents[2] / "model_store"


def _read_json(name: str) -> dict | None:
    path = MODEL_DIR / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not load model artifact %s", path)
        return None


def nearest_records(records: list[dict], point: dict, k: int = K_NEIGHBOURS) -> list[dict]:
    if not records:
        return []
    spans = {c: (max(float(r[c]) for r in records) - min(float(r[c]) for r in records)) or 1.0 for c in _COLUMNS}

    def distance(r: dict) -> float:
        return math.sqrt(sum(((float(r[c]) - point[c]) / spans[c]) ** 2 for c in _COLUMNS))

    return [{**{c: r[c] for c in _COLUMNS}, "result": r["result"], "distance": round(distance(r), 4)}
            for r in sorted(records, key=distance)[:k]]


def walk_tree(tree: dict, point: dict) -> tuple[dict, list[str]]:
    node, steps = tree, []
    while not node.get("leaf"):
        feature, threshold = node["feature"], node["threshold"]
        value = point[feature]
        below = value < threshold
        steps.append(f"{_LABELS.get(feature, feature)} is {value:g}, which is {'below' if below else 'at or above'} {threshold:g}")
        node = node["left"] if below else node["right"]
    return node, steps


class StudentInferenceService:
    def __init__(self, repository: BaseRepository[dict]):
        self._repository = repository

    def available_models(self) -> list[dict]:
        return [
            {"id": "decision_tree", "name": "Decision Tree", "kind": "supervised", "available": bool((_read_json("decision_tree_model.json") or {}).get("tree"))},
            {"id": "logistic_regression", "name": "Logistic Regression", "kind": "supervised", "available": bool((_read_json("logistic_regression_model.json") or {}).get("weights"))},
        ]

    def analytics(self) -> dict:
        summary = _read_json("analytics_summary.json") or {}
        pca = _read_json("pca_model.json")
        clusters = _read_json("kmeans_model.json")
        return {"summary": summary, "pca": pca, "clustering": clusters,
                "logistic_regression": _read_json("logistic_regression_model.json"),
                "models": self.available_models()}

    def unsupervised_profile(self, study_hours: float, attendance: float, previous_marks: float) -> dict:
        """Apply fitted K-Means and PCA transforms to a new student; neither is a classifier."""
        point = {"study_hours": float(study_hours), "attendance": float(attendance), "previous_marks": float(previous_marks)}
        pca = _read_json("pca_model.json") or {}
        km = _read_json("kmeans_model.json") or {}
        projection = None
        names = ["StudyHours", "Attendance", "PreviousMarks"]
        if pca.get("center") and pca.get("scale") and len(pca.get("loadings", [])) >= 2:
            z = [(point[k] - float(pca["center"].get(n, 0))) / (float(pca["scale"].get(n, 1)) or 1)
                 for k, n in zip(("study_hours", "attendance", "previous_marks"), names)]
            pcs = []
            for comp in pca["loadings"][:2]:
                vals = list(comp.values()) if isinstance(comp, dict) else comp
                pcs.append(round(sum(z[i] * float(vals[i]) for i in range(min(len(z), len(vals)))), 6))
            projection = {"pc1": pcs[0], "pc2": pcs[1]}
        cluster = None
        rate = None
        if km.get("center") and km.get("scale") and km.get("centers"):
            z = [(point[k] - float(km["center"].get(k, 0))) / (float(km["scale"].get(k, 1)) or 1)
                 for k in ("study_hours", "attendance", "previous_marks")]
            dists = []
            for ctr in km["centers"]:
                vals = list(ctr.values()) if isinstance(ctr, dict) else ctr
                dists.append(sum((z[i] - float(vals[i])) ** 2 for i in range(min(len(z), len(vals)))))
            if dists:
                cluster = int(min(range(len(dists)), key=dists.__getitem__)) + 1
                rates = km.get("cluster_pass_rates", [])
                rate = rates.get(str(cluster)) if isinstance(rates, dict) else (rates[cluster-1] if len(rates) >= cluster else None)
        return {"kmeans": {"cluster": cluster, "clusters": 2, "historical_training_pass_rate": rate,
                           "interpretation": "Descriptive training-cluster share only; not a validated individual Pass/Fail probability."},
                "pca": {"components": projection, "components_retained": 2,
                        "interpretation": "Training-fitted projection; not a Pass/Fail prediction."}}
    def _classify(self, model_payload: dict, study_hours: float, attendance: float,
                  previous_marks: float, model: str = "decision_tree") -> dict:
        """Run only a registered supervised classifier; PCA and K-Means are analytics-only."""
        if model not in {"decision_tree", "logistic_regression"}:
            raise ValueError("Choose Decision Tree or Logistic Regression.")
        point = {"study_hours": study_hours, "attendance": attendance, "previous_marks": previous_marks}
        records = model_payload.get("raw_records", [])
        similar = nearest_records(records, point)
        if model == "logistic_regression":
            artifact = _read_json("logistic_regression_model.json") or {}
            weights = artifact.get("weights")
            if not weights:
                raise ValueError("Logistic Regression artifact is missing. Run the R training workflow.")
            z = float(weights.get("intercept", 0))
            for key, value in point.items():
                center = float(artifact.get("center", {}).get(key, 0))
                scale = float(artifact.get("scale", {}).get(key, 1)) or 1
                z += float(weights.get(key, 0)) * ((value - center) / scale)
            pass_probability = 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, z))))
            prediction = "Pass" if pass_probability >= 0.5 else "Fail"
            score = max(pass_probability, 1 - pass_probability)
            explanation = [
                "Logistic Regression applies a sigmoid to a weighted combination of standardized inputs.",
                f"Estimated Pass probability: {pass_probability:.3f}.",
                "This estimate is based on synthetic demo data and is not calibrated for real student outcomes.",
            ]
            source = "R stats::glm binomial logistic regression"
            confidence_kind = "uncalibrated_model_probability"
            confidence_note = "Maximum class probability from the fitted logistic model; not calibrated uncertainty."
        else:
            tree = model_payload.get("tree")
            if not tree:
                raise ValueError("Decision Tree artifact is missing. Run the R training workflow.")
            leaf, explanation = walk_tree(tree, point)
            counts = leaf.get("counts", {})
            n = int(leaf.get("n") or sum(counts.values()))
            pass_probability = (counts.get("Pass", 0) + 1) / (n + 2)
            prediction = leaf["prediction"]
            score = max(pass_probability, 1 - pass_probability)
            explanation.append(
                f"This leaf contains {n} synthetic training rows: "
                f"{counts.get('Pass', 0)} Pass and {counts.get('Fail', 0)} Fail."
            )
            source = f"{model_payload.get('metadata', {}).get('framework', 'Trained')} decision tree"
            confidence_kind = "smoothed_training_leaf_share"
            confidence_note = "Smoothed class share in the reached training leaf; not calibrated confidence."
        return {
            "predicted_result": prediction,
            "confidence_score": round(score, 4),
            "confidence_kind": confidence_kind,
            "confidence_note": confidence_note,
            "pass_probability": round(pass_probability, 4),
            "similar_students": similar,
            "explanation": explanation,
            "model_source": source,
            "metadata": model_payload.get("metadata", {}),
            "raw_records": records,
            "selected_model": model,
            "unsupervised_analysis": self.unsupervised_profile(study_hours, attendance, previous_marks),
        }

    def execute_tree_classification(self, study_hours: float, attendance: float,
                                    previous_marks: float, model: str = "decision_tree") -> dict:
        logger.info("Prediction model=%s hours=%s attendance=%s marks=%s", model, study_hours, attendance, previous_marks)
        if model not in {"decision_tree", "logistic_regression"}:
            raise ValueError("Choose Decision Tree or Logistic Regression.")
        return self._classify(self._repository.fetch_all(), study_hours, attendance, previous_marks, model)

    def sensitivity(self, study_hours: float, attendance: float, previous_marks: float,
                    model: str = "decision_tree") -> dict:
        """Evaluate the selected trained model along one feature at a time.

        The two non-varied features stay fixed at the user's submitted values.
        This is model response/sensitivity, not a causal or real-world guarantee.
        """
        base = {"study_hours": study_hours, "attendance": attendance, "previous_marks": previous_marks}
        ranges = {"study_hours": (0.0, 12.0, 13), "attendance": (0.0, 100.0, 11), "previous_marks": (0.0, 100.0, 11)}
        curves = {}
        for feature, (low, high, count) in ranges.items():
            points = []
            for i in range(count):
                value = low + (high - low) * i / (count - 1)
                inputs = {**base, feature: round(value, 2)}
                result = self.execute_tree_classification(
                    inputs["study_hours"], inputs["attendance"], inputs["previous_marks"], model)
                points.append({"value": inputs[feature], "pass_probability": result["pass_probability"],
                               "confidence": result["confidence_score"], "predicted_result": result["predicted_result"],
                               "is_current": abs(inputs[feature] - base[feature]) < 1e-9})
            curves[feature] = {"label": _LABELS[feature], "current_value": base[feature], "points": points}
        return {"selected_model": model, "baseline_inputs": base, "curves": curves,
                "note": "Model response curve: one input varies while the other two stay fixed. Not causal evidence."}

    def training_predictions(self, model: str = "decision_tree") -> dict:
        """Run a selected model over the checked-in reference rows for descriptive comparison.

        These are in-sample predictions on training data, not held-out evaluation.
        """
        if model not in {"decision_tree", "logistic_regression"}:
            raise ValueError("Choose Decision Tree or Logistic Regression.")
        payload = self._repository.fetch_all()
        records = payload.get("raw_records", [])
        rows = []
        for index, record in enumerate(records):
            result = self._classify(payload, float(record["study_hours"]),
                                    float(record["attendance"]), float(record["previous_marks"]), model)
            rows.append({
                "record_index": index + 1,
                "study_hours": record["study_hours"],
                "attendance": record["attendance"],
                "previous_marks": record["previous_marks"],
                "actual_result": record.get("result"),
                "predicted_result": result["predicted_result"],
                "pass_probability": result["pass_probability"],
                "confidence_score": result["confidence_score"],
            })
        actual = [r for r in rows if r["actual_result"] in {"Pass", "Fail"}]
        correct = sum(r["actual_result"] == r["predicted_result"] for r in actual)
        return {
            "model": model,
            "source": "model artifact raw_records (synthetic training reference set)",
            "is_training_data": True,
            "warning": "In-sample predictions on synthetic training data; not an estimate of generalization.",
            "total_records": len(rows),
            "predicted_pass": sum(r["predicted_result"] == "Pass" for r in rows),
            "predicted_fail": sum(r["predicted_result"] == "Fail" for r in rows),
            "training_match_rate": (correct / len(actual)) if actual else None,
            "rows": rows,
        }

    def execute_batch(self, rows: list[dict], model: str = "decision_tree") -> list[dict]:
        payload = self._repository.fetch_all()
        out = []
        for r in rows:
            res = self._classify(payload, r["study_hours"], r["attendance"], r["previous_marks"], model)
            out.append({**r, "predicted_result": res["predicted_result"],
                        "confidence_score": res["confidence_score"], "pass_probability": res["pass_probability"],
                        "selected_model": model})
        return out
