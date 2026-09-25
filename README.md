# GradeAI

GradeAI is a student outcome analytics toy project with a React frontend, FastAPI backend, and R-based training pipeline. It demonstrates supervised classification (Decision Tree and Linear Regression), unsupervised analytics (PCA and K-Means), prediction explanations, and class-level charts.

> **Demo-data warning:** the included 50-row CSV is synthetic/sample data. Metrics are descriptive and mostly in-sample; do not use these predictions to make real academic decisions. Linear Regression is fitted to Pass=1/Fail=0 labels and returns a clamped score—not predicted exam marks or a calibrated probability.

## Train all models

Install R and run from the repository root:

```bash
Rscript r_analytics/src/train.R
```

The script installs/uses `rpart` and `jsonlite` and writes these files into `backend/model_store/`:

- `decision_tree_model.json` — tree structure, metadata, and training records used by the API.
- `regression_weights.json` — intercept and feature coefficients for the linear probability score.
- `pca_model.json` — centers, scales, loadings, explained variance, and PCA scores.
- `kmeans_model.json` — standardized cluster centers, cluster sizes, and assigned records.
- `analytics_summary.json` — dataset summaries and model diagnostics.

The same training pipeline runs automatically on pushes to `main` that touch `r_analytics/`, and can be started manually from GitHub Actions using **Train and validate GradeAI models**. The workflow validates all five JSON artifacts and uploads them as the `gradeai-trained-models` workflow artifact. Download/copy those artifacts into `backend/model_store/` if you want to use the exact CI-trained files locally.

### Why `utils.R` exists

`r_analytics/src/utils.R` is required by `train.R`: it exports the R decision tree into the JSON tree schema consumed by FastAPI and includes the original training records used for nearest-neighbor context. Keep it alongside `train.R`.

## Run locally

1. **Backend** (from `backend/`):
   ```bash
   pip install -r requirements.txt
   cp .env.example .env
   # Set SECRET_KEY and ADMIN_EMAIL in .env
   python -m app.main
   ```
   Register the account matching `ADMIN_EMAIL` first to grant it admin role.
2. **Frontend** (from `frontend-react/`):
   ```bash
   npm install
   npm run dev
   ```
   Open http://localhost:5173.

## API additions

- `GET /api/v1/predict/models` — available supervised prediction models.
- `GET /api/v1/predict/analytics` — model summary, PCA, and clustering artifacts (staff access).
- `POST /api/v1/predict/` — accepts `model: "decision_tree"` or `"linear_regression"`; defaults to Decision Tree.
- `POST /api/v1/predict/batch` — staff batch predictions, with the same model option.

## Roles

- **admin**: teacher capabilities plus user/role management and usage stats.
- **teacher**: classes, students, batch predictions, and PDF reports.
- **student**: single predictions and personal history.

## Before using real data

Replace the synthetic dataset with an appropriately collected and permissioned dataset, preserve the required columns (`StudyHours`, `Attendance`, `PreviousMarks`, `Result`), and evaluate with a held-out test set or cross-validation. The current summary's tree accuracy and regression RMSE are training-set diagnostics, not generalization estimates. Do not commit sensitive student information or secrets.

For deployment, configure a strong `SECRET_KEY`, production environment, HTTPS, a real database with migrations, and appropriate access controls.
