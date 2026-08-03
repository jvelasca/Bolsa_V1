"""API: health check (DB + Yahoo circuit + Redis best-effort + XTB)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

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
    except Exception as exc:  # pragma: no cover - defensive
        return ComponentHealthDto(
            status="error",
            message=f"Yahoo health introspection failed: {exc}",
        )


def _xtb_component() -> ComponentHealthDto:
    settings = get_settings()
    if settings.xtb_bridge_url:
        return ComponentHealthDto(
            status="configured",
            message=f"XTB_BRIDGE_URL set ({settings.xtb_bridge_url})",
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
            return ComponentHealthDto(
                status="ok",
                message="Redis ping ok",
                details={"url_host": url.split("@")[-1] if "@" in url else url},
            )
        return ComponentHealthDto(status="degraded", message="Redis ping returned falsy")
    except Exception as exc:
        return ComponentHealthDto(
            status="degraded",
            message=f"Redis unreachable: {exc}",
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
    }
    # DB error → degraded; Redis/Yahoo degraded no tumba el health global a error.
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
