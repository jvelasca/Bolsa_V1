"""C3 🔴 — Crash-injection real sobre el worker de recovery/scheduler (Iter-1 A7).

Batería V2.18 que empieza a cerrar el gap principal de la Iter-0 de A7:

* PG REAL aislado (BD dedicada ``bolsa_v1_a7`` en el job CI ``a7-gate``). Si no hay
  PostgreSQL o el Alembic no está a la head congelada ``023`` → ``pytest.skip`` salvo
  ``LIVE_A7_PG_REQUIRED=1`` (fail duro en CI, patrón `test_live_order_recovery_concurrency_pg`).
* Crash de **proceso real** (subproceso Python) sobre ``resolve_one_unknown`` +
  ``PostgresLiveOrderStore`` en el punto crítico (claim FOR UPDATE en vivo, sin commit).
  El harness de proceso vive en `_crash_recovery_probe.py` (solo unido aquí por ruta de
  fichero, no por import) para poder usarlo tras SIGKILL.

Invariantes (modo fsm_only, decisión V2.18 — el recovery del UNKNOWN NO materializa dinero,
veto XL-3: ver `apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py`):
la orden se resuelve exactamente una vez vía ``query_broker`` (nunca re-POST),
``financial_apply_count`` queda a 0 (no se inventa apply financiero), sin fila UNKNOWN
huérfana ni duplicación.

Escenarios:
* C3-A — un subproceso reclama UNKNOWN y es SIGKILLeado con el claim abierto; un segundo
  subproceso reaparece y lo resuelve EXACTAMENTE una vez.
* C3-B — tras una resolución durable (FILLED persistida), relanzar la recuperación no
  vuelve a transicionar ni a escribir dos veces (idempotencia del ``put`` upsert).
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

pytestmark = pytest.mark.asyncio

_PROBE = Path(__file__).resolve().parent / "_crash_recovery_probe.py"
_C3GATE = "LIVE_A7_PG_REQUIRED"


# ---------------------------------------------------------------------------
# PG env + factory (real, dedicado A7)
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    d = Path(__file__).resolve().parent
    for _ in range(0, 10):
        if (d / ".github").is_dir() and (d / "package.json").is_file():
            return d
        parent = d.parent
        if parent == d:
            break
        d = parent
    return d


def _load_root_env() -> None:
    if os.environ.get("DATABASE_URL"):
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        return
    dotenv = _repo_root() / ".env"
    if dotenv.exists():
        load_dotenv(dotenv, override=False)


def _open_engine() -> AsyncEngine:
    from sqlalchemy.ext.asyncio import create_async_engine

    from bolsa_infrastructure.config import get_settings

    get_settings.cache_clear()
    url = get_settings().database_url
    if url is None:
        raise RuntimeError("database_url not configured")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    # connect_timeout acotado: sin PG el skip del fixture no debe quedar colgado en el
    # timeout TCP por defecto (ergonomía dev; el PG del job A7 del CI responde).
    return create_async_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_C3GATE) == "1":
        raise AssertionError(
            f"live_a7 C3 required but PostgreSQL/Alembic unavailable: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic no disponible: {exc}")


@pytest_asyncio.fixture
async def factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Session-factory aislado para la batería C3 (PG real dedicado A7).

    Operativa: conecta (gate por `SELECT 1`) y lleva la BD dedicada a la head 023 vía
    `ensure_migrated` (idempotente, respeta `DATABASE_URL` de settings) para no depender
    de la migración CLI de `alembic.ini` (que apunta a la DB principal). Un esquema
    inexistente o desalineado se corrige aquí; si PG no responde → skip (o fail duro con
    `LIVE_A7_PG_REQUIRED=1`).
    """
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_session_factory

    _load_root_env()
    engine = _open_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        _require_or_skip(exc)
        raise RuntimeError("unreachable")  # noqa: B904
    # Esquema listo a head 023 de forma idempotente sobre la BD dedicada.
    await asyncio.to_thread(ensure_migrated)
    session_factory = create_session_factory(engine)
    try:
        yield session_factory
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Seeds / comprobaciones de la fila `live_orders` live_a7
# ---------------------------------------------------------------------------


