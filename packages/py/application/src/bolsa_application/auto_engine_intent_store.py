"""AutoEngineIntentStore — la INTENCIÓN del operador sobre AUTO como hecho durable (M10).

El problema que cierra: AUTO se habilitaba **sólo** por variable de entorno
(``AUTO_SIMULATION_WORKER_ENABLED``). Un operador que apagaba el motor y reiniciaba el
proceso con la variable todavía puesta lo veía arrancar de nuevo: no había ningún latch
durable del apagado.

Semántica (deliberadamente asimétrica):

* **``OFF`` durable GANA al env.** Es el latch: una fila ``OFF`` impide conducir turnos
  aunque ``AUTO_SIMULATION_WORKER_ENABLED=1``. Sin esto, «apagar» era un acto del proceso.
* **La AUSENCIA de fila no es ``OFF``.** Significa «el operador no ha declarado intención»
  y el env sigue decidiendo. Inventar un ``OFF`` al desplegar esta versión apagaría motores
  que hoy funcionan: la ausencia es información, no una decisión.
* Un ``desired_state`` fuera de ``ON``/``OFF`` tampoco es una decisión: el store lo trata
  como ausente (el env decide) en vez de convertirlo en un ``ON`` optimista.

Convenciones del repo (patrón ``kill_switch_store``/``reservation_store``): Protocol +
gemelo in-memory, imports de fila **perezosos** por método, ``ON CONFLICT`` para
idempotencia y ``autocommit`` explícito (``True`` por defecto: la intención debe ser durable
antes de que el motor la obedezca).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Protocol

__all__ = [
    "INTENT_OFF",
    "INTENT_ON",
    "InMemoryAutoEngineIntentStore",
    "AutoEngineIntent",
    "AutoEngineIntentStore",
    "PostgresAutoEngineIntentStore",
    "coerce_intent_state",
]

#: Estados válidos. Se comparan en mayúsculas y sin espacios (el operador escribe lo que
#: quiera en la API; la normalización es del borde, no del lector).
INTENT_ON = "ON"
INTENT_OFF = "OFF"
_VALID_STATES = frozenset({INTENT_ON, INTENT_OFF})


def coerce_intent_state(value: Any) -> str | None:
    """``ON``/``OFF`` normalizado, o ``None`` si el valor no es una decisión.

    ``None`` NO se convierte en ``ON``: un estado ilegible deja la decisión al env, que es
    el comportamiento previo. Convertirlo en ``ON`` sería inventar permiso para operar.
    """
    text = str(value or "").strip().upper()
    return text if text in _VALID_STATES else None


@dataclass(frozen=True, slots=True)
class AutoEngineIntent:
    """Una fila de ``auto_engine_intent``: la última intención declarada del operador."""

    account_id: str
    engine_id: str
    desired_state: str
    reason: str | None = None
    actor: str | None = None
    updated_at: str | None = None
    version: int = 1

    @property
    def is_off(self) -> bool:
        """¿El operador APAGÓ el motor? Sólo un ``OFF`` canónico lo afirma."""
        return self.desired_state == INTENT_OFF

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "engineId": self.engine_id,
            "desiredState": self.desired_state,
            "reason": self.reason,
            "actor": self.actor,
            "updatedAt": self.updated_at,
            "version": self.version,
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


def _row_to_intent(row: Any) -> AutoEngineIntent:
    return AutoEngineIntent(
        account_id=str(row.account_id or ""),
        engine_id=str(row.engine_id or ""),
        desired_state=coerce_intent_state(row.desired_state) or "",
        reason=row.reason,
        actor=row.actor,
        updated_at=_to_iso(row.updated_at),
        version=int(row.version or 1),
    )


class AutoEngineIntentStore(Protocol):
    """Persistencia de la intención del operador (una fila por cuenta + motor)."""

    async def load(self, account_id: str, engine_id: str) -> AutoEngineIntent | None:
        """La intención declarada, o ``None`` si el operador nunca la declaró."""
        ...

    async def save(self, intent: AutoEngineIntent) -> bool:
        """Alta/actualización idempotente; ``True`` si insertó y ``False`` si actualizó."""
        ...

    async def commit(self) -> None:
        """Hace durable lo escrito (no-op en el store in-memory)."""
        ...


class InMemoryAutoEngineIntentStore:
    """Store in-memory con la MISMA semántica que el PG (tests y camino hermético)."""

    def __init__(self, seed: tuple[AutoEngineIntent, ...] = ()) -> None:
        self._rows: dict[tuple[str, str], AutoEngineIntent] = {
            (row.account_id, row.engine_id): row for row in seed
        }

    def __len__(self) -> int:
        return len(self._rows)

    async def load(self, account_id: str, engine_id: str) -> AutoEngineIntent | None:
        return self._rows.get((str(account_id or ""), str(engine_id or "")))

    async def save(self, intent: AutoEngineIntent) -> bool:
        key = (intent.account_id, intent.engine_id)
        existing = self._rows.get(key)
        inserted = existing is None
        version = 1 if existing is None else existing.version + 1
        self._rows[key] = replace(intent, desired_state=coerce_intent_state(intent.desired_state) or "", version=version)
        return inserted

    async def commit(self) -> None:
        """No-op: el store in-memory ya es visible (espeja el contrato del PG)."""
        return None


class PostgresAutoEngineIntentStore:
    """``auto_engine_intent`` en PostgreSQL (idempotente por ``(account_id, engine_id)``)."""

    def __init__(self, session: Any, *, autocommit: bool = True) -> None:
        self._session = session
        self._autocommit = autocommit

    async def load(self, account_id: str, engine_id: str) -> AutoEngineIntent | None:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import AutoEngineIntentRow

        row = (
            await self._session.execute(
                sa.select(AutoEngineIntentRow)
                .where(AutoEngineIntentRow.account_id == str(account_id or ""))
                .where(AutoEngineIntentRow.engine_id == str(engine_id or ""))
            )
        ).scalar_one_or_none()
        return None if row is None else _row_to_intent(row)

    async def save(self, intent: AutoEngineIntent) -> bool:
        import sqlalchemy as sa
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import AutoEngineIntentRow

        state = coerce_intent_state(intent.desired_state)
        if state is None:
            # Un estado ilegible no es una decisión: no se escribe (ni ON ni OFF).
            raise ValueError(f"invalid AUTO intent state: {intent.desired_state!r}")
        values = {
            "account_id": intent.account_id,
            "engine_id": intent.engine_id,
            "desired_state": state,
            "reason": intent.reason,
            "actor": intent.actor,
            "updated_at": _to_instant(intent.updated_at),
            "version": max(1, int(intent.version or 1)),
        }
        insert_statement = (
            pg_insert(AutoEngineIntentRow)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["account_id", "engine_id"])
            .returning(AutoEngineIntentRow.engine_id)
        )
        result = await self._session.execute(insert_statement)
        inserted = result.scalars().first() is not None
        if not inserted:
            update_values = {
                name: value
                for name, value in values.items()
                if name not in ("account_id", "engine_id")
            }
            update_values["version"] = AutoEngineIntentRow.version + 1
            await self._session.execute(
                sa.update(AutoEngineIntentRow)
                .where(AutoEngineIntentRow.account_id == intent.account_id)
                .where(AutoEngineIntentRow.engine_id == intent.engine_id)
                .values(**update_values)
            )
        if self._autocommit:
            await self._session.commit()
        return inserted

    async def commit(self) -> None:
        await self._session.commit()
