"""V2.42.2 (slice 2c) — evidencia reproducible de un DÍA completo del motor AUTO.

Cierra el criterio de salida de ``AUTO-2`` con una MEDIDA, no con una impresión:

1. Corre un día hermético (sin PG) con tres posiciones que mueren por motivos distintos:
   ``time_exit`` (techo de mantenimiento congelado al nacer), ``thesis_exit`` (invalidación
   confirmada de la tesis) y ``structural_stop`` (stop-out, que NO se atribuye a la tesis).
2. Agrega el día con ``build_auto_daily_report`` (motivos de cierre + procedencia del ATR) y
   comprueba que el día es ``healthy``.
3. Sustituye la política de protección LEGACY por un contador y declara cuántas veces la leyó
   el camino ``AUTO_ENGINE_SIM_V2=1``: el criterio exige **cero**.

Uso (desde la raíz del repo):

    uv run python apps/api-python/scripts/v2_42_2_golden_day_evidence.py [--out RUTA.json]

El JSON que imprime es la evidencia que cita el audit-pack; ``--out`` lo guarda. El script
NO toca DB ni red: todo el día vive en memoria (stores ``InMemory*``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.auto_daily_journal import build_auto_daily_report
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV, EdgeReportSource
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore

_SYMBOLS = ("AAA", "BBB", "CCC")
_SECTORS = {"AAA": "tech", "BBB": "health", "CCC": "energy"}
_ATR = 2.0  # 2 % de 100 ⇒ stop estructural en 100 − 1.5×2 = 97.
_THESIS_LEVEL = 99.5  # por debajo del precio y por encima del stop (la invalida la tesis).
_STRUCTURAL_BREAK = 96.0  # rompe el stop (97): debe contarse como stop-out, no como tesis.


class _PolicySensor:
    """Contador de lecturas de la política legacy (el criterio exige CERO con V2 ON)."""

    def __init__(self) -> None:
        self.reads = 0

    def __call__(self, *_args: Any, **_kwargs: Any) -> None:
        self.reads += 1
        return None


async def _read_edge(_strategy_ref: str, _account_id: str | None) -> float | None:
    return 0.9


def _configure_env() -> None:
    os.environ.update(
        {
            "AUTO_ENGINE_SIMULATED_WATCH": ",".join(_SYMBOLS),
            "AUTO_ENGINE_SIMULATED_VENUE": "paper",
            "AUTO_SIMULATION_WORKER_ENABLED": "0",
            V2_ENGINE_ENV: "1",
            "AUTO_ENGINE_SIM_V2_REGIME": "BULL_TREND",
            "AUTO_ENGINE_SIM_V2_EQUITY": "100000",
        }
    )
    os.environ.pop("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", None)  # D3: el veto nace OFF.


def _decider(worker: AutoSimulationWorker, want: set[str]):
    def _d(symbol: str) -> DecisionPackage:
        if symbol in want and worker._open.get(symbol, Decimal("0")) <= 0:
            return DecisionPackage(action="BUY", instrument_id=symbol, quantity=250.0)
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


def _journal_codes(worker: AutoSimulationWorker) -> list[str]:
    return [
        code
        for entry in worker._v2_journal
        if entry.payload is not None and entry.event_type == "auto_position_management"
        for code in entry.payload["reasonCodes"]
    ]


async def _run_ticks(worker: AutoSimulationWorker, want: set[str], ticks: int = 6) -> None:
    for _ in range(ticks):
        worker._decider = _decider(worker, want)
        await worker.auto_turn()
        if want.issubset(set(worker.open_symbols)):
            return


async def _run_until_closed(worker: AutoSimulationWorker, symbol: str) -> None:
    for _ in range(6):
        worker._decider = _decider(worker, set())
        await worker.auto_turn()
        if worker._open.get(symbol, Decimal("0")) <= 0:
            return
    raise SystemExit(f"ERROR: la posición {symbol} no cerró (motivo no disparado)")


async def run_golden_day() -> dict[str, Any]:
    """Corre el día y devuelve la evidencia serializable (JSON-ready)."""
    import bolsa_api.background.auto_simulation_worker as worker_mod

    sensor = _PolicySensor()
    original_reason = worker_mod.protection_exit_reason
    original_fraction = worker_mod.protection_exit_fraction
    worker_mod.protection_exit_reason = sensor  # type: ignore[assignment]
    worker_mod.protection_exit_fraction = sensor  # type: ignore[assignment]

    prices = {symbol: 100.0 for symbol in _SYMBOLS}
    holder = {"now": datetime(2026, 9, 15, 9, 0, tzinfo=UTC)}
    try:
        return await _run_day_with_sensor(worker_mod, sensor, prices, holder)
    finally:
        worker_mod.protection_exit_reason = original_reason  # type: ignore[assignment]
        worker_mod.protection_exit_fraction = original_fraction  # type: ignore[assignment]


async def _run_day_with_sensor(
    worker_mod: Any,
    sensor: _PolicySensor,
    prices: dict[str, float],
    holder: dict[str, datetime],
) -> dict[str, Any]:
    worker = AutoSimulationWorker(
        clock=lambda: holder["now"],
        exec_store=InMemoryExecutionEventStore(),
        sector_source=lambda symbol: _SECTORS.get(symbol),
        liquidity_source=lambda _symbol: 1_000_000.0,
        edge_source=EdgeReportSource(reader=_read_edge),
        price_script=lambda symbol, _minute: prices[symbol],
        atr_source=lambda _symbol: _ATR,
    )

    await _run_ticks(worker, set(_SYMBOLS))
    opened = sorted(worker.open_symbols)
    if set(opened) != set(_SYMBOLS):
        raise SystemExit(f"ERROR: el día no abrió las tres posiciones (abiertas: {opened})")

    born_bbb = worker._v2_positions["BBB"]
    worker._v2_positions["BBB"] = replace(born_bbb, invalidation_price=_THESIS_LEVEL)
    deadline_aaa = worker._v2_positions["AAA"].holding_deadline_at

    prices["BBB"] = 99.0  # atraviesa la tesis sin tocar el stop.
    await _run_until_closed(worker, "BBB")
    prices["BBB"] = 100.0

    prices["CCC"] = _STRUCTURAL_BREAK  # rompe el stop estructural.
    await _run_until_closed(worker, "CCC")
    prices["CCC"] = 100.0

    holder["now"] = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)  # pasado el techo congelado.
    await _run_until_closed(worker, "AAA")

    report = build_auto_daily_report(
        rows=worker.journal_pairs(),
        atr_sources=worker.atr_source_counts(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    day = report.as_dict()
    atr = dict(report.atr_sources)
    signals = sum(atr.values())
    real = atr.get("real", 0)
    return {
        "bump": "1.67.2-beta",
        "day": day,
        "positions": {
            symbol: {
                "exit": next(
                    (
                        row.reason
                        for row in worker.journal_pairs()
                        if row.kind == "position_close" and symbol in row.execution_id
                    ),
                    None,
                ),
            }
            for symbol in _SYMBOLS
        },
        "holding_deadline_at": deadline_aaa,
        "journal_codes": sorted(set(_journal_codes(worker))),
        "legacy_policy_reads": sensor.reads,
        "atr": {
            "sources": atr,
            "signals": signals,
            "real_share_pct": round(100.0 * real / signals, 2) if signals else None,
            "veto": os.getenv("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", "0") or "0",
        },
        "open_symbols_at_close": sorted(worker.open_symbols),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None, help="ruta del JSON de evidencia")
    args = parser.parse_args()

    _configure_env()
    evidence = asyncio.run(run_golden_day())
    payload = json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)

    # Un día completo del criterio de AUTO-2: los tres motivos, sano y sin política legacy.
    expected = {"time_exit": 1, "thesis_exit": 1, "structural_stop": 1}
    if evidence["day"]["exit_reasons"] != expected:
        print(f"FALLO: motivos inesperados {evidence['day']['exit_reasons']}", file=sys.stderr)
        return 2
    if not evidence["day"]["healthy"]:
        print(f"FALLO: día no sano {evidence['day']['errors']}", file=sys.stderr)
        return 2
    if evidence["legacy_policy_reads"] != 0:
        print(
            f"FALLO: el camino V2 leyó la política legacy "
            f"{evidence['legacy_policy_reads']} veces",
            file=sys.stderr,
        )
        return 2
    if evidence["atr"]["sources"].get("real", 0) <= 0:
        print("FALLO: el día no midió ninguna señal con ATR real", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
