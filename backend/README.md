# Fluxora Backend — Energy Intelligence & Carbon Optimization

> **Decode Energy. Design a Greener Future.**

FastAPI service that validates hourly electricity readings, detects unusual
readings, forecasts next-hour demand, estimates operational carbon emissions,
and simulates energy-saving interventions — using the scikit-learn models
trained in the team's Colab notebook (`fluxora_model_training..ipynb`).

**Honesty rules this API is built around**

- Predictions are labeled `estimate`, never measurements.
- Anomaly flags mean *unusual reading*, never *confirmed fault*.
- Missing model artifacts degrade specific endpoints with `503` — the API
  **never fabricates predictions**. Check `GET /api/v1/ready`.
- No default carbon emission factor ships with the code; `/carbon/summary`
  refuses (422) until a documented factor is configured.
- Scenario results are deterministic projections of caller-supplied
  assumptions — never measured savings.

---

## 1. Quick start

```bash
cd backend
python -m pip install -r requirements.txt

# Run the API (from backend/)
uvicorn app.main:app --reload
```

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>

Requires **Python 3.13** (pinned versions in `requirements.txt`; 3.11+ should
work once re-verified).

### Tests

```bash
cd backend
python -m pytest app/tests -q
```

Tests use **synthetic fixtures only** (marked in `conftest.py`); no dataset
and no real artifacts are required. The integration tests that need the
genuine Colab export (the registry smoke test plus the 7 checksum-pinned
tests in `test_real_artifacts_integration.py`) auto-skip while the artifacts
are absent.

### Docker

```bash
cd backend
docker build -t fluxora-api .
docker run --rm -p 8000:8000 -v "$(pwd)/artifacts:/app/artifacts:ro" fluxora-api

# or, equivalently:
docker compose up --build
```

Artifacts are **mounted at runtime, never baked into the image** (enforced by
both the Dockerfile and `.dockerignore`), so the build succeeds on any clone.
Without artifacts the container still starts; `/ready` reports degraded.
Configured with `hadolint` (clean) and `docker-compose` port/volume checks.

---

## 2. Model artifacts (required for forecast/anomaly endpoints)

The Colab notebook exports four files (`/content/artifacts/`, cell 21-22).
**They are not in the repository** — a teammate must place them:

```
backend/artifacts/
├── anomaly_model.joblib      # IsolationForest
├── forecast_model.joblib     # HistGradientBoostingRegressor
├── model_config.json         # REQUIRED — training-time feature contract
└── forecast_metrics.json     # optional
```

Then install and verify:

```bash
python scripts/install_artifacts.py path/to/fluxora_trained_models.zip
# verifies the SHA-256 checksums pinned by the real-artifact tests,
# refuses overwrites without --force
curl http://127.0.0.1:8000/api/v1/ready   # expect "ready": true
```

Details, troubleshooting and the trusted-source warning:
[`artifacts/README.md`](artifacts/README.md).

**Verified training contracts the backend reproduces exactly** (read from the
committed notebook): feature names/order, `hour/day_of_week/month` calendar
features, lags `1/24/168`, `rolling_mean_24 = shift(1).rolling(24)`, hourly
grid + time-interpolation limit 3 (inside only), duplicate timestamps
aggregated by mean, negatives treated as invalid, IsolationForest output
`-1 = anomaly / 1 = typical`, score = `-score_samples` (higher = more
unusual; **not** a probability), single-step horizon (1 h).

Without artifacts the API still runs: `/health` 200, `/ready` 503 with
per-model reasons, forecast/anomaly endpoints 503 with structured errors. For
UI development you can generate **clearly-labeled synthetic demo artifacts**:

```bash
python scripts/train_demo_artifacts.py
# synthetic: true + artifact_source: synthetic_demo_local are disclosed
# by /ready and every model response — never present them as real results.
```

---

## 3. Configuration (`.env`)

Copy `.env.example` → `.env`. Placeholders only; **no secrets are committed**.

