"""Parte diario ESTUDIO — el troceo de opiniones NO multiplica la lectura de cartera.

El parte mide la cartera UNA vez (fase ``hints``) y después trocea los ids en
``_OPINION_CHUNK`` (10) llamadas a ``run_eod_batch``. Este test fija que el troceo es de
las OPINIONES, no de las posiciones: con 25 ids hay 3 trozos y una sola lectura de
cartera. Si alguien moviera la medición de posiciones dentro del bucle de trozos, el
contador de ``_FakePositions`` subiría a 3 y el test fallaría.

Reutiliza los fakes de ``test_estudio_daily_ops.py`` (misma forma que producción) para no
duplicar un universo/opiniones/propose falsos.
"""

from __future__ import annotations

import pytest
from test_estudio_daily_ops import (
    _DAY,
    _FakeComposite,
    _FakeEstudioList,
    _FakeFundamentals,
    _FakeOpinions,
    _FakePositions,
    _FakePropose,
    _Opinion,
)

from bolsa_application.estudio_daily_ops import RunEstudioDailyOps

ACCOUNT = "acc-1"


@pytest.mark.asyncio
async def test_3_opinion_chunks_still_reads_the_portfolio_once() -> None:
    ids = [f"inst-{index:02d}" for index in range(25)]
    rows = {iid: _Opinion(iid, "buy", 4) for iid in ids}
    opinions = _FakeOpinions(rows)
    positions = _FakePositions([ids[0]])
    service = RunEstudioDailyOps(
        _FakeEstudioList(ids),
        opinions,
        _FakePropose(),
        composite=_FakeComposite(),
        fundamentals=_FakeFundamentals(),
        positions=positions,
    )

    report = await service.execute(account_id=ACCOUNT, as_of=_DAY)

    # 25 ids / _OPINION_CHUNK (10) ⇒ 3 trozos de opiniones.
    assert [len(call) for call in opinions.calls] == [10, 10, 5]
    # …y aun así la cartera se lee UNA sola vez (fase de hints), no una por trozo.
    assert positions.calls == [ACCOUNT]
    assert report.universe["expectedCount"] == 25
    assert len(report.values) == 25
