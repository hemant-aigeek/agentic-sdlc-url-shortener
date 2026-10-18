"""Runtime configuration.

Everything that varies between a developer machine, the test suite and a demo
run is a field here, read from environment variables prefixed ``AGENTIC_``.
Demo-fault flags exist so reliability behaviour can be *executed* in scenario
runs rather than merely described; they default off.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTIC_", env_file=".env", extra="ignore")

    # --- application plane -------------------------------------------------
    database_url: str = "sqlite+pysqlite:///data/agentic.db"
    data_dir: Path = Path("data")
    api_key: str = Field(default="dev-key", description="Static key for mutating endpoints")
    base_url: str = "http://127.0.0.1:8000"
    max_url_length: int = 2048
    short_code_length: int = 7
    short_code_max_attempts: int = 5
    rate_limit_capacity: int = 20
    rate_limit_refill_per_second: float = 5.0
    blocked_hostnames: tuple[str, ...] = ("localhost", "metadata.google.internal")
    blocked_hostname_suffixes: tuple[str, ...] = (".localhost", ".internal", ".local")

    # --- control plane -----------------------------------------------------
    retry_max_attempts: int = 3
    retry_base_delay_s: float = 0.1
    retry_multiplier: float = 2.0
    retry_max_delay_s: float = 2.0
    stage_timeout_s: float = 5.0
    gate_timeout_s: float | None = None  # None = wait indefinitely (interactive use)
    max_parallel_stages: int = 4
    audit_retention_days: int | None = None  # None = retain for the life of the store

    # --- demonstration faults (off by default; used by scenario runs and tests) ---
    demo_fault_verify_transient_failures: int = 0
    demo_fault_security_permanent_failure: bool = False
    demo_fault_policy_fail: str | None = None  # policy id to force FAIL

    # --- telemetry ---------------------------------------------------------
    log_level: str = "INFO"
    log_json: bool = True

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"


def load_settings() -> Settings:
    return Settings()
