"""V2.28 / A10 (P1-02 real) — tests del cálculo puro de métricas observadas.

Verifican la contabilidad FIFO de round-trips y las métricas derivadas, además de la
guarda de muestra mínima: sin evidencia suficiente NO se emite señal (fail-closed).
"""

from __future__ import annotations

from decimal import Decimal

from bolsa_application.strategy_observed_metrics import (
    MIN_TRADES_DEFAULT,
    compute_observed_metrics,
    compute_observed_metrics_from_fills,
)


def _buy(qty: str, price: str) -> tuple[str, Decimal, Decimal]:
    return ("buy", Decimal(qty), Decimal(price))


def _sell(qty: str, price: str) -> tuple[str, Decimal, Decimal]:
    return ("sell", Decimal(qty), Decimal(price))


def test_single_winning_round_trip() -> None:
    metrics = compute_observed_metrics(
        [_buy("10", "100"), _sell("10", "110")],
        min_trades=1,
    )
    assert metrics.trades == 1
    assert metrics.realized_pnl == Decimal("100")
    assert metrics.return_pct == 10.0
    assert metrics.win_rate == 1.0
    assert metrics.max_drawdown_pct == 0.0


def test_single_losing_round_trip() -> None:
    metrics = compute_observed_metrics(
        [_buy("10", "100"), _sell("10", "90")],
        min_trades=1,
    )
    assert metrics.realized_pnl == Decimal("-100")
    assert metrics.return_pct == -10.0
    assert metrics.win_rate == 0.0
    assert metrics.max_drawdown_pct == 10.0


def test_partial_sell_realizes_fifo_then_rest() -> None:
    metrics = compute_observed_metrics(
        [
            _buy("10", "100"),
            _sell("5", "120"),  # +100
            _sell("5", "80"),  # -100
        ],
        min_trades=1,
    )
    assert metrics.trades == 2
    assert metrics.realized_pnl == Decimal("0")
    assert metrics.win_rate == 0.5


def test_sell_beyond_open_is_ignored() -> None:
    metrics = compute_observed_metrics(
        [_buy("5", "100"), _sell("50", "110")],
        min_trades=1,
    )
    # El exceso no fabrica una venta en corto: solo se realiza lo abierto.
    assert metrics.trades == 1
    assert metrics.realized_pnl == Decimal("50")


def test_profit_factor_and_drawdown() -> None:
    metrics = compute_observed_metrics(
        [
            _buy("1", "100"),
            _sell("1", "120"),  # +20 (pico 20)
            _buy("1", "100"),
            _sell("1", "60"),  # -40 (equity -20)
            _buy("1", "100"),
            _sell("1", "130"),  # +30 (equity 10)
        ],
        min_trades=1,
    )
    assert metrics.trades == 3
    assert metrics.win_rate == 2 / 3
    # Ganancias brutas 50 / pérdidas brutas 40.
    assert metrics.profit_factor == 1.25
    # Capital comprometido 300; caída de pico 20 a -20 = 40/300 ≈ 13.33%.
    assert metrics.max_drawdown_pct is not None
    assert abs(metrics.max_drawdown_pct - (40.0 / 300.0) * 100.0) < 1e-9


def test_profit_factor_none_without_losses() -> None:
    """Sin pérdidas el profit factor es indefinido (no ``inf``: no es JSON-safe)."""
    metrics = compute_observed_metrics(
        [_buy("1", "100"), _sell("1", "110")],
        min_trades=1,
    )
    assert metrics.profit_factor is None


def test_as_metrics_enforces_min_trades_guard() -> None:
    metrics = compute_observed_metrics(
        [_buy("1", "100"), _sell("1", "110")],
        min_trades=MIN_TRADES_DEFAULT,
    )
    # Un solo round-trip no alcanza la muestra mínima: sin señal.
    assert metrics.as_metrics() == {}


def test_as_metrics_emits_when_sample_is_sufficient() -> None:
    fills: list[tuple[str, Decimal, Decimal]] = []
    for _ in range(3):
        fills.append(_buy("1", "100"))
        fills.append(_sell("1", "110"))
    metrics = compute_observed_metrics(fills, min_trades=3)
    payload = metrics.as_metrics(min_trades=3)
    assert payload["observed_trades"] == 3
    assert payload["observed_return_pct"] == 10.0
    assert payload["observed_win_rate"] == 1.0
    assert payload["observed_max_drawdown_pct"] == 0.0


def test_from_fills_ignores_invalid_rows() -> None:
    class _Fill:
        def __init__(self, side: str, qty: str, price: str) -> None:
            self.side = side
            self.quantity = Decimal(qty)
            self.price = Decimal(price)

    result = compute_observed_metrics_from_fills(
        [
            _Fill("buy", "1", "100"),
            _Fill("sideways", "1", "100"),  # lado inválido
            _Fill("sell", "0", "110"),  # cantidad no positiva
            _Fill("sell", "1", "110"),
        ],
        min_trades=1,
    )
    assert result is not None
    assert result.trades == 1
    assert result.realized_pnl == Decimal("10")


def test_from_fills_empty_returns_none() -> None:
    assert compute_observed_metrics_from_fills([]) is None
