"""AUTO-20B (V2.63) — E2E REAL del exportador PAPER sobre PostgreSQL + oráculo same-material.

Certifica la deuda nº 1 de ``v2.62``: **demostrar físicamente, contra PostgreSQL real, que el
ciclo que entra en el calibrador es exactamente el ciclo que AUTO cree que está midiendo**, y
que lo que no se pudo medir se DECLARA (nunca se trunca en silencio).

Se siembra un material de cardinalidad CONOCIDA de antemano y se recorre la cadena entera:

    PG (fills + reservas + journal de régimen) → exportador real (main, sin mocks) → JSON en stdout
    → calibración walk-forward → oráculo de igualdad + oráculo same-material (AUTO-7 vs AUTO-20).

Fixture (26 ciclos cerrados):

* **A** — 12 ciclos, 9 con reserva (``reserved_risk > 0``) ⇒ **medida parcial** (NO ``unmeasured_r:A``).
* **B** — 8 ciclos, los 8 con riesgo ⇒ **medida completa**.
* **C** — 5 ciclos, ninguno con riesgo ⇒ **``unmeasured_r:C``**.
* **U** — 1 ciclo cuyos fills declaran DOS versiones ⇒ **``unversioned_cycles``**.
* **≥2 regímenes** — trazas ``TREND_UP``/``RANGE`` en el journal; 6 ciclos sin traza (se declaran).
* **coste aplicado** — ``reference_mid`` en los 17 ciclos con riesgo ⇒ ``costApplied`` COMPLETE.
* **perímetro (AUTO-20C)** — 2 fills SIN versión (``strategy_version_id`` NULL) y 2 de una versión
  NO solicitada: el exportador no los lee, pero el manifest los CUANTIFICA como excluidos.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO20B_EXPORT_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre el bridge LIVE.

Este fichero es SOLO el E2E (PG obligatorio). Los dos casos PUROS del mismo contrato —fail-closed
de la paginación y passthrough del manifest en el battery— viven en el fichero hermano
``test_auto_v63_auto20b_export_completeness.py``, que corre en el job offline: sin PG no puede
haber un skip silencioso que aparente certificar esta cadena.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO20B_EXPORT_PG_REQUIRED"
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "paper_cycles_export.py"

_A = "orb-a20b-A"
_B = "orb-a20b-B"
_C = "orb-a20b-C"
_VERSIONS = (_A, _B, _C)
_INSTRUMENT = "AAA20B"
_RESERVED_RISK = Decimal("50")
_QTY = Decimal("10")
_BUY_PRICE = Decimal("100")
_SELL_PRICE = Decimal("110")
# Fricción por pata con referencia: |100 − 99.9| × 10 = 1.0 (compra), |110.1 − 110| × 10 = 1.0.
_REF_BUY, _REF_SELL = Decimal("99.9"), Decimal("110.1")
_APPLIED_FRICTION = Decimal("2.0")


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(f"PostgreSQL requerido para AUTO-20B pero no disponible: {exc}") from exc
    pytest.skip(f"PostgreSQL/Alembic (AUTO-20B) no disponible: {exc}")


# ── Fixture determinista ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _CycleSpec:
    cycle_id: str
    buy_version: str
    sell_version: str
    effective_version: str
    with_risk: bool
    with_reference: bool
    regime: str | None


def _specs() -> list[_CycleSpec]:
    specs: list[_CycleSpec] = []
    for index in range(12):  # A: 12 ciclos, 9 con riesgo ⇒ parcial.
        cid = f"cyc-a20b-a-{index:02d}"
        specs.append(
            _CycleSpec(cid, _A, _A, _A, with_risk=index < 9, with_reference=index < 9, regime="TREND_UP")
        )
    for index in range(8):  # B: 8 ciclos, los 8 con riesgo ⇒ completa.
        cid = f"cyc-a20b-b-{index:02d}"
        specs.append(_CycleSpec(cid, _B, _B, _B, True, True, "RANGE"))
    for index in range(5):  # C: 5 ciclos, ninguno con riesgo ⇒ unmeasured_r:C.
        cid = f"cyc-a20b-c-{index:02d}"
        specs.append(_CycleSpec(cid, _C, _C, _C, False, False, None))
    specs.append(_CycleSpec("cyc-a20b-u-00", _A, _B, "", False, False, None))  # U: dos versiones.
    return specs


_SPECS = _specs()
_RISK_CYCLES = tuple(spec.cycle_id for spec in _SPECS if spec.with_risk)
_CONFIRMED_REGIMES = sum(1 for spec in _SPECS if spec.regime is not None)
#: AUTO-20C — perímetro: fills de la cuenta que quedan FUERA del universo pedido.
_NULL_VERSION_CYCLE = "cyc-a20b-null-00"
_OTHER_VERSION_CYCLE = "cyc-a20b-x-00"
_OTHER_VERSION = "orb-a20b-OTHER"
_EXCLUDED_FILLS = 2 + 2


def _expected_report_spec() -> dict[str, Any]:
    """Oráculo independiente (construido desde el fixture, no desde el producto)."""
    return {
        "closedCycles": len(_SPECS),
        "fillsRead": 2 * len(_SPECS),
        "cyclesWithRisk": len(_RISK_CYCLES),
        "cyclesWithoutRisk": len(_SPECS) - len(_RISK_CYCLES),
        "cyclesWithoutVersion": 1,
        "costAppliedCycles": len(_RISK_CYCLES),
        "regimeConfirmed": _CONFIRMED_REGIMES,
        "regimeAbsent": len(_SPECS) - _CONFIRMED_REGIMES,
        "reservationsRead": len(_RISK_CYCLES),
        "fillsTotalForAccount": 2 * len(_SPECS) + _EXCLUDED_FILLS,
        "fillsSelected": 2 * len(_SPECS),
        "fillsExcludedNoVersion": 2,
        "fillsExcludedOtherVersion": 2,
        "observedVersions": sorted({_A, _B, _C}),
        "regimesPresent": ["RANGE", "TREND_UP"],
    }


# ── Acceso a PostgreSQL ─────────────────────────────────────────────────────────────


async def _open_session_factory() -> tuple[Any, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    return engine, create_session_factory(engine)


async def _seed(account_id: str) -> None:
    from bolsa_analytics.cognitive.portfolio_reservation import build_reservation
    from bolsa_application.auto_cycle_journal import build_auto_cycle_regime_entry
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import (
        PostgresSimFillFinanceContextStore,
        SimFillFinanceContext,
    )
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    engine, factory = await _open_session_factory()
    try:
        async with factory() as session:
            fills = PostgresSimFillFinanceContextStore(session, autocommit=False)
            reservations = PostgresReservationStore(session, autocommit=False)
            journal = SqlAlchemyJournalRepository(session)
            for spec in _SPECS:
                await fills.save(
                    SimFillFinanceContext(
                        execution_id=f"{spec.cycle_id}-buy",
                        instrument_id=_INSTRUMENT,
                        side="buy",
                        quantity=_QTY,
                        price=_BUY_PRICE,
                        reference_mid=_REF_BUY if spec.with_reference else None,
                        account_id=account_id,
                        strategy_version_id=spec.buy_version,
                        cycle_id=spec.cycle_id,
                    )
                )
                await fills.save(
                    SimFillFinanceContext(
                        execution_id=f"{spec.cycle_id}-sell",
                        instrument_id=_INSTRUMENT,
                        side="sell",
                        quantity=_QTY,
                        price=_SELL_PRICE,
                        reference_mid=_REF_SELL if spec.with_reference else None,
                        account_id=account_id,
                        strategy_version_id=spec.sell_version,
                        cycle_id=spec.cycle_id,
                    )
                )
                if spec.with_risk:
                    await reservations.save(
                        build_reservation(
                            reservation_id=f"RES-{spec.cycle_id}",
                            account_id=account_id,
                            tick_id="2026-09-20T09:00:00Z",
                            instrument_id=_INSTRUMENT,
                            side="buy",
                            quantity=_QTY,
                            entry=_BUY_PRICE,
                            stop=Decimal("95"),
                            reserved_risk=_RESERVED_RISK,
                            strategy_version_id=spec.effective_version or spec.buy_version,
                            cycle_id=spec.cycle_id,
                            created_at="2026-09-20T09:00:00Z",
                        )
                    )
                if spec.regime is not None:
                    entry = build_auto_cycle_regime_entry(
                        cycle_id=spec.cycle_id,
                        market_regime=spec.regime,
                        actor="auto20b-test",
                        as_of="2026-09-20T10:00:00Z",
                        account_id=account_id,
                        instrument_id=_INSTRUMENT,
                    )
                    assert entry is not None
                    await journal.append(entry)
            # AUTO-20C — PERÍMETRO: fills que quedan FUERA del universo pedido. Uno sin versión
            # (``strategy_version_id`` NULL) y otro de una versión NO solicitada. El exportador no
            # los lee (no pertenecen a las versiones pedidas), pero el manifest debe CUANTIFICARLOS.
            for execution_id, cycle_id, version in (
                (f"{_NULL_VERSION_CYCLE}-buy", _NULL_VERSION_CYCLE, None),
                (f"{_NULL_VERSION_CYCLE}-sell", _NULL_VERSION_CYCLE, None),
                (f"{_OTHER_VERSION_CYCLE}-buy", _OTHER_VERSION_CYCLE, _OTHER_VERSION),
                (f"{_OTHER_VERSION_CYCLE}-sell", _OTHER_VERSION_CYCLE, _OTHER_VERSION),
            ):
                side = "buy" if execution_id.endswith("-buy") else "sell"
                await fills.save(
                    SimFillFinanceContext(
                        execution_id=execution_id,
                        instrument_id=_INSTRUMENT,
                        side=side,
                        quantity=_QTY,
                        price=_BUY_PRICE if side == "buy" else _SELL_PRICE,
                        account_id=account_id,
                        strategy_version_id=version,
                        cycle_id=cycle_id,
                    )
                )
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup(account_id: str) -> None:
    from sqlalchemy import delete, select

    from bolsa_application.auto_cycle_journal import (
        AUTO_CYCLE_REGIME_EVENT,
        cycle_decision_id,
    )
    from bolsa_infrastructure.database.models.tables import (
        DecisionJournalEntryRow,
        PortfolioReservationRow,
        SimFillFinanceContextRow,
    )

    engine, factory = await _open_session_factory()
    try:
        async with factory() as session:
            decision_ids = [
                derived
                for spec in _SPECS
                if (derived := cycle_decision_id(spec.cycle_id)) is not None
            ]
            await session.execute(
                delete(SimFillFinanceContextRow).where(
                    SimFillFinanceContextRow.account_id == account_id
                )
            )
            await session.execute(
                delete(PortfolioReservationRow).where(
                    PortfolioReservationRow.account_id == account_id
                )
            )
            await session.execute(
                delete(DecisionJournalEntryRow).where(
                    DecisionJournalEntryRow.account_id == account_id
                )
            )
            await session.execute(
                delete(DecisionJournalEntryRow).where(
                    DecisionJournalEntryRow.decision_id.in_(decision_ids),
                    DecisionJournalEntryRow.event_type == AUTO_CYCLE_REGIME_EVENT,
                )
            )
            await session.commit()
            leftovers = (
                await session.execute(
                    select(SimFillFinanceContextRow.execution_id).where(
                        SimFillFinanceContextRow.account_id == account_id
                    )
                )
            ).scalars().all()
            assert not leftovers
    finally:
        await engine.dispose()


def _load_exporter() -> Any:
    spec = importlib.util.spec_from_file_location("auto20b_paper_cycles_export", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_exporter(account_id: str, *, page_size: int) -> tuple[int, dict[str, Any], str]:
    """Ejecuta el exportador REAL releyendo ``sys.stdout``/``stderr`` (sin mocks)."""
    import io
    from contextlib import redirect_stderr, redirect_stdout

    module = _load_exporter()
    argv = ["--account-id", account_id, "--limit", str(page_size)]
    for version in _VERSIONS:
        argv += ["--strategy-version", version]
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = module.main(argv)
    payload = json.loads(out.getvalue()) if code == 0 else {}
    return code, payload, err.getvalue()


async def _read_same_material(account_id: str) -> tuple[list[Any], dict[str, Any]]:
    """Material AUTO-20 + informe AUTO-7 desde las MISMAS lecturas PG (oráculo)."""
    from bolsa_application.auto_cycle_regime_reader import read_cycle_regimes
    from bolsa_application.auto_self_evaluation_feed import (
        adaptive_instrument_cycles,
        build_auto_self_evaluation,
    )
    from bolsa_application.cycle_risk import cycle_risk_from_reservations
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    engine, factory = await _open_session_factory()
    try:
        async with factory() as session:
            fills_store = PostgresSimFillFinanceContextStore(session)
            reservation_store = PostgresReservationStore(session)
            journal = SqlAlchemyJournalRepository(session)
            fills: list[Any] = []
            for version in _VERSIONS:
                fills.extend(
                    await fills_store.list_for_strategy_version(version, account_id=account_id)
                )
            cycle_ids = sorted(
                {
                    str(fill.cycle_id).strip()
                    for fill in fills
                    if str(fill.cycle_id or "").strip()
                }
            )
            reservations = await reservation_store.list_by_cycle_ids(
                account_id, cycle_ids, limit=1000
            )
            reading = await read_cycle_regimes(journal.list_by_decision_ids, cycle_ids)
            cycle_risk = cycle_risk_from_reservations(
                cycle_ids,
                reservations,
                regime_by_cycle=dict(reading.regime_by_cycle),
                regime_source_durable=True,
            )
            material = adaptive_instrument_cycles(fills, cycle_risk)
            report = build_auto_self_evaluation(
                fills=fills, cycle_risk=cycle_risk, min_trades=1
            ).as_dict()
    finally:
        await engine.dispose()
    return material, report


@pytest.fixture
def a20b_pg() -> None:
    """Gate honesto: sin PostgreSQL real se salta (o falla duro con el env de gobierno)."""
    try:
        asyncio.run(_probe())
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise


async def _probe() -> None:
    engine, _factory = await _open_session_factory()
    await engine.dispose()


# ── El E2E ───────────────────────────────────────────────────────────────────────────


def test_the_export_is_certified_end_to_end_against_real_postgres(a20b_pg: None) -> None:
    """Fills + reservas + régimen → exportador real → JSON → calibración, con cardinalidad exacta."""
    account_id = f"acc-a20b-{uuid.uuid4().hex[:10]}"
    expected = _expected_report_spec()
    # ``--limit`` pequeño a propósito: fuerza varias páginas y prueba que NO se trunca nada.
    page_size = 3
    try:
        asyncio.run(_seed(account_id))
        code, payload, err = _run_exporter(account_id, page_size=page_size)
        assert code == 0, err
        manifest = payload["material_manifest"]
        cycles = payload["cycles"]

        # (1) Cardinalidad: el manifest coincide con el oráculo construido desde el fixture.
        assert manifest["closedCycles"] == expected["closedCycles"]
        assert manifest["fillsRead"] == expected["fillsRead"]
        assert manifest["cyclesWithRisk"] == expected["cyclesWithRisk"]
        assert manifest["cyclesWithoutRisk"] == expected["cyclesWithoutRisk"]
        assert manifest["cyclesWithoutVersion"] == expected["cyclesWithoutVersion"]
        assert manifest["costAppliedCycles"] == expected["costAppliedCycles"]
        assert manifest["regimeRead"]["confirmed"] == expected["regimeConfirmed"]
        assert manifest["regimeRead"]["absent"] == expected["regimeAbsent"]
        # (2) Paginación con --limit pequeño: se recuperan TODAS las reservas (no hay truncado).
        assert page_size < expected["reservationsRead"], "el caso debe forzar varias páginas"
        assert manifest["reservationsRead"] == expected["reservationsRead"]
        assert manifest["riskReadSaturated"] is False
        assert manifest["riskBasis"] == "reservation_reserved_risk"

        # (2b) AUTO-20C — PERÍMETRO declarado: el manifest cuantifica los fills que quedan FUERA
        # del universo pedido (sin versión / de otra versión) sin incluirlos, y declara la
        # procedencia virtual. El universo medido NO cambia.
        assert manifest["fillsTotalForAccount"] == expected["fillsTotalForAccount"]
        assert manifest["fillsSelected"] == expected["fillsSelected"]
        assert manifest["fillsExcludedNoVersion"] == expected["fillsExcludedNoVersion"]
        assert manifest["fillsExcludedOtherVersion"] == expected["fillsExcludedOtherVersion"]
        assert manifest["observedStrategyVersions"] == expected["observedVersions"]
        assert manifest["versionsRequestedWithoutMaterial"] == []
        assert manifest["versionsObservedNotRequested"] == []
        assert manifest["regimesPresent"] == expected["regimesPresent"]
        assert manifest["materialOrigin"] == "paper_real"
        assert manifest["executionReality"] == "virtual_paper_only"
        assert manifest["brokerVenue"] == "paper"

        # (3) Oráculo de igualdad por ciclo: cada ciclo del JSON es el que se sembró.
        by_id = {row["cycleId"]: row for row in cycles}
        assert set(by_id) == {spec.cycle_id for spec in _SPECS}
        for spec in _SPECS:
            row = by_id[spec.cycle_id]
            assert row["strategyVersion"] == spec.effective_version
            assert Decimal(str(row["pnl"])) == Decimal("100")
            assert ("riskAmount" in row) is spec.with_risk
            if spec.with_risk:
                assert Decimal(str(row["riskAmount"])) == _RESERVED_RISK
            assert ("costApplied" in row) is spec.with_reference
            if spec.with_reference:
                assert Decimal(str(row["costApplied"]["friction"])) == _APPLIED_FRICTION
                assert row["costApplied"]["measurement"] == "COMPLETE"
            assert row.get("regime") == spec.regime

        # (4) La huella del manifest es la del JSON exportado (los números normalizados cruzan
        # el ``json.dumps`` sin cambiar el sello: el mismo hecho medido, sin importar su tipo).
        from bolsa_analytics.cognitive.auto_material_manifest import material_fingerprint

        assert manifest["fingerprint"] == material_fingerprint(cycles)

        # (5) Calibración: el material real produce los pliegues por versión y declara los huecos.
        from bolsa_analytics.cognitive.auto_adaptive_calibration import build_calibration_report

        report = build_calibration_report(
            cycles, folds=3, min_is=2, min_oos=1, material=manifest
        )
        notes = report.notes
        assert "unmeasured_r:orb-a20b-C" in notes
        assert not any(note.startswith("unmeasured_r:orb-a20b-A") for note in notes)
        assert "unversioned_cycles" in notes
        assert {fold.cell.strategy_version for fold in report.folds} == {_A, _B}
        aggregate = report.aggregate
        assert aggregate["foldCount"] == 6, "3 pliegues de A + 3 de B"
        assert aggregate["pairedFoldCount"] == aggregate["foldCount"]
        assert aggregate["walkForwardEfficiency"] is not None
        assert report.as_dict()["material"] == manifest
    finally:
        asyncio.run(_cleanup(account_id))


def test_the_exporter_blocks_with_exit_two_when_completeness_cannot_be_proven(
    a20b_pg: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si la lectura no puede garantizar completitud, el exportador NO emite JSON: sale con 2."""
    module = _load_exporter()

    async def _saturated(*args: Any, **kwargs: Any) -> tuple[list[Any], bool]:
        return [], True

    monkeypatch.setattr(module, "_read_all_reservations", _saturated)
    import io
    from contextlib import redirect_stderr, redirect_stdout

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = module.main(["--account-id", "acc-saturated", "--strategy-version", _A])
    assert code == 2
    assert out.getvalue() == "", "un material incompleto NUNCA se publica como JSON"
    assert "BLOQUEADO" in err.getvalue()


