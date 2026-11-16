"""RD-1 — una sola fricción de referencia, verificada contra los umbrales.

El lab mide con costes; el gate P1 exige un suelo de coste declarado. Si los tres sitios que
declaran bps (``REFERENCE_COSTS``, ``CampaignCosts``, ``BaselineCosts``) divergen, el gate
podría aprobar una simulación con una fricción que el repo no considera realista. Este test
es el anti-drift: falla si alguien cambia un número en un solo sitio.
"""

from bolsa_analytics.backtest import REFERENCE_COSTS, round_trip_cost_bps
from bolsa_application.baseline_arms import BASELINE_THRESHOLDS, BaselineCosts
from bolsa_application.campaign_manifest import CampaignCosts


def test_reference_costs_equal_baseline_and_campaign_costs() -> None:
    reference = REFERENCE_COSTS
    baseline = BaselineCosts()
    campaign = CampaignCosts()
    assert (reference.commission_bps, reference.slippage_bps, reference.spread_bps) == (
        campaign.commission_bps,
        campaign.slippage_bps,
        campaign.spread_bps,
    )
    assert (baseline.commission_bps, baseline.slippage_bps, baseline.spread_bps) == (
        campaign.commission_bps,
        campaign.slippage_bps,
        campaign.spread_bps,
    )


def test_reference_round_trip_is_32_bps_and_clears_the_gate_floor() -> None:
    assert round_trip_cost_bps(REFERENCE_COSTS) == 32.0
    assert BaselineCosts().round_trip_bps == 32.0
    floor = float(BASELINE_THRESHOLDS["minRoundTripCostBps"])
    assert floor == 22.0
    assert round_trip_cost_bps(REFERENCE_COSTS) > floor
