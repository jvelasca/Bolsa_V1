"""V2.22 / A9 (last gap) — Finance SIM-ONLY para fills AUTO simulados.

Cierra el último tramo declarado del relevo: el worker AUTO (``auto_simulation_worker``)
conduce un día SIM-ONLY pero liquida con ``apply_finance=None``, de modo que sus fills
solo materializan ``ExecutionEvent`` (quedan ``CAPTURED``, sin dinero) y el día nunca se
reconcilia contra un libro real (positions/ledger/cash).

Este módulo aporta el tornillo de finanzas **reales por fill simulado**, reutilizando el
núcleo canónico (``ExecuteTrade`` idempotente por ``idempotency_key``) sin tocar el
núcleo LIVE:

* ejecución siempre SIM-ONLY: el tráfico solo rota cuenta/cash bajo un venue AUTO
  {paper, simulated}; cualquier alias live/xtb/real/broker_live/otro => bloqueo
  fail-closed (ni Positions/Ledger ni ExecuteTrade).
* idempotencia por fill vía ``simulated_idempotency_key(execution_id)`` (la MISMA del
  ``simulated_settlement``): el primer apply materializa; crash/reintento del mismo fill
  no duplica (C3 / P2-01 del repo). No se inventa otra key.
* el ExecuteTrade-seco se delega a ``ApplyFinanceCallable`` = exactamente lo que
  ``submit_simulated_order``/``apply_simulated_order_once`` ya esperan. Este módulo NO
  ejecuta ExecuteTrade desde el worker ni instaura aritmética propia.

Por qué hace falta un mapper: un ``ExecutionEvent`` durable lleva ``execution_id``/
``qty``/``account_id``/``venue`` pero NO ``instrument_id``/``side``/``price`` (esos son
contexto del ORDER simulado). Cualquier apply financiero real necesita reconstruir ese
contexto por fill: aquí se hace con un objeto ``SimulatedFillFinance`` (portador de los
argumentos de ExecuteTrade) derivado de forma pura del ``SimulatedOrderResult`` ya
aceptado + del ``ExecutionEvent`` que materializa. Así el apply puede resolver, por
``execution_id``, el precio/cantidad deterministas de ESE fill sin inventar nada (H4).

Diseño (dos mitades, recosen costuras sin ciclos):
* mitad pura (import-light, hermeticable): nodos ``SimulatedFillFinance``,
  ``sim_fill_finances`` / ``resolve_execution_finance`` (mapping, sin PG), guardas
  SIM-ONLY y un ``sim_roundtrip_accounting`` (mínimo puro para verificar el invariante
  de dominio con dinero real no-degenerado sobre un mini-día determinista).
* mitad ligada a PG (opcional, lazy): ``build_simulated_execute_trade_applier`` devuelve
  un ``ApplyFinanceCallable`` que, dado un ``ExecuteTrade`` real (creado por el caller en
  la MISMA sesión, igual que el recovery/a7 con ``SqlAlchemyAccountRepository`` +
  ``SqlAlchemyPortfolioRepository`` + ``SqlAlchemyLedgerRepository``), materializa cada
  fill con los argumentos derivados por el mapper.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from bolsa_application.execution_event import ExecutionEvent
from bolsa_application.simulated_broker import SimulatedFill, SimulatedOrderResult
from bolsa_application.simulated_settlement import (
    AUTO_SETTLE_VENUES,
    simulated_idempotency_key,
)

__all__ = [
    "SIM_FINANCE_VENUES",
    "SimulatedFillFinance",
    "build_simulated_execute_trade_applier",
    "guard_sim_only_venue",
    "resolve_execution_finance",
    "sim_fill_finances",
    "sim_roundtrip_accounting",
]

# Peaje SIM-ONLY: la finance AUTO rota cash/posiciones SOLO en venues simulados. Espeja
# el contrato ``ALLOWED_AUTO_VENUES``/``AUTO_SETTLE_VENUES`` sin acoplar import.
SIM_FINANCE_VENUES: frozenset[str] = frozenset(AUTO_SETTLE_VENUES)

# Semilla de capital por defecto para el mini-día puro (mismo rol que LIFECYCLE_CASH).
DEFAULT_INITIAL_CASH = Decimal("100000")


@dataclass(frozen=True, slots=True)
class SimulatedFillFinance:
    """Argumentos financieros REALES de un fill simulado (sin inversión).

    Es lo que ``ExecuteTrade.execute`` necesita y que el ``ExecutionEvent`` no
    transporta (instrument_id/side/price). La identidad financiera sigue siendo el
    ``execution_id``; nunca se fabrica una key nueva.
    """

    instrument_id: str
    side: str  # "buy" | "sell"
    execution_id: str
    quantity: Decimal
    price: Decimal
    account_id: str | None = None
    venue: str = "simulated"

    def __post_init__(self) -> None:
        if not self.execution_id or not self.execution_id.strip():
            raise ValueError("execution_id is required")
        if str(self.side).strip().lower() not in {"buy", "sell"}:
            raise ValueError(f"side must be buy/sell, got {self.side!r}")
        if self.quantity is None or self.quantity <= 0:
            raise ValueError(f"quantity must be > 0, got {self.quantity!r}")

    @property
    def trade_type(self) -> str:
        """`buy`/`sell`: el literal que ``ExecuteTrade.execute`` espera."""
        return str(self.side).strip().lower()

    @property
    def idempotency_key(self) -> str:
        """Reutiliza ``simulated_idempotency_key`` (NUNCA otra key)."""
        key = simulated_idempotency_key(self.execution_id)
        if not key:
            raise ValueError(f"no viable idempotency key for execution {self.execution_id!r}")
        return key

    @property
    def venue_is_sim_only(self) -> bool:
        return str(self.venue or "").strip().lower() in SIM_FINANCE_VENUES


def guard_sim_only_venue(venue: str) -> None:
    """Bloquea cualquier venue fuera de {paper, simulated} (nunca LIVE/real).

    Raises ``ValueError`` con el venue señalado en vez de abrir la vía REAL.
    """
    v = str(venue or "").strip().lower()
    if v not in SIM_FINANCE_VENUES:
        raise ValueError(
            f"simulated finance refused non-AUTO venue {venue!r} "
            f"(allowed={sorted(SIM_FINANCE_VENUES)})"
        )


def _fill_for_execution(result: SimulatedOrderResult, execution_id: str) -> SimulatedFill | None:
    """Devuelve el ``SimulatedFill`` (si existe) cuyo ``execution_id`` coincide."""
    for fill in result.fills:
        if fill.execution_id == execution_id:
            return fill
    return None


def sim_fill_finances(
    result: SimulatedOrderResult,
    *,
    instrument_id: str,
    side: str,
    account_id: str | None,
    venue: str,
) -> tuple[SimulatedFillFinance, ...]:
    """(PURA) mapper: de un ``SimulatedOrderResult`` aceptado a sus finanzas por fill.

    Cada ``SimulatedFill`` (con su qty/price deterministas y su ``execution_id``) se
    traduce en un ``SimulatedFillFinance`` listo para el libro. Fail-closed: un venue
    no AUTO-allowed devuelve tupla vacía (CERO dinero).
    """
    v = str(venue or "").strip().lower()
    if v not in SIM_FINANCE_VENUES:
        return ()
    out: list[SimulatedFillFinance] = []
    for fill in result.fills:
        qty = abs(fill.qty_delta)
        if qty <= 0 or fill.price is None or fill.price <= 0:
            continue
        out.append(
            SimulatedFillFinance(
                instrument_id=instrument_id,
                side=side,
                execution_id=fill.execution_id,
                quantity=qty,
                price=fill.price,
                account_id=account_id,
                venue=v,
            )
        )
    return tuple(out)


def resolve_execution_finance(
    result: SimulatedOrderResult,
    *,
    execution: ExecutionEvent,
    instrument_id: str,
    side: str,
    account_id: str | None,
) -> SimulatedFillFinance | None:
    """(PURA) mapper por evento: como ``sim_fill_finances`` pero para UN evento.

    El ``ExecutionEvent`` ya está CAPTURADO/materializado durablemente; este mapper le
    asigna el contexto financiero real (price/qty deterministas del ``SimulatedFill``
    correspondiente), de modo que el apply pueda ejecutar ExecuteTrade SIN inventar
    price/instrument/side. None = fail-closed (sin viabilidad): no se abre dinero.
    """
    if not execution or not execution.execution_id:
        return None
    v = str(execution.venue or "").strip().upper()
    if v.lower() not in SIM_FINANCE_VENUES:
        return None
    fill = _fill_for_execution(result, execution.execution_id)
    if fill is None or abs(fill.qty_delta) <= 0 or fill.price is None or fill.price <= 0:
        return None
    return SimulatedFillFinance(
        instrument_id=instrument_id,
        side=side,
        execution_id=execution.execution_id,
        quantity=abs(fill.qty_delta),
        price=fill.price,
        account_id=account_id if account_id is not None else execution.account_id,
        venue=v,
    )


# ── Mitad ligada a PG (lazy; opcional; nunca importa infra en el módulo) ──────────
FinanceResolver = Callable[[ExecutionEvent], SimulatedFillFinance | None]


def build_simulated_execute_trade_applier(
    execute_trade: Any,
    resolver: FinanceResolver,
) -> Any:
    """Fabrica un ``ApplyFinanceCallable`` que materializa un fill simulado en PG real.

    ``execute_trade`` es la instancia de ``ExecuteTrade`` (construida por el caller en su
    sesión, igual que el recovery/a7: ``SqlAlchemyAccountRepository``+``Portfolio``+
    ``Ledger`` sobre la MISMA sesión). ``resolver`` traduce un ``ExecutionEvent`` a su
    ``SimulatedFillFinance`` (típicamente ``sim_fill_finances``/``resolve_execution_finance``
    con el ``SimulatedOrderResult`` en mano).

    El callable devuelto es IDEMPOTENTE por fill (``simulated_idempotency_key``) y SIM-ONLY:
    sin contexto viable (mapper → None) o venue no-AUTO → ``False`` (no se marca APPLIED,
    fail-closed), exactamente como el recovery. Un error en ExecuteTrade se captura y
    devuelve ``False`` (NUNCA se marca APPLIED por excepción) — el store lo encamina a
    RETRY/FAILED.

    Para no acoplar el módulo a las repos/dominio PG, ``execute_trade`` se recibe ya
    construido (Any) y se valida por duck-typing de ``execute``.
    """
    executor = getattr(execute_trade, "execute", None)
    if executor is None:
        raise TypeError("execute_trade must expose an async .execute(**kwargs)")

    async def _apply(execution: ExecutionEvent) -> bool:
        finance = resolver(execution)
        if finance is None:
            # Sin contexto viable (no-match / venue no-AUTO / sin price) → nada que aplicar.
            return False
        if not finance.venue_is_sim_only:
            return False
        try:
            await executor(
                instrument_id=finance.instrument_id,
                trade_type=finance.trade_type,
                quantity=float(finance.quantity),
                price=float(finance.price),
                account_id=finance.account_id,
                idempotency_key=finance.idempotency_key,
            )
            return True
        except Exception:  # noqa: BLE001 — no applied; no marcar APPLIED por excepción.
            return False

    return _apply


# ── Mini-día puro (equity / invariante de dominio determinista, sin DB) ───────────
@dataclass(frozen=True, slots=True)
class SimRoundTripBook:
    """Libro Determinista de un mini-día (compra/vende) para el invariante de dominio.

    Es puro: reduce los fills a cash + posición, y confirma idempotencia por fill. NO es
    un reemplazo de Posición/Ledger PG; solo es el espejo aritmético que permite que el
    aggregator M7 delegue en ``assert_equity_invariant`` con dinero real no-degenerado.
    """

    initial_cash: Decimal
    cash: Decimal
    remaining: Decimal
    realized_pnl: Decimal
    last_price: Decimal
    fills_credited: int  # nº de fills que entraron en el libro (idempotente).

    @property
    def market_value(self) -> Decimal:
        return self.last_price * self.remaining

    @property
    def total_equity(self) -> Decimal:
        return self.cash + self.market_value

    @property
    def total_pnl(self) -> Decimal:
        return self.realized_pnl


def sim_roundtrip_accounting(
    finances: tuple[SimulatedFillFinance, ...],
    *,
    initial_cash: Decimal = DEFAULT_INITIAL_CASH,
    mark_price: Decimal | None = None,
) -> SimRoundTripBook:
    """(PURA) reduce finanzas por fill a un libro balanceado para el invariante.

    Fees asumidos = 0 (documentado): el mini-día ejecuta al precio de llenado simulado
    SIN comisiones para que el invariante sea determinista e independiente del preset de
    una cuenta. Una compra resta cash (y sube posición con re-ponderación de coste medio),
    una venta lo suma (materializando realized pnl). La posición restante se valora a
    ``mark_price`` (default: último precio de venta si el libro quedó plano, si no, el
    coste medio). La identidad ``equity == inicial + realized`` (invariante) vale por
    construcción con estos libros; un plan de dos vías balanceado somete esa identidad a
    dinero real no-degenerado.

    Sin fills → libro vacío balanceado (cero). Un fill duplicado del mismo execution_id
    (replay) se cuenta UNA vez (idempotencia real por fill).
    """
    _EPS = Decimal("0.000000001")
    seen: set[str] = set()
    cash = initial_cash
    remaining = Decimal("0")
    avg_cost = Decimal("0")
    realized = Decimal("0")
    fills_credited = 0
    last_sell_px = Decimal("0")

    for finance in finances:
        if finance.execution_id in seen:
            continue  # idempotente por fill: un replay no se cuenta dos veces.
        seen.add(finance.execution_id)
        fills_credited += 1
        qty = finance.quantity
        px = finance.price
        if finance.trade_type == "buy":
            cash -= qty * px
            if remaining + qty <= 0:
                raise ValueError("roundtrip book: buy would invert a short exposure")
            avg_cost = ((avg_cost * remaining) + (qty * px)) / (remaining + qty)
            remaining += qty
        else:
            if remaining < qty:
                raise ValueError("roundtrip book: sell exceeds the held position")
            realized += (px - avg_cost) * qty
            cash += qty * px
            remaining -= qty
            last_sell_px = px
        if remaining <= _EPS:
            remaining = Decimal("0")  # cierre limpio a cero.

    if mark_price is not None and mark_price > 0:
        mark = mark_price
    elif remaining == 0 and last_sell_px > 0:
        mark = last_sell_px
    else:
        mark = avg_cost if avg_cost > 0 else initial_cash
    return SimRoundTripBook(
        initial_cash=initial_cash,
        cash=cash,
        remaining=remaining,
        realized_pnl=realized,
        last_price=mark,
        fills_credited=fills_credited,
    )
