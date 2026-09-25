import logging
import math

from app.repositories.base import BaseRepository

logger = logging.getLogger("app")

K_NEIGHBOURS = 5
_COLUMNS = ("study_hours", "attendance", "previous_marks")
_LABELS = {"study_hours": "Study hours", "attendance": "Attendance", "previous_marks": "Previous marks"}


def nearest_records(records: list[dict], point: dict, k: int = K_NEIGHBOURS) -> list[dict]:
    """The k stored students closest to `point`, with each feature scaled to its own range."""
    spans = {c: (max(r[c] for r in records) - min(r[c] for r in records)) or 1.0 for c in _COLUMNS}

    def distance(r: dict) -> float:
        return math.sqrt(sum(((r[c] - point[c]) / spans[c]) ** 2 for c in _COLUMNS))

    return [
        {**{c: r[c] for c in _COLUMNS}, "result": r["result"], "distance": round(distance(r), 4)}
        for r in sorted(records, key=distance)[:k]
    ]


def walk_tree(tree: dict, point: dict) -> tuple[dict, list[str]]:
    """Follow the exported rpart tree (go left when value < threshold) and describe each step."""
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

    def _classify(self, model_payload: dict, study_hours: float, attendance: float, previous_marks: float) -> dict:
        point = {"study_hours": study_hours, "attendance": attendance, "previous_marks": previous_marks}
        similar = nearest_records(model_payload["raw_records"], point)
        tree = model_payload.get("tree")

        if tree:
            # Real model: the rpart tree exported by r_analytics/src/export_tree.R
            leaf, steps = walk_tree(tree, point)
            counts = leaf.get("counts", {})
            n = leaf.get("n") or sum(counts.values())
            prediction = leaf["prediction"]
            # Laplace-smoothed share of training students in this branch (a branch of 29 out of 29 is 0.97, not 1.0)
            confidence = (counts.get(prediction, 0) + 1) / (n + 2)
            pass_probability = (counts.get("Pass", 0) + 1) / (n + 2)
            steps.append(f"That branch holds {n} training students: {counts.get('Pass', 0)} passed and {counts.get('Fail', 0)} failed")
            source = f"{model_payload.get('metadata', {}).get('framework', 'Trained')} decision tree"
        else:
            # Fallback for an older model file without a tree: the original fixed rules
            if study_hours >= 5.5 and attendance >= 68.5:
                prediction, confidence = "Pass", 0.96
            elif previous_marks >= 53.5 or attendance >= 74.5:
                prediction, confidence = "Pass", 0.88
            else:
                prediction, confidence = "Fail", 0.94
            pass_probability = sum(1 for s in similar if s["result"] == "Pass") / len(similar) if similar else 0.0
            steps = ["No trained tree was found in the model file, so fixed fallback rules were used. Run export_tree.R."]
            source = "Fallback rules (no trained tree)"

        return {
            "predicted_result": prediction,
            "confidence_score": round(confidence, 4),
            "pass_probability": round(pass_probability, 4),
            "similar_students": similar,
            "explanation": steps,
            "model_source": source,
            "metadata": model_payload["metadata"],
            "raw_records": model_payload["raw_records"],
        }

    def execute_tree_classification(self, study_hours: float, attendance: float, previous_marks: float) -> dict:
        logger.info(f"Evaluating tactical matrix: hours={study_hours}, attendance={attendance}, marks={previous_marks}")
        return self._classify(self._repository.fetch_all(), study_hours, attendance, previous_marks)

    def execute_batch(self, rows: list[dict]) -> list[dict]:
        """Classify many students, reading the model file once."""
        payload = self._repository.fetch_all()
        out = []
        for r in rows:
            res = self._classify(payload, r["study_hours"], r["attendance"], r["previous_marks"])
            out.append({**r, "predicted_result": res["predicted_result"],
                        "confidence_score": res["confidence_score"], "pass_probability": res["pass_probability"]})
        return out
