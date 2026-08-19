"""Cálculo de plusvalías realizadas (FIFO / coste medio)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from bolsa_domain.entities.account import LedgerEntry


@dataclass(frozen=True, slots=True)
class TaxReportTransaction:
    id: str
    type: str
    instrument_id: str
    symbol: str
    quantity: float
    price: float
    total: float
    executed_at: str
    fee_amount: float = 0.0


@dataclass(frozen=True, slots=True)
class RealizedGainLine:
    id: str
    instrument_id: str
    symbol: str
    sell_transaction_id: str
    executed_at: str
    quantity: float
    sell_price: float
    proceeds: float
    cost_basis: float
    realized_gain: float
    method: str
    acquisition_dates: list[str]


@dataclass(frozen=True, slots=True)
class UnrealizedGainLine:
    instrument_id: str
    symbol: str
    quantity: float
    avg_cost: float
    market_price: float | None
    cost_basis: float
    market_value: float | None
    unrealized_gain: float | None


@dataclass(frozen=True, slots=True)
class TaxReportSummary:
    account_id: str
    currency: str
    method: str
    jurisdiction: str
    year: int
    period_label: str
    realized_lines: list[RealizedGainLine]
    total_gains: float
    total_losses: float
    net_realized_gain: float
    estimated_tax_liability: float | None
    unrealized_lines: list[UnrealizedGainLine]
    total_unrealized_gain: float | None
    fees_paid_total: float
    dividend_withholding_pct: float
    open_position_count: int


def _sort_tx(transactions: list[TaxReportTransaction]) -> list[TaxReportTransaction]:
    return sorted(transactions, key=lambda t: t.executed_at)


def _fifo_realized(transactions: list[TaxReportTransaction]) -> list[RealizedGainLine]:
    lots: dict[str, list[dict[str, Any]]] = {}
    lines: list[RealizedGainLine] = []

    for tx in _sort_tx(transactions):
        lots.setdefault(tx.instrument_id, [])
        if tx.type == "buy":
            fee = tx.fee_amount
            lots[tx.instrument_id].append(
                {
                    "quantity": tx.quantity,
                    "unit_cost": (tx.total + fee) / tx.quantity,
                    "acquired_at": tx.executed_at,
                }
            )
            continue

        remaining = tx.quantity
        sell_fee = tx.fee_amount
        proceeds_total = tx.total - sell_fee
        acquisition_dates: list[str] = []
        cost_basis = 0.0
        queue = lots[tx.instrument_id]

        while remaining > 1e-9 and queue:
            lot = queue[0]
            take = min(remaining, lot["quantity"])
            cost_basis += take * lot["unit_cost"]
            acquisition_dates.append(lot["acquired_at"])
            lot["quantity"] -= take
            remaining -= take
            if lot["quantity"] <= 1e-9:
                queue.pop(0)

        lines.append(
            RealizedGainLine(
                id=tx.id,
                instrument_id=tx.instrument_id,
                symbol=tx.symbol,
                sell_transaction_id=tx.id,
                executed_at=tx.executed_at,
                quantity=tx.quantity,
                sell_price=tx.price,
                proceeds=proceeds_total,
                cost_basis=cost_basis,
                realized_gain=proceeds_total - cost_basis,
                method="fifo",
                acquisition_dates=acquisition_dates,
            )
        )
    return lines


def _average_realized(transactions: list[TaxReportTransaction]) -> list[RealizedGainLine]:
    state: dict[str, dict[str, float]] = {}
    lines: list[RealizedGainLine] = []

    for tx in _sort_tx(transactions):
        state.setdefault(tx.instrument_id, {"quantity": 0.0, "total_cost": 0.0})
        holding = state[tx.instrument_id]

        if tx.type == "buy":
            holding["total_cost"] += tx.total + tx.fee_amount
            holding["quantity"] += tx.quantity
            continue

        avg_cost = holding["total_cost"] / holding["quantity"] if holding["quantity"] > 0 else 0.0
        sell_fee = tx.fee_amount
        proceeds = tx.total - sell_fee
        cost_basis = avg_cost * tx.quantity
        holding["total_cost"] = max(0.0, holding["total_cost"] - cost_basis)
        holding["quantity"] = max(0.0, holding["quantity"] - tx.quantity)

        lines.append(
            RealizedGainLine(
                id=tx.id,
                instrument_id=tx.instrument_id,
                symbol=tx.symbol,
                sell_transaction_id=tx.id,
                executed_at=tx.executed_at,
                quantity=tx.quantity,
                sell_price=tx.price,
                proceeds=proceeds,
                cost_basis=cost_basis,
                realized_gain=proceeds - cost_basis,
                method="average",
                acquisition_dates=[],
            )
        )
    return lines


def _compute_realized_gains(
    transactions: list[TaxReportTransaction],
    method: str,
) -> list[RealizedGainLine]:
    if method == "average":
        return _average_realized(transactions)
    return _fifo_realized(transactions)


def _is_in_fiscal_year(iso_date: str, year: int, start_month: int) -> bool:
    dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
    month = dt.month
    calendar_year = dt.year
    if start_month == 1:
        return calendar_year == year
    if month >= start_month:
        return calendar_year == year
    return calendar_year == year + 1


def fiscal_year_range(year: int, start_month: int) -> tuple[datetime, datetime]:
    """Devuelve [inicio, fin) del ejercicio fiscal ``year`` como datetimes UTC.

    Replica la semántica de ``_is_in_fiscal_year``: si ``start_month == 1`` el
    ejercicio coincide con el año natural; en otro caso, comienza el día 1 de
    ``start_month`` del año y termina el día 1 de ``start_month`` de ``year + 1``.
    Es la fuente canónica del rango que los repos aplican en SQL, de modo que el
    filtro en BD y el predicado de dominio jamás divergen.
    """
    start = datetime(year, start_month, 1, tzinfo=UTC)
    end = datetime(year + 1, start_month, 1, tzinfo=UTC)
    return start, end


def _period_label(year: int, start_month: int) -> str:
    if start_month == 1:
        return f"Año natural {year}"
    return f"Ejercicio {year}/{(year + 1) % 100:02d}"


def map_ledger_fees_to_transactions(entries: list[LedgerEntry]) -> dict[str, float]:
    result: dict[str, float] = {}
    for entry in entries:
        if entry.type != "fee" or not entry.reference_id:
            continue
        result[entry.reference_id] = result.get(entry.reference_id, 0.0) + abs(entry.amount)
    return result


def build_tax_report(
    *,
    account_id: str,
    currency: str,
    method: str,
    jurisdiction: str,
    year: int,
    transactions: list[TaxReportTransaction],
    fees_by_transaction_id: dict[str, float] | None = None,
    positions: list[UnrealizedGainLine] | None = None,
    fiscal_year_start_month: int = 1,
    capital_gains_tax_pct: float | None = None,
    dividend_withholding_pct: float = 0.0,
) -> TaxReportSummary:
    fees_map = fees_by_transaction_id or {}
    report_tx = [
        TaxReportTransaction(
            id=tx.id,
            type=tx.type,
            instrument_id=tx.instrument_id,
            symbol=tx.symbol,
            quantity=tx.quantity,
            price=tx.price,
            total=tx.total,
            executed_at=tx.executed_at,
            fee_amount=fees_map.get(tx.id, 0.0),
        )
        for tx in transactions
    ]

    all_realized = _compute_realized_gains(report_tx, method)
    realized_lines = [
        line
        for line in all_realized
        if _is_in_fiscal_year(line.executed_at, year, fiscal_year_start_month)
    ]

    total_gains = sum(line.realized_gain for line in realized_lines if line.realized_gain >= 0)
    total_losses = sum(line.realized_gain for line in realized_lines if line.realized_gain < 0)
    net_realized_gain = total_gains + total_losses
    # F-FIN-2: Fees del EJERCICIO, no de todo el historial. `report_tx` puede incluir
    # transacciones de ejercicios anteriores (carry-in de lots FIFO/avg) cuyo fee no
    # pertenece al año pedido.
    fees_paid_total = sum(
        tx.fee_amount
        for tx in report_tx
        if _is_in_fiscal_year(tx.executed_at, year, fiscal_year_start_month)
    )

    unrealized_lines = positions or []
    total_unrealized_gain = (
        sum(line.unrealized_gain or 0.0 for line in unrealized_lines)
        if unrealized_lines
        else None
    )

    estimated_tax = None
    if capital_gains_tax_pct is not None and capital_gains_tax_pct > 0 and net_realized_gain > 0:
        estimated_tax = net_realized_gain * capital_gains_tax_pct / 100

    return TaxReportSummary(
        account_id=account_id,
        currency=currency,
        method=method,
        jurisdiction=jurisdiction,
        year=year,
        period_label=_period_label(year, fiscal_year_start_month),
        realized_lines=realized_lines,
        total_gains=total_gains,
        total_losses=total_losses,
        net_realized_gain=net_realized_gain,
        estimated_tax_liability=estimated_tax,
        unrealized_lines=unrealized_lines,
        total_unrealized_gain=total_unrealized_gain,
        fees_paid_total=fees_paid_total,
        dividend_withholding_pct=dividend_withholding_pct,
        open_position_count=len(unrealized_lines),
    )
