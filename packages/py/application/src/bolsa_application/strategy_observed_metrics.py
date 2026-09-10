"""V2.28 / A10 (P1-02 real) — métricas *observadas* de la estrategia ACTIVA desde fills SIM.

La vigilancia (``strategy_vigilance_phase``) sabía comparar indicadores *predictivos* de
robustez (``edge``/``wfe``/``dsr``/``credibility``, del LAB) contra umbrales, pero el
orquestador la invocaba con ``metrics={}``: no había ninguna señal de lo que estaba
pasando de verdad con la ejecución simulada.

Aquí se calcula esa señal a partir de los fills **atribuidos a una versión**
(``sim_fill_finance_context.strategy_version_id``, migración 031): se reconstruye el
ciclo económico (compras/ventas), se realizan los PnL por round-trip y se derivan:

* ``observed_return_pct``       — retorno sobre el capital comprometido.
* ``observed_max_drawdown_pct`` — máxima caída de la curva de equity realizada.
* ``observed_win_rate``         — fracción de round-trips ganadores.
* ``observed_profit_factor``    — ganancias brutas / pérdidas brutas.
* ``observed_trades``           — nº de round-trips cerrados (guarda de muestra mínima).

Diseño:
* **Puro y determinista**: sin DB, sin red, sin reloj. Entra una secuencia de fills, sale
  un dict de métricas. Trivial de testear y de auditar.
* **Fail-closed / honesto**: con menos de ``min_trades`` round-trips cerrados devuelve un
  dict *vacío* (no se inventa evidencia con una muestra anecdótica); el llamante decide.
* **Sold-out only**: los round-trips se cierran al vender contra posición; el resultado se
  realiza FIFO sobre la cantidad abierta. Si una venta supera lo abierto, se ignora el
  exceso (no se fabrica una venta en corto).
* Los fills se procesan en el orden recibido (el store los devuelve en orden temporal).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

__all__ = [
    "MIN_TRADES_DEFAULT",
    "ObservedMetrics",
    "compute_observed_metrics",
    "compute_observed_metrics_from_fills",
]


# Muestra mínima por defecto para que las métricas observadas sean decisorias.
MIN_TRADES_DEFAULT = 10


@dataclass(frozen=True, slots=True)
class ObservedMetrics:
    """Métricas observadas de una versión + los round-trips que las sustentan."""

    trades: int
    realized_pnl: Decimal
    committed_capital: Decimal
    return_pct: float | None
    max_drawdown_pct: float | None
    win_rate: float | None
    profit_factor: float | None

    def as_metrics(self, *, min_trades: int = MIN_TRADES_DEFAULT) -> dict[str, Any]:
        """Dict listo para ``evaluate_active_health``.

        Con menos de ``min_trades`` round-trips cerrados devuelve ``{}``: sin evidencia
        suficiente NO se emite señal (el observado es informativo, no decisorio). El
        guard de muestra se materializa además en ``StrategyHealth`` vía
        ``min_observed_trades``, de modo que ambos caminos coinciden.
        """
        if self.trades < max(1, min_trades):
            return {}
        return {
            "observed_return_pct": self.return_pct,
            "observed_max_drawdown_pct": self.max_drawdown_pct,
            "observed_win_rate": self.win_rate,
            "observed_profit_factor": self.profit_factor,
            "observed_trades": self.trades,
        }


def compute_observed_metrics_from_fills(
    fills: Iterable[Any],
    *,
    min_trades: int = MIN_TRADES_DEFAULT,
) -> ObservedMetrics | None:
    """Igual que ``compute_observed_metrics`` pero tomando objetos con ``side``/``quantity``/
    ``price`` (p. ej. ``SimFillFinanceContext``). Devuelve ``None`` si no hay fills.
    """
    triples: list[tuple[str, Decimal, Decimal]] = []
    for fill in fills:
        side = str(getattr(fill, "side", "") or "").strip().lower()
        if side not in {"buy", "sell"}:
            continue
        try:
            qty = Decimal(str(getattr(fill, "quantity", 0) or 0))
            price = Decimal(str(getattr(fill, "price", 0) or 0))
        except Exception:  # noqa: BLE001 — un fill ilegible no debe romper la vigilancia.
            continue
        if qty <= 0 or price <= 0:
            continue
        triples.append((side, qty, price))
    if not triples:
        return None
    return compute_observed_metrics(triples, min_trades=min_trades)


def compute_observed_metrics(
    fills: Iterable[tuple[str, Decimal, Decimal]],
    *,
    min_trades: int = MIN_TRADES_DEFAULT,
) -> ObservedMetrics:
    """Calcula métricas observadas a partir de ``(side, quantity, price)`` en orden temporal.

    Contabilidad FIFO por símbolo-agnóstica (el llamante ya filtra por versión; se asume
    una única línea de ejecución por versión, que es el caso del motor AUTO por
    instrumento). Cada venta que cruza una compra realiza un round-trip.
    """
    open_lots: deque[tuple[Decimal, Decimal]] = deque()  # (qty, price)
    committed = Decimal("0")  # capital inmovilizado acumulado (coste de compras no cerradas)
    round_trips: list[Decimal] = []
    realized_total = Decimal("0")
    committed_total = Decimal("0")

    for side, qty, price in fills:
        if side == "buy":
            open_lots.append((qty, price))
            committed += qty * price
            continue
        # sell: realiza FIFO contra lo abierto; el exceso se ignora (no hay cortos).
        remaining = qty
        while remaining > 0 and open_lots:
            lot_qty, lot_price = open_lots[0]
            matched = min(remaining, lot_qty)
            pnl = (price - lot_price) * matched
            round_trips.append(pnl)
            realized_total += pnl
            committed_total += lot_price * matched
            committed -= lot_price * matched
            remaining -= matched
            if matched == lot_qty:
                open_lots.popleft()
            else:
                open_lots[0] = (lot_qty - matched, lot_price)

    if committed < 0:  # pragma: no cover — defensa: la aritmética no debe dejar negativo.
        committed = Decimal("0")

    # Drawdown de la curva de equity realizada. El equity arranca en 0, así que usar el
    # pico como denominador fallaría en la PRIMERA pérdida (pico=0 ⇒ sin drawdown, que es
    # absurdo). Se normaliza contra el capital comprometido total, que es una base
    # positiva y estable: una pérdida de 100 sobre 1000 de capital es un drawdown del 10%.
    running = Decimal("0")
    peak = Decimal("0")
    max_dd_pct = 0.0
    for pnl in round_trips:
        running += pnl
        if running > peak:
            peak = running
        if committed_total > 0:
            dd = float((peak - running) / committed_total) * 100.0
            if dd > max_dd_pct:
                max_dd_pct = dd

    trades = len(round_trips)
    wins = sum(1 for pnl in round_trips if pnl > 0)
    gross_profit = sum((pnl for pnl in round_trips if pnl > 0), Decimal("0"))
    gross_loss = -sum((pnl for pnl in round_trips if pnl < 0), Decimal("0"))

    return_pct: float | None = None
    if committed_total > 0:
        return_pct = float(realized_total / committed_total) * 100.0
    win_rate = (wins / trades) if trades > 0 else None
    if gross_loss > 0:
        profit_factor: float | None = float(gross_profit / gross_loss)
    else:
        # Sin pérdidas el profit factor es matemáticamente indefinido (∞). Se devuelve
        # ``None`` en vez de ``float("inf")``: ``inf`` no es JSON-serializable (rompería
        # el snapshot de salud en PG) ni comparable de forma útil contra un umbral.
        profit_factor = None

    return ObservedMetrics(
        trades=trades,
        realized_pnl=realized_total,
        committed_capital=committed_total,
        return_pct=return_pct,
        max_drawdown_pct=max_dd_pct if trades > 0 else None,
        win_rate=win_rate,
        profit_factor=profit_factor,
    )
