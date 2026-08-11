"""API: health check (DB + Yahoo circuit + Redis best-effort + XTB + SMTP)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from bolsa_infrastructure.alerts.estudio_opinion_email import smtp_ready
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.session import check_database

router = APIRouter()


class DatabaseHealthDto(BaseModel):
    """Estado de conectividad PostgreSQL."""

    status: str
    message: str


class ComponentHealthDto(BaseModel):
    """Estado de un componente opcional (sin probe de red agresivo salvo Redis ping)."""

    status: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class HealthResponseDto(BaseModel):
    """Payload ``GET /api/health``."""

    status: str
    service: str = "bolsa-api-python"
    timestamp: str
    database: DatabaseHealthDto | None = None
    components: dict[str, ComponentHealthDto] = Field(default_factory=dict)
    stack: str = Field(default="python-fastapi")


def _yahoo_component() -> ComponentHealthDto:
    """Yahoo: sin probe live; expone circuit breaker + cuarentena del proceso."""
    details: dict[str, object] = {}
    try:
        from bolsa_market.ohlcv_quarantine import get_ohlcv_quarantine_stats
        from bolsa_market.yahoo_client import get_yahoo_finance_client

        circuit = get_yahoo_finance_client().circuit.snapshot()
        quarantine = get_ohlcv_quarantine_stats().snapshot()
        details = {"circuit": circuit, "ohlcv_quarantine": quarantine}
        state = str(circuit.get("state") or "closed")
        if state == "open":
            return ComponentHealthDto(
                status="degraded",
                message=f"Yahoo circuit OPEN (cooldown {circuit.get('cooldown_sec')}s)",
                details=details,
            )
        if state == "half_open":
            return ComponentHealthDto(
                status="degraded",
                message="Yahoo circuit HALF_OPEN (probing recovery)",
                details=details,
            )
        return ComponentHealthDto(
            status="configured",
            message="Yahoo Finance client available (no live probe)",
            details=details,
        )
    except Exception:  # pragma: no cover - defensive
        # P2.5: no filtrar la excepción interna (detalle al público redactado).
        return ComponentHealthDto(
            status="error",
            message="Yahoo health introspection failed",
        )


def _xtb_component() -> ComponentHealthDto:
    settings = get_settings()
    if settings.xtb_bridge_url:
        # P2.5: exponer la URL real del bridge filtra infraestructura interna;
        # solo se informa del estado configurado, sin el valor.
        return ComponentHealthDto(
            status="configured",
            message="XTB_BRIDGE_URL set",
        )
    return ComponentHealthDto(
        status="disabled",
        message="XTB_BRIDGE_URL not set",
    )


async def _redis_component() -> ComponentHealthDto:
    """Ping Redis (ARQ). Si no hay Redis, degraded — no unhealthy de API."""
    settings = get_settings()
    url = (settings.redis_url or "").strip()
    if not url:
        return ComponentHealthDto(
            status="disabled",
            message="REDIS_URL not set",
        )
    try:
        from redis.asyncio import Redis

        client = Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
        try:
            pong = await client.ping()
        finally:
            await client.aclose()
        if pong:
            # P2.5: no exponer host/URL de Redis; solo el estado.
            return ComponentHealthDto(status="ok", message="Redis ping ok")
        return ComponentHealthDto(status="degraded", message="Redis ping returned falsy")
    except Exception:
        # P2.5: detalle de la excepción (host/port/credenciales) redactado del público.
        return ComponentHealthDto(status="degraded", message="Redis unreachable")


def _auth_component() -> ComponentHealthDto:
    """P2.5: estado auth sin exponer claves de config internas ni nombres de política."""
    settings = get_settings()
    pwd = (settings.app_password or "").strip()
    env = (settings.environment or "development").strip().lower()
    if pwd:
        return ComponentHealthDto(status="ok", message="auth secret configured")
    if env in {"development", "dev", "test", "local"}:
        return ComponentHealthDto(
            status="configured",
            message="auth secret empty (OK local)",
        )
    return ComponentHealthDto(
        status="degraded",
        message="auth secret empty outside development — set for shared demos",
    )


async def _worker_heartbeat_component() -> ComponentHealthDto:
    """OR-Obs: último heartbeat Arq en Redis (TTL ~180s)."""
    from bolsa_infrastructure.queue.worker_heartbeat import (
        WORKER_HEARTBEAT_TTL_SEC,
        read_arq_heartbeat,
    )

    settings = get_settings()
    if not (settings.redis_url or "").strip():
        return ComponentHealthDto(
            status="disabled",
            message="REDIS_URL not set — worker heartbeat unavailable",
        )
    ts = await read_arq_heartbeat()
    if not ts:
        return ComponentHealthDto(
            status="degraded",
            message="No Arq worker heartbeat (worker down or never started)",
            details={"ttlSec": WORKER_HEARTBEAT_TTL_SEC},
        )
    return ComponentHealthDto(
        status="ok",
        message=f"Arq worker heartbeat at {ts}",
        details={"at": ts, "ttlSec": WORKER_HEARTBEAT_TTL_SEC},
    )


async def _risk_component() -> ComponentHealthDto:
    """A3: estado kill switch + PAPER_D_EXECUTE (siempre default off en prod)."""
    from bolsa_application.paper_d_propose import paper_d_execute_allowed
    from bolsa_application.risk_runtime import kill_switch_status

    st = await kill_switch_status()
    paper_on = paper_d_execute_allowed()
    details = {**st, "paperDExecuteEnv": paper_on}
    if st.get("effective"):
        return ComponentHealthDto(
            status="degraded",
            message="Kill switch ACTIVE — aperturas automáticas bloqueadas",
            details=details,
        )
    return ComponentHealthDto(
        status="ok",
        message=(
            "Kill switch off"
            + ("; PAPER_D_EXECUTE on (opt-in)" if paper_on else "; PAPER_D_EXECUTE off")
        ),
        details=details,
    )


def _smtp_component() -> ComponentHealthDto:
    """SMTP para Alarmas / digest R3 — sin probe de red; solo config mínima."""
    settings = get_settings()
    ready = smtp_ready(settings)
    missing: list[str] = []
    if not (settings.smtp_host or "").strip():
        missing.append("SMTP_HOST")
    if not (settings.smtp_from or "").strip():
        missing.append("SMTP_FROM")
    return ComponentHealthDto(
        status="configured" if ready else "not-setup",
        message=(
            "SMTP listo para Alarmas / digest diario"
            if ready
            else f"SMTP incompleto — define en .env: {', '.join(missing) or 'SMTP_HOST / SMTP_FROM'}"
        ),
    )


@router.get("/health", response_model=HealthResponseDto)
async def health_check(request: Request) -> HealthResponseDto:
    engine = request.app.state.engine
    db_ok, db_message = await check_database(engine)
    components = {
        "database": ComponentHealthDto(
            status="ok" if db_ok else "error",
            message=db_message,
        ),
        "yahoo": _yahoo_component(),
        "xtb": _xtb_component(),
        "redis": await _redis_component(),
        "auth": _auth_component(),
        "worker_arq": await _worker_heartbeat_component(),
        "risk": await _risk_component(),
        "smtp": _smtp_component(),
    }
    # DB error → degraded; Redis/Yahoo/auth/worker degraded no tumba el health global a error.
    degraded = (not db_ok) or any(c.status == "error" for c in components.values())
    return HealthResponseDto(
        status="degraded" if degraded else "ok",
        timestamp=datetime.now(tz=UTC).isoformat(),
        database=DatabaseHealthDto(
            status="ok" if db_ok else "error",
            message=db_message,
        ),
        components=components,
    )
