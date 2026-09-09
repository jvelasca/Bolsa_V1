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
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    """Fill durable con identidad financiera (no lleva aritmética)."""

    execution_id: str
    order_id: str
    venue: str
    qty: Decimal
    account_id: str | None = None
    venue_order_id: str | None = None
    fill_seq: int | None = None
    captured_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.execution_id or not self.execution_id.strip():
            raise ValueError("execution_id is required")
        if self.captured_at is None:
            object.__setattr__(self, "captured_at", datetime.now(UTC))


@runtime_checkable
class ExecutionEventStore(Protocol):
    async def capture(self, execution: ExecutionEvent) -> CaptureStatus: ...

    async def get(self, execution_id: str) -> ExecutionEvent | None: ...


class InMemoryExecutionEventStore:
    """Test double: refleja exactamente la idempotencia por execution_id."""

    def __init__(self) -> None:
        self._rows: dict[str, ExecutionEvent] = {}

    async def capture(self, execution: ExecutionEvent) -> CaptureStatus:
        if execution.execution_id in self._rows:
            return "duplicate"
        self._rows[execution.execution_id] = execution
        return "inserted"

    async def get(self, execution_id: str) -> ExecutionEvent | None:
        return self._rows.get(execution_id)


class PostgresExecutionEventStore:
    """``execution_events`` en PostgreSQL con idempotencia real (ON CONFLICT).

    El unique (PK) ``execution_id`` + ``ON CONFLICT DO NOTHING ... RETURNING``
    garantiza que solo el insert que gana devuelve fila → clasifica inserted vs
    duplicate SIN lectura previa y SIN carreras (correcto entre workers).
    """

    def __init__(self, session: Any) -> None:
        self._session = session

    async def capture(self, execution: ExecutionEvent) -> CaptureStatus:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        result = await self._session.execute(
            sa.insert(ExecutionEventRow)  # type: ignore[attr-defined]
            .values(
                execution_id=execution.execution_id,
                order_id=execution.order_id,
                venue=execution.venue,
                account_id=execution.account_id,
                venue_order_id=execution.venue_order_id,
                fill_seq=execution.fill_seq,
                qty=execution.qty,
                captured_at=execution.captured_at
                or datetime.now(UTC),
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
                sa.select(ExecutionEventRow).where(
                    ExecutionEventRow.execution_id == execution_id
                )
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
        )


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
