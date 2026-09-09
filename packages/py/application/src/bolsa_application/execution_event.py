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

# V2.20 (P2-01) — mapa inverso: estados de ORIGEN desde los que una transición a
# ``nxt`` es legal. Deriva de ``_EXECUTION_EVENT_ALLOWED`` (una sola fuente de
# verdad; sin una segunda tabla que pueda desincronizarse). Se usa para expresar
# el CAS como un único ``UPDATE ... WHERE status IN (origins)`` atómico.
#
# IMPORTANTE (P2-01/V2.20): **``start_apply`` NO incluye ``APPLYING`` como origen**.
# ``APPLYING`` self sería el auto-reclaim con el que un segundo worker, al llegar
# justo después del ganador (que ya hizo commit de su APPLYING), se auto-reclama
# y también devuelve True → dos workers creyendo poseer el mismo apply (el fallo
# P1-01 del que nace esta versión). El único camino para retomar un ``APPLYING``
# es la REclamación explícita por lease (``reclaim_stale_apply``), que solo
# procede cuando el dueño ha caducado/muerto (ver ``_cas_sources_of`` y el reaper).
_EXECUTION_EVENT_SOURCES: dict[ExecutionEventStatus, tuple[ExecutionEventStatus, ...]] = {
    nxt: tuple(current for current, allowed in _EXECUTION_EVENT_ALLOWED.items() if nxt in allowed)
    for nxt in VALID_EXECUTION_EVENT_STATUSES
}

_HEARTBEAT_STALE_SECONDS = 30  # lease APPLYING: tras esto un dueño se considera caído.


def _cas_sources_of(nxt: ExecutionEventStatus) -> tuple[ExecutionEventStatus, ...]:
    """Orígenes legales para pasar a ``nxt`` (CAS atómico). Tuple (no set) por
    determinismo de orden en el SQL.

    Para ``APPLYING`` (adquisición exclusiva del apply por ``start_apply``) se
    EXCLUYE deliberadamente el auto-origen ``APPLYING``: la adquisición solo es
    legal desde ``CAPTURED``/``RETRY``/``FAILED`` (estados sin apply en curso).
    Retomar un ``APPLYING`` en marcha es responsabilidad de
    ``reclaim_stale_apply`` (lease/caducidad del dueño), no de un worker concurrente.
    """
    sources = _EXECUTION_EVENT_SOURCES[nxt]
    if nxt == "APPLYING":
        sources = tuple(s for s in sources if s != "APPLYING")
    return sources


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
    # V2.20 (P2-01) — lease de ownership del apply (observación de la fila, no de la
    # aritmética): quién posee el APPLYING en curso y cuándo se adquirió (updated_at).
    # Es el reloj que hace distinguir un APPLYING stale (dueño caído) de uno vivo.
    lease_owner: str | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.execution_id or not self.execution_id.strip():
            raise ValueError("execution_id is required")
        if self.captured_at is None:
            object.__setattr__(self, "captured_at", datetime.now(UTC))


