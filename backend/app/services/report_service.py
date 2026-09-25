from datetime import datetime, timezone
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BRASS = colors.HexColor("#8f6d2b")
PASS_C, FAIL_C = colors.HexColor("#2f7d5b"), colors.HexColor("#b4483c")
NOTE = ("Predictions are estimates made from a small training dataset. Use them to start a conversation with the "
        "student, not as a final judgement.")

_styles = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=_styles["Title"], textColor=BRASS, alignment=0, fontSize=22, spaceAfter=4)
H2 = ParagraphStyle("h2", parent=_styles["Heading2"], textColor=colors.HexColor("#222222"), spaceBefore=14, spaceAfter=6)
BODY = _styles["BodyText"]
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, textColor=colors.HexColor("#666666"))


def _p(text: str, style=BODY) -> Paragraph:
    return Paragraph(escape(str(text)), style)


def _table(data: list[list], widths: list[float], result_col: int | None = None) -> Table:
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#26241f")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f4ee")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if result_col is not None:
        for i, row in enumerate(data[1:], start=1):
            style.append(("TEXTCOLOR", (result_col, i), (result_col, i), PASS_C if row[result_col] == "Pass" else FAIL_C))
    t.setStyle(TableStyle(style))
    return t


def _build(title: str, story: list) -> bytes:
    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                      bottomMargin=16 * mm, title=title, author="GradeAI").build(story)
    return buf.getvalue()


def _fmt(dt: datetime | None) -> str:
    if dt is None:
        return "-"
    dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%d %b %Y, %H:%M UTC")


def build_student_report(student, class_name: str | None, predictions: list, prepared_by: str) -> bytes:
    story = [_p("GradeAI student report", H1), _p(f"Prepared by {prepared_by} on {_fmt(datetime.now(timezone.utc))}", SMALL),
             Spacer(1, 10)]
    story.append(_table([["Student", "Roll number", "Class"],
                         [student.full_name, student.roll_no or "-", class_name or "-"]], [70 * mm, 45 * mm, 59 * mm]))
    if predictions:
        latest = predictions[0]
        passed = sum(1 for p in predictions if p.result == "Pass")
        story += [_p("Summary", H2),
                  _p(f"Latest prediction: {latest.result} ({latest.pass_probability * 100:.0f}% estimated chance of passing), "
                     f"made {_fmt(latest.created_at)}. Of {len(predictions)} predictions on record, {passed} said Pass "
                     f"and {len(predictions) - passed} said Fail.")]
        rows = [["Date", "Study hours", "Attendance", "Marks", "Result", "Confidence"]]
        for p in predictions[:30]:
            rows.append([_fmt(p.created_at), f"{p.study_hours:g}", f"{p.attendance:g}%", f"{p.previous_marks:g}", p.result, f"{p.confidence * 100:.0f}%"])
        story += [_p("Prediction history", H2), _table(rows, [42 * mm, 26 * mm, 26 * mm, 22 * mm, 24 * mm, 34 * mm], result_col=4)]
    else:
        story += [_p("Summary", H2), _p("No predictions have been run for this student yet.")]
    story += [Spacer(1, 14), _p(NOTE, SMALL)]
    return _build(f"Report - {student.full_name}", story)


def build_class_report(class_name: str, rows: list[dict], prepared_by: str) -> bytes:
    checked = [r for r in rows if r["result"]]
    passed = sum(1 for r in checked if r["result"] == "Pass")
    story = [_p(f"GradeAI class report: {class_name}", H1), _p(f"Prepared by {prepared_by} on {_fmt(datetime.now(timezone.utc))}", SMALL),
             _p("Summary", H2),
             _p(f"{len(rows)} students in this class. {len(checked)} have a prediction on record: {passed} likely to pass, "
                f"{len(checked) - passed} at risk. {len(rows) - len(checked)} not checked yet.")]
    table = [["Student", "Roll number", "Latest result", "Chance of passing", "Checked"]]
    for r in rows:
        table.append([r["name"], r["roll_no"] or "-", r["result"] or "Not checked",
                      f"{r['probability'] * 100:.0f}%" if r["probability"] is not None else "-", _fmt(r["checked"])])
    story += [_p("Students", H2), _table(table, [52 * mm, 28 * mm, 28 * mm, 30 * mm, 36 * mm], result_col=2), Spacer(1, 14), _p(NOTE, SMALL)]
    return _build(f"Class report - {class_name}", story)
