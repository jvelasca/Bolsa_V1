"""V2.46.x (AUTO-6 hardening) — recuperación de la parada dura contra PostgreSQL REAL.

El gemelo hermético (``test_auto_v46_hardkill_recovery.py``) certifica la mecánica con los
stores in-memory. Este fichero certifica lo que solo se puede medir con PostgreSQL y con
procesos distintos:

1. **El HALT durable es la autoridad entre procesos** — un worker lo activa y lo persiste;
   un worker NUEVO (otra sesión, cero RAM compartida) lo RESTAURA al arrancar. Es el
   ``WORKER 1 → KILL → CRASH → WORKER 2`` que la auditoría de ``v2.46-beta`` marcó como P0
   abierto (el Crash Day certificaba crash con ``RISK_OFF``/``time_exit``, no con HARD KILL).
2. **La liberación exige ``reconciliation_id`` y viaja por la vía de producción** — la
   escribe el endpoint real (``POST /api/risk/kill-switch/durable-release``) y el worker la
   ADOPTA en su siguiente turno sin reiniciarse (``_v2_load_kill_state``), siempre que la
   liberación sea POSTERIOR a la activación.
3. **Una liberación más ANTIGUA que el halt no lo levanta** — una re-activación posterior
   manda sobre un release previo (se comparan instantes, no texto).
4. **R-1 — un HALT real que la escritura no llegó a fijar se RE-PERSISTE** — si el espejo
   no deja escribir en la activación, la parada vive sólo en RAM; cuando el store vuelve la
   lectura es sana pero sin fila (o con una fila liberada anterior) y hay que reintentar la
   escritura, o el reinicio siguiente reabre el motor. El placeholder
   ``KILL_STATE_UNREADABLE`` nunca se persiste: una lectura incompleta no es autorización
   para operar.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_HARDKILL_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_HARDKILL_PG_REQUIRED"
_ENGINE_ID = "auto-sim"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la recuperación de la parada dura AUTO-6 pero no "
            f"disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (parada dura AUTO-6) no disponible: {exc}")


@pytest_asyncio.fixture
async def hardkill_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _cleanup(
    factory: async_sessionmaker[AsyncSession], *, account_id: str
) -> None:
    from bolsa_infrastructure.database.models.tables import AutoKillStateRow

    async with factory() as session:
        await session.execute(
            delete(AutoKillStateRow).where(AutoKillStateRow.account_id == account_id)
        )
        await session.commit()


def _worker(session: AsyncSession, *, account_id: str) -> object:
    """Worker mínimo cableado a la parada durable real (sin el resto del motor)."""
    from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
    from bolsa_application.kill_switch_store import PostgresKillSwitchStore

    return AutoSimulationWorker(
        engine_id=_ENGINE_ID,
        account_id=account_id,
        kill_switch_store=PostgresKillSwitchStore(session),
    )


class _FaultyKillSwitchStore:
    """Store REAL envuelto: falla las primeras ``load``/``save`` y luego delega.

    Falla ANTES de tocar la sesión, para no envenenarla: el escenario que interesa es que
    el espejo no acepte la escritura (o no pueda leerse) sin dejar la transacción rota.
    ``saved`` guarda sólo las escrituras que llegaron al store: distingue «se intentó
    persistir» de «la parada es durable».
    """

    def __init__(
        self,
        inner: object,
        *,
        fail_loads: int = 0,
        fail_saves: int = 0,
    ) -> None:
        self._inner = inner
        self.fail_loads = fail_loads
        self.fail_saves = fail_saves
        self.loads = 0
        self.saves = 0
        self.failed_writes = 0
        self.saved: list[object] = []

    async def load(self, account_id: str, engine_id: str) -> object:
        self.loads += 1
        if self.fail_loads > 0:
            self.fail_loads -= 1
            raise RuntimeError("kill state not readable (R-1)")
        return await self._inner.load(account_id, engine_id)  # type: ignore[attr-defined]

    async def save(self, state: object) -> bool:
        self.saves += 1
        if self.fail_saves > 0:
            self.fail_saves -= 1
            self.failed_writes += 1
            raise RuntimeError("kill state not writable (R-1)")
        self.saved.append(state)
        return await self._inner.save(state)  # type: ignore[attr-defined]

    async def commit(self) -> None:
        await self._inner.commit()  # type: ignore[attr-defined]


def _faulty_worker(store: _FaultyKillSwitchStore, *, account_id: str) -> object:
    from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker

    return AutoSimulationWorker(
        engine_id=_ENGINE_ID,
        account_id=account_id,
        kill_switch_store=store,
    )


async def _durable_row(session: AsyncSession, *, account_id: str) -> object:
    from bolsa_application.kill_switch_store import PostgresKillSwitchStore

    return await PostgresKillSwitchStore(session).load(account_id, _ENGINE_ID)


def _same_instant(left: str | None, right: str | None) -> bool:
    """Compara INSTANTES, no texto: la columna ``timestamptz`` devuelve ``+00:00``."""
    if left is None or right is None:
        return left == right
    from datetime import UTC, datetime

    def _parse(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)

    try:
        return _parse(left) == _parse(right)
    except ValueError:
        return left == right


@pytest.mark.asyncio
async def test_the_full_hardkill_lifecycle_converges_against_postgres(
    hardkill_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """engage durable → crash → restart HALTED → release con reconciliación → RUNNING."""
    import uuid

    from bolsa_api.api.v1.routes.risk import (
        DurableKillReleaseBody,
        post_durable_kill_release,
    )

    account_id = f"acc-hardkill-{uuid.uuid4().hex[:10]}"
    try:
        # T1/T2 — un worker activa y PERSISTE la parada dura (productor real tipificado).
        async with hardkill_pg_factory() as session:
            w1 = _worker(session, account_id=account_id)  # type: ignore[assignment]
            await w1.engage_kill_switch_durable(  # type: ignore[attr-defined]
                "RECONCILIATION_FAILURE", at="2026-09-15T09:00:00Z"
            )
            assert w1._v2_kill_switch_halted() is True  # type: ignore[attr-defined]

        # T3/T4 — proceso NUEVO (otra sesión): la RAM no comparte nada con el anterior.
        async with hardkill_pg_factory() as session:
            w2 = _worker(session, account_id=account_id)  # type: ignore[assignment]
            assert w2._v2_kill_switch_halted() is False  # type: ignore[attr-defined]
            await w2._v2_load_kill_state()  # type: ignore[attr-defined]
            assert w2._v2_kill_switch_halted() is True  # type: ignore[attr-defined]
            assert w2._v2_kill_switch.reason == "RECONCILIATION_FAILURE"  # type: ignore[attr-defined]

            # La liberación entra por la VÍA DE PRODUCCIÓN (el endpoint real), no por el
            # método del worker: así se mide el camino que usará un operador.
            released = await post_durable_kill_release(
                DurableKillReleaseBody(
                    accountId=account_id,
                    engineId=_ENGINE_ID,
                    reconciliationId="recon-hardkill-77",
                ),
                session,
            )
            assert released.released is True

            # El MISMO worker (sin reiniciarse) adopta la liberación en el siguiente turno.
            await w2._v2_load_kill_state()  # type: ignore[attr-defined]
            assert w2._v2_kill_switch_halted() is False  # type: ignore[attr-defined]

        # Un no-op idempotente: liberar una parada no activa no es un error.
        async with hardkill_pg_factory() as session:
            again = await post_durable_kill_release(
                DurableKillReleaseBody(
                    accountId=account_id,
                    engineId=_ENGINE_ID,
                    reconciliationId="recon-hardkill-77",
                ),
                session,
            )
            assert again.released is False
            assert again.reason == "not_engaged"
    finally:
        await _cleanup(hardkill_pg_factory, account_id=account_id)


@pytest.mark.asyncio
async def test_a_stale_release_does_not_lift_a_newer_halt_against_postgres(
    hardkill_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Una liberación anterior a la re-activación NO levanta el halt vigente."""
    import uuid

    account_id = f"acc-hardkill-{uuid.uuid4().hex[:10]}"
    try:
        async with hardkill_pg_factory() as session:
            w = _worker(session, account_id=account_id)  # type: ignore[assignment]
            await w.engage_kill_switch_durable(  # type: ignore[attr-defined]
                "RECONCILIATION_FAILURE", at="2026-09-15T09:00:00Z"
            )
            await w.release_kill_switch_durable(  # type: ignore[attr-defined]
                reconciliation_ok=True, reconciliation_id="recon-old"
            )
            assert w._v2_kill_switch_halted() is False  # type: ignore[attr-defined]
            # Re-activación POSTERIOR al release.
            await w.engage_kill_switch_durable(  # type: ignore[attr-defined]
                "DUPLICATE_EXECUTION", at="2026-09-15T09:20:00Z"
            )
            assert w._v2_kill_switch_halted() is True  # type: ignore[attr-defined]

        # Proceso nuevo: lee la fila durable ENGAGED (la re-activación manda).
        async with hardkill_pg_factory() as session:
            w2 = _worker(session, account_id=account_id)  # type: ignore[assignment]
            await w2._v2_load_kill_state()  # type: ignore[attr-defined]
            assert w2._v2_kill_switch_halted() is True  # type: ignore[attr-defined]
            assert w2._v2_kill_switch.reason == "DUPLICATE_EXECUTION"  # type: ignore[attr-defined]
    finally:
        await _cleanup(hardkill_pg_factory, account_id=account_id)


