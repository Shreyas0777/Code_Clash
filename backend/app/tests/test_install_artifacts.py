"""Tests for ``scripts/install_artifacts.py``.

The success paths monkeypatch the expected checksums so they run on any
clone; when the genuine artifacts are present an additional end-to-end test
installs a real ZIP built from them (the same files are re-zipped in a
temporary directory — the source artifacts are never modified).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "install_artifacts.py"
ARTIFACTS_DIR = BACKEND_ROOT / "artifacts"

_spec = importlib.util.spec_from_file_location("install_artifacts", SCRIPT_PATH)
assert _spec and _spec.loader
install_artifacts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install_artifacts)

REQUIRED = install_artifacts.REQUIRED_MEMBERS

REAL_ARTIFACTS_PRESENT = (
    (ARTIFACTS_DIR / "anomaly_model.joblib").is_file()
    and (ARTIFACTS_DIR / "forecast_model.joblib").is_file()
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def dummy_members(anomaly: bytes, forecast: bytes) -> dict[str, bytes]:
    return {
        "anomaly_model.joblib": anomaly,
        "forecast_model.joblib": forecast,
        "model_config.json": json.dumps({"synthetic": True}),
        "forecast_metrics.json": json.dumps({"rmse": 0.0}),
    }


@pytest.fixture()
def patched_hashes(monkeypatch: pytest.MonkeyPatch):
    """Point the script's expected checksums at deterministic dummy content."""
    anomaly = b"dummy-anomaly-bytes"
    forecast = b"dummy-forecast-bytes"
    monkeypatch.setattr(
        install_artifacts, "EXPECTED_ANOMALY_SHA256", sha256_bytes(anomaly)
    )
    monkeypatch.setattr(
        install_artifacts, "EXPECTED_FORECAST_SHA256", sha256_bytes(forecast)
    )
    return anomaly, forecast


def test_missing_zip_returns_2(tmp_path: Path) -> None:
    assert install_artifacts.main([str(tmp_path / "nope.zip")]) == 2


def test_invalid_zip_returns_2(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.zip"
    bogus.write_bytes(b"this is not a zip archive")
    assert install_artifacts.main([str(bogus)]) == 2


def test_missing_required_member_returns_2(
    tmp_path: Path, patched_hashes
) -> None:
    anomaly, forecast = patched_hashes
    members = dummy_members(anomaly, forecast)
    del members["forecast_model.joblib"]
    zip_path = make_zip(tmp_path / "incomplete.zip", members)
    assert (
        install_artifacts.main([str(zip_path), "--dest", str(tmp_path / "out")]) == 2
    )


def test_checksum_mismatch_returns_3(tmp_path: Path, patched_hashes) -> None:
    """A zip whose content does not match the pinned hashes must be refused."""
    anomaly, forecast = patched_hashes
    members = dummy_members(anomaly, forecast)
    members["anomaly_model.joblib"] = anomaly + b" tampered"
    zip_path = make_zip(tmp_path / "tampered.zip", members)
    assert install_artifacts.main([str(zip_path), "--dest", str(tmp_path / "out")]) == 3
    assert not (tmp_path / "out" / "anomaly_model.joblib").exists()


def test_invalid_json_member_returns_3(
    tmp_path: Path, patched_hashes
) -> None:
    anomaly, forecast = patched_hashes
    members = dummy_members(anomaly, forecast)
    members["model_config.json"] = b"{not json"
    zip_path = make_zip(tmp_path / "badjson.zip", members)
    assert install_artifacts.main([str(zip_path), "--dest", str(tmp_path / "out")]) == 3


def test_success_then_overwrite_protection_then_force(
    tmp_path: Path, patched_hashes
) -> None:
    anomaly, forecast = patched_hashes
    zip_path = make_zip(tmp_path / "good.zip", dummy_members(anomaly, forecast))
    dest = tmp_path / "out"

    assert install_artifacts.main([str(zip_path), "--dest", str(dest)]) == 0
    for member in REQUIRED:
        assert (dest / member).is_file()
    assert sha256_bytes((dest / "anomaly_model.joblib").read_bytes()) == (
        sha256_bytes(anomaly)
    )

    # Re-run without --force: refuse (exit 4) and leave files untouched.
    sentinel = dest / "anomaly_model.joblib"
    original = sentinel.read_bytes()
    assert install_artifacts.main([str(zip_path), "--dest", str(dest)]) == 4
    assert sentinel.read_bytes() == original

    # Re-run with --force: allowed.
    assert install_artifacts.main([str(zip_path), "--dest", str(dest), "--force"]) == 0


def test_top_level_folder_prefix_is_tolerated(
    tmp_path: Path, patched_hashes
) -> None:
    anomaly, forecast = patched_hashes
    members = {
        f"fluxora_artifacts/{name}": data
        for name, data in dummy_members(anomaly, forecast).items()
    }
    zip_path = make_zip(tmp_path / "nested.zip", members)
    assert (
        install_artifacts.main([str(zip_path), "--dest", str(tmp_path / "out")]) == 0
    )


@pytest.mark.skipif(
    not REAL_ARTIFACTS_PRESENT,
    reason="genuine BDG2 artifacts not present in backend/artifacts/ "
    "(install with: python scripts/install_artifacts.py <zip>)",
)
def test_real_zip_end_to_end(tmp_path: Path, monkeypatch) -> None:
    """Round-trip the genuine artifacts through the installer unmodified."""
    monkeypatch.setattr(install_artifacts, "BACKEND_ROOT", tmp_path)
    source_zip = tmp_path / "real.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        for member in REQUIRED:
            archive.write(ARTIFACTS_DIR / member, member)

    dest = tmp_path / "installed"
    assert install_artifacts.main([str(source_zip), "--dest", str(dest)]) == 0
    for member in ("anomaly_model.joblib", "forecast_model.joblib"):
        source_hash = hashlib.sha256((ARTIFACTS_DIR / member).read_bytes()).hexdigest()
        installed_hash = hashlib.sha256((dest / member).read_bytes()).hexdigest()
        assert installed_hash == source_hash
