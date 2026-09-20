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

V2.42 slice 2c (cierre de ``AUTO-2``): además de los conteos, el reporte agrega **por qué**
cerró cada posición (``exit_reasons``, leído de la ``reason`` de cada fila de cierre) y la
**procedencia del ATR** de las candidatas del día (``atr_sources``, medición que el llamante
lee del worker). Así "``TIME_EXIT``/``THESIS_EXIT`` con evidencia en el journal de un día
completo" es un número verificable, no una impresión.

V2.45/AUTO-5 (Golden Day 2.0) añade el **embudo** del día y su atribución: cada oportunidad
termina en un estado final (``traded``/``rejected``/``expired``/``missed``) con su motivo, de
modo que ``seen == traded + rejected + expired + missed``; además agrega la atribución por
**estrategia**, el **MAE/MFE** por operación y el **coste de oportunidad** de las rechazadas
con su precio posterior. La disciplina de medición es la del repo: lo que no se puede medir
se declara (``UNKNOWN``/``PARTIAL`` + ``notes``) y **nunca** se publica como un ``0``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from bolsa_application.auto_reason_codes import (
    DAY_EXIT_REASON_UNDECLARED,
    MAE_MFE_UNMEASURED,
    OPPORTUNITY_COST_UNMEASURED,
    OPPORTUNITY_EXPIRED,
    OPPORTUNITY_MISSED,
    OPPORTUNITY_REJECTED,
    OPPORTUNITY_STATUSES,
    OPPORTUNITY_TRADED,
)
from bolsa_domain.lifecycle import LifecycleAccounting

# Venues que un día AUTO SIM-ONLY puede tocar (nunca LIVE real).
AUTO_SIM_VENUES: frozenset[str] = frozenset({"paper", "simulated"})

# V2.45/AUTO-5 — disciplina de medición del embudo y de los agregados de atribución. Un
# agregado que NO se pudo medir se declara ``UNKNOWN``/``PARTIAL`` (+ ``notes``); jamás se
# publica como un ``0`` que se leería como "no hubo nada que medir" (que es una afirmación).
MEASUREMENT_COMPLETE = "COMPLETE"
MEASUREMENT_PARTIAL = "PARTIAL"
MEASUREMENT_UNKNOWN = "UNKNOWN"

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
    """Aportación mínima a la agregación del día (venue del camino SIM).

    ``reason`` (V2.42 slice 2c) declara el motivo del cierre en la propia fila del día
    (``time_exit``/``thesis_exit``/``structural_stop``/...). Sin él, el día sabía CUÁNTAS
    posiciones cerró pero no POR QUÉ, y "``TIME_EXIT``/``THESIS_EXIT`` con evidencia en el
    journal de un día completo" (criterio de salida de ``AUTO-2``) no era contable.
    """

    kind: str  # "order" | "fill" | "fill_unapplied" | "position_open" | "position_close" | ...
    venue: str
    execution_id: str
    side: str = "buy"
    qty: Decimal = Decimal("0")
    reason: str = ""
    # V2.45/AUTO-5 — identidad de estrategia ADITIVA (misma disciplina que el ``payload``
    # JSONB del journal durable, sin migración). Sin versión la fila NO se atribuye: la
    # ausencia se declara (mapa de atribución vacío), nunca se reparte entre estrategias.
    strategy_version: str = ""


@dataclass(frozen=True, slots=True)
class OpportunityRow:
    """V2.45/AUTO-5 — una oportunidad del día y su estado FINAL auditado.

    Instala el invariante de `AUTO-7` desde ya: *toda oportunidad termina en un estado
    final* (``traded``/``rejected``/``expired``/``missed``) **con su motivo**. El embudo
    del día debe cuadrar: ``seen == traded + rejected + expired + missed``.

    ``reason`` es obligatorio para los tres estados NO operados (una rechazada sin motivo
    es una decisión en silencio). ``reference_price``/``subsequent_price`` son la materia
    prima del **coste de oportunidad**: el precio de la oportunidad cuando se descartó y el
    precio posterior observado. Si falta cualquiera de los dos, el coste se declara
    ``unmeasured`` — nunca se inventa un ``0``.
    """

    instrument_id: str
    status: str  # traded | rejected | expired | missed
    reason: str = ""
    strategy_version: str = ""
    reference_price: Decimal | None = None
    subsequent_price: Decimal | None = None


