# Fluxora Backend — Repository Audit & Implementation Plan

_Phase 1 (audit) and Phase 2 (architecture plan) of the backend build._

---

## PART A — PHASE 1: REPOSITORY AUDIT

All statements below were produced by inspecting the actual repository at
`https://github.com/Shreyas0777/Code_Clash` (branch `main`, commit `5a15463`
"Add files via upload"). Nothing is assumed.

### A.1 Repository tree (complete)

```
Code_Clash/
└── fluxora_model_training..ipynb   (1,023,993 bytes, 56 code cells)
```

`git ls-tree -r HEAD` returns **exactly one file**. Remote has a single branch
(`main`); `git ls-remote` shows no other branches or tags; the GitHub releases
API returns an empty list. There are **no other copies of the project on this
repository**.

### A.2 Existing components

| Component | Status |
|---|---|
| Training notebook (`fluxora_model_training..ipynb`) | **Present**, executed outputs embedded |
| Frontend (any framework) | **Absent** — no HTML/JS/TS/package.json anywhere |
| Backend / API code | **Absent** |
| README, `.gitignore`, `requirements.txt` | **Absent** |
| Docker / Compose configuration | **Absent** |
| Notebooks directory, training scripts | **Absent** (the notebook tried to copy itself to `notebooks/` in Colab; those cells failed — see A.6) |
| CI configuration | **Absent** |

### A.3 Model artifact availability (explicit verification)

| Artifact | In repository? |
|---|---|
| `anomaly_model.joblib` | **NO** |
| `forecast_model.joblib` | **NO** |
| `model_config.json` | **NO** |
| `forecast_metrics.json` | **NO** |
| `fluxora_trained_models.zip` | **NO** |

No `.joblib`, `.zip`, `.pkl`, `.onnx` or `.json` files exist anywhere in the
tree, in any branch, tag, or GitHub release.

**However**, the committed notebook contains embedded outputs proving the
artifacts *were* created inside a Colab session:

- Cell 21 output: `Export complete!` listing `anomaly_model.joblib`,
  `model_config.json`, `forecast_model.joblib`, `forecast_metrics.json` written
  to `/content/artifacts/`.
- Cell 22: `shutil.make_archive("/content/fluxora_trained_models", ...)`
  followed by `files.download(...)` — the ZIP was downloaded to the teammate's
  local machine and **never committed** (cells 24–49 attempt pushes that failed
  with `pathspec did not match`, empty-clone, and git-identity errors).

**Conclusion:** artifacts exist somewhere on a teammate's machine, not in the
repository. The backend must therefore run in a **degraded-but-honest mode**
until the artifacts are added, and must never fabricate predictions.

### A.4 Verified training contracts (read from the notebook source)

These are the contracts the backend must reproduce exactly.

**Dataset:** Building Data Genome Project 2, `data/meters/raw/electricity.csv`
(fetched via `git clone` + git-lfs in Colab). Recorded shape `(17544, 1579)`,
date range `2016-01-01 00:00` → `2017-12-31 23:00`, 1,576 meter columns.
Selected meter (by most valid readings): **`Robin_public_Carolina`**, 17,544
valid hourly readings.

**Preprocessing (cell 12):**
1. Parse timestamps, drop unparseable, sort.
2. Aggregate duplicate timestamps with `groupby(timestamp).mean()`.
3. Negative kWh → `NaN` (treated invalid, never zero).
4. Reindex to a contiguous **hourly** grid over `[min, max]`.
5. `interpolate(method="time", limit=3, limit_area="inside")` — only gaps ≤ 3h
   are filled; longer gaps stay missing.
6. Drop rows still `NaN`; require ≥ `24*14` usable observations.

**Anomaly model (cell 14):**
- `IsolationForest(n_estimators=200, contamination=0.02, random_state=42, n_jobs=-1)`
- Feature order: `["energy_kwh", "hour", "day_of_week", "month"]`
  (calendar features from the timestamp; `day_of_week` Monday=0).
- Chronological 80/20 split, no shuffling.
- Output interpretation: `predict()` → `-1` anomaly, `1` normal.
- Score exported by the notebook: `anomaly_score = -score_samples(X)`
  (higher = more unusual; **not** a calibrated probability).
- Recorded notebook output: 3,509 test readings, 133 flagged (3.79%).

**Forecast model (cells 16–18):**
- `HistGradientBoostingRegressor(max_iter=200, learning_rate=0.08,
  max_leaf_nodes=20, l2_regularization=1.0, random_state=42)`
- Feature order: `["hour", "day_of_week", "month", "lag_1", "lag_24",
  "lag_168", "rolling_mean_24"]`
- `rolling_mean_24 = shift(1).rolling(24, min_periods=24).mean()`
  → window is the 24 hours **strictly before** the target row (no leakage).
