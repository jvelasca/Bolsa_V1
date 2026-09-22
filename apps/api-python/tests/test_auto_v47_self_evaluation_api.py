"""AUTO-7 — endpoint de lectura del informe de autoevaluación (hermético, sin PG).

Se verifica el CONTRATO de la superficie de lectura: que sea read-only, que agregue por
versión desde los fills durables, que el scope de cuenta sea fail-closed (sin cuenta
visible del principal la respuesta declara el hueco en vez de leer global) y que los
huecos (R/MAE/MFE/slippage/embudo) viajen DECLARADOS, nunca como ceros.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from bolsa_api.api.v1.routes import auto_self_evaluation as route_mod
from bolsa_api.api.v1.routes.auto_self_evaluation import get_auto_self_evaluation
from bolsa_application.sim_durable_store import SimFillFinanceContext


class _Session:
    """Sesión que el endpoint usa solo como asa para construir el store (parcheado)."""


class _Store:
    """Store fake: el endpoint debe LEER de aquí, con el scope de cuenta resuelto."""

    calls: list[tuple[str, str | None]] = []

    def __init__(self, _session: Any) -> None:
        pass

    async def list_for_strategy_version(
        self, version_id: str, *, account_id: str | None = None, limit: int | None = None
    ) -> list[SimFillFinanceContext]:
        _Store.calls.append((version_id, account_id))
        return [
            SimFillFinanceContext(
                execution_id="e1",
                instrument_id="AAA",
                side="buy",
                quantity=Decimal("10"),
                price=Decimal("100"),
                strategy_version_id=version_id,
                cycle_id="cyc-1",
            ),
            SimFillFinanceContext(
                execution_id="e2",
                instrument_id="AAA",
                side="sell",
                quantity=Decimal("10"),
                price=Decimal("105"),
                strategy_version_id=version_id,
                cycle_id="cyc-1",
            ),
        ]


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    _Store.calls = []
    monkeypatch.setattr(route_mod, "PostgresSimFillFinanceContextStore", _Store)


@pytest.mark.asyncio
async def test_reports_the_version_read_only_and_with_declared_gaps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _scope(_request: Any, _account_id: str | None) -> str:
        return "acc-1"

    monkeypatch.setattr(route_mod, "resolve_account_scope_or_default", _scope)

    dto = await get_auto_self_evaluation(
        request=None,  # type: ignore[arg-type]
        version="orb-1",
        session=_Session(),  # type: ignore[arg-type]
        account_id=None,
    )

    assert _Store.calls == [("orb-1", "acc-1")], "la lectura se acota a la cuenta resuelta"
    assert dto.key == "autoSelfEvaluation"
    assert dto.readOnly is True and dto.version == "orb-1"
    assert dto.trades == 1
    assert dto.byStrategy[0].strategyVersion == "orb-1"
    assert dto.byStrategy[0].realizedPnl == "50.000000"
    assert dto.byStrategy[0].expectancyCurrency == "50.000000"
    assert dto.byStrategy[0].riskMeasurement == "UNKNOWN"
    assert dto.byStrategy[0].netExpectancyR is None
    assert dto.byStrategy[0].netRMeasurement == "UNKNOWN"
    assert dto.byStrategy[0].cyclesWithoutCost == 1
    assert dto.byStrategy[0].mfeR is None and dto.byStrategy[0].maeR is None
    assert dto.byStrategy[0].slippageCurrency is None
    # AUTO-9: el cruce `strategy × regime` viaja por la ruta con el régimen AUSENTE como
    # cubo propio (los fills de este test no declaran régimen), no repartido ni inventado.
    assert [cell.regime for cell in dto.byRegime] == ["UNKNOWN"]
    assert dto.byRegime[0].cycles == 1
    assert dto.byRegime[0].netExpectancyR is None
    assert dto.byRegime[0].cyclesWithoutRisk == 1
    assert dto.cyclesWithoutRegime == 1
    assert dto.funnel["seen"] is None and dto.funnel["closed"] is False
    assert dto.decisive is False
    assert dto.errors == []


@pytest.mark.asyncio
async def test_without_account_scope_it_declares_the_gap_instead_of_reading_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_scope(_request: Any, _account_id: str | None) -> None:
        return None

    monkeypatch.setattr(route_mod, "resolve_account_scope_or_default", _no_scope)

    dto = await get_auto_self_evaluation(
        request=None,  # type: ignore[arg-type]
        version="orb-1",
        session=_Session(),  # type: ignore[arg-type]
        account_id=None,
    )

    assert _Store.calls == [], "sin cuenta visible NO se lee global"
    assert dto.errors == ["no_account_scope"]
    assert dto.cycles == 0 and dto.byStrategy == [] and dto.byRegime == []
    assert dto.measurement == "UNKNOWN"
    assert dto.decisive is False
