"""M16 (auditoría .183) — la CUENTA y el INSTRUMENTO de una ACTIVE son ámbitos distintos.

El runtime AUTO cargaba la estrategia ACTIVE con ``get_active(instrument_id=<cuenta>)``:
la cuenta viajaba como si fuera un instrumento. Estos tests fijan el contrato del doble
hermético del store (``get_active_for_account``) para que la separación no se pueda
deshacer sin que algo se ponga rojo:

* una ACTIVE atribuida a una cuenta se lee POR CUENTA;
* el mismo id NO localiza nada por la ruta de instrumento;
* la fila histórica (cuenta metida en ``instrument_id``) sigue siendo legible, pero la
  ACTIVE resultante declara ``account_id=None``: el ámbito ausente no se rellena.
"""

from __future__ import annotations

import pytest

from bolsa_application.strategy_lifecycle_store import (
    ActiveStrategyRecord,
    InMemoryStrategyLifecycleStore,
)
from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy

pytestmark = pytest.mark.asyncio

_ACCOUNT = "acc-ventana-1"
_INSTRUMENT = "inst-v229-aaa"


def _record(*, account_id: str | None) -> ActiveStrategyRecord:
    return ActiveStrategyRecord(
        active=ActiveStrategy(
            version_id="ver-m16",
            candidate_id="cand-m16",
            instrument_id=_INSTRUMENT,
            name="SMA",
            definition={"lot_qty": 10.0, "watch": [_INSTRUMENT]},
            account_id=account_id,
        ),
        promoted_at="2026-11-04",
    )


async def test_account_scoped_active_is_read_by_account_not_by_instrument() -> None:
    store = InMemoryStrategyLifecycleStore()
    await store.save_active(_record(account_id=_ACCOUNT))

    by_account = await store.get_active_for_account(account_id=_ACCOUNT)
    assert by_account is not None
    assert by_account.active.account_id == _ACCOUNT
    assert by_account.active.instrument_id == _INSTRUMENT

    # La cuenta NO es un instrumento: por la ruta de instrumento no hay nada.
    assert await store.get_active(instrument_id=_ACCOUNT) is None
    # Y el instrumento sigue resolviendo su propia ACTIVE.
    by_instrument = await store.get_active(instrument_id=_INSTRUMENT)
    assert by_instrument is not None
    assert by_instrument.active.account_id == _ACCOUNT


async def test_instrument_scoped_active_is_not_returned_for_a_legacy_account_path() -> None:
    """Sin ``account_id`` la ACTIVE es de instrumento: pedirla por cuenta solo la
    encuentra si la cuenta coincide con el instrumento (ruta histórica del doble)."""
    store = InMemoryStrategyLifecycleStore()
    await store.save_active(_record(account_id=None))

    assert await store.get_active_for_account(account_id=_ACCOUNT) is None
    assert await store.get_active(instrument_id=_INSTRUMENT) is not None


async def test_legacy_row_keyed_by_account_stays_readable_without_inventing_the_scope() -> None:
    """Compatibilidad: la cuenta guardada como ``instrument_id`` se sigue leyendo.

    Es la semilla de la ventana anterior a la 064. La ACTIVE devuelta NO dice tener
    ``account_id``: la fila no lo declara y no se rellena a posteriori.
    """
    store = InMemoryStrategyLifecycleStore()
    legacy = ActiveStrategyRecord(
        active=ActiveStrategy(
            version_id="ver-legacy",
            candidate_id="cand-legacy",
            instrument_id=_ACCOUNT,  # la cuenta disfrazada de instrumento (previo a M16)
            name="LEGACY",
            definition={},
        ),
        promoted_at="2026-10-01",
    )
    await store.save_active(legacy)

    found = await store.get_active_for_account(account_id=_ACCOUNT)
    assert found is not None
    assert found.active.version_id == "ver-legacy"
    assert found.active.account_id is None


async def test_declared_account_wins_over_the_legacy_row() -> None:
    """Si conviven la fila declarada y la histórica, manda la declarada."""
    store = InMemoryStrategyLifecycleStore()
    legacy = ActiveStrategyRecord(
        active=ActiveStrategy(
            version_id="ver-legacy",
            candidate_id="cand-legacy",
            instrument_id=_ACCOUNT,
            name="LEGACY",
            definition={},
        ),
        promoted_at="2026-10-01",
    )
    await store.save_active(legacy)
    await store.save_active(_record(account_id=_ACCOUNT))

    found = await store.get_active_for_account(account_id=_ACCOUNT)
    assert found is not None
    assert found.active.version_id == "ver-m16"
    assert found.active.account_id == _ACCOUNT


async def test_list_active_includes_account_scoped_records() -> None:
    """``list_active`` no puede perder las ACTIVE de cuenta (antes solo veía instrumento)."""
    store = InMemoryStrategyLifecycleStore()
    await store.save_active(_record(account_id=_ACCOUNT))

    actives = await store.list_active()
    version_ids = {record.active.version_id for record in actives}
    assert version_ids == {"ver-m16"}
