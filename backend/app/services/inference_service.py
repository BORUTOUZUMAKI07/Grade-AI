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
            {"id": "linear_regression", "name": "Linear Regression", "kind": "supervised", "available": bool((_read_json("regression_weights.json") or {}).get("weights"))},
        ]

    def analytics(self) -> dict:
        summary = _read_json("analytics_summary.json") or {}
        pca = _read_json("pca_model.json")
        clusters = _read_json("kmeans_model.json")
        return {"summary": summary, "pca": pca, "clustering": clusters,
                "models": self.available_models()}

    def _classify(self, model_payload: dict, study_hours: float, attendance: float,
                  previous_marks: float, model: str = "decision_tree") -> dict:
        point = {"study_hours": study_hours, "attendance": attendance, "previous_marks": previous_marks}
        records = model_payload.get("raw_records", [])
        similar = nearest_records(records, point)
        steps = []
        if model == "linear_regression":
            regression = _read_json("regression_weights.json")
            weights = (regression or {}).get("weights")
            if not weights:
                raise ValueError("Linear Regression artifact is missing. Run the R training script.")
            score = (float(weights.get("intercept", 0)) +
                     float(weights.get("study_hours", 0)) * study_hours +
                     float(weights.get("attendance", 0)) * attendance +
                     float(weights.get("previous_marks", 0)) * previous_marks)
            pass_probability = min(1.0, max(0.0, score))
            prediction = "Pass" if pass_probability >= 0.5 else "Fail"
            confidence = max(pass_probability, 1 - pass_probability)
            steps = ["Linear Regression computes a weighted score from study hours, attendance and previous marks.",
                     f"Estimated pass score (clamped to 0–1): {pass_probability:.3f}.",
                     "This is a score fitted to Pass/Fail labels, not a predicted exam mark."]
            source = "R stats::lm linear probability model"
        else:
            tree = model_payload.get("tree")
            if tree:
                leaf, steps = walk_tree(tree, point)
                counts = leaf.get("counts", {})
                n = leaf.get("n") or sum(counts.values())
                prediction = leaf["prediction"]
                confidence = (counts.get(prediction, 0) + 1) / (n + 2)
                pass_probability = (counts.get("Pass", 0) + 1) / (n + 2)
                steps.append(f"That branch holds {n} training students: {counts.get('Pass', 0)} passed and {counts.get('Fail', 0)} failed")
                source = f"{model_payload.get('metadata', {}).get('framework', 'Trained')} decision tree"
            else:
                if study_hours >= 5.5 and attendance >= 68.5:
                    prediction, confidence = "Pass", 0.96
                elif previous_marks >= 53.5 or attendance >= 74.5:
                    prediction, confidence = "Pass", 0.88
                else:
                    prediction, confidence = "Fail", 0.94
                pass_probability = sum(1 for s in similar if s["result"] == "Pass") / len(similar) if similar else 0.0
                steps = ["No trained tree was found; fixed fallback rules were used. Run the R training script."]
                source = "Fallback rules (no trained tree)"
        return {"predicted_result": prediction, "confidence_score": round(confidence, 4),
                "pass_probability": round(pass_probability, 4), "similar_students": similar,
                "explanation": steps, "model_source": source,
                "metadata": model_payload.get("metadata", {}), "raw_records": records,
                "selected_model": model}

    def execute_tree_classification(self, study_hours: float, attendance: float,
                                    previous_marks: float, model: str = "decision_tree") -> dict:
        logger.info("Prediction model=%s hours=%s attendance=%s marks=%s", model, study_hours, attendance, previous_marks)
        if model not in {"decision_tree", "linear_regression"}:
            raise ValueError("Choose decision_tree or linear_regression for prediction.")
        return self._classify(self._repository.fetch_all(), study_hours, attendance, previous_marks, model)

    def execute_batch(self, rows: list[dict], model: str = "decision_tree") -> list[dict]:
        payload = self._repository.fetch_all()
        out = []
        for r in rows:
            res = self._classify(payload, r["study_hours"], r["attendance"], r["previous_marks"], model)
            out.append({**r, "predicted_result": res["predicted_result"],
                        "confidence_score": res["confidence_score"], "pass_probability": res["pass_probability"],
                        "selected_model": model})
        return out
