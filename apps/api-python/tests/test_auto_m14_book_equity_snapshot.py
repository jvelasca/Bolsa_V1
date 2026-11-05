"""M14 — la equity del libro es una foto de ESTE turno, no la del turno anterior.

El fallo que se cierra: ``load_book_equity`` guardaba la lectura en tres atributos sueltos
y sólo limpiaba el valor en la rama ``except Exception``. Una cancelación a mitad de la
lectura (``CancelledError`` **no** es ``Exception``) o un fallo fuera de esa rama dejaba la
equity del turno anterior como si fuera la del turno corriente.

La corrección: una sola foto inmutable (``BookEquitySnapshot``) con su ``as_of``, invalidada
**antes** del ``await`` y publicada con una única asignación.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from bolsa_api.background import auto_simulation_worker as worker_module
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker


def _worker() -> AutoSimulationWorker:
    return AutoSimulationWorker(
        clock=lambda: datetime(2026, 11, 5, 9, 0, tzinfo=UTC),
        account_id="acc-m14",
    )


@pytest.mark.asyncio
async def test_successful_read_stamps_the_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    async def read(_session: Any, _account_id: str | None) -> float:
        return 12_345.67

    monkeypatch.setattr(worker_module, "read_account_book_equity", read)
    worker = _worker()

    await worker.load_book_equity(object())

    assert worker._v2_equity() == pytest.approx(12_345.67)
    assert worker.book_equity_as_of == "2026-11-05T09:00:00Z"
    assert worker.book_equity_unreadable is False


@pytest.mark.asyncio
async def test_failed_read_vetoes_instead_of_reusing_the_previous_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un libro bueno en el turno N no puede autorizar un BUY en el turno N+1 roto."""
    equity = {"value": 50_000.0}
    broken = {"on": False}

    async def read(_session: Any, _account_id: str | None) -> float:
        if broken["on"]:
            raise RuntimeError("portfolio unreadable")
        return equity["value"]

    monkeypatch.setattr(worker_module, "read_account_book_equity", read)
    worker = _worker()
    await worker.load_book_equity(object())
    assert worker._v2_equity() == pytest.approx(50_000.0)

    broken["on"] = True
    await worker.load_book_equity(object())

    assert worker._v2_equity() == 0.0, "sin lectura no hay equity: nunca la del tick anterior"
    assert worker.book_equity_unreadable is True
    assert worker.book_equity_as_of is None


@pytest.mark.asyncio
async def test_cancelled_read_does_not_leave_the_previous_equity(monkeypatch: pytest.MonkeyPatch) -> None:
    """``CancelledError`` es ``BaseException``: no pasa por ``except Exception``.

    Antes de M14 el turno cancelado a mitad conservaba la equity del turno previo y el
    siguiente turno la habría usado como autoridad. La foto se invalida ANTES del await.
    """
    calls = {"n": 0}

    async def read(_session: Any, _account_id: str | None) -> float:
        calls["n"] += 1
        if calls["n"] == 2:
            raise asyncio.CancelledError()
        return 77_000.0

    monkeypatch.setattr(worker_module, "read_account_book_equity", read)
    worker = _worker()
    await worker.load_book_equity(object())
    assert worker._v2_equity() == pytest.approx(77_000.0)

    with pytest.raises(asyncio.CancelledError):
        await worker.load_book_equity(object())

    assert worker._v2_equity() == 0.0
    assert worker.book_equity_unreadable is True


@pytest.mark.asyncio
async def test_non_positive_equity_is_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def read(_session: Any, _account_id: str | None) -> float:
        return 0.0

    monkeypatch.setattr(worker_module, "read_account_book_equity", read)
    worker = _worker()

    await worker.load_book_equity(object())

    assert worker._v2_equity() == 0.0
    assert worker.book_equity_unreadable is True
    assert worker.book_equity_as_of is None


def test_hermetic_path_never_requires_the_book() -> None:
    """Sin ``load_book_equity`` la foto no se exige: se conserva el env/100_000."""
    worker = AutoSimulationWorker()

    assert worker._book_equity_required is False
    assert worker._v2_equity() == pytest.approx(100_000.0)


def test_snapshot_is_immutable() -> None:
    from dataclasses import FrozenInstanceError

    from bolsa_api.background.auto_simulation_worker import BookEquitySnapshot

    snapshot = BookEquitySnapshot(equity=1.0, as_of="2026-11-05T09:00:00Z")
    with pytest.raises(FrozenInstanceError):
        snapshot.equity = 2.0  # type: ignore[misc]
