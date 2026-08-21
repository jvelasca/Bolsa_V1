from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # F2·6: credentials de BD no van hardcodeadas en el código. Si no llega
    # `DATABASE_URL`, se compone desde DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME
    # (mismos defaults de docker-compose.yml). En local el .env provee DATABASE_URL.
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=5432, validation_alias="DB_PORT")
    db_user: str = Field(default="bolsa", validation_alias="DB_USER")
    db_password: str = Field(default="", validation_alias="DB_PASSWORD")
    db_name: str = Field(default="bolsa_v1", validation_alias="DB_NAME")
    redis_url: str = "redis://localhost:6379/0"
    cors_origin: str = "http://localhost:5173"
    # F-SEG-3: hosts/proxies de confianza que pueden añadir `X-Forwarded-For`.
    # Coma-separados; si se deja vacío (default) el rate-limit ignora el header y usa
    # `client.host` (comportamiento dev/local sin proxy, evita spoofing).
    trusted_proxies: str = Field(default="", validation_alias="TRUSTED_PROXIES")
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, validation_alias="API_PYTHON_PORT")
    xtb_bridge_url: str | None = Field(default=None, validation_alias="XTB_BRIDGE_URL")
    app_password: str | None = Field(default=None, validation_alias="APP_PASSWORD")
    # R12-AUTH fase 1: id de propietario single-tenant (no JWT, no tabla users).
    # Se estampa en altas nuevas de cuenta y se usa como request.state.principal.
    app_owner_id: str = Field(default="app", validation_alias="APP_OWNER_ID")
    # F2·6: sin secreto hardcodeado. Vacío por defecto; si se activa APP_PASSWORD
    # se exige un APP_AUTH_SECRET real (ver validator más abajo).
    app_auth_secret: str = Field(default="", validation_alias="APP_AUTH_SECRET")
    # TTL de sesión de la cookie HttpOnly stateless (ver bolsa_api.auth.session).
    # 1 día por defecto; 0 o negativo desactiva los Set-Cookie de sesión.
    app_auth_ttl_seconds: int = Field(default=86400, validation_alias="APP_AUTH_TTL_SECONDS")
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
    # R-10 F4b — job periódico de custodia (mueve ApplyCustodyFees del GET al
    # scheduler). On-by-default: reemplaza el side-effect que hoy hace el GET.
    custody_job_enabled: bool = Field(
        default=True, validation_alias="CUSTODY_JOB_ENABLED"
    )
    custody_job_interval_seconds: float = Field(
        default=300.0, validation_alias="CUSTODY_JOB_INTERVAL_SECONDS"
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
    # OR-RE — kill switch global aperturas automáticas (Risk Engine).
    risk_kill_switch: bool = Field(
        default=False, validation_alias="RISK_KILL_SWITCH"
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
    # R3 — digest operativo diario HTML tras eod-batch (off-by-default).
    daily_ops_digest_email_enabled: bool = Field(
        default=False, validation_alias="DAILY_OPS_DIGEST_EMAIL_ENABLED"
    )
    # R4 — adjuntar PDF al digest (off-by-default; requiere digest email).
    daily_ops_digest_pdf_enabled: bool = Field(
        default=False, validation_alias="DAILY_OPS_DIGEST_PDF_ENABLED"
    )

    @model_validator(mode="after")
    def compose_database_url(self) -> "Settings":
        # Si no se indicó DATABASE_URL en el entorno, se compone desde DB_*.
        # DB_PASSWORD vacío => sin credenciales si PostgreSQL local no las exige
        # (default de docker-compose usa user=bolsa y password bolsa_dev vía env).
        if not self.database_url:
            cred = f"{self.db_user}:{self.db_password}@" if self.db_password else f"{self.db_user}@"
            self.database_url = (
                f"postgresql+psycopg://{cred}{self.db_host}:{self.db_port}/{self.db_name}"
            )
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        # F2·6: si se activa contraseña de acceso (APP_PASSWORD), el secreto de
        # firma NO puede ser vacío ni el valor de desarrollo aún conocido.
        if self.app_password:
            secret = (self.app_auth_secret or "").strip()
            if not secret:
                raise ValueError(
                    "APP_PASSWORD activa requiere APP_AUTH_SECRET (secreto de firma) no vacío"
                )
            if secret == "bolsa-dev-secret":
                raise ValueError(
                    "APP_AUTH_SECRET no puedes ser 'bolsa-dev-secret' con APP_PASSWORD: usa un secreto aleatorio"
                )
        # F-SEG-1: fail-closed production. Fuera de dev/test/local/staging la app es
        # producción: NO debe arrancar con autenticación desactivada ni con secretos
        # de desarrollo conocidos. Esto convierte el antiguo aviso "degraded" de
        # /health en un bloqueo real de arranque.
        if self.environment.strip().lower() in {"prod", "production"}:
            if not self.app_password:
                raise ValueError(
                    "ENVIRONMENT=production exige APP_PASSWORD (autenticación no puede desactivarse en producción)"
                )
            secret = (self.app_auth_secret or "").strip()
            if not secret:
                raise ValueError(
                    "ENVIRONMENT=production exige APP_AUTH_SECRET (secreto de firma) no vacío"
                )
            if secret == "bolsa-dev-secret":
                raise ValueError(
                    "APP_AUTH_SECRET no puedes ser 'bolsa-dev-secret' en producción: usa un secreto aleatorio"
                )
        return self

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str | None:
        # Prisma suele añadir ?schema=public — psycopg no lo acepta en la URL
        if value and "?" in value:
            value = value.split("?", 1)[0]
        return value

    def owner_principal(self) -> str:
        """Id single-tenant estampado en cuentas nuevas y adjunto al request.

        Vacío o solo espacios cae a ``app`` para que auth-off y tests
        dejen el mismo ``user_id`` que el modo con ``APP_PASSWORD``.
        """
        return (self.app_owner_id or "").strip() or "app"

    def __repr__(self) -> str:
        # F-SEG-2: un `repr(Settings)` accidental en un log/traceback no debe exponer
        # el secreto de firma, la contraseña de acceso ni las credenciales de la BD.
        fields = {f for f in self.__class__.model_fields}
        redacted = {
            "app_password": "********",
            "app_auth_secret": "********",
            "db_password": "********",
        }
        pieces = []
        for field in sorted(fields):
            if field in redacted:
                pieces.append(f"{field}={redacted[field]}")
                continue
            value = getattr(self, field, None)
            if field == "database_url" and isinstance(value, str):
                value = _redact_dsn_credentials(value)
            pieces.append(f"{field}={value!r}")
        return f"Settings({', '.join(pieces)})"


def _redact_dsn_credentials(url: str) -> str:
    """Oculta `user:pass@` de un DSN (p. ej. `bolsa:s3cr3t@`) dejando host/puerto/DB."""
    for scheme in ("postgresql+psycopg://", "postgresql://"):
        if url.startswith(scheme):
            rest = url[len(scheme) :]
            if "@" in rest:
                auth, host = rest.split("@", 1)
                user = auth.split(":", 1)[0]
                return f"{scheme}{user}:***@{host}"
            return url
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
