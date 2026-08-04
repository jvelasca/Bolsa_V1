from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://bolsa:bolsa_dev@localhost:5432/bolsa_v1",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = "redis://localhost:6379/0"
    cors_origin: str = "http://localhost:5173"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, validation_alias="API_PYTHON_PORT")
    xtb_bridge_url: str | None = Field(default=None, validation_alias="XTB_BRIDGE_URL")
    app_password: str | None = Field(default=None, validation_alias="APP_PASSWORD")
    app_auth_secret: str = Field(default="bolsa-dev-secret", validation_alias="APP_AUTH_SECRET")
    environment: str = "development"
    scan_queue_backend: str = Field(default="postgres", validation_alias="SCAN_QUEUE_BACKEND")
    alert_webhook_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="ALERT_WEBHOOK_TIMEOUT_SECONDS",
    )
    signal_alert_eval_interval_seconds: float = Field(
        default=20.0,
        validation_alias="SIGNAL_ALERT_EVAL_INTERVAL_SECONDS",
    )
    scan_arq_max_jobs: int = Field(default=4, validation_alias="SCAN_ARQ_MAX_JOBS")
    scan_arq_job_timeout_seconds: int = Field(
        default=600,
        validation_alias="SCAN_ARQ_JOB_TIMEOUT_SECONDS",
    )
    smtp_host: str | None = Field(default=None, validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, validation_alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    smtp_from: str | None = Field(default=None, validation_alias="SMTP_FROM")
    tracker_schedule_enabled: bool = Field(default=True, validation_alias="TRACKER_SCHEDULE_ENABLED")
    tracker_schedule_interval_seconds: float = Field(
        default=60.0,
        validation_alias="TRACKER_SCHEDULE_INTERVAL_SECONDS",
    )
    # FA weekly pipeline (Screener → whitelist → Paper D). Off-by-default.
    fa_weekly_cron_enabled: bool = Field(default=False, validation_alias="FA_WEEKLY_CRON_ENABLED")
    fa_weekly_cron_interval_seconds: float = Field(
        default=900.0,
        validation_alias="FA_WEEKLY_CRON_INTERVAL_SECONDS",
    )
    fa_weekly_universe_list_id: str | None = Field(
        default=None, validation_alias="FA_WEEKLY_UNIVERSE_LIST_ID"
    )
    fa_weekly_whitelist_list_id: str | None = Field(
        default=None, validation_alias="FA_WEEKLY_WHITELIST_LIST_ID"
    )
    fa_weekly_execution_policy_id: str | None = Field(
        default=None, validation_alias="FA_WEEKLY_EXECUTION_POLICY_ID"
    )
    fa_weekly_execute: bool = Field(default=False, validation_alias="FA_WEEKLY_EXECUTE")
    fa_weekly_min_score_display_100: int = Field(
        default=55, validation_alias="FA_WEEKLY_MIN_SCORE_DISPLAY_100"
    )
    fa_weekly_max_candidates: int = Field(default=25, validation_alias="FA_WEEKLY_MAX_CANDIDATES")
    fa_weekly_max_results: int = Field(default=100, validation_alias="FA_WEEKLY_MAX_RESULTS")
    fa_weekly_weekday: int = Field(default=4, validation_alias="FA_WEEKLY_WEEKDAY")
    fa_weekly_hour: int = Field(default=18, validation_alias="FA_WEEKLY_HOUR")
    fa_weekly_max_trailing_pe: float = Field(
        default=25.0, validation_alias="FA_WEEKLY_MAX_TRAILING_PE"
    )
    fa_weekly_min_roe: float = Field(default=0.10, validation_alias="FA_WEEKLY_MIN_ROE")
    fa_weekly_min_piotroski: float = Field(default=6.0, validation_alias="FA_WEEKLY_MIN_PIOTROSKI")
    fa_weekly_use_sector_bands: bool = Field(
        default=True, validation_alias="FA_WEEKLY_USE_SECTOR_BANDS"
    )
    fa_weekly_gate_json: str | None = Field(default=None, validation_alias="FA_WEEKLY_GATE_JSON")
    feature_cache_backend: str = Field(default="memory", validation_alias="FEATURE_CACHE_BACKEND")
    feature_cache_ttl_seconds: float = Field(
        default=3600.0,
        validation_alias="FEATURE_CACHE_TTL_SECONDS",
    )
    feature_cache_max_entries: int = Field(
        default=512,
        validation_alias="FEATURE_CACHE_MAX_ENTRIES",
    )
    # Q3.4 — CORE-R cron servidor (re-encola desde reports BD). Off-by-default.
    core_r_cron_enabled: bool = Field(
        default=False, validation_alias="CORE_R_CRON_ENABLED"
    )
    core_r_cron_interval_seconds: float = Field(
        default=300.0, validation_alias="CORE_R_CRON_INTERVAL_SECONDS"
    )
    # Q3.5 — cost model v2 (volume-aware). Off by default; does not change Lab/paper tips.
    cost_model_v2_enabled: bool = Field(
        default=False, validation_alias="COST_MODEL_V2_ENABLED"
    )
    cost_model_v2_illiquid_extra_bps: int = Field(
        default=8, validation_alias="COST_MODEL_V2_ILLIQUID_EXTRA_BPS"
    )
    cost_model_v2_volume_ratio_illiquid: float = Field(
        default=0.35, validation_alias="COST_MODEL_V2_VOLUME_RATIO_ILLIQUID"
    )
    # D2 — batch EOD dictámenes Estudio. Off-by-default (ADR-022 / triage).
    estudio_eod_opinion_enabled: bool = Field(
        default=False, validation_alias="ESTUDIO_EOD_OPINION_ENABLED"
    )
    estudio_eod_opinion_interval_seconds: float = Field(
        default=3600.0, validation_alias="ESTUDIO_EOD_OPINION_INTERVAL_SECONDS"
    )
    # D2 — email Alarmas Estudio (off-by-default; requiere SMTP_* + EMAIL_TO).
    estudio_opinion_email_enabled: bool = Field(
        default=False, validation_alias="ESTUDIO_OPINION_EMAIL_ENABLED"
    )
    estudio_opinion_email_to: str | None = Field(
        default=None, validation_alias="ESTUDIO_OPINION_EMAIL_TO"
    )

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Prisma suele añadir ?schema=public — psycopg no lo acepta en la URL
        if "?" in value:
            value = value.split("?", 1)[0]
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
