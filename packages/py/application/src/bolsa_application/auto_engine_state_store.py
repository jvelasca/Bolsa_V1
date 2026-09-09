"""V2.22 / A9 (M4 · P2 del audit) — estado durable del AUTO Engine.

Sustituye la telemetría AUTO en-memoria de ``PaperAutoEngine``
(``_state|_last_tick|_proposals|_vetoes|_pending_plans|_last_reason``) por un
espejo durable en PostgreSQL (tablas ``auto_engine_runs`` + ``auto_engine_ticks``,
Alembic ``027``), de modo que un worker reiniciado readopta ``RUNNING`` +
contadores SIN un tick doble tras crash (invariante exact-una-vez del bucle AUTO).

Sigue el patrón ya maduro de ``execution_event.py``: un Protocol + un doble
en-memoria (tests hermético/reina) + un ``Postgres*Store`` que importa las filas
del modelo infra de forma diferida (en cada método, no en el módulo), para no
acoplar este paquete application al infra en import-time.

Semántica de conteo (exact-una-vez por tick matriculado):

* ``AutoEngineTickInput`` porta los **totales ABS** tras ese tick
  (proposals/vetoes/pending_plans son acumulados monótonos desde el arranque) y un
  ``seq`` igual a la posición monotónica del tick en el run.
* ``record_tick`` matricula UNA fila de tick y, si el ``seq`` ya está registrado,
  lo trata como re-registro idempotente (no dobla). Solo sincroniza la fila-run
  cuando el tick es NUEVO (avance monótono de ``seq``).
* Como cada tick corre SOLO cuando el worker decide ejecutarlo y un reinicio
  relee el store (no re-ejecuta el tick del crash), la cuenta leída tras un
  crash/relaunch refleja SOLO los ticks realmente matriculados antes del crash —
  jamás se dobla por el hecho de reiniciar. `crash_restart_readopts` materializa
  exactamente esa propiedad de "readoptar sin doblar tick".

SIM-ONLY / fail-closed: este módulo solo persiste telemetría/estado del motor; no
abre venue alguno ni materializa dinero (la liquidación SIM queda en otras capas
gobernadas por decision_contract/simulated_settlement).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, runtime_checkable

AutoEngineState = Literal[
    "RUNNING",
    "PAUSED",
    "BLOCKED",
    "DEGRADED",
    "REQUIRES_ATTENTION",
]


def _reason_text(reasons: tuple[str, ...] | list[str] | None) -> str:
    return ", ".join(reasons or ("idle",))


def _state_of(raw: str) -> AutoEngineState:
    v = str(raw or "PAUSED").upper()
    mapping: dict[str, AutoEngineState] = {
        "RUNNING": "RUNNING",
        "PAUSED": "PAUSED",
        "BLOCKED": "BLOCKED",
        "DEGRADED": "DEGRADED",
        "REQUIRES_ATTENTION": "REQUIRES_ATTENTION",
    }
    return mapping.get(v, "REQUIRES_ATTENTION")


@dataclass(frozen=True, slots=True)
class AutoEngineSnapshot:
    """Vista durable del estado AUTO que un proceso reiniciado readopta."""

    engine_id: str
    state: AutoEngineState = "PAUSED"
    venue: str = "paper"
    ticks: int = 0
    proposals: int = 0
    vetoes: int = 0
    pending_plans: int = 0
    last_reason: tuple[str, ...] = ("idle",)
    last_tick_at: datetime | None = None

    @property
    def last_reason_text(self) -> str:
        return _reason_text(self.last_reason)


@dataclass(frozen=True, slots=True)
class AutoEngineTickInput:
    """Payload de un ``run_tick`` que el store debe matricular una sola vez.

    ``seq`` = posición monotónica 1-based del tick en el run (== siguiente valor
    tras el último tick matriculado). ``proposals/vetoes/pending_plans`` son los
    TOTALES acumulados tras este tick (el store los sincroniza a la run).
    """

    engine_id: str
    venue: str
    state: AutoEngineState
    seq: int
    proposals: int
    vetoes: int
    pending_plans: int
    last_reason: tuple[str, ...] = ("idle",)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@runtime_checkable
class AutoEngineStore(Protocol):
    async def read(self, engine_id: str) -> AutoEngineSnapshot | None: ...

    async def record_tick(self, tick: AutoEngineTickInput) -> None: ...


class InMemoryAutoEngineStore:
    """Test double: espeja la durabilidad por-engine del Postgres store.

    Guarda por ``engine_id`` el snapshot más reciente (totales monótonos) y una
    lista de ticks matriculados para poder contar (invariante no-doble-tick). Un
    crash/relaunch se simula ``read()`` de nuevo → readopta sin re-ejecutar tick.
    """

    def __init__(self) -> None:
        self._runs: dict[str, AutoEngineSnapshot] = {}
        self._max_seq: dict[str, int] = {}

    async def read(self, engine_id: str) -> AutoEngineSnapshot | None:
        return self._runs.get(engine_id)

    async def record_tick(self, tick: AutoEngineTickInput) -> None:
        max_seq = self._max_seq.get(tick.engine_id, 0)
        if tick.seq <= max_seq:
            # Re-registro de un tick ya matriculado → no avanza (no dobla).
            return
        self._max_seq[tick.engine_id] = tick.seq
        self._runs[tick.engine_id] = AutoEngineSnapshot(
            engine_id=tick.engine_id,
            state=tick.state,
            venue=tick.venue,
            ticks=tick.seq,
            proposals=tick.proposals,
            vetoes=tick.vetoes,
            pending_plans=tick.pending_plans,
            last_reason=tuple(tick.last_reason or ("idle",)),
            last_tick_at=tick.occurred_at,
        )

    def recorded_seq_max(self, engine_id: str) -> int:
        """Último ``seq`` matriculado (diagnóstico de no-doble en tests)."""
        return self._max_seq.get(engine_id, 0)


class PostgresAutoEngineStore:
    """``auto_engine_runs`` + ``auto_engine_ticks`` en PostgreSQL (Alembic 027).

    ``read`` relee la fila-run (+ cuenta de ticks). ``record_tick`` matricula la
    fila de tick (INGEST) y sincroniza el acumulado de la run; si el ``seq`` ya
    está matriculado (UNIQUE ``auto_engine_ticks_engine_seq_uidx``), el tick se
    omite (no-doble) y la run no avanza. El commit único hace la operación
    atómica entre tick y run.
    """

    def __init__(self, session: Any) -> None:
        self._session = session

    def _now(self) -> datetime:
        return datetime.now(UTC)

    async def read(self, engine_id: str) -> AutoEngineSnapshot | None:
        import sqlalchemy as sa
        from bolsa_infrastructure.database.models.tables import AutoEngineRunRow

        row = (
            await self._session.execute(
                sa.select(AutoEngineRunRow).where(AutoEngineRunRow.engine_id == engine_id)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        ticks = await self._read_tick_count(engine_id)
        return AutoEngineSnapshot(
            engine_id=row.engine_id,
            state=_state_of(row.state),
            venue=row.venue,
            ticks=ticks,
            proposals=int(row.proposals),
            vetoes=int(row.vetoes),
            pending_plans=int(row.pending_plans),
            last_reason=tuple(
                [r.strip() for r in (row.last_reason or "").split(",") if r.strip()]
                if row.last_reason
                else ("idle",)
            ),
            last_tick_at=row.last_tick_at,
        )

    async def _read_tick_count(self, engine_id: str) -> int:
        import sqlalchemy as sa
        from bolsa_infrastructure.database.models.tables import AutoEngineTickRow

        count = await self._session.scalar(
            sa.select(sa.func.count())
            .select_from(AutoEngineTickRow)
            .where(AutoEngineTickRow.engine_id == engine_id)
        )
        return int(count or 0)

    async def record_tick(self, tick: AutoEngineTickInput) -> None:
        from bolsa_infrastructure.database.models.tables import (
            AutoEngineRunRow,
            AutoEngineTickRow,
        )
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        now = self._now()
        occurred = tick.occurred_at or now
        # 1) Matricular la fila de tick exactamente una vez (UNIQUE engine+seq).
        inserted = await self._session.execute(
            pg_insert(AutoEngineTickRow)
            .values(
                tick_id=f"tick-{tick.engine_id}-{tick.seq}",
                engine_id=tick.engine_id,
                seq=tick.seq,
                state=tick.state,
                proposals=int(tick.proposals),
                vetoes=int(tick.vetoes),
                pending_plans=int(tick.pending_plans),
                reason=_reason_text(tick.last_reason),
                tick_at=occurred,
                created_at=now,
            )
            .on_conflict_do_nothing(constraint="auto_engine_ticks_engine_seq_uidx")
        )
        if inserted.rowcount == 0:
            # Tick ya matriculado (crash/re-registro) → no avanzar la run (no dobla).
            await self._session.rollback()
            return
        # 2) Sincronizar el acumulado durable de la run a los totales DE ESTE tick.
        await self._session.execute(
            pg_insert(AutoEngineRunRow)
            .values(
                engine_id=tick.engine_id,
                venue=tick.venue,
                state=tick.state,
                last_tick_at=occurred,
                proposals=int(tick.proposals),
                vetoes=int(tick.vetoes),
                pending_plans=int(tick.pending_plans),
                last_reason=_reason_text(tick.last_reason),
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[AutoEngineRunRow.engine_id],
                set_={
                    "venue": tick.venue,
                    "state": tick.state,
                    "last_tick_at": occurred,
                    "proposals": int(tick.proposals),
                    "vetoes": int(tick.vetoes),
                    "pending_plans": int(tick.pending_plans),
                    "last_reason": _reason_text(tick.last_reason),
                    "updated_at": now,
                },
            )
        )
        await self._session.commit()


# ---------------------------------------------------------------------------
# Orchestación durable: un ciclo de motor que persiste y readopta sin doblar.
# ---------------------------------------------------------------------------


def next_tick_input(
    snapshot: AutoEngineSnapshot | None,
    *,
    venue: str,
    state: AutoEngineState,
    more_proposals: int,
    more_vetoes: int,
    more_pending_plans: int,
    reason: tuple[str, ...] = ("idle",),
    occurred_at: datetime | None = None,
) -> AutoEngineTickInput:
    """Construye el ``AutoEngineTickInput`` del siguiente tick a partir del
    snapshot durable readoptado (acumulados monótonos) + el delta del dry_tick.

    ``seq`` = ticks(snapshot) + 1 (siguiente posición monotónica). Al crash que
    pierde un tick no-persistido, su releer del snapshot devuelve los ticks
    anteriores y recomputar el mismo delta produce de nuevo ``seq = prev+1`` →
    el tick se registra UNA vez (idempotente por store).
    """
    prev = snapshot
    seq = (prev.ticks if prev is not None else 0) + 1
    return AutoEngineTickInput(
        engine_id=(prev.engine_id if prev is not None else f"engine-{venue}"),
        venue=str(venue or (prev.venue if prev is not None else "paper")),
        state=state,
        seq=seq,
        proposals=(prev.proposals if prev is not None else 0) + more_proposals,
        vetoes=(prev.vetoes if prev is not None else 0) + more_vetoes,
        pending_plans=(prev.pending_plans if prev is not None else 0) + more_pending_plans,
        last_reason=reason if reason else ("idle",),
        occurred_at=occurred_at or datetime.now(UTC),
    )


async def crash_restart_readopts(
    store: AutoEngineStore,
    *,
    engine_id: str,
) -> AutoEngineSnapshot | None:
    """Readopta el estado durable de un motor tras un crash/relaunch.

    El reinicio NO ejecuta un nuevo ``run_tick``: relee el store. Si el diseño
    re-ejecutara el tick del crash se doblaría el contador de ticks; aquí se
    demuestra que reiniciar NO dobla: el snapshot reflecta solo los ticks que se
    matricularon durablemente antes del crash.
    """
    return await store.read(engine_id)
