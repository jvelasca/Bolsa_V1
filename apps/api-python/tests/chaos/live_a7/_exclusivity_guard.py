"""Guarda de EXCLUSIVIDAD de la BD de la batería ``chaos/live_a7`` (precondición operativa).

El escenario C3-A siembra una fila ``live_orders`` en ``UNKNOWN`` y exige que SOLO los
procesos del propio test la reclamen. ``PostgresLiveOrderStore.claim_unknown_batch`` es
una barrida GLOBAL de ``status='UNKNOWN'`` **sin filtro de cuenta** (correcto en
producción: un worker de recovery atiende cualquier cuenta). Por eso, si la batería corre
contra la BD del stack de desarrollo (``bolsa_v1``) y hay un ``scheduler_worker`` vivo
(``pnpm dev`` lo arranca; el recovery nace ON con tick de 5 s), ese worker consume la fila
entre el SIGKILL del primer subproceso y el reap del segundo: el sentinel escribe
``drained=0 resolved=0`` y el fallo PARECE un defecto del código de recovery cuando en
realidad es la precondición incumplida.

Esta guarda convierte esa condición en un veredicto EXPLÍCITO:

* **Identidad de la BD** (determinista, sin red): el nombre debe ser dedicado — sufijo
  ``_a7`` o el declarado en ``LIVE_A7_DB_NAME``. ``LIVE_A7_ALLOW_SHARED_DB=1`` lo relaja
  (y entonces el resultado deja de certificar exclusividad).
* **Claim ajeno fresco**: una fila ``UNKNOWN`` con lease reciente cuyo dueño NO es de esta
  suite (``live-a7-*``) demuestra que otro worker está drenando la MISMA BD.
* **Sonda del stack dev** (información, no criterio): nombra los puertos vivos del stack
  (API ``:8000``, Vite ``:5173``, mock XTB ``:3002``) dentro del mensaje. No se usa como
  criterio duro: la API de ``:8000`` puede apuntar a otra BD y el puerto abierto no prueba
  por sí solo contención, así que produciría skips falsos.

Semántica: ``pytest.skip`` accionable; con ``LIVE_A7_PG_REQUIRED=1`` (job ``a7-gate`` del
CI) se convierte en fallo duro, igual que el resto de gates de la batería.
"""

from __future__ import annotations

import os
import socket
from datetime import UTC, datetime, timedelta
from typing import Any

#: Sufijo de una BD dedicada a la batería (``bolsa_v1_a7`` en el job ``a7-gate``).
DEDICATED_SUFFIX = "_a7"
#: Prefijo de los workers/procesos que ESTA batería crea (``live-a7-<tag>-<hex>``).
TEST_WORKER_PREFIX = "live-a7-"
#: Gate del CI: con ``1`` la precondición rota es FALLO, no skip.
GATE_ENV = "LIVE_A7_PG_REQUIRED"
#: Override explícito para aceptar una BD compartida (relaja solo la identidad de BD).
ALLOW_SHARED_ENV = "LIVE_A7_ALLOW_SHARED_DB"
#: Nombre alternativo de BD dedicada cuando no se usa el sufijo.
DB_NAME_ENV = "LIVE_A7_DB_NAME"
#: Ventana de lease del recovery (misma que ``live_order_recovery_worker``).
CLAIM_STALE_ENV = "LIVE_RECOVERY_CLAIM_STALE_SECONDS"
DEFAULT_CLAIM_STALE_SECONDS = 120
#: Puertos canónicos del stack dev (``scripts/run-dev.mjs``): solo informativos.
DEV_STACK_PORTS: tuple[tuple[str, int], ...] = (
    ("API", 8000),
    ("Vite", 5173),
    ("mock XTB", 3002),
)


# ---------------------------------------------------------------------------
# Identidad de la BD (criterio determinista, sin tocar la red)
# ---------------------------------------------------------------------------


def database_url() -> str | None:
    """``DATABASE_URL`` efectiva de settings (misma fuente que el fixture ``factory``)."""
    from bolsa_infrastructure.config import get_settings

    get_settings.cache_clear()
    return get_settings().database_url


def database_name(url: str | None) -> str | None:
    """Nombre de la BD del DSN (``postgresql[+psycopg]://…/<nombre>?…``), o ``None``."""
    if not url or not str(url).strip():
        return None
    from sqlalchemy.engine import make_url

    try:
        return make_url(url).database or None
    except Exception:  # noqa: BLE001 — DSN ilegible: el veredicto lo da el nombre ausente
        return None


def is_dedicated_database_name(name: str | None) -> bool:
    """¿El nombre identifica una BD dedicada a la batería?

    Regla: ``LIVE_A7_DB_NAME`` (si se declara) manda; si no, el sufijo ``_a7``. Un nombre
    ausente/ilegible NUNCA se considera dedicado (fail-closed).
    """
    clave = (name or "").strip()
    if not clave:
        return False
    declared = (os.environ.get(DB_NAME_ENV) or "").strip()
    if declared:
        return clave == declared
    return clave.endswith(DEDICATED_SUFFIX)


def shared_db_reason(url: str | None) -> str | None:
    """Motivo por el que la BD de ``url`` no es exclusiva, o ``None`` si sí lo es."""
    if not url or not str(url).strip():
        return "DATABASE_URL no está configurada (la batería exige PostgreSQL real dedicado)"
    if (os.environ.get(ALLOW_SHARED_ENV) or "").strip() == "1":
        return None
    name = database_name(url)
    if is_dedicated_database_name(name):
        return None
    shown = f"'{name}'" if name else "desconocida (DSN ilegible)"
    return (
        f"DATABASE_URL apunta a la BD {shown}, que no está dedicada a live_a7 "
        f"(se espera un nombre con sufijo '{DEDICATED_SUFFIX}', p. ej. 'bolsa_v1_a7'); "
        + describe_dev_stack()
    )


