"""P1-02 (E2 full V2.14) — reconcile de POSICIÓN continuo (LR-1) → incidentes.

Cubre ``reconcile_live_positions``: una pasada sobre cuentas de un venue ``live``
lee el status LR-1 y, si hay drift o unavailable, abre incidentes durables
``live_drift``/``live_unavailable`` reusando ``sync_opening_incidents`` (dedup
1-por-(account,kind), sin auto-heal).

Inyectable sin DB (fake de lookup + store InMemory); el PG real queda en C1.
"""

from __future__ import annotations

import pytest

from bolsa_application.operational_incident_store import (
    InMemoryOperationalIncidentStore,
)
from bolsa_application.reconcile_live_positions import (
    SyncOpeningIncidentsOpener,
    reconcile_and_open_position_incidents,
)


class _LiveReconFake:
    """Devuelve un status LR-1 por cuenta; 'boom' lanza (simula infra caída)."""

    def __init__(self, status_by_account: dict[str, str]) -> None:
        self._status = status_by_account

    async def live_recon_status(self, account_id: str) -> str:
        if account_id == "boom":
            raise RuntimeError("recon unavailable infra")
        return self._status.get(account_id, "clean")


async def _kinds(store: InMemoryOperationalIncidentStore, aid: str) -> list[str]:
    return [i.kind for i in await store.list_active(aid)]


@pytest.mark.asyncio
async def test_drift_account_opens_live_drift() -> None:
    store = InMemoryOperationalIncidentStore()
    opener = SyncOpeningIncidentsOpener(store)
    recon = _LiveReconFake({"acc-1": "drift"})

    result = await reconcile_and_open_position_incidents(
        ["acc-1"],
        live_recon=recon,  # type: ignore[arg-type]
        opener=opener,
    )
    assert result.drifted == 1
    assert result.accounts_considered == 1
    assert result.clean == 0
    assert await _kinds(store, "acc-1") == ["live_drift"]


@pytest.mark.asyncio
async def test_clean_and_unavailable() -> None:
    store = InMemoryOperationalIncidentStore()
    opener = SyncOpeningIncidentsOpener(store)
    recon = _LiveReconFake({"acc-ok": "clean", "acc-down": "unavailable"})

    result = await reconcile_and_open_position_incidents(
        ["acc-ok", "acc-down"],
        live_recon=recon,  # type: ignore[arg-type]
        opener=opener,
    )
    assert result.clean == 1
    assert result.unavailable == 1
    assert result.drifted == 0
    assert await _kinds(store, "acc-ok") == []
    assert await _kinds(store, "acc-down") == ["live_unavailable"]


@pytest.mark.asyncio
async def test_error_in_recon_is_tolerated() -> None:
    store = InMemoryOperationalIncidentStore()
    opener = SyncOpeningIncidentsOpener(store)
    recon = _LiveReconFake({"boom": "drift"})

    result = await reconcile_and_open_position_incidents(
        ["boom"],
        live_recon=recon,  # type: ignore[arg-type]
        opener=opener,
    )
    assert result.errors == 1
    assert result.account_errors == ["boom"]
    assert await _kinds(store, "boom") == []


@pytest.mark.asyncio
async def test_blank_account_ids_are_ignored() -> None:
    store = InMemoryOperationalIncidentStore()
    opener = SyncOpeningIncidentsOpener(store)
    recon = _LiveReconFake({"": "drift", "  ": "drift", "acc-real": "clean"})

    result = await reconcile_and_open_position_incidents(
        ["", "  ", "acc-real"],
        live_recon=recon,  # type: ignore[arg-type]
        opener=opener,
    )
    assert result.accounts_considered == 1
    assert result.clean == 1
    assert await _kinds(store, "") == []


@pytest.mark.asyncio
async def test_two_passes_do_not_duplicate_incident() -> None:
    """Mismo drift, DOS pasadas → 1 incidente (open idempotente, sin auto-heal)."""
    store = InMemoryOperationalIncidentStore()
    opener = SyncOpeningIncidentsOpener(store)
    recon = _LiveReconFake({"acc-1": "drift"})

    first = await reconcile_and_open_position_incidents(
        ["acc-1"],
        live_recon=recon,
        opener=opener,  # type: ignore[arg-type]
    )
    second = await reconcile_and_open_position_incidents(
        ["acc-1"],
        live_recon=recon,
        opener=opener,  # type: ignore[arg-type]
    )
    assert first.drifted == 1
    assert second.drifted == 1
    assert len(await store.list_active("acc-1")) == 1
