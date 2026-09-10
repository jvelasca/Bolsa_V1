"""V2.22 / A9 (M7) — Journal / diario AUTO (build puro + invariantes SIM-ONLY).

Build puro de la síntesis diaria del motor AUTO tras la simulación de un día
autónomo. Dado el recorrido de una sesión (órdenes, fills, posiciones abiertas/
cerradas, trazas de ejecución, venues y balances netos) devuelve el resumen y
evalúa los invariantes que el audit exige a un día AUTO sano:

  orders > 0, fills > 0, positions_created > 0, exits > 0,
  ledger_balanced (assert_equity_invariant del dominio o par (delta_cash,
  Σledger)), no_duplicate_execution_events, all_venues ⊆ {paper, simulated},
  no_live_bridge_posts (AUTO jamás toca el bridge LIVE).

El módulo es **puro/estructural**: no toca DB ni brokers. Solo agrega lo que el
caller (reina / worker / test) le entrega y decide la integridad. Los checks son
predicados locales; la comprobación del ledger puede delegar en el dominio
(``bolsa_domain.lifecycle.assert_equity_invariant``) cuando se le pasa un
``LifecycleAccounting``, o verificar una igualdad simple por importes si no.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from bolsa_domain.lifecycle import LifecycleAccounting

# Venues que un día AUTO SIM-ONLY puede tocar (nunca LIVE real).
AUTO_SIM_VENUES: frozenset[str] = frozenset({"paper", "simulated"})

# V2.23/A9 (Bloque 6): tri-estado del balance del ledger. ``NOT_CHECKED`` (sin datos
# de balance) NUNCA es un PASS: un día AUTO no es certificable si no se comprobó el
# ledger con datos reales.
LEDGER_BALANCED = "BALANCED"
LEDGER_UNBALANCED = "UNBALANCED"
LEDGER_NOT_CHECKED = "NOT_CHECKED"

# Razones de orden/fill que cuentan como orden enviada y fill confirmado.
_ORDER_SIDES = ("buy", "sell")


@dataclass(frozen=True, slots=True)
class SimJournalRow:
    """Aportación mínima a la agregación del día (venue del camino SIM)."""

    kind: str  # "order" | "fill" | "position_open" | "position_close"
    venue: str
    execution_id: str
    side: str = "buy"
    qty: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class AutoDailyReport:
    """Síntesis del día AUTO: conteos + invariantes + motivos de fallo."""

    orders: int
    fills: int
    positions_created: int
    exits: int
    ledger_balanced: bool
    no_duplicate_execution_events: bool
    all_venues_in_auto_sim: bool
    no_live_bridge_posts: bool
    errors: tuple[str, ...] = ()
    # V2.23/A9 (Bloque 6): tri-estado del balance del ledger. ``NOT_CHECKED`` NUNCA
    # cuenta como balance verdadero (el "no comprobado" deja de ser un PASS silencioso).
    ledger_balance_status: str = LEDGER_NOT_CHECKED

    @property
    def healthy(self) -> bool:
        """Un día AUTO SIM-ONLY es sano si supera TODOS los invariantes."""
        return (
            self.orders > 0
            and self.fills > 0
            and self.positions_created > 0
            and self.exits > 0
            and self.ledger_balanced
            and self.ledger_balance_status == LEDGER_BALANCED
            and self.no_duplicate_execution_events
            and self.all_venues_in_auto_sim
            and self.no_live_bridge_posts
            and not self.errors
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "orders": self.orders,
            "fills": self.fills,
            "positions_created": self.positions_created,
            "exits": self.exits,
            "ledger_balanced": self.ledger_balanced,
            "ledger_balance_status": self.ledger_balance_status,
            "no_duplicate_execution_events": self.no_duplicate_execution_events,
            "all_venues_in_auto_sim": self.all_venues_in_auto_sim,
            "no_live_bridge_posts": self.no_live_bridge_posts,
            "healthy": self.healthy,
            "errors": list(self.errors),
        }


def _norm_venue(v: str | None) -> str:
    return str(v or "").strip().lower()


def execution_events_are_unique(execution_ids: Sequence[str]) -> bool:
    """No hay doble ``execution_events`` (idempotencia financiera del día AUTO)."""
    seen: set[str] = set()
    for eid in execution_ids:
        e = str(eid or "").strip()
        if not e:
            continue
        if e in seen:
            return False
        seen.add(e)
    return True


def venues_are_auto_sim(venues: Sequence[str]) -> bool:
    """Todos los venues del día están en {paper, simulated} (SIM-ONLY)."""
    return all(_norm_venue(v) in AUTO_SIM_VENUES for v in venues)


def no_live_bridge_posts(venues: Sequence[str]) -> bool:
    """AUTO jamás publica al bridge LIVE: ningún venue live/broker_live/xtb/real."""
    bad = {"live", "broker_live", "xtb", "real", "live_bridge"}
    return not any(_norm_venue(v) in bad for v in venues)


def ledger_balance_status(
    *,
    accounting: Any | None = None,
    net_cash_delta: Decimal | None = None,
    ledger_remainder: Decimal | None = None,
    tol: Decimal | None = None,
) -> str:
    """Tri-estado del balance: ``BALANCED`` | ``UNBALANCED`` | ``NOT_CHECKED``.

    V2.23/A9 (Bloque 6, §10): NO comprobar el ledger NO es un PASS. Antes, sin datos
    de balance se devolvía ``True`` (not-checked == pass). Ahora ese caso es
    ``NOT_CHECKED`` y el reporte/certificación lo trata como NO certificable.
    """
    from decimal import ROUND_HALF_UP

    scale = Decimal("0.000001")
    t = tol if tol is not None else scale
    if accounting is not None:
        try:
            from bolsa_domain.lifecycle import (
                LifecycleAccounting as _LA,
            )

            assert isinstance(accounting, _LA)
            from bolsa_domain.lifecycle import assert_equity_invariant

            assert_equity_invariant(accounting, tol=t)
            return LEDGER_BALANCED
        except Exception:  # noqa: BLE001 — cualquier invariante roto ⇒ balance NO ok
            return LEDGER_UNBALANCED
    if net_cash_delta is None or ledger_remainder is None:
        # Sin datos de balance ⇒ NO comprobado (jamás un PASS silencioso).
        return LEDGER_NOT_CHECKED
    a = Decimal(str(net_cash_delta)).quantize(scale, rounding=ROUND_HALF_UP)
    b = Decimal(str(ledger_remainder)).quantize(scale, rounding=ROUND_HALF_UP)
    return LEDGER_BALANCED if abs(a - b) <= t else LEDGER_UNBALANCED


def ledger_balanced(
    *,
    accounting: Any | None = None,
    net_cash_delta: Decimal | None = None,
    ledger_remainder: Decimal | None = None,
    tol: Decimal | None = None,
) -> bool:
    """Comprueba que el ledger queda balanceado tras el día AUTO.

    delegación preferida: si se pasa un ``LifecycleAccounting`` del dominio se
    llama a ``assert_equity_invariant`` (puede lanzar → False). Si no (test puro),
    se exige ``net_cash_delta() == ledger_remainder()`` dentro de ``tol``.
    V2.23/A9 (Bloque 6): ``NOT_CHECKED`` (sin datos) ⇒ ``False`` (no-pass).
    """
    return (
        ledger_balance_status(
            accounting=accounting,
            net_cash_delta=net_cash_delta,
            ledger_remainder=ledger_remainder,
            tol=tol,
        )
        == LEDGER_BALANCED
    )


def build_lifecycle_accounting(
    *,
    cash: Decimal,
    remaining: Decimal,
    avg_cost: Decimal,
    last_price: Decimal,
    realized_pnl: Decimal,
    initial_equity: Decimal,
) -> LifecycleAccounting:
    """V2.24/A9.1 (P2-05) — construye el ``LifecycleAccounting`` del dominio.

    Permite que el día AUTO se certifique con el INVARIANTE DE EQUITY real
    (``assert_equity_invariant``) calculado desde el estado financiero canónico
    (cash/posición del ledger), y no con una igualdad trivial de ceros.
    """
    market_value = (remaining * last_price).quantize(Decimal("0.000001"))
    unrealized = ((last_price - avg_cost) * remaining).quantize(Decimal("0.000001"))
    total_pnl = (realized_pnl + unrealized).quantize(Decimal("0.000001"))
    total_equity = (cash + market_value).quantize(Decimal("0.000001"))
    return LifecycleAccounting(
        cash=cash,
        remaining=remaining,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized,
        total_pnl=total_pnl,
        last_price=last_price,
        market_value=market_value,
        total_equity=total_equity,
        avg_cost=avg_cost,
        initial_equity=initial_equity,
    )


@dataclass(frozen=True, slots=True)
class LedgerCashMovement:
    """Movimiento de caja del ledger canónico (aportación mínima para reconstruir).

    ``category`` clasifica la fila para no confundir flujo de caja con P&L:

    * ``deposit``     — aportación externa/seed (+). NO es P&L; forma parte de
      ``initial_equity``.
    * ``withdrawal``  — retirada externa (−). NO es P&L.
    * ``buy``         — compra de instrumento (−notional). NO es P&L por sí sola.
    * ``sell``        — venta de instrumento (+notional). NO es P&L por sí sola.
    * ``fee``         — comisión (−abs). SÍ es P&L (coste realizado).
    """

    category: str
    amount: Decimal


def reconstruct_accounting_from_state(
    *,
    movements: Sequence[LedgerCashMovement],
    remaining: Decimal,
    avg_cost: Decimal,
    last_price: Decimal,
    closed_pnl: Decimal = Decimal("0"),
) -> LifecycleAccounting:
    """V2.24.2 (P2-A) — reconstruye la contabilidad REAL del día AUTO.

    A diferencia de una construcción con ``last_price=0``/``realized_pnl=0`` (la
    invariante quedaría tautológica: ``market_value=0`` y ``unrealized=0``), esta
    función deriva cada término de datos canónicos y produce una contabilidad
    **NO degenerada** que ``assert_equity_invariant`` puede certificar de verdad:

    * ``cash``            = Σ (deposits + withdrawals + buys + sells + fees)
    * ``initial_equity``  = Σ deposits − Σ withdrawals  (capital aportado neto)
    * ``realized_pnl``    = ``closed_pnl`` (P&L cerrado) − Σ |fees|
    * ``unrealized_pnl``  = ``(last_price − avg_cost) × remaining`` (dentro del build)
    * ``total_equity``    = ``cash + remaining × last_price`` (dentro del build)

    La invariante del dominio exige entonces
    ``cash + market_value == initial_equity + realized_pnl + unrealized_pnl``,
    que solo se cumple si cash, coste medio, precio y P&L cerrado son coherentes.
    """
    cash = Decimal("0")
    deposits = Decimal("0")
    withdrawals = Decimal("0")
    fees = Decimal("0")
    for mv in movements:
        amount = Decimal(str(mv.amount))
        cash += amount
        category = (mv.category or "").strip().lower()
        if category == "deposit":
            deposits += amount
        elif category == "withdrawal":
            withdrawals += abs(amount)
        elif category == "fee":
            fees += abs(amount)
    initial_equity = deposits - withdrawals
    realized_pnl = (Decimal(str(closed_pnl)) - fees).quantize(Decimal("0.000001"))
    return build_lifecycle_accounting(
        cash=cash.quantize(Decimal("0.000001")),
        remaining=Decimal(str(remaining)),
        avg_cost=Decimal(str(avg_cost)),
        last_price=Decimal(str(last_price)),
        realized_pnl=realized_pnl,
        initial_equity=initial_equity.quantize(Decimal("0.000001")),
    )


def build_auto_daily_report(
    *,
    rows: Sequence[SimJournalRow],
    accounting: Any | None = None,
    net_cash_delta: Decimal | None = None,
    ledger_remainder: Decimal | None = None,
    venue_overrides: Sequence[str] = (),
) -> AutoDailyReport:
    """(PURA) agrega un recorrido de día AUTO en el resumen diario + invariantes.

    ``rows`` son las aportaciones mínimas (orden/fill/position_open/position_close)
    del día. La agregación local es suficiente para el conteo y las invariantes
    estructurales; para el balance del ledger se delega en ``ledger_balanced``.
    """
    orders = 0
    fills = 0
    positions_created = 0
    exits = 0
    exec_ids: list[str] = []
    venues: list[str] = list(venue_overrides)
    errors: list[str] = []
    for r in rows:
        venues.append(r.venue)
        if r.kind == "order" and str(r.side).strip().lower() in _ORDER_SIDES:
            orders += 1
        elif r.kind == "fill":
            fills += 1
            exec_ids.append(r.execution_id)
        elif r.kind == "position_open":
            positions_created += 1
        elif r.kind == "position_close":
            exits += 1
    if fills and not positions_created:
        errors.append("fills_without_opened_position")
    unique_events = execution_events_are_unique(exec_ids)
    auto_venues = venues_are_auto_sim(venues)
    no_live = no_live_bridge_posts(venues)
    balance_status = ledger_balance_status(
        accounting=accounting,
        net_cash_delta=net_cash_delta,
        ledger_remainder=ledger_remainder,
    )
    balanced = balance_status == LEDGER_BALANCED
    if balance_status == LEDGER_NOT_CHECKED:
        errors.append("ledger_balance_not_checked")
    elif balance_status == LEDGER_UNBALANCED:
        errors.append("ledger_unbalanced")
    return AutoDailyReport(
        orders=orders,
        fills=fills,
        positions_created=positions_created,
        exits=exits,
        ledger_balanced=balanced,
        ledger_balance_status=balance_status,
        no_duplicate_execution_events=unique_events,
        all_venues_in_auto_sim=auto_venues,
        no_live_bridge_posts=no_live,
        errors=tuple(errors),
    )
