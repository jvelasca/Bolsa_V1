"""PositionLedger — la posición como Σ FILLS APLICADOS (AUTO 2.0 · AUTO-1A).

La ambigüedad que cierra este módulo (auditoría v2.40.4-beta, hallazgo P0 nº1):

    POSITION = quantity de la ORDEN        ← incorrecto
    POSITION = INTENDED quantity           ← incorrecto
    POSITION = contexto de simulación      ← incorrecto
    POSITION = Σ APPLIED FILLS             ← única fuente de verdad

Un fill puede quedar **parcialmente materializado**: el venue llena 50 + 23,5 de una
orden de 100 y los chunks de cola quedan en ``RETRY`` (no han movido dinero). Si el
worker contabiliza los 100 pedidos, la posición real (73,5) y el exit (100) divergen, y
el hueco viaja a riesgo, exposición, equity y protección.

Reglas de honestidad de este read-model:

* Solo entra lo **aplicado** (``APPLIED``). ``CAPTURED``/``APPLYING``/``RETRY``/``FAILED``
  son órdenes pendientes: su capital se reserva (``open_order``), jamás se realiza.
* Una venta aplicada por encima de lo comprado es una **violación** explícita: no se
  inventa un corto ni se realiza P&L de una posición que no existía.
* Una fila no interpretable (lado/cantidad/precio inválidos) **no se descarta en
  silencio**: baja el estado de medición, de modo que "no pude leer el libro" nunca se
  confunda con "el libro está plano".

Módulo puro y determinista (sin I/O y sin reloj): el I/O vive en la capa de aplicación
(``bolsa_application.applied_fills``) y la decisión en el worker.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MeasurementStatus,
    measurement_from_counts,
)

SIDE_BUY = "buy"
SIDE_SELL = "sell"

# ``quantity`` de la posición es Σ compras aplicadas; una venta no puede superarla.
_QTY_EPS = 1e-9


def round4(value: float) -> float:
    """Redondeo de la casa (4 decimales) para cantidades y precios."""
    return round(value * 10000) / 10000


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


def normalize_side(value: Any) -> str:
    """``"buy"``/``"sell"`` normalizado; ``""`` si no es un lado válido."""
    raw = str(value or "").strip().lower()
    return raw if raw in {SIDE_BUY, SIDE_SELL} else ""


@dataclass(frozen=True, slots=True)
class AppliedFillFact:
    """Un fill cuyo dinero YA se materializó (``execution_events.status == APPLIED``).

    Es la unidad atómica del libro: sin ``execution_id`` no hay identidad financiera y la
    fila no es reconciliable. ``applied_at`` ordena el fold (determinismo del P&L
    realizado); su ausencia no invalida el hecho, solo lo deja sin fecha.
    """

    execution_id: str
    instrument_id: str
    side: str
    quantity: float
    price: float
    applied_at: str | None = None
    strategy_version_id: str | None = None
    # AUTO hardening (v2.43.2): la posición es POR CUENTA. Sin esto, un libro leído con
    # ``account_id=None`` (todas las cuentas) fundía en ``quantities()`` dos posiciones del
    # mismo instrumento en cuentas distintas y la reconciliación no podía distinguirlas.
    # Un hecho sin cuenta declarada va al cajón ``""`` (se agrupa, nunca se suma a otra).
    account_id: str = ""

    def __post_init__(self) -> None:
        if not str(self.execution_id or "").strip():
            raise ValueError("AppliedFillFact exige execution_id no vacío")
        if self.side not in (SIDE_BUY, SIDE_SELL):
            # Un lado que no es compra NI venta NO se puede doblar: el fold lo trataría
            # como una venta (reduciría la posición y realizaría P&L contra un coste que
            # no le corresponde). La fila no interpretable se declara al LEER
            # (``coerce_applied_fill_fact`` ⇒ rechazada ⇒ measurement), nunca se
            # representa como un hecho con un lado inventado.
            raise ValueError(
                f"AppliedFillFact exige side {SIDE_BUY!r}/{SIDE_SELL!r}: {self.side!r}"
            )

    @property
    def is_buy(self) -> bool:
        return self.side == SIDE_BUY

    @property
    def is_sell(self) -> bool:
        return self.side == SIDE_SELL

    @property
    def notional(self) -> float:
        return round4(self.quantity * self.price)

    def to_dict(self) -> dict[str, Any]:
        return {
            "executionId": self.execution_id,
            "instrumentId": self.instrument_id,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "notional": self.notional,
            "appliedAt": self.applied_at,
            "strategyVersionId": self.strategy_version_id,
            "accountId": self.account_id,
        }


@dataclass(frozen=True, slots=True)
class LedgerPosition:
    """Posición materializada de un instrumento, derivada SOLO de fills aplicados.

    ``quantity`` es Σ compras aplicadas (tamaño bruto de entrada) y ``remaining_qty`` la
    posición viva; ``realized_qty`` es la cantidad de ventas que **realmente casó** contra
    inventario comprado (``quantity_closed``). La relación canónica es
    ``remaining_qty == quantity - realized_qty`` (nunca negativa: si las ventas superan
    las compras, hay violación y se declara).

    ``sold_qty`` es Σ ventas **ejecutadas** (lo que el venue movió) y
    ``unmatched_exit_qty = sold_qty - realized_qty`` el exceso que no tenía inventario
    contra el que casar. Separarlos es lo que evita que una venta rechazada (o el exceso
    de un oversell) se cuele en ``realized_qty`` y oculte compras legítimas posteriores:
    ``realized_qty`` solo avanza por lo casado, igual que ``cost_basis``/``realized_pnl``.

    ``average_entry`` es el coste medio de lo que **queda abierto**: una posición plana no
    tiene entrada y publica ``None`` (nunca 0,0). Un consumidor que necesite el precio de
    entrada histórico lo tiene en ``fills``, no en un campo de la posición viva.
    """

    instrument_id: str
    quantity: float
    realized_qty: float
    remaining_qty: float
    average_entry: float | None
    realized_pnl: float
    fills: tuple[AppliedFillFact, ...] = ()
    violations: tuple[str, ...] = ()
    # AUTO hardening (v2.43.2) — cantidad vendida EJECUTADA y exceso no casado. Aditivos:
    # un consumidor anterior que solo lea ``realized_qty`` sigue viendo la cantidad
    # cerrada real (que ahora sí es ``min(Σ SELL, Σ BUY)``, no ``Σ SELL``).
    sold_qty: float = 0.0
    unmatched_exit_qty: float = 0.0
    account_id: str = ""

    @property
    def is_open(self) -> bool:
        return self.remaining_qty > _QTY_EPS

    @property
    def is_flat(self) -> bool:
        return not self.is_open

    @property
    def cost_basis(self) -> float | None:
        """Coste de lo que queda abierto (``None`` sin entrada conocida)."""
        if self.average_entry is None:
            return None
        return round4(self.remaining_qty * self.average_entry)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrumentId": self.instrument_id,
            "accountId": self.account_id,
            "quantity": self.quantity,
            "realizedQty": self.realized_qty,
            "soldQty": self.sold_qty,
            "unmatchedExitQty": self.unmatched_exit_qty,
            "remainingQty": self.remaining_qty,
            "averageEntry": self.average_entry,
            "costBasis": self.cost_basis,
            "realizedPnl": self.realized_pnl,
            "fillCount": len(self.fills),
            "violations": list(self.violations),
        }


@dataclass(frozen=True, slots=True)
class PositionLedger:
    """Libro de posición completo: posiciones + huecos de medición declarados."""

    positions: tuple[LedgerPosition, ...] = ()
    measurement: MeasurementStatus = MEASUREMENT_COMPLETE
    facts_applied: int = 0
    facts_rejected: int = 0
    violations: tuple[str, ...] = ()

    def position(self, instrument_id: str) -> LedgerPosition | None:
        target = str(instrument_id or "").strip()
        for candidate in self.positions:
            if candidate.instrument_id == target:
                return candidate
        return None

    def quantities(self) -> dict[str, float]:
        """Mapa canónico ``instrument_id → remaining_qty`` de las posiciones ABIERTAS.

        Es la forma que consume la reconciliación del worker: la posición viva derivada
        de fills aplicados, nunca la cantidad pedida ni el espejo de la proyección.
        """
        return {p.instrument_id: p.remaining_qty for p in self.positions if p.is_open}

    @property
    def is_complete(self) -> bool:
        return self.measurement == MEASUREMENT_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "positions": [p.to_dict() for p in self.positions],
            "quantities": self.quantities(),
            "measurement": self.measurement,
            "factsApplied": self.facts_applied,
            "factsRejected": self.facts_rejected,
            "violations": list(self.violations),
        }


def _fold_instrument(facts: list[AppliedFillFact]) -> LedgerPosition:
    """Dobla los fills de UN instrumento en una posición materializada.

    Semántica long (la del camino AUTO actual): las compras construyen el coste medio
    ponderado y las ventas realizan P&L contra ese coste medio **en el momento de la
    venta**. Una venta sin compra previa suficiente no realiza P&L de lo que no existe:
    se registra como violación y el resto se ignora.

    Regla de oro (v2.43.2): ``realized_qty`` avanza SOLO por ``matched`` (lo que casó
    contra inventario), igual que ``cost_basis`` y ``realized_pnl``. Sumar la cantidad
    solicitada inflaba ``remaining_qty = quantity - realized_qty`` y podía reportar como
    plana una compra real posterior; el exceso rechazado queda declarado en
    ``sold_qty``/``unmatched_exit_qty`` y en ``violations``, nunca en la cantidad viva.
    """
    instrument_id = facts[0].instrument_id
    account_id = facts[0].account_id
    quantity = 0.0
    realized_qty = 0.0
    sold_qty = 0.0
    cost_basis = 0.0
    realized_pnl = 0.0
    violations: list[str] = []

    for fact in facts:
        if fact.is_buy:
            quantity += fact.quantity
            cost_basis += fact.quantity * fact.price
            continue
        # Venta aplicada: se cuenta SIEMPRE como venta ejecutada (es un hecho del venue),
        # pero solo realiza P&L / cierra cantidad en la parte que casa contra inventario.
        # El ``else`` es una venta por CONSTRUCCIÓN: ``AppliedFillFact`` solo admite
        # ``buy``/``sell``, así que ningún lado no interpretable puede llegar hasta aquí
        # (una fila ilegible se declara al leerla, no se disfraza de venta).
        sold_qty += fact.quantity
        avg_entry = (cost_basis / quantity) if quantity > _QTY_EPS else None
        sellable = quantity - realized_qty
        if sellable <= _QTY_EPS:
            violations.append(f"oversell_without_position:{fact.execution_id}")
            continue
        matched = min(fact.quantity, sellable)
        if avg_entry is not None:
            realized_pnl += matched * (fact.price - avg_entry)
            cost_basis -= matched * avg_entry
        if fact.quantity > matched + _QTY_EPS:
            violations.append(f"oversell_above_position:{fact.execution_id}")
        realized_qty += matched

    remaining = max(0.0, quantity - realized_qty)
    avg_entry = None
    if quantity > _QTY_EPS and remaining > _QTY_EPS:
        # Coste medio del inventario vivo (los recortes consumen coste proporcionalmente).
        avg_entry = round4(max(0.0, cost_basis) / remaining)
    # Una posición PLANA no tiene entrada: ``average_entry`` es ``None``, no un 0,0 de
    # arrastre ni una entrada histórica rancia. El residuo de ``cost_basis`` que deja el
    # redondeo a 4 decimales no autoriza a publicar "la entrada era 0,0" (un consumidor
    # que marque contra ese número lo haría contra cero). La historia de lo comprado vive
    # en ``fills``, no en un campo de la posición viva.

    return LedgerPosition(
        instrument_id=instrument_id,
        account_id=account_id,
        quantity=round4(quantity),
        realized_qty=round4(realized_qty),
        sold_qty=round4(sold_qty),
        unmatched_exit_qty=round4(max(0.0, sold_qty - realized_qty)),
        remaining_qty=round4(remaining),
        average_entry=avg_entry,
        realized_pnl=round4(realized_pnl),
        fills=tuple(facts),
        violations=tuple(violations),
    )


def _fold_sort_key(fact: AppliedFillFact) -> tuple[int, str, str]:
    """Clave determinista del fold: ``(tiene_fecha, applied_at, execution_id)``.

    AUTO hardening (v2.43.2): un hecho SIN fecha no puede ordenarse como si fuera el
    PRIMERO. ``str(None or "") == ""`` precede a cualquier ISO real en orden lexicográfico,
    así que una fila legada sin fecha se doblaba como "la compra más antigua" y torcía el
    coste medio (que depende del orden de compras y ventas). Los hechos sin fecha se
    separan al FINAL de forma declarada (``1``) y el orden entre ellos sigue siendo
    determinista por ``execution_id``. AUTO-1b ya cerró la causa raíz (un ``datetime`` de
    PostgreSQL dejaba de perder su fecha al normalizarse); esto protege el residuo legado.
    """
    return (
        0 if fact.applied_at else 1,
        str(fact.applied_at or ""),
        str(fact.execution_id or ""),
    )


def build_position_ledger(
    facts: Iterable[AppliedFillFact],
    *,
    rejected: int = 0,
) -> PositionLedger:
    """Construye el libro de posición a partir de fills APLICADOS.

    Orden determinista por ``(applied_at, execution_id)``: dos ejecuciones con el mismo
    conjunto de fills producen exactamente el mismo libro y el mismo P&L realizado.

    Idempotencia (v2.43.2): ``execution_id`` es la clave financiera del fill (PK de
    ``execution_events`` con ``ON CONFLICT DO NOTHING``), así que un MISMO hecho no puede
    contarse dos veces: el fold lo deduplica aquí y declara los repetidos como rechazados.
    Sin esta disciplina, dos hechos con el mismo ``execution_id`` doblaban posición, riesgo,
    cash y P&L (``APPLIED fill #123`` × 2 ⇒ 2 × fill).

    ``rejected`` declara las filas que el lector no pudo interpretar (sin lado/cantidad/
    precio): si hay alguna, el libro baja a ``PARTIAL``/``UNKNOWN`` y **no** puede
    leerse como "la posición es exactamente esta". Un libro vacío es exacto (``COMPLETE``)
    solo si no hubo filas rechazadas, duplicadas ni colisión de cuenta.
    """
    ordered = sorted(facts, key=_fold_sort_key)
    # Idempotencia por identidad financiera: gana la PRIMERA aparición (ya ordenada) y las
    # repeticiones se declaran. ``execution_id`` es global (PK), no por instrumento.
    seen: set[str] = set()
    deduped: list[AppliedFillFact] = []
    duplicates: list[str] = []
    for fact in ordered:
        key = str(fact.execution_id or "").strip()
        if key in seen:
            duplicates.append(key)
            continue
        seen.add(key)
        deduped.append(fact)

    grouped: dict[tuple[str, str], list[AppliedFillFact]] = {}
    for fact in deduped:
        grouped.setdefault((fact.account_id, fact.instrument_id), []).append(fact)

    # Colisión de instrumento entre cuentas: el mapa ``quantities()`` (instrumento →
    # cantidad viva) no puede representar dos posiciones del MISMO símbolo en cuentas
    # distintas sin fundirlas en una. Se declara degradando la medición en lugar de
    # publicar una cantidad fusionada que la reconciliación tomaría por real.
    accounts_by_instrument: dict[str, set[str]] = {}
    for account_id, instrument_id in grouped:
        accounts_by_instrument.setdefault(instrument_id, set()).add(account_id)
    cross_account_collision = any(
        len(accounts) > 1 for accounts in accounts_by_instrument.values()
    )

    positions = tuple(_fold_instrument(grouped[key]) for key in sorted(grouped))
    violations = tuple(
        f"{position.instrument_id}:{violation}"
        for position in positions
        for violation in position.violations
    ) + tuple(f"duplicate_execution_id:{execution_id}" for execution_id in duplicates)
    unvalued = max(0, rejected) + len(duplicates) + (1 if cross_account_collision else 0)
    return PositionLedger(
        positions=positions,
        measurement=measurement_from_counts(valued=len(deduped), unvalued=unvalued),
        facts_applied=len(deduped),
        facts_rejected=max(0, rejected) + len(duplicates),
        violations=violations,
    )


def _instant_text(value: Any) -> str | None:
    """Instante crudo (``str`` ISO o ``datetime``) → ``str`` ISO; ``None`` si no hay.

    AUTO-1b: el espejo durable devuelve ``datetime`` (columna ``timestamptz``) y esta
    normalización solo aceptaba ``str``, así que TODOS los hechos leídos de PostgreSQL
    quedaban **sin fecha**: el fold del libro perdía su orden determinista y la
    reconciliación de reservas no podía ventanear "¿este fill es posterior al alta?".
    Se normaliza aquí, en el único sitio que traduce filas a hechos.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat()).strip() or None
    return str(value).strip() or None


