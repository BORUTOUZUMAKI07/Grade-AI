#!/usr/bin/env python3
"""Generate reproducible synthetic GradeAI demo data (not real student records)."""
import csv
import random
from pathlib import Path

SEED = 20260926
N_PER_CLASS = 500
OUT = Path(__file__).resolve().parent / "student_data.csv"
rng = random.Random(SEED)

def bounded_normal(mean, sd, low, high):
    return round(max(low, min(high, rng.gauss(mean, sd))), 1)

def main():
    rows = []
    specs = (
        ("Pass", 5.7, 2.3, 78, 15, 65, 20),
        ("Fail", 3.6, 2.0, 67, 17, 48, 21),
    )
    for label, hm, hs, am, ass, mm, ms in specs:
        for _ in range(N_PER_CLASS):
            rows.append({
                "StudyHours": bounded_normal(hm, hs, 0, 12),
                "Attendance": bounded_normal(am, ass, 40, 100),
                "PreviousMarks": bounded_normal(mm, ms, 0, 100),
                "Result": label,
            })
    rng.shuffle(rows)
    if len(rows) != 2 * N_PER_CLASS:
        raise RuntimeError("Unexpected dataset row count")
    counts = {label: sum(row["Result"] == label for row in rows) for label in ("Pass", "Fail")}
    if counts != {"Pass": N_PER_CLASS, "Fail": N_PER_CLASS}:
        raise RuntimeError(f"Unexpected class counts: {counts}")
    for row in rows:
        if not (0 <= row["StudyHours"] <= 12 and 40 <= row["Attendance"] <= 100
                and 0 <= row["PreviousMarks"] <= 100):
            raise RuntimeError(f"Out-of-range generated row: {row}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["StudyHours", "Attendance", "PreviousMarks", "Result"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} synthetic rows to {OUT}")
    print(f"Class counts: {counts}")

if __name__ == "__main__":
    main()
