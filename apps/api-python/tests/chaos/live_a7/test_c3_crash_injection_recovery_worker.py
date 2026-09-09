"""C3 🔴 — Crash-injection real sobre el worker de recovery/scheduler (Iter-1 A7).

Batería V2.18 que empieza a cerrar el gap principal de la Iter-0 de A7:

* PG REAL aislado (BD dedicada ``bolsa_v1_a7`` en el job CI ``a7-gate``). Si no hay
  PostgreSQL o el Alembic no está a la head (hoy ``024_execution_events_state``) →
  ``pytest.skip`` salvo
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
    from bolsa_infrastructure.config import get_settings
    from sqlalchemy.ext.asyncio import create_async_engine

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

    Operativa: conecta (gate por `SELECT 1`) y lleva la BD dedicada a la head (hoy
    `024_execution_events_state`) vía
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
    # Esquema listo a la head (024_execution_events_state) de forma idempotente.
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


def _probe_env(
    *,
    mode: str,
    sentinel: str,
    worker: str,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ)
    env["LIVE_A7_PROBE_MODE"] = mode
    env["LIVE_A7_SENTINEL"] = sentinel
    env["LIVE_A7_WORKER_ID"] = worker
    # Go fail-closed del apply financiero: solo se materializa dinero vía el
    # puente V2.19/P2-01 cuando el subproceso lo trae explícito (default OFF).
    env.setdefault("LIVE_ORDER_RECOVERY_FINANCIAL_APPLY_ENABLED", "1")
    if extra:
        env.update(extra)
    return env


def launch_probe(
    *,
    mode: str,
    sentinel: Path,
    worker: str,
    extra: dict[str, str] | None = None,
):
    """Arranca el probe (proceso real Python) y devuelve el ``Popen`` no bloqueante."""
    sentinel.unlink(missing_ok=True)
    return subprocess.Popen(
        [sys.executable, str(_PROBE)],
        env=_probe_env(mode=mode, sentinel=str(sentinel), worker=worker, extra=extra),
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


# ---------------------------------------------------------------------------
# C3-C / C3-D — vertiente FINANCIERA del crash (V2.19 · P2-01), PG real.
# ---------------------------------------------------------------------------
# Produce un LENADO recuperado REAL (cuenta+cartera+cash en la BD dedicada A7) que
# el puente V2.19 materializa por fases (CAPTURED→APPLYING→APPLIED) con ExecuteTrade
# idempotente por `idempotency_key`. La cuenta/cash/posición/ledger las lee un
# `ExecuteTrade` real vía los repos de producción sobre la MISMA BD.
_FIN_PRICE = 12.50


def fin_extra(*, order_id: str, fill_seq: str) -> dict[str, str]:
    return {
        "LIVE_A7_FIN_ORDER_ID": order_id,
        "LIVE_A7_FIN_FILL_SEQ": fill_seq,
        "LIVE_A7_FIN_FILL_PRICE": str(_FIN_PRICE),
    }


async def seed_financial_acct_instr(session, *, name: str, instrument_id: str) -> str:
    """Cuenta simulada REAL + instrumento (id dado) en la BD dedicada A7.

    Patrón canónico heredado de `infrastructure/tests/chaos/test_crash_consistency.py`
    (``create_simulated_account`` + ``InstrumentRow``) para darle a ``ExecuteTrade``
    la cuenta/cartera/cash/settings/legacy que necesita. Devuelve el account_id. El
    ``instrument_id`` se pasa desde el test para que sea el MISMO que el del fill del
    recovery (ExecuteTrade materializa sobre ese instrument real).
    """
    from datetime import UTC, datetime
    from uuid import uuid4

    from bolsa_infrastructure.database.models.tables import InstrumentRow
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=name,
        initial_deposit=100_000.0,
    )
    hexsuffix = uuid4().hex
    session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=f"CF{hexsuffix[:5].upper()}",
            yahoo_symbol=f"CF{hexsuffix[:9]}",
            isin=None,
            name=name,
            exchange="BMAD",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    await session.flush()
    await session.commit()
    return scope.account.id


async def seed_financial_unknown(
    *,
    session,
    order_id: str,
    account_id: str,
    instrument_id: str,
    quantity: float = 100.0,
    side: str = "buy",
) -> str:
    """Crea la fila `live_orders` UNKNOWN durable ligada a la cuenta/instrumento reales."""
    from bolsa_analytics.cognitive.live_order import (
        build_live_order,
        transition_live_order,
    )
    from bolsa_application.live_order_store import PostgresLiveOrderStore

    vid = f"xtb-{order_id}"
    built = build_live_order(
        order_id=order_id,
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        account_id=account_id,
    )
    submitted = transition_live_order(built, "SUBMITTING", venue_order_id=vid)
    unknown = transition_live_order(submitted, "UNKNOWN")
    await PostgresLiveOrderStore(session).put(unknown, account_id=account_id)
    await session.commit()
    return vid


async def cleanup_financial(
    factory,
    *,
    account_id: str,
    instrument_id: str,
    execution_id: str,
    order_id: str,
) -> None:
    """Borra cuenta (cierre+delete canónico) + instrumento + traza + live_order."""
    async with factory() as session:
        from bolsa_application.live_order_store import PostgresLiveOrderStore
        from bolsa_infrastructure.database.models.tables import (
            ExecutionEventRow,
            InstrumentRow,
        )
        from bolsa_infrastructure.database.repositories.account_repository import (
            SqlAlchemyAccountRepository,
        )
        from sqlalchemy import delete

        try:
            await PostgresLiveOrderStore(session).delete(order_id)
        finally:
            pass
        try:
            await session.execute(
                delete(ExecutionEventRow).where(ExecutionEventRow.execution_id == execution_id)
            )
        finally:
            pass
        repo = SqlAlchemyAccountRepository(session)
        try:
            await repo.close_account(account_id)
            await repo.delete_simulated_account(account_id)
        except Exception:  # noqa: BLE001 — best-effort
            pass
        try:
            await session.execute(delete(InstrumentRow).where(InstrumentRow.id == instrument_id))
        except Exception:  # noqa: BLE001 — best-effort
            pass
        try:
            await session.commit()
        except Exception:  # noqa: BLE001 — best-effort
            await session.rollback()


async def fin_event_row(factory, *, execution_id: str):
    async with factory() as session:
        from bolsa_infrastructure.database.models.tables import ExecutionEventRow
        from sqlalchemy import select

        return (
            await session.execute(
                select(ExecutionEventRow).where(ExecutionEventRow.execution_id == execution_id)
            )
        ).scalar_one_or_none()


async def fin_account_total_cash(factory, *, account_id: str) -> float:
    async with factory() as session:
        from decimal import Decimal

        from bolsa_infrastructure.database.models.tables import (
            InvestmentPortfolioRow,
            PortfolioRow,
        )
        from sqlalchemy import select

        rows = (
            await session.execute(
                select(PortfolioRow.cash)
                .join(
                    InvestmentPortfolioRow,
                    InvestmentPortfolioRow.legacy_portfolio_id == PortfolioRow.id,
                )
                .where(InvestmentPortfolioRow.account_id == account_id)
            )
        ).scalars().all()
        return float(sum((c for c in rows), Decimal("0")))


async def fin_count_ledger_effects(factory, *, account_id: str) -> int:
    """Nº de filas ledger del efecto financiero real (buy/sell/trade) del account.

    Invariante A7: tras el crash+reclaim SOLO UNA materialización (1 efecto ledger).
    Un doble apply dejaría dos. Reutiliza la semántica exacta con la que
    ``ExecuteTrade`` escribe el ledger (``entry_type`` = 'buy'|'sell').
    """
    async with factory() as session:
        from bolsa_infrastructure.database.models.tables import LedgerEntryRow
        from sqlalchemy import func, select

        return int(
            (
                await session.execute(
                    select(func.count(LedgerEntryRow.id)).where(
                        LedgerEntryRow.account_id == account_id,
                        LedgerEntryRow.type.in_(("buy", "sell", "trade")),
                    )
                )
            ).scalar_one()
        )


async def _account_legacy_ids(session, account_id: str):
    from bolsa_infrastructure.database.models.tables import InvestmentPortfolioRow
    from sqlalchemy import select

    return list(
        (
            await session.execute(
                select(InvestmentPortfolioRow.legacy_portfolio_id).where(
                    InvestmentPortfolioRow.account_id == account_id
                )
            )
        ).scalars()
    )


async def fin_position_for_instrument(factory, *, account_id: str, instrument_id: str) -> float:
    async with factory() as session:
        from bolsa_infrastructure.database.models.tables import PositionRow
        from sqlalchemy import func, select

        legacy = await _account_legacy_ids(session, account_id)
        q = (
            await session.execute(
                select(func.coalesce(func.sum(PositionRow.quantity), 0)).where(
                    PositionRow.portfolio_id.in_(legacy),
                    PositionRow.instrument_id == instrument_id,
                )
            )
        ).scalar_one()
        return float(q or 0)


async def seed_captured_event(factory, *, execution_id: str, worker: str) -> None:
    """Siembra una traza ``execution_events`` en CAPTURED (sin order/live_order).

    Es el punto de partida de los CONCURSOS de adquisición (Single-owner): two
    workers concurrently intentan ``start_apply`` sobre el mismo ``execution_id``
    CAPTURED. No pasa por ningún puente recovery/ExecuteTrade: se centra en el CAS
    del execution_event en aislamiento real-PG.
    """
    from datetime import UTC, datetime
    from decimal import Decimal
    from uuid import uuid4

    from bolsa_infrastructure.database.models.tables import ExecutionEventRow

    async with factory() as session:
        session.add(
            ExecutionEventRow(
                execution_id=execution_id,
                order_id=f"cas-{uuid4().hex[:8]}",
                venue="LIVE",
                account_id="acc-cas",
                venue_order_id=execution_id,
                fill_seq=1,
                qty=Decimal("10"),
                captured_at=datetime.now(UTC),
                status="CAPTURED",
                attempt_count=0,
                lease_owner=None,
                updated_at=datetime.now(UTC),
            )
        )
        await session.commit()
    _ = worker


async def age_stale_applying(factory, *, execution_id: str, ago_seconds: int) -> None:
    """Envejece el lease ``updated_at`` de una fila APPLYING (simula dueño muerto).

    Solo para pruebas de reclaim/crash: hace retroceder el reloj de lease para que
    el siguiente reclaim lo considere VENCIDO (equivalente a que el worker real, al
    caerse, deje de hacer heartbeat de su updated_at por más de ``ago_seconds``).
    """
    from datetime import UTC, datetime, timedelta

    import sqlalchemy as sa
    from bolsa_infrastructure.database.models.tables import ExecutionEventRow

    past = datetime.now(UTC) - timedelta(seconds=ago_seconds)
    async with factory() as session:
        await session.execute(
            sa.update(ExecutionEventRow)
            .where(ExecutionEventRow.execution_id == execution_id)
            .values(updated_at=past)
        )
        await session.commit()


async def cleanup_execution_event(factory, *, execution_id: str) -> None:
    async with factory() as session:
        from bolsa_infrastructure.database.models.tables import ExecutionEventRow
        from sqlalchemy import delete

        await session.execute(
            delete(ExecutionEventRow).where(ExecutionEventRow.execution_id == execution_id)
        )
        await session.commit()


async def test_c3c_crash_financial_apply_reexecuted_exact_once(factory, tmp_path: Path) -> None:
    """C3-C: crash real en MEDIO del apply financiero → re-run materializa UNA sola vez.

    Subproceso A: captura la traza durable, pasa a APPLYING (commit) y ejecuta el
    ExecuteTrade real (dinero en vuelo, SIN commit) y parkea ahí — el peor instante.
    El driver hace SIGKILL: la transacción de A (cash/posición/ledger sin commit)
    cae en ROLLBACK; la traza queda durable en APPLYING. Subproceso B (segundo
    proceso real): re-encuentra la traza durable APPLYING y la reclama por
    `apply_execution_financial_once` idempotente → materializa EXACTAMENTE una
    posición/ledger y deja la traza terminal APPLIED, sin 100+100 ni 100+0.
    """
    from uuid import uuid4

    order_id = unique_order_id("c3c")
    instrument_id = f"inst-c3c-{uuid4().hex[:8]}"
    exec_id = ""
    async with factory() as session:
        # account/cash reales + instrument real (ExecuteTrade los materializa).
        account_id = await seed_financial_acct_instr(
            session, name=f"C3C-{order_id}", instrument_id=instrument_id
        )
        vid = await seed_financial_unknown(
            session=session,
            order_id=order_id,
            account_id=account_id,
            instrument_id=instrument_id,
            quantity=100.0,
        )
        await session.commit()
    exec_id = f"{vid}#1"
    try:
        # A — crash point financiero (APPLYING durable + ExecuteTrade en vuelo).
        sentinel_a = sentinel_write(tmp_path, "c3c-a")
        proc_a = launch_probe(
            mode="crasher-financial",
            sentinel=sentinel_a,
            worker=worker_id("c3ca"),
            extra=fin_extra(order_id=order_id, fill_seq="1"),
        )
        try:
            text_a = wait_sentinel_text(sentinel_a, timeout=45.0)
            assert "financial-applying=1" in text_a, f"crasher financiero no llegó: {text_a!r}"
            force_kill(proc_a)
            wait_for_exit(proc_a)
        finally:
            force_kill(proc_a)
            wait_for_exit(proc_a)

        # Tras el kill la traza quedó durable en APPLYING (sin doble materializar).
        ev_mid = await fin_event_row(factory, execution_id=exec_id)
        assert ev_mid is not None, "no queda traza durable tras el crash financiero"
        assert ev_mid.status == "APPLYING", (
            f"crash en medio del apply debe dejar APPLYING durable, era {ev_mid.status}"
        )

        # B — segundo proceso real reclama y materializa exactamente una vez.
        sentinel_b = sentinel_write(tmp_path, "c3c-b")
        proc_b = launch_probe(
            mode="reader-financial",
            sentinel=sentinel_b,
            worker=worker_id("c3cb"),
            extra=fin_extra(order_id=order_id, fill_seq="1"),
        )
        try:
            text_b = wait_sentinel_text(sentinel_b, timeout=45.0)
            assert "finished=applied" in text_b, f"el reclaim financiero falló: {text_b!r}"
            wait_for_exit(proc_b)
        finally:
            force_kill(proc_b)
            wait_for_exit(proc_b)

        # Evento terminal APPLIED con attempt≥1 y efecto financiero ÚNICO.
        ev = await fin_event_row(factory, execution_id=exec_id)
        assert ev is not None and ev.status == "APPLIED", (
            f"la traza debió quedar APPLIED, era {getattr(ev, 'status', None)!r}"
        )
        assert ev.attempt_count >= 1, "attempt_count debió registrar el (re)apply"
        assert ev.applied_at is not None, "APPLIED debe llevar applied_at"
        pos = await fin_position_for_instrument(
            factory, account_id=account_id, instrument_id=instrument_id
        )
        # Posición EXACTAMENTE una vez: 100 (no 200) — nunca 100+100.
        assert pos == float("100.0"), f"posición exactamente-una (100), era {pos}"
        # Un único efecto ledger del fill (no dos).
        assert await fin_count_ledger_effects(
            factory, account_id=account_id
        ) == 1, "el crash+reclaim debió escribir UN solo efecto ledger de fill"
        cash = await fin_account_total_cash(factory, account_id=account_id)
        # cash == 100000 − 100×12.50 − comisiones (una sola vez; si hubiera sido
        # aplicado dos veces bajaría en > 2×notional).
        assert cash < 100_000.0 and cash > 100_000.0 - 2 * 100 * _FIN_PRICE, (
            f"cash NO deducido exactamente una vez: {cash}"
        )
    finally:
        await cleanup_financial(
            factory,
            account_id=account_id,
            instrument_id=instrument_id,
            execution_id=exec_id,
            order_id=order_id,
        )


async def test_c3d_reclaim_applying_or_terminal_no_double(factory, tmp_path: Path) -> None:
    """C3-D: reapply de un fill ya APPLIED → strict no-op (no-doble terminal).

    Tras materializar una vez (traza APPLIED durable con 1 efecto de cash/posición),
    un segundo proceso real solicita de nuevo el mismo fill recuperado (restart/
    re-emisión del que autorizó el recovery) y `apply_execution_financial_once`
    responde `already_applied` SIN tocar dinero: el ledger/cash/posición, el
    `attempt_count` y el `applied_at` quedan idénticos. Cierra el no-doble 100+100
    incluso cuando el reclaim se re-entrega sobre un evento ya consumado.
    """
    from uuid import uuid4

    order_id = unique_order_id("c3d")
    instrument_id = f"inst-c3d-{uuid4().hex[:8]}"
    exec_id = ""
    async with factory() as session:
        account_id = await seed_financial_acct_instr(
            session, name=f"C3D-{order_id}", instrument_id=instrument_id
        )
        vid = await seed_financial_unknown(
            session=session,
            order_id=order_id,
            account_id=account_id,
            instrument_id=instrument_id,
            quantity=100.0,
        )
        await session.commit()
    exec_id = f"{vid}#1"
    try:
        # 1er apply financiero real → APPLIED durable (1 efecto). C3-C prueba el
        # crash-mitad; aquí verificamos el guard TERMINAL del reclaim repetido.
        sentinel_1 = sentinel_write(tmp_path, "c3d-1")
        proc_1 = launch_probe(
            mode="reader-financial",
            sentinel=sentinel_1,
            worker=worker_id("c3d1"),
            extra=fin_extra(order_id=order_id, fill_seq="1"),
        )
        try:
            text_1 = wait_sentinel_text(sentinel_1, timeout=45.0)
            assert "finished=applied" in text_1, f"1er apply financiero falló: {text_1!r}"
            wait_for_exit(proc_1)
        finally:
            force_kill(proc_1)
            wait_for_exit(proc_1)

        row_after_first = await fin_event_row(factory, execution_id=exec_id)
        cash_first = await fin_account_total_cash(factory, account_id=account_id)
        pos_first = await fin_position_for_instrument(
            factory, account_id=account_id, instrument_id=instrument_id
        )
        ledger_first = await fin_count_ledger_effects(factory, account_id=account_id)
        assert row_after_first is not None and row_after_first.status == "APPLIED"
        assert pos_first == float("100.0")
        assert ledger_first == 1

        # Reclaim / replay del MISMO fill → already_applied, cero dinero nuevo.
        sentinel_2 = sentinel_write(tmp_path, "c3d-2")
        proc_2 = launch_probe(
            mode="reader-financial",
            sentinel=sentinel_2,
            worker=worker_id("c3d2"),
            extra=fin_extra(order_id=order_id, fill_seq="1"),
        )
        try:
            text_2 = wait_sentinel_text(sentinel_2, timeout=45.0)
            assert "finished=already_applied" in text_2, (
                f"reclaim sobre APPLIED debió ser already_applied: {text_2!r}"
            )
            wait_for_exit(proc_2)
        finally:
            force_kill(proc_2)
            wait_for_exit(proc_2)

        # Invariante: nada cambió (posición/cash/ledger/attempt/applied_at).
        ev2 = await fin_event_row(factory, execution_id=exec_id)
        assert ev2 is not None and ev2.status == "APPLIED"
        assert getattr(ev2, "attempt_count", None) == row_after_first.attempt_count
        assert getattr(ev2, "applied_at", None) == row_after_first.applied_at
        cash_second = await fin_account_total_cash(factory, account_id=account_id)
        pos_second = await fin_position_for_instrument(
            factory, account_id=account_id, instrument_id=instrument_id
        )
        ledger_second = await fin_count_ledger_effects(factory, account_id=account_id)
        assert cash_second == cash_first, "reclaim terminal NO debió mover cash"
        assert pos_second == pos_first == float("100.0"), (
            "reclaim terminal NO debió duplicar la posición"
        )
        assert ledger_second == ledger_first == 1, (
            "reclaim terminal NO debió añadir efecto ledger"
        )
    finally:
        await cleanup_financial(
            factory,
            account_id=account_id,
            instrument_id=instrument_id,
            execution_id=exec_id,
            order_id=order_id,
        )


# ---------------------------------------------------------------------------
# V2.20 (P1-01/#2) — CONCURSO de adquisición real-PG: SINGLE-OWNER (winner=1/loser=0)
# ---------------------------------------------------------------------------
# El test obligatorio del audit: dos WORKERS reales (subprocesos) intentan
# ``start_apply`` sobre EL MISMO ``execution_events`` en CAPTURED. Resultado
# obligatorio: EXACTAMENTE un winner (``won=1``) y un loser (``won=0``), nunca dos
# ``won=1``. Es la propiedad que P1-01 asegura ahora con CAS atómico SQL.


async def test_v220_two_workers_cas_exactly_one_owner(factory, tmp_path: Path) -> None:
    from uuid import uuid4

    exec_id = f"cas-{uuid4().hex[:16]}"
    try:
        await seed_captured_event(factory, execution_id=exec_id, worker="seed")

        # Dos procesos reales compiten por el MISMO CAPTURED al mismo tiempo.
        proc_a = launch_probe(
            mode="cas-contest",
            sentinel=sentinel_write(tmp_path, "cas-a"),
            worker=worker_id("casa"),
            extra={"LIVE_A7_CAS_EXECUTION_ID": exec_id},
        )
        proc_b = launch_probe(
            mode="cas-contest",
            sentinel=sentinel_write(tmp_path, "cas-b"),
            worker=worker_id("casb"),
            extra={"LIVE_A7_CAS_EXECUTION_ID": exec_id},
        )
        try:
            text_a = wait_sentinel_text(sentinel_write(tmp_path, "cas-a"), timeout=45.0)
            text_b = wait_sentinel_text(sentinel_write(tmp_path, "cas-b"), timeout=45.0)
        finally:
            force_kill(proc_a)
            force_kill(proc_b)
            wait_for_exit(proc_a)
            wait_for_exit(proc_b)

        assert "won=1" in text_a or "won=1" in text_b, (
            f"debe haber EXACTAMENTE un winner, A={text_a!r} B={text_b!r}"
        )
        count_won = int("won=1" in text_a) + int("won=1" in text_b)
        # El test #2 obligatorio: winner=1, loser=0, nunca ambos True.
        assert count_won == 1, f"CAS roto: ambos workers ganaron o ninguno ({text_a!r}, {text_b!r})"
        assert ("won=0" in text_a) != ("won=0" in text_b), (
            f"debe haber exactamente un loser: {text_a!r} {text_b!r}"
        )
    finally:
        await cleanup_execution_event(factory, execution_id=exec_id)


# ---------------------------------------------------------------------------
# V2.20 (C3-E) — crash DESPUÉS del commit financiero y ANTES del APPLIED
# ---------------------------------------------------------------------------
# El peor instante "posterior" del apply (tu #9 / Auditoría): el dinero de
# ExecuteTrade ya está COMMITTED (durable) pero la traza sigue en APPLYING cuando
# el proceso muere. La recuperación (B) debe re-encajar la traza durable: reclama el
# APPLYING (lease del dueño caído) y, aunque ExecuteTrade vuelve a ejecutarse, la
# idempotencia por `recovery_idempotency_key` corta y NO duplica ledger/posición.
# Invariante: cash/posición/ledger EXACTAMENTE como tras UN solo apply (valor dura
# del commit de A), y la traza pasa a APPLIED apenas B reclama.


async def test_c3e_crash_after_financial_commit_no_second_effect(
    factory, tmp_path: Path
) -> None:
    _ = tmp_path
    from uuid import uuid4

    order_id = unique_order_id("c3e")
    instrument_id = f"inst-c3e-{uuid4().hex[:8]}"
    exec_id = ""
    async with factory() as session:
        account_id = await seed_financial_acct_instr(
            session, name=f"C3E-{order_id}", instrument_id=instrument_id
        )
        vid = await seed_financial_unknown(
            session=session,
            order_id=order_id,
            account_id=account_id,
            instrument_id=instrument_id,
            quantity=100.0,
        )
        await session.commit()
    exec_id = f"{vid}#1"
    try:
        # A: commit FINANCIERO durable (dinero materializado) + la traza en APPLYING.
        sentinel_a = sentinel_write(tmp_path, "c3e-a")
        extra = {**fin_extra(order_id=order_id, fill_seq="1"), "LIVE_A7_FIN_CRASH_COMMITTED": "1"}
        proc_a = launch_probe(
            mode="crasher-financial",
            sentinel=sentinel_a,
            worker=worker_id("c3ea"),
            extra=extra,
        )
        try:
            text_a = wait_sentinel_text(sentinel_a, timeout=45.0)
            assert "financial-committed=1" in text_a, f"C3-E crasher no llegó: {text_a!r}"
        finally:
            force_kill(proc_a)
            wait_for_exit(proc_a)

        # Tras el SIGKILL: el dinero de A quedó COMMITTED (cash/posición/ledger
        # valen ya) pero la traza aún está en APPLYING (sin APPLIED).
        ev_a = await fin_event_row(factory, execution_id=exec_id)
        assert ev_a is not None and ev_a.status == "APPLYING", (
            f"C3-E: crash tras commit debe dejar APPLYING durable, era {ev_a and ev_a.status}"
        )
        cash_a = await fin_account_total_cash(factory, account_id=account_id)
        pos_a = await fin_position_for_instrument(
            factory, account_id=account_id, instrument_id=instrument_id
        )
        ledger_a = await fin_count_ledger_effects(factory, account_id=account_id)
        assert pos_a == float("100.0"), "el commit financiero de A materializó la posición"
        assert ledger_a == 1, "el commit financiero de A dejó UNA effect de ledger"

        # B reclama el APPLYING (dueño caído, lease 0) y reaparece la traza.
        sentinel_b = sentinel_write(tmp_path, "c3e-b")
        proc_b = launch_probe(
            mode="reader-financial",
            sentinel=sentinel_b,
            worker=worker_id("c3eb"),
            extra=fin_extra(order_id=order_id, fill_seq="1"),
        )
        try:
            text_b = wait_sentinel_text(sentinel_b, timeout=45.0)
            assert "finished=applied" in text_b, f"recovery tras C3-E falló: {text_b!r}"
            wait_for_exit(proc_b)
        finally:
            force_kill(proc_b)
            wait_for_exit(proc_b)

        # Invariante: NO hubo 2º efecto — dinero/posición/ledger exactos de A.
        ev_fin = await fin_event_row(factory, execution_id=exec_id)
        assert ev_fin is not None and ev_fin.status == "APPLIED", (
            f"tras recovery C3-E la traza debe ser APPLIED: {ev_fin and ev_fin.status}"
        )
        cash_fin = await fin_account_total_cash(factory, account_id=account_id)
        pos_fin = await fin_position_for_instrument(
            factory, account_id=account_id, instrument_id=instrument_id
        )
        ledger_fin = await fin_count_ledger_effects(factory, account_id=account_id)
        assert cash_fin == cash_a, "recovery C3-E NO debió mover cash (400-1250 exactos)"
        assert pos_fin == pos_a == float("100.0"), (
            "recovery C3-E NO debió duplicar la posición"
        )
        assert ledger_fin == ledger_a == 1, "recovery C3-E NO debió añadir efecto ledger"
    finally:
        await cleanup_financial(
            factory,
            account_id=account_id,
            instrument_id=instrument_id,
            execution_id=exec_id,
            order_id=order_id,
        )


# ---------------------------------------------------------------------------
# V2.20 (P2-02) — reaper real-PG: orfanado APPLYING (lease muerto) → APPLIED
# ---------------------------------------------------------------------------
# Escenario que cierra P2-02 con la semántica safe-by-default elegida (sin
# auto-sweep irrestricto en el worker): el MECANISMO de reap se valida aquí sobre
# PG real con un dueño GARANTIZADO-muerto (oración de proceso caído, no worker
# concurrente en marcha). ``reap_stale_applying`` (apply idempotente con
# ExecuteTrade) lleva el orfanado APPLYING a APPLIED una sola vez, y NO roba un
# APPLYING cuya lease sigue viva (single-owner).
async def test_v220_stale_reaper_converges_orphaned_apply(factory, tmp_path: Path) -> None:
    _ = tmp_path
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal
    from uuid import uuid4

    from bolsa_application.accounts import ExecuteTrade
    from bolsa_application.execution_event import (
        LEASE_WINDOW_SECONDS,
        ExecutionEvent,
        PostgresExecutionEventStore,
        reap_stale_applying,
    )
    from bolsa_application.live_order_store import PostgresLiveOrderStore
    from bolsa_application.recovery_apply import recovery_idempotency_key
    from bolsa_infrastructure.database.models.tables import ExecutionEventRow
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    # 1) Scope financiero real: cuenta + instrumento + 2 live_orders (UNKNOWN), uno
    #    para el orfanado (reap) y otro con lease VIVA (no robar).
    order_orph = unique_order_id("c3fang")
    order_live = unique_order_id("c3flive")
    instrument_id = f"inst-c3fang-{uuid4().hex[:8]}"
    async with factory() as session:
        account_id = await seed_financial_acct_instr(
            session, name=f"C3FROPH-{order_orph}", instrument_id=instrument_id
        )
        vid_orph = await seed_financial_unknown(
            session=session, order_id=order_orph, account_id=account_id,
            instrument_id=instrument_id, quantity=100.0,
        )
        vid_live = await seed_financial_unknown(
            session=session, order_id=order_live, account_id=account_id,
            instrument_id=instrument_id, quantity=50.0,
        )
        await session.commit()
    exec_orph = f"{vid_orph}#1"
    exec_live = f"{vid_live}#1"

    try:
        # 2) Siembra del orfanado: traza durable directa en APPLYING con dueño muerto
        #    y lease VECIDA (proceso caído). La VIVA queda con lease fresca (no se roba).
        async with factory() as session:
            now = datetime.now(UTC)
            opid = "dead-worker-orph"
            session.add(
                ExecutionEventRow(
                    execution_id=exec_orph,
                    order_id=order_orph,
                    venue="LIVE",
                    account_id=account_id,
                    venue_order_id=vid_orph,
                    fill_seq=1,
                    qty=Decimal("100.000000"),
                    captured_at=now - timedelta(seconds=600),
                    status="APPLYING",
                    attempt_count=1,
                    lease_owner=opid,
                    updated_at=now - timedelta(seconds=LEASE_WINDOW_SECONDS + 60),
                )
            )
            session.add(
                ExecutionEventRow(
                    execution_id=exec_live,
                    order_id=order_live,
                    venue="LIVE",
                    account_id=account_id,
                    venue_order_id=vid_live,
                    fill_seq=1,
                    qty=Decimal("50.000000"),
                    captured_at=now,
                    status="APPLYING",
                    attempt_count=1,
                    lease_owner="live-worker-b",
                    updated_at=now,  # lease sin vencer.
                )
            )
            await session.commit()

        # 3) Reaper real-PG: misma maquinaria del recovery (ExecuteTrade idempotente).
        async with factory() as session:
            store = PostgresExecutionEventStore(session)
            live_store = PostgresLiveOrderStore(session)
            acct_repo = SqlAlchemyAccountRepository(session)
            port_repo = SqlAlchemyPortfolioRepository(session)
            led_repo = SqlAlchemyLedgerRepository(session)
            trade = ExecuteTrade(acct_repo, port_repo, led_repo)

            async def _applier(ev: ExecutionEvent) -> bool:
                # Apply idempotente por execution_id (igual que el recovery/C3).
                order = await live_store.get(ev.order_id)
                price = _FIN_PRICE
                try:
                    await trade.execute(
                        instrument_id=order.instrument_id,
                        trade_type=order.side,
                        quantity=float(ev.qty),
                        price=price,
                        account_id=ev.account_id,
                        idempotency_key=recovery_idempotency_key(ev.execution_id),
                    )
                    return True
                except Exception:  # noqa: BLE001
                    return False

            async def _resolver(ev: ExecutionEvent) -> ExecutionEvent | None:
                # Re-derivar candidato re-materializable desde su propia traza (no
                # fabrica: usa campos durDB/dominio estables del evento reclamado).
                return ev

            counts = await reap_stale_applying(
                store,
                owner="reaper-pg-1",
                stale_before=datetime.now(UTC) - timedelta(seconds=LEASE_WINDOW_SECONDS),
                limit=10,
                resolve_candidate=_resolver,
                apply_finance=_applier,
            )

        assert counts["reclaimed"] == 1, counts
        assert counts["applied"] == 1, counts
        assert counts["retry"] == 0 and counts["errors"] == 0, counts

        # 4) Invariantes: el orfanado llegó a APPLIED; el VIVO no fue robado.
        row = await fin_event_row(factory, execution_id=exec_orph)
        assert row is not None and row.status == "APPLIED", (
            f"reaper debió llevar el orfanado APPLYING→APPLIED: {row and row.status}"
        )
        assert row.applied_at is not None, "APPLIED debe llevar applied_at"
        assert row.lease_owner is None, "terminal APPLIED libera la lease (no retenida)"
        live = await fin_event_row(factory, execution_id=exec_live)
        assert live is not None and live.status == "APPLYING", (
            f"lease VIVA no debe robarse: {live and live.status}"
        )
        # Money exactamente una vez (posición única del orfanado de 100).
        pos = await fin_position_for_instrument(
            factory, account_id=account_id, instrument_id=instrument_id
        )
        assert pos == float("100.0"), f"reaper debe materializar la posición UNA vez: {pos}"
        assert await fin_count_ledger_effects(factory, account_id=account_id) == 1, (
            "reaper debe escribir UN solo efecto de ledger de fill"
        )
        cash = await fin_account_total_cash(factory, account_id=account_id)
        # Cash == 100000 − 100×12.50 − comisión (UNA vez). Si el apply se duplicara
        # (100+100) bajaría en > 2×notional → quedamos por encima de ese límite.
        assert cash < 100_000.0 and cash > 100_000.0 - 2 * 100 * _FIN_PRICE, (
            f"cash NO deducido exactamente una vez: {cash}"
        )
    finally:
        await cleanup_financial(
            factory,
            account_id=account_id,
            instrument_id=instrument_id,
            execution_id=exec_orph,
            order_id=order_orph,
        )
        # Limpieza del segundo scope (live-no-robado) y su traza.
        async with factory() as session:
            from bolsa_application.live_order_store import PostgresLiveOrderStore
            from bolsa_infrastructure.database.models.tables import ExecutionEventRow
            from sqlalchemy import delete

            await session.execute(
                delete(ExecutionEventRow).where(ExecutionEventRow.execution_id == exec_live)
            )
            await PostgresLiveOrderStore(session).delete(order_live)
            await session.commit()

