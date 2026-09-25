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
            {"id": "kmeans", "name": "K-Means (cluster to Pass/Fail)", "kind": "unsupervised + label mapping", "available": bool((_read_json("kmeans_model.json") or {}).get("centers"))},
            {"id": "pca_knn", "name": "PCA + nearest-neighbour", "kind": "PCA + supervised neighbour vote", "available": bool((_read_json("pca_model.json") or {}).get("scores"))},
        ]

    def analytics(self) -> dict:
        summary = _read_json("analytics_summary.json") or {}
        pca = _read_json("pca_model.json")
        clusters = _read_json("kmeans_model.json")
        return {"summary": summary, "pca": pca, "clustering": clusters,
                "regression": _read_json("regression_weights.json"),
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
        elif model == "kmeans":
            km = _read_json("kmeans_model.json") or {}
            pca = _read_json("pca_model.json") or {}
            centers = km.get("centers", [])
            if not centers: raise ValueError("K-Means artifact missing; run the R training script.")
            vals = [study_hours, attendance, previous_marks]
            names = ["StudyHours", "Attendance", "PreviousMarks"]
            z = [(vals[i] - float(pca.get("center", {}).get(names[i], 0))) / (float(pca.get("scale", {}).get(names[i], 1)) or 1) for i in range(3)]
            cluster_id = min(range(len(centers)), key=lambda j: sum((z[i] - float(centers[j][i])) ** 2 for i in range(3))) + 1
            members = [r for r in km.get("records", []) if int(r.get("cluster", 0)) == cluster_id]
            passed = sum(r.get("result") == "Pass" for r in members); failed = len(members) - passed
            pass_probability = (passed + 1) / (len(members) + 2); prediction = "Pass" if pass_probability >= 0.5 else "Fail"
            confidence = max(pass_probability, 1 - pass_probability)
            steps = [f"Nearest K-Means centroid is cluster {cluster_id}.", f"Cluster labels: {passed} Pass and {failed} Fail.", "Pass probability is the smoothed Pass share of the assigned cluster."]
            source = "K-Means with cluster-to-outcome label mapping"
        elif model == "pca_knn":
            pca = _read_json("pca_model.json") or {}
            scores, loads, names = pca.get("scores", []), pca.get("loadings", []), pca.get("loading_names", [])
            if not scores or not loads: raise ValueError("PCA artifact missing; run the R training script.")
            vals = {"StudyHours": study_hours, "Attendance": attendance, "PreviousMarks": previous_marks}
            z = [(vals[n] - float(pca.get("center", {}).get(n, 0))) / (float(pca.get("scale", {}).get(n, 1)) or 1) for n in names]
            projected = [sum(z[i] * float(loads[j].get(names[i], 0)) for i in range(len(names))) for j in range(min(3, len(loads)))]
            train = (_read_json("kmeans_model.json") or {}).get("records", []); ranked = []
            for i, row in enumerate(scores):
                coords = row if isinstance(row, list) else [row]
                dist = math.sqrt(sum((projected[j] - float(coords[j])) ** 2 for j in range(min(len(projected), len(coords)))))
                if i < len(train): ranked.append((dist, train[i]))
            neighbours = sorted(ranked, key=lambda x: x[0])[:15]
            passed = sum(r.get("result") == "Pass" for _, r in neighbours); failed = len(neighbours) - passed
            pass_probability = (passed + 1) / (len(neighbours) + 2); prediction = "Pass" if pass_probability >= 0.5 else "Fail"
            confidence = max(pass_probability, 1 - pass_probability)
            steps = [f"Projected inputs into {len(projected)} principal components.", f"Among nearest PCA-space records: {passed} Pass and {failed} Fail.", "Pass probability is the smoothed neighbour Pass share."]
            source = "PCA projection + nearest-neighbour label vote"
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
        confidence_kind = {
            "decision_tree": "smoothed_training_leaf_share",
            "linear_regression": "distance_from_0.5_linear_score",
            "kmeans": "smoothed_cluster_pass_share",
            "pca_knn": "smoothed_neighbour_vote_share",
        }.get(model, "fallback_heuristic")
        confidence_note = {
            "decision_tree": "Smoothed Pass/Fail share in the reached training leaf; not calibrated confidence.",
            "linear_regression": "Distance of a clipped linear score from 0.5; not a calibrated probability or uncertainty estimate.",
            "kmeans": "Smoothed Pass share among training records in the nearest cluster; cluster labels are descriptive.",
            "pca_knn": "Smoothed Pass share among nearby training records in PCA space; not calibrated.",
        }.get(model, "Fallback-rule score; not model-estimated or calibrated.")
        if source.startswith("Fallback rules"):
            confidence_kind = "fallback_heuristic"
            confidence_note = "Fallback rule heuristic; it is not learned, validated, or calibrated."
        return {"predicted_result": prediction, "confidence_score": round(confidence, 4),
                "confidence_kind": confidence_kind, "confidence_note": confidence_note,
                "pass_probability": round(pass_probability, 4), "similar_students": similar,
                "explanation": steps, "model_source": source,
                "metadata": model_payload.get("metadata", {}), "raw_records": records,
                "selected_model": model}

    def execute_tree_classification(self, study_hours: float, attendance: float,
                                    previous_marks: float, model: str = "decision_tree") -> dict:
        logger.info("Prediction model=%s hours=%s attendance=%s marks=%s", model, study_hours, attendance, previous_marks)
        if model not in {"decision_tree", "linear_regression", "kmeans", "pca_knn"}:
            raise ValueError("Choose Decision Tree, Linear Regression, K-Means or PCA + nearest-neighbour.")
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
        if model not in {"decision_tree", "linear_regression", "kmeans", "pca_knn"}:
            raise ValueError("Choose Decision Tree, Linear Regression, K-Means or PCA + nearest-neighbour.")
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
