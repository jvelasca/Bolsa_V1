"""AdaptiveGateStore — la racha de fallos del sink del gate Adaptive, del SISTEMA (AUTO-15).

``assess_data_gate`` (``bolsa_analytics.cognitive.auto_adaptive_data_gate``) es puro y recibe sus
hechos ya medidos. Uno de ellos —``sink_failures``, los fallos **consecutivos** del sink del
journal— vivía en el worker como atributo de proceso (``_v2_adaptive_sink_failures``), así que

    WORKER 1 → 2 fallos (DEGRADED) → CRASH → WORKER 2 → 0 fallos → OK

El sistema olvidaba la racha con la que juzgaba su propia evidencia, y con ``3`` consecutivos el
gate pasa a ``STALE`` (congela el reparto y no admite reactivaciones). Y **no es reconstruible**:
un fallo de escritura no dejó fila en ``decision_journal_entries`` y el ancla de antigüedad mide
*publicación*, no *error*. Deducirla sería inventar la prueba.

Aquí el contador se persiste por ``(account_id, engine_id)`` y el arranque lo LEE para sembrar el
contador del proceso. El patrón es el del ``auto_kill_state`` de ``AUTO-3`` (mismo P0, misma casa):
Protocol + gemelo in-memory, imports de fila **perezosos** por método, ``ON CONFLICT`` para la
idempotencia y ``autocommit`` explícito.

Dos operaciones, y **ninguna** es "guardar la fila entera":

* ``record_failure`` — incremento **atómico** (``INSERT ... ON CONFLICT DO UPDATE SET
  sink_failures = sink_failures + 1``). Un ``load`` + ``save`` perdería fallos concurrentes, y la
  racha es justo el dato que no puede perderse. Devuelve la racha resultante.
* ``record_success`` — reset **sin amplificación**: ``UPDATE ... WHERE sink_failures > 0``, de modo
  que un despliegue sano no escribe una fila por tick en el camino caliente. Devuelve cuántas filas
  reseteó (``0`` ⇒ no había racha que resetear: no se escribió nada).

El contrato de sesión es el del sink de ``AUTO-10``: el store escribe en la MISMA sesión del tick,
así que un fallo de escritura hace ``rollback`` y **sube** el error (el worker lo declara y la racha
cae al proceso). Sin ese ``rollback``, el siguiente store del turno fallaría con
``PendingRollbackError`` y una traza rota tumbaría el compromiso de capital.

Una fila ausente significa "no hay constancia durable de fallos": la ausencia es información
(racha 0), nunca un cero fabricado — y el arranque lo declara.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

__all__ = [
    "AdaptiveGateState",
    "AdaptiveGateStore",
    "InMemoryAdaptiveGateStore",
    "PostgresAdaptiveGateStore",
    "sink_failures_from_state",
]


@dataclass(frozen=True, slots=True)
class AdaptiveGateState:
    """Estado durable del gate de EVIDENCIA: una fila por ``(account_id, engine_id)``.

    ``sink_failures`` es la racha **consecutiva** (un éxito la resetea). ``last_failure_at`` y
    ``last_success_at`` fechan las dos transiciones, para que "cuándo empezó a fallar" y "cuándo
    se curó" sean auditables sin releer el log del proceso.
    """

    account_id: str = ""
    engine_id: str = ""
    sink_failures: int = 0
    last_failure_at: str | None = None
    last_success_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "engineId": self.engine_id,
            "sinkFailures": self.sink_failures,
            "lastFailureAt": self.last_failure_at,
            "lastSuccessAt": self.last_success_at,
            "updatedAt": self.updated_at,
        }


def sink_failures_from_state(state: AdaptiveGateState | None) -> int:
    """(PURA) la racha que ENTRÓ al gate a partir del estado durable.

    Una fila ausente (o ilegible) es racha ``0``: no se observó ningún fallo durable. No se
    supone salud ni se inventa un fallo: el hueco de "sin constancia durable" lo declara el
    llamante, no este helper.
    """
    if state is None:
        return 0
    return max(0, int(state.sink_failures or 0))


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


def _row_to_state(row: Any) -> AdaptiveGateState:
    return AdaptiveGateState(
        account_id=str(row.account_id or ""),
        engine_id=str(row.engine_id or ""),
        sink_failures=max(0, int(row.sink_failures or 0)),
        last_failure_at=_to_iso(row.last_failure_at),
        last_success_at=_to_iso(row.last_success_at),
        updated_at=_to_iso(row.updated_at),
    )


class AdaptiveGateStore(Protocol):
    """Persistencia de la racha de fallos del gate de evidencia."""

    async def load(self, account_id: str, engine_id: str) -> AdaptiveGateState | None:
        """La fila de esa cuenta+motor, o ``None`` (sin constancia durable de fallos)."""
        ...

    async def record_failure(
        self, account_id: str, engine_id: str, *, at: str | None = None
    ) -> int:
        """Cuenta un fallo consecutivo y devuelve la racha resultante."""
        ...

    async def record_success(
        self, account_id: str, engine_id: str, *, at: str | None = None
    ) -> int:
        """Resetea la racha si había una. Devuelve las filas reseteadas (``0`` = no escribió)."""
        ...

    async def commit(self) -> None:
        """Hace durable lo escrito (no-op en el store in-memory)."""
        ...


class InMemoryAdaptiveGateStore:
    """Store in-memory con la MISMA semántica que el PG (tests y camino hermético)."""

    def __init__(self, seed: tuple[AdaptiveGateState, ...] = ()) -> None:
        self._rows: dict[tuple[str, str], AdaptiveGateState] = {
            (row.account_id, row.engine_id): row for row in seed
        }

    def __len__(self) -> int:
        return len(self._rows)

    async def load(self, account_id: str, engine_id: str) -> AdaptiveGateState | None:
        return self._rows.get((str(account_id or ""), str(engine_id or "")))

    async def record_failure(
        self, account_id: str, engine_id: str, *, at: str | None = None
    ) -> int:
        key = (str(account_id or ""), str(engine_id or ""))
        previous = self._rows.get(key)
        failures = sink_failures_from_state(previous) + 1
        self._rows[key] = AdaptiveGateState(
            account_id=key[0],
            engine_id=key[1],
            sink_failures=failures,
            last_failure_at=at,
            last_success_at=previous.last_success_at if previous is not None else None,
            updated_at=at,
        )
        return failures

    async def record_success(
        self, account_id: str, engine_id: str, *, at: str | None = None
    ) -> int:
        key = (str(account_id or ""), str(engine_id or ""))
        previous = self._rows.get(key)
        if previous is None or sink_failures_from_state(previous) <= 0:
            # Sin racha viva no se escribe: es el mismo "sin amplificación" del PG.
            return 0
        self._rows[key] = AdaptiveGateState(
            account_id=key[0],
            engine_id=key[1],
            sink_failures=0,
            last_failure_at=previous.last_failure_at,
            last_success_at=at,
            updated_at=at,
        )
        return 1

    async def commit(self) -> None:
        """No-op: el store in-memory ya es visible (espeja el contrato del PG)."""
        return None


class PostgresAdaptiveGateStore:
    """``adaptive_gate_state`` en PostgreSQL (idempotente por ``(account_id, engine_id)``)."""

    def __init__(self, session: Any, *, autocommit: bool = True) -> None:
        self._session = session
        self._autocommit = autocommit

    async def load(self, account_id: str, engine_id: str) -> AdaptiveGateState | None:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import AdaptiveGateStateRow

        row = (
            await self._session.execute(
                sa.select(AdaptiveGateStateRow)
                .where(AdaptiveGateStateRow.account_id == str(account_id or ""))
                .where(AdaptiveGateStateRow.engine_id == str(engine_id or ""))
            )
        ).scalar_one_or_none()
        return None if row is None else _row_to_state(row)

    async def record_failure(
        self, account_id: str, engine_id: str, *, at: str | None = None
    ) -> int:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import AdaptiveGateStateRow

        instant = _to_instant(at)
        statement = (
            pg_insert(AdaptiveGateStateRow)
            .values(
                account_id=str(account_id or ""),
                engine_id=str(engine_id or ""),
                sink_failures=1,
                last_failure_at=instant,
                updated_at=instant,
            )
            .on_conflict_do_update(
                index_elements=["account_id", "engine_id"],
                set_={
                    # Incremento ATÓMICO en la base: la racha no puede perder un fallo por una
                    # carrera entre dos lectores (un ``load``+``save`` sí lo perdería).
                    "sink_failures": AdaptiveGateStateRow.sink_failures + 1,
                    "last_failure_at": instant,
                    "updated_at": instant,
                },
            )
            .returning(AdaptiveGateStateRow.sink_failures)
        )
        try:
            result = await self._session.execute(statement)
            failures = int(result.scalars().one())
            if self._autocommit:
                await self._session.commit()
        except Exception:
            # Fail-open DE VERDAD (mismo contrato que el sink de AUTO-10): el worker escribe la
            # racha en la MISMA sesión del tick, así que una escritura fallida la deja envenenada
            # y, sin ``rollback``, el SIGUIENTE store del turno fallaría con
            # ``PendingRollbackError`` —esa traza rota tumbaría el compromiso de capital—. Se
            # limpia aquí y el error SUBE para que el worker lo DECLARE: la racha cae al proceso
            # (``sinkFailuresDurable = false``), nunca se finge persistida.
            await self._session.rollback()
            raise
        return failures

    async def record_success(
        self, account_id: str, engine_id: str, *, at: str | None = None
    ) -> int:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import AdaptiveGateStateRow

        instant = _to_instant(at)
        statement = (
            sa.update(AdaptiveGateStateRow)
            .where(AdaptiveGateStateRow.account_id == str(account_id or ""))
            .where(AdaptiveGateStateRow.engine_id == str(engine_id or ""))
            # El ``WHERE`` es la optimización declarada: sin racha viva no se escribe (ni se
            # crea fila), así que un despliegue sano no amplifica escrituras por tick.
            .where(AdaptiveGateStateRow.sink_failures > 0)
            .values(sink_failures=0, last_success_at=instant, updated_at=instant)
        )
        try:
            result = await self._session.execute(statement)
            reset = int(result.rowcount or 0)
            if self._autocommit and reset:
                await self._session.commit()
        except Exception:
            # Mismo contrato de sesión que en ``record_failure``: la publicación ya ocurrió, así
            # que un reset que no se puede escribir se LIMPIA (``rollback``) y se declara, en vez
            # de dejar la sesión del tick envenenada para los stores que vengan después.
            await self._session.rollback()
            raise
        return reset

    async def commit(self) -> None:
        await self._session.commit()
