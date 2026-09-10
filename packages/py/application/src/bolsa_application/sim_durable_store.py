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

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

__all__ = [
    "InMemorySimAutoPositionStore",
    "InMemorySimFillFinanceContextStore",
    "PostgresSimAutoPositionStore",
    "PostgresSimFillFinanceContextStore",
    "SimAutoPositionStore",
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


@dataclass(frozen=True, slots=True)
class SimFillFinanceContext:
    """Contexto financiero durable de un fill SIM (lineal a ``SimulatedFillFinance``)."""

    execution_id: str
    instrument_id: str
    side: str  # "buy" | "sell" (minúsculas)
    quantity: Decimal
    price: Decimal
    account_id: str | None = None
    venue: str = "simulated"
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise ValueError("SimFillFinanceContext exige execution_id no vacío")
        if self.side not in {"buy", "sell"}:
            raise ValueError(f"side inválido (esperado buy/sell): {self.side!r}")
        if self.quantity <= 0:
            raise ValueError("quantity debe ser > 0")
        if self.price <= 0:
            raise ValueError("price debe ser > 0")


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


class SimFillFinanceContextStore(Protocol):
    async def save(self, context: SimFillFinanceContext) -> None: ...
    async def get(self, execution_id: str) -> SimFillFinanceContext | None: ...


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
    ) -> None: ...
    async def delete(self, account_id: str, engine_id: str, symbol: str) -> None: ...


class InMemorySimFillFinanceContextStore:
    """Doble hermético: idempotente por ``execution_id``."""

    def __init__(self) -> None:
        self._rows: dict[str, SimFillFinanceContext] = {}

    async def save(self, context: SimFillFinanceContext) -> None:
        self._rows.setdefault(context.execution_id, context)

    async def get(self, execution_id: str) -> SimFillFinanceContext | None:
        return self._rows.get(execution_id)

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
            s: r
            for s, r in self._rows.get((account_id, engine_id), {}).items()
            if r.quantity > 0
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
        )

    async def delete(self, account_id: str, engine_id: str, symbol: str) -> None:
        self._rows.get((account_id, engine_id), {}).pop(symbol, None)


class PostgresSimFillFinanceContextStore:
    """Store durable del contexto financiero por fill (tabla ``sim_fill_finance_context``)."""

    def __init__(self, session: Any) -> None:
        self._session = session

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
                account_id=context.account_id,
                venue=context.venue,
                idempotency_key=context.idempotency_key,
                created_at=_now(),
            )
            .on_conflict_do_nothing(index_elements=["execution_id"])
        )
        # Commit propio: la fila debe ser DURABLE y visible ANTES de mover dinero
        # (idempotencia/recuperación). No interferimos con la transacción externa
        # del ExecutionEventStore (que commitea por su cuenta).
        await self._session.commit()

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
            account_id=row.account_id,
            venue=row.venue,
            idempotency_key=row.idempotency_key,
        )


class PostgresSimAutoPositionStore:
    """Store durable de la proyección de posición SIM (tabla ``sim_auto_positions``).

    V2.24 / A9.1: aislada por ``account_id`` (P1-02) y con estado de protección
    (P2-01). La proyección es **reconstruible** desde el estado financiero canónico
    (P1-01) — ver ``rebuild_sim_position_projection``.
    """

    def __init__(self, session: Any) -> None:
        self._session = session

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
                    "updated_at": now,
                },
            )
        )
        await self._session.commit()

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
        await self._session.commit()


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
    ``high_watermark`` al reconstruir).
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
        )
    for symbol in set(current) - set(canonical):
        await position_store.delete(account_id, engine_id, symbol)
    return dict(canonical)
