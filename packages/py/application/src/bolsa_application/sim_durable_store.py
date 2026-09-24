"""V2.23/V2.24 / A9·A9.1 — durabilidad SIM: contexto financiero + posición AUTO.

Dos espejos durables (migración 028, endurecidos en 029), con el mismo patrón que
``auto_engine_state_store`` (Protocol + doble InMemory + store Postgres con imports
de fila perezosos por método y commit explícito):

* ``SimFillFinanceContextStore`` — contexto financiero por ``execution_id`` para que
  un resolver reconstruya la finance de un fill sin memoria del ``SimulatedOrderResult``
  (P1-05). Idempotente por PK ``execution_id`` (``ON CONFLICT DO NOTHING``).
* ``SimAutoPositionStore`` — posición abierta por ``(account_id, engine_id, symbol)``
  para que el worker AUTO readopte tras crash/restart (P1-06 / G7) en vez de
  re-comprar, **aislada por cuenta** (V2.24 · P1-02: antes solo ``(engine_id,
  symbol)``, dos cuentas colisionaban en la misma fila) y con el **estado de
  protección** durable (V2.24 · P2-01: ``entry_price``/``high_watermark``/
  ``stop_price``/``t1_state``/``trailing_state``).

V2.24 / A9.1 (P1-01) — ``sim_auto_positions`` es una **PROYECCIÓN de recuperación
reconstruible**, NO una autoridad financiera: ``rebuild_open`` la reconstruye desde
el estado financiero canónico (posiciones/ledger) cuando falta o diverge. Una
proyección jamás puede autorizar por sí sola una compra.

No hay aquí aritmética financiera ni decisiones: son espejos de estado. La autoridad
sigue en ``decision_contract`` + ``ExecuteTrade`` idempotente.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

__all__ = [
    "InMemorySimAutoPositionStore",
    "InMemorySimConsumedSignalStore",
    "InMemorySimFillFinanceContextStore",
    "PostgresSimAutoPositionStore",
    "PostgresSimConsumedSignalStore",
    "PostgresSimFillFinanceContextStore",
    "SimAutoPositionStore",
    "SimConsumedSignal",
    "SimConsumedSignalStore",
    "SimDurableUnitOfWork",
    "SimFillFinanceContext",
    "SimFillFinanceContextStore",
    "SimPositionProjection",
]


def _now() -> datetime:
    return datetime.now(UTC)


def _to_decimal(raw: object) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return Decimal(str(raw))
    except (ArithmeticError, ValueError):
        return None


def usable_reference_mid(raw: object) -> Decimal | None:
    """(PURA, AUTO-16) el mid de referencia UTILIZABLE, o ``None`` si no describe un precio.

    El mid de referencia es un PRECIO: un ``0`` o un negativo no describen ninguno, y
    aceptarlos convertiría la fricción aplicada en un número inventado (``|price − 0|``
    sería el precio entero). Un valor inservible se declara como "no hay referencia",
    jamás como una referencia de cero. Devuelve ``Decimal`` para que el mismo hecho no
    viaje con dos tipos distintos.
    """
    value = _to_decimal(raw)
    if value is None or not value.is_finite() or value <= 0:
        return None
    return value


async def _commit_if(session: Any, autocommit: bool) -> None:
    """V2.24.2 (P2-B) — commit condicional.

    Los stores Postgres de esta clase commitean por su cuenta por defecto
    (``autocommit=True``): la fila debe ser durable y visible ANTES de mover dinero
    (idempotencia/recuperación) y el store no debe depender de la transacción externa
    del ``ExecutionEventStore``. Con ``autocommit=False`` el caller (unidad-de-trabajo)
    controla el commit y puede componer la proyección y el contexto financiero en una
    ÚNICA transacción, eliminando la ventana residual entre ambos espejos sin cambiar
    la naturaleza reconstruible de la proyección (P1-01).
    """
    if autocommit:
        await session.commit()


@dataclass(frozen=True, slots=True)
class SimFillFinanceContext:
    """Contexto financiero durable de un fill SIM (lineal a ``SimulatedFillFinance``)."""

    execution_id: str
    instrument_id: str
    side: str  # "buy" | "sell" (minúsculas)
    quantity: Decimal
    price: Decimal
    # V2.57 / AUTO-16 — mid de REFERENCIA con el que el simulador construyó ``price``
    # (migración 046). ``None`` = no se midió (fila anterior a 2.57, o un mid inválido):
    # la fricción aplicada NO se puede afirmar. Nunca un ``0``: diría "fricción gratis".
    reference_mid: Decimal | None = None
    account_id: str | None = None
    venue: str = "simulated"
    idempotency_key: str | None = None
    # V2.28 / A10 (P1-02 real): versión de estrategia que originó el fill. ``None``
    # cuando no hay atribución (spine determinista sin ACTIVE) — no se inventa.
    strategy_version_id: str | None = None
    # V2.47 — ciclo financiero (señal→…→PnL) al que pertenece el fill. ``None`` cuando no
    # se conoce (filas previas a 2.47 / fill sin decisión AUTO) — desconocido ≠ fabricado.
    cycle_id: str | None = None
    # V2.53 / AUTO-12 — instante durable del fill (la columna ``created_at`` de la tabla,
    # que YA existía: sin migración). Lo necesita la ventana RECIENTE del Adaptive para
    # ordenar por instante real y no por posición de lista. ``None`` en los dobles
    # herméticos que no conocen fechas: la ausencia se DECLARA (``recent_unavailable``),
    # nunca se finge cronología.
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise ValueError("SimFillFinanceContext exige execution_id no vacío")
        if self.side not in {"buy", "sell"}:
            raise ValueError(f"side inválido (esperado buy/sell): {self.side!r}")
        if self.quantity <= 0:
            raise ValueError("quantity debe ser > 0")
        if self.price <= 0:
            raise ValueError("price debe ser > 0")
        # AUTO-16: un mid de referencia que no es un precio (ausente, ``NaN``, ``≤ 0``) NO
        # se convierte en un ``0`` —diría "fricción gratis"— ni tumba el settlement del
        # fill (que sí es un hecho). Se DECLARA sin referencia: la fricción aplicada de ese
        # fill pasa a ser un hueco, que es exactamente lo que se sabe de él. Y se normaliza
        # a ``Decimal`` para que el mismo hecho no viaje con dos tipos distintos.
        object.__setattr__(self, "reference_mid", usable_reference_mid(self.reference_mid))


@dataclass(frozen=True, slots=True)
class SimPositionProjection:
    """Fila de la proyección de posición (V2.24 · P2-01: incluye protección)."""

    symbol: str
    quantity: Decimal
    avg_price: Decimal | None = None
    entry_price: Decimal | None = None
    high_watermark: Decimal | None = None
    stop_price: Decimal | None = None
    t1_state: str | None = None
    trailing_state: str | None = None
    # V2.32 / A12: versión de estrategia que abrió la posición. Se restaura en
    # ``readopt_positions`` para que los cierres post-crash sigan atribuyéndose.
    strategy_version_id: str | None = None
    # AUTO 2.0 · P4 (migración 040): plan operativo V2 completo (``PositionState.to_dict``).
    # Con él el reinicio REHIDRATA la posición (stop/T1/T2/parciales reales) en vez de
    # reconstruir la geometría por ATR. ``None`` = fila anterior a P4 ⇒ el worker cae a
    # la adopción reconstruida (auditada con ``adopted``).
    position_state: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class SimConsumedSignal:
    """AUTO 2.0 · P4 — señal consumida (entrada ya ejecutada) sobre una barra concreta."""

    signal_id: str
    instrument_id: str
    bar_timestamp: str
    consumed_at: datetime


class SimFillFinanceContextStore(Protocol):
    async def save(self, context: SimFillFinanceContext) -> None: ...
    async def get(self, execution_id: str) -> SimFillFinanceContext | None: ...

    # AUTO-1A: lectura por lote de la identidad financiera de los fills ya aplicados
    # (el ``PositionLedger`` necesita lado/cantidad/precio de N fills sin N round-trips).
    # Un ``execution_id`` ausente se OMITE del mapa: el llamante declara la fila como
    # rechazada (medición incompleta), nunca la cuenta como cero.
    async def get_many(
        self, execution_ids: Sequence[str]
    ) -> Mapping[str, SimFillFinanceContext]: ...

    async def list_for_strategy_version(
        self,
        strategy_version_id: str,
        *,
        account_id: str | None = None,
        limit: int | None = None,
    ) -> list[SimFillFinanceContext]: ...

    # AUTO-16: los fills de un CICLO financiero (``cycle_id``, migración 044). Es la costura
    # con la que la fricción APLICADA se recompone ciclo a ciclo —incluida la pata de ENTRADA,
    # liquidada en otro tick y por tanto invisible para la memoria del turno—. Un ciclo sin
    # filas NO aparece: el hueco lo declara el llamante, no se rellena con una fricción de
    # ceros. Con ``account_id`` se acota la lectura (una fila de otra cuenta no casa nunca).
    async def list_by_cycle_ids(
        self,
        account_id: str | None,
        cycle_ids: Sequence[str],
        *,
        limit: int = 500,
    ) -> list[SimFillFinanceContext]: ...


class SimAutoPositionStore(Protocol):
    async def read_open(self, account_id: str, engine_id: str) -> Mapping[str, Decimal]: ...
    async def read_projection(
        self, account_id: str, engine_id: str
    ) -> Mapping[str, SimPositionProjection]: ...
    async def upsert(
        self,
        account_id: str,
        engine_id: str,
        symbol: str,
        quantity: Decimal,
        *,
        avg_price: Decimal | None = None,
        entry_price: Decimal | None = None,
        high_watermark: Decimal | None = None,
        stop_price: Decimal | None = None,
        t1_state: str | None = None,
        trailing_state: str | None = None,
        strategy_version_id: str | None = None,
        position_state: Mapping[str, Any] | None = None,
    ) -> None: ...
    async def delete(self, account_id: str, engine_id: str, symbol: str) -> None: ...


class SimConsumedSignalStore(Protocol):
    """AUTO 2.0 · P4 — señales ya consumidas (idempotente por identidad canónica).

    La semántica es de BARRA: solo se leen/marcan las señales de la barra corriente y
    las anteriores se podan (``prune_before``), de modo que el espejo no crece sin
    límite. ``mark`` es idempotente (repetir la marca de la misma señal no duplica ni
    falla: el crash/retry es el caso normal).
    """

    async def mark(
        self,
        account_id: str,
        engine_id: str,
        signal_id: str,
        *,
        instrument_id: str,
        bar_timestamp: str,
        consumed_at: datetime | None = None,
    ) -> None: ...
    async def list_bar(self, account_id: str, engine_id: str, bar_timestamp: str) -> list[str]: ...
    async def prune_before(self, account_id: str, engine_id: str, bar_timestamp: str) -> int: ...


class InMemorySimFillFinanceContextStore:
    """Doble hermético: idempotente por ``execution_id``."""

    def __init__(self) -> None:
        self._rows: dict[str, SimFillFinanceContext] = {}

    async def save(self, context: SimFillFinanceContext) -> None:
        self._rows.setdefault(context.execution_id, context)

    async def get(self, execution_id: str) -> SimFillFinanceContext | None:
        return self._rows.get(execution_id)

    async def get_many(
        self, execution_ids: Sequence[str]
    ) -> Mapping[str, SimFillFinanceContext]:
        """Batch hermético: espeja el contrato del store PG (ausentes se omiten)."""
        out: dict[str, SimFillFinanceContext] = {}
        for execution_id in execution_ids:
            row = self._rows.get(execution_id)
            if row is not None:
                out[execution_id] = row
        return out

    async def list_for_strategy_version(
        self,
        strategy_version_id: str,
        *,
        account_id: str | None = None,
        limit: int | None = None,
    ) -> list[SimFillFinanceContext]:
        """Fills atribuidos a una versión (orden de inserción estable por ``execution_id``).

        V2.28/A10: insumo de las métricas observadas de la vigilancia real. El doble
        hermético no conoce ``created_at``; el orden por ``execution_id`` es determinista
        y suficiente para el contrato (el store PG ordena por ``created_at`` real).
        """
        rows = [
            row
            for row in self._rows.values()
            if row.strategy_version_id == strategy_version_id
            and (account_id is None or row.account_id == account_id)
        ]
        rows.sort(key=lambda r: r.execution_id)
        if limit is not None and limit > 0:
            rows = rows[:limit]
        return rows

    async def list_by_cycle_ids(
        self,
        account_id: str | None,
        cycle_ids: Sequence[str],
        *,
        limit: int = 500,
    ) -> list[SimFillFinanceContext]:
        """Fills de esos ciclos (AUTO-16), con el mismo contrato que el store PG.

        ``cycle_ids`` vacío ⇒ ``[]`` sin recorrer nada. Solo filas que declaran el ciclo —una
        fila sin ``cycle_id`` (anterior a ``2.47``) no casa nunca— y, con ``account_id``, solo
        las de esa cuenta: un fill de otra cuenta no puede aportar la fricción de este ciclo.
        """
        wanted = {str(c).strip() for c in cycle_ids if str(c).strip()}
        if not wanted:
            return []
        rows = [
            row
            for row in self._rows.values()
            if str(row.cycle_id or "").strip() in wanted
            and (account_id is None or row.account_id == account_id)
        ]
        rows.sort(key=lambda r: (str(r.cycle_id), r.execution_id))
        if limit is not None and limit > 0:
            rows = rows[:limit]
        return rows

    def size(self) -> int:
        return len(self._rows)


class InMemorySimAutoPositionStore:
    """Doble hermético del espejo de posición (por ``account_id``→``engine_id``→symbol)."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], dict[str, SimPositionProjection]] = {}

    async def read_open(self, account_id: str, engine_id: str) -> Mapping[str, Decimal]:
        rows = self._rows.get((account_id, engine_id), {})
        return {s: r.quantity for s, r in rows.items() if r.quantity > 0}

    async def read_projection(
        self, account_id: str, engine_id: str
    ) -> Mapping[str, SimPositionProjection]:
        return {
            s: r for s, r in self._rows.get((account_id, engine_id), {}).items() if r.quantity > 0
        }

    async def upsert(
        self,
        account_id: str,
        engine_id: str,
        symbol: str,
        quantity: Decimal,
        *,
        avg_price: Decimal | None = None,
        entry_price: Decimal | None = None,
        high_watermark: Decimal | None = None,
        stop_price: Decimal | None = None,
        t1_state: str | None = None,
        trailing_state: str | None = None,
        strategy_version_id: str | None = None,
        position_state: Mapping[str, Any] | None = None,
    ) -> None:
        self._rows.setdefault((account_id, engine_id), {})[symbol] = SimPositionProjection(
            symbol=symbol,
            quantity=quantity,
            avg_price=avg_price,
            entry_price=entry_price,
            high_watermark=high_watermark,
            stop_price=stop_price,
            t1_state=t1_state,
            trailing_state=trailing_state,
            strategy_version_id=strategy_version_id,
            position_state=dict(position_state) if position_state is not None else None,
        )

    async def delete(self, account_id: str, engine_id: str, symbol: str) -> None:
        self._rows.get((account_id, engine_id), {}).pop(symbol, None)


