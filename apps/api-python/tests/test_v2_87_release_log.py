"""V2.87 · AUTO-MATERIAL-19 — el log de retiradas del harness publica el MOTIVO.

Por qué existe este fichero
---------------------------

El instrumento cuenta ``byDeadTail`` leyendo el MOTIVO de cada retirada
(``tail_dead`` = cola de un fill parcial cuya orden ya no estaba en vuelo, el defecto de
``OBS-18``). El primer corte de esa instrumentación registraba estado, instrumento y
instante… pero **no** el motivo: el artefacto publicaba ``byDeadTail: 0`` sobre 64 retiradas.

Ese cero no era una medición, era un HUECO: «no medí el motivo» leído como «ninguna retirada
fue una cola muerta». Esta suite fija el contrato que lo hace imposible — **el motivo que el
libro resuelve viaja al log**, o el conteo no es evidencia.
"""

from __future__ import annotations

import importlib.util
import pathlib
from typing import Any

import pytest

from bolsa_analytics.cognitive.portfolio_reservation import (
    RELEASE_REASON_DEAD_TAIL,
    RESERVATION_RELEASED_BY_CANCEL,
    build_reservation,
)
from bolsa_application.replay_oos import count_release_reasons, tally_releases

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_V87_SCRIPT = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_87_replay_oos_durable_cycle.py"