| Variable | Default | Meaning |
|---|---|---|
| `ENVIRONMENT` | `development` | deployment label |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `json` | structured logging |
| `CORS_ALLOW_ORIGINS` | `http://localhost:5173,http://localhost:3000` | explicit allowed origins (never `*`) |
| `MODEL_ARTIFACTS_DIR` | `backend/artifacts` | artifact directory |
| `MAX_READINGS_PER_REQUEST` | `50000` | per-request reading cap (422 above) |
| `MAX_REQUEST_BYTES` | `10485760` | body-size cap (413 above) |
| `CARBON_EMISSION_FACTOR` | *unset* | kg CO2 / kWh — **required for /carbon/summary** |
| `CARBON_FACTOR_SOURCE` / `_REGION` | *unset* | **required provenance** |
| `CARBON_FACTOR_YEAR` / `_EFFECTIVE_DATE` / `_UNITS` | `kg_CO2_per_kwh` | recommended provenance |

> Set `CARBON_EMISSION_FACTOR` only from a documented source (official grid
> factor publication, region, year, units). This project deliberately does
> not ship or invent a value.

---

## 4. API contract

Base path: **`/api/v1`**. All bodies are JSON. All errors share one envelope:

```json
{ "error": { "code": "insufficient_history", "message": "…", "details": [
    { "field": "readings", "message": "…", "type": "…" } ] } }
```

| Status | Meaning |
|---|---|
| `400` | malformed JSON body |
| `404` | unknown route |
| `413` | body exceeds `MAX_REQUEST_BYTES` |
| `422` | schema/validation failure, unsupported horizon, insufficient history, missing emission-factor config |
| `503` | required model artifact unavailable (structured `error.code`) |
| `500` | unexpected error or `model_inference_failed` (message only; details in server logs) |

### `GET /api/v1/health` — liveness

```json
{ "status": "ok", "service": "Fluxora API", "version": "0.1.0",
  "environment": "development", "timestamp": "2026-10-14T16:46:21+00:00" }
```

### `GET /api/v1/ready` — readiness (distinct from health)

`200` when all required artifacts loaded, `503` while degraded:

```json
{ "ready": false, "model_config_status": "missing",
  "models": { "anomaly": { "status": "config_missing", "version": null,
                           "dataset": null, "model_class": null,
                           "feature_names": null,
                           "error_code": "model_config_missing",
                           "error_detail": "…" }, "forecast": { … } },
  "carbon_factor_configured": false,
  "notes": [ "Degraded readiness: …" ], "api_version": "0.1.0" }
```

Model `version` is `sha256-<12 hex>` of the artifact file (or an explicit
fixture label in tests). Filesystem paths never appear in responses.

### `POST /api/v1/energy/analyze`

Validates readings, returns statistics, and adds anomaly flags **when the
anomaly model is available** (otherwise those fields are `null` with an
`anomaly_model_unavailable` warning — statistics are never blocked).

```bash
curl -X POST http://127.0.0.1:8000/api/v1/energy/analyze \
  -H 'content-type: application/json' \
  -d '{"meter_id":"meter_demo_01","readings":[
        {"timestamp":"2026-10-10T10:00:00Z","energy_kwh":21.4},
        {"timestamp":"2026-10-10T11:00:00Z","energy_kwh":24.1}]}'
```

```json
{ "meter_id": "meter_demo_01",
  "period": { "start": "2026-10-10T10:00:00", "end": "2026-10-10T11:00:00" },
  "valid_readings": 2,
  "stats": { "count": 2, "mean_kwh": 22.75, "min_kwh": 21.4,
             "max_kwh": 24.1, "total_kwh": 45.5 },
  "anomaly_count": null, "flagged_readings": null,
  "warnings": [ { "code": "anomaly_model_unavailable", "message": "…", "count": null } ],
  "dataset_provenance": "Building Data Genome Project 2",
  "anomaly_model": { "name": "anomaly", "status": "unavailable",
                     "version": null, "dataset": null },
  "anomaly_interpretation": null }
```

Validation rules: `energy_kwh` finite and `≥ 0` (NaN/Infinity/negatives →
422); ISO-8601 timestamps (naive = UTC, mixing naive/aware → 422);
duplicates aggregated by mean **with warning**; out-of-order sorted **with
warning**; cap `MAX_READINGS_PER_REQUEST` → 422.

### `POST /api/v1/forecast` — next-hour estimate (1 h only)

Requires ≥168 hours of coverage before the forecast hour (the trained
`lag_168`), with no gap >3 h in the required window (training-time rule;
missing hours are interpolated ≤3 h — **never treated as zero**).

```bash
curl -X POST http://127.0.0.1:8000/api/v1/forecast \
  -H 'content-type: application/json' \
  -d '{"meter_id":"m","readings":[ …168+ hourly readings… ],"horizon_hours":1}'
```