# ---------------------------------------------------------------------------
# Sonda del stack dev (información para el mensaje, nunca criterio duro)
# ---------------------------------------------------------------------------


def probe_ports(
    ports: tuple[tuple[str, int], ...],
    *,
    host: str = "127.0.0.1",
    timeout: float = 0.2,
) -> list[str]:
    """Etiquetas de los puertos que aceptan conexión TCP ahora mismo (``"API :8000"``)."""
    alive: list[str] = []
    for label, port in ports:
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                alive.append(f"{label} :{port}")
        except OSError:
            continue
    return alive


def listening_dev_stack() -> list[str]:
    """Componentes del stack dev que están escuchando en loopback."""
    return probe_ports(DEV_STACK_PORTS)


def describe_dev_stack() -> str:
    """Frase con el estado del stack dev, para adjuntar al diagnóstico."""
    alive = listening_dev_stack()
    if not alive:
        return "no hay stack dev escuchando en 127.0.0.1 (:8000/:5173/:3002)"
    return "stack dev vivo en 127.0.0.1 (" + ", ".join(alive) + ")"


# ---------------------------------------------------------------------------
# Claims ajenos sobre la MISMA BD (criterio con evidencia durable)
# ---------------------------------------------------------------------------


def is_test_worker(worker_id: str | None) -> bool:
    """¿El lease pertenece a un proceso de esta batería (``live-a7-*``)?"""
    return (worker_id or "").strip().startswith(TEST_WORKER_PREFIX)


def is_foreign_worker(worker_id: str | None) -> bool:
    """¿El lease es de un worker ajeno? Un dueño vacío NO es evidencia (no se inventa)."""
    clave = (worker_id or "").strip()
    return bool(clave) and not is_test_worker(clave)


def claim_stale_seconds() -> int:
    """Ventana de lease efectiva del recovery (misma semántica que el worker)."""
    raw = (os.environ.get(CLAIM_STALE_ENV) or "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_CLAIM_STALE_SECONDS
    return value if value > 0 else DEFAULT_CLAIM_STALE_SECONDS


async def foreign_claim_reason(
    session_factory: Any,
    *,
    stale_after_seconds: int | None = None,
) -> str | None:
    """Motivo si otra sesión/worker tiene un claim FRESCO en la BD, o ``None``.

    Evidencia: filas ``UNKNOWN`` con ``recovery_claimed_at`` dentro de la ventana viva y
    ``recovery_worker_id`` que no es de esta suite. Cubre el caso de un ``scheduler_worker``
    apuntando a la BD dedicada (el que la identidad de nombre no puede ver).
    """
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import LiveOrderRow

    stale = claim_stale_seconds() if stale_after_seconds is None else int(stale_after_seconds)
    stmt = (
        select(
            LiveOrderRow.order_id,
            LiveOrderRow.recovery_worker_id,
            LiveOrderRow.recovery_claimed_at,
        )
        .where(LiveOrderRow.status == "UNKNOWN")
        .where(LiveOrderRow.recovery_claimed_at.is_not(None))
        .where(
            LiveOrderRow.recovery_claimed_at >= datetime.now(UTC) - timedelta(seconds=max(1, stale))
        )
        .order_by(LiveOrderRow.recovery_claimed_at.desc())
        .limit(20)
    )
    try:
        async with session_factory() as session:
            rows = (await session.execute(stmt)).all()
    except Exception:  # noqa: BLE001 — no poder verificar no se convierte en skip inventado
        return None
    foreign = [(order_id, worker) for order_id, worker, _ in rows if is_foreign_worker(worker)]
    if not foreign:
        return None
    sample_order, sample_worker = foreign[0]
    return (
        f"hay {len(foreign)} orden(es) UNKNOWN con claim FRESCO de un worker ajeno "
        f"(p. ej. {sample_order} reclamada por '{sample_worker}'): otro recovery "
        f"(scheduler_worker) está drenando ESTA BD; " + describe_dev_stack()
    )


# ---------------------------------------------------------------------------
# Veredicto (skip accionable en local / fallo duro en CI)
# ---------------------------------------------------------------------------


def describe(reason: str) -> str:
    """Mensaje accionable único para la precondición rota."""
    return (
        "BD no exclusiva para chaos/live_a7: "
        f"{reason}. "
        "El worker de recovery (scheduler_worker; tick 5 s, nace ON) reclama las filas "
        "UNKNOWN de la tabla ENTERA (claim_unknown_batch no filtra por cuenta), así que el "
        "escenario lee drained=0 resolved=0 sin que haya un defecto de código. "
        "Cómo arreglarlo: apunta DATABASE_URL a una BD dedicada *_a7 (el job a7-gate usa "
        "'bolsa_v1_a7', drop+create) y para el stack dev (pnpm dev: API :8000, Vite :5173, "
        "mock XTB :3002); o autoriza explícitamente con LIVE_A7_ALLOW_SHARED_DB=1 (entonces "
        "el resultado NO certifica exclusividad). "
        "Este run NO certifica C3: con LIVE_A7_PG_REQUIRED=1 (job a7-gate del CI) el mismo "
        "run falla en vez de saltar, así que un verde con skips no es el veredicto del sello."
    )


def require_exclusive(reason: str | None) -> None:
    """Materializa el veredicto: nada que hacer, skip accionable o fallo duro en CI."""
    if not reason:
        return
    import pytest

    message = describe(reason)
    if (os.environ.get(GATE_ENV) or "").strip() == "1":
        raise AssertionError(f"live_a7 C3 required but {message}")
    pytest.skip(message)