# ---------------------------------------------------------------------------
# R-1 — el HALT local cuya escritura no llegó al espejo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r1_a_failed_write_is_repersisted_after_a_healthy_read_against_postgres(
    hardkill_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Escritura fallida → lectura sana SIN fila → re-persistencia → reinicio HALTED.

    Es el ciclo completo del hallazgo, medido contra PG real: sin el reintento de R-1 la
    parada vivía sólo en la RAM del worker y el reinicio siguiente leía «la parada nunca
    se activó» y reabría el motor.
    """
    import uuid

    account_id = f"acc-r1-{uuid.uuid4().hex[:10]}"
    try:
        async with hardkill_pg_factory() as session:
            from bolsa_application.kill_switch_store import PostgresKillSwitchStore

            store = _FaultyKillSwitchStore(PostgresKillSwitchStore(session))
            store.fail_saves = 1
            w = _faulty_worker(store, account_id=account_id)  # type: ignore[assignment]

            assert await w.engage_kill_switch_durable(  # type: ignore[attr-defined]
                "DUPLICATE_EXECUTION", at="2026-09-15T09:00:00Z"
            ) is True
            assert store.saves == 1, "se intentó persistir"
            assert store.failed_writes == 1, "la escritura falló"
            assert await _durable_row(session, account_id=account_id) is None, (
                "el espejo no tiene fila: la parada es sólo local"
            )
            assert w._v2_kill_switch_halted() is True  # type: ignore[attr-defined]
            engagement_id = w._v2_kill_switch.engagement_id  # type: ignore[attr-defined]
            engaged_at = w._v2_kill_switch.engaged_at  # type: ignore[attr-defined]

            # Lectura SANA sin fila: R-1 reintenta la escritura en vez de devolverse.
            await w._v2_load_kill_state()  # type: ignore[attr-defined]
            assert store.saves == 2, "la lectura sana sin fila disparó el reintento"
            assert store.saved, "la escritura se reintentó con éxito"

            row = await _durable_row(session, account_id=account_id)
            assert row is not None
            assert row.engaged is True
            assert row.reason == "DUPLICATE_EXECUTION"
            assert row.engagement_id == engagement_id, (
                "el reintento conserva la identidad de la activación, no inventa otra"
            )
            assert _same_instant(row.engaged_at, engaged_at)

        # Reinicio: sesión nueva, cero RAM compartida. El HALT ya es durable.
        async with hardkill_pg_factory() as session:
            restarted = _worker(session, account_id=account_id)  # type: ignore[assignment]
            assert restarted._v2_kill_switch_halted() is False  # type: ignore[attr-defined]
            await restarted._v2_load_kill_state()  # type: ignore[attr-defined]
            assert restarted._v2_kill_switch_halted() is True  # type: ignore[attr-defined]
            assert restarted._v2_kill_switch.reason == "DUPLICATE_EXECUTION"  # type: ignore[attr-defined]
            assert restarted._v2_kill_switch.engagement_id == engagement_id  # type: ignore[attr-defined]
    finally:
        await _cleanup(hardkill_pg_factory, account_id=account_id)


@pytest.mark.asyncio
async def test_r1_a_halt_newer_than_a_released_row_is_repersisted_against_postgres(
    hardkill_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Una fila liberada ANTERIOR al halt local no lo borra: se vuelve a persistir.

    La otra rama en la que el espejo no contiene el halt vigente. El halt local manda
    (regla ya existente), pero sólo sobrevive al reinicio si R-1 lo hace durable.
    """
    import uuid

    account_id = f"acc-r1-{uuid.uuid4().hex[:10]}"
    try:
        async with hardkill_pg_factory() as session:
            from bolsa_application.kill_switch_store import (
                KillState,
                PostgresKillSwitchStore,
            )

            # Semilla por el store REAL: una liberación anterior al halt.
            await PostgresKillSwitchStore(session).save(
                KillState(
                    account_id=account_id,
                    engine_id=_ENGINE_ID,
                    engaged=False,
                    reason=None,
                    engaged_at=None,
                    engagement_id=None,
                    reengagements=0,
                    released_at="2026-09-15T08:00:00Z",
                    release_actor="api",
                    release_reconciliation_id="recon-old",
                    updated_at="2026-09-15T08:00:00Z",
                )
            )

            store = _FaultyKillSwitchStore(PostgresKillSwitchStore(session))
            store.fail_saves = 1
            w = _faulty_worker(store, account_id=account_id)  # type: ignore[assignment]

            assert await w.engage_kill_switch_durable(  # type: ignore[attr-defined]
                "RISK_BREACH", at="2026-09-15T09:00:00Z"
            ) is True
            assert store.failed_writes == 1, "la activación posterior no llegó al espejo"
            seeded = await _durable_row(session, account_id=account_id)
            assert seeded is not None and seeded.engaged is False, (
                "la fila sigue liberada: la activación falló"
            )

            await w._v2_load_kill_state()  # type: ignore[attr-defined]
            assert w._v2_kill_switch_halted() is True  # type: ignore[attr-defined]

            row = await _durable_row(session, account_id=account_id)
            assert row is not None
            assert row.engaged is True, "el halt posterior se reintenta hacer durable"
            assert row.reason == "RISK_BREACH"
            assert _same_instant(row.engaged_at, "2026-09-15T09:00:00Z")

            # Idempotente: con la fila ya engaged, la lectura siguiente no vuelve a escribir.
            writes = store.saves
            await w._v2_load_kill_state()  # type: ignore[attr-defined]
            assert store.saves == writes, "persistir no es un latido por tick"

        # Proceso nuevo: el halt posterior sobrevive a la liberación vieja.
        async with hardkill_pg_factory() as session:
            restarted = _worker(session, account_id=account_id)  # type: ignore[assignment]
            await restarted._v2_load_kill_state()  # type: ignore[attr-defined]
            assert restarted._v2_kill_switch_halted() is True  # type: ignore[attr-defined]
            assert restarted._v2_kill_switch.reason == "RISK_BREACH"  # type: ignore[attr-defined]
    finally:
        await _cleanup(hardkill_pg_factory, account_id=account_id)


