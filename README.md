# Fluxora — Energy Intelligence & Carbon Optimization

**Decode Energy. Design a Greener Future.**

Hackathon project (team repo: `Shreyas0777/Code_Clash`).

## Repository contents

| Path | What it is |
|---|---|
| `fluxora_model_training..ipynb` | Colab training pipeline: BDG2 data → IsolationForest (anomaly) + HistGradientBoostingRegressor (forecast) → `.joblib` export |
| [`backend/`](backend/README.md) | FastAPI backend — analysis, forecasting, anomaly detection, carbon summary, scenario simulation |
| [`docs/AUDIT_AND_PLAN.md`](docs/AUDIT_AND_PLAN.md) | Repository audit + backend architecture plan |
| [`docs/VERIFICATION_REPORT.md`](docs/VERIFICATION_REPORT.md) | Final build & test verification report |

## Backend in 30 seconds

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload      # Swagger UI: http://127.0.0.1:8000/docs
python -m pytest app/tests -q      # test suite
```

Model artifacts (`.joblib` + `model_config.json`) are produced by the Colab
notebook and placed in `backend/artifacts/` — they are **not** committed to
Git. Until then the API runs with `/ready` reporting `503` degraded and the
model endpoints refusing cleanly (no fabricated predictions). See
[`backend/artifacts/README.md`](backend/artifacts/README.md).
