"""V2.43 (AUTO-3, slice 1) — evidencia reproducible de que la TABLA gobierna la decisión.

Criterio del slice: el gobernador ``MarketRegime × RiskRegime × DD × Vol × Liquidez`` debe
GOBERNAR la decisión de entrada, no decorarla. Este script mide, sobre el camino REAL del
worker (snapshot del libro + ``plan_v2_tick``, sin PG ni red), una escalera de drawdown y
comprueba para cada tramo:

* el **estado** que resuelve la tabla (``ENTRY_ALLOWED`` → ``ENTRY_REDUCED`` →
  ``ENTRY_RESTRICTED`` → ``EXIT_ONLY`` → ``HALTED``);
* el **efecto** sobre la decisión (aprobada con tamaño escalado, o vetada con su motivo
  ``governor_*`` propio);
* que el **journal** publica las tres dimensiones (hecho de mercado, estado de riesgo y
  permiso) incluso cuando la decisión es un no-trade;
* que con el flag OFF el mismo drawdown **no cambia nada** (control de byte-identidad).

Uso (desde la raíz del repo):

    uv run python apps/api-python/scripts/v2_43_governor_evidence.py [--out RUTA.json]

``exit != 0`` si algún tramo no se comporta como la tabla declara (es decir, si la tabla no
está gobernando). El JSON que imprime es la evidencia que cita el audit-pack.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.account_drawdown import EquityMarkBook
from bolsa_application.auto_v2_entry import (
    V2_ENGINE_ENV,
    EdgeReportSource,
    V2Signal,
    plan_v2_tick,
    signal_identity_for_bar,
    tunables_from_env,
)
from bolsa_application.execution_event import InMemoryExecutionEventStore

_SYMBOL = "BBB"
_SECTORS = {_SYMBOL: "tech", "AAA": "health"}
_AS_OF = "2026-09-18T09:00:00Z"
_DAY = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)

#: Env que este script pisa: se guarda y se RESTAURA al terminar (el script es hermético y
#: no debe dejar el proceso de quien lo importe con la configuración de la evidencia).
_ENV_KEYS: tuple[str, ...] = (
    "AUTO_ENGINE_SIMULATED_WATCH",
    "AUTO_ENGINE_SIMULATED_VENUE",
    "AUTO_SIMULATION_WORKER_ENABLED",
    V2_ENGINE_ENV,
    "AUTO_ENGINE_SIM_V2_REGIME",
    "AUTO_ENGINE_SIM_V2_EQUITY",
    "AUTO_ENGINE_SIM_V2_GOVERNOR",
    "AUTO_ENGINE_SIM_V2_MAX_POSITION_PCT",
    "AUTO_ENGINE_SIM_V2_ATR_REQUIRED",
    "AUTO_ENGINE_SIM_V2_GOV_RESTRICTED_EDGE_FACTOR",
)


@contextmanager
def _scoped_env() -> Iterator[None]:
    """Guarda/restaura el env que toca la evidencia (importable desde un test)."""
    saved = {key: os.environ.get(key) for key in _ENV_KEYS}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


#: (drawdown esperado, estado esperado de la tabla, motivo esperado si veta)
_LADDER: tuple[tuple[float, str], ...] = (
    (0.0, "ENTRY_ALLOWED"),
    (6.0, "ENTRY_REDUCED"),
    (12.0, "ENTRY_RESTRICTED"),
    (15.0, "EXIT_ONLY"),
    (22.0, "HALTED"),
)


async def _read_edge(_strategy_ref: str, _account_id: str | None) -> float | None:
    return 0.9


def _signal(*, edge: float = 0.9) -> V2Signal:
    identity = signal_identity_for_bar(
        instrument_id=_SYMBOL,
        action="BUY",
        strategy_version="v43",
        timeframe="1d",
        moment=_DAY,
    )
    assert identity is not None
    return V2Signal(
        _SYMBOL,
        "BUY",
        price=100.0,
        atr=2.0,
        edge=edge,
        sector="tech",
        liquidity_notional=1_000_000.0,
        strategy_version="v43",
        signal_id=identity.signal_id,
        bar_timestamp=identity.bar_timestamp,
        valid_until=identity.valid_until,
    )


def _worker(marks: EquityMarkBook, prices: dict[str, float]) -> AutoSimulationWorker:
    """Worker hermético: precios, ATR y edge inyectados; libro de marcas COMPARTIDO."""
    return AutoSimulationWorker(
        exec_store=InMemoryExecutionEventStore(),
        sector_source=lambda symbol: _SECTORS.get(symbol),
        liquidity_source=lambda _symbol: 1_000_000.0,
        edge_source=EdgeReportSource(reader=_read_edge),
        price_script=lambda symbol, _minute: prices[symbol],
        atr_source=lambda _symbol: 2.0,
        equity_marks=marks,
    )


def _tick(
    worker: AutoSimulationWorker,
    *,
    equity: float,
    edge: float = 0.9,
    factor: float | None = None,
) -> dict[str, Any]:
    """Un tick del camino real: snapshot del worker → ``plan_v2_tick``.

    Cada medición lleva su CONTROL con el flag OFF **sobre el mismo snapshot**: así el
    escalado se lee como el factor del gobernador (misma equity ⇒ mismo presupuesto) y los
    vetos se leen como "el gobernador fue quien frenó" (el control aprobaba).
    """
    os.environ["AUTO_ENGINE_SIM_V2_EQUITY"] = str(equity)
    snapshot = worker._v2_snapshot("BULL_TREND")  # noqa: SLF001 — seam del worker.
    tunables = worker._v2_tunables  # noqa: SLF001
    if factor is not None:
        tunables = replace(tunables, governor_restricted_edge_factor=factor)
    plan = plan_v2_tick(
        snapshot=snapshot,
        signals=[_signal(edge=edge)],
        regime="BULL_TREND",
        tunables=tunables,
        as_of=_AS_OF,
    )
    control = plan_v2_tick(
        snapshot=snapshot,
        signals=[_signal(edge=edge)],
        regime="BULL_TREND",
        tunables=replace(tunables, governor_enabled=False),
        as_of=_AS_OF,
    )
    decision = plan.decisions[0]
    payload = dict(plan.journal_entries[0].payload or {})
    package = plan.entry_packages.get(_SYMBOL)
    control_package = control.entry_packages.get(_SYMBOL)
    return {
        "equity": equity,
        "drawdownPct": snapshot.drawdown_pct,
        "operationalState": decision.operational_state,
        "marketRegime": decision.market_regime,
        "riskRegime": decision.risk_regime,
        "reasonCodes": list(decision.reason_codes),
        "approved": decision.approved,
        "quantity": None if package is None else package.quantity,
        "journalKeys": sorted(
            key for key in ("marketRegime", "riskRegime", "operationalState") if key in payload
        ),
        "governorStates": dict(plan.governor_states),
        "control": {
            "approved": control.decisions[0].approved,
            "reasonCodes": list(control.decisions[0].reason_codes),
            "quantity": None if control_package is None else control_package.quantity,
            "operationalState": control.decisions[0].operational_state,
        },
    }


async def run_evidence() -> dict[str, Any]:
    """Corre la escalera de drawdown y devuelve la evidencia serializable."""
    with _scoped_env():
        return _run_evidence()


def _run_evidence() -> dict[str, Any]:
    """Cuerpo de la evidencia (síncrono: no hay awaits reales en los seams medidos)."""
    os.environ.update(
        {
            "AUTO_ENGINE_SIMULATED_WATCH": f"{_SYMBOL},AAA",
            "AUTO_ENGINE_SIMULATED_VENUE": "paper",
            "AUTO_SIMULATION_WORKER_ENABLED": "0",
            V2_ENGINE_ENV: "1",
            "AUTO_ENGINE_SIM_V2_REGIME": "BULL_TREND",
            "AUTO_ENGINE_SIM_V2_GOVERNOR": "1",
            "AUTO_ENGINE_SIM_V2_MAX_POSITION_PCT": "100",
        }
    )
    os.environ.pop("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", None)
    os.environ.pop("AUTO_ENGINE_SIM_V2_GOV_RESTRICTED_EDGE_FACTOR", None)

    prices = {_SYMBOL: 100.0, "AAA": 100.0}
    marks = EquityMarkBook()
    worker = _worker(marks, prices)

    # La marca del día la fija el PRIMER tick con la equity de referencia (100 000).
    baseline = _tick(worker, equity=100_000.0)
    ladder: dict[str, Any] = {}
    for drawdown, _expected in _LADDER:
        equity = 100_000.0 * (1.0 - drawdown / 100.0)
        measured = _tick(worker, equity=equity)
        ladder[str(drawdown)] = measured

    # Con el umbral de edge por defecto (factor 2.0) RESTRICTED no deja pasar una candidata
    # del rango alcanzable (score = edge × 0.30 + liquidez × 0.10 ≤ 0.40): el tramo se mide
    # TAMBIÉN con el factor relajado para ver que el escalado de tamaño es real y no teórico.
    restricted_relaxed = _tick(worker, equity=88_000.0, factor=1.2)

    # La pata NO REALIZADA de la equity entra en la medición: con una posición viva que cae,
    # el drawdown del gobernador la ve aunque la equity base no cambie.
    marks_positions = EquityMarkBook()
    holder_prices = {_SYMBOL: 100.0, "AAA": 100.0}
    holder = _worker(marks_positions, holder_prices)
    holder._open = {"AAA": Decimal("600")}  # noqa: SLF001 — estado del libro (evidencia).
    holder._entry_price = {"AAA": Decimal("100")}  # noqa: SLF001
    flat = _tick(holder, equity=100_000.0)  # fija la marca con la posición a precio de entrada
    holder_prices["AAA"] = 90.0  # −6 000 sobre 100 000 ⇒ 6 % ⇒ ENTRY_REDUCED
    marked = _tick(holder, equity=100_000.0)

    # Control de byte-identidad: el MISMO drawdown con el flag OFF no cambia nada.
    os.environ["AUTO_ENGINE_SIM_V2_GOVERNOR"] = "0"
    off_marks = EquityMarkBook()
    off_worker = _worker(off_marks, prices)
    off_flat = _tick(off_worker, equity=100_000.0)
    off_deep = _tick(off_worker, equity=78_000.0)
    os.environ["AUTO_ENGINE_SIM_V2_GOVERNOR"] = "1"

    return {
        "bump": "1.68.0-beta",
        "governorEnabled": tunables_from_env().governor_enabled,
        "baseline": baseline,
        "ladder": ladder,
        "restrictedRelaxedFactor": restricted_relaxed,
        "unrealizedLeg": {"flat": flat, "marked": marked},
        "flagOff": {"flat": off_flat, "deep": off_deep},
    }


def _scale(measured: dict[str, Any]) -> float | None:
    """Factor de escalado del gobernador: cantidad con el flag ON / cantidad del control."""
    quantity = measured["quantity"]
    control = measured["control"]["quantity"]
    if not quantity or not control:
        return None
    return quantity / control


def _approx(actual: float | None, expected: float, tolerance: float = 1e-3) -> bool:
    """Comparación numérica tolerante (``None`` nunca es "aproximadamente" nada)."""
    return actual is not None and abs(float(actual) - expected) <= tolerance


def verify(evidence: dict[str, Any]) -> list[str]:
    """Comprueba que la tabla GOBIERNA; devuelve los fallos (vacío si todo cuadra)."""
    failures: list[str] = []
    baseline = evidence["baseline"]

    if baseline["operationalState"] != "ENTRY_ALLOWED" or not baseline["approved"]:
        failures.append(f"sin drawdown la tabla no autoriza la entrada: {baseline}")
    if not _approx(_scale(baseline), 1.0):
        failures.append(f"ENTRY_ALLOWED no dejó el tamaño intacto: {baseline}")

    for drawdown, expected in _LADDER:
        measured = evidence["ladder"][str(drawdown)]
        if measured["operationalState"] != expected:
            failures.append(
                f"dd {drawdown}% resolvió {measured['operationalState']} (esperado {expected})"
            )
        if measured["governorStates"].get(_SYMBOL) != expected:
            failures.append(f"dd {drawdown}% no publicó el estado en el plan: {measured}")
        if measured["journalKeys"] != ["marketRegime", "operationalState", "riskRegime"]:
            failures.append(f"dd {drawdown}% no publicó las tres dimensiones: {measured}")
        if measured["marketRegime"] != "TREND_UP":
            failures.append(f"dd {drawdown}% perdió el hecho de mercado: {measured}")

    allowed = evidence["ladder"]["0.0"]
    reduced = evidence["ladder"]["6.0"]
    restricted = evidence["ladder"]["12.0"]
    exit_only = evidence["ladder"]["15.0"]
    halted = evidence["ladder"]["22.0"]

    if not allowed["approved"] or not _approx(_scale(allowed), 1.0):
        failures.append(f"ENTRY_ALLOWED no entró con el tamaño intacto: {allowed}")
    if not reduced["approved"] or not _approx(_scale(reduced), 0.75):
        failures.append(f"ENTRY_REDUCED no escaló al 75 %: {reduced}")
    if restricted["reasonCodes"] != ["edge_below_threshold"]:
        failures.append(f"ENTRY_RESTRICTED no subió el listón de edge: {restricted}")
    if not restricted["control"]["approved"]:
        failures.append(f"ENTRY_RESTRICTED no fue el gobernador quien vetó: {restricted}")
    if restricted["riskRegime"] != "RISK_REDUCING":
        failures.append(f"ENTRY_RESTRICTED no declaró RISK_REDUCING: {restricted}")
    if exit_only["approved"] or exit_only["reasonCodes"] != ["governor_exit_only"]:
        failures.append(f"EXIT_ONLY no vetó con su motivo: {exit_only}")
    if not exit_only["control"]["approved"]:
        failures.append(f"EXIT_ONLY no fue el gobernador quien vetó: {exit_only}")
    if halted["approved"] or halted["reasonCodes"] != ["governor_halted"]:
        failures.append(f"HALTED no vetó con su motivo: {halted}")
    if not halted["control"]["approved"]:
        failures.append(f"HALTED no fue el gobernador quien vetó: {halted}")

    relaxed = evidence["restrictedRelaxedFactor"]
    if relaxed["operationalState"] != "ENTRY_RESTRICTED" or not relaxed["approved"]:
        failures.append(f"RESTRICTED con factor relajado no entró: {relaxed}")
    elif not _approx(_scale(relaxed), 0.5):
        failures.append(f"RESTRICTED no escaló al 50 %: {relaxed}")

    leg = evidence["unrealizedLeg"]
    if leg["flat"]["drawdownPct"] != 0.0 or leg["flat"]["operationalState"] != "ENTRY_ALLOWED":
        failures.append(f"la marca plana no partió de 0 %: {leg['flat']}")
    if leg["marked"]["operationalState"] != "ENTRY_REDUCED":
        failures.append(f"la pérdida NO realizada no movió el gobernador: {leg['marked']}")

    off = evidence["flagOff"]
    if off["deep"]["reasonCodes"] != off["flat"]["reasonCodes"]:
        failures.append(f"con el flag OFF el drawdown cambió la decisión: {off}")
    if off["flat"]["quantity"] != baseline["quantity"]:
        failures.append(f"con el flag OFF el tamaño no es el histórico: {off['flat']}")
    if off["deep"]["journalKeys"] or off["deep"]["operationalState"] is not None:
        failures.append(f"con el flag OFF el journal no es el histórico: {off['deep']}")
    if off["deep"]["drawdownPct"] is not None:
        failures.append(f"con el flag OFF el drawdown no debería ni medirse: {off['deep']}")
    return failures


def main() -> int:
    import asyncio

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None, help="ruta del JSON de evidencia")
    args = parser.parse_args()

    evidence = asyncio.run(run_evidence())
    payload = json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)

    failures = verify(evidence)
    if failures:
        for failure in failures:
            print(f"FALLO: {failure}", file=sys.stderr)
        return 2
    print("OK: la tabla gobierna la decisión de entrada", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