@pytest.mark.asyncio
async def test_r1_the_unreadable_placeholder_never_becomes_a_durable_row_against_postgres(
    hardkill_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Criterio de auditoría: el placeholder NUNCA se persiste.

    Con ``load`` fallando el latch local queda en ``KILL_STATE_UNREADABLE`` y no se escribe
    fila. La lectura posterior sana sin fila libera el placeholder y tampoco escribe: una
    lectura incompleta no se convierte en parada real ni en autorización para operar.
    """
    import uuid

    from bolsa_analytics.cognitive.hard_kill_switch import KILL_STATE_UNREADABLE

    account_id = f"acc-r1-{uuid.uuid4().hex[:10]}"
    try:
        async with hardkill_pg_factory() as session:
            from bolsa_application.kill_switch_store import PostgresKillSwitchStore

            store = _FaultyKillSwitchStore(PostgresKillSwitchStore(session))
            store.fail_loads = 1
            w = _faulty_worker(store, account_id=account_id)  # type: ignore[assignment]

            await w._v2_load_kill_state()  # type: ignore[attr-defined]
            assert w._v2_kill_switch_halted() is True, "no leer no autoriza a operar"  # type: ignore[attr-defined]
            assert w._v2_kill_switch.reason == KILL_STATE_UNREADABLE  # type: ignore[attr-defined]
            assert store.saves == 0, "el placeholder no se escribe"
            assert await _durable_row(session, account_id=account_id) is None

            # Aunque se intente persistir explícitamente, el placeholder no es un hecho.
            assert await w._v2_persist_kill_state() is False  # type: ignore[attr-defined]
            assert store.saves == 0
            assert await _durable_row(session, account_id=account_id) is None

            # Lectura posterior SANA y sin fila: libera el placeholder, no escribe nada.
            await w._v2_load_kill_state()  # type: ignore[attr-defined]
            assert w._v2_kill_switch_halted() is False  # type: ignore[attr-defined]
            assert store.saves == 0, "liberar el placeholder no fabrica una fila"
            assert await _durable_row(session, account_id=account_id) is None
    finally:
        await _cleanup(hardkill_pg_factory, account_id=account_id)