def coerce_applied_fill_fact(
    *,
    execution_id: Any,
    instrument_id: Any,
    side: Any,
    quantity: Any,
    price: Any,
    applied_at: Any = None,
    strategy_version_id: Any = None,
    account_id: Any = None,
) -> AppliedFillFact | None:
    """Normaliza una fila cruda a ``AppliedFillFact``; ``None`` si NO es interpretable.

    ``None`` significa "esta fila no se puede contar" (el llamante la declara como
    rechazada, bajando el measurement), nunca "cuenta cero".
    """
    trimmed_id = str(execution_id or "").strip()
    trimmed_instrument = str(instrument_id or "").strip()
    normalized = normalize_side(side)
    qty = _finite_positive(quantity)
    px = _finite_positive(price)
    if not trimmed_id or not trimmed_instrument or not normalized or qty is None or px is None:
        return None
    return AppliedFillFact(
        execution_id=trimmed_id,
        instrument_id=trimmed_instrument,
        side=normalized,
        quantity=round4(qty),
        price=round4(px),
        applied_at=_instant_text(applied_at),
        strategy_version_id=(
            str(strategy_version_id).strip()
            if isinstance(strategy_version_id, str) and strategy_version_id.strip()
            else None
        ),
        # La cuenta del hecho acota la posición (AUTO hardening v2.43.2). Sin ella el
        # hecho cae al cajón ``""`` y el libro no lo funde con una cuenta concreta.
        account_id=(str(account_id).strip() if account_id is not None else ""),
    )


def ledger_quantities(ledger: PositionLedger | Mapping[str, Any] | None) -> dict[str, float]:
    """Posición viva por instrumento desde un libro (o su forma serializada)."""
    if ledger is None:
        return {}
    if isinstance(ledger, PositionLedger):
        return ledger.quantities()
    if isinstance(ledger, Mapping):
        raw = ledger.get("quantities")
        if isinstance(raw, Mapping):
            out: dict[str, float] = {}
            for key, value in raw.items():
                number = _finite(value)
                if number is not None and number > 0:
                    out[str(key)] = round4(number)
            return out
    return {}


__all__ = [
    "SIDE_BUY",
    "SIDE_SELL",
    "AppliedFillFact",
    "LedgerPosition",
    "PositionLedger",
    "build_position_ledger",
    "coerce_applied_fill_fact",
    "ledger_quantities",
    "normalize_side",
    "round4",
]