def test_the_report_and_the_instrument_measure_the_same_material(a20b_pg: None) -> None:
    """La prueba clave: el informe durable (AUTO-7) y el material del calibrador (AUTO-20)
    describen el MISMO universo, incluso cruzando la frontera del JSON exportado."""
    account_id = f"acc-a20b-{uuid.uuid4().hex[:10]}"
    try:
        asyncio.run(_seed(account_id))
        code, payload, err = _run_exporter(account_id, page_size=4)
        assert code == 0, err
        material, durable_report = asyncio.run(_read_same_material(account_id))

        from bolsa_analytics.cognitive.auto_self_evaluation import evaluate_auto_self_evaluation

        exported_cycles = payload["cycles"]

        # Mismo conjunto de ciclos, mismos campos medidos (cycleId/version/riesgo/coste/régimen).
        by_id = {row["cycleId"]: row for row in material}
        exported_by_id = {row["cycleId"]: row for row in exported_cycles}
        assert set(by_id) == set(exported_by_id)
        for cycle_id, row in by_id.items():
            exported = exported_by_id[cycle_id]
            assert row["strategyVersion"] == exported["strategyVersion"]
            assert Decimal(str(row["pnl"])) == Decimal(str(exported["pnl"]))
            assert ("riskAmount" in row) is ("riskAmount" in exported)
            assert ("costApplied" in row) is ("costApplied" in exported)
            assert row.get("regime") == exported.get("regime")

        # El informe durable es EXACTAMENTE el que se recalcula desde el JSON exportado.
        round_trip_report = evaluate_auto_self_evaluation(
            cycles=exported_cycles, min_trades=1
        ).as_dict()
        assert round_trip_report == durable_report, (
            "el material exportado debe reproducir el informe durable sin diferencias"
        )
    finally:
        asyncio.run(_cleanup(account_id))
