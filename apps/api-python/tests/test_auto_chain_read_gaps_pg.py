"""C-1 contra PostgreSQL real: el hueco de LECTURA se declara y no aborta la sesión.

El dictamen exige certificar en integración (condición 1 y 6):

* un fallo de lectura de propuestas **dentro de un SAVEPOINT** no aborta la transacción de la
  sesión compartida del tick: las lecturas siguientes (DÍA-D) y un ``commit`` posterior siguen
  funcionando;
* ``readGaps`` llega al artefacto publicado;
* un ciclo sin enlaces legibles declara ``unmeasured``/``proposals_unreadable`` y **nunca**
  ``not_proposed``, mientras que un veredicto ya sellado por el journal (``exact``) **no** se
  degrada.

Cómo se fuerza un fallo REAL de PostgreSQL sin tocar el esquema: se crea un esquema señuelo con
una tabla homónima de columnas incompatibles y se antepone en ``search_path``. La consulta no
encuentra las columnas y PostgreSQL aborta el statement, que es exactamente lo que el SAVEPOINT
tiene que aislar. Es reversible (``DROP SCHEMA ... CASCADE``) y no depende de mocks.

Gate ``AUTO_CHAIN_READ_GAPS_PG_REQUIRED=1`` (fail-if-skipped) en ``lifecycle-pg``.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text

from bolsa_application.auto_chain_durable_reader import (
    DAILY_PROPOSALS_UNREADABLE,
    DIA_D_UNREADABLE,
    build_chain_evidence_artifact,
    read_daily_proposals,
    read_dia_d_verifications,
    read_estudio_chain_evidence,
    resolve_cycle_attribution,
)
from bolsa_application.estudio_daily_proposals import (
    ADOPTION_ABSENT_NOT_PROPOSED,
    ADOPTION_ABSENT_UNMEASURED,
    ADOPTION_EXACT,
)
from tests._estudio_pg_helpers import make_pg_session_factory, require_or_skip

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

#: Gate propio (fail-if-skipped) del job ``lifecycle-pg``.
_REQUIRED_ENV = "AUTO_CHAIN_READ_GAPS_PG_REQUIRED"

#: Columnas mínimas del señuelo: el nombre de tabla es el correcto y NINGUNA columna coincide,
#: así el statement falla con ``UndefinedColumn`` (un error real de PostgreSQL, no un mock).
_DECOY_COLUMN = "decoy_only_column"


@pytest_asyncio.fixture
async def pg_factory() -> AsyncIterator[Any]:
    try:
        factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="huecos de lectura de la cadena")
        return
    try:
        yield factory
    finally:
        await engine.dispose()


def _decoy_schema(table: str) -> str:
    """Nombre único de esquema señuelo (aislamiento entre ejecuciones y entre tests)."""
    return f"decoy_{table}_{uuid.uuid4().hex[:10]}"


async def _install_decoy(factory: Any, table: str) -> str:
    """Crea ``schema."<table>"`` con una sola columna incompatible y lo antepone al path."""
    schema = _decoy_schema(table)
    async with factory() as session:
        await session.execute(text(f'CREATE SCHEMA "{schema}"'))
        await session.execute(
            text(f'CREATE TABLE "{schema}".{table} ({_DECOY_COLUMN} integer)')
        )
        await session.commit()
    return schema


async def _use_search_path(session: Any, *schemas: str) -> None:
    quoted = ", ".join(f'"{schema}"' for schema in schemas)
    await session.execute(text(f"SET search_path = {quoted}"))


async def _drop_decoy(factory: Any, schema: str) -> None:
    async with factory() as session:
        await session.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await session.commit()


# ── Condición 1: SAVEPOINT aísla el fallo y la sesión sigue viva ───────────────


@pytest.mark.asyncio
async def test_unreadable_proposals_do_not_abort_the_shared_session(pg_factory: Any) -> None:
    """C-1 — el fallo de lectura queda en el SAVEPOINT: la sesión sigue usable y commiteable.

    Sin ``begin_nested``, PostgreSQL deja la transacción en estado ``aborted``: el ``SELECT``
    siguiente fallaría con ``InFailedSqlTransaction`` y el ``INSERT`` de prueba no se
    persistiría. Este es el daño en cascada que el dictamen pide certificar que no ocurre.
    """
    schema = await _install_decoy(pg_factory, "estudio_daily_proposals")
    account_id = f"acc-readgaps-{uuid.uuid4().hex[:10]}"
    marker = f"probe-{uuid.uuid4().hex[:10]}"
    table = f"{schema}.commit_probe"
    try:
        async with pg_factory() as session:
            await _use_search_path(session, schema, "public")
            # Tabla propia del señuelo: la escritura posterior prueba que el COMMIT es real.
            await session.execute(text(f"CREATE TABLE {table} (marker text)"))
            await session.commit()

            read = await read_daily_proposals(session, account_id)
            assert read.read is False
            assert read.rows == ()
            assert read.reason == DAILY_PROPOSALS_UNREADABLE

            # (a) La MISMA sesión sigue consultando: el SAVEPOINT acotó el daño.
            alive = (await session.execute(text("SELECT 1"))).scalar_one()
            assert alive == 1

            # (b) La siguiente lectura de la cadena en la misma sesión también funciona.
            dia_d = await read_dia_d_verifications(session, account_id)
            assert dia_d.read is True
            assert dia_d.by_cycle == {}

            # (c) Una escritura posterior se COMMITEA: la transacción no quedó abortada.
            await session.execute(
                text(f"INSERT INTO {table} (marker) VALUES (:marker)"), {"marker": marker}
            )
            await session.commit()

        # El commit fue real y visible desde otra conexión.
        async with pg_factory() as session:
            stored = (
                await session.execute(text(f"SELECT marker FROM {table}"))
            ).scalars().all()
        assert stored == [marker]
    finally:
        await _drop_decoy(pg_factory, schema)


@pytest.mark.asyncio
async def test_unreadable_dia_d_does_not_empty_the_proposals_link(pg_factory: Any) -> None:
    """C-1 — cada etapa tiene su propio SAVEPOINT: un fallo DÍA-D no vacía las propuestas."""
    schema = await _install_decoy(pg_factory, "dia_d_cycle_verifications")
    account_id = f"acc-readgaps-{uuid.uuid4().hex[:10]}"
    try:
        async with pg_factory() as session:
            await _use_search_path(session, schema, "public")

            dia_d = await read_dia_d_verifications(session, account_id)
            assert dia_d.read is False
            assert dia_d.reason == DIA_D_UNREADABLE

            # La lectura de propuestas de la MISMA sesión sigue midiendo de verdad.
            proposals = await read_daily_proposals(session, account_id)
            assert proposals.read is True
            assert proposals.rows == ()

            await session.commit()
    finally:
        await _drop_decoy(pg_factory, schema)


# ── Condición 6: readGaps publicado y atribución declarada ─────────────────────


@pytest.mark.asyncio
async def test_read_gaps_are_published_and_empty_when_every_stage_is_measured(
    pg_factory: Any,
) -> None:
    """C-1 — ``readGaps`` viaja del lector al artefacto; con todo medido, sin motivos."""
    account_id = f"acc-readgaps-{uuid.uuid4().hex[:10]}"
    async with pg_factory() as session:
        read = await read_estudio_chain_evidence(session, account_id)
    assert read["readGaps"] == {"dailyProposals": None, "diaD": None}

    artifact = build_chain_evidence_artifact(
        account_id=account_id,
        estudio={"status": "ok", "instrumentIds": []},
        cycles=read["cycles"],
        best_scored=read["bestScored"],
        best_scored_by_cycle=read.get("bestScoredByCycle"),
        read_gaps=read.get("readGaps"),
    )
    assert artifact["readGaps"] == {"dailyProposals": None, "diaD": None}


@pytest.mark.asyncio
async def test_read_gap_reaches_the_artifact_and_marks_the_attribution_unmeasured(
    pg_factory: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C-1 — con la lectura de propuestas caída, el artefacto lo declara y el ciclo no miente.

    La composición real (``read_estudio_chain_evidence`` → artefacto) se prueba inyectando el
    resultado tipado del lector: es el contrato que la ruta consume. El camino SQL real del
    fallo ya se certifica arriba con el esquema señuelo.
    """
    from bolsa_application import auto_chain_durable_reader as reader

    account_id = f"acc-readgaps-{uuid.uuid4().hex[:10]}"
    unreadable = reader.DailyProposalsRead(
        rows=(), read=False, reason=DAILY_PROPOSALS_UNREADABLE
    )

    async def _unreadable(*_args: Any, **_kwargs: Any) -> Any:
        return unreadable

    monkeypatch.setattr(reader, "read_daily_proposals", _unreadable)
    # Un ciclo durable sin propuestas enlazadas: el caso que antes se publicaba como
    # ``not_proposed`` («no nació de una propuesta») siendo en realidad «no se pudo leer».
    cycle = {
        "cycleId": "cyc-readgap",
        "instrumentId": "inst-readgap",
        "attribution": None,
    }

    enriched = dict(cycle)
    enriched["attribution"] = resolve_cycle_attribution(
        cycle, [], proposals_read=unreadable.read
    )
    assert enriched["attribution"]["state"] == ADOPTION_ABSENT_UNMEASURED
    assert enriched["attribution"]["reason"] == DAILY_PROPOSALS_UNREADABLE
    assert enriched["attribution"]["state"] != ADOPTION_ABSENT_NOT_PROPOSED

    artifact = build_chain_evidence_artifact(
        account_id=account_id,
        estudio={"status": "ok", "instrumentIds": ["inst-readgap"]},
        cycles=[enriched],
        read_gaps={"dailyProposals": DAILY_PROPOSALS_UNREADABLE, "diaD": None},
    )
    assert artifact["readGaps"]["dailyProposals"] == DAILY_PROPOSALS_UNREADABLE
    assert artifact["readGaps"]["diaD"] is None
    published = artifact["values"][0]["cycles"][0]["attribution"]
    assert published["state"] == ADOPTION_ABSENT_UNMEASURED
    assert published["reason"] == DAILY_PROPOSALS_UNREADABLE


