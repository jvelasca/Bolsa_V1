"""P7/P8 (auditoría .183) — lease entre procesos y claim de la barra lógica, SIN PostgreSQL.

Cierra, con evidencia ejecutable y sin base de datos, las dos propiedades que la auditoría
dejó abiertas en el motor AUTO:

* **P7 — un solo dueño por motor entre PROCESOS.** El ``asyncio.Lock`` del runtime sólo
  serializa dentro de un proceso. El store durable arbitra con
  ``acquire/renew/release_lease`` + ``lease_generation`` (valla monótona): dos dueños no
  coexisten, el lease vencido se puede reclamar y el dueño anterior NO puede escribir
  después (``AutoEngineLeaseLost``).
* **P8 — una barra lógica se conduce UNA vez.** ``claim_cycle`` reserva la barra en el
  ledger antes de ejecutar: el segundo proceso sobre la MISMA barra no recibe claim y no
  ejecuta. Al cerrar, el turno liquidación esa fila (mismo ``seq``), de modo que reclamar
  y cerrar cuentan UN tick, no dos.

El doble ``InMemoryAutoEngineStore`` implementa la MISMA semántica que el store Postgres
(ver ``test_auto_p7_lease_claim_pg.py`` para la certificación contra la base real). Aquí se
mide además el seam del runtime: cuándo deja de ejecutar y cuándo readopta la posición.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from bolsa_application.auto_engine_state_store import (
    AutoEngineLeaseLost,
    AutoEngineTickInput,
    InMemoryAutoEngineStore,
)

_ENGINE = "auto-sim-p7"
_T0 = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)
_BAR = "2026-11-04T08:30:00+00:00"
_TTL = 180.0


def _tick(
    *,
    seq: int,
    claim_tick_id: str | None = None,
    lease: Any = None,
    proposals: int = 0,
) -> AutoEngineTickInput:
    return AutoEngineTickInput(
        engine_id=_ENGINE,
        venue="paper",
        state="RUNNING",
        seq=seq,
        proposals=proposals,
        vetoes=0,
        pending_plans=0,
        last_reason=("idle",),
        occurred_at=_T0,
        claim_tick_id=claim_tick_id,
        lease_owner=(lease.owner if lease is not None else None),
        lease_generation=(lease.generation if lease is not None else None),
    )


# ── P7 · un solo dueño por motor entre procesos ───────────────────────────────


@pytest.mark.asyncio
async def test_two_processes_never_hold_the_motor_lease_at_the_same_time() -> None:
    """A adquiere; B NO puede mientras el lease de A esté vivo (y se le dice: ``None``)."""
    store = InMemoryAutoEngineStore()
    store.set_clock(_T0)

    lease_a = await store.acquire_lease(_ENGINE, owner="proc-a", ttl_seconds=_TTL)
    assert lease_a is not None and lease_a.owner == "proc-a" and lease_a.generation == 1

    lease_b = await store.acquire_lease(_ENGINE, owner="proc-b", ttl_seconds=_TTL)
    assert lease_b is None, "dos procesos no pueden conducir el mismo motor a la vez"

    renewed = await store.renew_lease(lease_a, ttl_seconds=_TTL)
    assert renewed is not None
    assert renewed.generation == lease_a.generation, (
        "renovar es seguir siendo el mismo dueño: la generación no cambia"
    )


@pytest.mark.asyncio
async def test_an_expired_lease_can_be_stolen_and_bumps_the_generation() -> None:
    """Vencido el TTL, B adquiere y la generación avanza: A deja de ser el dueño."""
    store = InMemoryAutoEngineStore()
    store.set_clock(_T0)

    lease_a = await store.acquire_lease(_ENGINE, owner="proc-a", ttl_seconds=_TTL)
    assert lease_a is not None

    store.set_clock(_T0 + timedelta(seconds=_TTL + 1))
    lease_b = await store.acquire_lease(_ENGINE, owner="proc-b", ttl_seconds=_TTL)
    assert lease_b is not None and lease_b.owner == "proc-b"
    assert lease_b.generation == lease_a.generation + 1, (
        "cada adquisición incrementa la generación: es la valla del dueño anterior"
    )
    assert await store.renew_lease(lease_a, ttl_seconds=_TTL) is None, (
        "el dueño anterior ya no puede renovar"
    )


@pytest.mark.asyncio
async def test_the_previous_owner_cannot_write_after_the_lease_moved() -> None:
    """La valla rechaza el tick de A cuando B ya conduce: no se publica el turno ajeno."""
    store = InMemoryAutoEngineStore()
    store.set_clock(_T0)

    lease_a = await store.acquire_lease(_ENGINE, owner="proc-a", ttl_seconds=_TTL)
    assert lease_a is not None
    store.set_clock(_T0 + timedelta(seconds=_TTL + 1))
    lease_b = await store.acquire_lease(_ENGINE, owner="proc-b", ttl_seconds=_TTL)
    assert lease_b is not None

    with pytest.raises(AutoEngineLeaseLost):
        await store.record_tick(_tick(seq=1, lease=lease_a))

    await store.record_tick(_tick(seq=1, lease=lease_b))
    snapshot = await store.read(_ENGINE)
    assert snapshot is not None and snapshot.ticks == 1


@pytest.mark.asyncio
async def test_the_released_lease_leaves_the_motor_free_without_rewinding_the_generation() -> None:
    """Soltar el lease libera el motor, pero la generación NO vuelve atrás (la valla sigue)."""
    store = InMemoryAutoEngineStore()
    store.set_clock(_T0)

    lease_a = await store.acquire_lease(_ENGINE, owner="proc-a", ttl_seconds=_TTL)
    assert lease_a is not None
    assert await store.release_lease(lease_a) is True

    store.set_clock(_T0 + timedelta(seconds=1))
    lease_b = await store.acquire_lease(_ENGINE, owner="proc-b", ttl_seconds=_TTL)
    assert lease_b is not None
    assert lease_b.generation == lease_a.generation + 1
    assert await store.renew_lease(lease_a, ttl_seconds=_TTL) is None


# ── P8 · reserva de la identidad del ciclo (barra + seq) antes de ejecutar ────


@pytest.mark.asyncio
async def test_the_claim_reserves_the_ledger_identity_before_the_work() -> None:
    """El claim existe ANTES de ejecutar: `seq` y `tick_id` quedan fijados (no al cerrar)."""
    store = InMemoryAutoEngineStore()
    store.set_clock(_T0)
    lease = await store.acquire_lease(_ENGINE, owner="proc-a", ttl_seconds=_TTL)

    claim = await store.claim_cycle(_ENGINE, logical_bar=_BAR, lease=lease)

    assert claim is not None
    assert claim.seq == 1
    assert claim.logical_bar == _BAR
    assert claim.tick_id == f"cycle-{_ENGINE}-{_BAR}-1"
    assert await store.read(_ENGINE) is None, (
        "el claim NO publica un turno: el ledger del run sigue sin tick cerrado"
    )


@pytest.mark.asyncio
async def test_two_claims_never_share_the_reserved_seq() -> None:
    """Dos turnos de la MISMA barra reservan secuencias distintas (la carrera del ledger)."""

    store = InMemoryAutoEngineStore()
    store.set_clock(_T0)
    lease = await store.acquire_lease(_ENGINE, owner="proc-a", ttl_seconds=_TTL)

    first = await store.claim_cycle(_ENGINE, logical_bar=_BAR, lease=lease)
    second = await store.claim_cycle(_ENGINE, logical_bar=_BAR, lease=lease)

    assert first is not None and second is not None
    assert second.seq == first.seq + 1, (
        "la misma barra puede tener varios turnos (gestión de posición), pero NUNCA "
        "el mismo seq: eso es lo que se asignaba después de ejecutar y se perdía"
    )
    assert first.tick_id != second.tick_id


@pytest.mark.asyncio
async def test_closing_a_claim_settles_it_as_ONE_tick_not_two() -> None:
    """Reclamar + cerrar deja UN tick en el ledger (mismo ``seq``), no un tick y medio."""
    store = InMemoryAutoEngineStore()
    store.set_clock(_T0)
    lease = await store.acquire_lease(_ENGINE, owner="proc-a", ttl_seconds=_TTL)
    claim = await store.claim_cycle(_ENGINE, logical_bar=_BAR, lease=lease)
    assert claim is not None

    await store.record_tick(
        _tick(seq=claim.seq, claim_tick_id=claim.tick_id, lease=lease, proposals=3)
    )
    snapshot = await store.read(_ENGINE)
    assert snapshot is not None
    assert snapshot.ticks == claim.seq == 1
    assert snapshot.proposals == 3

    # Reintentar el cierre (crash tras liquidar) no dobla ni rompe: se re-liquida el claim.
    await store.record_tick(
        _tick(seq=claim.seq, claim_tick_id=claim.tick_id, lease=lease, proposals=3)
    )
    again = await store.read(_ENGINE)
    assert again is not None and again.ticks == 1


@pytest.mark.asyncio
async def test_a_claim_is_refused_when_the_lease_belongs_to_somebody_else() -> None:
    """Reservar exige ser el dueño: un proceso sin lease vigente no reclama ciclos."""
    store = InMemoryAutoEngineStore()
    store.set_clock(_T0)
    lease_a = await store.acquire_lease(_ENGINE, owner="proc-a", ttl_seconds=_TTL)
    assert lease_a is not None

    store.set_clock(_T0 + timedelta(seconds=_TTL + 1))
    lease_b = await store.acquire_lease(_ENGINE, owner="proc-b", ttl_seconds=_TTL)
    assert lease_b is not None

    assert await store.claim_cycle(_ENGINE, logical_bar=_BAR, lease=lease_a) is None
    assert await store.claim_cycle(_ENGINE, logical_bar=_BAR, lease=lease_b) is not None


# ── El seam del RUNTIME: no ejecutar sin lease y readoptar al cambiar de generación ──


class _WorkerSpy:
    """Doble mínimo: registra si el runtime exigió readoptar la posición."""

    def __init__(self) -> None:
        self.readopts = 0

    def require_position_readopt(self) -> None:
        self.readopts += 1


def _runtime(*, worker: _WorkerSpy, ttl: float = _TTL) -> Any:
    from bolsa_api.background.auto_simulation_worker import AutoSimRuntime

    return AutoSimRuntime(
        session_factory=None,
        worker=worker,
        engine_id=_ENGINE,
        account_id="acc-p7",
        lease_ttl_seconds=ttl,
    )


@pytest.mark.asyncio
async def test_the_runtime_refuses_to_run_when_another_process_holds_the_lease() -> None:
    """El proceso B no adquiere lease ⇒ ``_hold_lease`` devuelve ``None`` (no hay ciclo)."""
    store = InMemoryAutoEngineStore()
    store.set_clock(_T0)
    owner = await store.acquire_lease(_ENGINE, owner="proc-a", ttl_seconds=_TTL)
    assert owner is not None

    runtime_b = _runtime(worker=_WorkerSpy())
    assert await runtime_b._hold_lease(store) is None  # noqa: SLF001 — seam interno medido.
    assert runtime_b._lease is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_the_runtime_readopts_the_position_when_the_lease_generation_moves() -> None:
    """Lease robado tras vencer ⇒ al recuperarlo, ``_open`` se reconstruye del espejo."""
    store = InMemoryAutoEngineStore()
    store.set_clock(_T0)
    worker = _WorkerSpy()
    runtime = _runtime(worker=worker)

    first = await runtime._hold_lease(store)  # noqa: SLF001
    assert first is not None and worker.readopts == 0, (
        "el primer lease de un proceso no exige readoptar: el turno ya readopta al arrancar"
    )

    # El lease vence y OTRO proceso lo toma; al volver, este proceso adquiere otra generación.
    store.set_clock(_T0 + timedelta(seconds=_TTL + 1))
    stolen = await store.acquire_lease(_ENGINE, owner="proc-b", ttl_seconds=_TTL)
    assert stolen is not None

    store.set_clock(_T0 + timedelta(seconds=2 * _TTL + 2))
    recovered = await runtime._hold_lease(store)  # noqa: SLF001
    assert recovered is not None
    assert recovered.generation > first.generation
    assert worker.readopts == 1, (
        "con la generación cambiada, la RAM dejó de ser la verdad: hay que readoptar"
    )
