"""Tests: health vs readiness distinction and degraded readiness payloads."""

from __future__ import annotations

import json

from .conftest import make_client, make_settings


def test_health_returns_ok_and_version():
    with make_client() as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "Fluxora API"
    assert body["version"]
    assert body["timestamp"].endswith("+00:00")


def test_health_ok_even_when_models_missing(degraded_registry):
    """Liveness must not depend on artifacts."""
    with make_client(registry=degraded_registry) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_ready_degraded_without_artifacts(degraded_registry):
    with make_client(registry=degraded_registry) as client:
        response = client.get("/api/v1/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["ready"] is False
    assert set(body["models"]) == {"anomaly", "forecast"}
    assert body["model_config_status"] in {"missing", "invalid", "config_missing"}
    assert body["notes"], "degraded readiness must explain itself"
    assert body["carbon_factor_configured"] is False


def test_ready_ok_with_loaded_models(loaded_registry):
    with make_client(registry=loaded_registry) as client:
        response = client.get("/api/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["models"]["anomaly"]["status"] == "loaded"
    assert body["models"]["forecast"]["status"] == "loaded"
    # Synthetic fixtures must be disclosed, never silent.
    assert any("SYNTHETIC" in note for note in body["notes"])


def test_ready_does_not_leak_filesystem_paths(degraded_registry):
    with make_client(registry=degraded_registry) as client:
        payload = client.get("/api/v1/ready").text
    body = json.loads(payload)
    serialized = json.dumps(body)
    assert "C:" not in serialized
    assert "/home/" not in serialized
    assert "Traceback" not in serialized


def test_root_lists_service_entrypoints():
    with make_client() as client:
        body = client.get("/").json()
    assert body["docs"] == "/docs"
    assert body["health"] == "/api/v1/health"


def test_settings_cors_defaults():
    settings = make_settings()
    assert settings.cors_origins_list == [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