@pytest.mark.asyncio
async def test_a_durable_journal_verdict_is_not_degraded_by_a_read_failure(
    pg_factory: Any,
) -> None:
    """C-1 — el veredicto del journal es un hecho DURABLE: no se degrada por no leer.

    El dictamen lo exige explícitamente: mantener ``exact`` en el journal y declarar
    ``unmeasured`` en la atribución cuando no se pueden leer las propuestas es coherente
    **siempre que ambos estados permanezcan separados**. Aquí se comprueba que no se pisan.
    """
    account_id = f"acc-readgaps-{uuid.uuid4().hex[:10]}"
    schema = await _install_decoy(pg_factory, "estudio_daily_proposals")
    try:
        cycle = {
            "cycleId": "cyc-readgap-journal",
            "planId": "plan-1",
            "signalId": "sig-1",
            "attribution": {
                "state": ADOPTION_EXACT,
                "reason": None,
                "measurement": "COMPLETE",
                "proposalId": "prop-1",
                "source": "journal",
            },
        }
        async with pg_factory() as session:
            await _use_search_path(session, schema, "public")
            read = await read_daily_proposals(session, account_id)
            assert read.read is False

        attribution = resolve_cycle_attribution(
            cycle, [], proposals_read=read.read
        )
        # El veredicto del journal manda y NO se convierte en ``unmeasured``.
        assert attribution["state"] == ADOPTION_EXACT
        assert attribution["source"] == "journal"

        # Y el hueco de lectura queda declarado aparte, en su propio canal.
        artifact = build_chain_evidence_artifact(
            account_id=account_id,
            estudio={"status": "ok", "instrumentIds": ["inst-readgap"]},
            cycles=[{**cycle, "instrumentId": "inst-readgap", "attribution": attribution}],
            read_gaps={"dailyProposals": read.reason, "diaD": None},
        )
        assert artifact["readGaps"]["dailyProposals"] == DAILY_PROPOSALS_UNREADABLE
        published = artifact["values"][0]["cycles"][0]["attribution"]
        assert published["state"] == ADOPTION_EXACT
    finally:
        await _drop_decoy(pg_factory, schema)


@pytest.mark.asyncio
async def test_a_measured_absence_is_still_not_proposed(pg_factory: Any) -> None:
    """C-1 — control negativo: si la lectura SÍ se hizo, la ausencia es ``not_proposed``."""
    account_id = f"acc-readgaps-{uuid.uuid4().hex[:10]}"
    async with pg_factory() as session:
        read = await read_daily_proposals(session, account_id)
    assert read.read is True

    attribution = resolve_cycle_attribution(
        {"cycleId": "cyc-measured"}, [], proposals_read=read.read
    )
    assert attribution["state"] == ADOPTION_ABSENT_NOT_PROPOSED
    assert attribution["reason"] == "no_daily_proposal"