class InMemorySimConsumedSignalStore:
    """Doble hermético de las señales consumidas (por cuenta+engine, idempotente)."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], dict[str, SimConsumedSignal]] = {}

    async def mark(
        self,
        account_id: str,
        engine_id: str,
        signal_id: str,
        *,
        instrument_id: str,
        bar_timestamp: str,
        consumed_at: datetime | None = None,
    ) -> None:
        row = SimConsumedSignal(
            signal_id=signal_id,
            instrument_id=instrument_id,
            bar_timestamp=bar_timestamp,
            consumed_at=consumed_at or _now(),
        )
        self._rows.setdefault((account_id, engine_id), {}).setdefault(signal_id, row)

    async def list_bar(self, account_id: str, engine_id: str, bar_timestamp: str) -> list[str]:
        rows = self._rows.get((account_id, engine_id), {})
        return sorted(sid for sid, row in rows.items() if row.bar_timestamp == bar_timestamp)

    async def prune_before(self, account_id: str, engine_id: str, bar_timestamp: str) -> int:
        rows = self._rows.get((account_id, engine_id))
        if not rows:
            return 0
        stale = [sid for sid, row in rows.items() if row.bar_timestamp < bar_timestamp]
        for sid in stale:
            rows.pop(sid, None)
        return len(stale)

    def size(self) -> int:
        return sum(len(rows) for rows in self._rows.values())


class PostgresSimFillFinanceContextStore:
    """Store durable del contexto financiero por fill (tabla ``sim_fill_finance_context``).

    ``autocommit=True`` (default) conserva la durabilidad-e-idempotencia histórica
    (commit propio). ``autocommit=False`` (V2.24.2 · P2-B) cede el commit al caller
    para componer una unidad-de-trabajo con la proyección de posición.
    """

    def __init__(self, session: Any, *, autocommit: bool = True) -> None:
        self._session = session
        self._autocommit = autocommit

    async def save(self, context: SimFillFinanceContext) -> None:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import SimFillFinanceContextRow

        await self._session.execute(
            pg_insert(SimFillFinanceContextRow)
            .values(
                execution_id=context.execution_id,
                instrument_id=context.instrument_id,
                side=context.side,
                quantity=context.quantity,
                price=context.price,
                reference_mid=context.reference_mid,
                account_id=context.account_id,
                venue=context.venue,
                strategy_version_id=context.strategy_version_id,
                idempotency_key=context.idempotency_key,
                cycle_id=context.cycle_id,
                created_at=_now(),
            )
            .on_conflict_do_nothing(index_elements=["execution_id"])
        )
        # Commit propio por defecto: la fila debe ser DURABLE y visible ANTES de mover
        # dinero (idempotencia/recuperación). Con ``autocommit=False`` lo controla el
        # caller (unidad-de-trabajo P2-B) para compartir transacción con la proyección.
        await _commit_if(self._session, self._autocommit)

    async def get(self, execution_id: str) -> SimFillFinanceContext | None:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import SimFillFinanceContextRow

        row = (
            await self._session.execute(
                select(SimFillFinanceContextRow).where(
                    SimFillFinanceContextRow.execution_id == execution_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return SimFillFinanceContext(
            execution_id=row.execution_id,
            instrument_id=row.instrument_id,
            side=row.side,
            quantity=row.quantity,
            price=row.price,
            reference_mid=getattr(row, "reference_mid", None),
            account_id=row.account_id,
            venue=row.venue,
            idempotency_key=row.idempotency_key,
            strategy_version_id=row.strategy_version_id,
            cycle_id=getattr(row, "cycle_id", None),
            created_at=getattr(row, "created_at", None),
        )

    async def get_many(
        self, execution_ids: Sequence[str]
    ) -> Mapping[str, SimFillFinanceContext]:
        """Lee N contextos financieros en UNA consulta (AUTO-1A · PositionLedger).

        Sin esto el libro de posición haría N round-trips (uno por fill aplicado).
        Los ``execution_id`` no encontrados se OMITEN del mapa: el llamante los declara
        como filas no interpretables (medición incompleta) y nunca los cuenta como cero.
        Un lote vacío no consulta la base.
        """
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import SimFillFinanceContextRow

        wanted = [str(e).strip() for e in execution_ids if str(e).strip()]
        if not wanted:
            return {}
        rows = (
            await self._session.execute(
                select(SimFillFinanceContextRow).where(
                    SimFillFinanceContextRow.execution_id.in_(wanted)
                )
            )
        ).scalars().all()
        return {
            row.execution_id: SimFillFinanceContext(
                execution_id=row.execution_id,
                instrument_id=row.instrument_id,
                side=row.side,
                quantity=row.quantity,
                price=row.price,
                reference_mid=getattr(row, "reference_mid", None),
                account_id=row.account_id,
                venue=row.venue,
                idempotency_key=row.idempotency_key,
                strategy_version_id=row.strategy_version_id,
                cycle_id=getattr(row, "cycle_id", None),
                created_at=getattr(row, "created_at", None),
            )
            for row in rows
        }

    async def list_for_strategy_version(
        self,
        strategy_version_id: str,
        *,
        account_id: str | None = None,
        limit: int | None = None,
    ) -> list[SimFillFinanceContext]:
        """Fills atribuidos a una versión, en orden temporal (V2.28/A10, vigilancia real).

        Solo devuelve filas con atribución explícita; las de ``strategy_version_id``
        NULL (spine determinista / anteriores a la migración 031) quedan fuera por
        diseño: sin atribución no se puede afirmar que pertenezcan a la versión.
        """
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import SimFillFinanceContextRow

        stmt = (
            select(SimFillFinanceContextRow)
            .where(SimFillFinanceContextRow.strategy_version_id == strategy_version_id)
            .order_by(
                SimFillFinanceContextRow.created_at.asc(),
                SimFillFinanceContextRow.execution_id.asc(),
            )
        )
        if account_id is not None:
            stmt = stmt.where(SimFillFinanceContextRow.account_id == account_id)
        if limit is not None and limit > 0:
            stmt = stmt.limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            SimFillFinanceContext(
                execution_id=row.execution_id,
                instrument_id=row.instrument_id,
                side=row.side,
                quantity=row.quantity,
                price=row.price,
                reference_mid=getattr(row, "reference_mid", None),
                account_id=row.account_id,
                venue=row.venue,
                idempotency_key=row.idempotency_key,
                strategy_version_id=row.strategy_version_id,
                cycle_id=getattr(row, "cycle_id", None),
                created_at=getattr(row, "created_at", None),
            )
            for row in rows
        ]

    async def list_by_cycle_ids(
        self,
        account_id: str | None,
        cycle_ids: Sequence[str],
        *,
        limit: int = 500,
    ) -> list[SimFillFinanceContext]:
        """Fills de esos ciclos financieros (AUTO-16), en orden de ejecución.

        La costura que ata el fill a su ciclo (``cycle_id``, migración ``044``) y devuelve el
        material completo de la fricción APLICADA: la pata de ENTRADA y la de SALIDA. Cuál
        agregue el llamante es su decisión, no del store.

        ``cycle_ids`` vacío ⇒ ``[]`` sin consultar la base. Las filas sin ciclo (``NULL``,
        anteriores a ``2.47``) no casan nunca: "anterior a 2.47" no es un ciclo. Con
        ``account_id`` se acota en SQL (una fila de otra cuenta no puede aportar la fricción
        de este ciclo); sin él se lee sin filtro de cuenta —el llamante declara ese alcance—.
        """
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import SimFillFinanceContextRow

        wanted = [str(c).strip() for c in cycle_ids if str(c).strip()]
        if not wanted:
            return []
        stmt = (
            select(SimFillFinanceContextRow)
            .where(SimFillFinanceContextRow.cycle_id.in_(wanted))
            .order_by(
                SimFillFinanceContextRow.created_at.asc(),
                SimFillFinanceContextRow.execution_id.asc(),
            )
        )
        if account_id is not None:
            stmt = stmt.where(SimFillFinanceContextRow.account_id == account_id)
        if limit is not None and limit > 0:
            stmt = stmt.limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            SimFillFinanceContext(
                execution_id=row.execution_id,
                instrument_id=row.instrument_id,
                side=row.side,
                quantity=row.quantity,
                price=row.price,
                reference_mid=getattr(row, "reference_mid", None),
                account_id=row.account_id,
                venue=row.venue,
                idempotency_key=row.idempotency_key,
                strategy_version_id=row.strategy_version_id,
                cycle_id=getattr(row, "cycle_id", None),
                created_at=getattr(row, "created_at", None),
            )
            for row in rows
        ]


class PostgresSimAutoPositionStore:
    """Store durable de la proyección de posición SIM (tabla ``sim_auto_positions``).

    V2.24 / A9.1: aislada por ``account_id`` (P1-02) y con estado de protección
    (P2-01). La proyección es **reconstruible** desde el estado financiero canónico
    (P1-01) — ver ``rebuild_sim_position_projection``.

    ``autocommit=True`` (default) conserva el commit propio. ``autocommit=False``
    (V2.24.2 · P2-B) cede el commit al caller para una unidad-de-trabajo atómica
    entre proyección y contexto financiero del mismo fill.
    """

    def __init__(self, session: Any, *, autocommit: bool = True) -> None:
        self._session = session
        self._autocommit = autocommit

    async def read_open(self, account_id: str, engine_id: str) -> dict[str, Decimal]:
        projection = await self.read_projection(account_id, engine_id)
        return {symbol: row.quantity for symbol, row in projection.items()}

    async def read_projection(
        self, account_id: str, engine_id: str
    ) -> dict[str, SimPositionProjection]:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import SimAutoPositionRow

        rows = (
            await self._session.execute(
                select(SimAutoPositionRow).where(
                    SimAutoPositionRow.account_id == account_id,
                    SimAutoPositionRow.engine_id == engine_id,
                )
            )
        ).scalars()
        out: dict[str, SimPositionProjection] = {}
        for row in rows:
            if row.quantity is None or row.quantity <= 0:
                continue
            out[row.symbol] = SimPositionProjection(
                symbol=row.symbol,
                quantity=row.quantity,
                avg_price=row.avg_price,
                entry_price=row.entry_price,
                high_watermark=row.high_watermark,
                stop_price=row.stop_price,
                t1_state=row.t1_state,
                trailing_state=row.trailing_state,
                strategy_version_id=row.strategy_version_id,
                position_state=dict(row.position_state) if row.position_state else None,
            )
        return out

    async def upsert(
        self,
        account_id: str,
        engine_id: str,
        symbol: str,
        quantity: Decimal,
        *,
        avg_price: Decimal | None = None,
        entry_price: Decimal | None = None,
        high_watermark: Decimal | None = None,
        stop_price: Decimal | None = None,
        t1_state: str | None = None,
        trailing_state: str | None = None,
        strategy_version_id: str | None = None,
        position_state: Mapping[str, Any] | None = None,
    ) -> None:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import SimAutoPositionRow

        now = _now()
        await self._session.execute(
            pg_insert(SimAutoPositionRow)
            .values(
                account_id=account_id,
                engine_id=engine_id,
                symbol=symbol,
                quantity=quantity,
                avg_price=avg_price,
                entry_price=entry_price,
                high_watermark=high_watermark,
                stop_price=stop_price,
                t1_state=t1_state,
                trailing_state=trailing_state,
                strategy_version_id=strategy_version_id,
                position_state=dict(position_state) if position_state is not None else None,
                opened_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["account_id", "engine_id", "symbol"],
                set_={
                    "quantity": quantity,
                    "avg_price": avg_price,
                    "entry_price": entry_price,
                    "high_watermark": high_watermark,
                    "stop_price": stop_price,
                    "t1_state": t1_state,
                    "trailing_state": trailing_state,
                    "strategy_version_id": strategy_version_id,
                    "position_state": (
                        dict(position_state) if position_state is not None else None
                    ),
                    "updated_at": now,
                },
            )
        )
        await _commit_if(self._session, self._autocommit)

    async def delete(self, account_id: str, engine_id: str, symbol: str) -> None:
        from sqlalchemy import delete

        from bolsa_infrastructure.database.models.tables import SimAutoPositionRow

        await self._session.execute(
            delete(SimAutoPositionRow).where(
                SimAutoPositionRow.account_id == account_id,
                SimAutoPositionRow.engine_id == engine_id,
                SimAutoPositionRow.symbol == symbol,
            )
        )
        await _commit_if(self._session, self._autocommit)


class PostgresSimConsumedSignalStore:
    """Store durable de señales consumidas (tabla ``sim_consumed_signals``).

    ``autocommit=True`` (default) commitea por su cuenta: la marca debe ser durable
    ANTES de que el proceso pueda morir, porque de ella depende no re-emitir la misma
    oportunidad sobre la misma barra tras el reinicio.
    """

    def __init__(self, session: Any, *, autocommit: bool = True) -> None:
        self._session = session
        self._autocommit = autocommit

    async def mark(
        self,
        account_id: str,
        engine_id: str,
        signal_id: str,
        *,
        instrument_id: str,
        bar_timestamp: str,
        consumed_at: datetime | None = None,
    ) -> None:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import SimConsumedSignalRow

        await self._session.execute(
            pg_insert(SimConsumedSignalRow)
            .values(
                account_id=account_id,
                engine_id=engine_id,
                signal_id=signal_id,
                instrument_id=instrument_id,
                bar_timestamp=bar_timestamp,
                consumed_at=consumed_at or _now(),
            )
            .on_conflict_do_nothing(index_elements=["account_id", "engine_id", "signal_id"])
        )
        await _commit_if(self._session, self._autocommit)

    async def list_bar(self, account_id: str, engine_id: str, bar_timestamp: str) -> list[str]:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import SimConsumedSignalRow

        rows = (
            await self._session.execute(
                select(SimConsumedSignalRow.signal_id).where(
                    SimConsumedSignalRow.account_id == account_id,
                    SimConsumedSignalRow.engine_id == engine_id,
                    SimConsumedSignalRow.bar_timestamp == bar_timestamp,
                )
            )
        ).scalars()
        return sorted(rows)

    async def prune_before(self, account_id: str, engine_id: str, bar_timestamp: str) -> int:
        """Borra las señales de barras ANTERIORES (la tabla queda acotada a la actual)."""
        from sqlalchemy import delete

        from bolsa_infrastructure.database.models.tables import SimConsumedSignalRow

        result = await self._session.execute(
            delete(SimConsumedSignalRow).where(
                SimConsumedSignalRow.account_id == account_id,
                SimConsumedSignalRow.engine_id == engine_id,
                SimConsumedSignalRow.bar_timestamp < bar_timestamp,
            )
        )
        await _commit_if(self._session, self._autocommit)
        return int(result.rowcount or 0)


# ── P1-01: reconstrucción de la proyección desde el estado canónico ──────────────
# ``canonical_reader(account_id) -> Mapping[symbol, Decimal]`` (p. ej. posiciones
# abiertas del ledger/portfolio canónico). El worker AUTO lo usa para reconstruir la
# proyección cuando falta o diverge: la proyección es un espejo de recuperación, no
# una autoridad financiera.
CanonicalPositionReader = Callable[[str], Awaitable[Mapping[str, Decimal]]]


async def rebuild_sim_position_projection(
    *,
    account_id: str,
    engine_id: str,
    position_store: SimAutoPositionStore,
    canonical_reader: CanonicalPositionReader,
    protection: Mapping[str, SimPositionProjection] | None = None,
) -> dict[str, Decimal]:
    """Reconstruye la proyección durable desde el estado financiero canónico.

    Devuelve ``{symbol: qty}`` reconstruido y deja el espejo alineado (upsert de lo
    que existe en el canónico, delete de lo que ya no). ``protection`` permite
    conservar el estado de protección si el símbolo sigue abierto (no se pierde el
    ``high_watermark`` al reconstruir) — incluido el plan V2 (``position_state``): la
    reconstrucción ajusta la CANTIDAD, jamás el plan operativo de la posición.
    """
    canonical = await canonical_reader(account_id)
    canonical = {str(s): Decimal(str(q)) for s, q in canonical.items() if Decimal(str(q)) > 0}
    current = await position_store.read_projection(account_id, engine_id)
    for symbol, qty in canonical.items():
        prior = (protection or {}).get(symbol) or current.get(symbol)
        await position_store.upsert(
            account_id,
            engine_id,
            symbol,
            qty,
            avg_price=None,
            entry_price=prior.entry_price if prior else None,
            high_watermark=prior.high_watermark if prior else None,
            stop_price=prior.stop_price if prior else None,
            t1_state=prior.t1_state if prior else None,
            trailing_state=prior.trailing_state if prior else None,
            strategy_version_id=prior.strategy_version_id if prior else None,
            position_state=prior.position_state if prior else None,
        )
    for symbol in set(current) - set(canonical):
        await position_store.delete(account_id, engine_id, symbol)
    return dict(canonical)


# ── V2.24.2 (P2-B): unidad-de-trabajo proyección + finance ───────────────────────
@dataclass(frozen=True, slots=True)
class SimDurableUnitOfWork:
    """Compone contexto financiero + proyección de posición en UNA transacción.

    P2-B del audit V2.24: los dos espejos durables hacían ``commit()`` independiente,
    dejando una ventana en la que un crash podía persistir uno y no el otro. Con
    ``autocommit=False`` en ambos stores, esta unidad-de-trabajo hace los dos
    ``execute`` y commitea UNA sola vez al final (o no commitea nada si algo falla),
    de modo que proyección y contexto financiero del mismo fill son atómicos.

    No altera la regla P1-01: la proyección sigue siendo reconstruible desde el
    canónico; esto solo cierra la ventana transaccional entre ambos espejos.
    """

    session: Any
    finance_store: PostgresSimFillFinanceContextStore
    position_store: PostgresSimAutoPositionStore
    consumed_signal_store: PostgresSimConsumedSignalStore

    @classmethod
    def open(cls, session: Any) -> SimDurableUnitOfWork:
        """Abre la unidad-de-trabajo sobre una sesión (el caller commitea/rollback)."""
        return cls(
            session=session,
            finance_store=PostgresSimFillFinanceContextStore(session, autocommit=False),
            position_store=PostgresSimAutoPositionStore(session, autocommit=False),
            # P4: la marca de "señal consumida" pertenece a la MISMA transacción que el
            # espejo del fill que la consume — o el fill y su dedupe quedan juntos, o
            # no queda ninguno de los dos.
            consumed_signal_store=PostgresSimConsumedSignalStore(session, autocommit=False),
        )

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