- Chronological 80/20 split. Recorded: 13,900 train rows / 3,476 test rows;
  training period `2016-01-08 00:00` → `2017-08-09 03:00`, testing period
  `2017-08-09 04:00` → `2017-12-31 23:00`.
- Horizon: next-hour only (`forecast_horizon_hours: 1` in the exported config).
- Minimum history to produce one feature row: **168 prior hourly slots**
  (first valid training row is exactly 168 h after series start).

**Metrics recorded in the notebook output (not re-measured by me):**

| | MAE | RMSE | R² |
|---|---|---|---|
| Fluxora ML Model | 5.3437 | 7.9461 | 0.9654 |
| Previous-day baseline | 18.2679 | 29.2429 | 0.5319 |

**Exported `model_config.json` schema (from cell 21):**
`project, dataset, selected_meter, timestamp_column, target_column,
forecast_features, anomaly_features, anomaly_contamination,
forecast_horizon_hours, data_frequency, training_period_start/end,
testing_period_start/end`.

### A.5 Dependency conflicts & environment

- The notebook installs **unpinned** `pandas numpy scikit-learn matplotlib
  seaborn joblib`; no versions were recorded in notebook metadata. The
  scikit-learn version used to train the (missing) joblib files is therefore
  **unknown** → joblib/pickle compatibility cannot be verified offline.
- No `requirements.txt` exists → no conflicts, but also no reproducibility.
- Local environment (verified): Python 3.13.15, FastAPI 0.141.1, Pydantic
  2.13.5, pydantic-settings 2.15.0, Uvicorn 0.52.4, pytest 9.1.1, httpx 0.28.1,
  NumPy 2.5.3; **installed for this project:** scikit-learn 1.9.1, pandas 3.0.6,
  joblib 1.6.0. All backend code will be pinned to these verified versions.

### A.6 Integration risks

1. **No model artifacts in the repo** → forecast/anomaly endpoints must return
   structured `503` until artifacts are placed in `backend/artifacts/`.
2. **Training sklearn version unknown** → loading real artifacts may fail on
   version mismatch; registry must catch and report this clearly.
3. **No frontend exists** → integration contract must be documented (types,
   `API_BASE_URL`, states) for teammates to build against.
4. **Git friction recorded in the notebook** (failed pushes, wrong git email) —
   history shows `main` only ever received one web-upload commit. Work stays on
   local `main`, uncommitted, so teammates' future changes are untouched.
5. Feature drift risk: if the team retrains with different features, the
   registry detects config/feature mismatch instead of predicting garbage.

---

## PART B — PHASE 2: ARCHITECTURE, API CONTRACTS, DEPENDENCY PLAN

### B.1 Stack & versions (all locally verified)

Python 3.13 · FastAPI 0.141.1 · Pydantic 2.13.5 · pydantic-settings 2.15.0 ·
pandas 3.0.6 · NumPy 2.5.3 · scikit-learn 1.9.1 · joblib 1.6.0 ·
uvicorn 0.52.4 · pytest 9.1.1 · httpx 0.28.1.

### B.2 Module layout (new `backend/` tree; the existing notebook is untouched)

```
backend/
  app/
    main.py                  # app factory, lifespan, middleware, handlers
    api/v1/                  # router, health, energy, forecasts, anomalies, carbon, scenarios
    core/                    # config (env-based), structured logging, exceptions
    schemas/                 # Pydantic request/response models
    services/                # model_registry, data_validation, statistics,
                             # energy, forecast, anomaly, carbon, scenario
    utils/                   # timestamps (hourly grid), metrics
    tests/                   # pytest suite with synthetic fixtures
  artifacts/                 # drop-in dir for joblib artifacts (binaries git-ignored)
  scripts/train_demo_artifacts.py   # clearly-labeled synthetic demo artifacts
  requirements.txt  .env.example  Dockerfile  README.md
docs/AUDIT_AND_PLAN.md  docs/VERIFICATION_REPORT.md
```

### B.3 Model lifecycle design

- `ModelRegistry` loads **once during FastAPI lifespan startup**: reads
  `model_config.json`, `anomaly_model.joblib`, `forecast_model.joblib`,
  `forecast_metrics.json` from `MODEL_ARTIFACTS_DIR` (env-configurable).
- Per-model statuses: `loaded | missing | invalid | config_missing |
  feature_mismatch`, surfaced by `GET /api/v1/ready`.
- Validation on load: file exists & readable → `joblib.load` in try/except →
  type check (`IsolationForest` / `HistGradientBoostingRegressor`) → feature
  list must be a subset of the backend's supported engineering (config order is
  authoritative for column ordering).
- Model `version` = `sha256-<first 12 hex of artifact file>` plus dataset/training
  metadata from config (no invented version strings).
- Missing/invalid model → affected endpoints return structured `503`; **never**
  retraining, never downloading, never fake predictions. Detailed paths and
  tracebacks go to server logs only.
