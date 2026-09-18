"""PortfolioReservation — el motor de reservas explícito (AUTO 2.0 · AUTO-1 / V2.41).

El agujero que cierra este módulo (auditoría de ``v2.40.4-beta``, §3 del roadmap AUTO):

    aprobar una entrada  ⇒  solo un ``TradePlan``        ← no hay reserva con identidad
    reservar a mano      ⇒  ``committed[]`` local        ← muere al volver del tick
    liberar              ⇒  no existe                    ← nadie libera, nadie audita

La reserva artesanal de ``plan_v2_tick`` funcionaba (impedía que N candidatas del mismo
tick gastaran el mismo cash), pero era **anónima**: una ``PortfolioPosition`` sintética
metida en una lista local, sin identidad, sin ciclo de vida, sin persistencia y sin
liberación explícita. Este módulo instala la reserva como objeto de primera clase.

Invariante que instala:

    no existe aprobación sin reserva, y no existe reserva sin liberación

Toda reserva declara sus dimensiones comprometidas — capital, riesgo, exposición de
activo, exposición de sector, correlación, capacidad de estrategia y capacidad de
liquidez — y es **reversible**: se puede liberar por fill, por cancelación, por reinicio
o por rollback, y se puede **reproducir** con ``replay`` (misma secuencia de eventos ⇒
mismo libro, byte a byte). De ahí sale la pregunta que hoy no se puede responder:
"¿cuánto riesgo tenía AUTO reservado antes de lanzar esta orden?".

Honestidad (fail-closed), en la línea de ``measurement``/``open_order``/``position_ledger``:

* Una reserva cuyas dimensiones no se pueden cuantificar **no reserva 0**: baja el
  ``measurement`` del libro. "Sé que reservé 100" no puede leerse como "reservé 100".
* Una liberación parcial (fill parcial) **escala** las dimensiones reservadas: lo llenado
  deja de ser reserva y pasa a ser posición; la cola sigue siendo capital comprometido.
* Liberar dos veces la misma reserva es un no-op (idempotente), nunca un doble liberado.
* "El libro no se pudo leer" jamás se confunde con "el libro está vacío".

Módulo puro y determinista (sin I/O y sin reloj): las fechas entran como ``str`` del
llamante y el I/O durable vive en la capa de aplicación (``reservation_store``). El
``ReservationLedger`` es un read-model con estado **determinista**: dado el mismo orden de
operaciones produce siempre el mismo libro, y ``replay(ledger.events())`` lo reproduce.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from bolsa_analytics.cognitive.auto_portfolio_snapshot import (
    UNKNOWN_SECTOR,
    PortfolioPosition,
)
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
    coerce_measurement,
    measurement_from_counts,
)
from bolsa_domain.account_settings import AccountSettings, calculate_trade_fees

SIDE_BUY = "buy"
SIDE_SELL = "sell"

# Ciclo de vida de una reserva. ``OPEN`` es la única viva: todo lo demás ya liberó (y por
# tanto ya no consume capital, riesgo ni exposición).
ReservationStatus = Literal[
    "OPEN",
    "RELEASED_BY_FILL",
    "RELEASED_BY_CANCEL",
    "RELEASED_BY_RESTART",
    "RELEASED_BY_ROLLBACK",
]

RESERVATION_OPEN: ReservationStatus = "OPEN"
RESERVATION_RELEASED_BY_FILL: ReservationStatus = "RELEASED_BY_FILL"
RESERVATION_RELEASED_BY_CANCEL: ReservationStatus = "RELEASED_BY_CANCEL"
RESERVATION_RELEASED_BY_RESTART: ReservationStatus = "RELEASED_BY_RESTART"
RESERVATION_RELEASED_BY_ROLLBACK: ReservationStatus = "RELEASED_BY_ROLLBACK"

# Motivos tipificados de liberación (observables en el journal).
RELEASE_REASON_FILL = "fill"
RELEASE_REASON_CANCEL = "cancel"
RELEASE_REASON_RESTART = "restart"
RELEASE_REASON_ROLLBACK = "rollback"

_RELEASED_STATUSES: frozenset[str] = frozenset(
    {
        RESERVATION_RELEASED_BY_FILL,
        RESERVATION_RELEASED_BY_CANCEL,
        RESERVATION_RELEASED_BY_RESTART,
        RESERVATION_RELEASED_BY_ROLLBACK,
    }
)

ReservationEventKind = Literal["reserve", "release"]

RESERVATION_EVENT_RESERVE: ReservationEventKind = "reserve"
RESERVATION_EVENT_RELEASE: ReservationEventKind = "release"

_RESERVATION_EVENT_KINDS: frozenset[str] = frozenset(
    {RESERVATION_EVENT_RESERVE, RESERVATION_EVENT_RELEASE}
)

_QTY_EPS = 1e-9


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _finite_positive(value: Any) -> float | None:
    number = _finite(value)
    if number is None or number <= 0:
        return None
    return number


def _non_negative(value: Any) -> float | None:
    number = _finite(value)
    if number is None or number < 0:
        return None
    return number


def _round4(value: float) -> float:
    """Redondeo de la casa (4 decimales) para capital, riesgo y cantidades."""
    return round(value * 10000) / 10000


def _scale(value: float | None, factor: float) -> float | None:
    """Escala proporcional de una dimensión reservada (``None`` sigue siendo ``None``)."""
    if value is None:
        return None
    return _round4(value * factor)


def normalize_side(value: Any) -> str:
    """``"buy"``/``"sell"`` normalizado; ``""`` si no es un lado válido."""
    raw = str(value or "").strip().lower()
    return raw if raw in {SIDE_BUY, SIDE_SELL} else ""


def coerce_reservation_status(value: Any) -> ReservationStatus | None:
    """Normaliza un estado de reserva; ``None`` si no es uno de los canónicos."""
    raw = str(value or "").strip().upper()
    if raw == RESERVATION_OPEN or raw in _RELEASED_STATUSES:
        return raw  # type: ignore[return-value]
    return None


# ── Coste real de negociación ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TradingCostModel:
    """Modelo de coste de **ida y vuelta** para dimensionar por riesgo real.

    ``risk_real = stop loss + comisión + spread + slippage``. Los bps de ``spread_bps`` y
    ``slippage_bps`` se interpretan por lado (como en ``cost_model_v2``/``simulated_broker``):
    el coste de ida y vuelta es ``spread_bps`` una vez (medio spread por lado) y
    ``slippage_bps`` **dos** veces (una por lado). La comisión, si hay ``settings``, sale de
    la tarifa real de la cuenta (``calculate_trade_fees``), que es la única fuente de
    verdad de comisiones; sin ella se usa ``commission_bps`` por lado.

    ``gap_bps`` modela el hueco adverso que atraviesa el stop (el stop no retiene): es una
    cola de pérdida, no una fricción, y por eso no entra en ``total``.
    """

    commission_bps: float = 10.0
    spread_bps: float = 2.0
    slippage_bps: float = 5.0
    gap_bps: float = 0.0
    settings: AccountSettings | None = None

    def commission_for(self, notional: float, exit_notional: float) -> float | None:
        """Comisión de ida y vuelta; ``None`` si no se puede cuantificar (fail-closed)."""
        if self.settings is not None:
            entry_fee = calculate_trade_fees(notional, "buy", self.settings).total
            exit_fee = calculate_trade_fees(exit_notional, "sell", self.settings).total
            return _round4(entry_fee + exit_fee)
        bps = _non_negative(self.commission_bps)
        if bps is None:
            return None
        return _round4(notional * bps / 10000.0 * 2.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "commissionBps": self.commission_bps,
            "spreadBps": self.spread_bps,
            "slippageBps": self.slippage_bps,
            "gapBps": self.gap_bps,
            "commissionPresetId": (
                self.settings.commission.preset_id if self.settings is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class TradingCost:
    """Desglose del coste de una operación y las pérdidas que de él se derivan.

    ``expected_loss`` es la pérdida si el stop se ejecuta en su nivel (stop loss +
    fricciones); ``gap_adjusted_loss`` asume que el stop **no** retiene y lo peor entre el
    stop y el hueco manda; ``worst_case_loss`` es la cota aditiva de ambos. ``measurement``
    declara cuántos componentes se pudieron cuantificar: con un componente ausente
    (p.ej. sin stop no hay ``stop_loss``) el coste **no** está completo y no debe usarse
    como número cerrado.
    """

    notional: float | None = None
    commission: float | None = None
    spread: float | None = None
    slippage: float | None = None
    gap: float | None = None
    total: float | None = None
    stop_loss: float | None = None
    expected_loss: float | None = None
    gap_adjusted_loss: float | None = None
    worst_case_loss: float | None = None
    measurement: MeasurementStatus = MEASUREMENT_UNKNOWN

    @property
    def is_complete(self) -> bool:
        return self.measurement == MEASUREMENT_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "notional": self.notional,
            "commission": self.commission,
            "spread": self.spread,
            "slippage": self.slippage,
            "gap": self.gap,
            "total": self.total,
            "stopLoss": self.stop_loss,
            "expectedLoss": self.expected_loss,
            "gapAdjustedLoss": self.gap_adjusted_loss,
            "worstCaseLoss": self.worst_case_loss,
            "measurement": self.measurement,
        }


def stop_distance(*, entry: float, stop: float, direction: str = "long") -> float | None:
    """Distancia de riesgo ``|entry − stop|``; ``None`` si la geometría es inválida.

    Long exige ``stop < entry`` y short ``stop > entry``: un stop del lado equivocado no
    es un stop, y devolver una distancia ahí inventaría un riesgo que nadie va a respetar.
    """
    e = _finite_positive(entry)
    s = _finite_positive(stop)
    if e is None or s is None:
        return None
    if direction == "short":
        return _round4(s - e) if s > e else None
    return _round4(e - s) if s < e else None


def estimate_trading_cost(
    *,
    quantity: Any,
    entry: Any,
    stop: Any = None,
    direction: str = "long",
    model: TradingCostModel | None = None,
) -> TradingCost:
    """Coste real de una operación de ``quantity`` a ``entry`` con stop ``stop``.

    Fail-closed: sin cantidad/entrada positivas no hay coste (todo ``None``,
    ``UNKNOWN``). Sin stop válido no hay ``stop_loss`` y por tanto tampoco
    ``expected_loss``/``worst_case_loss``/``gap_adjusted_loss``: el coste queda
    ``PARTIAL`` y el allocator debe tratarlo como incompleto, no como gratis.
    """
    cfg = model if model is not None else TradingCostModel()
    qty = _finite_positive(quantity)
    e = _finite_positive(entry)
    if qty is None or e is None:
        return TradingCost(measurement=MEASUREMENT_UNKNOWN)

    notional = _round4(qty * e)
    distance = stop_distance(entry=e, stop=stop, direction=direction) if stop is not None else None
    exit_price = _finite_positive(stop) if distance is not None else None
    exit_notional = _round4(qty * exit_price) if exit_price is not None else notional
    stop_loss = _round4(qty * distance) if distance is not None else None

    spread_bps = _non_negative(cfg.spread_bps)
    slip_bps = _non_negative(cfg.slippage_bps)
    gap_bps = _non_negative(cfg.gap_bps)

    commission = cfg.commission_for(notional, exit_notional)
    spread = None if spread_bps is None else _round4(notional * spread_bps / 10000.0)
    slippage = None if slip_bps is None else _round4(notional * slip_bps / 10000.0 * 2.0)
    gap = None if gap_bps is None else _round4(notional * gap_bps / 10000.0)

    total: float | None = None
    if commission is not None and spread is not None and slippage is not None:
        total = _round4(commission + spread + slippage)

    expected_loss: float | None = None
    gap_adjusted: float | None = None
    worst_case: float | None = None
    if total is not None and stop_loss is not None:
        expected_loss = _round4(stop_loss + total)
        if gap is not None:
            # El stop no retiene: manda lo peor entre lo que arriesgabas y el hueco.
            gap_adjusted = _round4(max(stop_loss, gap) + total)
            # Cota aditiva (el hueco se suma al stop): techo conservador declarado.
            worst_case = _round4(stop_loss + gap + total)

    components = (notional, commission, spread, slippage, gap, stop_loss, total, expected_loss)
    valued = sum(1 for value in components if value is not None)
    return TradingCost(
        notional=notional,
        commission=commission,
        spread=spread,
        slippage=slippage,
        gap=gap,
        total=total,
        stop_loss=stop_loss,
        expected_loss=expected_loss,
        gap_adjusted_loss=gap_adjusted,
        worst_case_loss=worst_case,
        measurement=measurement_from_counts(
            valued=valued, unvalued=len(components) - valued
        ),
    )


def _first(raw: Mapping[str, Any], *keys: str) -> float | None:
    """Primer valor presente y finito de las claves dadas (``0`` es un valor válido)."""
    for key in keys:
        if key in raw:
            value = _finite(raw[key])
            if value is not None:
                return value
    return None


def coerce_trading_cost(raw: Any) -> TradingCost | None:
    """Reconstruye un ``TradingCost`` desde su forma serializada (``to_dict``).

    ``None`` si el origen no es un coste reconocible. Un coste ilegible **no** puede
    leerse como "coste 0": el llamante debe declararlo como ausente.
    """
    if isinstance(raw, TradingCost):
        return raw
    if not isinstance(raw, Mapping):
        return None
    measurement = coerce_measurement(raw.get("measurement")) or MEASUREMENT_UNKNOWN
    return TradingCost(
        notional=_first(raw, "notional"),
        commission=_first(raw, "commission"),
        spread=_first(raw, "spread"),
        slippage=_first(raw, "slippage"),
        gap=_first(raw, "gap"),
        total=_first(raw, "total"),
        stop_loss=_first(raw, "stopLoss", "stop_loss"),
        expected_loss=_first(raw, "expectedLoss", "expected_loss"),
        gap_adjusted_loss=_first(raw, "gapAdjustedLoss", "gap_adjusted_loss"),
        worst_case_loss=_first(raw, "worstCaseLoss", "worst_case_loss"),
        measurement=measurement,
    )


# ── La reserva ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class PortfolioReservation:
    """Una aprobación materializada en reserva, con identidad y ciclo de vida.

    Las siete dimensiones comprometidas (roadmap §3) son ``reserved_cash``,
    ``reserved_risk``, ``asset_exposure``, ``sector_exposure``, ``correlation``,
    ``strategy_capacity`` y ``liquidity_capacity``. Las tres primeras y la quinta son
    importes/coeficientes de la operación; ``strategy_capacity`` y ``liquidity_capacity``
    declaran el presupuesto de la estrategia y la capacidad de liquidez consumidos.

    Una reserva de VENTA no reserva capital (libera o cierra): ``reserved_cash = 0``. Su
    ``reserved_risk`` es 0 salvo que el llamante declare otra cosa (vender no añade riesgo
    nuevo, pero puede realizarlo).
    """

    reservation_id: str
    account_id: str = ""
    tick_id: str = ""
    instrument_id: str = ""
    side: str = ""
    sector: str | None = None
    strategy_version_id: str | None = None
    quantity: float = 0.0
    entry: float | None = None
    stop: float | None = None
    reserved_cash: float | None = None
    reserved_risk: float | None = None
    asset_exposure: float | None = None
    sector_exposure: float | None = None
    correlation: float | None = None
    strategy_capacity: float | None = None
    liquidity_capacity: float | None = None
    cost: TradingCost | None = None
    status: ReservationStatus = RESERVATION_OPEN
    created_at: str | None = None
    released_at: str | None = None
    release_reason: str | None = None
    released_qty: float = 0.0
    remaining_qty: float = 0.0
    lease_generation: int = 0

    def __post_init__(self) -> None:
        if not str(self.reservation_id or "").strip():
            raise ValueError("PortfolioReservation exige reservation_id no vacío")

    @property
    def is_live(self) -> bool:
        """True solo si sigue consumiendo capital/riesgo (``OPEN`` con cantidad viva)."""
        return self.status == RESERVATION_OPEN and self.remaining_qty > _QTY_EPS

    @property
    def is_released(self) -> bool:
        return self.status in _RELEASED_STATUSES

    @property
    def is_buy(self) -> bool:
        return self.side == SIDE_BUY

    @property
    def is_sell(self) -> bool:
        return self.side == SIDE_SELL

    @property
    def is_quantified(self) -> bool:
        """True si sus dimensiones son cuantificables (capital, riesgo y sector).

        Es la unidad con la que el libro decide su ``measurement``: una reserva que no se
        puede cuantificar del todo convierte el agregado en un SUELO.
        """
        return (
            self.side in (SIDE_BUY, SIDE_SELL)
            and self.reserved_cash is not None
            and self.reserved_risk is not None
            and bool(str(self.sector or "").strip())
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "reservationId": self.reservation_id,
            "accountId": self.account_id,
            "tickId": self.tick_id,
            "instrumentId": self.instrument_id,
            "side": self.side,
            "sector": self.sector,
            "strategyVersionId": self.strategy_version_id,
            "quantity": self.quantity,
            "entry": self.entry,
            "stop": self.stop,
            "reservedCash": self.reserved_cash,
            "reservedRisk": self.reserved_risk,
            "assetExposure": self.asset_exposure,
            "sectorExposure": self.sector_exposure,
            "correlation": self.correlation,
            "strategyCapacity": self.strategy_capacity,
            "liquidityCapacity": self.liquidity_capacity,
            "cost": None if self.cost is None else self.cost.to_dict(),
            "status": self.status,
            "createdAt": self.created_at,
            "releasedAt": self.released_at,
            "releaseReason": self.release_reason,
            "releasedQty": self.released_qty,
            "remainingQty": self.remaining_qty,
            "leaseGeneration": self.lease_generation,
        }


def build_reservation(
    *,
    reservation_id: str,
    instrument_id: str,
    quantity: Any,
    side: Any = SIDE_BUY,
    account_id: str = "",
    tick_id: str = "",
    sector: Any = None,
    strategy_version_id: Any = None,
    entry: Any = None,
    stop: Any = None,
    reserved_cash: Any = None,
    reserved_risk: Any = None,
    asset_exposure: Any = None,
    sector_exposure: Any = None,
    correlation: Any = None,
    strategy_capacity: Any = None,
    liquidity_capacity: Any = None,
    cost: TradingCost | None = None,
    created_at: str | None = None,
    lease_generation: int = 0,
) -> PortfolioReservation:
    """Construye una reserva normalizando lo que se conozca (fail-closed).

    Derivación:

    * VENTA ⇒ ``reserved_cash = 0`` y ``asset_exposure = 0`` (no compromete capital).
    * COMPRA ⇒ si el llamante no aporta ``reserved_cash`` se deriva de ``quantity × entry``;
      ``asset_exposure`` cae a ``reserved_cash``.
    * ``sector_exposure`` solo existe si hay sector declarado: sin sector la exposición
      sectorial **no es 0**, es desconocida (``None``), y el libro lo declara.
    * ``reserved_risk`` **no se inventa**: sin ``TradePlan``/allocator que lo declare queda
      ``None`` y el libro baja su ``measurement`` (nunca un 0 que se lea como "riesgo nulo").
    """
    normalized_side = normalize_side(side)
    qty = _finite_positive(quantity)
    px = _finite_positive(entry)
    resolved_sector = (
        str(sector).strip() if isinstance(sector, str) and str(sector).strip() else None
    )

    explicit_cash = _finite(reserved_cash)
    resolved_cash: float | None
    if normalized_side == SIDE_SELL:
        resolved_cash = explicit_cash if explicit_cash is not None else 0.0
    elif normalized_side == SIDE_BUY and qty is not None and px is not None:
        resolved_cash = explicit_cash if explicit_cash is not None else _round4(qty * px)
    else:
        resolved_cash = explicit_cash

    resolved_asset = _finite(asset_exposure)
    if resolved_asset is None:
        resolved_asset = resolved_cash

    resolved_sector_exposure = _finite(sector_exposure)
    if resolved_sector_exposure is None and resolved_sector is not None:
        resolved_sector_exposure = resolved_cash

    return PortfolioReservation(
        reservation_id=str(reservation_id or "").strip(),
        account_id=str(account_id or "").strip(),
        tick_id=str(tick_id or "").strip(),
        instrument_id=str(instrument_id or "").strip(),
        side=normalized_side,
        sector=resolved_sector,
        strategy_version_id=(
            str(strategy_version_id).strip()
            if isinstance(strategy_version_id, str) and strategy_version_id.strip()
            else None
        ),
        quantity=_round4(qty) if qty is not None else 0.0,
        entry=px,
        stop=_finite_positive(stop),
        reserved_cash=resolved_cash,
        reserved_risk=_finite(reserved_risk),
        asset_exposure=resolved_asset,
        sector_exposure=resolved_sector_exposure,
        correlation=_finite(correlation),
        strategy_capacity=_finite(strategy_capacity),
        liquidity_capacity=_finite(liquidity_capacity),
        cost=cost,
        status=RESERVATION_OPEN,
        created_at=created_at,
        remaining_qty=_round4(qty) if qty is not None else 0.0,
        lease_generation=max(0, int(lease_generation)),
    )


# ── El libro de reservas ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ReservationEvent:
    """Un paso del ciclo de vida de una reserva (unitario, serializable y reproducible).

    ``kind="reserve"`` exige la reserva completa; ``kind="release"`` basta con su
    identidad más el estado y la cantidad liberada (que por defecto es la viva).

    El evento es la unidad de ``replay``: un evento que no se puede aplicar **no puede
    representarse**. Un ``kind`` desconocido se aplicaría como liberación (relajaría el
    libro) y un alta sin su reserva se perdería en silencio (el libro reconstruido
    declararía MENOS capital comprometido del real, que es la dirección peligrosa), así
    que ambos se rechazan al construir en vez de degradarse al reproducir.
    """

    kind: ReservationEventKind
    reservation_id: str
    reservation: PortfolioReservation | None = None
    status: ReservationStatus = RESERVATION_RELEASED_BY_CANCEL
    reason: str | None = None
    released_qty: float | None = None
    at: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _RESERVATION_EVENT_KINDS:
            raise ValueError(
                f"ReservationEvent exige kind {RESERVATION_EVENT_RESERVE!r}/"
                f"{RESERVATION_EVENT_RELEASE!r}: {self.kind!r}"
            )
        if self.kind == RESERVATION_EVENT_RESERVE and self.reservation is None:
            raise ValueError("ReservationEvent de alta exige la reserva completa")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "reservationId": self.reservation_id,
            "reservation": None if self.reservation is None else self.reservation.to_dict(),
            "status": self.status,
            "reason": self.reason,
            "releasedQty": self.released_qty,
            "at": self.at,
        }


class ReservationLedger:
    """Libro de reservas de una cuenta/tick: alta, consulta y liberación explícitas.

    Invariantes (los mide el gate de la fase):

    * ``reserved_cash == Σ reserved_cash de las reservas VIVAS`` (ídem ``reserved_risk``).
    * Ninguna reserva consume dos veces: el alta es idempotente por ``reservation_id``.
    * Toda reserva viva tiene una liberación posible por fill, cancelación, reinicio o
      rollback, y liberar no duplica (liberar dos veces es un no-op).
    * El libro es **reproducible**: ``replay(ledger.events())`` devuelve el mismo estado.
    """

    def __init__(self, *, account_id: str = "", tick_id: str = "") -> None:
        self.account_id = str(account_id or "").strip()
        self.tick_id = str(tick_id or "").strip()
        self._reservations: dict[str, PortfolioReservation] = {}
        self._events: list[ReservationEvent] = []

    # -- alta ---------------------------------------------------------------------

    def reserve(self, reservation: PortfolioReservation) -> PortfolioReservation | None:
        """Da de alta una reserva; ``None`` si ya existe o no tiene cantidad viva.

        Devolver ``None`` en vez de sobrescribir es lo que hace imposible que dos
        aprobaciones del mismo tick se pisen la reserva y comprometan el mismo capital
        dos veces.
        """
        key = str(reservation.reservation_id or "").strip()
        if not key or key in self._reservations:
            return None
        if reservation.remaining_qty <= _QTY_EPS:
            return None
        self._reservations[key] = reservation
        self._events.append(
            ReservationEvent(
                kind=RESERVATION_EVENT_RESERVE,
                reservation_id=key,
                reservation=reservation,
                at=reservation.created_at,
            )
        )
        return reservation

    # -- liberación ---------------------------------------------------------------

    def release(
        self,
        reservation_id: str,
        *,
        status: ReservationStatus = RESERVATION_RELEASED_BY_CANCEL,
        reason: str | None = None,
        released_qty: Any = None,
        at: str | None = None,
    ) -> PortfolioReservation | None:
        """Libera total o parcialmente una reserva viva (``None`` si no había nada que liberar).

        Una liberación **parcial** (un fill parcial) escala proporcionalmente capital,
        riesgo y exposición a la cantidad que queda viva: lo llenado deja de ser reserva y
        pasa a ser posición, y la cola sigue siendo capital comprometido. Una liberación
        **total** cierra la reserva con el ``status`` indicado.

        Idempotente: si la reserva no existe o ya está liberada devuelve ``None`` sin
        tocar el libro (nunca un doble liberado).
        """
        key = str(reservation_id or "").strip()
        current = self._reservations.get(key)
        if current is None or not current.is_live:
            return None
        total = current.remaining_qty
        requested = _finite_positive(released_qty)
        qty = total if requested is None else min(requested, total)
        if qty <= _QTY_EPS:
            return None
        remaining = _round4(max(0.0, total - qty))
        fully_released = remaining <= _QTY_EPS
        # Las dimensiones reservadas significan "comprometido AHORA": una liberación
        # parcial las escala a lo que queda vivo y una total las deja a 0. Lo que se
        # reservó originalmente queda en el evento de alta (historia inmutable), no en el
        # estado del libro. Invariante de este camino: una reserva NO viva tiene sus
        # dimensiones a 0 (``factor=0.0``). OJO: ese invariante lo cumple ``release``, no
        # la propiedad: ``reserved_cash``/``reserved_risk`` filtran ADEMÁS por ``.live()``
        # como cinturón de seguridad, porque cualquier camino de liberación futuro debe
        # seguir escalando a 0 para que sumar ``all()`` sin filtrar no doble-cuente. El
        # contrato lo garantiza la propiedad; no te "ahorres" el filtro por este comentario.
        factor = 0.0 if fully_released else remaining / total
        resolved_reason = reason or current.release_reason
        updated = replace(
            current,
            reserved_cash=_scale(current.reserved_cash, factor),
            reserved_risk=_scale(current.reserved_risk, factor),
            asset_exposure=_scale(current.asset_exposure, factor),
            sector_exposure=_scale(current.sector_exposure, factor),
            strategy_capacity=_scale(current.strategy_capacity, factor),
            liquidity_capacity=_scale(current.liquidity_capacity, factor),
            released_qty=_round4(current.released_qty + qty),
            remaining_qty=remaining,
            status=status if fully_released else current.status,
            released_at=at or current.released_at,
            release_reason=resolved_reason,
        )
        self._reservations[key] = updated
        self._events.append(
            ReservationEvent(
                kind=RESERVATION_EVENT_RELEASE,
                reservation_id=key,
                status=status,
                reason=resolved_reason,
                released_qty=_round4(qty),
                at=at,
            )
        )
        return updated

    def release_by_fill(
        self, reservation_id: str, *, filled_qty: Any, at: str | None = None
    ) -> PortfolioReservation | None:
        """Libera la parte de la reserva que un fill materializó."""
        return self.release(
            reservation_id,
            status=RESERVATION_RELEASED_BY_FILL,
            reason=RELEASE_REASON_FILL,
            released_qty=filled_qty,
            at=at,
        )

    def release_by_cancel(
        self, reservation_id: str, *, reason: str | None = None, at: str | None = None
    ) -> PortfolioReservation | None:
        """Libera una reserva cancelada/descartada sin fill."""
        return self.release(
            reservation_id,
            status=RESERVATION_RELEASED_BY_CANCEL,
            reason=reason or RELEASE_REASON_CANCEL,
            at=at,
        )

    def release_by_restart(
        self, reservation_id: str, *, reason: str | None = None, at: str | None = None
    ) -> PortfolioReservation | None:
        """Libera una reserva que un reinicio declara no reconciliable."""
        return self.release(
            reservation_id,
            status=RESERVATION_RELEASED_BY_RESTART,
            reason=reason or RELEASE_REASON_RESTART,
            at=at,
        )

    def rollback(
        self, *, tick_id: str | None = None, at: str | None = None
    ) -> tuple[PortfolioReservation, ...]:
        """Deshace (libera) las reservas vivas, opcionalmente solo las de un tick.

        Es la operación que hace la reserva **reversible**: si un tick se aborta
        (excepción, veto posterior, replay), su presupuesto comprometido vuelve a estar
        disponible en vez de quedarse colgado hasta el siguiente reinicio.
        """
        wanted = None if tick_id is None else str(tick_id).strip()
        released: list[PortfolioReservation] = []
        for reservation in self.live():
            if wanted is not None and reservation.tick_id != wanted:
                continue
            updated = self.release(
                reservation.reservation_id,
                status=RESERVATION_RELEASED_BY_ROLLBACK,
                reason=RELEASE_REASON_ROLLBACK,
                at=at,
            )
            if updated is not None:
                released.append(updated)
        return tuple(released)

    # -- consulta -----------------------------------------------------------------

    def get(self, reservation_id: str) -> PortfolioReservation | None:
        return self._reservations.get(str(reservation_id or "").strip())

    def all(self) -> tuple[PortfolioReservation, ...]:
        """Todas las reservas en orden de alta (determinista)."""
        return tuple(self._reservations.values())

    def live(self) -> tuple[PortfolioReservation, ...]:
        """Reservas vivas en orden de alta (las únicas que consumen presupuesto)."""
        return tuple(r for r in self._reservations.values() if r.is_live)

    @property
    def reserved_cash(self) -> float:
        """Capital reservado: Σ de las reservas VIVAS (nunca incluye liberadas)."""
        return _round4(sum(max(0.0, r.reserved_cash or 0.0) for r in self.live()))

    @property
    def reserved_risk(self) -> float:
        """Riesgo reservado: Σ de las reservas VIVAS."""
        return _round4(sum(max(0.0, r.reserved_risk or 0.0) for r in self.live()))

    def cash_by_sector(self) -> dict[str, float]:
        """Capital reservado vivo por sector (``<unknown>`` si la reserva no lo declara)."""
        return self._by_sector(lambda r: r.reserved_cash)

    def risk_by_sector(self) -> dict[str, float]:
        """Riesgo reservado vivo por sector (``<unknown>`` si la reserva no lo declara)."""
        return self._by_sector(lambda r: r.reserved_risk)

    def risk_by_strategy(self) -> dict[str, float]:
        """Riesgo reservado vivo por versión de estrategia (``<unknown>`` si no la declara)."""
        buckets: dict[str, float] = {}
        for reservation in self.live():
            risk = _non_negative(reservation.reserved_risk)
            if risk is None:
                continue
            key = str(reservation.strategy_version_id or "").strip() or UNKNOWN_SECTOR
            buckets[key] = _round4(buckets.get(key, 0.0) + risk)
        return buckets

    def _by_sector(self, pick: Any) -> dict[str, float]:
        buckets: dict[str, float] = {}
        for reservation in self.live():
            value = _non_negative(pick(reservation))
            if value is None:
                continue
            key = str(reservation.sector or "").strip() or UNKNOWN_SECTOR
            buckets[key] = _round4(buckets.get(key, 0.0) + value)
        return buckets

    def live_measurement(self) -> MeasurementStatus:
        """Estado de medición de las reservas vivas (fail-closed).

        Una reserva viva que no declara capital, riesgo o sector convierte el agregado en
        un SUELO: el consumidor que no pueda tolerarlo debe vetar, no asumir 0.
        """
        live = self.live()
        quantified = sum(1 for r in live if r.is_quantified)
        return measurement_from_counts(
            valued=quantified, unvalued=len(live) - quantified
        )

    def committed_positions(self) -> tuple[PortfolioPosition, ...]:
        """Proyecta las reservas vivas como posiciones comprometidas del tick.

        Es el puente con ``AutoPortfolioSnapshot``: la foto de trabajo del tick se construye
        sumando estas posiciones a las reales, de modo que el motor de decisión vea el
        capital y el riesgo YA reservados. La proyección no es la reserva (la reserva tiene
        identidad y ciclo de vida); es su forma agregable para la aritmética del snapshot.
        """
        positions: list[PortfolioPosition] = []
        for reservation in self.live():
            if reservation.is_sell:
                # Una VENTA no compromete capital: libera/cierra, no consume presupuesto.
                continue
            if not reservation.instrument_id:
                continue
            market_value = _finite(reservation.reserved_cash)
            positions.append(
                PortfolioPosition(
                    instrument_id=reservation.instrument_id,
                    quantity=reservation.remaining_qty,
                    market_value=market_value,
                    sector=reservation.sector,
                    risk_amount=_finite(reservation.reserved_risk),
                )
            )
        return tuple(positions)

    def events(self) -> tuple[ReservationEvent, ...]:
        """Secuencia de operaciones aplicada (reproducible con ``replay``)."""
        return tuple(self._events)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "tickId": self.tick_id,
            "reservations": [r.to_dict() for r in self.all()],
            "live": [r.reservation_id for r in self.live()],
            "reservedCash": self.reserved_cash,
            "reservedRisk": self.reserved_risk,
            "cashBySector": self.cash_by_sector(),
            "riskBySector": self.risk_by_sector(),
            "riskByStrategy": self.risk_by_strategy(),
            "measurement": self.live_measurement(),
        }


def replay(
    events: Iterable[ReservationEvent], *, account_id: str = "", tick_id: str = ""
) -> ReservationLedger:
    """Reproduce un libro aplicando la MISMA secuencia de eventos.

    Determinista por construcción: mismo orden de eventos ⇒ mismo libro y mismo
    ``reserved_cash``/``reserved_risk``. Es lo que permite auditar/rehacer un tick sin
    volver a decidir: ``replay(ledger.events())`` reconstruye el estado exacto.

    El ``kind`` de ``ReservationEvent`` es canónico por construcción y un alta siempre
    trae su reserva, así que no hay evento que se pueda "aplicar por la puerta de atrás"
    ni alta que se pierda: lo que no se puede reproducir no se puede ni representar.
    """
    ledger = ReservationLedger(account_id=account_id, tick_id=tick_id)
    for event in events:
        if event.kind == RESERVATION_EVENT_RESERVE:
            if event.reservation is not None:
                ledger.reserve(event.reservation)
            continue
        ledger.release(
            event.reservation_id,
            status=event.status,
            reason=event.reason,
            released_qty=event.released_qty,
            at=event.at,
        )
    return ledger


# ── Estado de riesgo de cartera ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PortfolioRiskState:
    """Las dimensiones de riesgo de la cartera, todas explícitas y con medición.

    ``gross_risk`` es la suma de riesgo vivo (posiciones abiertas + reservas vivas);
    ``net_risk`` coincide con ella en long-only (no hay cortos que compensen) y se publica
    igualmente para que un futuro motor con cortos no tenga que cambiar el contrato.
    ``reserved_risk`` es el riesgo YA comprometido por reservas vivas, ``pending_risk`` el
    de las órdenes durables no materializadas, y ``correlation_adjusted_risk`` la cota
    superior conservadora (ver ``build_portfolio_risk_state``).

    ``gross_risk``/``net_risk`` son ``None`` cuando el riesgo de las posiciones **no se
    pudo medir**: "no sé cuánto arriesga la cartera" no puede leerse como un total menor.
    """

    gross_risk: float | None = None
    net_risk: float | None = None
    reserved_risk: float | None = None
    pending_risk: float | None = None
    sector_risk: dict[str, float] = field(default_factory=dict)
    strategy_risk: dict[str, float] = field(default_factory=dict)
    correlation_adjusted_risk: float | None = None
    measurement: MeasurementStatus = MEASUREMENT_UNKNOWN

    @property
    def is_complete(self) -> bool:
        return self.measurement == MEASUREMENT_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "grossRisk": self.gross_risk,
            "netRisk": self.net_risk,
            "reservedRisk": self.reserved_risk,
            "pendingRisk": self.pending_risk,
            "sectorRisk": dict(self.sector_risk),
            "strategyRisk": dict(self.strategy_risk),
            "correlationAdjustedRisk": self.correlation_adjusted_risk,
            "measurement": self.measurement,
        }


def sector_risk_from_positions(
    positions: Iterable[PortfolioPosition],
) -> tuple[dict[str, float], int]:
    """Riesgo por sector de las posiciones abiertas y cuántas no declaran su riesgo.

    Devuelve ``(por_sector, sin_medir)``. Una posición sin ``risk_amount`` **no** aporta 0:
    incrementa ``sin_medir``, porque "no sé cuánto arriesga" no es "no arriesga".
    """
    buckets: dict[str, float] = {}
    unmeasured = 0
    for position in positions:
        if position.quantity <= 0:
            continue
        risk = _non_negative(position.risk_amount)
        if risk is None:
            unmeasured += 1
            continue
        key = str(position.sector or "").strip() or UNKNOWN_SECTOR
        buckets[key] = _round4(buckets.get(key, 0.0) + risk)
    return buckets, unmeasured


def build_portfolio_risk_state(
    *,
    ledger: ReservationLedger | None = None,
    position_risk_total: Any = None,
    position_risk_by_sector: Mapping[str, float] | None = None,
    unmeasured_positions: int = 0,
    pending_risk: Any = 0.0,
) -> PortfolioRiskState:
    """Compone el estado de riesgo de cartera a partir del libro y de las posiciones.

    ``position_risk_total`` es el riesgo ya consumido por posiciones abiertas (el
    ``risk_used`` del snapshot); ``position_risk_by_sector`` su desglose y
    ``unmeasured_positions`` cuántas posiciones no lo declaran. ``pending_risk`` es el de
    las órdenes durables no materializadas.

    Fail-closed en el total: si el riesgo de las posiciones **no se pudo medir**
    (``position_risk_total`` ``None``/inválido), ``gross_risk`` y ``net_risk`` quedan
    ``None`` — nunca se publica "solo lo reservado" como si fuera el total, porque un
    suelo leído como total es justo lo que este módulo existe para evitar. El
    ``measurement`` degrada en consecuencia. Sin libro, el riesgo reservado es 0 medido.

    ``correlation_adjusted_risk`` es una **cota superior conservadora**: parte de
    ``reserved_risk`` y suma ``reserved_risk × max(0, correlación)`` por reserva. Con la
    correlación sin declarar no se descuenta nada — exactamente el estado actual del
    motor ("hoy solo Σ stop risk") — y declarar correlación positiva **incrementa** la
    cota; nunca la reduce, porque asumir diversificación que no se ha medido es
    precisamente lo que un sistema fail-closed no puede hacer.
    """
    book = ledger
    reserved_risk = book.reserved_risk if book is not None else 0.0
    pending = _non_negative(pending_risk)
    position_total = _non_negative(position_risk_total)

    gross: float | None = None
    if position_total is not None:
        # Solo se publica un total cuando el riesgo de las posiciones está MEDIDO: un
        # ``position_total=None`` (hay posiciones sin ``risk_amount``) no puede sumarse
        # como 0 ni siquiera para publicar "solo lo reservado" — sería un suelo leído
        # como total. ``reserved_risk`` nunca es ``None`` (es 0 medido sin libro), así que
        # no decide si el cálculo es posible: solo forma parte del cálculo.
        gross = _round4(position_total + reserved_risk)

    correlation_adjusted: float | None = None
    if book is not None:
        total = 0.0
        measurable = True
        for reservation in book.live():
            risk = _non_negative(reservation.reserved_risk)
            if risk is None:
                measurable = False
                break
            correlation = _non_negative(reservation.correlation) or 0.0
            total += risk * (1.0 + correlation)
        correlation_adjusted = _round4(total) if measurable else None
    else:
        # Sin libro no hay reserva que ajustar: el riesgo reservado es 0 medido.
        correlation_adjusted = 0.0

    sector_risk = dict(position_risk_by_sector or {})
    if book is not None:
        for sector, risk in book.risk_by_sector().items():
            sector_risk[sector] = _round4(sector_risk.get(sector, 0.0) + risk)
    strategy_risk = book.risk_by_strategy() if book is not None else {}

    scalars = (gross, reserved_risk, pending, correlation_adjusted)
    valued = sum(1 for value in scalars if value is not None)
    unvalued = len(scalars) - valued + max(0, int(unmeasured_positions))
    return PortfolioRiskState(
        gross_risk=gross,
        net_risk=gross,
        reserved_risk=reserved_risk,
        pending_risk=pending,
        sector_risk=sector_risk,
        strategy_risk=strategy_risk,
        correlation_adjusted_risk=correlation_adjusted,
        measurement=measurement_from_counts(valued=valued, unvalued=unvalued),
    )


__all__ = [
    "RELEASE_REASON_CANCEL",
    "RELEASE_REASON_FILL",
    "RELEASE_REASON_RESTART",
    "RELEASE_REASON_ROLLBACK",
    "RESERVATION_EVENT_RELEASE",
    "RESERVATION_EVENT_RESERVE",
    "RESERVATION_OPEN",
    "RESERVATION_RELEASED_BY_CANCEL",
    "RESERVATION_RELEASED_BY_FILL",
    "RESERVATION_RELEASED_BY_RESTART",
    "RESERVATION_RELEASED_BY_ROLLBACK",
    "SIDE_BUY",
    "SIDE_SELL",
    "PortfolioReservation",
    "PortfolioRiskState",
    "ReservationEvent",
    "ReservationEventKind",
    "ReservationLedger",
    "ReservationStatus",
    "TradingCost",
    "TradingCostModel",
    "build_portfolio_risk_state",
    "build_reservation",
    "coerce_reservation_status",
    "coerce_trading_cost",
    "estimate_trading_cost",
    "normalize_side",
    "replay",
    "sector_risk_from_positions",
    "stop_distance",
]
