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

from bolsa_application.decision_contract import (
    DecisionPackage,
    format_active_strategy_source,
)
from bolsa_application.signal_feature_context import feature_source

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
    feature_source: str | None = None,
    signal_window_bars: int | None = None,
) -> DecisionPackage:
    """Traduce el tipo de señal a ``DecisionPackage`` (lote acotado al de la ACTIVE)."""
    if signal_kind == "entry_long":
        return DecisionPackage(
            action="BUY",
            instrument_id=symbol,
            quantity=lot_qty,
            source=source,
            feature_source=feature_source,
            signal_window_bars=signal_window_bars,
        )
    if signal_kind == "exit":
        return DecisionPackage(
            action="SELL",
            instrument_id=symbol,
            quantity=lot_qty,
            source=source,
            feature_source=feature_source,
            signal_window_bars=signal_window_bars,
        )
    return DecisionPackage(
        action="HOLD",
        instrument_id=symbol,
        quantity=0,
        source=source,
        feature_source=feature_source,
        signal_window_bars=signal_window_bars,
    )


def make_active_strategy_decider(
    *,
    active: Any,
    watch: Sequence[str],
    bars_by_symbol: Callable[[str], list[Any]] | None = None,
    lot_qty: float = 100.0,
    long_by_symbol: Callable[[str], bool] | None = None,
) -> Callable[[str], DecisionPackage]:
    """``DecisionProvider`` que evalúa la señal real de la ACTIVE (SIM-only).

    ``bars_by_symbol`` devuelve las barras ya cargadas para el símbolo (snapshot
    síncrono). Si no hay barras, si la definición no trae ``executable`` o si la
    evaluación falla, devuelve **HOLD** (fail-closed): la ACTIVE nunca ejecuta la
    lógica de otra estrategia (V2.31/A11, P1-02).

    ``long_by_symbol`` (B-3) devuelve si el **libro real** tiene posición larga abierta
    en ese símbolo. Con él, el motor arranca el estado ``gated`` con la posición abierta
    en vez de replayar la ventana desde cero: así una salida se emite aunque no haya
    entrada en la ventana (la posición pudo abrirse antes). Sin él se conserva el replay
    —comportamiento previo— y el contrato ``raw``/``gated`` queda como estaba.

    Un fallo de ``long_by_symbol`` cae en el mismo ``except`` que los demás: **HOLD**,
    nunca una venta inventada ni una venta silenciada.
    """
    definition = dict(getattr(active, "definition", None) or {})
    executable = definition.get("executable")
    version_id = str(getattr(active, "version_id", "") or "")
    # H1: la fuente transporta la identidad exacta (preset_key) si la ACTIVE la tiene.
    source = format_active_strategy_source(version_id, getattr(active, "preset_key", None))
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
            assume_long = bool(long_by_symbol(symbol)) if long_by_symbol is not None else False
            signal_kind, warmup_reason = _evaluate_last_signal(
                executable, bars, symbol, assume_long=assume_long
            )
        except Exception:  # noqa: BLE001 — una evaluación fallida no rompe el motor.
            logger.debug("signal evaluator failed for %s", symbol, exc_info=True)
            return _hold(symbol)
        # O-6: la procedencia de la feature y el tamaño de la ventana se declaran en TODA
        # decisión que llegue a evaluar barras —incluido el HOLD—, porque es justo el HOLD
        # el que hoy no se puede leer: «no había señal» y «la ventana no alcanza» eran la
        # misma fila. Sin barras no se declara nada: no se evaluó, y eso no es "synthetic".
        declared_source = feature_source(bars)
        window_bars = len(bars)
        if warmup_reason is not None:
            # B-1: la ventana no alcanza el warmup del preset. Se sigue en HOLD
            # (fail-closed), pero el motivo viaja en ``memo``: un HOLD por falta de
            # datos **no** es un HOLD por ausencia de señal, y hasta ahora se leían
            # igual. El artefacto de decisión lo declara en vez de callarlo.
            logger.info("signal evaluator %s: %s", symbol, warmup_reason)
            return DecisionPackage(
                action="HOLD",
                instrument_id=symbol,
                quantity=0,
                source=source,
                memo=warmup_reason,
                feature_source=declared_source,
                signal_window_bars=window_bars,
            )
        if signal_kind is None:
            return DecisionPackage(
                action="HOLD",
                instrument_id=symbol,
                quantity=0,
                source=source,
                feature_source=declared_source,
                signal_window_bars=window_bars,
            )
        effective = _bounded_lot(signal_kind, effective_lot)
        return _to_decision(
            symbol=symbol,
            signal_kind=signal_kind,
            lot_qty=effective,
            source=source,
            feature_source=declared_source,
            signal_window_bars=window_bars,
        )

    return _decide


