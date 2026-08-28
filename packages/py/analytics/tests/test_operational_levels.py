"""V1.26 — geometría operativa única (paridad con TS)."""

from bolsa_analytics.cognitive.operational_invariants import adverse_exposure
from bolsa_analytics.cognitive.operational_levels import validate_operational_levels


def test_long_ok() -> None:
    v = validate_operational_levels(
        direction="long", entry=100.0, stop=95.0, target1=110.0, target2=120.0
    )
    assert v["ok"] is True
    assert v["reason"] is None
    assert v["riskDistance"] == 5.0


def test_long_stop_wrong_side() -> None:
    v = validate_operational_levels(direction="long", entry=100.0, stop=110.0)
    assert v["ok"] is False
    assert v["reason"] == "stop_wrong_side"


def test_short_stop_wrong_side() -> None:
    v = validate_operational_levels(direction="short", entry=100.0, stop=90.0)
    assert v["ok"] is False
    assert v["reason"] == "stop_wrong_side"


def test_short_ok() -> None:
    v = validate_operational_levels(
        direction="short", entry=100.0, stop=110.0, target1=90.0, target2=80.0
    )
    assert v["ok"] is True
    assert v["riskDistance"] == 10.0


def test_targets_invalid() -> None:
    v = validate_operational_levels(
        direction="long", entry=100.0, stop=95.0, target1=90.0
    )
    assert v["ok"] is False
    assert v["reason"] == "targets_invalid"


def test_missing_direction_or_non_positive() -> None:
    assert (
        validate_operational_levels(direction="none", entry=100.0, stop=95.0)[
            "reason"
        ]
        == "risk_non_positive"
    )
    assert (
        validate_operational_levels(direction="long", entry=100.0, stop=0.0)["reason"]
        == "risk_non_positive"
    )


def test_adverse_exposure_is_signed() -> None:
    assert adverse_exposure("long", 100.0, 95.0) == 5.0
    assert adverse_exposure("long", 100.0, 110.0) == 0.0
    assert adverse_exposure("short", 100.0, 110.0) == 10.0
    assert adverse_exposure("short", 100.0, 90.0) == 0.0
