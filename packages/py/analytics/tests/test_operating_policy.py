"""V1.35 — OperatingPolicy skeleton."""

from bolsa_analytics.cognitive.operating_policy import resolve_operating_policy


def test_resolve_operating_policy_moderate() -> None:
    policy = resolve_operating_policy("moderate")
    assert policy.template_id == "moderate"
    assert policy.exit.t2_reduce_fraction == 0.3
    assert policy.concentration.max_sector_exposure_pct == 30.0


def test_resolve_operating_policy_conservative_exit() -> None:
    policy = resolve_operating_policy("conservative")
    assert policy.exit.t1_reduce_fraction == 0.5
    assert policy.trailing.ratchet_only is True