@runtime_checkable
class ExecutionEventStore(Protocol):
    async def capture(self, execution: ExecutionEvent) -> CaptureStatus: ...

    async def get(self, execution_id: str) -> ExecutionEvent | None: ...

    # V2.19/V2.20 P2-01 — workflow durable (idempotente por execution_id). Quien
    # adquiere ``APPLYING`` FIRST (exclusivo desde CAPTURED/RETRY/FAILED) posee el
    # derecho a materializar. Un ``APPLYING`` en curso NO puede ser auto-reclamado
    # por otro worker (cada worker debe demostrar que el dueño ha caído: hueco que
    # cierra ``reclaim_stale_apply`` con lease/updated_at). False = no ganó.
    async def start_apply(self, execution_id: str, *, owner: str | None = None) -> bool: ...

    # V2.20 — retomar un ``APPLYING`` cuyo dueño ha caducado/muerto (lease stale).
    # Solo procede si la fila está en APPLYING y NO pertenece a un dueño vivo
    # distinto del solicitante (updated_at <= stale_before). True = reclaim efectivo.
    async def reclaim_stale_apply(
        self,
        execution_id: str,
        *,
        owner: str | None,
        stale_before: datetime,
    ) -> bool: ...

    async def mark_applied(self, execution_id: str) -> bool: ...

    async def mark_failed(self, execution_id: str, *, error: str) -> bool: ...

    async def mark_retry(self, execution_id: str, *, error: str) -> bool: ...

    # V2.20 — broadcast de lease vencido sobre filas APPLYING huérfanas (P2-02):
    # se usa materializar en SQL un reclaim condicionado por actualidad (ver worker).
    # Devuelve la lista de execution_id reclamados en este barrido.
    async def reclaim_stale_applying_batch(
        self,
        *,
        owner: str | None,
        stale_before: datetime,
        limit: int = 100,
    ) -> list[str]: ...


