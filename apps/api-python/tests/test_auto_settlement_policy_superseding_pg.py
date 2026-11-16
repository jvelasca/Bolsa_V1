"""ADR-051 — dos hechos de settlement por ciclo: superación, no duplicado.

El contrato introduce un hecho NUEVO por ciclo (política ``applied_per_fill_v1``) sin borrar el
histórico. Cualquier lector que no distinga política vería DOS cierres del mismo ciclo y lo
declararía contradictorio. Este nodo mide que los tres lectores que podrían caer en eso ya no
lo hacen, sobre un ciclo cerrado por el camino PRODUCTIVO:

1. **Monitor.** Con solo el hecho histórico el paso ``SETTLEMENT`` no se afirma limpio: queda
   ``PARTIAL`` con ``settlement_policy_stale`` (y la nota sube al resumen del ciclo). Con los
   dos coexistiendo se lee el VIGENTE, se declara ``settlement_policy_superseded`` y **no**
   aparece ``duplicate_settlement_cycle``.
2. **Recuperación.** El lector de hechos del worker (``build_durable_fact_cycle_reader``) NO
   cuenta un histórico como «ya liquidado»: mientras solo exista el histórico, la recuperación
   reemitirá el ciclo con la política vigente. Tras el ``--apply`` el ciclo entra en el conjunto.
3. **Conciliación de la cadena.** Con solo el histórico, ``pnl_reconciliation`` declara
   ``reconciled = None`` + ``settlement_policy_stale`` — un hueco declarado, no un ``False``
   causado por comparar dos aritméticas. Con el vigente vuelve a ``reconciled = True``.

Se reutiliza el arnés y los sembradores del nodo v2.103 (mismo ciclo, mismos hechos) para que
los dos nodos midan el mismo escenario y no dos variantes parecidas.

GOBIERNO DE HONESTIDAD: sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_IDENTITY_CHAIN_PG_REQUIRED=1`` el skip es FALLO. Nunca abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import importlib.util
import pathlib
import sys
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.cycle_pnl_policy import (
    CYCLE_PNL_POLICY,
    CYCLE_PNL_POLICY_LEGACY,
)

# Arnés y sembradores: el MISMO ciclo productivo y los MISMOS hechos que el nodo de reemisión.
from tests.test_auto_identity_chain_battery_pg import (
    _IDENTITY_SOURCE,
    _drive_cycle,
    _read_evidence,
    _teardown,
    identity_pg_factory,  # noqa: F401 — fixture: se solicita por su NOMBRE
)
from tests.test_v2_103_reenvio_settlements_politica_pg import (
    _delete_facts,
    _facts,
    _insert_historical_fact,
    _run_cli,
)

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_CLI = (
    pathlib.Path(__file__).resolve().parents[1]
    / "scripts"
    / "v2_103_reenvio_settlements_politica.py"
)


def _load_cli() -> Any:
    name = "v2_103_reenvio_settlements_politica_superseding"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


async def _cycle_pnls(
    factory: async_sessionmaker[AsyncSession], *, account_id: str, cycle_id: str
) -> tuple[Decimal, Decimal]:
    """``(pnl aplicado, pnl exacto)`` del ciclo, del MISMO productor que el producto."""
    from bolsa_application.auto_self_evaluation_feed import cycles_from_fills

    cli = _load_cli()
    async with factory() as session:
        fills = await cli._load_cycle_fills(session, account_id=account_id, cycle_id=cycle_id)
    cycle = next(row for row in cycles_from_fills(fills) if str(row.get("cycleId")) == cycle_id)
    return Decimal(str(cycle["pnl"])), Decimal(str(cycle["pnlExact"]))


async def _monitor_cycle(
    factory: async_sessionmaker[AsyncSession], *, account_id: str, engine_id: str, cycle_id: str
) -> dict[str, Any]:
    """Ciclo del monitor (drill-down a UN ciclo: la lectura no depende de la ventana)."""
    from bolsa_application.auto_operational_monitor import read_operational_monitor

    async with factory() as session:
        monitor = await read_operational_monitor(
            session, account_id, engine_id=engine_id, cycle_id=cycle_id
        )
    cycles = [row for row in monitor.get("cycles") or [] if row.get("cycleId") == cycle_id]
    assert len(cycles) == 1, f"el drill-down debe devolver UN ciclo: {monitor.get('cycles')}"
    return cycles[0]


def _settlement_step(cycle: dict[str, Any]) -> dict[str, Any]:
    steps = [step for step in cycle.get("steps") or [] if step.get("id") == "SETTLEMENT"]
    assert len(steps) == 1, f"el ciclo debe declarar UN paso SETTLEMENT: {cycle.get('steps')}"
    return steps[0]


def _fact_value(step: dict[str, Any], key: str) -> Any:
    for fact in step.get("facts") or []:
        if fact.get("key") == key:
            return fact.get("value")
    return None


async def _chain_pnl(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    engine_id: str,
    instrument_id: str,
) -> dict[str, Any]:
    """Bloque ``pnl`` del ciclo en la evidencia de la cadena (mismo lector que el producto)."""
    artifact = await _read_evidence(
        factory,
        account_id=account_id,
        engine_id=engine_id,
        study_instruments=[instrument_id],
    )
    value = next(row for row in artifact["values"] if row["instrumentId"] == instrument_id)
    cycles = value["cycles"]
    assert len(cycles) == 1, f"se esperaba UN ciclo del valor: {cycles}"
    return cycles[0]["pnl"]


async def _recovery_reader(
    factory: async_sessionmaker[AsyncSession], *, account_id: str, engine_id: str
) -> frozenset[str]:
    """El MISMO lector que usa la recuperación del worker (no una copia del criterio)."""
    from bolsa_api.background.auto_worker_runtime import build_durable_fact_cycle_reader

    async with factory() as session:
        reader = build_durable_fact_cycle_reader(
            session, account_id=account_id, engine_id=engine_id
        )
        return await reader("auto_cycle_settlement")


@pytest.mark.asyncio
async def test_monitor_reads_the_current_policy_and_calls_it_superseding_pg(
    identity_pg_factory: async_sessionmaker[AsyncSession],  # noqa: F811 — fixture del arnés
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Histórico + vigente conviviendo: manda el vigente y NO es ``duplicate_settlement_cycle``."""
    state = await _drive_cycle(
        identity_pg_factory, monkeypatch, source=_IDENTITY_SOURCE, prefix="inst-pol-"
    )
    try:
        account_id = state["accountId"]
        engine_id = state["engineId"]
        cycle_id = state["cycleId"]
        current = await _facts(identity_pg_factory, account_id=account_id, cycle_id=cycle_id)
        assert len(current) == 1
        applied_pnl, exact_pnl = await _cycle_pnls(
            identity_pg_factory, account_id=account_id, cycle_id=cycle_id
        )

        # El histórico se AÑADE (append-only) con el PnL exacto del FIFO: los dos coexisten.
        await _insert_historical_fact(
            identity_pg_factory,
            account_id=account_id,
            engine_id=engine_id,
            cycle_id=cycle_id,
            payload=current[0]["payload"],
            pnl_exact=exact_pnl,
        )
        both = await _facts(identity_pg_factory, account_id=account_id, cycle_id=cycle_id)
        assert len(both) == 2, both

        cycle_view = await _monitor_cycle(
            identity_pg_factory, account_id=account_id, engine_id=engine_id, cycle_id=cycle_id
        )
        step = _settlement_step(cycle_view)
        assert step["state"] == "reached", step
        assert step["measurement"] == "COMPLETE", step
        assert step["note"] is None, step
        # Se publica el PnL del hecho VIGENTE, no el del histórico.
        assert Decimal(str(_fact_value(step, "pnl"))) == applied_pnl, step
        assert _fact_value(step, "pnlPolicy") == CYCLE_PNL_POLICY, step
        assert "settlement_policy_superseded" in cycle_view["notes"], cycle_view["notes"]
        assert "duplicate_settlement_cycle" not in cycle_view["notes"], cycle_view["notes"]
        assert "settlement_policy_stale" not in cycle_view["notes"], cycle_view["notes"]

        # La conciliación compara contra el vigente: la coexistencia no la degrada.
        pnl = await _chain_pnl(
            identity_pg_factory,
            account_id=account_id,
            engine_id=engine_id,
            instrument_id=state["instrumentId"],
        )
        assert pnl["reconciled"] is True, pnl
        assert pnl["settlementPolicy"] == CYCLE_PNL_POLICY, pnl
        assert pnl["superseded"] is True, pnl
        assert pnl["policy"] == CYCLE_PNL_POLICY, pnl
        assert Decimal(str(pnl["cycleClosedPnl"])) == applied_pnl, pnl
        assert Decimal(str(pnl["cycleExactPnl"])) == exact_pnl, pnl

        # Y el ciclo sigue contando como liquidado para la recuperación.
        settled = await _recovery_reader(
            identity_pg_factory, account_id=account_id, engine_id=engine_id
        )
        assert cycle_id in settled, sorted(settled)
    finally:
        await _teardown(identity_pg_factory, state)


