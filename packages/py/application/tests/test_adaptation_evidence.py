"""Evidencia de adaptación (ADR-049): determinista, sin ceros y con huecos declarados."""

from __future__ import annotations

from bolsa_application.adaptation_evidence import (
    AdaptationObservation,
    build_adaptation_evidence,
)


def _obs(r: float | None, *, mae: float | None = None, mfe: float | None = None, driver: str | None = None) -> AdaptationObservation:
    return AdaptationObservation(realized_r=r, mae_r=mae, mfe_r=mfe, loss_driver=driver)


def test_insufficient_sample_declares_gap_and_leaves_metrics_unmeasured() -> None:
    evidence = build_adaptation_evidence(
        [_obs(0.5), _obs(-0.4)],
        regime="TREND",
        family="breakout",
        instrument="AAA",
        min_samples=12,
    )

    payload = evidence.to_dict()
    assert payload["measured"] is False
    assert payload["closedCycles"] == 2
    assert payload["expectancyR"] is None
    assert payload["hitRate"] is None
    assert payload["capture"] is None
    assert "insufficient_sample:2/12" in payload["gaps"]
    assert payload["lossDrivers"] == []


def test_unclosed_cycles_do_not_count_toward_sample() -> None:
    evidence = build_adaptation_evidence(
        [_obs(None), _obs(None), _obs(1.0)],
        regime="TREND",
        family="breakout",
        instrument="AAA",
        min_samples=2,
    )

    payload = evidence.to_dict()
    assert payload["cycles"] == 3
    assert payload["closedCycles"] == 1
    assert payload["measured"] is False


def test_metrics_and_drivers_are_computed_and_ordered() -> None:
    observations = [
        _obs(1.0, mae=-0.2, mfe=2.0, driver="b"),
        _obs(-0.5, mae=-0.9, mfe=0.5, driver="a"),
        _obs(-0.5, mae=-0.7, mfe=0.5, driver="a"),
        _obs(0.5, mae=-0.1, mfe=1.0, driver="b"),
    ]
    evidence = build_adaptation_evidence(
        observations,
        regime="TREND",
        family="breakout",
        instrument="AAA",
        failed_gates=["maxDrawdownPct"],
        artifact_refs=["docs/engineering/dia-d-evidencia-politica-2026-11-05.md"],
        min_samples=3,
    )

    payload = evidence.to_dict()
    assert payload["measured"] is True
    assert payload["closedCycles"] == 4
    assert payload["expectancyR"] == 0.125
    assert payload["hitRate"] == 0.5
    assert payload["avgMaeR"] == -0.475
    assert payload["avgMfeR"] == 1.0
    assert payload["capture"] == 0.125
    assert [driver["driver"] for driver in payload["lossDrivers"]] == ["a", "b"]
    assert payload["lossDrivers"][0]["cycles"] == 2
    assert payload["failedGates"] == ["maxDrawdownPct"]


def test_evidence_hash_is_deterministic_and_prefix_independent() -> None:
    observations = [_obs(0.7, mfe=1.4, driver="x") for _ in range(14)]
    kwargs = {
        "regime": "RANGE",
        "family": "meanrev",
        "instrument": "BBB",
        "failed_gates": ["minPositiveWindowPct"],
        "artifact_refs": ["ref:one"],
        "min_samples": 12,
    }

    first = build_adaptation_evidence(observations, **kwargs).to_dict()
    second = build_adaptation_evidence(list(observations), **kwargs).to_dict()
    longer = build_adaptation_evidence([*observations, _obs(0.1)], **kwargs).to_dict()

    assert first["hash"] == second["hash"]
    assert first["hash"] != longer["hash"]


def test_capture_is_unknown_when_no_positive_mfe() -> None:
    observations = [_obs(-1.0, mfe=0.0) for _ in range(3)]
    payload = build_adaptation_evidence(
        observations,
        regime="RANGE",
        family="meanrev",
        instrument="BBB",
        min_samples=3,
    ).to_dict()

    assert payload["measured"] is True
    assert payload["capture"] is None
