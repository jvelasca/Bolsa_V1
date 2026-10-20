"""Batería integrada POR VALOR — identidad ganadora → señal → plan → ciclo SIM → DÍA-D → P&L.

Certifica, sobre PostgreSQL real y por el camino PRODUCTIVO (``AutoSimRuntime.run_tick``,
no una siembra a mano), el eslabón que ningún arnés cubría de punta a punta:

* **Identidad GANADORA** — la foto durable ``top3_opportunities`` (migración 057) declara el
  ``strategyPresetKey``/``strategyVersion`` del candidato que ganó el ranking cross-asset.
* **Identidad EJECUTADA** — la decisión durable ``auto_entry_decision`` sella la MISMA
  identidad, que llegó desde ``DecisionPackage.source = active-strategy:<v>::<preset>``.
* **Señal y plan** — el ciclo nace de una señal con ``signalId`` y de un ``TradePlan`` cuyo
  ``decisionId`` se deriva del ``cycleId`` (misma clave acuñada).
* **Ciclo SIM** — reserva, orden, fill, protección, liquidación y cierre con las NUEVE
  etapas encendidas desde hechos durables.
* **DÍA-D** — la verificación durable se enlaza al ciclo copiando SU identidad (nunca
  inventada) y el contraste independiente coincide.
* **Resultado conciliado** — ``CYCLE_CLOSED.pnl`` ↔ ``SETTLEMENT.pnl`` al quantum del dinero
  (``NUMERIC(18,6)``) y la suma de los ciclos cuadra EXACTA con el libro aplicado.

Y fija el TRI-ESTADO de la medición de identidad (v2.88.153) con un control NEGATIVO: una
señal sin ``preset`` (``source = auto-2.0:<v>``) deja ``PARTIAL``, no ``COMPLETE``, y el
contraste ``presetMatch`` es un hueco declarado (``None``), no un ``False`` inventado.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_IDENTITY_CHAIN_PG_REQUIRED=1`` un skip es FALLO DURO. NUNCA abre el bridge LIVE
(venue ``simulated``). Un hueco viaja ``None``; jamás un ``0``/``False`` de relleno.

LÍMITE DECLARADO (este arnés NO lo cierra, y no debe fingir que lo hace): el parte diario
de ESTUDIO construye sus hits con identidad CONSTANTE (``presetKey="estudio_auto"``,
``strategyVersion=1``) y el ``TradePlan`` no publica ``signalId``/``planId`` en el DTO del
ciclo. La atribución señal↔ciclo se demuestra aquí por ``signalId``/``decisionId`` del
hecho durable, no por el contrato del parte. Ver
``docs/engineering/bateria-integrada-por-valor-2026-10-20.md``.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Arnés determinista reutilizado (mismo día, mismos helpers: NO se duplica el motor).
from tests._estudio_pg_helpers import cleanup_instrument, restore_estudio, set_estudio
from tests.test_golden_day_v2_process_pg import (
    _CANONICAL_STEPS,
    _expire_holding_deadlines,
    _filling_instrument_id,
    _seed_account,
    _seed_edge_report,
    _seed_instrument,
)

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
#: Gate propio (fail-if-skipped) del job ``lifecycle-pg``.
_REQUIRED_ENV = "AUTO_IDENTITY_CHAIN_PG_REQUIRED"

#: Identidad EXACTA que la fuente productiva declara (H1, separador de DOS caracteres).
_IDENTITY_VERSION = "v1"
_IDENTITY_PRESET = "sma_crossover"
_IDENTITY_SOURCE = f"active-strategy:{_IDENTITY_VERSION}::{_IDENTITY_PRESET}"
#: Control NEGATIVO: fuente con versión pero SIN sufijo de preset ⇒ identidad a medias.
_NO_PRESET_SOURCE = f"auto-2.0:{_IDENTITY_VERSION}"

#: Quantum del DINERO (``NUMERIC(18, 6)`` en el ledger).
_MONEY = Decimal("0.000001")

#: Presupuesto de ticks: abrir en la cola noisy puede requerir reintentos intra-barra.
_MAX_TICKS = 12


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la batería de identidad por valor pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (batería de identidad por valor) no disponible: {exc}")


@pytest_asyncio.fixture
async def identity_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    if _DOTENV.exists():
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


# ── Decider con FUENTE versionada (la identidad real del camino productivo) ──────────


class _SourcedSpine:
    """Spine determinista que declara la identidad EXACTA en ``DecisionPackage.source``.

    El worker NORMALIZA esa fuente (``_strategy_version_from_source`` /
    ``_strategy_preset_from_source``): no se inyecta identidad en el journal ni en la
    reserva, se deja que el camino real la selle. Ese es el punto del arnés.
    """

    def __init__(self, symbol: str, source: str, lot: float = 100.0) -> None:
        self._symbol = symbol
        self._source = source
        self._lot = lot

    def __call__(self, symbol: str) -> Any:
        from bolsa_application.decision_contract import DecisionPackage

        if symbol != self._symbol:
            return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)
        return DecisionPackage(
            action="BUY",
            instrument_id=self._symbol,
            quantity=self._lot,
            source=self._source,
        )


# ── Lectura de evidencia (mismo lector que la ruta HTTP, sin segunda verdad) ─────────


async def _read_evidence(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    engine_id: str,
    study_instruments: list[str],
) -> dict[str, Any]:
    from bolsa_application.auto_chain_durable_reader import (
        build_chain_evidence_artifact,
        read_estudio_chain_evidence,
    )

    async with factory() as session:
        read = await read_estudio_chain_evidence(session, account_id, engine_id=engine_id)
    return build_chain_evidence_artifact(
        account_id=account_id,
        estudio={"status": "ok", "instrumentIds": list(study_instruments)},
        cycles=read["cycles"],
        best_scored=read["bestScored"],
    )


async def _gross_notional(factory: async_sessionmaker[AsyncSession], account_id: str) -> Decimal:
    from bolsa_infrastructure.database.models.tables import SimFillFinanceContextRow

    async with factory() as session:
        rows = (
            await session.execute(
                select(
                    SimFillFinanceContextRow.quantity,
                    SimFillFinanceContextRow.price,
                ).where(SimFillFinanceContextRow.account_id == account_id)
            )
        ).all()
    gross = Decimal("0")
    for quantity, price in rows:
        if quantity is None or price is None:
            continue
        gross += abs(Decimal(str(quantity)) * Decimal(str(price)))
    return gross


def _to_money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(_MONEY, rounding=ROUND_HALF_UP)


async def _only_cycle(artifact: dict[str, Any], instrument_id: str) -> dict[str, Any]:
    """El ÚNICO ciclo del valor sembrado (un watch de un símbolo ⇒ una entrada)."""
    values = {value["instrumentId"]: value for value in artifact["values"]}
    assert instrument_id in values, f"la evidencia debe cubrir el valor de ESTUDIO: {values.keys()}"
    value = values[instrument_id]
    assert value["measured"] is True, f"el valor no declara ciclo medido: {value}"
    assert len(value["cycles"]) == 1, f"se esperaba UN ciclo por valor, hay {value['cycles']}"
    return value["cycles"][0]


# ── El día: abre por la ruta real y cierra por salida determinista ───────────────────


async def _drive_cycle(
    factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    *,
    source: str,
    prefix: str,
) -> dict[str, Any]:
    """Siembra, abre y cierra un ciclo por el camino PRODUCTIVO; devuelve el estado VIVO.

    NO limpia: el ciclo y su evidencia se leen DESPUÉS (con el ``finally`` del test
    llamando a ``_teardown``). Borrar aquí las reservas y la foto TOP3 destruiría
    justamente los hechos que la batería certifica.

    El cierre es una SALIDA determinista (``SELL`` de la cantidad viva tras reinicio), el
    seam que ya usa ``test_auto_scheduler_real_pg_zero_human_intervention``: no toca
    producción y deja los mismos hechos durables que un ``time_exit``.
    """
    from bolsa_api.background.auto_simulation_worker import (
        AutoSimRuntime,
        AutoSimulationWorker,
    )

    instrument_id = _filling_instrument_id(prefix)
    engine_id = f"auto-idch-{uuid.uuid4().hex[:10]}"
    symbol = f"IDC{uuid.uuid4().hex[:6].upper()}"
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "simulated")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", instrument_id)
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")
    # Sin el sink de auditoría las etapas SIGNAL/TOP_N/ORDER/SETTLEMENT quedan ``unknown``:
    # la cadena se puede medir sólo porque se enciende EXPLÍCITAMENTE.
    monkeypatch.setenv("AUTO_OPERATIONAL_AUDIT", "1")

    account_id: str | None = None
    edge_report_id: str | None = None
    originals: list[str] | None = None
    state: dict[str, Any] = {
        "instrumentId": instrument_id,
        "symbol": symbol,
        "engineId": engine_id,
        "accountId": None,
        "edgeReportId": None,
        "estudioOriginals": None,
        "cycleId": None,
    }
    try:
        account_id = await _seed_account(factory)
        state["accountId"] = account_id
        await _seed_instrument(
            factory, instrument_id=instrument_id, symbol=symbol, sector="Technology"
        )
        edge_report_id = await _seed_edge_report(
            factory, account_id=account_id, strategy_ref=_IDENTITY_VERSION
        )
        state["edgeReportId"] = edge_report_id
        originals = await set_estudio(factory, [instrument_id])
        state["estudioOriginals"] = originals

        spine = _SourcedSpine(instrument_id, source)
        worker = AutoSimulationWorker(
            decider=spine, engine_id=engine_id, account_id=account_id
        )
        runtime = AutoSimRuntime(
            factory, worker=worker, engine_id=engine_id, account_id=account_id
        )

        # 1) APERTURA — el BUY recorre señal → ranking → reserva → orden → fill → protección.
        for _ in range(_MAX_TICKS):
            await runtime.run_tick()
            if worker._open.get(instrument_id, Decimal("0")) > 0:  # noqa: SLF001 — seam del arnés.
                break
        assert worker._open.get(instrument_id, Decimal("0")) > 0, (
            "la ruta productiva debe abrir la posición sobre el valor de ESTUDIO"
        )
        state["cycleId"] = await _single_open_cycle_id(factory, account_id)

        # 2) REINICIO EN CALIENTE — readopta la posición durable y NO apila un segundo BUY.
        worker2 = AutoSimulationWorker(
            decider=spine, engine_id=engine_id, account_id=account_id
        )
        runtime2 = AutoSimRuntime(
            factory, worker=worker2, engine_id=engine_id, account_id=account_id
        )
        report_restart = await runtime2.run_tick()
        assert worker2._open.get(instrument_id, Decimal("0")) > 0, (  # noqa: SLF001
            "el worker nuevo debe readoptar la posición durable"
        )
        assert report_restart is not None and report_restart.opened == 0, (
            f"un reinicio NO puede re-abrir la misma oportunidad: {report_restart}"
        )

        # 3) TECHO DE MANTENIMIENTO — se lleva el ``holdingDeadlineAt`` durable al pasado
        #    (seam E1 del Golden Day). Es la forma REAL de disparar el ``time_exit`` que en
        #    un día natural ocurriría al vencer el horizonte: no se toca producción.
        expired = await _expire_holding_deadlines(factory, account_id)
        assert expired >= 1, "el ciclo abierto debe declarar su techo durable de mantenimiento"

        # 4) CIERRE — un worker NUEVO rehidrata el plan ya vencido y lo liquida.
        worker3 = AutoSimulationWorker(
            decider=spine, engine_id=engine_id, account_id=account_id
        )
        runtime3 = AutoSimRuntime(
            factory, worker=worker3, engine_id=engine_id, account_id=account_id
        )
        closed = False
        for _ in range(_MAX_TICKS):
            report = await runtime3.run_tick()
            if report is not None and report.closed == 1:
                closed = True
                break
        assert closed, "el vencimiento del techo debe cerrar el ciclo (settlement durable)"
        assert worker3._open.get(instrument_id, Decimal("0")) == 0, (  # noqa: SLF001
            "tras la salida el libro debe quedar plano"
        )
        return state
    except BaseException:
        await _teardown(factory, state)
        raise


async def _teardown(factory: async_sessionmaker[AsyncSession], state: dict[str, Any]) -> None:
    """Cero residuo, simétrico a la siembra (siempre se invoca desde el ``finally``)."""
    account_id = state.get("accountId")
    if account_id:
        await _cleanup(factory, account_id=account_id, edge_report_id=state.get("edgeReportId"))
    originals = state.get("estudioOriginals")
    if originals is not None:
        await restore_estudio(factory, originals)
    instrument_id = state.get("instrumentId")
    if instrument_id:
        await cleanup_instrument(factory, instrument_id)


async def _single_open_cycle_id(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> str:
    """``cycleId`` de la reserva durable del ciclo abierto (fuente: la reserva, no el journal)."""
    from bolsa_infrastructure.database.models.tables import PortfolioReservationRow

    async with factory() as session:
        rows = (
            await session.execute(
                select(PortfolioReservationRow.cycle_id).where(
                    PortfolioReservationRow.account_id == account_id,
                    PortfolioReservationRow.cycle_id.is_not(None),
                )
            )
        ).scalars().all()
    cycles = list(dict.fromkeys(str(row) for row in rows if row))
    assert len(cycles) == 1, f"se esperaba UN ciclo para la cuenta, hay {cycles}"
    return cycles[0]


async def _cleanup(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    edge_report_id: str | None,
) -> None:
    """Cero residuo: las filas AUTO por cuenta y la foto TOP3 por ``run_id``.

    La cadena de ESTUDIO no borraba ``portfolio_reservations`` ni ``top3_opportunities`` y
    dejó antecedente de reservas huérfanas; aquí se limpian EXPLÍCITAMENTE.
    """
    from bolsa_infrastructure.database.models.tables import (
        DecisionJournalEntryRow,
        DiaDCycleVerificationRow,
        EdgeReportRow,
        ExecutionEventRow,
        PortfolioReservationRow,
        SimAutoPositionRow,
        SimConsumedSignalRow,
        SimFillFinanceContextRow,
        Top3OpportunityRow,
    )
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    async with factory() as session:
        for model in (
            DiaDCycleVerificationRow,
            SimAutoPositionRow,
            SimConsumedSignalRow,
            SimFillFinanceContextRow,
            ExecutionEventRow,
            DecisionJournalEntryRow,
            PortfolioReservationRow,
        ):
            await session.execute(delete(model).where(model.account_id == account_id))
        await session.execute(
            delete(Top3OpportunityRow).where(
                Top3OpportunityRow.run_id.like(f"top3-{account_id}-%")
            )
        )
        if edge_report_id is not None:
            await session.execute(delete(EdgeReportRow).where(EdgeReportRow.id == edge_report_id))
        try:
            await SqlAlchemyAccountRepository(session).close_account(account_id)
        except Exception:  # noqa: BLE001 — el cleanup nunca tira el test
            pass
        await session.commit()


# ── Test POSITIVO — la cadena completa con identidad real ───────────────────────────


@pytest.mark.asyncio
async def test_identity_chain_battery_complete_end_to_end_pg(
    identity_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Identidad ganadora → señal → plan → ciclo SIM → DÍA-D → resultado conciliado."""
    state = await _drive_cycle(
        identity_pg_factory,
        monkeypatch,
        source=_IDENTITY_SOURCE,
        prefix="inst-idch-",
    )
    try:
        await _assert_complete_chain(identity_pg_factory, state)
    finally:
        await _teardown(identity_pg_factory, state)


