"""AUTO-10 — tests del LECTOR del régimen por ciclo (paso 3).

Lo que se prueba es la DISCIPLINA de la lectura, no el acceso a datos (ese puerto se inyecta):

* que el régimen leído se **confirma** contra el ``payload['cycleId']`` y no se cree por la
  forma del ``decision_id`` (el fallback aleatorio tiene la misma forma y el ``decision_id`` de
  un ciclo lo comparte su entrada de ventana);
* que los tres huecos posibles se declaren **distintos** (no confirmado / ausente / no
  derivable), porque un solo contador mentiría en alguno;
* que el ``decision_id`` se pida al puerto ya derivado y en tandas acotadas;
* que un régimen declarado ``None`` (``UNKNOWN`` en la traza) no se convierta en un valor;
* que el reintento del tick (varias filas del mismo ciclo) no rompa nada y **se declare**: gana
  la confirmación más nueva y las filas de más se cuentan en ``duplicates`` (paso 4).
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.auto_cycle_journal import AUTO_CYCLE_REGIME_EVENT
from bolsa_application.auto_cycle_regime_reader import (
    REGIME_READ_ABSENT,
    REGIME_READ_NOT_DERIVABLE,
    REGIME_READ_UNCONFIRMED,
    read_cycle_regimes,
)

_ACCOUNT = "acc-1"


def _entry(
    *,
    decision_id: str,
    cycle_id: str | None,
    regime: str | None = "TREND_UP",
    event_type: str = AUTO_CYCLE_REGIME_EVENT,
    created_at: str = "2026-09-22T10:00:00Z",
) -> Any:
    """Fila del journal durable con lo justo que el lector mira: evento, id y payload."""
    from types import SimpleNamespace

    payload: dict[str, Any] = {}
    if cycle_id is not None:
        payload["cycleId"] = cycle_id
        payload["marketRegime"] = regime
    return SimpleNamespace(
        id=f"JNL-{decision_id}",
        decision_id=decision_id,
        event_type=event_type,
        actor="auto-sim",
        created_at=created_at,
        session_id=None,
        account_id=_ACCOUNT,
        instrument_id="AAA",
        payload=payload,
    )


class _Fetch:
    """Puerto de lectura de mentira: registra lo pedido y sirve las filas que le den."""

    def __init__(self, *entries: Any) -> None:
        self.entries = list(entries)
        self.calls: list[list[str]] = []

    async def __call__(self, decision_ids: Any) -> list[Any]:
        asked = list(decision_ids)
        self.calls.append(asked)
        return [entry for entry in self.entries if entry.decision_id in asked]


# ── El régimen confirmado ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_confirmed_trace_closes_the_cycle_regime() -> None:
    fetch = _Fetch(_entry(decision_id="dec-aaa", cycle_id="cyc-aaa"))

    reading = await read_cycle_regimes(fetch, ["cyc-aaa"])

    assert reading.regime_by_cycle == {"cyc-aaa": "TREND_UP"}
    assert reading.confirmed == 1
    assert reading.gaps == 0
    assert fetch.calls == [["dec-aaa"]], "se pregunta por el decision_id DERIVADO"


@pytest.mark.asyncio
async def test_the_reading_is_invariant_to_the_order_of_the_request() -> None:
    fetch = _Fetch(
        _entry(decision_id="dec-aaa", cycle_id="cyc-aaa"),
        _entry(decision_id="dec-bbb", cycle_id="cyc-bbb", regime="RANGE"),
    )

    forward = await read_cycle_regimes(fetch, ["cyc-aaa", "cyc-bbb"])
    backward = await read_cycle_regimes(fetch, ["cyc-bbb", "cyc-aaa"])

    assert forward.regime_by_cycle == backward.regime_by_cycle


@pytest.mark.asyncio
async def test_a_repeated_cycle_is_asked_once() -> None:
    fetch = _Fetch(_entry(decision_id="dec-aaa", cycle_id="cyc-aaa"))

    reading = await read_cycle_regimes(fetch, ["cyc-aaa", "cyc-aaa", " cyc-aaa "])

    assert reading.requested == 1
    assert fetch.calls == [["dec-aaa"]]


@pytest.mark.asyncio
async def test_the_newest_trace_wins_when_a_cycle_was_written_twice() -> None:
    """Reintento del tick ⇒ dos filas: el puerto las sirve de nueva a vieja y gana la nueva."""
    fetch = _Fetch(
        _entry(
            decision_id="dec-aaa",
            cycle_id="cyc-aaa",
            regime="TREND_UP",
            created_at="2026-09-22T11:00:00Z",
        ),
        _entry(
            decision_id="dec-aaa",
            cycle_id="cyc-aaa",
            regime="RANGE",
            created_at="2026-09-22T09:00:00Z",
        ),
    )

    reading = await read_cycle_regimes(fetch, ["cyc-aaa"])

    assert reading.regime_by_cycle == {"cyc-aaa": "TREND_UP"}


# ── El reintento se declara: gana la más nueva y las de más se cuentan ──────────────


@pytest.mark.asyncio
async def test_a_retry_declares_the_rows_it_collapsed() -> None:
    """Dos trazas del mismo ciclo: una sola verdad publicada y la fila de más DECLARADA."""
    fetch = _Fetch(
        _entry(
            decision_id="dec-aaa",
            cycle_id="cyc-aaa",
            regime="TREND_UP",
            created_at="2026-09-22T11:00:00Z",
        ),
        _entry(
            decision_id="dec-aaa",
            cycle_id="cyc-aaa",
            regime="RANGE",
            created_at="2026-09-22T09:00:00Z",
        ),
    )

    reading = await read_cycle_regimes(fetch, ["cyc-aaa"])
    summary = reading.as_dict()

    assert reading.duplicates == {"cyc-aaa": 1}
    assert reading.collapsed_rows == 1
    assert summary["duplicates"] == {"cyc-aaa": 1}
    assert summary["collapsedRows"] == 1
    assert reading.gaps == 0, "un reintento no es un hueco: es una lectura con nota"


@pytest.mark.asyncio
async def test_every_extra_row_is_counted_not_just_the_second_one() -> None:
    """Tres filas del mismo ciclo ⇒ dos de más: la nota cuenta TODAS las descartadas."""
    fetch = _Fetch(
        _entry(decision_id="dec-aaa", cycle_id="cyc-aaa", regime="C", created_at="3"),
        _entry(decision_id="dec-aaa", cycle_id="cyc-aaa", regime="B", created_at="2"),
        _entry(decision_id="dec-aaa", cycle_id="cyc-aaa", regime="A", created_at="1"),
    )

    reading = await read_cycle_regimes(fetch, ["cyc-aaa"])

    assert reading.regime_by_cycle == {"cyc-aaa": "C"}, "gana la primera servida (la más nueva)"
    assert reading.duplicates == {"cyc-aaa": 2}
    assert reading.collapsed_rows == 2


@pytest.mark.asyncio
async def test_a_single_trace_declares_no_duplicates() -> None:
    """El caso normal no inventa nota: sin filas de más, ``duplicates`` va vacío."""
    fetch = _Fetch(_entry(decision_id="dec-aaa", cycle_id="cyc-aaa"))

    reading = await read_cycle_regimes(fetch, ["cyc-aaa"])

    assert reading.duplicates == {}
    assert reading.collapsed_rows == 0


@pytest.mark.asyncio
async def test_an_unusable_row_of_more_is_declared_as_gap_not_as_duplicate() -> None:
    """Sin confirmación no hay "ganadora": el hueco se declara y NO se cuenta como duplicado."""
    fetch = _Fetch(
        _entry(decision_id="dec-aaa", cycle_id="cyc-OTHER", created_at="2"),
        _entry(decision_id="dec-aaa", cycle_id="cyc-OTHER", created_at="1"),
    )

    reading = await read_cycle_regimes(fetch, ["cyc-aaa"])

    assert reading.unconfirmed == ("cyc-aaa",)
    assert reading.duplicates == {}, "no hay régimen publicado: llamarlo duplicado confundiría"
    assert reading.collapsed_rows == 0


@pytest.mark.asyncio
async def test_the_newest_CONFIRMING_row_wins_over_a_newer_window_entry() -> None:
    """La entrada de ventana es más nueva y comparte ``decision_id``: no puede robar el régimen.

    Es la frontera del dedupe: "gana la más nueva" se mide entre las que **confirman**, no entre
    todas las filas del ``decision_id``. Si no, un ciclo con decisión y traza se leería como
    hueco, y el régimen que SÍ está escrito se perdería.
    """
    fetch = _Fetch(
        _entry(
            decision_id="dec-aaa",
            cycle_id="cyc-aaa",
            event_type="auto_v2_decision",
            created_at="2026-09-22T11:00:00Z",
        ),
        _entry(
            decision_id="dec-aaa",
            cycle_id="cyc-aaa",
            regime="TREND_UP",
            created_at="2026-09-22T09:00:00Z",
        ),
    )

    reading = await read_cycle_regimes(fetch, ["cyc-aaa"])

    assert reading.regime_by_cycle == {"cyc-aaa": "TREND_UP"}
    assert reading.duplicates == {"cyc-aaa": 1}, "la fila no confirmante también se cuenta"
    assert reading.unconfirmed == ()


# ── La confirmación: la forma NO prueba origen ──────────────────────────────────────


@pytest.mark.asyncio
async def test_a_row_of_another_cycle_is_not_believed() -> None:
    """El ``decision_id`` derivado puede existir por OTRO motivo: sin confirmación, no se cree."""
    fetch = _Fetch(_entry(decision_id="dec-aaa", cycle_id="cyc-OTHER"))

    reading = await read_cycle_regimes(fetch, ["cyc-aaa"])

    assert reading.regime_by_cycle == {}
    assert reading.unconfirmed == ("cyc-aaa",)
    assert REGIME_READ_UNCONFIRMED == "regime_unconfirmed"


@pytest.mark.asyncio
async def test_the_window_entry_of_the_same_decision_is_not_believed() -> None:
    """La entrada de ventana comparte ``decision_id`` con su traza: sin el evento, no se cree."""
    fetch = _Fetch(
        _entry(
            decision_id="dec-aaa",
            cycle_id="cyc-aaa",
            event_type="auto_v2_decision",
        )
    )

    reading = await read_cycle_regimes(fetch, ["cyc-aaa"])

    assert reading.regime_by_cycle == {}
    assert reading.unconfirmed == ("cyc-aaa",)


@pytest.mark.asyncio
async def test_a_trace_that_declared_unknown_does_not_become_a_value() -> None:
    """Una traza con ``marketRegime = None`` declara su hueco: el lector no lo rellena."""
    fetch = _Fetch(_entry(decision_id="dec-aaa", cycle_id="cyc-aaa", regime=None))

    reading = await read_cycle_regimes(fetch, ["cyc-aaa"])

    assert reading.regime_by_cycle == {}
    assert "cyc-aaa" not in reading.regime_by_cycle
    assert reading.confirmed == 0
    assert reading.absent == ()
    assert reading.unconfirmed == ("cyc-aaa",), "la fila existe y no sirve: se declara"


# ── Los tres huecos, declarados por separado ────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_absent_cycle_is_declared_absent() -> None:
    fetch = _Fetch()

    reading = await read_cycle_regimes(fetch, ["cyc-aaa"])

    assert reading.regime_by_cycle == {}
    assert reading.absent == ("cyc-aaa",)
    assert reading.unconfirmed == ()
    assert reading.gaps == 1
    assert REGIME_READ_ABSENT == "regime_absent"


@pytest.mark.asyncio
async def test_a_cycle_without_the_derivable_prefix_is_declared_and_never_asked() -> None:
    """Sin forma ``cyc-`` no hay ``decision_id`` derivable: se declara, no se adivina."""
    fetch = _Fetch(_entry(decision_id="dec-aaa", cycle_id="cyc-aaa"))

    reading = await read_cycle_regimes(fetch, ["cyc-aaa", "cycle-raw", "cyc-"])

    assert reading.regime_by_cycle == {"cyc-aaa": "TREND_UP"}
    assert reading.not_derivable == ("cycle-raw", "cyc-")
    assert REGIME_READ_NOT_DERIVABLE == "regime_not_derivable"
    assert fetch.calls == [["dec-aaa"]], "lo no derivable NO se consulta"


@pytest.mark.asyncio
async def test_the_three_gaps_are_told_apart_in_the_summary() -> None:
    fetch = _Fetch(
        _entry(decision_id="dec-unconfirmed", cycle_id="cyc-OTHER"),
    )

    reading = await read_cycle_regimes(fetch, ["cyc-unconfirmed", "cyc-absent", "raw-cycle"])
    summary = reading.as_dict()

    assert summary["requested"] == 3
    assert summary["confirmed"] == 0
    assert summary["unconfirmed"] == ["cyc-unconfirmed"]
    assert summary["absent"] == ["cyc-absent"]
    assert summary["notDerivable"] == ["raw-cycle"]


# ── Tandas acotadas ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_read_is_asked_in_bounded_chunks() -> None:
    """El ``IN`` no puede crecer sin límite: la lectura se parte en tandas del tamaño pedido."""
    fetch = _Fetch()
    cycle_ids = [f"cyc-{index:012x}" for index in range(5)]

    reading = await read_cycle_regimes(fetch, cycle_ids, chunk_size=2)

    assert [len(call) for call in fetch.calls] == [2, 2, 1]
    assert reading.requested == 5
    assert reading.absent == tuple(cycle_ids)


@pytest.mark.asyncio
async def test_an_empty_request_does_not_touch_the_port() -> None:
    fetch = _Fetch()

    reading = await read_cycle_regimes(fetch, [])

    assert reading.requested == 0
    assert reading.regime_by_cycle == {}
    assert fetch.calls == [], "sin ciclos no hay lectura que hacer"
