"""AUTO-1A — lectura del libro de posición desde fills APLICADOS.

Traduce el estado financiero durable a ``AppliedFillFact`` (una sola vez, en un solo
sitio) para que el ``PositionLedger`` y el worker compartan la MISMA definición de
posición:

    execution_events(status=APPLIED)  ──┐
                                        ├──► AppliedFillFact ──► PositionLedger
    sim_fill_finance_context  ──────────┘        (lado/precio)

Reglas de honestidad (fail-closed):

* ``list_unapplied`` (órdenes pendientes) y ``list_applied`` (posición) son lecturas
  DISTINTAS y no se mezclan: un ``RETRY`` reserva capital, jamás materializa posición.
* Un ``APPLIED`` cuyo contexto financiero falta o no es interpretable **no se descarta
  en silencio**: cuenta como fila rechazada y baja el estado de medición. El llamante
  que necesite certeza (reconciliación de posición) trata la lectura incompleta como
  ``UNKNOWN`` y veta aperturas — nunca reconstruye una posición con datos a medias.
* Un tope de lectura agotado (``truncated``) implica ``UNKNOWN``: ver ``limit`` filas no
  es ver el libro.

Sin aritmética financiera más allá del fold determinista del ``PositionLedger``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
    combine_measurements,
)
from bolsa_analytics.cognitive.position_ledger import (
    AppliedFillFact,
    LedgerPosition,
    PositionLedger,
    build_position_ledger,
    coerce_applied_fill_fact,
)
from bolsa_application.execution_event import ExecutionEventStore
from bolsa_application.sim_durable_store import SimFillFinanceContextStore

# Tope de lectura por defecto del libro (fills aplicados de una jornada AUTO). Igual
# criterio que el libro de pendientes: agotarlo ⇒ medición incompleta, no "no hay más".
DEFAULT_APPLIED_LIMIT = 1000

# Tolerancia de comparación entre la cantidad del ``execution_event`` (identidad
# financiera) y la del contexto (aritmética del fill): un descuadre es una divergencia
# declarada, nunca algo que se redondee a la baja.
_QTY_EPS = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class AppliedFillsRead:
    """Resultado de leer el libro de posición, con sus huecos DECLARADOS."""

    facts: tuple[AppliedFillFact, ...] = ()
    ledger: PositionLedger = field(default_factory=PositionLedger)
    measurement: MeasurementStatus = MEASUREMENT_COMPLETE
    rejected: int = 0
    mismatched: int = 0
    truncated: bool = False
    error: str | None = None

    @property
    def is_complete(self) -> bool:
        """True solo si el libro se leyó ENTERO y todas las filas se interpretaron."""
        return self.measurement == MEASUREMENT_COMPLETE

    @property
    def facts_applied(self) -> int:
        return self.ledger.facts_applied

    @property
    def facts_rejected(self) -> int:
        return self.ledger.facts_rejected

    def position(self, instrument_id: str) -> LedgerPosition | None:
        return self.ledger.position(instrument_id)

    def quantities(self) -> dict[str, float]:
        return self.ledger.quantities()

    def to_dict(self) -> dict[str, Any]:
        payload = self.ledger.to_dict()
        payload.update(
            {
                "measurement": self.measurement,
                "rejected": self.rejected,
                "mismatched": self.mismatched,
                "truncated": self.truncated,
                "error": self.error,
            }
        )
        return payload


def _unreadable(reason: str) -> AppliedFillsRead:
    """Lectura NO afirmable: el consumidor debe tratar la posición como desconocida."""
    return AppliedFillsRead(
        ledger=PositionLedger(measurement=MEASUREMENT_UNKNOWN),
        measurement=MEASUREMENT_UNKNOWN,
        error=reason,
    )


def _event_qty(event: Any) -> Decimal | None:
    raw = getattr(event, "qty", None)
    if raw is None:
        return None
    try:
        value = Decimal(str(raw))
    except (ArithmeticError, ValueError):
        return None
    if not value.is_finite() or value <= 0:
        return None
    return value


async def read_applied_fill_facts(
    exec_store: ExecutionEventStore | None,
    context_store: SimFillFinanceContextStore | None,
    account_id: str | None,
    *,
    limit: int = DEFAULT_APPLIED_LIMIT,
) -> AppliedFillsRead:
    """Lee los fills materializados y los convierte en libro de posición.

    Fail-closed en cada costura (ver docstring del módulo). Los cuatro modos de fallo
    —sin store, sin soporte de listado, excepción de lectura y tope agotado— devuelven
    ``measurement=UNKNOWN`` con el motivo, nunca un libro "vacío pero plausible".
    """
    if exec_store is None:
        return _unreadable("no_execution_event_store")
    lister = getattr(exec_store, "list_applied", None)
    if not callable(lister):
        return _unreadable("store_without_list_applied")
    if limit <= 0:
        return _unreadable("non_positive_limit")
    try:
        events = list(await lister(account_id, limit=limit))
    except Exception as exc:  # noqa: BLE001 — sin lectura no se afirma posición.
        return _unreadable(f"list_applied_failed:{type(exc).__name__}")

    truncated = len(events) >= limit

    contexts: dict[str, Any] = {}
    if events:
        if context_store is None:
            # Sin contexto financiero no hay lado/precio: ninguna fila es interpretable.
            return AppliedFillsRead(
                measurement=MEASUREMENT_UNKNOWN,
                rejected=len(events),
                truncated=truncated,
                error="no_fill_context_store",
            )
        reader = getattr(context_store, "get_many", None)
        if not callable(reader):
            return AppliedFillsRead(
                measurement=MEASUREMENT_UNKNOWN,
                rejected=len(events),
                truncated=truncated,
                error="context_store_without_get_many",
            )
        try:
            contexts = dict(
                await reader([str(getattr(e, "execution_id", "") or "") for e in events])
            )
        except Exception as exc:  # noqa: BLE001 — contexto a medias ⇒ libro a medias.
            return AppliedFillsRead(
                measurement=MEASUREMENT_UNKNOWN,
                rejected=len(events),
                truncated=truncated,
                error=f"get_many_failed:{type(exc).__name__}",
            )

    facts: list[AppliedFillFact] = []
    rejected = 0
    mismatched = 0
    for event in events:
        execution_id = str(getattr(event, "execution_id", "") or "").strip()
        context = contexts.get(execution_id)
        if context is None:
            rejected += 1
            continue
        qty = _event_qty(event)
        if qty is None:
            rejected += 1
            continue
        context_qty = getattr(context, "quantity", None)
        try:
            context_qty_dec = (
                Decimal(str(context_qty)) if context_qty is not None else None
            )
        except (ArithmeticError, ValueError):
            context_qty_dec = None
        if context_qty_dec is None or abs(context_qty_dec - qty) > _QTY_EPS:
            # La identidad financiera y la aritmética del fill no cuadran: se declara.
            mismatched += 1
        fact = coerce_applied_fill_fact(
            execution_id=execution_id,
            instrument_id=getattr(context, "instrument_id", None),
            side=getattr(context, "side", None),
            quantity=qty,
            price=getattr(context, "price", None),
            applied_at=getattr(event, "applied_at", None),
            strategy_version_id=getattr(context, "strategy_version_id", None),
            # La CUENTA del hecho acota la posición (AUTO hardening v2.43.2): con
            # ``account_id=None`` la lectura ve todas las cuentas y sin esto el libro
            # fundía dos posiciones del mismo símbolo en una sola cantidad.
            account_id=getattr(event, "account_id", None),
        )
        if fact is None:
            rejected += 1
            continue
        facts.append(fact)

    ledger = build_position_ledger(facts, rejected=rejected)
    measurement = combine_measurements(
        ledger.measurement,
        MEASUREMENT_PARTIAL if mismatched > 0 else MEASUREMENT_COMPLETE,
        MEASUREMENT_UNKNOWN if truncated else MEASUREMENT_COMPLETE,
    )
    return AppliedFillsRead(
        facts=tuple(facts),
        ledger=ledger,
        measurement=measurement,
        rejected=rejected,
        mismatched=mismatched,
        truncated=truncated,
    )


async def read_position_ledger(
    exec_store: ExecutionEventStore | None,
    context_store: SimFillFinanceContextStore | None,
    account_id: str | None,
    *,
    limit: int = DEFAULT_APPLIED_LIMIT,
) -> PositionLedger:
    """Atajo: solo el libro (el detalle de la lectura vive en ``AppliedFillsRead``)."""
    read = await read_applied_fill_facts(
        exec_store, context_store, account_id, limit=limit
    )
    return read.ledger


class CanonicalPositions(dict[str, Decimal]):
    """Mapa ``symbol -> qty materializada`` con las TRAZAS que lo sustentan.

    Es un ``dict`` (contrato del seam ``canonical_positions_reader`` intacto: cualquier
    consumidor que haga ``dict(canonical).items()`` sigue funcionando) que además lleva
    los ``AppliedFillFact`` que produjeron cada cantidad. Con ellos la reconciliación
    puede comparar ``expected`` (Σ fills aplicados) contra el canónico en el MISMO acto
    de leerlo — imprescindible tras un crash, cuando el libro en RAM del worker está
    vacío y una proyección inflada no tendría contra qué contrastarse (quedaría
    ``DIVERGENT`` y la posición inflada sobreviviría al reinicio).

    Solo incluye cantidades VIVAS (>0): un símbolo plano no es una posición y no debe
    arrastrar veredictos ni bloqueos.
    """

    __slots__ = ("facts", "measurement")

    facts: tuple[AppliedFillFact, ...]
    measurement: MeasurementStatus

    def __init__(
        self,
        quantities: Mapping[str, Any] | None = None,
        *,
        facts: tuple[AppliedFillFact, ...] = (),
        measurement: MeasurementStatus = MEASUREMENT_COMPLETE,
    ) -> None:
        rows: dict[str, Decimal] = {}
        for symbol, qty in dict(quantities or {}).items():
            try:
                value = Decimal(str(qty))
            except (ArithmeticError, ValueError):
                continue
            if value.is_finite() and value > 0:
                rows[str(symbol)] = value
        super().__init__(rows)
        self.facts = facts
        self.measurement = measurement


def build_canonical_positions(read: AppliedFillsRead) -> CanonicalPositions:
    """Convierte una lectura de fills aplicados en el mapa canónico de posición."""
    return CanonicalPositions(
        read.quantities(), facts=read.facts, measurement=read.measurement
    )


__all__ = [
    "DEFAULT_APPLIED_LIMIT",
    "AppliedFillsRead",
    "CanonicalPositions",
    "build_canonical_positions",
    "read_applied_fill_facts",
    "read_position_ledger",
]
