"""Live progress bridge for threaded VectorBT / Optuna optimizers."""

from __future__ import annotations

import asyncio
import time

import pytest

from bolsa_application.optimize import _run_in_thread_with_live_progress


def _fake_grid(*, on_progress=None, n: int = 5) -> list[int]:
    best = None
    out: list[int] = []
    for i in range(1, n + 1):
        time.sleep(0.05)
        score = float(i)
        if best is None or score > best:
            best = score
        out.append(i)
        if on_progress is not None:
            on_progress(i, n, best)
    return out


@pytest.mark.asyncio
async def test_threaded_progress_flushes_mid_run() -> None:
    samples: list[tuple[int, float | None]] = []

    async def on_progress(done: int, _total: int, best: float | None) -> None:
        samples.append((done, best))

    result = await _run_in_thread_with_live_progress(
        _fake_grid,
        trials_total=5,
        on_progress=on_progress,
        poll_seconds=0.03,
        n=5,
    )

    assert result == [1, 2, 3, 4, 5]
    dones = [item[0] for item in samples]
    assert max(dones) == 5
    # Mid-run: at least one update before the final 5.
    assert any(done < 5 for done in dones)


@pytest.mark.asyncio
async def test_threaded_progress_without_callback() -> None:
    result = await _run_in_thread_with_live_progress(
        _fake_grid,
        trials_total=3,
        on_progress=None,
        n=3,
    )
    assert result == [1, 2, 3]
