"""Environment-based application settings.

All runtime configuration comes from environment variables (optionally a
``.env`` file).  No secrets are committed to the repository; see
``backend/.env.example`` for placeholders only.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[0]=core, [1]=app, [2]=backend
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACTS_DIR = BACKEND_ROOT / "artifacts"

CARBON_FACTOR_UNITS_SUPPORTED = "kg_CO2_per_kwh"


class Settings(BaseSettings):
    """Runtime settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- application -----------------------------------------------------
    app_name: str = "Fluxora API"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    # --- logging ---------------------------------------------------------
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "text"

    # --- CORS ------------------------------------------------------------
    # Comma-separated explicit origins. Unrestricted CORS is never the default.
    cors_allow_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- model artifacts -------------------------------------------------
    model_artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR

    # --- request limits --------------------------------------------------
    max_readings_per_request: int = 50_000
    max_request_bytes: int = 10 * 1024 * 1024  # 10 MiB

    # --- carbon emission factor -----------------------------------------
    # Deliberately unset by default: the backend refuses to invent a grid
    # emission factor. Configure with a documented, sourced factor.
    carbon_emission_factor: Optional[float] = None  # kg CO2 per kWh
    carbon_factor_source: Optional[str] = None
    carbon_factor_region: Optional[str] = None
    carbon_factor_year: Optional[int] = None
    carbon_factor_units: Optional[str] = CARBON_FACTOR_UNITS_SUPPORTED
    carbon_factor_effective_date: Optional[str] = None

    # --- validators ------------------------------------------------------
    @field_validator(
        "carbon_emission_factor",
        "carbon_factor_year",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        # An empty env var (``CARBON_EMISSION_FACTOR=``) means "unset".
        if value == "":
            return None
        return value

    @field_validator("log_format", mode="before")
    @classmethod
    def _default_log_format(cls, value: object) -> object:
        return value or "json"

    # --- derived ---------------------------------------------------------
    @property
    def cors_origins_list(self) -> List[str]:
        return [
            origin.strip()
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]

    @property
    def carbon_factor_configured(self) -> bool:
        return self.carbon_emission_factor is not None


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton for module-level use."""
    return Settings()