@dataclass(frozen=True, slots=True)
class OperationMeasurement:
    """V2.45/AUTO-5 — MAE/MFE de una operación del día (leído de ``mfe_mae`` del JSONB).

    Se **recoge**, no se calibra (la calibración de stop/T1/trailing es ``AUTO-7``). Sin
    las dos patas (``mfe`` y ``mae``) la medición de esa operación queda declarada como
    ``UNKNOWN`` y el agregado del día lo publica como ``PARTIAL``/``UNKNOWN`` con su nota.
    """

    instrument_id: str
    strategy_version: str = ""
    mfe: Decimal | None = None
    mae: Decimal | None = None


@dataclass(frozen=True, slots=True)
class OpportunityCost:
    """V2.45/AUTO-5 — coste de oportunidad de una rechazada (medido o declarado).

    ``missed_return`` es el movimiento relativo ``(subsequent − reference) / reference``
    del precio que la oportunidad rechazada dejó pasar. Solo se publica cuando AMBOS
    precios existen y la referencia no es cero; si no, la fila queda ``UNKNOWN`` con la
    nota ``opportunity_cost_unmeasured``.
    """

    instrument_id: str
    reason: str
    status: str
    strategy_version: str = ""
    reference_price: Decimal | None = None
    subsequent_price: Decimal | None = None
    missed_return: Decimal | None = None
    measurement: str = MEASUREMENT_UNKNOWN
    notes: tuple[str, ...] = ()


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
    # V2.42 slice 2c: POR QUÉ cerró cada posición (etiqueta -> conteo, orden determinista).
    # ``sum(exit_reasons) == exits``: una salida sin motivo de protección se cuenta como
    # ``undeclared`` (jamás se le atribuye un motivo que no declaró).
    exit_reasons: tuple[tuple[str, int], ...] = ()
    # V2.42 slice 2c: procedencia del ATR de las candidatas del día (``real``/``fallback``/
    # ``missing``). Es la MEDICIÓN con la que se decide el flip del veto (D3), no un juicio.
    atr_sources: tuple[tuple[str, int], ...] = ()
    # V2.45/AUTO-5 — embudo del día: ``seen == traded + rejected + expired + missed``.
    # ``funnel_measurement`` es ``UNKNOWN`` cuando NO se aportaron oportunidades (no medir
    # no es un 0), ``COMPLETE`` cuando el embudo cuadra y ``PARTIAL`` cuando no.
    seen: int = 0
    traded: int = 0
    rejected: int = 0
    expired: int = 0
    missed: int = 0
    funnel_measurement: str = MEASUREMENT_UNKNOWN
    rejection_reasons: tuple[tuple[str, int], ...] = ()
    # V2.45/AUTO-5 — atribución por estrategia (entradas decididas y salidas del journal).
    strategy_traded: tuple[tuple[str, int], ...] = ()
    strategy_exits: tuple[tuple[str, int], ...] = ()
    # V2.45/AUTO-5 — MAE/MFE por operación (recogido, no calibrado) + estado del agregado.
    mae_mfe: tuple[OperationMeasurement, ...] = ()
    mae_mfe_measurement: str = MEASUREMENT_UNKNOWN
    # V2.45/AUTO-5 — coste de oportunidad de las rechazadas (medido o declarado).
    opportunity_cost: tuple[OpportunityCost, ...] = ()
    opportunity_cost_measurement: str = MEASUREMENT_UNKNOWN
    # Notas de medición del día (por qué un agregado quedó ``UNKNOWN``/``PARTIAL``).
    notes: tuple[str, ...] = ()

    @property
    def funnel_closed(self) -> bool:
        """El embudo del día cuadra y está MEDIDO (``seen == Σ estados``)."""
        return self.funnel_measurement == MEASUREMENT_COMPLETE

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
            "exit_reasons": dict(self.exit_reasons),
            "atr_sources": dict(self.atr_sources),
            "seen": self.seen,
            "traded": self.traded,
            "rejected": self.rejected,
            "expired": self.expired,
            "missed": self.missed,
            "funnel_measurement": self.funnel_measurement,
            "rejection_reasons": dict(self.rejection_reasons),
            "strategy_traded": dict(self.strategy_traded),
            "strategy_exits": dict(self.strategy_exits),
            "mae_mfe_measurement": self.mae_mfe_measurement,
            "mae_mfe": [
                {
                    "instrumentId": m.instrument_id,
                    "strategyVersion": m.strategy_version or None,
                    "mfe": None if m.mfe is None else str(m.mfe),
                    "mae": None if m.mae is None else str(m.mae),
                }
                for m in self.mae_mfe
            ],
            "opportunity_cost_measurement": self.opportunity_cost_measurement,
            "opportunity_cost": [
                {
                    "instrumentId": c.instrument_id,
                    "status": c.status,
                    "reason": c.reason,
                    "strategyVersion": c.strategy_version or None,
                    "missedReturn": None if c.missed_return is None else str(c.missed_return),
                    "measurement": c.measurement,
                    "notes": list(c.notes),
                }
                for c in self.opportunity_cost
            ],
            "notes": list(self.notes),
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


