"""V2.14 E1 — ExecutionEvent durable + idempotencia financiera GATED (P1-01).

Un fill confirmado del venue se traduce, ANTES de tocar dinero, en una
``execution_events`` fila con identity ``execution_id`` (PK / ON CONFLICT DO
NOTHING). Esa fila es la clave de idempotencia financiera: dos eventos del MISMO
fill → el primero sólo materializa.

El materializado a PositionState/Ledger se delega a un callable ``apply_finance``
que esta capa NO invoca ciegamente:
  * si la fila ya existía → ``duplicate_skipped`` (nada se aplica dos veces);
  * si ``permit=False`` (default) → la fila se captura y queda
    ``captured_pending_operator_consent``: NO se materializa dinero (honesta H4/H3
    del repo: detect ≠ heal; se requirió go operator/máquina explícito);
  * solo cuando el go (``permit``) es otorgado por una capa autorizada se llama a
    ``apply_finance(execution)``.

Si el go llega DESPUÉS de la captura (consentimiento en dos fases oídas:
captura en T0 con ``permit=False`` y aprobación en T1), ``apply_pending_execution``
retoma la traza ya capturada y materializa sin chocar con ``duplicate_skipped``
(Auditoría 3). Esta operación no crea una 2ª captura: requiere que la traza
exista (``event_not_found`` si no), a la vez que con ``execution_id`` idempotente
evita doble materialización vía un ``apply_finance`` idempotente por execution.

El counter ``financial_apply_count`` del dominio NO es el mecanismo de idempotencia:
lo es la clave `execution_id` (venue_order_id + fill_seq).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol, runtime_checkable

_INSERTED = "inserted"
_DUPLICATE = "duplicate"
CaptureStatus = Literal["inserted", "duplicate"]
ApplyDecision = Literal[
    "duplicate_skipped",
    "captured_pending_operator_consent",
    "applied",
    "captured_not_applied",
    "event_not_found",
]

# V2.19 (P2-01) — workflow durable del apply financiero (por fases, GATED).
# Marco de truth del apply para probar crash en medio de la materialización sin
# perder/duplicar dinero. El contador NO es el mecanismo de idempotencia; lo
# sigue siendo la PK ``execution_id`` (+ ``idempotency_key`` financiera reusada).
ExecutionEventStatus = Literal[
    "CAPTURED",  # fila insertada; aún NO se ha materializado dinero.
    "APPLYING",  # una instancia posee el apply en curso (previa al commit).
    "APPLIED",  # materialización efectiva y durable (no se reaplica).
    "FAILED",  # apply no efectivo (no-retryable → requiere revisión).
    "RETRY",  # fallo transitorio → reaplicable por un tick posterior.
]

# Transiciones legales del workflow (aplicar en una capa que ya consultó la fila).
_EXECUTION_EVENT_ALLOWED: dict[ExecutionEventStatus, frozenset[ExecutionEventStatus]] = {
    "CAPTURED": frozenset({"APPLYING", "FAILED", "RETRY", "CAPTURED"}),
    "APPLYING": frozenset({"APPLIED", "FAILED", "RETRY", "APPLYING"}),
    "APPLIED": frozenset({"APPLIED"}),  # terminal: no se re-materializa.
    "FAILED": frozenset({"FAILED", "RETRY", "APPLYING"}),  # revisable/reintentable.
    "RETRY": frozenset({"APPLYING", "RETRY"}),  # solo hacia apply o quedarse.
}


def can_transition_execution_event(
    current: ExecutionEventStatus,
    nxt: ExecutionEventStatus,
) -> bool:
    """True si el workflow permite ``current → nxt`` (self por casos especiales)."""
    return nxt in _EXECUTION_EVENT_ALLOWED.get(current, frozenset())


VALID_EXECUTION_EVENT_STATUSES: frozenset[ExecutionEventStatus] = frozenset(
    _EXECUTION_EVENT_ALLOWED
)


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    """Fill durable con identidad financiera (no lleva aritmética).

    Los campos ``status``/``applied_at``/``attempt_count``/``last_error`` son el
    **workflow durable del apply** (V2.19 P2-01), observación de la fila no de la
    aritmética. ``capture`` inserta con ``status=CAPTURED``; el resto se marca
    por ``execution_id`` vía el store durable. Defaults backward-compatibles.
    """

    execution_id: str
    order_id: str
    venue: str
    qty: Decimal
    account_id: str | None = None
    venue_order_id: str | None = None
    fill_seq: int | None = None
    captured_at: datetime | None = None
    status: ExecutionEventStatus = "CAPTURED"
    applied_at: datetime | None = None
    attempt_count: int = 0
    last_error: str | None = None

    def __post_init__(self) -> None:
        if not self.execution_id or not self.execution_id.strip():
            raise ValueError("execution_id is required")
        if self.captured_at is None:
            object.__setattr__(self, "captured_at", datetime.now(UTC))


@runtime_checkable
class ExecutionEventStore(Protocol):
    async def capture(self, execution: ExecutionEvent) -> CaptureStatus: ...

    async def get(self, execution_id: str) -> ExecutionEvent | None: ...

    # V2.19 P2-01 — workflow durable (idempotente por execution_id). Quien marca
    # ``APPLYING`` primero "gana" el derecho a materializar (CAS); así dos
    # workers/restart no materializan dos veces el mismo fill. Los returns
    # devuelven False si la transición no era legal (p.ej. ya APPLIED).
    async def start_apply(self, execution_id: str) -> bool: ...

    async def mark_applied(self, execution_id: str) -> bool: ...

    async def mark_failed(self, execution_id: str, *, error: str) -> bool: ...

    async def mark_retry(self, execution_id: str, *, error: str) -> bool: ...


class InMemoryExecutionEventStore:
    """Test double: refleja la idempotencia por execution_id + workflow durable.

    El con `_rows` almacena ``ExecutionEvent`` completos (status incluido).
    ``capture`` devuelve duplicate si ya existe; los ``mark_*`` solo mutan si la
    transición es legal desde el estado actual (mismo invariante que PG).
    """

    def __init__(self) -> None:
        self._rows: dict[str, ExecutionEvent] = {}

    async def capture(self, execution: ExecutionEvent) -> CaptureStatus:
        if execution.execution_id in self._rows:
            return "duplicate"
        stored = replace(execution, status="CAPTURED")
        self._rows[execution.execution_id] = stored
        return "inserted"

    async def get(self, execution_id: str) -> ExecutionEvent | None:
        return self._rows.get(execution_id)

    async def _transition(
        self,
        execution_id: str,
        nxt: ExecutionEventStatus,
        *,
        applied_at: datetime | None = None,
        error: str | None = None,
    ) -> bool:
        current = self._rows.get(execution_id)
        if current is None:
            return False
        if not can_transition_execution_event(current.status, nxt):
            return False
        self._rows[execution_id] = replace(
            current,
            status=nxt,
            applied_at=applied_at if applied_at is not None else current.applied_at,
            attempt_count=current.attempt_count + (1 if nxt == "APPLYING" else 0),
            last_error=error if error is not None else current.last_error,
        )
        return True

    async def start_apply(self, execution_id: str) -> bool:
        return await self._transition(execution_id, "APPLYING")

    async def mark_applied(self, execution_id: str) -> bool:
        return await self._transition(execution_id, "APPLIED", applied_at=datetime.now(UTC))

    async def mark_failed(self, execution_id: str, *, error: str) -> bool:
        return await self._transition(execution_id, "FAILED", error=error)

    async def mark_retry(self, execution_id: str, *, error: str) -> bool:
        return await self._transition(execution_id, "RETRY", error=error)


class PostgresExecutionEventStore:
    """``execution_events`` en PostgreSQL con idempotencia real (ON CONFLICT).

    El unique (PK) ``execution_id`` + ``ON CONFLICT DO NOTHING ... RETURNING``
    garantiza que solo el insert que gana devuelve fila → clasifica inserted vs
    duplicate SIN lectura previa y SIN carreras (correcto entre workers).
    """

    def __init__(self, session: Any) -> None:
        self._session = session

    async def capture(self, execution: ExecutionEvent) -> CaptureStatus:
        # ON CONFLICT requiere el insert del dialecto PostgreSQL (capture idempotente
        # por execution_id en PG): el ``insert`` genérico de SQLAlchemy no expone
        # ``on_conflict_do_nothing``. Sigue siendo idempotente ante la PK/unique.
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        result = await self._session.execute(
            pg_insert(ExecutionEventRow)
            .values(
                execution_id=execution.execution_id,
                order_id=execution.order_id,
                venue=execution.venue,
                account_id=execution.account_id,
                venue_order_id=execution.venue_order_id,
                fill_seq=execution.fill_seq,
                qty=execution.qty,
                captured_at=execution.captured_at or datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=["execution_id"])
            .returning(ExecutionEventRow.execution_id)
        )
        inserted = result.scalars().first()
        return "inserted" if inserted is not None else "duplicate"

    async def get(self, execution_id: str) -> ExecutionEvent | None:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        row = (
            await self._session.execute(
                sa.select(ExecutionEventRow).where(ExecutionEventRow.execution_id == execution_id)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return ExecutionEvent(
            execution_id=row.execution_id,
            order_id=row.order_id,
            venue=row.venue,
            qty=row.qty,
            account_id=row.account_id,
            venue_order_id=row.venue_order_id,
            fill_seq=row.fill_seq,
            captured_at=row.captured_at,
            status=row.status,
            applied_at=row.applied_at,
            attempt_count=row.attempt_count,
            last_error=row.last_error,
        )

    async def start_apply(self, execution_id: str) -> bool:
        return await self._transition(execution_id, "APPLYING")

    async def mark_applied(self, execution_id: str) -> bool:
        return await self._transition(execution_id, "APPLIED", applied_at=datetime.now(UTC))

    async def mark_failed(self, execution_id: str, *, error: str) -> bool:
        return await self._transition(execution_id, "FAILED", error=error)

    async def mark_retry(self, execution_id: str, *, error: str) -> bool:
        return await self._transition(execution_id, "RETRY", error=error)

    async def _transition(
        self,
        execution_id: str,
        nxt: ExecutionEventStatus,
        *,
        applied_at: datetime | None = None,
        error: str | None = None,
    ) -> bool:
        """Idempotente + seguro: solo muta si la transición desde el estado de la
        fila en BD es legal (CAS). Devuelve False si no existe o es ilegal
        (p.ej. ya APPLIED). ``attempt_count`` sube solo al pasar a APPLYING.
        """
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        row = (
            await self._session.execute(
                sa.select(ExecutionEventRow).where(ExecutionEventRow.execution_id == execution_id)
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        if not can_transition_execution_event(row.status, nxt):
            return False
        row.status = nxt
        row.attempt_count += 1 if nxt == "APPLYING" else 0
        if applied_at is not None:
            row.applied_at = applied_at
        if error is not None:
            row.last_error = error
        await self._session.commit()
        return True


ApplyFinanceCallable = Callable[[ExecutionEvent], Awaitable[bool]]


async def apply_fill_idempotent(
    store: ExecutionEventStore,
    *,
    execution: ExecutionEvent,
    permit: bool = False,
    apply_finance: ApplyFinanceCallable | None = None,
) -> ApplyDecision:
    """Captura el fill con idempotencia y solo materializa bajo consentimiento.

    Devuelve la decisión exacta:
    * ``duplicate_skipped`` si el ``execution_id`` ya existía (sin aplicar).
    * ``captured_pending_operator_consent`` = capturado, pero el go NO está
      otorgado (default): la fila queda pero NO se materializa dinero.
    * ``applied`` = captura nueva (o re-captura) y ``permit=True`` +
      ``apply_finance`` efectivo devolvió True.
    * ``captured_not_applied`` = capturado con permit, pero el apply falló/no-efectivo.
    """
    if await store.capture(execution) == "duplicate":
        return "duplicate_skipped"
    if not permit or apply_finance is None:
        # No se toca Position/Ledger: depositar aquí sería el atajo H4 eliminado.
        return "captured_pending_operator_consent"
    effective = await apply_finance(execution)
    return "applied" if effective else "captured_not_applied"


async def apply_pending_execution(
    store: ExecutionEventStore,
    *,
    execution_id: str,
    apply_finance: ApplyFinanceCallable,
) -> ApplyDecision:
    """Fase 2 (consentimiento del operador/máquina) — materializa un fill capturado.

    Cierra el hueco Auditoría 3 del flujo de dos fases: ``apply_fill_idempotent``
    captura y NUNCA puede volver sobre una fila ya capturada (2º call →
    ``duplicate_skipped`` porque el ``execution_id`` ya existe), así que a un go
    entregado DESPUÉS de la captura no le quedaba salida para materializar el
    dinero. Esta API separada parte de la traza ya capturada y solo aplica
    Position/Ledger si existe sin importar duplicate, respetando el GATED:

    * ``event_not_found`` = no hay traza capturada para ``execution_id``:
      no se unge (y no se materializa) un fill que nunca se capturó (fail-closed).
    * ``applied`` = la traza existe y ``apply_finance`` fue efectivo.
    * ``captured_not_applied`` = la traza existe pero el apply no fue efectivo
      (fallo/no-op): NO se marca como consumado; el caller puede reintentar.

    Honestidad de idempotencia financiera: dentro de esta capa la traza única
    ``execution_id`` impide la doble CAPTURA; el doble APPLY se evita porque el
    ``apply_finance`` (kernel Decimal / sincronización Position·Ledger) es
    idempotente por ``execution_id`` — si la materialización ya se registró,
    una 2ª confirmación vuelve sin efecto y devuelve ``captured_not_applied``.
    """
    if not execution_id or not execution_id.strip():
        raise ValueError("execution_id is required")
    execution = await store.get(execution_id.strip())
    if execution is None:
        return "event_not_found"
    effective = await apply_finance(execution)
    return "applied" if effective else "captured_not_applied"


DurableApplyOutcome = Literal[
    "applied",  # esta instancia materializó (una sola vez, APPLIED durable).
    "already_applied",  # un worker previo ya marcó APPLIED → no se re-materializa.
    "no_apply_another_in_progress",  # start_apply CAS falló (otro en curso/ilegal).
    "retry_scheduled",  # apply no efectivo/transitorio → fila en RETRY reaplicable.
    "failed",  # apply no efectivo y no-retryable → fila en FAILED (revisión).
    "event_absent",  # sin fila capturada (no se unge nada; fail-closed).
]


async def apply_execution_financial_once(
    store: ExecutionEventStore,
    *,
    execution: ExecutionEvent,
    apply_finance: ApplyFinanceCallable,
    retryable_on_ineffective: bool = True,
) -> DurableApplyOutcome:
    """Aplica un fill capturado de forma durable y una sola vez (P2-01/C3).

    Fases (puente por fases idempotentes bajo go fail-closed):
      1. ``capture`` idempotente por ``execution_id`` (first-insert gana).
      2. ``start_apply`` = CAS sobre el estado: solo la instancia que pasa a
         APPLYING posee el apply (dos workers/restart jamás materializan a la
         vez sobre la misma fila; si ya está APPLIED no se vuelve a apply).
      3. ``apply_finance`` — materialización real (ExecuteTrade idempotente por
         ``idempotency_key`` en la capa de la app); esta capa NO lo fabrica.
      4. ``mark_applied`` (efectivo) o ``FAILED/RETRY`` (inefectivo), según si el
         fallo es reaplicable en un siguiente tick.

    Invariante buscado (C3): crash en cualquier punto ⇒ a lo sumo **una**
    materialización; nunca ``100+100``, nunca ``100+0`` por error de estado.
    El ``apply_finance`` también es idempotente por sí mismo (M4), de modo que un
    ``mark_*`` posterior a un crash (fila APPLYING stale) puede re-tomarse con
    retorno ``retry_scheduled`` sin duplicar el ledger.
    """
    if not execution.execution_id or not execution.execution_id.strip():
        raise ValueError("execution_id is required")
    await store.capture(execution)
    row = await store.get(execution.execution_id)
    if row is None:
        return "event_absent"
    if row.status == "APPLIED":
        return "already_applied"
    if not await store.start_apply(execution.execution_id):
        # APPLYING de otra instancia / ilegal desde estado actual → no hacemos 2º
        # apply; quien tenga APPLYING completará (crash → reclaim a RETRY en tick).
        return "no_apply_another_in_progress"
    try:
        effective = await apply_finance(execution)
    except Exception:  # noqa: BLE001 — error en la materialización no es un APPLIED.
        await store.mark_retry(execution.execution_id, error="apply_exception")
        return "retry_scheduled"
    if effective:
        await store.mark_applied(execution.execution_id)
        return "applied"
    if retryable_on_ineffective:
        await store.mark_retry(execution.execution_id, error="apply_ineffective")
        return "retry_scheduled"
    await store.mark_failed(execution.execution_id, error="apply_ineffective_no_retry")
    return "failed"
