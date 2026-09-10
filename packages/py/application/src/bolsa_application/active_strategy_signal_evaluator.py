"""V2.29 / A10 — SignalEvaluator real para la estrategia ACTIVE (SIM-only).

Hasta V2.28 el ``DecisionProvider`` de la estrategia ACTIVE delegaba la ACCIÓN en el
spine determinista (``fallback``) y solo reescalaba el lote (P2 "SignalEvaluator real").
V2.29 permitió que la ACTIVE **evalúe su propia señal** sobre las últimas barras,
reutilizando el motor declarativo existente (``evaluate_strategy_last_bar``).

V2.31/A11 (P1-02): el contrato pasa a **fail-closed a NO TRADE**. Antes, si la ACTIVE
no podía evaluar su señal, el decisor heredaba la ACCIÓN del spine (otra estrategia),
lo que hacía que el AUTO pudiera operar con una lógica distinta a la estrategia que él
mismo había promocionado. Ahora:

* La ACTIVE evalúa su definición ejecutable ⇒ BUY/SELL/HOLD según su propia señal.
* Si no hay definición ejecutable, barras, snapshot, o la evaluación falla ⇒ **HOLD**
  (no se opera). Nunca se delega en otra estrategia.

Dos piezas:

* ``make_bar_snapshot_loader(ohlcv, symbols, limit)`` — carga async de las últimas N
  barras por símbolo. El decisor del worker es **síncrono**, así que el worker refresca
  este snapshot antes de cada turno y lo cierra sobre el ``DecisionProvider``.
* ``make_active_strategy_decider(...)`` — traduce la señal (``entry_long``/``exit``) a
  ``DecisionPackage``. **Fail-closed**: sin snapshot, sin ``executable`` o ante
  cualquier error de evaluación, devuelve HOLD (nunca inventa una orden ni hereda la
  de otra estrategia).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from bolsa_application.decision_contract import DecisionPackage

logger = logging.getLogger(__name__)

__all__ = [
    "BarSnapshotLoader",
    "make_active_strategy_decider",
    "make_bar_snapshot_loader",
]

# Tipo del cargador de barras: ``(instrument_id) -> list[close]`` (vacío si no hay).
BarSnapshotLoader = Callable[[str], "list[Any]"]


class _OhlcvPort(Protocol):
    async def get_bars(
        self,
        instrument_id: str,
        *,
        timeframe: Any = ...,
        limit: int | None = ...,
    ) -> list[Any]: ...


def make_bar_snapshot_loader(
    ohlcv: _OhlcvPort,
    symbols: Sequence[str],
    *,
    timeframe: Any = None,
    limit: int = 120,
) -> Callable[[], Any]:
    """Devuelve un ``refresh()`` async que precarga ``{symbol: [bars]}``.

    El worker lo invoca antes de cada turno (``auto_turn``) y guarda el resultado en un
    dict que cierra sobre el decisor síncrono. Un fallo por símbolo se ignora (ese
    símbolo se queda sin snapshot y el decisor hará HOLD), nunca aborta el refresco.
    """
    from bolsa_domain.value_objects.timeframe import TimeFrame

    effective_timeframe = timeframe if timeframe is not None else TimeFrame.D1

    async def refresh() -> dict[str, list[Any]]:
        snapshot: dict[str, list[Any]] = {}
        for symbol in symbols:
            try:
                bars = await ohlcv.get_bars(
                    symbol, timeframe=effective_timeframe, limit=limit
                )
            except Exception:  # noqa: BLE001 — sin barras ⇒ HOLD, no se rompe.
                logger.debug("signal evaluator: no bars for %s", symbol, exc_info=True)
                continue
            if bars:
                snapshot[str(symbol)] = list(bars)
        return snapshot

    return refresh


def _to_decision(
    *,
    symbol: str,
    signal_kind: str,
    lot_qty: float,
    source: str,
) -> DecisionPackage:
    """Traduce el tipo de señal a ``DecisionPackage`` (lote acotado al de la ACTIVE)."""
    if signal_kind == "entry_long":
        return DecisionPackage(
            action="BUY", instrument_id=symbol, quantity=lot_qty, source=source
        )
    if signal_kind == "exit":
        return DecisionPackage(
            action="SELL", instrument_id=symbol, quantity=lot_qty, source=source
        )
    return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0, source=source)


def make_active_strategy_decider(
    *,
    active: Any,
    watch: Sequence[str],
    bars_by_symbol: Callable[[str], list[Any]] | None = None,
    lot_qty: float = 100.0,
) -> Callable[[str], DecisionPackage]:
    """``DecisionProvider`` que evalúa la señal real de la ACTIVE (SIM-only).

    ``bars_by_symbol`` devuelve las barras ya cargadas para el símbolo (snapshot
    síncrono). Si no hay barras, si la definición no trae ``executable`` o si la
    evaluación falla, devuelve **HOLD** (fail-closed): la ACTIVE nunca ejecuta la
    lógica de otra estrategia (V2.31/A11, P1-02).
    """
    definition = dict(getattr(active, "definition", None) or {})
    executable = definition.get("executable")
    version_id = str(getattr(active, "version_id", "") or "")
    source = f"active-strategy:{version_id}"
    effective_lot = float(definition.get("lot_qty", lot_qty) or lot_qty)
    effective_watch = tuple(str(s) for s in (definition.get("watch") or watch))

    def _hold(symbol: str) -> DecisionPackage:
        return DecisionPackage(
            action="HOLD", instrument_id=symbol, quantity=0, source=source
        )

    def _decide(symbol: str) -> DecisionPackage:
        if symbol not in effective_watch:
            return _hold(symbol)
        if not isinstance(executable, dict) or bars_by_symbol is None:
            # Sin estrategia ejecutable: no se opera (no se delega en el spine).
            return _hold(symbol)
        try:
            bars = bars_by_symbol(symbol)
            if not bars:
                return _hold(symbol)
            signal_kind = _evaluate_last_signal(executable, bars, symbol)
        except Exception:  # noqa: BLE001 — una evaluación fallida no rompe el motor.
            logger.debug("signal evaluator failed for %s", symbol, exc_info=True)
            return _hold(symbol)
        if signal_kind is None:
            return _hold(symbol)
        effective = _bounded_lot(signal_kind, effective_lot)
        return _to_decision(
            symbol=symbol, signal_kind=signal_kind, lot_qty=effective, source=source
        )

    return _decide


def _bounded_lot(signal_kind: str, lot_qty: float) -> float:
    return lot_qty if signal_kind in {"entry_long", "exit"} else 0.0


def _evaluate_last_signal(
    executable: dict[str, Any],
    bars: list[Any],
    symbol: str,
) -> str | None:
    """Evalúa la última barra y devuelve el ``signalKind`` dominante (o ``None``).

    Se apoya en ``evaluate_strategy_last_bar`` (motor declarativo real). ``exit`` tiene
    prioridad sobre ``entry_long``: si en la misma barra hay ambas, cerrar es la acción
    conservadora.
    """
    from bolsa_analytics.signals.strategy import (
        StrategyBarInput,
        evaluate_strategy_last_bar,
    )

    bar_inputs = [
        StrategyBarInput(timestamp=str(getattr(b, "timestamp", "")), close=float(b.close))
        for b in bars
    ]
    if not bar_inputs:
        return None
    events = evaluate_strategy_last_bar(
        executable, bar_inputs, instrument_id=symbol, mode="gated"
    )
    kinds = {e.kind for e in events}
    if "exit" in kinds:
        return "exit"
    if "entry_long" in kinds:
        return "entry_long"
    return None