def _bounded_lot(signal_kind: str, lot_qty: float) -> float:
    return lot_qty if signal_kind in {"entry_long", "exit"} else 0.0


def _evaluate_last_signal(
    executable: dict[str, Any],
    bars: list[Any],
    symbol: str,
    *,
    assume_long: bool = False,
) -> tuple[str | None, str | None]:
    """Evalúa la última barra y devuelve ``(signalKind dominante | None, motivo | None)``.

    Se apoya en ``evaluate_strategy_last_bar`` (motor declarativo real). ``exit`` tiene
    prioridad sobre ``entry_long``: si en la misma barra hay ambas, cerrar es la acción
    conservadora.

    El ``indicator_context`` se construye con las MISMAS barras OHLCV que usa el scan
    (``signal_feature_context``). Sin él, el motor sintetiza ``open = high = low = close`` y
    ``volume = 0``, y el decisor evalúa una señal distinta de la que el scan publica sobre
    las mismas barras: el banco de contrato mide **5 de 16 acciones** distintas en presets de
    volumen/rango. El modo sigue siendo ``gated``: el contrato es la **proyección** del scan,
    no el scan.

    **B-1.** Antes de evaluar se pregunta si la ventana alcanza el warmup del preset. Si no
    alcanza, el segundo elemento trae el motivo ``warmup_insufficient`` y el decisor lo
    publica: la ventana por defecto (120 barras) **no es evaluable** para SMA200 ni para
    los cruces de 50/200, y devolver ``None`` sin más los confundía con «sin señal».

    **B-3.** ``assume_long`` arranca el replay ``gated`` con la posición del libro real. Sin
    él, una posición abierta antes de la ventana no ve su entrada y la salida se suprime.
    """
    from bolsa_analytics.signals.preset_evaluability import evaluability_reason
    from bolsa_analytics.signals.strategy import (
        StrategyBarInput,
        evaluate_strategy_last_bar,
    )
    from bolsa_application.signal_feature_context import build_signal_indicator_context
    bar_inputs = [
        StrategyBarInput(timestamp=str(getattr(b, "timestamp", "")), close=float(b.close))
        for b in bars
    ]
    if not bar_inputs:
        return None, None
    indicator_context = build_signal_indicator_context(bars, executable)
    warmup_reason = evaluability_reason(
        executable,
        indicator_context or {},
        bar_count=len(bar_inputs),
    )
    if warmup_reason is not None:
        return None, warmup_reason
    events = evaluate_strategy_last_bar(
        executable,
        bar_inputs,
        instrument_id=symbol,
        mode="gated",
        indicator_context=indicator_context or None,
        assume_long=assume_long,
    )
    kinds = {e.kind for e in events}
    if assume_long:
        # Estamos DENTRO. La única acción con sentido es cerrar, y la pregunta de salida
        # es de NIVEL, no de transición (B-3): con la posición abierta antes de la
        # ventana, el replay ya consumió la transición al principio y en la última barra
        # no queda ningún ``exit`` que emitir. Se pregunta a la regla de salida en la
        # última barra con el contexto REAL (no se reutiliza
        # ``evaluate_exit_last_bar_gated``, que reconstruye barras sintéticas close-only
        # y perdería volumen/rango).
        if "exit" in kinds or _exit_rule_holds(executable, bars, indicator_context):
            return "exit", None
        # Sin salida: no se vuelve a comprar lo que ya se tiene.
        return None, None
    if "exit" in kinds:
        return "exit", None
    if "entry_long" in kinds:
        return "entry_long", None
    return None, None


def _exit_rule_holds(
    executable: dict[str, Any],
    bars: list[Any],
    indicator_context: dict[str, list[float | None]] | None,
) -> bool:
    """¿La regla de SALIDA se cumple en la última barra? (pregunta de nivel, B-3).

    Usa el ``indicator_context`` real, de modo que la salida de un preset de volumen o
    rango se decide con las mismas series que el scan. Un contexto vacío no inventa una
    venta: el motor devuelve ``None`` para las reglas que dependen de series, así que el
    resultado es el mismo ``False`` sin cortar antes las reglas que solo miran ``close``.
    """
    from bolsa_analytics.signals.preset_rules import enrich_definition_with_preset_rules
    from bolsa_analytics.signals.rules_engine import evaluate_rules_bar

    closes = [float(bar.close) for bar in bars]
    if not closes:
        return False
    resolved = enrich_definition_with_preset_rules(executable)
    kind = evaluate_rules_bar(
        resolved,
        index=len(closes) - 1,
        context=indicator_context or {},
        closes=closes,
        side="exits",
    )
    return kind == "exit"
