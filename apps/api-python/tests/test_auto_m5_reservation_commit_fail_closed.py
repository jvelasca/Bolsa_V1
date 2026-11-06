"""M5/M6 — el compromiso que no es durable no se declara, y la evidencia no se pierde.

Cierra las dos mitades que la auditoría `.183` dejó abiertas y que el commit previo solo
cubría a medias:

* **M5** — un ``commit()`` fallido ya vetaba la emisión (fail-closed), pero la sesión se
  registraba como DUEÑA de las reservas y publicaba sus claims como ganados **antes** de
  saber si eran durables: el journal afirmaba la propiedad de un capital que no estaba
  reservado y el cierre de turno intentaba retirar una reserva inexistente.
* **M6** — los eventos cuyo sink falla se reencolan acotados por
  ``_POSITION_JOURNAL_RETRY_CAP``; el certificado cubre que el tope descarta los MÁS
  ANTIGUOS y que los conservados se publican al recuperarse el sink.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.portfolio_reservation import build_reservation
from bolsa_api.background import auto_simulation_worker as worker_module
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.reservation_store import InMemoryReservationStore

_ACCOUNT = "acc-m5"


def _reservation(instrument_id: str) -> Any:
    return build_reservation(
        reservation_id=f"RES-dec-{instrument_id.lower()}",
        account_id=_ACCOUNT,
        tick_id="2026-11-05T09:00:00Z",
        instrument_id=instrument_id,
        side="buy",
        quantity=100.0,
        entry=10.0,
        sector="tech",
        reserved_cash=1000.0,
        reserved_risk=20.0,
        created_at="2026-11-05T09:00:00Z",
    )


def _worker(**kwargs: Any) -> AutoSimulationWorker:
    return AutoSimulationWorker(
        clock=lambda: datetime(2026, 11, 5, 9, 0, tzinfo=UTC),
        account_id=_ACCOUNT,
        **kwargs,
    )


class _FailingCommitStore(InMemoryReservationStore):
    """Store que acepta el claim pero no puede confirmarlo (commit fallido)."""

    async def commit(self) -> None:
        raise RuntimeError("commit failed")


class _LostClaimStore(InMemoryReservationStore):
    """Store con un compromiso VIVO previo de la MISMA identidad: la carrera se pierde."""

    async def save_claim(self, reservation: Any) -> bool:
        return False


# ── M5: commit fallido ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_failed_commit_vetoes_the_instrument() -> None:
    """Sin commit no hay compromiso: la entrada de ese instrumento NO se emite."""
    worker = _worker(reservation_store=_FailingCommitStore())

    await worker._v2_persist_tick_reservations(SimpleNamespace(reservations=(_reservation("AAA"),)))

    assert worker._v2_reservation_blocked == frozenset({"AAA"})
    assert worker._v2_reservations == (), "lo no confirmado no queda como reserva viva"


@pytest.mark.asyncio
async def test_failed_commit_does_not_claim_ownership() -> None:
    """M5: la propiedad de una reserva solo existe si la reserva existe.

    Antes se registraba junto al claim GANADO (antes del commit), así que el cierre de
    turno intentaba retirar una reserva que nunca se escribió.
    """
    worker = _worker(reservation_store=_FailingCommitStore())

    await worker._v2_persist_tick_reservations(SimpleNamespace(reservations=(_reservation("AAA"),)))

    assert worker._v2_owned_reservations == frozenset()


@pytest.mark.asyncio
async def test_failed_commit_does_not_publish_a_won_claim() -> None:
    """M5: el journal no puede afirmar un claim sobre capital no reservado."""
    published: list[Any] = []

    async def sink(entry: Any) -> None:
        published.append(entry)

    worker = _worker(reservation_store=_FailingCommitStore(), operational_audit_sink=sink)

    await worker._v2_persist_tick_reservations(SimpleNamespace(reservations=(_reservation("AAA"),)))

    claims = [e for e in published if (e.payload or {}).get("event") == "auto_reservation_claim"]
    assert claims == [], "un claim ganado sin commit no es un hecho durable"


@pytest.mark.asyncio
async def test_failed_commit_still_publishes_lost_claims() -> None:
    """Las carreras PERDIDAS ocurrieron antes del commit: se publican igual."""

    class _LostThenBroken(InMemoryReservationStore):
        async def save_claim(self, reservation: Any) -> bool:
            return False

        async def commit(self) -> None:
            raise RuntimeError("commit failed")

    published: list[Any] = []

    async def sink(entry: Any) -> None:
        published.append(entry)

    worker = _worker(
        reservation_store=_LostThenBroken(),
        operational_audit_sink=sink,
    )

    await worker._v2_persist_tick_reservations(SimpleNamespace(reservations=(_reservation("AAA"),)))

    claims = [e for e in published if (e.payload or {}).get("event") == "auto_reservation_claim"]
    assert [c.payload["claimed"] for c in claims] == [False]


@pytest.mark.asyncio
async def test_winning_a_lost_claim_is_declared_without_ownership() -> None:
    """La carrera perdida veta por ``reservation_already_live`` y no da propiedad."""
    published: list[Any] = []

    async def sink(entry: Any) -> None:
        published.append(entry)

    worker = _worker(reservation_store=_LostClaimStore(), operational_audit_sink=sink)

    await worker._v2_persist_tick_reservations(SimpleNamespace(reservations=(_reservation("AAA"),)))

    assert worker._v2_reservation_blocked == frozenset()
    assert worker._v2_reservation_carryover == frozenset({"AAA"})
    assert worker._v2_owned_reservations == frozenset()
    claims = [e for e in published if (e.payload or {}).get("event") == "auto_reservation_claim"]
    assert [c.payload["claimed"] for c in claims] == [False]


@pytest.mark.asyncio
async def test_successful_commit_registers_ownership_and_claim() -> None:
    """Contraprueba: con commit bueno la sesión SÍ es dueña y el claim se publica."""
    published: list[Any] = []

    async def sink(entry: Any) -> None:
        published.append(entry)

    worker = _worker(
        reservation_store=InMemoryReservationStore(),
        operational_audit_sink=sink,
    )

    await worker._v2_persist_tick_reservations(SimpleNamespace(reservations=(_reservation("AAA"),)))

    assert worker._v2_owned_reservations == frozenset({"RES-dec-aaa"})
    assert [row.reservation_id for row in worker._v2_reservations] == ["RES-dec-aaa"]
    claims = [e for e in published if (e.payload or {}).get("event") == "auto_reservation_claim"]
    assert [c.payload["claimed"] for c in claims] == [True]


# ── M6: cola de journal acotada ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_journal_retry_cap_discards_the_oldest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El tope conserva lo MÁS RECIENTE: perder lo viejo es preferible a crecer sin límite."""
    monkeypatch.setattr(worker_module, "_POSITION_JOURNAL_RETRY_CAP", 2)
    worker = _worker(operational_audit_sink=lambda entry: _boom())
    worker._v2_seal_audit_identity = lambda e: e  # type: ignore[method-assign]

    worker._v2_position_journal_pending = ["e1", "e2", "e3", "e4", "e5"]

    await worker._v2_flush_position_journal()

    assert worker._v2_position_journal_pending == ["e4", "e5"]


async def _boom() -> None:
    raise RuntimeError("sink down")


@pytest.mark.asyncio
async def test_requeued_events_are_published_when_the_sink_recovers() -> None:
    """Un fallo transitorio del sink no pierde la evidencia: se publica en el turno siguiente."""
    delivered: list[Any] = []
    failing = {"on": True}

    async def sink(entry: Any) -> None:
        if failing["on"]:
            raise RuntimeError("sink down")
        delivered.append(entry)

    worker = _worker(operational_audit_sink=sink)
    worker._v2_seal_audit_identity = lambda e: e  # type: ignore[method-assign]
    worker._v2_position_journal_pending = ["a", "b"]

    await worker._v2_flush_position_journal()
    assert worker._v2_position_journal_pending == ["a", "b"]

    failing["on"] = False
    await worker._v2_flush_position_journal()

    assert delivered == ["a", "b"], "se conserva el orden en que ocurrieron"
    assert worker._v2_position_journal_pending == []