```json
{ "meter_id": "m", "forecast_timestamp": "2026-02-04T00:00:00",
  "predicted_energy_kwh": 118.584, "horizon_hours": 1, "unit": "kWh",
  "prediction_type": "estimate",
  "model": { "name": "forecast", "status": "loaded",
             "version": "sha256-abc123def456",
             "dataset": "Building Data Genome Project 2" },
  "input_period": { "start": "2026-01-05T00:00:00", "end": "2026-02-03T23:00:00" },
  "warnings": [], "interpretation_note": "This value is a model-generated estimate…" }
```

Errors: `horizon_hours != 1` → 422 `unsupported_forecast_horizon`;
missing history → 422 `insufficient_history` (details state the 168-h
requirement and actual coverage); no model → 503.

### `POST /api/v1/anomalies/detect`

Same input shape as `/energy/analyze`; shares the same inference service.

```json
{ "meter_id": "m",
  "model": { "name": "anomaly", "status": "loaded", "version": "sha256-…", "dataset": "…" },
  "results": [ { "timestamp": "2026-03-02T10:00:00", "energy_kwh": 5000.0,
                 "label": "anomaly", "model_output": -1,
                 "anomaly_score": 0.6123 } ],
  "anomaly_count": 1, "warnings": [],
  "interpretation": "An anomaly flag indicates a reading that is unusual … not a confirmed equipment fault …" }
```

`model_output`: `-1` anomaly, `1` typical. `anomaly_score` =
`-score_samples()` — **relative score, higher = more unusual; not a
calibrated probability**. No model → 503.

### `POST /api/v1/carbon/summary`

`emissions_kg_co2 = energy_kwh × emission_factor_kg_co2_per_kwh`

```bash
# requires CARBON_EMISSION_FACTOR + SOURCE + REGION (+ recommended YEAR/DATE)
curl -X POST http://127.0.0.1:8000/api/v1/carbon/summary \
  -H 'content-type: application/json' \
  -d '{"meter_id":"meter_demo_01","readings":[ … ]}'
```

```json
{ "meter_id": "meter_demo_01",
  "period": { "start": "…", "end": "…" },
  "energy_total_kwh": 300.0,
  "emission_factor": { "value": 0.713, "units": "kg_CO2_per_kwh",
                       "source": "…", "region": "…", "year": 2024,
                       "effective_date": "2024-04-01" },
  "emissions_kg_co2": 213.9,
  "calculation": "emissions_kg_co2 = energy_kwh × emission_factor_kg_co2_per_kwh",
  "assumptions": [ "…" ], "provenance": "… — region: …", "warnings": [] }
```

Unconfigured factor → 422 `emission_factor_not_configured`; missing
source/region → 422 `emission_factor_metadata_incomplete`; other units → 422
`unsupported_emission_factor_units`.

### `POST /api/v1/scenarios/simulate` — deterministic projection

```bash
curl -X POST http://127.0.0.1:8000/api/v1/scenarios/simulate \
  -H 'content-type: application/json' \
  -d '{"scenario_name":"led_retrofit",
       "baseline_energy_kwh":1000,"reduction_percent":15,
       "tariff_per_kwh":8.5,"currency":"INR",
       "emission_factor_kg_co2_per_kwh":0.7,
       "emission_factor_source":"caller-supplied assumption"}'
```

```json
{ "scenario_name": "led_retrofit",
  "baseline_energy_kwh": 1000.0, "reduction_percent": 15.0,
  "projected_energy_kwh": 850.0, "energy_savings_kwh": 150.0,
  "tariff_per_kwh": 8.5, "currency": "INR", "cost_savings": 1275.0,
  "emission_factor_kg_co2_per_kwh": 0.7, "emissions_reduction_kg_co2": 105.0,
  "assumptions": [ "…" ], "parameters": { …request echo… },
  "interpretation_note": "These results are deterministic projections … not measured …" }
```

Validation: `0 ≤ reduction_percent ≤ 100`, `baseline_energy_kwh > 0`,
`tariff_per_kwh ≥ 0`, `emission_factor > 0`, finite values only, `currency`
required. No ML involved.

---

## 5. Frontend integration

> **Status:** the repository currently contains **no frontend** — this is the
> contract to build against (see `docs/AUDIT_AND_PLAN.md`).