class InMemoryExecutionEventStore:
    """Test double: refleja la idempotencia por execution_id + workflow durable.

    El con `_rows` almacena ``ExecutionEvent`` completos (status+lease incluidos).
    ``capture`` devuelve duplicate si ya existe; ``start_apply`` adquiere APPLYING
    EXCLUSIVO desde CAPTURED/RETRY/FAILED (sin auto-origen APPLYING); un APPLYING
    en curso solo se retoma vía ``reclaim_stale_apply`` cuando el dueño ha
    caducado. Espeja el invariante real-PG, de modo que los tests de unidad del
    dominio y de ``apply_execution_financial_once`` son representativos del PG.
    """

    def __init__(self) -> None:
        self._rows: dict[str, ExecutionEvent] = {}

    async def capture(self, execution: ExecutionEvent) -> CaptureStatus:
        if execution.execution_id in self._rows:
            return "duplicate"
        now = datetime.now(UTC)
        stored = replace(
            execution,
            status="CAPTURED",
            lease_owner=None,
            updated_at=now,
        )
        self._rows[execution.execution_id] = stored
        return "inserted"

    async def get(self, execution_id: str) -> ExecutionEvent | None:
        return self._rows.get(execution_id)

    async def _apply(
        self,
        execution_id: str,
        *,
        owner: str | None,
        now: datetime,
    ) -> bool:
        """Acquire exclusivo APPLYING (CAS). Espeja `_cas_sources_of("APPLYING")`."""
        current = self._rows.get(execution_id)
        if current is None:
            return False
        if current.status not in ("CAPTURED", "RETRY", "FAILED"):
            return False
        self._rows[execution_id] = replace(
            current,
            status="APPLYING",
            lease_owner=owner,
            updated_at=now,
            attempt_count=current.attempt_count + 1,
            last_error=current.last_error,
        )
        return True

    async def start_apply(
        self,
        execution_id: str,
        *,
        owner: str | None = None,
    ) -> bool:
        return await self._apply(execution_id, owner=owner, now=datetime.now(UTC))

    async def reclaim_stale_apply(
        self,
        execution_id: str,
        *,
        owner: str | None,
        stale_before: datetime,
    ) -> bool:
        current = self._rows.get(execution_id)
        if current is None or current.status != "APPLYING":
            return False
        # El dueño actual debe estar caído: o bien nadie lo posee (updated_at sin
        # marcar aún / lease null) o bien su updated_at caducó y no es el solicitante
        # duplicando a sí mismo con lease fresco.
        last = current.updated_at
        if last is not None and last > stale_before:
            return False  # dueño vivo (lease reciente): no robamos el apply.
        now = datetime.now(UTC)
        self._rows[execution_id] = replace(
            current,
            lease_owner=owner,
            updated_at=now,
            attempt_count=current.attempt_count + 1,
        )
        return True

    async def reclaim_stale_applying_batch(
        self,
        *,
        owner: str | None,
        stale_before: datetime,
        limit: int = 100,
    ) -> list[str]:
        reclaimed: list[str] = []
        for exec_id in list(self._rows):
            if len(reclaimed) >= limit:
                break
            if await self.reclaim_stale_apply(
                exec_id,
                owner=owner,
                stale_before=stale_before,
            ):
                reclaimed.append(exec_id)
        return reclaimed

    async def mark_applied(self, execution_id: str) -> bool:
        current = self._rows.get(execution_id)
        if current is None or current.status != "APPLYING":
            return False
        self._rows[execution_id] = replace(
            current,
            status="APPLIED",
            applied_at=datetime.now(UTC),
            lease_owner=None,
            updated_at=datetime.now(UTC),
        )
        return True

    async def mark_failed(self, execution_id: str, *, error: str) -> bool:
        current = self._rows.get(execution_id)
        if current is None or current.status not in ("CAPTURED", "APPLYING", "FAILED"):
            return False
        self._rows[execution_id] = replace(
            current,
            status="FAILED",
            lease_owner=None,
            updated_at=datetime.now(UTC),
            last_error=error if error is not None else current.last_error,
        )
        return True

    async def mark_retry(self, execution_id: str, *, error: str) -> bool:
        current = self._rows.get(execution_id)
        if current is None or current.status not in (
            "CAPTURED",
            "APPLYING",
            "FAILED",
            "RETRY",
        ):
            return False
        self._rows[execution_id] = replace(
            current,
            status="RETRY",
            lease_owner=None,
            updated_at=datetime.now(UTC),
            last_error=error if error is not None else current.last_error,
        )
        return True


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
                # V2.20: seed del lease-clock en la captura (updated_at = captured).
                updated_at=execution.captured_at or datetime.now(UTC),
                lease_owner=None,
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
            lease_owner=row.lease_owner,
            updated_at=row.updated_at,
        )

    # ------------------------------------------------------------------
    # V2.20 (P2-01) — adquisición EXCLUSIVA del apply (CAS real atómico).
    # ------------------------------------------------------------------

    def _now(self) -> datetime:
        return datetime.now(UTC)

    async def start_apply(
        self,
        execution_id: str,
        *,
        owner: str | None = None,
    ) -> bool:
        """CAS exclusivo CAPTURED/RETRY/FAILED → APPLYING (ownership lease).

        Un ÚNICO ``UPDATE ... WHERE status IN ('CAPTURED','RETRY','FAILED')``
        incondicionado por la fila con su dueño actual. El que gana adquiere
        APPLYING con su ``owner`` + ``updated_at`` (lease). Dos workers sobre el
        MISMO CAPTURED → exactamente uno hace rowcount=1 (winner); el otro, al
        ver ya APPLYING (no en el set), hace 0 filas → False. Sin ventana.
        """
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        result = await self._session.execute(
            sa.update(ExecutionEventRow)
            .where(ExecutionEventRow.execution_id == execution_id)
            .where(ExecutionEventRow.status.in_(_cas_sources_of("APPLYING")))
            .values(
                status="APPLYING",
                attempt_count=ExecutionEventRow.attempt_count + 1,
                lease_owner=owner,
                updated_at=self._now(),
            )
        )
        won = bool(result.rowcount)
        await self._session.commit()
        return won

    async def reclaim_stale_apply(
        self,
        execution_id: str,
        *,
        owner: str | None,
        stale_before: datetime,
    ) -> bool:
        """Reclaim de un APPLYING cuyo dueño ha caducado/muerto (lease stale).

        UN ÚNICO ``UPDATE`` condicionado: solo filas en ``APPLYING`` cuya lease NO
        esté viva para otro dueño (``updated_at`` es NULL → desconocido/legacy, o
        bien ``updated_at <= stale_before``). NO se condiciona por equality al
        ``owner`` previo: lo que concede el reclaim es la CADUCIDAD, no la identidad
        (un worker caído no puede liberar su propia lease — de ahí que la señal sea
        el paso del tiempo frente a ``stale_before``, exactamente como el claim de
        ``live_orders``). True si lo reclamó esta instancia (rowcount=1).
        """
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        result = await self._session.execute(
            sa.update(ExecutionEventRow)
            .where(ExecutionEventRow.execution_id == execution_id)
            .where(ExecutionEventRow.status == "APPLYING")
            .where(
                sa.or_(
                    ExecutionEventRow.updated_at.is_(None),
                    ExecutionEventRow.updated_at <= stale_before,
                )
            )
            .values(
                lease_owner=owner,
                updated_at=self._now(),
                attempt_count=ExecutionEventRow.attempt_count + 1,
            )
        )
        won = bool(result.rowcount)
        await self._session.commit()
        return won

    async def reclaim_stale_applying_batch(
        self,
        *,
        owner: str | None,
        stale_before: datetime,
        limit: int = 100,
    ) -> list[str]:
        """Barrido P2-02: reclama hasta ``limit`` filas APPLYING stale (lease muerto).

        Atomico por fila vía single UPDATE con `CTE`/`FOR UPDATE SKIP LOCKED` para
        que varios reapers no se pisen. Devuelve las execution_id reclamadas (el
        caller las reaparecerá y las reaplicará por el camino durable idempotente).
        """
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        # SELECT ... FOR UPDATE SKIP LOCKED de candidatas stale, luego reclaim por id.
        cand = (
            sa.select(ExecutionEventRow.execution_id)
            .where(ExecutionEventRow.status == "APPLYING")
            .where(
                sa.or_(
                    ExecutionEventRow.updated_at.is_(None),
                    ExecutionEventRow.updated_at <= stale_before,
                )
            )
            .order_by(ExecutionEventRow.updated_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.execute(cand)).scalars().all()
        reclaimed: list[str] = []
        for exec_id in rows:
            if await self.reclaim_stale_apply(
                exec_id,
                owner=owner,
                stale_before=stale_before,
            ):
                reclaimed.append(str(exec_id))
        return reclaimed

    async def mark_applied(self, execution_id: str) -> bool:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        result = await self._session.execute(
            sa.update(ExecutionEventRow)
            .where(ExecutionEventRow.execution_id == execution_id)
            .where(ExecutionEventRow.status == "APPLYING")
            .values(
                status="APPLIED",
                applied_at=self._now(),
                lease_owner=None,
                updated_at=self._now(),
            )
        )
        won = bool(result.rowcount)
        await self._session.commit()
        return won

    async def mark_failed(self, execution_id: str, *, error: str) -> bool:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        result = await self._session.execute(
            sa.update(ExecutionEventRow)
            .where(ExecutionEventRow.execution_id == execution_id)
            .where(ExecutionEventRow.status.in_(("APPLYING", "CAPTURED", "FAILED")))
            .values(
                status="FAILED",
                lease_owner=None,
                updated_at=self._now(),
                last_error=error if error is not None else ExecutionEventRow.last_error,
            )
        )
        won = bool(result.rowcount)
        await self._session.commit()
        return won

    async def mark_retry(self, execution_id: str, *, error: str) -> bool:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        result = await self._session.execute(
            sa.update(ExecutionEventRow)
            .where(ExecutionEventRow.execution_id == execution_id)
            .where(
                ExecutionEventRow.status.in_(
                    ("CAPTURED", "APPLYING", "FAILED", "RETRY")
                )
            )
            .values(
                status="RETRY",
                lease_owner=None,
                updated_at=self._now(),
                last_error=error if error is not None else ExecutionEventRow.last_error,
            )
        )
        won = bool(result.rowcount)
        await self._session.commit()
        return won


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
    "no_apply_another_in_progress",  # APPLYING en curso por otro dueño vivo (no stole).
    "retry_scheduled",  # apply no efectivo/transitorio → fila en RETRY reaplicable.
    "failed",  # apply no efectivo y no-retryable → fila en FAILED (revisión).
    "event_absent",  # sin fila capturada (no se unge nada; fail-closed).
]

