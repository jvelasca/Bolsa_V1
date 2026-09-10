"""V2.23 / A9 (Bloque 5) — durabilidad SIM: contexto financiero + posición AUTO.

Dos espejos durables introducidos en la migración 028, con el mismo patrón que
``auto_engine_state_store`` (Protocol + doble InMemory + store Postgres con imports
de fila perezosos por método y commit explícito):

* ``SimFillFinanceContextStore`` — contexto financiero por ``execution_id`` para que
  un resolver reconstruya la finance de un fill sin memoria del ``SimulatedOrderResult``
  (P1-05). Idempotente por PK ``execution_id`` (``ON CONFLICT DO NOTHING``).
* ``SimAutoPositionStore`` — posición abierta por ``(engine_id, symbol)`` para que el
  worker AUTO readopte tras crash/restart (P1-06 / G7) en vez de re-comprar.

No hay aquí aritmética financiera ni decisiones: son espejos de estado. La autoridad
sigue en ``decision_contract`` + ``ExecuteTrade`` idempotente.
"""

from __future__ import annotations

from collections.abc import Mapping
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
]


def _now() -> datetime:
    return datetime.now(UTC)


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


class SimFillFinanceContextStore(Protocol):
    async def save(self, context: SimFillFinanceContext) -> None: ...
    async def get(self, execution_id: str) -> SimFillFinanceContext | None: ...


class SimAutoPositionStore(Protocol):
    async def read_open(self, engine_id: str) -> Mapping[str, Decimal]: ...
    async def upsert(self, engine_id: str, symbol: str, quantity: Decimal,
                     *, avg_price: Decimal | None = None) -> None: ...
    async def delete(self, engine_id: str, symbol: str) -> None: ...


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
    """Doble hermético del espejo de posición (por ``engine_id`` → symbol→qty)."""

    def __init__(self) -> None:
        self._rows: dict[str, dict[str, Decimal]] = {}

    async def read_open(self, engine_id: str) -> Mapping[str, Decimal]:
        return {s: q for s, q in self._rows.get(engine_id, {}).items() if q > 0}

    async def upsert(self, engine_id: str, symbol: str, quantity: Decimal,
                     *, avg_price: Decimal | None = None) -> None:
        self._rows.setdefault(engine_id, {})[symbol] = quantity

    async def delete(self, engine_id: str, symbol: str) -> None:
        self._rows.get(engine_id, {}).pop(symbol, None)


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
    """Store durable del espejo de posición SIM (tabla ``sim_auto_positions``)."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def read_open(self, engine_id: str) -> dict[str, Decimal]:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import SimAutoPositionRow

        rows = (
            await self._session.execute(
                select(SimAutoPositionRow).where(SimAutoPositionRow.engine_id == engine_id)
            )
        ).scalars()
        return {
            row.symbol: row.quantity
            for row in rows
            if row.quantity is not None and row.quantity > 0
        }

    async def upsert(self, engine_id: str, symbol: str, quantity: Decimal,
                     *, avg_price: Decimal | None = None) -> None:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import SimAutoPositionRow

        now = _now()
        await self._session.execute(
            pg_insert(SimAutoPositionRow)
            .values(
                engine_id=engine_id,
                symbol=symbol,
                quantity=quantity,
                avg_price=avg_price,
                opened_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["engine_id", "symbol"],
                set_={
                    "quantity": quantity,
                    "avg_price": avg_price,
                    "updated_at": now,
                },
            )
        )
        await self._session.commit()

    async def delete(self, engine_id: str, symbol: str) -> None:
        from sqlalchemy import delete

        from bolsa_infrastructure.database.models.tables import SimAutoPositionRow

        await self._session.execute(
            delete(SimAutoPositionRow).where(
                SimAutoPositionRow.engine_id == engine_id,
                SimAutoPositionRow.symbol == symbol,
            )
        )
        await self._session.commit()
