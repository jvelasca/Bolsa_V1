from datetime import UTC, datetime, timedelta

from bolsa_analytics.signals.fundamental_gate import (
    build_fundamental_gate,
    definition_has_fundamental_gate,
    fundamentals_need_refresh,
    passes_fundamental_gate,
)


def test_definition_has_fundamental_gate() -> None:
    assert definition_has_fundamental_gate(
        {"hybrid": {"fundamentalGate": {"operator": "all", "conditions": []}}}
    ) is False
    assert definition_has_fundamental_gate(
        {
            "hybrid": {
                "fundamentalGate": {
                    "operator": "all",
                    "conditions": [{"metric": "trailingPe", "operator": "lte", "value": 20}],
                }
            }
        }
    ) is True


def test_fundamentals_need_refresh_missing() -> None:
    assert fundamentals_need_refresh(None, 30) is True


def test_fundamentals_need_refresh_fresh() -> None:
    fetched_at = datetime.now(UTC).isoformat()
    assert fundamentals_need_refresh({"fetchedAt": fetched_at}, 30) is False


def test_fundamentals_need_refresh_stale() -> None:
    stale = (datetime.now(UTC) - timedelta(days=45)).isoformat()
    assert fundamentals_need_refresh({"fetchedAt": stale}, 30) is True


def test_fundamentals_thin_for_cognitive() -> None:
    from bolsa_analytics.signals.fundamental_gate import fundamentals_thin_for_cognitive

    assert fundamentals_thin_for_cognitive(None) is True
    assert fundamentals_thin_for_cognitive({"marketCap": 1e9, "trailingPe": 20}) is True
    assert fundamentals_thin_for_cognitive({"roe": 0.15}) is False


def _fresh(**overrides):
    base = {
        "fetchedAt": datetime.now(UTC).isoformat(),
        "sector": "Technology",
        "trailingPe": 18.0,
        "marketCap": 5e9,
        "roe": 0.2,
        "debtToEquity": 0.5,
        "altmanZ": 3.5,
        "fcfYield": 0.04,
        "currentRatio": 1.5,
    }
    base.update(overrides)
    return base


def test_passes_gate_roe_and_altman() -> None:
    gate = build_fundamental_gate(min_roe=0.15, min_altman_z=2.99)
    assert gate is not None
    definition = {"hybrid": {"fundamentalGate": gate}}
    ok, reason = passes_fundamental_gate(definition, _fresh())
    assert ok and reason is None
    ok2, reason2 = passes_fundamental_gate(definition, _fresh(roe=0.05))
    assert not ok2 and reason2


def test_passes_gate_any_operator() -> None:
    gate = {
        "operator": "any",
        "conditions": [
            {"metric": "roe", "operator": "gte", "value": 0.5},
            {"metric": "altmanZ", "operator": "gte", "value": 2.99},
        ],
        "maxAgeDays": 30,
    }
    definition = {"hybrid": {"fundamentalGate": gate}}
    ok, _ = passes_fundamental_gate(definition, _fresh(roe=0.1, altmanZ=3.2))
    assert ok


def test_unknown_metric_fails_condition() -> None:
    gate = {
        "operator": "all",
        "conditions": [{"metric": "notARealMetric", "operator": "gte", "value": -2}],
        "maxAgeDays": 30,
    }
    definition = {"hybrid": {"fundamentalGate": gate}}
    ok, _ = passes_fundamental_gate(definition, _fresh(beneishM=-3))
    assert not ok  # métrica no permitida


def test_passes_gate_roic_and_beneish() -> None:
    gate = build_fundamental_gate(min_roic=0.08, max_beneish_m=-1.78)
    assert gate is not None
    definition = {"hybrid": {"fundamentalGate": gate}}
    ok, _ = passes_fundamental_gate(
        definition, _fresh(roic=0.12, beneishM=-2.5)
    )
    assert ok
    ok_hi_m, _ = passes_fundamental_gate(
        definition, _fresh(roic=0.12, beneishM=-1.0)
    )
    assert not ok_hi_m


def test_passes_gate_piotroski() -> None:
    gate = build_fundamental_gate(min_piotroski=7)
    assert gate is not None
    definition = {"hybrid": {"fundamentalGate": gate}}
    ok, reason = passes_fundamental_gate(definition, _fresh(piotroski=8))
    assert ok and reason is None
    ok_low, _ = passes_fundamental_gate(definition, _fresh(piotroski=5))
    assert not ok_low
    # null / ausente = no pasa (sin score parcial)
    ok_missing, _ = passes_fundamental_gate(definition, _fresh(piotroski=None))
    assert not ok_missing


def test_passes_gate_dcf_upside() -> None:
    gate = build_fundamental_gate(min_dcf_upside=0.1)
    assert gate is not None
    definition = {"hybrid": {"fundamentalGate": gate}}
    ok, _ = passes_fundamental_gate(definition, _fresh(dcfUpside=0.25))
    assert ok
    ok2, _ = passes_fundamental_gate(definition, _fresh(dcfUpside=0.05))
    assert not ok2
    ok3, _ = passes_fundamental_gate(definition, _fresh(dcfUpside=None))
    assert not ok3