def unique_order_id(prefix: str = "c3") -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def worker_id(tag: str) -> str:
    return f"live-a7-{tag}-{uuid4().hex[:6]}"


async def seed_unknown_row(factory, *, order_id: str, quantity: float = 100.0) -> None:
    """Crea una fila `live_orders` UNKNOWN durable (camino real del store)."""
    from bolsa_analytics.cognitive.live_order import (
        build_live_order,
        transition_live_order,
    )
    from bolsa_application.live_order_store import PostgresLiveOrderStore

    vid = f"xtb-{order_id}"
    built = build_live_order(
        order_id=order_id,
        instrument_id="inst-c3-a7",
        side="buy",
        quantity=quantity,
        account_id="acc-c3-test",
    )
    submitted = transition_live_order(built, "SUBMITTING", venue_order_id=vid)
    unknown = transition_live_order(submitted, "UNKNOWN")
    async with factory() as session:
        await PostgresLiveOrderStore(session).put(unknown, account_id="acc-c3-test")


async def fetch_order(factory, order_id: str):
    from bolsa_application.live_order_store import PostgresLiveOrderStore

    async with factory() as session:
        return await PostgresLiveOrderStore(session).get(order_id)


async def count_unknown(factory) -> int:
    from bolsa_application.live_order_store import PostgresLiveOrderStore

    async with factory() as session:
        return len(await PostgresLiveOrderStore(session).list_unknown(limit=1000))


async def cleanup_row(factory, order_id: str) -> None:
    from bolsa_application.live_order_store import PostgresLiveOrderStore

    try:
        async with factory() as session:
            await PostgresLiveOrderStore(session).delete(order_id)
    except Exception:  # noqa: BLE001 — cleanup best-effort
        pass


# ---------------------------------------------------------------------------
# Driver de subproceso (proceso REAL) + espera por sentinel
# ---------------------------------------------------------------------------


def _probe_env(*, mode: str, sentinel: str, worker: str) -> dict[str, str]:
    env = dict(os.environ)
    env["LIVE_A7_PROBE_MODE"] = mode
    env["LIVE_A7_SENTINEL"] = sentinel
    env["LIVE_A7_WORKER_ID"] = worker
    return env


