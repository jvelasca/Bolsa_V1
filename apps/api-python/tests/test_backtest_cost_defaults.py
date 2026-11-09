"""Defaults de coste de backtests/estrategias: el silencio deja de significar 0 bps.

Un backtest «gratis» era un techo optimista frente al coste que el propio motor mide
(~12,7 bps por lado). El default debe ser el MISMO que el manifiesto de campaña
(``CampaignCosts`` 10/5/2), y un ``0`` explícito debe seguir siendo válido.
"""

from __future__ import annotations

from bolsa_api.api.v1.routes import backtests as backtests_route
from bolsa_api.api.v1.routes import strategies as strategies_route
from bolsa_api.schemas.backtests import BacktestRunRequestDto
from bolsa_api.schemas.strategies import CreateStrategyFromPresetRequestDto
from bolsa_application.campaign_manifest import CampaignCosts


def test_route_defaults_are_the_campaign_manifest_costs() -> None:
    manifest = CampaignCosts()

    assert manifest.commission_bps == 10
    assert manifest.slippage_bps == 5
    assert manifest.spread_bps == 2
    assert backtests_route._DEFAULT_COSTS.commission_bps == manifest.commission_bps
    assert backtests_route._DEFAULT_COSTS.slippage_bps == manifest.slippage_bps
    assert backtests_route._DEFAULT_COSTS.spread_bps == manifest.spread_bps
    assert strategies_route._DEFAULT_COSTS.commission_bps == manifest.commission_bps
    assert strategies_route._DEFAULT_COSTS.slippage_bps == manifest.slippage_bps


def test_an_absent_cost_becomes_the_campaign_default_and_zero_is_respected() -> None:
    assert backtests_route._cost_bps(None, 10) == 10
    assert backtests_route._cost_bps(0, 10) == 0
    assert backtests_route._cost_bps(7, 10) == 7
    assert strategies_route._cost_bps(None, 5) == 5
    assert strategies_route._cost_bps(0, 5) == 0


def test_http_dtos_keep_absent_costs_as_none_so_the_route_can_default() -> None:
    backtest = BacktestRunRequestDto(instrumentId="X")
    strategy = CreateStrategyFromPresetRequestDto(name="n", presetKey="sma_crossover")

    assert backtest.commission_bps is None
    assert backtest.slippage_bps is None
    assert backtest.spread_bps is None
    assert strategy.commission_bps is None
    assert strategy.slippage_bps is None