async def _assert_complete_chain(
    factory: async_sessionmaker[AsyncSession], state: dict[str, Any]
) -> None:
    """Aserciones de la cadena completa (positivo), con el ciclo AÚN durable."""
    from bolsa_application.auto_chain_durable_reader import read_operational_monitor
    from bolsa_application.auto_cycle_journal import cycle_decision_id
    from bolsa_application.dia_d_cycle_verification import (
        build_dia_d_cycle_verification_draft,
    )
    from bolsa_infrastructure.database.models.tables import (
        DecisionJournalEntryRow,
        InstrumentRow,
    )
    from bolsa_infrastructure.database.repositories.dia_d_cycle_verification_repository import (
        SqlAlchemyDiaDCycleVerificationRepository,
    )
    from tests.applied_fill_equity import realized_notional_from_applied_fills

    account_id = state["accountId"]
    engine_id = state["engineId"]
    instrument_id = state["instrumentId"]
    cycle_id = state["cycleId"]

    artifact = await _read_evidence(
        factory,
        account_id=account_id,
        engine_id=engine_id,
        study_instruments=[instrument_id],
    )

    # 0) Doctrina del artefacto: read-only y sin la palabra prohibida.
    assert artifact["readOnly"] is True
    assert "CONFIRMED" not in str(artifact)

    # 1) IDENTIDAD GANADORA — la foto cross-asset sella preset Y versión del #1.
    best = artifact["bestScored"]
    assert best is not None, "la foto durable del TOP3 debe existir: sin ella no hay ganadora"
    assert best["rank"] == 1, best
    assert best["assetId"] == instrument_id, best
    assert best["strategyPresetKey"] == _IDENTITY_PRESET, best
    assert best["strategyVersion"] == _IDENTITY_VERSION, best
    assert best["bestScoredPresetKey"] == _IDENTITY_PRESET, best
    assert best["bestScoredStrategyVersion"] == _IDENTITY_VERSION, best
    assert best["strategyMeasurement"] == "COMPLETE", (
        f"la foto declara ambos términos de la identidad: {best}"
    )

    # 2) Ciclo único del valor, con las NUEVE etapas encendidas desde hechos durables.
    cycle = await _only_cycle(artifact, instrument_id)
    assert cycle["cycleId"] == cycle_id
    assert cycle["steps"] == dict.fromkeys(_CANONICAL_STEPS, 1), (
        f"las nueve etapas deben estar encendidas; no alcanzadas={cycle['chain']['notReached']}"
    )
    assert cycle["chain"]["complete"] is True

    # 3) IDENTIDAD EJECUTADA — sellada por el ciclo, no inferida del ranking.
    executed = cycle["executed"]
    assert executed["measurement"] == "COMPLETE", executed
    assert executed["strategyPresetKey"] == _IDENTITY_PRESET
    assert executed["strategyVersion"] == _IDENTITY_VERSION
    assert isinstance(executed["rank"], int) and executed["rank"] > 0, executed
    assert cycle["opportunityId"] is not None, (
        f"la identidad de la oportunidad es de 1ª clase en el ciclo: {cycle['opportunityId']}"
    )

    # 4) SEÑAL y PLAN — la decisión durable y el plan comparten la clave del ciclo.
    decision_id = cycle_decision_id(cycle_id)
    assert decision_id is not None, f"el cycleId debe permitir derivar su decisión: {cycle_id}"
    async with factory() as session:
        entry_rows = (
            await session.execute(
                select(DecisionJournalEntryRow).where(
                    DecisionJournalEntryRow.decision_id == decision_id,
                    DecisionJournalEntryRow.event_type == "auto_entry_decision",
                )
            )
        ).scalars().all()
    assert entry_rows, f"el ciclo {cycle_id} debe tener su hecho durable {decision_id}"
    payload = dict(entry_rows[0].payload or {})
    assert payload.get("cycleId") == cycle_id
    assert str(payload.get("strategyPresetKey") or "") == _IDENTITY_PRESET
    assert str(payload.get("strategyVersion") or "") == _IDENTITY_VERSION
    assert str(payload.get("signalId") or "").strip(), f"la señal debe estar identificada: {payload}"
    assert str(payload.get("opportunityId") or "").strip(), payload
    # El plan nace de la MISMA decisión (``thesis_id = decision_id`` en ``_build_trade_plan``).
    assert entry_rows[0].instrument_id == instrument_id

    # 5) EJECUTADA vs MEJOR PUNTUADA — coincide la identidad; el puesto es 1.
    compare = cycle["executedVsBest"]
    assert compare["executedIsTopRanked"] is True, compare
    assert compare["executedRank"] == executed["rank"]
    assert compare["presetMatch"] is True, compare
    assert compare["versionMatch"] is True, compare
    assert compare["strategyMeasurement"] == "COMPLETE", compare
    # El activo ganador y el ejecutado son el MISMO id de catálogo: la comparación de activo
    # no canoniza símbolos, pero aquí ambos lados son el id (la foto colapsa a ``_base_symbol``
    # del ``instrument_id``), así que la identidad de activo coincide sin ambigüedad.
    assert compare["executedIsBestScoredAsset"] is True, compare

    # 6) LECTURA DEL MONITOR — la identidad del ciclo es la de la foto (una sola verdad).
    async with factory() as session:
        monitor = await read_operational_monitor(
            session, account_id, engine_id=engine_id, cycle_id=cycle_id
        )
    assert monitor["cycles"], monitor
    cycle_row = monitor["cycles"][0]
    assert cycle_row["strategyPresetKey"] == _IDENTITY_PRESET
    assert cycle_row["strategyVersion"] == _IDENTITY_VERSION
    # La decisión de cartera durable que produjo el ciclo está enlazada (no es un hueco).
    assert cycle_row["decision"] is not None, "el ciclo debe declarar su decisión de cartera"

    # 7) DÍA-D — antes de la verificación el eslabón NO se puede enlazar ni afirmar.
    assert cycle["diaD"] is None, "sin verificación durable no hay hecho DÍA-D que leer"
    assert cycle["diaDLink"]["linkable"] is False, cycle["diaDLink"]
    assert cycle["executedVsDiaD"]["matches"] is None, cycle["executedVsDiaD"]

    async with factory() as session:
        instrument_symbol = (
            await session.execute(
                select(InstrumentRow.symbol).where(InstrumentRow.id == instrument_id)
            )
        ).scalar_one_or_none()
    assert instrument_symbol, "el instrumento sembrado debe estar en el catálogo"

    # El borrador se compone con los HECHOS del ciclo: su identidad se COPIA, no se inventa.
    draft = build_dia_d_cycle_verification_draft(
        {
            "cycleId": cycle_id,
            "instrumentId": instrument_id,
            "symbol": instrument_symbol,
            "diaD": cycle["entryDay"],
            "endDate": cycle["exitDay"],
            "mode": "auto",
            "strategyPresetKey": executed["strategyPresetKey"],
            "strategyVersion": executed["strategyVersion"],
        }
    )
    assert draft is not None, "con los hechos del ciclo la verificación es enlazable"
    async with factory() as session:
        await SqlAlchemyDiaDCycleVerificationRepository(session).upsert(
            **draft, account_id=account_id
        )
        await session.commit()

    # 8) Tras escribir la verificación, el eslabón se enlaza y el contraste coincide.
    artifact_linked = await _read_evidence(
        factory,
        account_id=account_id,
        engine_id=engine_id,
        study_instruments=[instrument_id],
    )
    cycle_linked = await _only_cycle(artifact_linked, instrument_id)
    assert cycle_linked["diaD"] is not None
    assert cycle_linked["diaDLink"]["linkable"] is True, cycle_linked["diaDLink"]
    assert cycle_linked["executedVsDiaD"]["matches"] is True, cycle_linked["executedVsDiaD"]
    assert cycle_linked["executedVsDiaD"]["measurement"] == "COMPLETE"
    value = artifact_linked["values"][0]
    assert value["strategy"]["presetKey"] == _IDENTITY_PRESET
    assert value["strategy"]["presetKeyAmbiguous"] is False
    assert value["strategyDiaD"]["verifications"] == 1

    # 9) RESULTADO CONCILIADO — cierre vs liquidación al quantum, y contra el libro aplicado.
    pnl = cycle_linked["pnl"]
    assert pnl["reconciled"] is True, pnl
    assert _to_money(pnl["cycleClosedPnl"]) == _to_money(pnl["settlementPnl"]), pnl
    async with factory() as session:
        ledger_realized = await realized_notional_from_applied_fills(session, account_id)
    assert _to_money(pnl["cycleClosedPnl"]) == _to_money(ledger_realized), (
        "el P&L del ciclo debe cuadrar EXACTO con el libro aplicado: "
        f"ciclo={pnl['cycleClosedPnl']} libro={ledger_realized}"
    )
    assert await _gross_notional(factory, account_id) > 0, (
        "el día debe mover notional bruto > 0; si no, la conciliación no dice nada"
    )


