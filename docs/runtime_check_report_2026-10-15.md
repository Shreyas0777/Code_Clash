# Fluxora Backend — Runtime Verification Report

**Date:** 2026-10-15
**Environment:** Windows, Python 3.13, scikit-learn 1.9.1 (runtime), artifacts trained on 1.6.1
**Scope:** Does everything I built still run? Is the API connected to the backend end-to-end?

---

## 1. Automated test suite — PASS

| Check | Command | Result | Exit code |
|---|---|---|---|
| Full test suite | `python -m pytest app/tests -q` | **85 passed, 0 skipped** in 10.6 s | **0** |
| Dead-code scan | `python -m pyflakes app/ scripts/` | clean, no findings | **0** |

Notes:
- The 8 `test_real_artifacts_integration.py` tests **ran for real** (not skipped): the genuine
  BDG2 Colab artifacts are present in `backend/artifacts/` and their SHA-256 hashes match the
  checksums pinned in the tests (`7dd68ffe…` anomaly, `00e6bfe3…` forecast).
- `pytest` emits `InconsistentVersionWarning` (artifacts pickled with scikit-learn **1.6.1**,
  loaded with **1.9.1**). All parity tests still pass — API output equals direct-model output —
  but this is a real forward-compatibility risk documented in §6 below.

## 2. Server startup — PASS

`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`

- Ready in **< 1 s**: `GET /api/v1/health` → **200**
  `{"status":"ok","service":"Fluxora API","version":"0.1.0","environment":"development",…}`
- Lifespan startup loaded `model_config.json` and both real models with no errors.

## 3. Live API smoke test — every endpoint exercised over HTTP

Server tested at `http://127.0.0.1:8000/api/v1` with 200 real-pattern hourly readings
(diurnal sine wave + one injected 180 kWh spike), i.e. real client-style HTTP calls, not
the in-process test client.

| # | Endpoint | Status | Evidence |
|---|---|---|---|
| 1 | `GET /health` | **200** | service/version/environment payload |
| 2 | `GET /ready` | **200** | `ready: true`, both models `loaded`, `dataset: "Building Data Genome Project 2"`, `version: sha256-7dd68ffe830a` |
| 3 | `POST /energy/analyze` | **200** | 200 valid readings, stats mean 121.95 / max 280.0 kWh, period 2016-06-01 → 2016-06-09 |
| 4 | `POST /forecast` | **200** | next-hour prediction **159.94 kWh**, `horizon_hours: 1`, model provenance returned |
| 5 | `POST /anomalies/detect` | **200** | scored all readings with the real IsolationForest, per-reading results returned |
| 6 | `POST /scenarios/simulate` | **200** | 1000 kWh − 12 % → 880 projected, 120 kWh saved — arithmetic correct, projection disclaimer attached |
| 7 | `POST /carbon/summary` (config set) | **200** | second instance on :8001 with `CARBON_EMISSION_FACTOR=0.42` → 210 kWh × 0.42 = **88.2 kg CO₂**, source/region/year echoed back |
| 8 | `POST /carbon/summary` (config unset) | **422** | structured `emission_factor_not_configured` error naming exactly which env vars to set — correct by design |
| 9 | `POST /energy/analyze` with invalid payload (`meter_id:""`, bad timestamp, negative kWh) | **422** | `request_validation_error` with per-field details, no stack trace leaked |
| 10 | `GET /nope` (unknown route) | **404** | structured `not_found` error envelope |

**OpenAPI / docs:** `GET /docs` → 200 (Swagger UI), `GET /openapi.json` → 200,
**7 routes** registered under `/api/v1`.

**CORS (frontend connectivity):** `OPTIONS` preflight with `Origin: http://localhost:5173`
→ **200** with `Access-Control-Allow-Origin: http://localhost:5173`. A browser frontend on
Vite/any dev port can call the API.

**Conclusion: the API layer is connected to the backend service layer end-to-end.** Every
endpoint accepts an HTTP request, validates it, reaches the real BDG2 models (or the
deterministic services), and returns a structured response.

## 4. Clean shutdown

Both test instances (:8000 and :8001) were terminated (`taskkill /T /F` on the listener PIDs)
and both ports verified closed afterwards. No stray processes.

## 5. What is NOT verified

| Item | Status | Why |
|---|---|---|
| Docker image build | **could not run** | Docker not installed in this environment; `Dockerfile`/`docker-compose.yml` are committed but unbuilt |
| Real BDG2 `.joblib` artifacts in git | **intentionally absent** | git-ignored by design; a fresh clone runs 77 passed / **8 skipped** until the ZIP is placed in `backend/artifacts/` |
| Production/TLS deployment | not in scope | verified only on loopback |

## 6. Known limitations & risks (unchanged, documented)

1. **scikit-learn version skew:** artifacts trained on **1.6.1** load under **1.9.1** with a
   persistent `InconsistentVersionWarning`. Parity tests pass today, but retraining or pinning
   `scikit-learn==1.6.1` in `requirements.txt` is the durable fix.
2. **Carbon factor is deployment config:** `/carbon/summary` intentionally 422s until
   `CARBON_EMISSION_FACTOR` + source/region/units are set (see `backend/.env.example`).
3. **Frontend:** there is still **no website code in the repository** — this report verifies
   the backend and its HTTP contract only.

## 7. Repository state

- Cleanup pass: **22 files modified (+179/−49), uncommitted** — awaiting go-ahead to commit/push.
- Servers started for this check were stopped; nothing left running.