- Tests inject in-memory synthetic models via dependency injection
  (`registry.set_model(...)`, labeled `source="test_fixture"`); a separate
  script can produce clearly-labeled `synthetic_demo` artifacts for manual
  smoke tests — never presented as BDG2-trained.

### B.4 API contract (prefix `/api/v1`, JSON errors `{"error": {code, message, details}}`)

| Endpoint | Purpose | Failure modes |
|---|---|---|
| `GET /health` | liveness, version | always 200 while process runs |
| `GET /ready` | readiness incl. per-model status | 200 ready / 503 degraded |
| `POST /energy/analyze` | stats + optional anomaly flags + warnings + provenance | 422 validation; degrades gracefully if anomaly model absent |
| `POST /forecast` | next-hour estimate only (`horizon_hours` ≠ 1 → 422 `unsupported_forecast_horizon`; history < 168 h coverage → 422 `insufficient_history`; model absent → 503) | |
| `POST /anomalies/detect` | labels `-1/1`, score = `-score_samples`, interpretation disclaimer | 503 if model absent |
| `POST /carbon/summary` | `kg = kWh × factor` with full factor provenance | 422 `emission_factor_not_configured` if unset — **no default factor shipped** |
| `POST /scenarios/simulate` | deterministic baseline-vs-intervention math | 422 for out-of-range params |
| `GET /docs`, `GET /openapi.json` | Swagger UI / OpenAPI | — |

Status codes: `400` malformed JSON · `413` oversized body · `422` schema/
validation · `503` model unavailable · `500` unexpected (no stack traces).

**Shared logic:** `/energy/analyze` and `/anomalies/detect` both call
`anomaly_service.detect()`; forecast and analyze share `data_validation`
normalization (sort, duplicate-mean, warnings) and the exact training-time
hourly-grid/interpolation preprocessing for feature engineering.

### B.5 Validation rules (enforced, never silent)

- `energy_kwh`: finite (`NaN`/`inf` rejected), `≥ 0` (negatives invalid for
  this data source → 422 listing offending rows).
- Timestamps: ISO-8601; naive treated as UTC (documented); mixing naive and
  aware → 422; unparseable → 422.
- Duplicates → mean-aggregated **with warning**; out-of-order → sorted **with
  warning**; missing hours ≠ zero (interpolation only inside forecast feature
  engineering, ≤ 3 h, matching training, and reported as a warning).
- Request caps: `MAX_READINGS_PER_REQUEST` (default 50 000) → 422;
  `Content-Length > MAX_REQUEST_BYTES` (10 MB) → 413.
- Forecast leakage guard: features for target hour `T = last + 1h` use only
  data `< T` (lags `T-1/T-24/T-168`, rolling window `T-24..T-1`).

### B.6 Configuration (`.env.example`, placeholders only)

`ENVIRONMENT`, `LOG_LEVEL`, `LOG_FORMAT`, `CORS_ALLOW_ORIGINS`,
`MODEL_ARTIFACTS_DIR`, `MAX_READINGS_PER_REQUEST`, `MAX_REQUEST_BYTES`,
`CARBON_EMISSION_FACTOR` + `CARBON_FACTOR_SOURCE/REGION/YEAR/UNITS/EFFECTIVE_DATE`
(all carbon fields unset by default — no invented grid factor).

CORS defaults to `http://localhost:5173,http://localhost:3000` only.

### B.7 Test plan (synthetic fixtures, marked; real-artifact tests auto-skip)

Health vs readiness distinction · missing/invalid artifacts · registry init ·
valid/invalid energy payloads · forecast feature generation & exact-value
agreement with direct `model.predict` · insufficient history · anomaly label
interpretation (outlier → `-1`, typical → `1`, score direction) · carbon math
with a known test factor · deterministic scenario math · NaN/inf/negative/
timestamp/duplicate/out-of-order handling · CORS allowed/disallowed origins ·
structured errors (400/413/422/503).

### B.8 Deployment

`uvicorn app.main:app --reload` from `backend/`; Dockerfile (`python:3.13-slim`)
mounting `artifacts/`; no database, queue, auth, or cloud credentials.

---

## PHASE EXECUTION STATUS

- [x] Phase 1 — audit complete (this document, Part A)
- [x] Phase 2 — architecture & plan (this document, Part B)
- [x] Phase 3 — scaffold, config, schemas, registry
- [x] Phase 4 — energy/anomaly/forecast services
- [x] Phase 5 — carbon & scenario services
- [x] Phase 6 — routes, validation, error handling
- [x] Phase 7 — tests + smoke tests (74 passed, 1 skipped)
- [x] Phase 8 — frontend integration docs (backend/README.md §5)
- [x] Phase 9 — final verification report → `docs/VERIFICATION_REPORT.md`