def launch_probe(*, mode: str, sentinel: Path, worker: str):
    """Arranca el probe (proceso real Python) y devuelve el ``Popen`` no bloqueante."""
    sentinel.unlink(missing_ok=True)
    return subprocess.Popen(
        [sys.executable, str(_PROBE)],
        env=_probe_env(mode=mode, sentinel=str(sentinel), worker=worker),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def wait_until(pred: Callable[[], bool], timeout: float = 40.0, step: float = 0.1) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(step)
    return False


def wait_sentinel_text(sentinel: Path, timeout: float = 40.0) -> str:
    """Espera el sentinel (texto no vacío) y verifica que no arranque con ``error:``."""
    out: list[str] = []

    def _has_text() -> bool:
        if not sentinel.exists():
            return False
        try:
            value = sentinel.read_text(encoding="utf-8").strip()
        except OSError:
            return False
        if value == "":
            return False
        out.append(value)
        return True

    assert wait_until(_has_text, timeout=timeout), f"timeout esperando sentinel {sentinel}"
    assert not out[0].startswith("error:"), f"probe falló: {out[0]}"
    return out[0]


def force_kill(proc) -> None:
    try:
        proc.kill()
        proc.wait(timeout=8.0)
    except (OSError, subprocess.TimeoutExpired):
        pass


def wait_for_exit(proc) -> None:
    try:
        proc.wait(timeout=30.0)
    except subprocess.TimeoutExpired:
        force_kill(proc)


def sentinel_write(tmp_path: Path, tag: str) -> Path:
    return tmp_path / f"sentinel-{tag}.txt"


# ---------------------------------------------------------------------------
# Escenarios
# ---------------------------------------------------------------------------


async def test_c3a_crash_after_recovery_claim_then_second_is_exact_once(
    factory,
    tmp_path: Path,
) -> None:
    """C3-A: crash real (SIGKILL) con claim en vivo → recuperación exacta-una vez."""
    order_id = unique_order_id("c3a")
    await seed_unknown_row(factory, order_id=order_id, quantity=100.0)

    sentinel_a = sentinel_write(tmp_path, "a")
    proc_a = launch_probe(mode="crasher", sentinel=sentinel_a, worker=worker_id("a"))
    try:
        text_a = wait_sentinel_text(sentinel_a, timeout=40.0)
        assert "claimed=" in text_a, f"crasher no reclamó nada: {text_a!r}"
        claimed = text_a.split("claimed=", 1)[1]
        assert order_id in claimed, f"crasher reclamó otras filas: {claimed!r}"

        # Mientras el proceso A vive nada quedó durable: la orden sigue UNKNOWN.
        mid = await fetch_order(factory, order_id)
        assert mid is not None and mid.status == "UNKNOWN", (
            "tras el claim (sin commit) no debe haberse salido del UNKNOWN"
        )

        # Kill real en el peor instante (claim FOR UPDATE abierto, sin commit).
        force_kill(proc_a)
        wait_for_exit(proc_a)
    finally:
        force_kill(proc_a)
        wait_for_exit(proc_a)

    # Segundo proceso reaparece y recupera exactamente una vez (rollback del claim A).
    sentinel_b = sentinel_write(tmp_path, "b")
    proc_b = launch_probe(mode="reader", sentinel=sentinel_b, worker=worker_id("b"))
    try:
        text_b = wait_sentinel_text(sentinel_b, timeout=40.0)
        assert "resolved=1" in text_b, (
            f"el segundo proceso no resolvió exactamente una vez: {text_b!r}"
        )
        wait_for_exit(proc_b)
    finally:
        force_kill(proc_b)
        wait_for_exit(proc_b)

    try:
        final = await fetch_order(factory, order_id)
        assert final is not None, "la orden no quedó persistida tras la recuperación"
        assert final.status == "FILLED"
        assert int(final.financial_apply_count) == 0, (
            "C3 fsm_only: no debe haberse inventado apply financiero"
        )
        assert float(final.remaining_quantity) == 0.0
        assert await count_unknown(factory) == 0, "quedaron UNKNOWN huérfanas tras C3-A"
    finally:
        await cleanup_row(factory, order_id)


async def test_c3b_crash_after_resolve_put_no_double_on_relaunch(
    factory,
    tmp_path: Path,
) -> None:
    """C3-B: relanzar la recuperación tras un resolve durable no duplica transición."""
    order_id = unique_order_id("c3b")
    await seed_unknown_row(factory, order_id=order_id, quantity=100.0)
    try:
        sentinel_1 = sentinel_write(tmp_path, "b1")
        proc_1 = launch_probe(mode="reader", sentinel=sentinel_1, worker=worker_id("b1"))
        try:
            text_1 = wait_sentinel_text(sentinel_1, timeout=40.0)
            assert "resolved=1" in text_1, f"primer resolve no reclamó la fila: {text_1!r}"
            wait_for_exit(proc_1)
        finally:
            force_kill(proc_1)
            wait_for_exit(proc_1)

        # La fila ya es terminal (FILLED, no UNKNOWN) → relanzar es no-op.
        sentinel_2 = sentinel_write(tmp_path, "b2")
        proc_2 = launch_probe(mode="reader", sentinel=sentinel_2, worker=worker_id("b2"))
        try:
            text_2 = wait_sentinel_text(sentinel_2, timeout=40.0)
            assert "drained=0" in text_2 and "resolved=0" in text_2, (
                f"relanzar no debería re-procesar: {text_2!r}"
            )
            wait_for_exit(proc_2)
        finally:
            force_kill(proc_2)
            wait_for_exit(proc_2)

        final = await fetch_order(factory, order_id)
        assert final is not None and final.status == "FILLED"
        assert int(final.financial_apply_count) == 0, (
            "no debe re-aplicarse efecto financiero en un relanzamiento"
        )
    finally:
        await cleanup_row(factory, order_id)