# Lease por defecto del apply: tras ``LEASE_WINDOW`` sin heartbeat de updated_at, un
# APPLYING se considera huérfano (dueño caído) y puede ser reclamado por un reaper /
# relaunch. Ajustable por unidad en ``apply_execution_financial_once``.
LEASE_WINDOW_SECONDS = 30


async def apply_execution_financial_once(
    store: ExecutionEventStore,
    *,
    execution: ExecutionEvent,
    apply_finance: ApplyFinanceCallable,
    owner: str = "worker",
    lease_window_seconds: int = LEASE_WINDOW_SECONDS,
    retryable_on_ineffective: bool = True,
) -> DurableApplyOutcome:
    """Aplica un fill capturado de forma durable y una sola vez (P2-01/C3).
    V2.20 — single-owner por lease.

    Fases (puente por fases idempotentes bajo go fail-closed):
      1. ``capture`` idempotente por ``execution_id`` (first-insert gana).
      2. ``start_apply`` = CAS EXCLUSIVO desde CAPTURED/RETRY/FAILED con el ``owner``
         + lease (``updated_at``). Solo la instancia que gana posee el APPLYING; un
         APPLYING en curso por OTRO dueño VIVO NO se roba (``no_apply_...``).
      3. Si el CAS exclusivo falla porque la fila está en APPLYING pero su lease está
         CADUCADA (``updated_at <= now - lease_window_seconds``), este pass puede
         ``reclaim_stale_apply`` (dueño caído, p.ej. crash de otro worker) y completar.
         Con ``lease_window_seconds`` grande (default) la reclamación solo procede si
         el dueño lleva un lease vencido → ninguna doble-marcha simultánea.
      4. ``apply_finance`` — materialización real (ExecuteTrade idempotente por
         ``idempotency_key`` en la capa de la app); esta capa NO lo fabrica.
      5. ``mark_applied`` (efectivo) o ``FAILED/RETRY`` (inefectivo), según si el
         fallo es reaplicable en un siguiente tick.

    Invariante buscado (C3): crash en cualquier punto ⇒ a lo sumo **una**
    materialización; nunca ``100+100``, nunca ``100+0`` por error de estado.
    """
    if not execution.execution_id or not execution.execution_id.strip():
        raise ValueError("execution_id is required")
    await store.capture(execution)
    row = await store.get(execution.execution_id)
    if row is None:
        return "event_absent"
    if row.status == "APPLIED":
        return "already_applied"
    from datetime import timedelta

    # Threshold de lease: un APPLYING cuyo updated_at sea <= stale_before se considera
    # VENCIDO (dueño caído) y reclamable. window>0 ⇒ solo se reclama tras el lease;
    # window=0 (sólo test de crash con dueño muerto) ⇒ reclaim inmediato. En prod el
    # recovery usa un window real para NO robar un APPLYING vivo de otro worker.
    stale_before = datetime.now(UTC) - timedelta(seconds=lease_window_seconds)
    # 1) adquisición exclusiva. 2) ante APPLYING ajeno: solo si el lease está vencido.
    won = await store.start_apply(execution.execution_id, owner=owner)
    if not won:
        won = await store.reclaim_stale_apply(
            execution.execution_id,
            owner=owner,
            stale_before=stale_before,
        )
        if not won:
            # APPLYING en curso por otro dueño vivo / ilegal → NO hacemos 2º apply;
            # quien tenga el APPLYING completará (crash → reclaim tras lease vencido).
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


