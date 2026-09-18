"""V2.43 (AUTO-3, slice 1) — integración hermética: la tabla GOBIERNA la decisión.

El criterio del slice no es "existe la tabla", es "la tabla decide". Este fichero corre la
evidencia reproducible (``apps/api-python/scripts/v2_43_governor_evidence.py``) por el camino
REAL del worker —snapshot del libro → ``plan_v2_tick``— y exige que la escalera de drawdown
produzca la escalera de estados y de efectos declarada:

    0 %  → ENTRY_ALLOWED    → entra con el tamaño intacto
    6 %  → ENTRY_REDUCED    → entra al 75 %
    12 % → ENTRY_RESTRICTED → tamaño al 50 % y listón de edge más alto
    15 % → EXIT_ONLY        → ``governor_exit_only``
    22 % → HALTED           → ``governor_halted``

Cada tramo se mide con su CONTROL (mismo snapshot, flag OFF), así que el veto se atribuye
al gobernador y no a otro gate. Sin PG, sin red y sin reloj real.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.account_drawdown import EquityMarkBook
from bolsa_application.execution_event import InMemoryExecutionEventStore

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "v2_43_governor_evidence.py"
_DAY = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)


def _evidence_module():
    """Carga el script de evidencia por ruta (no es un paquete instalable)."""
    spec = importlib.util.spec_from_file_location("v2_43_governor_evidence", _SCRIPT)
    assert spec is not None and spec.loader is not None, _SCRIPT
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run_evidence() -> tuple[object, dict]:
    module = _evidence_module()
    evidence = await module.run_evidence()
    return module, evidence


@pytest.mark.asyncio
async def test_governor_table_governs_the_entry_decision() -> None:
    """La escalera de drawdown produce la escalera de estados y de efectos (medida)."""
    module, evidence = await _run_evidence()

    failures = module.verify(evidence)
    assert failures == [], failures

    ladder = evidence["ladder"]
    assert [
        ladder[step]["operationalState"] for step in ("0.0", "6.0", "12.0", "15.0", "22.0")
    ] == [
        "ENTRY_ALLOWED",
        "ENTRY_REDUCED",
        "ENTRY_RESTRICTED",
        "EXIT_ONLY",
        "HALTED",
    ]
    # El drawdown medido es el que entra en la tabla (no un 0 % optimista: sin marca no hay
    # número y el eje de riesgo sería UNKNOWN).
    assert [ladder[step]["drawdownPct"] for step in ("0.0", "6.0", "12.0", "15.0", "22.0")] == [
        0.0,
        6.0,
        12.0,
        15.0,
        22.0,
    ]
    # El hecho de mercado y el permiso viajan SEPARADOS en el journal de cada decisión.
    for step in ("0.0", "6.0", "12.0", "15.0", "22.0"):
        assert ladder[step]["journalKeys"] == ["marketRegime", "operationalState", "riskRegime"]
        assert ladder[step]["marketRegime"] == "TREND_UP"
    # Los dos vetos del gobernador son los suyos, y el control (flag OFF) SÍ aprobaba:
    # el freno es del gobernador, no de otro gate de la cartera.
    assert ladder["15.0"]["reasonCodes"] == ["governor_exit_only"]
    assert ladder["22.0"]["reasonCodes"] == ["governor_halted"]
    assert ladder["15.0"]["control"]["approved"] is True
    assert ladder["22.0"]["control"]["approved"] is True


@pytest.mark.asyncio
async def test_governor_evidence_measures_the_unrealized_leg_and_the_off_control() -> None:
    """La equity medida incluye el P&L no realizado, y con el flag OFF nada cambia."""
    _module, evidence = await _run_evidence()

    leg = evidence["unrealizedLeg"]
    # Posición viva que cae un 10 % (60 000 de exposición sobre 100 000 de equity) ⇒ 6 % de
    # drawdown ⇒ el gobernador lo ve aunque la equity base declarada no se mueva.
    assert leg["flat"]["drawdownPct"] == 0.0
    assert leg["flat"]["operationalState"] == "ENTRY_ALLOWED"
    assert leg["marked"]["drawdownPct"] == 6.0
    assert leg["marked"]["operationalState"] == "ENTRY_REDUCED"

    off = evidence["flagOff"]
    # Byte-identidad: ni se mide el drawdown, ni se publican dimensiones, ni cambia el motivo
    # ni el tamaño. La comparación de cantidad es a MISMA equity (100 000): con equity
    # distinta el presupuesto de riesgo cambia por diseño, no por el gobernador.
    assert off["flat"]["drawdownPct"] is None and off["deep"]["drawdownPct"] is None
    assert off["flat"]["journalKeys"] == [] and off["deep"]["journalKeys"] == []
    assert off["flat"]["reasonCodes"] == off["deep"]["reasonCodes"] == ["approved"]
    assert off["flat"]["quantity"] == pytest.approx(evidence["baseline"]["quantity"])


def test_worker_publishes_measurement_only_with_the_flag_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seam del worker: la marca inyectada publica el drawdown SOLO con el gobernador ON."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_REGIME", raising=False)
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_GOVERNOR", raising=False)
    marks = EquityMarkBook()
    worker = AutoSimulationWorker(
        clock=lambda: _DAY,
        exec_store=InMemoryExecutionEventStore(),
        equity_marks=marks,
    )
    assert worker._v2_snapshot("BULL_TREND").drawdown_pct is None  # flag OFF ⇒ no se mide.

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", "1")
    measured = AutoSimulationWorker(
        clock=lambda: _DAY,
        exec_store=InMemoryExecutionEventStore(),
        equity_marks=marks,
    )
    assert measured._v2_snapshot("BULL_TREND").drawdown_pct == 0.0  # fija la marca del día.
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "88000")
    assert measured._v2_snapshot("BULL_TREND").drawdown_pct == pytest.approx(12.0)