def _sorted_counts(counts: Mapping[str, int]) -> tuple[tuple[str, int], ...]:
    """Conteos con orden determinista (conteo desc, etiqueta asc) para poder compararlos."""
    return tuple(
        sorted(
            ((str(k), int(v)) for k, v in counts.items()),
            key=lambda kv: (-kv[1], kv[0]),
        )
    )


def _opportunity_breakdown(
    opportunities: Sequence[OpportunityRow],
    *,
    declared_seen: int | None,
) -> tuple[dict[str, int], int, dict[str, int], list[str], list[str]]:
    """Embudo del día: cuenta por estado, valida el cierre y exige motivo a los no-operados.

    Devuelve ``(counts, seen, rejection_reasons, errors, notes)``. El embudo es
    **disjunto y exhaustivo**: cada oportunidad cae en exactamente un estado. Un estado
    NO catalogado es un defecto (``opportunity_status_unknown``) y deja el embudo abierto;
    una rechazada sin motivo es una decisión en silencio (``rejection_without_reason``).
    """
    counts = {
        OPPORTUNITY_TRADED: 0,
        OPPORTUNITY_REJECTED: 0,
        OPPORTUNITY_EXPIRED: 0,
        OPPORTUNITY_MISSED: 0,
    }
    rejection_reasons: dict[str, int] = {}
    errors: list[str] = []
    for row in opportunities:
        status = str(row.status or "").strip().lower()
        if status not in OPPORTUNITY_STATUSES:
            errors.append("opportunity_status_unknown")
            continue
        counts[status] += 1
        reason = str(row.reason or "").strip()
        if status != OPPORTUNITY_TRADED and not reason:
            errors.append("rejection_without_reason")
        if status == OPPORTUNITY_REJECTED and reason:
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
    measured = sum(counts.values())
    seen = declared_seen if declared_seen is not None else len(opportunities)
    if declared_seen is not None and declared_seen != len(opportunities):
        # ``seen`` declarado por el productor ≠ filas construidas ⇒ hay oportunidades
        # vistas que NO terminaron en un estado (el caso exacto que el embudo debe cazar).
        errors.append("funnel_seen_mismatch")
    if seen != measured:
        errors.append("funnel_unbalanced")
    return counts, seen, rejection_reasons, errors, []