# ── Control NEGATIVO — identidad a medias: PARTIAL, nunca COMPLETE ──────────────────


@pytest.mark.asyncio
async def test_identity_chain_battery_declares_partial_without_preset_pg(
    identity_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin ``::preset`` la identidad es ``PARTIAL`` y ningún contraste se inventa.

    La fuente ``auto-2.0:<v>`` declara versión pero NO preset. El ciclo sella lo que la
    fuente declara y el lector lo publica como medido A MEDIAS: jamás ``COMPLETE`` (que
    afirmaría una identidad completa), y ``presetMatch`` queda ``None`` (un hueco), no
    ``False`` (que afirmaría una divergencia sin término de comparación).
    """
    state = await _drive_cycle(
        identity_pg_factory,
        monkeypatch,
        source=_NO_PRESET_SOURCE,
        prefix="inst-idchp-",
    )
    try:
        await _assert_partial_chain(identity_pg_factory, state)
    finally:
        await _teardown(identity_pg_factory, state)


async def _assert_partial_chain(
    factory: async_sessionmaker[AsyncSession], state: dict[str, Any]
) -> None:
    """Aserciones del control negativo (identidad a medias), con el ciclo vivo."""
    from bolsa_application.auto_chain_durable_reader import read_operational_monitor
    from bolsa_application.dia_d_cycle_verification import (
        build_dia_d_cycle_verification_draft,
    )
    from bolsa_infrastructure.database.models.tables import InstrumentRow
    from bolsa_infrastructure.database.repositories.dia_d_cycle_verification_repository import (
        SqlAlchemyDiaDCycleVerificationRepository,
    )
    account_id = state["accountId"]
    engine_id = state["engineId"]
    instrument_id = state["instrumentId"]
    cycle_id = state["cycleId"]

    artifact = await _read_evidence(
        factory,
        account_id=account_id,
        engine_id=engine_id,
        study_instruments=[instrument_id],
    )
    cycle = await _only_cycle(artifact, instrument_id)
    assert cycle["cycleId"] == cycle_id
    assert cycle["chain"]["complete"] is True, "la cadena se mide aunque la identidad sea parcial"

    executed = cycle["executed"]
    assert executed["measurement"] == "PARTIAL", executed
    assert executed["strategyPresetKey"] is None, "la ausencia de preset es información, no relleno"
    assert executed["strategyVersion"] == _IDENTITY_VERSION
    assert isinstance(executed["rank"], int) and executed["rank"] > 0, executed

    compare = cycle["executedVsBest"]
    assert compare["presetMatch"] is None, (
        f"sin preset en la foto NO se puede afirmar coincidencia ni divergencia: {compare}"
    )
    assert compare["versionMatch"] is True, compare
    assert compare["strategyMeasurement"] == "PARTIAL", compare
    assert compare["executedIsTopRanked"] is True, compare

    best = artifact["bestScored"]
    assert best is not None
    assert best["rank"] == 1
    assert best["strategyPresetKey"] is None
    assert best["strategyVersion"] == _IDENTITY_VERSION
    assert best["bestScoredPresetKey"] is None
    assert best["strategyMeasurement"] == "PARTIAL", best

    async with factory() as session:
        monitor = await read_operational_monitor(
            session, account_id, engine_id=engine_id, cycle_id=cycle_id
        )
    cycle_row = monitor["cycles"][0]
    assert cycle_row["strategyPresetKey"] is None
    assert cycle_row["strategyVersion"] == _IDENTITY_VERSION

    # La verificación DÍA-D se escribe COPIANDO el hueco: el contraste sigue sin afirmarse.
    async with factory() as session:
        symbol = (
            await session.execute(
                select(InstrumentRow.symbol).where(InstrumentRow.id == instrument_id)
            )
        ).scalar_one_or_none()
    draft = build_dia_d_cycle_verification_draft(
        {
            "cycleId": cycle_id,
            "instrumentId": instrument_id,
            "symbol": symbol,
            "diaD": cycle["entryDay"],
            "endDate": cycle["exitDay"],
            "mode": "auto",
            "strategyPresetKey": executed["strategyPresetKey"],
            "strategyVersion": executed["strategyVersion"],
        }
    )
    assert draft is not None
    assert draft["strategy_preset_key"] is None, "el borrador no rellena la identidad ausente"
    async with factory() as session:
        await SqlAlchemyDiaDCycleVerificationRepository(session).upsert(
            **draft, account_id=account_id
        )
        await session.commit()

    linked = await _only_cycle(
        await _read_evidence(
            factory,
            account_id=account_id,
            engine_id=engine_id,
            study_instruments=[instrument_id],
        ),
        instrument_id,
    )
    assert linked["diaDLink"]["linkable"] is True
    assert linked["executedVsDiaD"]["matches"] is None, (
        "sin preset en ambos lados la coincidencia NO se puede afirmar: "
        f"{linked['executedVsDiaD']}"
    )
    assert linked["executedVsDiaD"]["measurement"] == "UNKNOWN"
    assert linked["pnl"]["reconciled"] is True, linked["pnl"]
