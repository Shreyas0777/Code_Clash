"""Tests: error contract, CORS policy, request limits, API documentation."""

from __future__ import annotations

from datetime import datetime

from .conftest import make_client, make_settings

BASE = datetime(2026, 3, 2, 0, 0)


def test_cors_allows_configured_origin():
    with make_client() as client:
        response = client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:5173"},
        )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin():
    with make_client() as client:
        response = client.get(
            "/api/v1/health",
            headers={"Origin": "https://evil.example"},
        )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") is None


def test_cors_second_allowed_origin():
    with make_client() as client:
        response = client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:3000"},
        )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_malformed_json_returns_structured_400():
    with make_client() as client:
        response = client.post(
            "/api/v1/energy/analyze",
            content="{not valid json",
            headers={"content-type": "application/json"},
        )
    assert response.status_code in (400, 422)
    body = response.json()
    assert body["error"]["code"] in {"invalid_json", "request_validation_error"}
    assert "Traceback" not in response.text


def test_unknown_path_returns_structured_404():
    with make_client() as client:
        response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_oversized_request_rejected_with_413():
    settings = make_settings(max_request_bytes=512)
    with make_client(settings=settings) as client:
        response = client.post(
            "/api/v1/energy/analyze",
            json={
                "meter_id": "m",
                "readings": [
                    {"timestamp": BASE.isoformat(), "energy_kwh": float(i)}
                    for i in range(200)
                ],
            },
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_validation_errors_use_standard_envelope():
    with make_client() as client:
        response = client.post(
            "/api/v1/energy/analyze",
            json={"meter_id": "", "readings": [{"timestamp": BASE.isoformat(), "energy_kwh": 1.0}]},
        )
    assert response.status_code == 422
    body = response.json()
    assert set(body["error"]) == {"code", "message", "details"}
    assert isinstance(body["error"]["details"], list)


def test_error_response_has_no_stack_trace_or_paths():
    with make_client() as client:
        response = client.post(
            "/api/v1/carbon/summary",
            json={"meter_id": "m", "readings": [{"timestamp": BASE.isoformat(), "energy_kwh": 1.0}]},
        )
    assert response.status_code == 422
    text = response.text
    assert "Traceback" not in text
    assert "site-packages" not in text
    assert "C:" not in text


def test_openapi_document_contains_all_endpoints():
    with make_client() as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for path in (
        "/api/v1/health",
        "/api/v1/ready",
        "/api/v1/energy/analyze",
        "/api/v1/forecast",
        "/api/v1/anomalies/detect",
        "/api/v1/carbon/summary",
        "/api/v1/scenarios/simulate",
    ):
        assert path in paths


def test_swagger_ui_accessible():
    with make_client() as client:
        response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


def test_request_id_header_present():
    with make_client() as client:
        response = client.get("/api/v1/health")
    assert response.headers.get("x-request-id")
