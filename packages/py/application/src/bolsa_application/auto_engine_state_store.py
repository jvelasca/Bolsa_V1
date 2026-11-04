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

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol, runtime_checkable

AutoEngineState = Literal[
    "RUNNING",
    "PAUSED",
    "BLOCKED",
    "DEGRADED",
    "REQUIRES_ATTENTION",
]

#: v2.88.79 — fase operacional REAL del turno (telemetría, no inferencia de ``RUNNING``).
#: Un latido no es una fase; ``NO_ACTIVITY`` es «vivo pero sin actividad concreta medida»,
#: y su ausencia (``None``) es «sin dato todavía» — nunca una fase inventada.
AutoActivity = Literal[
    "ANALYZING",
    "WAITING_SIGNAL",
    "PREPARING_OPERATION",
    "WAITING_EXECUTION",
    "APPLYING_RESULT",
    "NO_ACTIVITY",
    "BLOCKED",
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


def _activity_of(raw: str | None) -> AutoActivity | None:
    """Traduce el token durable a la fase operacional, fail-closed.

    Un token ausente o fuera del conjunto cerrado es ``None`` (la UI declara
    «Sin dato todavía»), nunca una fase inventada. ``NO_ACTIVITY`` se conserva como
    valor válido y distinto de ``None``.
    """
    v = str(raw or "").strip().upper()
    mapping: dict[str, AutoActivity] = {
        "ANALYZING": "ANALYZING",
        "WAITING_SIGNAL": "WAITING_SIGNAL",
        "PREPARING_OPERATION": "PREPARING_OPERATION",
        "WAITING_EXECUTION": "WAITING_EXECUTION",
        "APPLYING_RESULT": "APPLYING_RESULT",
        "NO_ACTIVITY": "NO_ACTIVITY",
        "BLOCKED": "BLOCKED",
    }
    return mapping.get(v)


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
    activity: AutoActivity | None = None

    @property
    def last_reason_text(self) -> str:
        return _reason_text(self.last_reason)


@dataclass(frozen=True, slots=True)
class AutoEngineTickInput:
    """Payload de un ``run_tick`` que el store debe matricular una sola vez.

    ``seq`` = posición monotónica 1-based del tick en el run (== siguiente valor
    tras el último tick matriculado). ``proposals/vetoes/pending_plans`` son los
    TOTALES acumulados tras este tick (el store los sincroniza a la run).

    P7/P8 (auditoría .183): ``claim_tick_id`` convierte la escritura en la
    **liquidación** de un ciclo reclamado ANTES de ejecutarlo (ver
    ``claim_cycle``); sin él, el tick se matricula como siempre. ``lease_owner`` y
    ``lease_generation`` son la valla: si el lease ya no es de este proceso, el
    store se niega a escribir (``AutoEngineLeaseLost``) en vez de publicar el
    turno de un dueño que ya no conduce el motor.
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
    activity: AutoActivity | None = None
    #: ``tick_id`` del claim previo a la ejecución (``None`` = matrícula normal).
    claim_tick_id: str | None = None
    #: Valla del lease con el que se ejecutó el ciclo (``None`` = sin lease, legacy).
    lease_owner: str | None = None
    lease_generation: int | None = None


@dataclass(frozen=True, slots=True)
class AutoEngineLease:
    """Derecho EXCLUSIVO a conducir un ``engine_id`` (P7, migración 063).

    ``generation`` es monótona: cambia cada vez que OTRO proceso adquiere el lease
    (o este lo re-adquiere tras vencerse), y es lo que el tick presenta al escribir.
    """

    engine_id: str
    owner: str
    generation: int
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AutoEngineCycleClaim:
    """Reserva de la identidad del ciclo ANTES de ejecutar (P8, migración 063).

    ``tick_id`` identifica la fila del ledger (lleva la barra lógica y el ``seq``
    reservado) y ``seq`` es su posición. La reserva es DURABLE: si el proceso muere a
    mitad de turno, la fila queda con ``reason = cycle_claimed`` y el ciclo
    interrumpido es visible. La fila se COMPLETA al cerrar el turno.
    """

    engine_id: str
    tick_id: str
    seq: int
    logical_bar: str
    claimed_at: datetime


class AutoEngineLeaseLost(RuntimeError):
    """El ciclo intentó escribir sin poseer ya el lease (fence, P7)."""


class AutoEngineClaimLost(RuntimeError):
    """El ciclo intentó liquidar un claim que no existe (barrido/registro perdido)."""


#: P7 (auditoría .183) — TTL del lease del motor, en segundos. Default 180 s: tres
#: veces la cadencia de tick del scheduler (60 s), que es el margen con el que un tick
#: lento sigue dentro de su lease antes de que otro proceso pueda reclamarlo.
AUTO_ENGINE_LEASE_TTL_ENV = "AUTO_ENGINE_LEASE_TTL_SECONDS"
AUTO_ENGINE_LEASE_TTL_DEFAULT_SECONDS = 180.0


def lease_ttl_seconds(raw: str | None = None) -> float:
    """TTL del lease desde el entorno, fail-closed al default.

    Un valor ilegible o no positivo NO se convierte en «sin lease» ni en 0 (que haría
    el lease eternamente vencido y permitiría a cualquiera conducir): se declara el
    default y el llamante puede registrarlo.
    """
    value = raw if raw is not None else os.getenv(AUTO_ENGINE_LEASE_TTL_ENV)
    text = str(value or "").strip()
    if not text:
        return AUTO_ENGINE_LEASE_TTL_DEFAULT_SECONDS
    try:
        ttl = float(text)
    except ValueError:
        return AUTO_ENGINE_LEASE_TTL_DEFAULT_SECONDS
    if ttl <= 0:
        return AUTO_ENGINE_LEASE_TTL_DEFAULT_SECONDS
    return ttl


@runtime_checkable
class AutoEngineStore(Protocol):
    async def read(self, engine_id: str) -> AutoEngineSnapshot | None: ...

    async def record_tick(self, tick: AutoEngineTickInput) -> None: ...


@runtime_checkable
class AutoEngineLeaseStore(AutoEngineStore, Protocol):
    """Store que además arbitra el ownership entre procesos (P7) y el claim (P8)."""

    async def acquire_lease(
        self, engine_id: str, *, owner: str, ttl_seconds: float
    ) -> AutoEngineLease | None: ...

    async def renew_lease(
        self, lease: AutoEngineLease, *, ttl_seconds: float
    ) -> AutoEngineLease | None: ...

    async def release_lease(self, lease: AutoEngineLease) -> bool: ...

    async def claim_cycle(
        self, engine_id: str, *, logical_bar: str, lease: AutoEngineLease | None = None
    ) -> AutoEngineCycleClaim | None: ...


class InMemoryAutoEngineStore:
    """Test double: espeja la durabilidad por-engine del Postgres store.

    Guarda por ``engine_id`` el snapshot más reciente (totales monótonos) y una
    lista de ticks matriculados para poder contar (invariante no-doble-tick). Un
    crash/relaunch se simula ``read()`` de nuevo → readopta sin re-ejecutar tick.
    """

    def __init__(self) -> None:
        self._runs: dict[str, AutoEngineSnapshot] = {}
        self._max_seq: dict[str, int] = {}
        # P7/P8 — el doble también arbitra ownership y claim: así el seam del runtime se
        # puede probar sin PostgreSQL sin cambiar de semántica.
        self._leases: dict[str, AutoEngineLease] = {}
        self._claims: dict[str, AutoEngineCycleClaim] = {}
        # La generación NO se reinicia al soltar el lease: es la prueba de que hubo un
        # dueño anterior y lo que impide que un tick viejo vuelva a ser válido.
        self._lease_generation: dict[str, int] = {}
        self._clock: datetime | None = None

    def _now(self) -> datetime:
        return self._clock or datetime.now(UTC)

    def set_clock(self, now: datetime | None) -> None:
        """Fija el reloj del doble (para probar vencimiento de lease sin dormir)."""
        self._clock = now

    async def read(self, engine_id: str) -> AutoEngineSnapshot | None:
        return self._runs.get(engine_id)

    async def acquire_lease(
        self, engine_id: str, *, owner: str, ttl_seconds: float
    ) -> AutoEngineLease | None:
        now = self._now()
        current = self._leases.get(engine_id)
        if current is not None and current.owner != owner and current.expires_at > now:
            return None
        generation = self._lease_generation.get(engine_id, 0) + 1
        self._lease_generation[engine_id] = generation
        lease = AutoEngineLease(
            engine_id=engine_id,
            owner=owner,
            generation=generation,
            expires_at=now + timedelta(seconds=float(ttl_seconds)),
        )
        self._leases[engine_id] = lease
        return lease

    async def renew_lease(
        self, lease: AutoEngineLease, *, ttl_seconds: float
    ) -> AutoEngineLease | None:
        current = self._leases.get(lease.engine_id)
        if current is None or current.owner != lease.owner:
            return None
        if current.generation != lease.generation:
            return None
        renewed = AutoEngineLease(
            engine_id=lease.engine_id,
            owner=lease.owner,
            generation=lease.generation,
            expires_at=self._now() + timedelta(seconds=float(ttl_seconds)),
        )
        self._leases[lease.engine_id] = renewed
        return renewed

    async def release_lease(self, lease: AutoEngineLease) -> bool:
        current = self._leases.get(lease.engine_id)
        if current is None or current.owner != lease.owner:
            return False
        if current.generation != lease.generation:
            return False
        del self._leases[lease.engine_id]
        return True

    async def claim_cycle(
        self, engine_id: str, *, logical_bar: str, lease: AutoEngineLease | None = None
    ) -> AutoEngineCycleClaim | None:
        if lease is not None:
            current = self._leases.get(engine_id)
            if current is None or (current.owner, current.generation) != (
                lease.owner,
                lease.generation,
            ):
                return None
        bar = logical_bar or "sin-barra"
        seq = max(self._max_seq.get(engine_id, 0), *(c.seq for c in self._claims.values()), 0) + 1
        tick_id = f"cycle-{engine_id}-{bar}-{seq}"
        claim = AutoEngineCycleClaim(
            engine_id=engine_id,
            tick_id=tick_id,
            seq=seq,
            logical_bar=logical_bar,
            claimed_at=self._now(),
        )
        self._claims[tick_id] = claim
        return claim

    async def record_tick(self, tick: AutoEngineTickInput) -> None:
        if tick.lease_owner is not None:
            current = self._leases.get(tick.engine_id)
            if current is None or (current.owner, current.generation) != (
                tick.lease_owner,
                tick.lease_generation,
            ):
                raise AutoEngineLeaseLost(
                    "el lease del motor cambió de dueño: el ciclo ya no puede escribir "
                    f"(engine={tick.engine_id})"
                )
        max_seq = self._max_seq.get(tick.engine_id, 0)
        if tick.seq <= max_seq and not tick.claim_tick_id:
            # Re-registro de un tick ya matriculado → no avanza (no dobla).
            return
        if tick.claim_tick_id is not None and tick.claim_tick_id not in self._claims:
            raise AutoEngineClaimLost(
                f"el claim {tick.claim_tick_id} ya no existe (engine={tick.engine_id})"
            )
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
            activity=tick.activity,
        )

    def claimed_bars(self, engine_id: str) -> tuple[str, ...]:
        """Barras lógicas ya reclamadas (diagnóstico de claim único en tests)."""
        return tuple(
            claim.logical_bar
            for claim in self._claims.values()
            if claim.engine_id == engine_id
        )

    def recorded_seq_max(self, engine_id: str) -> int:
        """Último ``seq`` matriculado (diagnóstico de no-doble en tests)."""
        return self._max_seq.get(engine_id, 0)


class PostgresAutoEngineStore:
    """``auto_engine_runs`` + ``auto_engine_ticks`` en PostgreSQL (Alembic 027).

    ``read`` relee la fila-run (+ cuenta de ticks). ``record_tick`` matricula la
    fila de tick (INGEST) y sincroniza el acumulado de la run; si el tick ya está
    matriculado —``seq`` repetido (UNIQUE ``auto_engine_ticks_engine_seq_uidx``) **o**
    ``tick_id`` repetido (PK ``auto_engine_ticks_pkey``, función de ``(engine_id, seq)``)—,
    el tick se omite (no-doble) y la run no avanza. El commit único hace la operación
    atómica entre tick y run.
    """

    def __init__(self, session: Any) -> None:
        self._session = session

    def _now(self) -> datetime:
        return datetime.now(UTC)

    # ---- P7: lease de ownership entre procesos (migración 063) ------------------

    async def acquire_lease(
        self, engine_id: str, *, owner: str, ttl_seconds: float
    ) -> AutoEngineLease | None:
        """Adquiere el lease SOLO si está libre o vencido (CAS atómico).

        ``UPDATE ... WHERE lease_owner IS NULL OR lease_expires_at <= now()`` en una
        sola sentencia: no hay ventana entre «leer si está libre» y «escribir mi
        dueño» (un ``SELECT`` seguido de ``UPDATE`` sí la tendría, y es exactamente lo
        que deja a dos procesos conduciendo el mismo motor). Devuelve ``None`` cuando
        otro proceso lo posee y está vigente: el llamante NO ejecuta el ciclo.
        """
        import sqlalchemy as sa
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import AutoEngineRunRow

        now = self._now()
        expires = now + timedelta(seconds=float(ttl_seconds))
        # La fila-run puede no existir todavía (primer arranque): se crea vacía en
        # PAUSED. No inventa contadores ni ticks; solo da soporte al lease.
        await self._session.execute(
            pg_insert(AutoEngineRunRow)
            .values(
                engine_id=engine_id,
                venue="paper",
                state="PAUSED",
                lease_generation=0,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=[AutoEngineRunRow.engine_id])
        )
        acquired = await self._session.execute(
            sa.update(AutoEngineRunRow)
            .where(
                AutoEngineRunRow.engine_id == engine_id,
                sa.or_(
                    AutoEngineRunRow.lease_owner.is_(None),
                    AutoEngineRunRow.lease_expires_at.is_(None),
                    AutoEngineRunRow.lease_expires_at <= now,
                ),
            )
            .values(
                lease_owner=owner,
                lease_generation=AutoEngineRunRow.lease_generation + 1,
                lease_expires_at=expires,
                updated_at=now,
            )
            .returning(AutoEngineRunRow.lease_generation, AutoEngineRunRow.lease_expires_at)
        )
        row = acquired.one_or_none()
        if row is None:
            # Otro proceso conduce el motor: se cierra la transacción para no dejar
            # abierta la del insert (una sesión por tick).
            await self._session.commit()
            return None
        await self._session.commit()
        return AutoEngineLease(
            engine_id=engine_id,
            owner=owner,
            generation=int(row[0]),
            expires_at=row[1] or expires,
        )

    async def renew_lease(
        self, lease: AutoEngineLease, *, ttl_seconds: float
    ) -> AutoEngineLease | None:
        """Extiende el lease SI sigue siendo de este dueño y generación.

        ``None`` ⇒ el lease fue robado (o soltado): el llamante no debe ejecutar. La
        generación NO cambia al renovar: renovar es seguir siendo el mismo dueño.
        """
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import AutoEngineRunRow

        now = self._now()
        expires = now + timedelta(seconds=float(ttl_seconds))
        renewed = await self._session.execute(
            sa.update(AutoEngineRunRow)
            .where(
                AutoEngineRunRow.engine_id == lease.engine_id,
                AutoEngineRunRow.lease_owner == lease.owner,
                AutoEngineRunRow.lease_generation == lease.generation,
            )
            .values(lease_expires_at=expires, updated_at=now)
            .returning(AutoEngineRunRow.lease_expires_at)
        )
        row = renewed.one_or_none()
        await self._session.commit()
        if row is None:
            return None
        return AutoEngineLease(
            engine_id=lease.engine_id,
            owner=lease.owner,
            generation=lease.generation,
            expires_at=row[0] or expires,
        )

    async def release_lease(self, lease: AutoEngineLease) -> bool:
        """Suelta el lease (``lease_owner = NULL``) sin tocar la generación.

        La generación no vuelve atrás: es la prueba de que hubo un dueño anterior, y
        reiniciarla convertiría un tick viejo en válido (la valla dejaría de vallar).
        """
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import AutoEngineRunRow

        result = await self._session.execute(
            sa.update(AutoEngineRunRow)
            .where(
                AutoEngineRunRow.engine_id == lease.engine_id,
                AutoEngineRunRow.lease_owner == lease.owner,
                AutoEngineRunRow.lease_generation == lease.generation,
            )
            .values(lease_owner=None, lease_expires_at=None, updated_at=self._now())
        )
        await self._session.commit()
        return bool(getattr(result, "rowcount", 0))

    # ---- P8: claim de la barra lógica ANTES de ejecutar ------------------------

    async def claim_cycle(
        self, engine_id: str, *, logical_bar: str, lease: AutoEngineLease | None = None
    ) -> AutoEngineCycleClaim | None:
        """Reserva la identidad del ciclo en el ledger ANTES de ejecutarlo (P8).

        El ``seq`` se reserva con ``MAX(seq)+1`` y la fila se inserta con
        ``tick_id = cycle-<engine>-<bar>-<seq>``; el UNIQUE ``(engine_id, seq)`` es el
        árbitro: si otra sesión se llevó ese ``seq`` entre el cálculo y el INSERT, el
        ``ON CONFLICT DO NOTHING`` no devuelve fila y se reintenta con el siguiente.
        La fila queda durable con ``reason = cycle_claimed`` aunque el proceso muera a
        mitad de turno: un ciclo interrumpido deja traza en vez de desaparecer.

        **Por qué la clave NO es ``(engine, barra)`` a secas** (desvío declarado de la
        auditoría .183, medido): el reloj de DECISIÓN del motor es ``1d`` por defecto y
        el turno se ejecuta muchas veces dentro de la MISMA barra —gestión de posición,
        protección, trailing, salidas—. Bloquear por barra detendría el motor el resto
        del día tras el primer turno. La idempotencia del CICLO la garantizan el lease
        (P7: un solo dueño ejecutando) y los guardas durables ya existentes (señales
        consumidas, posición readoptada, reservas); aquí se cierra la carrera del
        ledger, que era el fallo concreto descrito: ``seq`` se asignaba DESPUÉS de
        ejecutar, así que dos turnos podían ejecutar y solo uno matricularse.

        ``lease`` es opcional: con él se exige seguir siendo el dueño en el instante
        de reclamar (defensa extra sobre el fence de escritura).
        """
        import sqlalchemy as sa
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import AutoEngineTickRow

        if lease is not None and not await self._holds_lease(lease):
            return None
        now = self._now()
        bar = logical_bar or "sin-barra"
        for _ in range(3):
            seq = await self._session.scalar(
                sa.select(sa.func.coalesce(sa.func.max(AutoEngineTickRow.seq), 0) + 1).where(
                    AutoEngineTickRow.engine_id == engine_id
                )
            )
            next_seq = int(seq or 1)
            tick_id = f"cycle-{engine_id}-{bar}-{next_seq}"
            inserted = await self._session.execute(
                pg_insert(AutoEngineTickRow)
                .values(
                    tick_id=tick_id,
                    engine_id=engine_id,
                    seq=next_seq,
                    state="RUNNING",
                    proposals=0,
                    vetoes=0,
                    pending_plans=0,
                    reason="cycle_claimed",
                    activity=None,
                    tick_at=now,
                    created_at=now,
                )
                .on_conflict_do_nothing()
                .returning(AutoEngineTickRow.seq)
            )
            if inserted.scalar_one_or_none() is not None:
                # DURABLE ANTES DE EJECUTAR: si el turno muere a mitad, el claim ya está
                # confirmado y deja la traza del ciclo interrumpido (si no, el INSERT se
                # perdería con el rollback de la sesión y P8 seguiría abierto).
                await self._session.commit()
                return AutoEngineCycleClaim(
                    engine_id=engine_id,
                    tick_id=tick_id,
                    seq=next_seq,
                    logical_bar=logical_bar,
                    claimed_at=now,
                )
            # Otro proceso se llevó ese ``seq``: reintentar con el siguiente.
            await self._session.rollback()
        return None

    async def _holds_lease(self, lease: AutoEngineLease) -> bool:
        """¿Sigue este proceso siendo el dueño vigente del lease?"""
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import AutoEngineRunRow

        row = (
            await self._session.execute(
                sa.select(AutoEngineRunRow.lease_owner, AutoEngineRunRow.lease_generation)
                .where(AutoEngineRunRow.engine_id == lease.engine_id)
            )
        ).one_or_none()
        if row is None:
            return False
        return row[0] == lease.owner and int(row[1] or 0) == int(lease.generation)

    async def _assert_lease(self, tick: AutoEngineTickInput) -> None:
        """Valla (fence) de la escritura: el tick debe presentar el lease VIGENTE.

        Se lee la fila-run ``FOR UPDATE`` para que la comprobación y el UPDATE que
        viene después ocurran en la MISMA transacción: entre «¿sigo siendo el dueño?»
        y «escribo» no cabe una adquisición ajena, que es justo el interleaving que
        producía dos turnos escribiendo el mismo ledger.
        """
        if tick.lease_owner is None:
            return
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import AutoEngineRunRow

        row = (
            await self._session.execute(
                sa.select(AutoEngineRunRow.lease_owner, AutoEngineRunRow.lease_generation)
                .where(AutoEngineRunRow.engine_id == tick.engine_id)
                .with_for_update()
            )
        ).one_or_none()
        if row is None:
            return
        owner, generation = row
        if owner != tick.lease_owner or int(generation or 0) != int(tick.lease_generation or 0):
            raise AutoEngineLeaseLost(
                "el lease del motor cambió de dueño: el ciclo ya no puede escribir "
                f"(engine={tick.engine_id} owner={tick.lease_owner} "
                f"generation={tick.lease_generation} vigente={owner}/{generation})"
            )

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
            activity=_activity_of(row.activity),
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
        import sqlalchemy as sa
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import (
            AutoEngineRunRow,
            AutoEngineTickRow,
        )

        now = self._now()
        occurred = tick.occurred_at or now
        # 0) P7 — valla del lease ANTES de tocar el ledger: si el motor cambió de dueño,
        # este ciclo no publica nada. La comprobación toma la fila-run ``FOR UPDATE``, así
        # que ningún otro proceso puede adquirir el lease entre la comprobación y el
        # UPDATE que sigue.
        if tick.lease_owner is not None:
            await self._assert_lease(tick)
        if tick.claim_tick_id:
            # P8 — el ciclo fue RECLAMADO antes de ejecutarse: se LIQUIDA esa misma fila
            # (misma identidad, mismo ``seq``), no se matricula una nueva. Si el claim ya
            # no existe (barrido) se declara y NO se escribe la run: un turno sin su
            # reclamación no es representable sin inventar historia.
            settled = await self._session.execute(
                sa.update(AutoEngineTickRow)
                .where(
                    AutoEngineTickRow.tick_id == tick.claim_tick_id,
                    AutoEngineTickRow.engine_id == tick.engine_id,
                )
                .values(
                    state=tick.state,
                    proposals=int(tick.proposals),
                    vetoes=int(tick.vetoes),
                    pending_plans=int(tick.pending_plans),
                    reason=_reason_text(tick.last_reason),
                    activity=tick.activity,
                    tick_at=occurred,
                )
                .returning(AutoEngineTickRow.tick_id)
            )
            if settled.scalar_one_or_none() is None:
                await self._session.rollback()
                raise AutoEngineClaimLost(
                    f"el claim {tick.claim_tick_id} ya no existe: no se liquida el ciclo "
                    f"(engine={tick.engine_id})"
                )
        else:
            # 1) Matricular la fila de tick exactamente una vez (UNIQUE engine+seq).
            # V2.23/A9 (Bloque 5, P2): el "intento de matrícula" va en un SAVEPOINT para
            # que un tick ya matriculado (crash/re-registro) NO arrastre con un rollback
            # de sesión el trabajo previo pendiente del MISMO tick (p.ej. la captura de
            # ``execution_events`` que el scheduler hizo sobre esta misma sesión). El
            # savepoint aísla SOLO la inserción duplicada; el resto de la transacción
            # queda intacto.
            #
            # OBS-21 — el árbitro NO se nombra y la omisión se lee por ``RETURNING``.
            # Medido en la certificación concurrente (5 sesiones ``AsyncSession`` sobre la
            # MISMA ``engine_id``/``seq``): con ``on_conflict_do_nothing(constraint=...)``
            # el árbitro era SOLO el índice nombrado, y la carrera moría con
            # ``UniqueViolation`` del PK (``auto_engine_ticks_pkey``) en 2 de 5 sesiones
            # —el PK es otro índice y ``tick_id`` es función de ``(engine_id, seq)``, así
            # que la clave repetida es la MISMA—. Sin árbitro, ``ON CONFLICT DO NOTHING``
            # cubre todos los índices únicos usables: la matrícula es idempotente por
            # ``seq`` o por ``tick_id`` y nunca revienta el tick. Además ``rowcount`` se
            # midió inútil aquí (``-1`` en las 125 inserciones de la sonda, ganadas y
            # omitidas: el guardián ``== 0`` era código muerto), así que la omisión se
            # lee del ``RETURNING``: sin fila devuelta, el tick ya estaba matriculado.
            async with self._session.begin_nested() as _sp:
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
                        activity=tick.activity,
                        tick_at=occurred,
                        created_at=now,
                    )
                    .on_conflict_do_nothing()
                    .returning(AutoEngineTickRow.tick_id)
                )
                if inserted.scalar_one_or_none() is None:
                    # Tick ya matriculado (crash/re-registro) → no avanzar la run (no
                    # dobla) y deshace SOLO el savepoint (la transacción externa y su
                    # trabajo previo —p.ej. la captura de execution_events del tick—
                    # quedan intactos).
                    await _sp.rollback()
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
                activity=tick.activity,
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
                    "activity": tick.activity,
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
    activity: AutoActivity | None = None,
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
        activity=activity,
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
