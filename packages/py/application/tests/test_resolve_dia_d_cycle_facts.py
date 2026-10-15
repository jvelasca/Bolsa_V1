"""v111 — identidad DURABLE del ciclo para anclar la verificación DÍA-D (`resolve_dia_d_cycle_facts`).

**Regresión que fija este módulo** (destapada por el `Release tag CI` del sello `v2.88.136`):

El harness de siembra del E2E (`scripts/dev/seed_auto_cycle_for_ui.py`) guarda el **SÍMBOLO**
como ``instrument_id`` de la reserva (``_reservation(instrument=symbol)``), mientras el navegador
declara el **id de catálogo** del instrumento (el fixture lo resuelve por símbolo contra
``/api/instruments``). Si la identidad derivada viaja **cruda** (el símbolo), el contraste
declarado del contrato DÍA-D (`_declared_conflicts`) compara cadenas distintas y dispara un
``409 cycle_identity_conflict``: el enlace durable **nunca** se escribe, así que el E2E
``GP-V288-S5-04`` (exige una fila con el ``cycleId`` **y** el ``instrumentId`` del ciclo) falla
incluso en el reintento.

Antes de v111 la identidad la declaraba el navegador (siempre el id de catálogo) y el defecto
vivía latente; al mover la derivación al servidor se hizo visible. Sin la canonización al id de
catálogo, estos tests **rompen**.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_application.auto_chain_durable_reader import (
    canonical_instrument_identity,
    resolve_dia_d_cycle_facts,
)
from bolsa_application.dia_d_cycle_verification import (
    DiaDCycleFacts,
    DiaDCycleIdentityConflictError,
    ResolveDiaDCycleVerification,
)

_CATALOG_UUID = "8f6c2b1e-0000-4000-8000-aaaaaaaaaaaa"
_SYMBOL = "ACS"
_CYCLE = "cyc-seeded-1"
_ACCOUNT = "acc-e2e"


class _Result:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row

    def first(self) -> tuple[Any, ...] | None:
        return self._row


class _FakeSession:
    """Sesión mínima: solo la lectura de catálogo (``id``/``symbol``) del resolver."""

    def __init__(self, catalog_row: tuple[Any, ...] | None) -> None:
        self.catalog_row = catalog_row
        self.queries: list[Any] = []

    async def execute(self, statement: Any) -> _Result:
        self.queries.append(statement)
        return _Result(self.catalog_row)


class _CapturingRepo:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def upsert(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(**kwargs)


def _resolver_for(facts: DiaDCycleFacts) -> Any:
    async def _resolve(*, account_id: str, cycle_id: str) -> DiaDCycleFacts:
        return facts

    return SimpleNamespace(resolve=_resolve)


@pytest.fixture
def seeded_symbol_seams(monkeypatch: pytest.MonkeyPatch) -> None:
    """Siembra E2E: la reserva guarda el SÍMBOLO y el monitor sella la estrategia ejecutada."""

    async def _list_by_cycle_ids(
        self: Any,
        account_id: str | None,
        cycle_ids: Any,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> list[Any]:
        if _CYCLE not in list(cycle_ids):
            return []
        return [SimpleNamespace(instrument_id=_SYMBOL, cycle_id=_CYCLE, account_id=account_id)]

    async def _monitor(session: Any, account_id: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "cycles": [
                {
                    "cycleId": _CYCLE,
                    "strategyPresetKey": "sma_crossover",
                    "strategyVersion": "ver-7",
                }
            ]
        }

    monkeypatch.setattr(
        "bolsa_application.reservation_store.PostgresReservationStore.list_by_cycle_ids",
        _list_by_cycle_ids,
    )
    monkeypatch.setattr(
        "bolsa_application.auto_chain_durable_reader.read_operational_monitor", _monitor
    )


# --- Regla pura: canonización al id de catálogo ---------------------------------------------


def test_canonical_identity_prefers_catalog_id_over_seeded_symbol() -> None:
    """La costura de siembra (símbolo como id) se canoniza al id de catálogo."""
    assert canonical_instrument_identity(_SYMBOL, (_CATALOG_UUID, _SYMBOL)) == (
        _CATALOG_UUID,
        _SYMBOL,
    )


def test_canonical_identity_is_idempotent_on_catalog_id() -> None:
    assert canonical_instrument_identity(_CATALOG_UUID, (_CATALOG_UUID, _SYMBOL)) == (
        _CATALOG_UUID,
        _SYMBOL,
    )


def test_canonical_identity_keeps_raw_value_without_catalog_row() -> None:
    """Sin fila de catálogo NO se inventa identidad: crudo + símbolo como hueco declarado."""
    assert canonical_instrument_identity(_SYMBOL, None) == (_SYMBOL, None)


def test_canonical_identity_falls_back_when_catalog_id_is_blank() -> None:
    assert canonical_instrument_identity(_SYMBOL, ("  ", _SYMBOL)) == (_SYMBOL, _SYMBOL)


def test_canonical_identity_declares_hueco_for_blank_input() -> None:
    assert canonical_instrument_identity("", (_CATALOG_UUID, _SYMBOL)) == (_CATALOG_UUID, _SYMBOL)


# --- Resolver real (con las costuras de la siembra) -----------------------------------------


@pytest.mark.asyncio
async def test_resolve_facts_canonicalizes_seeded_symbol_to_catalog_id(
    seeded_symbol_seams: None,
) -> None:
    facts = await resolve_dia_d_cycle_facts(
        _FakeSession((_CATALOG_UUID, _SYMBOL)), _ACCOUNT, cycle_id=_CYCLE
    )
    assert facts is not None
    # El hecho DURABLE es el símbolo; la identidad que se propaga es la del CATÁLOGO.
    assert facts.instrument_id == _CATALOG_UUID
    assert facts.symbol == _SYMBOL
    assert facts.strategy_preset_key == "sma_crossover"
    assert facts.strategy_version == "ver-7"


@pytest.mark.asyncio
async def test_resolve_facts_keeps_raw_identity_when_catalog_is_unreadable(
    seeded_symbol_seams: None,
) -> None:
    facts = await resolve_dia_d_cycle_facts(_FakeSession(None), _ACCOUNT, cycle_id=_CYCLE)
    assert facts is not None
    assert facts.instrument_id == _SYMBOL
    assert facts.symbol is None


@pytest.mark.asyncio
async def test_resolve_facts_declares_gap_for_unknown_cycle(seeded_symbol_seams: None) -> None:
    facts = await resolve_dia_d_cycle_facts(_FakeSession(None), _ACCOUNT, cycle_id="cyc-otro")
    assert facts is None


# --- Regresión de CI: el contraste declarado NO debe dar 409 --------------------------------


@pytest.mark.asyncio
async def test_declared_catalog_uuid_does_not_conflict_with_seeded_symbol(
    seeded_symbol_seams: None,
) -> None:
    """EL TEST DE LA REGRESIÓN: el navegador declara el id de catálogo y el hecho durable es el
    símbolo sembrado. Con la canonización el contraste coincide y el enlace durable se ESCRIBE
    con el id de catálogo — que es lo que exige el E2E `GP-V288-S5-04`."""
    facts = await resolve_dia_d_cycle_facts(
        _FakeSession((_CATALOG_UUID, _SYMBOL)), _ACCOUNT, cycle_id=_CYCLE
    )
    assert isinstance(facts, DiaDCycleFacts)

    repo = _CapturingRepo()
    row = await ResolveDiaDCycleVerification(repo, _resolver_for(facts)).execute(
        {
            "cycleId": _CYCLE,
            "diaD": "2026-10-15",
            "endDate": "2026-10-16",
            "mode": "auto",
            "instrumentId": _CATALOG_UUID,
            "symbol": _SYMBOL,
        },
        account_id=_ACCOUNT,
    )
    assert row is not None
    assert len(repo.calls) == 1
    assert repo.calls[0]["instrument_id"] == _CATALOG_UUID
    assert repo.calls[0]["symbol"] == _SYMBOL


@pytest.mark.asyncio
async def test_raw_seeded_symbol_would_conflict_with_declared_catalog_uuid() -> None:
    """Falsabilidad de la guardia: con la identidad SIN canonizar (el símbolo sembrado, como
    viajaba antes del arreglo) el mismo contraste dispara `409` y NO se escribe nada."""
    raw_facts = DiaDCycleFacts(
        cycle_id=_CYCLE,
        instrument_id=_SYMBOL,
        symbol=_SYMBOL,
        strategy_preset_key="sma_crossover",
        strategy_version="ver-7",
    )
    repo = _CapturingRepo()
    with pytest.raises(DiaDCycleIdentityConflictError):
        await ResolveDiaDCycleVerification(repo, _resolver_for(raw_facts)).execute(
            {
                "cycleId": _CYCLE,
                "diaD": "2026-10-15",
                "endDate": "2026-10-16",
                "mode": "auto",
                "instrumentId": _CATALOG_UUID,
            },
            account_id=_ACCOUNT,
        )
    assert repo.calls == []
