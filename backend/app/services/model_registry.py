"""Centralized model artifact registry.

Loads artifacts exactly once during application lifespan startup, validates
them, and serves them to inference services across requests.

Rules enforced here:
- No training at startup, no downloads, no retraining on requests.
- Missing/invalid artifacts degrade readiness and yield 503s on the affected
  endpoints — never silent fake predictions.
- Filesystem paths and stack traces stay in server logs, not API responses.
- Joblib/pickle artifacts are only loaded from the trusted, configured
  directory (see backend/README.md security notes).
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Colab / scikit-learn unpickling compatibility:
# In models serialized with scikit-learn 1.6 on Linux (e.g. Google Colab),
# CyHalfSquaredError references '_loss' instead of 'sklearn._loss._loss'.
# Provide a safe module alias so the genuine trained HistGradientBoostingRegressor
# loads cleanly across environments without modifying the serialized binary.
try:
    import sklearn._loss._loss
    if "_loss" not in sys.modules:
        sys.modules["_loss"] = sklearn._loss._loss
except (ImportError, AttributeError):
    pass

import joblib

from ..core.exceptions import ModelUnavailableError

logger = logging.getLogger("fluxora.model_registry")

CONFIG_FILE = "model_config.json"
METRICS_FILE = "forecast_metrics.json"

# Feature sets the backend knows how to engineer (from the training notebook).
SUPPORTED_FEATURES = {
    "energy_kwh",
    "hour",
    "day_of_week",
    "month",
    "lag_1",
    "lag_24",
    "lag_168",
    "rolling_mean_24",
}

MODEL_SPECS: Dict[str, Dict[str, Any]] = {
    "anomaly": {
        "file": "anomaly_model.joblib",
        "expected_class": "IsolationForest",
        "config_key": "anomaly_features",
        "fallback_features": ["energy_kwh", "hour", "day_of_week", "month"],
    },
    "forecast": {
        "file": "forecast_model.joblib",
        "expected_class": "HistGradientBoostingRegressor",
        "config_key": "forecast_features",
        "fallback_features": [
            "hour",
            "day_of_week",
            "month",
            "lag_1",
            "lag_24",
            "lag_168",
            "rolling_mean_24",
        ],
    },
}

STATUS_LOADED = "loaded"
STATUS_MISSING = "missing"
STATUS_INVALID = "invalid"
STATUS_CONFIG_MISSING = "config_missing"
STATUS_FEATURE_MISMATCH = "feature_mismatch"

_UNAVAILABLE_MESSAGE = (
    "A required model artifact is not available or could not be validated. "
    "Place the exported artifacts (anomaly_model.joblib, forecast_model.joblib, "
    "model_config.json) in the configured model directory and restart the API. "
    "See backend/README.md."
)


def _safe_file_hash(path: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return f"sha256-{digest.hexdigest()[:12]}"
    except OSError:
        return None


def _safe_full_sha256(path: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


@dataclass
class ModelEntry:
    """Validation state of a single model artifact."""

    name: str
    status: str
    version: Optional[str] = None
    dataset: Optional[str] = None
    feature_names: Optional[List[str]] = None
    model_class: Optional[str] = None
    error_code: Optional[str] = None
    error_detail: Optional[str] = None  # safe, human-readable; no paths
    model: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.status == STATUS_LOADED and self.model is not None

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "status": self.status,
            "version": self.version,
            "dataset": self.dataset,
            "model_class": self.model_class,
            "feature_names": self.feature_names,
        }
        if self.error_code:
            payload["error_code"] = self.error_code
        if self.error_detail:
            payload["error_detail"] = self.error_detail
        payload.update(self.metadata)
        return payload


class ModelRegistry:
    """Loads and holds model artifacts for the application lifetime."""

    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = Path(artifacts_dir)
        self.config: Dict[str, Any] = {}
        self.config_status: str = STATUS_MISSING
        self.metrics: Dict[str, Any] = {}
        self.models: Dict[str, ModelEntry] = {
            name: ModelEntry(name=name, status=STATUS_MISSING) for name in MODEL_SPECS
        }
        self._loaded = False

    # ------------------------------------------------------------------ load
    def load(self) -> None:
        """(Re)load all artifacts.  Never raises; failures become statuses."""
        if self._loaded:
            return
        self.config = {}
        self.metrics = {}
        self.models = {
            name: ModelEntry(name=name, status=STATUS_MISSING) for name in MODEL_SPECS
        }

        config_path = self.artifacts_dir / CONFIG_FILE
        if config_path.is_file():
            try:
                with config_path.open("r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    self.config = loaded
                    self.config_status = STATUS_LOADED
                else:
                    self.config_status = STATUS_INVALID
                    logger.error(
                        "model_config_invalid",
                        extra={"event": "model_config_invalid", "path": str(config_path)},
                    )
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                self.config_status = STATUS_INVALID
                logger.error(
                    "model_config_unreadable",
                    extra={
                        "event": "model_config_unreadable",
                        "path": str(config_path),
                        "error": str(exc),
                    },
                )
        else:
            logger.warning(
                "model_config_missing",
                extra={"event": "model_config_missing", "path": str(config_path)},
            )

        metrics_path = self.artifacts_dir / METRICS_FILE
        if metrics_path.is_file():
            try:
                with metrics_path.open("r", encoding="utf-8") as handle:
                    loaded_metrics = json.load(handle)
                if isinstance(loaded_metrics, dict):
                    self.metrics = loaded_metrics
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                logger.warning(
                    "forecast_metrics_unreadable",
                    extra={"event": "forecast_metrics_unreadable", "path": str(metrics_path)},
                )

        if self.config_status != STATUS_LOADED:
            # Without the exported config we cannot know the training-time
            # feature contract, so models are treated as unusable.
            for name in MODEL_SPECS:
                entry = ModelEntry(
                    name=name,
                    status=STATUS_CONFIG_MISSING,
                    error_code="model_config_missing",
                    error_detail=(
                        "model_config.json is missing or unreadable; the training-time "
                        "feature contract cannot be verified."
                    ),
                )
                self.models[name] = entry
            self._loaded = True
            return

        dataset = self.config.get("dataset")
        for name, spec in MODEL_SPECS.items():
            self.models[name] = self._load_one(name, spec, dataset)
        self._loaded = True

    def _load_one(self, name: str, spec: Dict[str, Any], dataset: Optional[str]) -> ModelEntry:
        path = self.artifacts_dir / spec["file"]

        if not path.is_file():
            logger.warning(
                "model_artifact_missing",
                extra={"event": "model_artifact_missing", "model": name, "path": str(path)},
            )
            return ModelEntry(
                name=name,
                status=STATUS_MISSING,
                dataset=dataset,
                error_code="model_artifact_missing",
                error_detail=f"Artifact '{spec['file']}' was not found in the model directory.",
            )

        # --- feature contract -------------------------------------------
        configured = self.config.get(spec["config_key"])
        if not isinstance(configured, list) or not configured:
            configured = spec["fallback_features"]
        unknown = [f for f in configured if f not in SUPPORTED_FEATURES]
        if unknown:
            logger.error(
                "model_feature_mismatch",
                extra={
                    "event": "model_feature_mismatch",
                    "model": name,
                    "unsupported_features": unknown,
                },
            )
            return ModelEntry(
                name=name,
                status=STATUS_FEATURE_MISMATCH,
                dataset=dataset,
                feature_names=[str(f) for f in configured],
                error_code="incompatible_model_features",
                error_detail=(
                    "The exported model config requires features this API does not "
                    f"support: {', '.join(str(u) for u in unknown)}."
                ),
            )

        version = _safe_file_hash(path)
        try:
            model = joblib.load(path)
        except Exception as exc:  # joblib may raise many unpickling errors
            logger.error(
                "model_artifact_unloadable",
                extra={
                    "event": "model_artifact_unloadable",
                    "model": name,
                    "path": str(path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            return ModelEntry(
                name=name,
                status=STATUS_INVALID,
                version=version,
                dataset=dataset,
                feature_names=[str(f) for f in configured],
                error_code="model_artifact_invalid",
                error_detail=(
                    "The model artifact could not be loaded. It may be corrupt or "
                    "incompatible with the installed scikit-learn version "
                    "(re-export it with the current environment)."
                ),
            )

        actual_class = type(model).__name__
        if actual_class != spec["expected_class"]:
            logger.error(
                "model_class_mismatch",
                extra={
                    "event": "model_class_mismatch",
                    "model": name,
                    "expected": spec["expected_class"],
                    "actual": actual_class,
                },
            )
            return ModelEntry(
                name=name,
                status=STATUS_INVALID,
                version=version,
                dataset=dataset,
                model_class=actual_class,
                feature_names=[str(f) for f in configured],
                error_code="model_artifact_invalid",
                error_detail=(
                    f"Expected a {spec['expected_class']} artifact but found "
                    f"{actual_class}."
                ),
            )

        n_features = getattr(model, "n_features_in_", None)
        if isinstance(n_features, int) and n_features != len(configured):
            logger.error(
                "model_feature_count_mismatch",
                extra={
                    "event": "model_feature_count_mismatch",
                    "model": name,
                    "expected": len(configured),
                    "actual": n_features,
                },
            )
            return ModelEntry(
                name=name,
                status=STATUS_FEATURE_MISMATCH,
                version=version,
                dataset=dataset,
                model_class=actual_class,
                feature_names=[str(f) for f in configured],
                error_code="incompatible_model_features",
                error_detail=(
                    "The model expects a different number of input features than "
                    "the exported config declares."
                ),
            )

        logger.info(
            "model_loaded",
            extra={
                "event": "model_loaded",
                "model": name,
                "version": version,
                "model_class": actual_class,
                "dataset": dataset,
            },
        )
        metadata: Dict[str, Any] = {}
        full_hash = _safe_full_sha256(path)
        if full_hash:
            metadata["sha256_full"] = full_hash
        # Training-environment provenance: prefer what the exported config
        # declares. Fall back to the known Colab training environment only
        # for genuine (non-synthetic) exports — synthetic demo/test fixtures
        # must never claim to be Colab-trained.
        is_synthetic = self.config.get("synthetic") is True or str(
            self.config.get("artifact_source", "")
        ).startswith("synthetic")
        config_library = self.config.get("training_library")
        if isinstance(config_library, str) and config_library:
            metadata["training_library"] = config_library
        elif not is_synthetic:
            metadata["training_library"] = "scikit-learn 1.6.1 (Google Colab)"
        for key in (
            "training_period_start",
            "training_period_end",
            "testing_period_start",
            "testing_period_end",
            "selected_meter",
            "data_frequency",
            "forecast_horizon_hours",
            "anomaly_contamination",
            "artifact_source",
            "synthetic",
        ):
            if key in self.config:
                metadata[key] = self.config[key]
        return ModelEntry(
            name=name,
            status=STATUS_LOADED,
            version=version,
            dataset=dataset if isinstance(dataset, str) else None,
            feature_names=[str(f) for f in configured],
            model_class=actual_class,
            model=model,
            metadata=metadata,
        )

    # ------------------------------------------------------------- accessors
    @property
    def loaded(self) -> bool:
        return self._loaded

    def get(self, name: str) -> ModelEntry:
        return self.models[name]

    def require(self, name: str) -> ModelEntry:
        entry = self.models[name]
        if not entry.available:
            logger.warning(
                "model_unavailable_request",
                extra={"event": "model_unavailable_request", "model": name, "status": entry.status},
            )
            details = [{"field": "model", "message": entry.error_detail or _UNAVAILABLE_MESSAGE, "type": entry.error_code or "model_unavailable"}]
            raise ModelUnavailableError(
                message=_UNAVAILABLE_MESSAGE,
                code=entry.error_code or "model_unavailable",
                details=details,
            )
        return entry

    def anomaly_model_entry(self) -> ModelEntry:
        return self.require("anomaly")

    def forecast_model_entry(self) -> ModelEntry:
        return self.require("forecast")

    # ------------------------------------------------------ test/demo injection
    def set_model(
        self,
        name: str,
        model: Any,
        feature_names: List[str],
        version: str,
        dataset: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Inject a model directly (dependency injection for tests/fixtures).

        Callers must label synthetic fixtures honestly — this never writes
        serialized artifacts and is never used to substitute production
        predictions silently.
        """
        if name not in MODEL_SPECS:
            raise KeyError(name)
        self.models[name] = ModelEntry(
            name=name,
            status=STATUS_LOADED,
            version=version,
            dataset=dataset,
            feature_names=list(feature_names),
            model_class=type(model).__name__,
            model=model,
            metadata=dict(metadata or {}),
        )
        self._loaded = True

    def set_config(self, config: Dict[str, Any]) -> None:
        """Inject a config dict (test/demo dependency injection)."""
        self.config = dict(config)
        self.config_status = STATUS_LOADED

    # --------------------------------------------------------------- reporting
    @property
    def all_models_loaded(self) -> bool:
        return all(entry.available for entry in self.models.values())

    def readiness_report(self) -> Dict[str, Any]:
        models = {name: entry.as_dict() for name, entry in self.models.items()}
        ready = self.config_status == STATUS_LOADED and self.all_models_loaded
        notes: List[str] = []
        if self.config.get("synthetic") is True or str(
            self.config.get("artifact_source", "")
        ).startswith("synthetic"):
            notes.append(
                "Loaded artifacts are flagged as SYNTHETIC DEMO data — they were "
                "not trained on BDG2 and must not be presented as production results."
            )
        if not ready:
            notes.append(
                "Degraded readiness: one or more model artifacts are missing or "
                "invalid; forecast/anomaly endpoints return 503 until resolved."
            )
        return {
            "ready": ready,
            "model_config_status": self.config_status,
            "models": models,
            "notes": notes,
        }
