"""O-2 contra PostgreSQL real: el desenlace se sella en SAVEPOINT y es durable.

El dictamen exige certificar en integración (condición 5) el rollback del sumidero de desenlaces
ante un fallo intermedio. Lo que solo se puede medir con PostgreSQL:

* un statement fallido DENTRO del SAVEPOINT no aborta la transacción del tick (sin
  ``begin_nested`` la sesión quedaría ``aborted`` y todo el turno fallaría en cascada);
* el ``UPDATE`` del desenlace se revierte **solo** en su savepoint: la propuesta sigue
  adoptable y los cambios anteriores de la misma sesión se pueden commitear;
* con éxito, el helper commitea y el desenlace es visible desde otra conexión (durable antes de
  emitir la orden).

Gate ``AUTO_PROPOSAL_OUTCOMES_PG_REQUIRED=1`` (fail-if-skipped) en ``lifecycle-pg``.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, text, update

from bolsa_application.estudio_daily_proposals import (
    RecordDailyProposalOutcomes,
    record_outcomes_in_savepoint,
)
from bolsa_infrastructure.database.models import EstudioDailyProposalRow
from bolsa_infrastructure.database.repositories.estudio_daily_proposal_repository import (
    SqlAlchemyEstudioDailyProposalRepository,
)
from tests._estudio_pg_helpers import make_pg_session_factory, require_or_skip

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

#: Gate propio (fail-if-skipped) del job ``lifecycle-pg``.
_REQUIRED_ENV = "AUTO_PROPOSAL_OUTCOMES_PG_REQUIRED"

_STATUS_PROPOSED = "proposed"


@pytest_asyncio.fixture
async def pg_factory() -> AsyncIterator[Any]:
    try:
        factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="desenlace de propuestas")
        return
    try:
        yield factory
    finally:
        await engine.dispose()


async def _insert_proposal(
    factory: Any,
    *,
    account_id: str,
    status: str = _STATUS_PROPOSED,
    day: str = "2026-11-03",
) -> str:
    proposal_id = f"test-prop-{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC)
    async with factory() as session:
        session.add(
            EstudioDailyProposalRow(
                id=proposal_id,
                account_id=account_id,
                day=day,
                instrument_id=f"inst-{proposal_id}",
                symbol="AAA",
                decision_id=None,
                signal_id=None,
                strategy_definition_id=None,
                strategy_version=None,
                preset_key="opportunity_daily",
                bar_date=day,
                plan={"decisionId": "plan-x"},
                status=status,
                consumed_cycle_id=None,
                consumed_at=None,
                reason=None,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    return proposal_id


async def _read_proposal(factory: Any, proposal_id: str) -> EstudioDailyProposalRow | None:
    async with factory() as session:
        return await session.get(EstudioDailyProposalRow, proposal_id)


async def _delete(factory: Any, *proposal_ids: str) -> None:
    async with factory() as session:
        await session.execute(
            delete(EstudioDailyProposalRow).where(
                EstudioDailyProposalRow.id.in_(proposal_ids)
            )
        )
        await session.commit()


# ── Condición 5: rollback intermedio ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_midway_failure_rolls_back_only_the_savepoint(pg_factory: Any) -> None:
    """O-2 — el ``UPDATE`` revocado a medias NO se persiste y la sesión sigue viva.

    El sumidero hace un ``UPDATE`` real de la propuesta y DESPUÉS lanza. El SAVEPOINT debe
    revertir ese cambio: la propuesta sigue ``proposed`` (adoptable), no ``consumed`` con un
    ``cycle_id`` que nunca existió.
    """
    account_id = f"acc-o2-{uuid.uuid4().hex[:10]}"
    proposal_id = await _insert_proposal(pg_factory, account_id=account_id)
    before = await _read_proposal(pg_factory, proposal_id)
    assert before is not None
    updated_before = before.updated_at
    try:
        async with pg_factory() as session:

            async def _half_written_then_boom(_outcomes: Any) -> Any:
                await session.execute(
                    update(EstudioDailyProposalRow)
                    .where(EstudioDailyProposalRow.id == proposal_id)
                    .values(status="consumed", consumed_cycle_id="cycle-phantom")
                )
                await session.flush()
                raise RuntimeError("fallo intermedio tras el UPDATE")

            result = await record_outcomes_in_savepoint(
                session, _half_written_then_boom, [{"proposalId": proposal_id}]
            )
            assert result is None

            # (a) La sesión sigue usable: el statement no la dejó abortada.
            assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
            # (b) El turno puede cerrar su transacción pese al fallo del sumidero.
            await session.commit()

        # (c) El efecto del savepoint revertido NO está en la BD.
        after = await _read_proposal(pg_factory, proposal_id)
        assert after is not None
        assert after.status == _STATUS_PROPOSED, "el UPDATE a medias no debe persistirse"
        assert after.consumed_cycle_id is None
        assert after.updated_at == updated_before
    finally:
        await _delete(pg_factory, proposal_id)


@pytest.mark.asyncio
async def test_previous_writes_of_the_turn_survive_the_sink_failure(pg_factory: Any) -> None:
    """O-2 — un fallo del sumidero no tumba las escrituras previas del turno."""
    account_id = f"acc-o2-{uuid.uuid4().hex[:10]}"
    marker = f"turn-{uuid.uuid4().hex[:10]}"
    proposal_id = await _insert_proposal(pg_factory, account_id=account_id)
    try:
        async with pg_factory() as session:
            # Escritura del turno ANTES del desenlace (misma sesión, sin commit todavía).
            await session.execute(
                update(EstudioDailyProposalRow)
                .where(EstudioDailyProposalRow.id == proposal_id)
                .values(reason=marker)
            )
            await session.flush()

            async def _boom(_outcomes: Any) -> Any:
                raise RuntimeError("SQL roto del desenlace")

            result = await record_outcomes_in_savepoint(
                session, _boom, [{"proposalId": proposal_id}]
            )
            assert result is None

            # El turno puede cerrar su transacción: el fallo quedó acotado al SAVEPOINT.
            await session.commit()

        stored = await _read_proposal(pg_factory, proposal_id)
        assert stored is not None
        assert stored.reason == marker, "la escritura previa del turno debe sobrevivir"
        assert stored.status == _STATUS_PROPOSED
    finally:
        await _delete(pg_factory, proposal_id)


# ── Condición 5: commit duradero ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_healthy_outcome_is_committed_and_visible_from_another_connection(
    pg_factory: Any,
) -> None:
    """O-2 — con ``autocommit=False`` el helper sella el desenlace y otra sesión lo ve."""
    account_id = f"acc-o2-{uuid.uuid4().hex[:10]}"
    proposal_id = await _insert_proposal(pg_factory, account_id=account_id)
    cycle_id = f"cycle-{uuid.uuid4().hex[:10]}"
    try:
        async with pg_factory() as session:
            # ``autocommit=False``: un commit DENTRO del savepoint lo cerraría en falso.
            outcomes = RecordDailyProposalOutcomes(
                SqlAlchemyEstudioDailyProposalRepository(session, autocommit=False)
            )
            result = await record_outcomes_in_savepoint(
                session,
                outcomes.execute,
                [{"proposalId": proposal_id, "status": "consumed", "cycleId": cycle_id}],
            )

        assert result is not None
        assert result["consumed"] == 1

        # Visible desde OTRA conexión: el commit fue real, no un flush.
        stored = await _read_proposal(pg_factory, proposal_id)
        assert stored is not None
        assert stored.status == "consumed"
        assert stored.consumed_cycle_id == cycle_id
        assert stored.consumed_at is not None
    finally:
        await _delete(pg_factory, proposal_id)


@pytest.mark.asyncio
async def test_a_second_outcome_on_the_same_proposal_is_not_consumed_again(
    pg_factory: Any,
) -> None:
    """O-2 — el sello es idempotente por estado: dos desenlaces no atribuyen dos ciclos."""
    account_id = f"acc-o2-{uuid.uuid4().hex[:10]}"
    proposal_id = await _insert_proposal(pg_factory, account_id=account_id)
    try:
        first_cycle = f"cycle-{uuid.uuid4().hex[:10]}"
        second_cycle = f"cycle-{uuid.uuid4().hex[:10]}"
        for cycle_id in (first_cycle, second_cycle):
            async with pg_factory() as session:
                outcomes = RecordDailyProposalOutcomes(
                    SqlAlchemyEstudioDailyProposalRepository(session, autocommit=False)
                )
                await record_outcomes_in_savepoint(
                    session,
                    outcomes.execute,
                    [
                        {
                            "proposalId": proposal_id,
                            "status": "consumed",
                            "cycleId": cycle_id,
                        }
                    ],
                )

        stored = await _read_proposal(pg_factory, proposal_id)
        assert stored is not None
        assert stored.status == "consumed"
        assert stored.consumed_cycle_id == first_cycle
    finally:
        await _delete(pg_factory, proposal_id)