1. **Configurable base URL — never hardcode localhost:**

   ```bash
   # .env of the frontend (e.g. Vite)
   VITE_API_BASE_URL=http://127.0.0.1:8000
   # Next.js
   NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
   ```

   ```ts
   const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
   const api = (path: string) => `${API_BASE_URL}/api/v1${path}`;
   ```

2. **CORS:** the backend only allows `http://localhost:5173` and
   `http://localhost:3000` by default — add your dev origin to
   `CORS_ALLOW_ORIGINS` if different.

3. **Dashboard view → endpoint map:**

   | Fluxora view | Endpoint | Key fields |
   |---|---|---|
   | Energy overview & consumption trends | `POST /energy/analyze` | `stats`, `period`, `warnings` |
   | Anomaly alerts | `POST /anomalies/detect` (or `flagged_readings` from analyze) | `results[].label`, `anomaly_score`, `interpretation` |
   | Next-hour demand forecast | `POST /forecast` | `forecast_timestamp`, `predicted_energy_kwh`, `prediction_type` |
   | Carbon summary | `POST /carbon/summary` | `energy_total_kwh`, `emissions_kg_co2`, `emission_factor` |
   | Optimization scenario comparison | `POST /scenarios/simulate` | `projected_energy_kwh`, `cost_savings`, `emissions_reduction_kg_co2` |

4. **Required UI states** (the API supports telling them apart):

   - **Loading** — request in flight.
   - **Empty** — `readings: []` is rejected with 422; show an empty state
     *before* calling instead.
   - **Error** — non-2xx: render `error.message`, keep `error.code` for
     retry logic (`422` = fix input, `503` = backend degraded, `413/400` =
     payload problem).
   - **Degraded** — poll `GET /ready`; when `ready:false` show a banner from
     `notes[]` and render forecast/anomaly widgets as "model unavailable"
     (their fields are `null`, or the call returns 503). **Never substitute
     mock analytics while presenting them as real results.**
   - `prediction_type === "estimate"` and the `interpretation` /
     `interpretation_note` fields **must** be surfaced verbatim in the UI.

5. **TypeScript types** (match the Pydantic schemas):

   ```ts
   interface Reading { timestamp: string; energy_kwh: number }        // kWh >= 0, finite
   interface Warning  { code: string; message: string; count?: number | null }
   interface ModelInfo { name: string; status: "loaded" | "unavailable" | "error"
     | "feature_mismatch" | "config_missing"; version?: string | null; dataset?: string | null }
   interface ApiError { error: { code: string; message: string;
     details: { field: string | null; message: string; type: string | null }[] } }

   interface EnergyAnalyzeResponse {
     meter_id: string; period: { start: string | null; end: string | null };
     valid_readings: number;
     stats: { count: number; mean_kwh: number; min_kwh: number; max_kwh: number; total_kwh: number };
     anomaly_count: number | null;
     flagged_readings: { timestamp: string; energy_kwh: number; anomaly_score: number }[] | null;
     warnings: Warning[]; dataset_provenance: string | null;
     anomaly_model: ModelInfo; anomaly_interpretation: string | null;
   }
   interface ForecastResponse {
     meter_id: string; forecast_timestamp: string; predicted_energy_kwh: number;
     horizon_hours: 1; unit: "kWh"; prediction_type: "estimate";
     model: ModelInfo; input_period: { start: string | null; end: string | null };
     warnings: Warning[]; interpretation_note: string;
   }
   interface AnomalyResult { timestamp: string; energy_kwh: number;
     label: "anomaly" | "typical"; model_output: -1 | 1; anomaly_score: number }
   interface CarbonSummaryResponse {
     meter_id: string; period: { start: string | null; end: string | null };
     energy_total_kwh: number;
     emission_factor: { value: number; units: string; source: string; region: string;
       year: number | null; effective_date: string | null };
     emissions_kg_co2: number; calculation: string;
     assumptions: string[]; provenance: string; warnings: Warning[];
   }
   interface ScenarioResponse {
     scenario_name: string; intervention_description: string | null;
     baseline_energy_kwh: number; reduction_percent: number;
     projected_energy_kwh: number; energy_savings_kwh: number;
     tariff_per_kwh: number; currency: string; cost_savings: number;
     emission_factor_kg_co2_per_kwh: number; emissions_reduction_kg_co2: number;
     calculation_period: string; assumptions: string[];
     parameters: Record<string, unknown>; interpretation_note: string;
   }
   interface ReadyResponse {
     ready: boolean; model_config_status: string;
     models: Record<string, { status: string; version: string | null;
       dataset: string | null; model_class: string | null;
       feature_names: string[] | null; error_code?: string; error_detail?: string }>;
     carbon_factor_configured: boolean; notes: string[]; api_version: string;
   }
   ```

