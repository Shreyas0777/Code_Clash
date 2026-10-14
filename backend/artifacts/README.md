# Model artifacts directory

The API loads model artifacts **from this directory at startup** (once,
never retraining, never downloading). This directory ships **empty** — model
binaries are intentionally kept out of Git.

## Expected files

| File | Producer | Required |
|---|---|---|
| `anomaly_model.joblib` | Colab notebook — `joblib.dump(anomaly_model, ...)` | for `/anomalies/detect`, anomaly flags in `/energy/analyze` |
| `forecast_model.joblib` | Colab notebook — `joblib.dump(forecast_model, ...)` | for `/forecast` |
| `model_config.json` | Colab notebook cell 21 | **yes — the API refuses inference without it** (it carries the training-time feature contract) |
| `forecast_metrics.json` | Colab notebook cell 21 | optional (informational) |

## How to place them

1. Run `fluxora_model_training..ipynb` in Google Colab (it downloads BDG2,
   trains, and exports `/content/artifacts/`).
2. Download `fluxora_trained_models.zip` (cell 22) **or** download the four
   files individually.
3. Extract the files into this directory (`backend/artifacts/`).
4. Restart the API and check `GET /api/v1/ready` → `ready: true`.

Alternative: set `MODEL_ARTIFACTS_DIR` to any other directory (see
`backend/.env.example`).

## Security

Joblib/pickle artifacts can execute arbitrary code when loaded. **Only load
artifacts you or your team exported yourself** from the Colab notebook — never
accept `.joblib` files from untrusted sources. This directory's binaries are
git-ignored; share them out-of-band (ZIP to teammates, release asset, etc.).

## No artifacts yet?

The API still starts: `/api/v1/health` returns `200`, `/api/v1/ready`
returns `503` with per-model reasons, and the model-dependent endpoints return
structured `503` errors. `/carbon/summary` (configured factor) and
`/scenarios/simulate` work regardless. For UI development you can generate
**clearly-labeled synthetic demo artifacts**:

```bash
python scripts/train_demo_artifacts.py   # writes SYNTHETIC, non-BDG2 artifacts here
```

Demo artifacts are flagged (`artifact_source: synthetic_demo_local`,
`synthetic: true`) in `model_config.json`, and `/api/v1/ready` and every model
response disclose that label — they must never be presented as real BDG2
results. Delete the generated files before placing the real export.
