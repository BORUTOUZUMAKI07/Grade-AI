#!/usr/bin/env python3
"""Generate the reproducible, balanced synthetic GradeAI demo dataset.

This is simulated data for software demonstrations only, not real student records
or a validated educational assessment dataset.
"""
import csv
import math
import random
from pathlib import Path

SEED = 20260925
N_PER_CLASS = 250
OUT = Path(__file__).resolve().parent / "student_data.csv"
rng = random.Random(SEED)

def bounded_normal(mean, sd, low, high):
    return max(low, min(high, rng.gauss(mean, sd)))

rows = []
for result, study_mean, study_sd, attendance_mean, attendance_sd, marks_mean, marks_sd in [
    ("Pass", 5.7, 2.3, 78, 15, 65, 20),
    ("Fail", 3.6, 2.0, 67, 17, 48, 21),
]:
    for _ in range(N_PER_CLASS):
        rows.append({
            "StudyHours": round(bounded_normal(study_mean, study_sd, 0, 12), 1),
            "Attendance": round(bounded_normal(attendance_mean, attendance_sd, 40, 100), 1),
            "PreviousMarks": round(bounded_normal(marks_mean, marks_sd, 0, 100), 1),
            "Result": result,
        })
rng.shuffle(rows)
with OUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["StudyHours", "Attendance", "PreviousMarks", "Result"])
    writer.writeheader()
    writer.writerows(rows)
print(f"Wrote {len(rows)} synthetic rows to {OUT}")
print("Class counts:", {label: sum(r["Result"] == label for r in rows) for label in ("Pass", "Fail")})