# CandidateResolver → ExecutionEvent candidato para (re)aplicar un stale APPLYING.
# Este retry está inyectado (no aquí) porque (re)derivar un candidato exige una
# capa que vuelva a relevar price/venue desde el broker/live_order (V2.20 · P2-02):
# el reaper NO inventa aritmética financiera (H4/H6). Devuelve None si ese stale
# no es (re)materializable ahora (p.ej. sin order viva/bridge → pasar a RETRY).
CandidateResolver = Callable[[ExecutionEvent], Awaitable["ExecutionEvent | None"]]


async def reap_stale_applying(
    store: ExecutionEventStore,
    *,
    owner: str,
    stale_before: datetime,
    limit: int = 20,
    resolve_candidate: CandidateResolver | None = None,
    apply_finance: ApplyFinanceCallable | None = None,
) -> dict[str, int]:
    """V2.20 (P2-02) — reaper de ``APPLYING`` stale (lease del dueño muerto).

    Barrido defensivo que saca de ``APPLYING`` las filas huérfanas de un dueño
    caído (``reclaim_stale_applying_batch`` — concede al ``owner`` del reaper) y
    las encamina a terminal reaplicable:

    * Si se puede re-derivar el candidato (``resolve_candidate``) y hay
      ``apply_finance`` (materialización idempotente), se ejecuta el apply y se
      marca ``APPLIED`` una sola vez; si el apply no es efectivo / lanza →
      ``RETRY`` reaplicable (jamás APPLIED falso).
    * Si NO se puede re-derivar (sin bridge/order viva ahora), la fila pasa a
      ``RETRY`` vía ``mark_retry`` (libera su lease): ni robada por el reaper ni
      varada en APPLYING; otro tick con parámetros la retomará desde ``RETRY``.
    * Una fila cuya lease sigue VIVA no se roba (la batch solo devuelve stale).

    Fíjate que el reaper NO rehúsa su propio claim: la batch ya le concedió
    ownership (lease fresca suya), así que luego aplica y completa directamente
    sin un segundo CAS. Un fallo aislado no tumba el barrido (fail-closed) y se
    cuenta en ``errors``.
    """
    reclaimed = await store.reclaim_stale_applying_batch(
        owner=owner,
        stale_before=stale_before,
        limit=limit,
    )
    counts = {
        "reclaimed": len(reclaimed),
        "applied": 0,
        "already_applied": 0,
        "retry": 0,
        "failed": 0,
        "errors": 0,
    }
    for execution_id in reclaimed:
        try:
            row = await store.get(execution_id)
            if row is None:
                await store.mark_retry(execution_id, error="orphan_applying_gone")
                counts["retry"] += 1
                continue
            # Seguridad: si entre el claim y aquí la fila ya fue marcada APPLIED por
            # otros medios, no la retocamos (no-doble terminal).
            if row.status == "APPLIED":
                counts["already_applied"] += 1
                continue
            if (resolve_candidate is not None and apply_finance is not None):
                candidate = await resolve_candidate(row)
                if candidate is None:
                    # Sin candidato re-derivable ahora → RETRY reaplicable (honesto).
                    await store.mark_retry(execution_id, error="lease_expired_no_candidate")
                    counts["retry"] += 1
                    continue
                try:
                    effective = await apply_finance(candidate)
                except Exception:  # noqa: BLE001 — no marcar APPLIED por error.
                    await store.mark_retry(execution_id, error="reap_apply_exception")
                    counts["retry"] += 1
                    continue
                if effective:
                    await store.mark_applied(execution_id)
                    counts["applied"] += 1
                else:
                    await store.mark_retry(execution_id, error="reap_apply_ineffective")
                    counts["retry"] += 1
                continue
            # Sin resolver/apply (default fail-closed) → RETRY, no varado en APPLYING.
            await store.mark_retry(execution_id, error="lease_expired_no_candidate")
            counts["retry"] += 1
        except Exception:  # noqa: BLE001 — un evento no tumba el barrido
            counts["errors"] += 1
    return counts
