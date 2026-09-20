"""KillSwitchStore — el latcheo de la parada DURA como propiedad del SISTEMA (V2.43.3).

``HardKillSwitch`` (``bolsa_analytics.cognitive.hard_kill_switch``) es puro y **en memoria**:
su propio docstring lo dice ("el llamante lo persiste si quiere"). El problema que cierra
este store es exactamente ese "si quiere": el worker creaba ``HardKillSwitch()`` en cada
arranque, así que

    WORKER 1 → KILL ON → CRASH → WORKER 2 → engaged = False

El sistema olvidaba el HALT. Eso contradice la semántica operacional de una parada dura.

Aquí el estado se persiste por ``(account_id, engine_id)`` y el arranque lo LEE antes de
readoptar posición: un reinicio no puede reabrir el motor. La liberación exige
``reconciliation_id`` (reconciliación explícita) y también se persiste, con actor y motivo,
para que "quién levantó la parada y con qué reconciliación" sea auditable.

Convenciones del repo (patrón ``reservation_store``/``sim_durable_store``): Protocol +
gemelo in-memory, imports de fila **perezosos** por método, ``ON CONFLICT`` para
idempotencia y ``autocommit`` explícito (``True`` por defecto: la parada debe ser durable
antes de que el motor siga). Una fila ausente significa "la parada nunca se activó": la
ausencia es información, nunca un ``engaged=False`` inventado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from bolsa_analytics.cognitive.hard_kill_switch import (
    KillSwitchReason,
    coerce_kill_switch_reason,
)

__all__ = [
    "InMemoryKillSwitchStore",
    "KillState",
    "KillSwitchStore",
    "PostgresKillSwitchStore",
]


@dataclass(frozen=True, slots=True)
class KillState:
    """Estado durable de la parada dura: una fila por ``(account_id, engine_id)``.

    ``engaged`` es el latch; ``reason`` el motivo tipificado; ``engagement_id`` la identidad
    de la activación (no solo el motivo: permite auditar "qué activación concreta"); el
    resto es el rastro de la liberación. Un ``reason`` no canónico se descarta (``None``):
    un halt sin causa tipificada no es auditable, y aquí no se inventa uno.
    """

    account_id: str
    engine_id: str
    engaged: bool = False
    reason: KillSwitchReason | None = None
    engaged_at: str | None = None
    engagement_id: str | None = None
    reengagements: int = 0
    released_at: str | None = None
    release_actor: str | None = None
    release_reconciliation_id: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "engineId": self.engine_id,
            "engaged": self.engaged,
            "reason": self.reason,
            "engagedAt": self.engaged_at,
            "engagementId": self.engagement_id,
            "reengagements": self.reengagements,
            "releasedAt": self.released_at,
            "releaseActor": self.release_actor,
            "releaseReconciliationId": self.release_reconciliation_id,
            "updatedAt": self.updated_at,
        }


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return str(value.isoformat())
    except AttributeError:
        return str(value)


def _to_instant(value: Any) -> Any:
    """ISO del modelo puro → ``datetime`` (la columna es ``timestamptz``)."""
    from datetime import UTC, datetime

    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _row_to_state(row: Any) -> KillState:
    return KillState(
        account_id=str(row.account_id or ""),
        engine_id=str(row.engine_id or ""),
        engaged=bool(row.engaged),
        reason=coerce_kill_switch_reason(row.reason),
        engaged_at=_to_iso(row.engaged_at),
        engagement_id=row.engagement_id,
        reengagements=int(row.reengagements or 0),
        released_at=_to_iso(row.released_at),
        release_actor=row.release_actor,
        release_reconciliation_id=row.release_reconciliation_id,
        updated_at=_to_iso(row.updated_at),
    )


class KillSwitchStore(Protocol):
    """Persistencia del estado de la parada dura."""

    async def load(self, account_id: str, engine_id: str) -> KillState | None:
        """La fila de esa cuenta+motor, o ``None`` (la parada nunca se activó)."""
        ...

    async def save(self, state: KillState) -> bool:
        """Alta/actualización idempotente por ``(account_id, engine_id)``.

        Devuelve ``True`` si insertó y ``False`` si actualizó.
        """
        ...

    async def commit(self) -> None:
        """Hace durable lo escrito (no-op en el store in-memory)."""
        ...


class InMemoryKillSwitchStore:
    """Store in-memory con la MISMA semántica que el PG (tests y camino hermético)."""

    def __init__(self, seed: tuple[KillState, ...] = ()) -> None:
        self._rows: dict[tuple[str, str], KillState] = {
            (row.account_id, row.engine_id): row for row in seed
        }

    def __len__(self) -> int:
        return len(self._rows)

    async def load(self, account_id: str, engine_id: str) -> KillState | None:
        return self._rows.get((str(account_id or ""), str(engine_id or "")))

    async def save(self, state: KillState) -> bool:
        key = (state.account_id, state.engine_id)
        inserted = key not in self._rows
        self._rows[key] = state
        return inserted

    async def commit(self) -> None:
        """No-op: el store in-memory ya es visible (espeja el contrato del PG)."""
        return None


class PostgresKillSwitchStore:
    """``auto_kill_state`` en PostgreSQL (idempotente por ``(account_id, engine_id)``)."""

    def __init__(self, session: Any, *, autocommit: bool = True) -> None:
        self._session = session
        self._autocommit = autocommit

    async def load(self, account_id: str, engine_id: str) -> KillState | None:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import AutoKillStateRow

        row = (
            await self._session.execute(
                sa.select(AutoKillStateRow)
                .where(AutoKillStateRow.account_id == str(account_id or ""))
                .where(AutoKillStateRow.engine_id == str(engine_id or ""))
            )
        ).scalar_one_or_none()
        return None if row is None else _row_to_state(row)

    async def save(self, state: KillState) -> bool:
        import sqlalchemy as sa
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import AutoKillStateRow

        values = {
            "account_id": state.account_id,
            "engine_id": state.engine_id,
            "engaged": state.engaged,
            "reason": state.reason,
            "engaged_at": _to_instant(state.engaged_at),
            "engagement_id": state.engagement_id,
            "reengagements": state.reengagements,
            "released_at": _to_instant(state.released_at),
            "release_actor": state.release_actor,
            "release_reconciliation_id": state.release_reconciliation_id,
            "updated_at": _to_instant(state.updated_at),
        }
        insert_statement = (
            pg_insert(AutoKillStateRow)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["account_id", "engine_id"])
            .returning(AutoKillStateRow.engine_id)
        )
        result = await self._session.execute(insert_statement)
        inserted = result.scalars().first() is not None
        if not inserted:
            update_values = {
                name: value
                for name, value in values.items()
                if name not in ("account_id", "engine_id")
            }
            await self._session.execute(
                sa.update(AutoKillStateRow)
                .where(AutoKillStateRow.account_id == state.account_id)
                .where(AutoKillStateRow.engine_id == state.engine_id)
                .values(**update_values)
            )
        if self._autocommit:
            await self._session.commit()
        return inserted

    async def commit(self) -> None:
        await self._session.commit()