@pytest.mark.asyncio
async def test_the_historical_fact_alone_is_stale_for_readers_and_reemitible_pg(
    identity_pg_factory: async_sessionmaker[AsyncSession],  # noqa: F811 — fixture del arnés
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Solo el histórico: ``stale`` en monitor y cadena, y el worker lo dará por NO liquidado."""
    state = await _drive_cycle(
        identity_pg_factory, monkeypatch, source=_IDENTITY_SOURCE, prefix="inst-polb-"
    )
    try:
        account_id = state["accountId"]
        engine_id = state["engineId"]
        cycle_id = state["cycleId"]
        facts = await _facts(identity_pg_factory, account_id=account_id, cycle_id=cycle_id)
        assert len(facts) == 1
        applied_pnl, exact_pnl = await _cycle_pnls(
            identity_pg_factory, account_id=account_id, cycle_id=cycle_id
        )

        # Se deja SOLO el hecho histórico, con la cifra que el contrato anterior publicaba.
        await _delete_facts(identity_pg_factory, account_id=account_id, cycle_id=cycle_id)
        await _insert_historical_fact(
            identity_pg_factory,
            account_id=account_id,
            engine_id=engine_id,
            cycle_id=cycle_id,
            payload=facts[0]["payload"],
            pnl_exact=exact_pnl,
        )

        # (1) Monitor: el hecho existe pero NO se afirma limpio.
        cycle_view = await _monitor_cycle(
            identity_pg_factory, account_id=account_id, engine_id=engine_id, cycle_id=cycle_id
        )
        step = _settlement_step(cycle_view)
        assert step["state"] == "reached", step
        assert step["measurement"] == "PARTIAL", step
        assert step["note"] == "settlement_policy_stale", step
        assert "settlement_policy_stale" in cycle_view["notes"], cycle_view["notes"]
        assert "duplicate_settlement_cycle" not in cycle_view["notes"], cycle_view["notes"]
        assert "settlement_policy_superseded" not in cycle_view["notes"], cycle_view["notes"]

        # (2) Cadena: hueco DECLARADO, no un False por comparar dos aritméticas.
        pnl = await _chain_pnl(
            identity_pg_factory,
            account_id=account_id,
            engine_id=engine_id,
            instrument_id=state["instrumentId"],
        )
        assert pnl["reconciled"] is None, pnl
        assert pnl["measurement"] == "UNKNOWN", pnl
        assert "settlement_policy_stale" in pnl["notes"], pnl
        assert pnl["settlementPolicy"] is None, pnl
        assert pnl["policy"] == CYCLE_PNL_POLICY, pnl
        assert pnl["superseded"] is False, pnl

        # (3) Recuperación: el histórico NO cuenta como liquidado ⇒ el worker reemitirá.
        settled = await _recovery_reader(
            identity_pg_factory, account_id=account_id, engine_id=engine_id
        )
        assert cycle_id not in settled, sorted(settled)

        # (4) Tras la reemisión el ciclo entra en el conjunto y la conciliación vuelve a True.
        applied = await _run_cli(account_id, apply=True, cycle_id=cycle_id)
        assert applied["applied"]["inserted"] == 1, applied["applied"]
        settled = await _recovery_reader(
            identity_pg_factory, account_id=account_id, engine_id=engine_id
        )
        assert cycle_id in settled, sorted(settled)
        pnl = await _chain_pnl(
            identity_pg_factory,
            account_id=account_id,
            engine_id=engine_id,
            instrument_id=state["instrumentId"],
        )
        assert pnl["reconciled"] is True, pnl
        assert pnl["settlementPolicy"] == CYCLE_PNL_POLICY, pnl
        assert pnl["superseded"] is True, pnl
        assert "settlement_policy_stale" not in pnl["notes"], pnl

        # El PnL publicado por la cadena es el del libro aplicado; el exacto viaja aparte.
        assert Decimal(str(pnl["cycleClosedPnl"])) == applied_pnl, pnl
        assert Decimal(str(pnl["cycleExactPnl"])) == exact_pnl, pnl
        assert pnl["settlementPnl"] is not None, pnl
        assert Decimal(str(pnl["settlementPnl"])) == applied_pnl, pnl
        # El histórico sigue en el spine con su política declarada (nadie lo reescribió).
        after = await _facts(identity_pg_factory, account_id=account_id, cycle_id=cycle_id)
        assert len(after) == 2, after
        historical = [fact for fact in after if "pnlPolicy" not in fact["payload"]]
        assert len(historical) == 1, after
        assert Decimal(str(historical[0]["payload"]["pnl"])) == exact_pnl, historical[0]
        assert CYCLE_PNL_POLICY_LEGACY == "fifo_exact_v0"  # nombre declarado del histórico
    finally:
        await _teardown(identity_pg_factory, state)