def _opportunity_costs(
    opportunities: Sequence[OpportunityRow],
) -> tuple[tuple[OpportunityCost, ...], str, list[str]]:
    """Coste de oportunidad de las rechazadas: medido con el precio posterior, o declarado.

    Nunca se inventa: sin precio de referencia o sin precio posterior la fila queda
    ``UNKNOWN`` con la nota ``opportunity_cost_unmeasured``. El agregado es ``COMPLETE``
    solo si TODAS las rechazadas son medibles.
    """
    rejected_like = [
        row
        for row in opportunities
        if str(row.status or "").strip().lower()
        in {OPPORTUNITY_REJECTED, OPPORTUNITY_EXPIRED, OPPORTUNITY_MISSED}
    ]
    costs: list[OpportunityCost] = []
    measured = 0
    for row in rejected_like:
        ref = row.reference_price
        sub = row.subsequent_price
        notes: tuple[str, ...] = ()
        missed_return: Decimal | None = None
        measurement = MEASUREMENT_UNKNOWN
        if ref is None or sub is None or Decimal(str(ref)) == 0:
            notes = (OPPORTUNITY_COST_UNMEASURED,)
        else:
            missed_return = (
                (Decimal(str(sub)) - Decimal(str(ref))) / Decimal(str(ref))
            ).quantize(Decimal("0.000001"))
            measurement = MEASUREMENT_COMPLETE
            measured += 1
        costs.append(
            OpportunityCost(
                instrument_id=row.instrument_id,
                reason=str(row.reason or ""),
                status=str(row.status or "").strip().lower(),
                strategy_version=str(row.strategy_version or ""),
                reference_price=ref,
                subsequent_price=sub,
                missed_return=missed_return,
                measurement=measurement,
                notes=notes,
            )
        )
    if not rejected_like or measured == 0:
        aggregate = MEASUREMENT_UNKNOWN
    elif measured == len(rejected_like):
        aggregate = MEASUREMENT_COMPLETE
    else:
        aggregate = MEASUREMENT_PARTIAL
    notes_out = (
        [OPPORTUNITY_COST_UNMEASURED]
        if rejected_like and aggregate != MEASUREMENT_COMPLETE
        else []
    )
    return tuple(costs), aggregate, notes_out


def _mae_mfe(
    measurements: Sequence[OperationMeasurement],
) -> tuple[tuple[OperationMeasurement, ...], str, list[str]]:
    """MAE/MFE del día: ``COMPLETE`` solo si TODAS las operaciones traen ambas patas."""
    if not measurements:
        return (), MEASUREMENT_UNKNOWN, []
    complete = sum(1 for m in measurements if m.mfe is not None and m.mae is not None)
    if complete == len(measurements):
        return tuple(measurements), MEASUREMENT_COMPLETE, []
    aggregate = MEASUREMENT_PARTIAL if complete else MEASUREMENT_UNKNOWN
    return tuple(measurements), aggregate, [MAE_MFE_UNMEASURED]


