# GradeAI

Predicts whether a student will pass or fail from study hours, attendance and previous marks.
React front end, FastAPI back end, decision tree trained in R.

## First run

1. **Model** (needs R with the `rpart` and `jsonlite` packages). From the project root:
   `Rscript r_analytics/src/export_tree.R`
   This writes `backend/model_store/decision_tree_model.json`, including the tree.
2. **Back end** (from `backend/`):
   - `pip install -r requirements.txt`
   - copy `.env.example` to `.env`, set `SECRET_KEY` and `ADMIN_EMAIL`
   - delete any old `gradeai.db` (the tables changed)
   - `python -m app.main`, then register the `ADMIN_EMAIL` account first so it becomes admin
3. **Front end** (from `frontend-react/`): `npm install`, then `npm run dev` and open http://localhost:5173

Check the API any time with `python tests/smoke_test.py` (from `backend/`).

## Roles
- **admin**: everything a teacher can do, plus the Admin page (users, roles, usage).
- **teacher** (default for new sign-ups): classes, students, batch predictions, PDF reports.
- **student**: can run single predictions and see their own history.

## Before going live
- Set `ENVIRONMENT=production`, a long random `SECRET_KEY`, and your real front end address in `ALLOWED_ORIGINS`. Serve over HTTPS.
- Use PostgreSQL (`DATABASE_URL`) and Alembic migrations instead of the automatic table creation.
- Rate limits and refresh-token state are per process; use Redis if you run several workers.
- Behind a reverse proxy, configure trusted forwarded headers so rate limiting sees real client addresses.
- Predictions come from 50 sample rows. Retrain on real data before relying on them.
