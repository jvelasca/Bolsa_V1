"""P2 — verificación DÍA-D enlazada a un ciclo: helper puro + caso de uso.

Sin DB ni red: se prueba el draft (huecos declarados, sin fabricar identidad) y el
caso de uso contra un repositorio doble.
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.dia_d_cycle_verification import (
    ListDiaDCycleVerifications,
    PersistDiaDCycleVerification,
    build_dia_d_cycle_verification_draft,
)
from bolsa_domain.entities.dia_d_cycle_verification import DiaDCycleVerification


def test_draft_completes_identity_when_cycle_declares_it() -> None:
    draft = build_dia_d_cycle_verification_draft(
        {
            "cycleId": "cyc-1",
            "instrumentId": "inst-1",
            "symbol": "ACS",
            "diaD": "2026-01-01",
            "endDate": "2026-01-10",
            "mode": "auto",
            "strategyPresetKey": "sma_crossover",
            "strategyVersion": "ver-1",
            "strategyDefinitionId": "def-1",
            "band": "favorable",
            "result": {"band": "favorable", "returnPct": 3.2},
            "researchEvidenceId": "ev-1",
        }
    )
    assert draft is not None
    assert draft["cycle_id"] == "cyc-1"
    assert draft["strategy_preset_key"] == "sma_crossover"
    assert draft["strategy_version"] == "ver-1"
    assert draft["strategy_definition_id"] == "def-1"
    assert draft["band"] == "favorable"
    assert draft["result"] == {"band": "favorable", "returnPct": 3.2}
    assert draft["research_evidence_id"] == "ev-1"


def test_draft_declares_gaps_never_fabricates_identity() -> None:
    # Un ciclo histórico SIN claves de estrategia: huecos declarados, nunca "" ni inventado.
    draft = build_dia_d_cycle_verification_draft(
        {
            "cycleId": "cyc-2",
            "instrumentId": "inst-2",
            "symbol": "ITX",
            "diaD": "2026-02-01",
            "endDate": "2026-02-05",
            "mode": "auto",
        }
    )
    assert draft is not None
    assert draft["strategy_preset_key"] is None
    assert draft["strategy_version"] is None
    assert draft["strategy_definition_id"] is None
    assert draft["result"] is None
    assert draft["band"] is None


@pytest.mark.parametrize(
    "missing",
    ["cycleId", "instrumentId", "symbol", "diaD", "endDate", "mode"],
)
def test_draft_is_none_without_the_indispensable_key(missing: str) -> None:
    payload: dict[str, Any] = {
        "cycleId": "cyc-3",
        "instrumentId": "inst-3",
        "symbol": "SAN",
        "diaD": "2026-03-01",
        "endDate": "2026-03-04",
        "mode": "auto",
    }
    payload.pop(missing)
    assert build_dia_d_cycle_verification_draft(payload) is None


def test_draft_ignores_non_dict_result() -> None:
    draft = build_dia_d_cycle_verification_draft(
        {
            "cycleId": "cyc-4",
            "instrumentId": "inst-4",
            "symbol": "TEF",
            "diaD": "2026-04-01",
            "endDate": "2026-04-02",
            "mode": "auto",
            "result": "no-es-un-dict",
        }
    )
    assert draft is not None
    assert draft["result"] is None


class _FakeRepo:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def upsert(self, **kwargs: Any) -> DiaDCycleVerification:
        self.calls.append(kwargs)
        return DiaDCycleVerification(
            id="v-1",
            cycle_id=kwargs["cycle_id"],
            account_id=kwargs.get("account_id"),
            instrument_id=kwargs["instrument_id"],
            symbol=kwargs["symbol"],
            dia_d=kwargs["dia_d"],
            end_date=kwargs["end_date"],
            mode=kwargs["mode"],
            created_at="2026-04-02T00:00:00+00:00",
            strategy_preset_key=kwargs.get("strategy_preset_key"),
            strategy_version=kwargs.get("strategy_version"),
            band=kwargs.get("band"),
            result=kwargs.get("result"),
            research_evidence_id=kwargs.get("research_evidence_id"),
        )

    async def list_verifications(
        self,
        *,
        account_id: str | None = None,
        cycle_id: str | None = None,
        limit: int = 200,
    ) -> list[DiaDCycleVerification]:
        return [
            DiaDCycleVerification(
                id="v-1",
                cycle_id=cycle_id or "cyc-x",
                account_id=account_id,
                instrument_id="inst-1",
                symbol="ACS",
                dia_d="2026-04-01",
                end_date="2026-04-02",
                mode="auto",
                created_at="2026-04-02T00:00:00+00:00",
            )
        ]


@pytest.mark.asyncio
async def test_persist_use_case_passes_account_scope() -> None:
    repo = _FakeRepo()
    row = await PersistDiaDCycleVerification(repo).execute(
        {
            "cycleId": "cyc-9",
            "instrumentId": "inst-9",
            "symbol": "IBE",
            "diaD": "2026-05-01",
            "endDate": "2026-05-02",
            "mode": "auto",
        },
        account_id="acc-1",
    )
    assert row is not None
    assert repo.calls[0]["account_id"] == "acc-1"
    assert repo.calls[0]["cycle_id"] == "cyc-9"


@pytest.mark.asyncio
async def test_persist_use_case_is_noop_without_indispensable_key() -> None:
    repo = _FakeRepo()
    row = await PersistDiaDCycleVerification(repo).execute(
        {"cycleId": "", "instrumentId": "i", "symbol": "S", "diaD": "d", "endDate": "e", "mode": "m"},
        account_id="acc-1",
    )
    assert row is None
    assert repo.calls == []


@pytest.mark.asyncio
async def test_list_use_case_returns_repository_rows() -> None:
    repo = _FakeRepo()
    rows = await ListDiaDCycleVerifications(repo).execute(
        account_id="acc-1", cycle_id="cyc-1"
    )
    assert len(rows) == 1
    assert rows[0].cycle_id == "cyc-1"