def build_auto_daily_report(
    *,
    rows: Sequence[SimJournalRow],
    accounting: Any | None = None,
    net_cash_delta: Decimal | None = None,
    ledger_remainder: Decimal | None = None,
    venue_overrides: Sequence[str] = (),
    atr_sources: Mapping[str, int] | None = None,
    opportunities: Sequence[OpportunityRow] = (),
    measurements: Sequence[OperationMeasurement] = (),
    seen: int | None = None,
) -> AutoDailyReport:
    """(PURA) agrega un recorrido de día AUTO en el resumen diario + invariantes.

    ``rows`` son las aportaciones mínimas (orden/fill/position_open/position_close/...)
    del día. La agregación local es suficiente para el conteo y las invariantes
    estructurales; para el balance del ledger se delega en ``ledger_balanced``.

    V2.42 slice 2c: además del conteo de cierres, agrega **por qué** cerró cada posición
    (``exit_reasons``, de la ``reason`` de cada fila de cierre) y la procedencia del ATR de
    las candidatas del día (``atr_sources``, medición que el llamante lee del worker). Un
    cierre sin motivo declarado se cuenta como ``undeclared``: la suma de ``exit_reasons``
    es siempre igual a ``exits`` y ningún cierre se atribuye a un motivo que no declaró.

    V2.45/AUTO-5: agrega el **embudo de oportunidades** (``seen == traded + rejected +
    expired + missed``, con motivo en cada rechazo), la **atribución por estrategia**
    (entradas decididas y salidas del journal), el **MAE/MFE** por operación y el **coste de
    oportunidad** de las rechazadas. ``opportunities``/``measurements`` son ADITIVOS: sin
    ellos el embudo queda ``UNKNOWN`` (no medir no es un ``0``) y el día vigente no cambia.
    """
    orders = 0
    fills = 0
    positions_created = 0
    exits = 0
    exec_ids: list[str] = []
    venues: list[str] = list(venue_overrides)
    errors: list[str] = []
    exit_reason_counts: dict[str, int] = {}
    strategy_exit_counts: dict[str, int] = {}
    strategy_traded_counts: dict[str, int] = {}
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
            label = str(r.reason or "").strip().lower() or DAY_EXIT_REASON_UNDECLARED
            exit_reason_counts[label] = exit_reason_counts.get(label, 0) + 1
            version = str(r.strategy_version or "").strip()
            if version:
                strategy_exit_counts[version] = strategy_exit_counts.get(version, 0) + 1
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

    # V2.45/AUTO-5 — embudo, atribución, MAE/MFE y coste de oportunidad (aditivos).
    notes: list[str] = []
    if opportunities:
        funnel, seen_count, rejection_reasons, funnel_errors, _funnel_notes = (
            _opportunity_breakdown(opportunities, declared_seen=seen)
        )
        errors.extend(funnel_errors)
        funnel_measurement = (
            MEASUREMENT_COMPLETE if not funnel_errors else MEASUREMENT_PARTIAL
        )
        for row in opportunities:
            if str(row.status or "").strip().lower() == OPPORTUNITY_TRADED:
                version = str(row.strategy_version or "").strip()
                if version:
                    strategy_traded_counts[version] = (
                        strategy_traded_counts.get(version, 0) + 1
                    )
    else:
        funnel = {
            OPPORTUNITY_TRADED: 0,
            OPPORTUNITY_REJECTED: 0,
            OPPORTUNITY_EXPIRED: 0,
            OPPORTUNITY_MISSED: 0,
        }
        seen_count = 0
        rejection_reasons = {}
        funnel_measurement = MEASUREMENT_UNKNOWN

    costs, cost_measurement, cost_notes = _opportunity_costs(opportunities)
    mae_mfe, mae_mfe_measurement, mae_notes = _mae_mfe(measurements)
    notes.extend(cost_notes)
    notes.extend(mae_notes)

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
        exit_reasons=_sorted_counts(exit_reason_counts),
        atr_sources=_sorted_counts(atr_sources or {}),
        seen=seen_count,
        traded=funnel[OPPORTUNITY_TRADED],
        rejected=funnel[OPPORTUNITY_REJECTED],
        expired=funnel[OPPORTUNITY_EXPIRED],
        missed=funnel[OPPORTUNITY_MISSED],
        funnel_measurement=funnel_measurement,
        rejection_reasons=_sorted_counts(rejection_reasons),
        strategy_traded=_sorted_counts(strategy_traded_counts),
        strategy_exits=_sorted_counts(strategy_exit_counts),
        mae_mfe=mae_mfe,
        mae_mfe_measurement=mae_mfe_measurement,
        opportunity_cost=costs,
        opportunity_cost_measurement=cost_measurement,
        notes=tuple(dict.fromkeys(notes)),
    )