def _load_v87() -> Any:
    """Carga el orquestador por ruta (no es un módulo instalable)."""
    spec = importlib.util.spec_from_file_location("v2_87_replay_oos_durable_cycle_log", _V87_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reservation(reservation_id: str = "RES-TAIL"):
    """Reserva VIVA (compra) con identidad y dimensiones declaradas."""
    return build_reservation(
        reservation_id=reservation_id,
        instrument_id="AAA",
        quantity=100.0,
        side="buy",
        account_id="acc-release-log",
        tick_id="2026-01-02T00:00:00Z",
        sector="TECH",
        entry=100.0,
        stop=95.0,
        reserved_cash=1000.0,
        reserved_risk=20.0,
        created_at="2026-01-02T00:00:00Z",
    )


async def _store_with_live(reservation_id: str = "RES-TAIL") -> Any:
    store = _load_v87()._AccountingReservationStore()
    await store.save(_reservation(reservation_id))
    return store


@pytest.mark.asyncio
async def test_release_log_records_the_reason_the_book_resolved() -> None:
    """La retirada de una cola muerta queda en el log con su motivo, no solo con su estado."""
    store = await _store_with_live()

    row = await store.release(
        "RES-TAIL",
        status=RESERVATION_RELEASED_BY_CANCEL,
        reason=RELEASE_REASON_DEAD_TAIL,
    )

    assert row is not None and row.is_live is False
    (entry,) = store.releases
    assert entry["status"] == RESERVATION_RELEASED_BY_CANCEL
    assert entry["reason"] == RELEASE_REASON_DEAD_TAIL


@pytest.mark.asyncio
async def test_release_log_keeps_a_partial_chunk_live_and_still_declares_its_reason() -> None:
    """Un chunk PARCIAL no es una retirada: la fila sigue viva, aunque el motivo quede anotado.

    Por eso el conteo de retiradas no lo cuenta (``count_releases`` cuenta estados terminales)
    y, sin embargo, el log conserva el motivo: son dos preguntas distintas —«¿se retiró?» y
    «¿por qué se tocó?»— y mezclarlas inventaría retiradas donde solo hubo descarga de cantidad.
    """
    store = await _store_with_live()

    row = await store.release(
        "RES-TAIL",
        status=RESERVATION_RELEASED_BY_CANCEL,
        reason=RELEASE_REASON_DEAD_TAIL,
        released_qty=40.0,
    )

    assert row is not None and row.is_live is True
    (entry,) = store.releases
    assert entry["reason"] == RELEASE_REASON_DEAD_TAIL
    assert entry["releasedQty"] == 40.0
    assert count_release_reasons(store.releases) == {}
    assert tally_releases([], store.releases).by_cancel == 0


@pytest.mark.asyncio
async def test_release_log_feeds_the_dead_tail_count_instead_of_a_silent_zero() -> None:
    """El motivo del log alimenta ``byDeadTail``: el conteo es MEDIBLE, no un hueco."""
    store = await _store_with_live()

    await store.release(
        "RES-TAIL",
        status=RESERVATION_RELEASED_BY_CANCEL,
        reason=RELEASE_REASON_DEAD_TAIL,
    )
    store.releases.append(
        {
            "reservationId": "RES-ORPHAN",
            "status": RESERVATION_RELEASED_BY_CANCEL,
            "reason": "cancel",
        }
    )

    tally = tally_releases([], store.releases)

    assert tally.by_cancel == 2
    assert tally.by_dead_tail == 1
    assert count_release_reasons(store.releases) == {"tail_dead": 1, "cancel": 1}


@pytest.mark.asyncio
async def test_release_log_does_not_invent_a_reason_when_none_was_declared() -> None:
    """Sin motivo, la fila publica vacío: "no se declaró" no se convierte en "cancel"."""
    store = await _store_with_live()

    await store.release("RES-TAIL", status=RESERVATION_RELEASED_BY_CANCEL)

    (row,) = store.releases
    assert row["reason"] == ""
    assert tally_releases([], store.releases).by_dead_tail == 0


@pytest.mark.asyncio
async def test_release_log_ignores_an_idempotent_release() -> None:
    """Una liberación que no retiró nada (reserva ya muerta) NO entra al log."""
    store = await _store_with_live()

    await store.release("RES-TAIL", status=RESERVATION_RELEASED_BY_CANCEL, reason="cancel")
    assert len(store.releases) == 1

    again = await store.release("RES-TAIL", status=RESERVATION_RELEASED_BY_CANCEL, reason="cancel")

    assert again is None
    assert len(store.releases) == 1


# ── Capa v6 (DÍA-D-3g): evento de gestión ↔ cycle_id ─────────────────────────────


class _JournalEntry:
    """Stub mínimo de una fila del journal (lo que la costura LEE, sin motor)."""

    def __init__(
        self,
        *,
        event_type: str,
        instrument_id: str,
        created_at: str,
        payload: dict[str, Any],
    ) -> None:
        self.event_type = event_type
        self.instrument_id = instrument_id
        self.created_at = created_at
        self.payload = payload


def test_management_rows_join_the_open_cycle_by_instrument_and_day() -> None:
    """Un evento de gestión pertenece al ciclo abierto de su símbolo en D1; se une y se declara."""
    journal = [
        _JournalEntry(
            event_type="auto_position_management",
            instrument_id="AAA",
            created_at="2022-01-07T00:00:00Z",
            payload={
                "reasonCodes": ["thesis_exit"],
                "primaryReason": "THESIS_INVALIDATION",
                "exitReasons": ["STRUCTURAL_STOP", "THESIS_INVALIDATION"],
                "thesisInvalid": True,
            },
        ),
        # Evento no-gestión: no entra.
        _JournalEntry(
            event_type="position_close",
            instrument_id="AAA",
            created_at="2022-01-07T00:00:00Z",
            payload={},
        ),
    ]
    rows = _load_v87()._management_rows_with_cycle(
        journal, cycle_by_symbol_day={("AAA", "2022-01-07"): "C1"}
    )
    assert len(rows) == 1
    assert rows[0]["cycleId"] == "C1"
    assert rows[0]["primaryReason"] == "THESIS_INVALIDATION"
    assert rows[0]["exitReasons"] == ["STRUCTURAL_STOP", "THESIS_INVALIDATION"]


def test_management_row_on_the_entry_day_declares_a_gap_never_an_invented_cycle() -> None:
    """Sin ciclo abierto previo (día de ENTRADA) el ``cycleId`` es un hueco declarado, no inventado."""
    journal = [
        _JournalEntry(
            event_type="auto_position_management",
            instrument_id="BBB",
            created_at="2022-01-05T00:00:00Z",
            payload={"primaryReason": None, "reasonCodes": [], "exitReasons": []},
        )
    ]
    rows = _load_v87()._management_rows_with_cycle(journal, cycle_by_symbol_day={})
    assert rows[0]["cycleId"] is None