---

## 6. Architecture

```
backend/
├── app/
│   ├── main.py               # factory, lifespan (one-time model load), CORS,
│   │                         # size limits, request logging, error handlers
│   ├── api/v1/               # health · energy · forecasts · anomalies · carbon · scenarios
│   ├── core/                 # config (env) · structured logging · exceptions
│   ├── schemas/              # Pydantic request/response models
│   ├── services/
│   │   ├── model_registry.py # artifact load + validation + readiness + DI hooks
│   │   ├── data_validation.py# sort/dedup/timezone rules with warnings
│   │   ├── statistics_service.py
│   │   ├── energy_service.py # orchestration (stats + optional anomalies)
│   │   ├── anomaly_service.py# SHARED inference (analyze + detect)
│   │   ├── forecast_service.py # training-faithful features, leakage guards
│   │   ├── carbon_service.py # factor provenance enforcement
│   │   └── scenario_service.py # deterministic math
│   ├── utils/                # hourly grid + interpolation
│   └── tests/                # 85 tests, synthetic fixtures only
├── artifacts/                # drop-in model dir (binaries git-ignored)
├── scripts/train_demo_artifacts.py  # clearly-labeled SYNTHETIC demo models
├── requirements.txt  .env.example  Dockerfile  README.md
```

Design decisions: models load **once** in the lifespan (no retraining, no
downloads, no request-time file loads); inference lives in services shared by
routes; every data transformation that alters input is surfaced as a
`warnings[]` entry; model-inference failures return a structured 500
(`model_inference_failed`) while diagnostics stay in server logs only;
detailed diagnostics go to structured stdout logs only.

---

## 7. Model training & artifact compatibility

- Training notebook: `fluxora_model_training..ipynb` (repo root) — BDG2
  `electricity.csv`, meter `Robin_public_Carolina`, 17,544 hourly readings
  2016–2017, chronological 80/20 splits.
- Training environment is now recorded: **scikit-learn 1.6.1 (Google
  Colab)**, established by the real-model integration PR and pinned there by
  exact SHA-256 checksums of the genuine artifacts. The registry includes a
  cross-platform pickle-compat shim (`sys.modules["_loss"]`) so models
  serialized on Colab Linux unpickle cleanly elsewhere. `model_config.json`
  may carry an optional `training_library` key, which the registry surfaces
  and prefers; synthetic-flagged configs never claim the Colab environment.
- This project pins `scikit-learn==1.6.1` — the artifact training version —
  so the genuine artifacts unpickle with **zero version warnings** (verified
  by loading both models with `warnings.simplefilter("error")`). If
  `joblib.load` ever fails on the real files (deeper version mismatch),
  re-export the artifacts with the pinned version — the registry reports
  `model_artifact_invalid` in `/ready` when this happens.
- The backend validates on load: file readability, `IsolationForest` /
  `HistGradientBoostingRegressor` class, feature-name compatibility with the
  exported `model_config.json`, and feature-count consistency. Mismatches
  surface as `feature_mismatch` in `/ready` + `503` on affected endpoints —
  never as garbage predictions.

---

## 8. Known limitations & assumptions

1. **Model artifacts are not in the repository** — forecast/anomaly endpoints
   run in 503-degraded mode until the ZIP is placed (audit: `docs/AUDIT_AND_PLAN.md`).
2. Training environment is recorded (scikit-learn 1.6.1, Colab) and a
   pickle-compat shim is in place, but end-to-end compatibility is proven
   only by the checksum-pinned integration tests — which run solely when the
   genuine artifacts are present in `backend/artifacts/`.
3. Naive timestamps are interpreted as UTC; callers should send offsets (`Z`).
4. Single meter/time series per request; no database, auth, or persistence
   (intentionally lightweight — nothing in the app requires them).
5. One-step forecast model: multi-step horizons are rejected, not faked.
6. Carbon factor is flat per deployment; time-of-varying grid factors are not
   modeled.
7. Anomaly scores are uncalibrated relative scores; `contamination=0.02`
   shapes training, the observed flag rate can differ (the notebook saw
   3.79% on its holdout — recorded output, not re-measured here).
8. Repository currently has **no frontend**; integration guidance above is a
   contract, not working code.
