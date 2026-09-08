"""API: health check (DB + Yahoo circuit + Redis best-effort + XTB + SMTP)."""

from datetime import UTC, datetime

from bolsa_infrastructure.alerts.estudio_opinion_email import smtp_ready
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.session import check_database, read_db_schema_current
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

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


class ProvenanceDto(BaseModel):
    """Bloque de provenance: identidad inequívoca de la versión en ejecución.

    Ver ``bolsa_api.provenance``. Ningún campo es obligatorio: si una fuente no
    está disponible (p.ej. sin árbol git o sin env de release) se reporta ``null``
    en lugar de inventar un valor que pueda estar desalineado con el tip real de
    ``main`` (hallazgo de provenance del auditor externo V2.14).
    """

    product: str | None = None
    package: str | None = None
    git_sha: str | None = None
    schema_revision: str | None = None
    api_contract: str | None = None


class HealthResponseDto(BaseModel):
    """Payload ``GET /api/health``."""

    status: str
    service: str = "bolsa-api-python"
    timestamp: str
    database: DatabaseHealthDto | None = None
    components: dict[str, ComponentHealthDto] = Field(default_factory=dict)
    stack: str = Field(default="python-fastapi")
    provenance: ProvenanceDto = Field(default_factory=ProvenanceDto)


class LiveResponseDto(BaseModel):
    """Payload ``GET /api/health/live`` — liveness.

    Sólo confirma que el proceso de la API responde (sin tocar la BD). Un
    orquestador usa este endpoint para decidir si reiniciar el contenedor, por
    lo que NO debe depender del estado de componentes externos.
    """

    status: str = "live"
    service: str = "bolsa-api-python"
    timestamp: str
    provenance: ProvenanceDto = Field(default_factory=ProvenanceDto)


class ReadyComponentStatusDto(BaseModel):
    """Estado de un componente requerido para ``/health/ready``."""

    status: str
    message: str


class ReadinessResponseDto(BaseModel):
    """Payload ``GET /api/health/ready`` — readiness.

    Para servir tráfico una app financiera exige (fail-closed):
      - PostgreSQL responde, y
      - el esquema migrado coincide con el head esperado por el código (Alembic).
    Redis/worker Arq se reportan como ``optional`` informativos (degradados no
    tumban el readiness global). ``required`` resume la conectividad de BD y
    ``schema_status`` detalla alineación de esquema con el head (V2.15 C2 / V2.15-03).
    """

    status: str
    service: str = "bolsa-api-python"
    timestamp: str
    required: ReadyComponentStatusDto | None = None
    schema_status: ReadyComponentStatusDto | None = None
    optional: dict[str, ReadyComponentStatusDto] = Field(default_factory=dict)
    provenance: ProvenanceDto = Field(default_factory=ProvenanceDto)


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


def _provenance_dto() -> ProvenanceDto:
    """Ensambla el bloque de provenance (identidad inequívoca V2.14/V2.15).

    Delegado a ``bolsa_api.provenance.build_provenance`` (single source, cacheado,
    sin dependencia de BD). Compartido por /health, /health/live y /health/ready.
    """
    from bolsa_api.provenance import build_provenance

    prov = build_provenance()
    return ProvenanceDto(
        product=prov.product,
        package=prov.package,
        git_sha=prov.git_sha,
        schema_revision=prov.schema_revision,
        api_contract=prov.api_contract,
    )


@router.get("/health", response_model=HealthResponseDto)
async def health_check(request: Request) -> HealthResponseDto:
    engine = request.app.state.engine
    db_ok, db_message = await check_database(engine)
    provenance = _provenance_dto()
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
        provenance=provenance,
        database=DatabaseHealthDto(
            status="ok" if db_ok else "error",
            message=db_message,
        ),
        components=components,
    )


def _ready_status(msg: str, status: str) -> ReadyComponentStatusDto:
    return ReadyComponentStatusDto(status=status, message=msg)


@router.get("/health/live", response_model=LiveResponseDto)
async def health_live() -> LiveResponseDto:
    """Liveness: el proceso responde sin tocar BD (para reinicio por orquestador)."""
    return LiveResponseDto(
        timestamp=datetime.now(tz=UTC).isoformat(),
        provenance=_provenance_dto(),
    )


@router.get("/health/ready", response_model=ReadinessResponseDto)
async def health_ready(request: Request, response: Response) -> ReadinessResponseDto:
    """Readiness: la app puede servir tráfico — fail-closed schema-aware.

    READY ⇔  PostgreSQL responde (DB), AND ``alembic_version == expected_head``
    (Alembic). La conectividad ya no basta: una build más nueva nunca debe quedar
    "ready" corriendo contra una BD sin la última migración (V2.15 C2 / V2.15-03).
    Redis y el heartbeat del worker Arq se reportan opcionales/informativos.
    Respuesta: 200 con `status: ready` si todo ok; 503 en caso contrario.
    """
    engine = request.app.state.engine
    db_ok, db_message = await check_database(engine)
    provenance = _provenance_dto()
    new = datetime.now(tz=UTC).isoformat()
    expected_head = provenance.schema_revision  # head Alembic esperado por el código

    if not db_ok:
        response.status_code = 503
        return ReadinessResponseDto(
            status="not_ready",
            timestamp=new,
            required=_ready_status(db_message, "error"),
            optional={},
            provenance=provenance,
        )

    # DB lista: comprobar alineación de esquema con el head esperado.
    current, schema_state = await read_db_schema_current(engine)
    if schema_state == "error":
        # BD caída justo después del check (carrera) → not_ready.
        response.status_code = 503
        return ReadinessResponseDto(
            status="not_ready",
            timestamp=new,
            required=_ready_status("PostgreSQL inaccesible tras el check", "error"),
            schema_status=_ready_status("esquema no verificable", "error"),
            optional={},
            provenance=provenance,
        )

    if expected_head and current == expected_head:
        schema_ok = True
        schema_c = _ready_status(f"esquema en head ({expected_head})", "ok")
    else:
        schema_ok = False
        if not expected_head:
            detail = "head esperado no resoluble localmente; esquema sin verificar"
        elif not current:
            detail = f"BD sin esquema migrado (se esperaba {expected_head})"
        else:
            detail = f"esquema {current} ≠ head esperado {expected_head}"
        schema_c = _ready_status(detail, "error")

    if not schema_ok:
        response.status_code = 503
        redis_c = await _redis_component()
        worker_c = await _worker_heartbeat_component()
        return ReadinessResponseDto(
            status="not_ready",
            timestamp=new,
            required=_ready_status("PostgreSQL listo", "ok"),
            schema_status=schema_c,
            optional={
                "redis": _ready_status(redis_c.message, redis_c.status),
                "worker_arq": _ready_status(worker_c.message, worker_c.status),
            },
            provenance=provenance,
        )

    # Todo ok (DB + esquema) → ready.
    redis_c = await _redis_component()
    worker_c = await _worker_heartbeat_component()
    response.status_code = 200
    return ReadinessResponseDto(
        status="ready",
        timestamp=new,
        required=_ready_status("PostgreSQL listo", "ok"),
        schema_status=_ready_status(f"esquema en head ({expected_head})", "ok"),
        optional={
            "redis": _ready_status(redis_c.message, redis_c.status),
            "worker_arq": _ready_status(worker_c.message, worker_c.status),
        },
        provenance=provenance,
    )
