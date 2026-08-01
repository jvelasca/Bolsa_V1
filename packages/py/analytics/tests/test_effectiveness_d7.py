"""RFC-008 D7 — Confidence Lifecycle + Observed + Efectividad."""

from __future__ import annotations

from bolsa_analytics.cognitive import (
    BehaviorTradeSample,
    ConfidenceEvent,
    DeclaredInvestorProfile,
    StatisticalSuiteResult,
    TrialsLog,
    apply_confidence_event,
    apply_time_decay,
    build_edge_report,
    build_effectiveness_summary,
    build_memory_entry,
    observe_investor_profile,
    open_confidence_state,
)


def test_confidence_lifecycle_invalidator_tightens_then_exits():
    state = open_confidence_state(
        decision_id="DEC-1",
        instrument_id="AAPL",
        confidence_0=0.8,
        expires_at="2099-01-01T00:00:00Z",
    )
    assert state.hint == "hold"
    state = apply_confidence_event(
        state,
        ConfidenceEvent(
            kind="invalidator",
            delta=-0.25,
            claim="exhaustion",
            at="2026-07-23T12:00:00Z",
        ),
    )
    assert state.confidence == 0.55
    assert state.hint == "tighten"
    state = apply_confidence_event(
        state,
        ConfidenceEvent(
            kind="regime_change",
            delta=-0.4,
            claim="crisis",
            at="2026-07-23T13:00:00Z",
        ),
        hard_exit=True,
    )
    assert state.hint == "exit"
    assert state.confidence < 0.25


def test_confidence_time_decay_and_expiry():
    state = open_confidence_state(
        decision_id="DEC-2",
        instrument_id="MSFT",
        confidence_0=0.7,
        expires_at="2026-07-23T12:00:00Z",
    )
    state = apply_time_decay(
        state,
        half_life_hours=24,
        elapsed_hours=24,
        at="2026-07-23T11:00:00Z",
    )
    assert state.confidence < 0.7
    assert state.expired is False
    state = apply_confidence_event(
        state,
        ConfidenceEvent(
            kind="time_decay",
            delta=0.0,
            claim="tick past expiry",
            at="2026-07-23T13:00:00Z",
        ),
    )
    assert state.expired is True
    assert state.hint == "expire"


def test_observed_does_not_mutate_declared_and_flags_divergence():
    declared = DeclaredInvestorProfile(
        horizon="swing",
        objectives=("growth",),
        risk_tolerance="low",
        experience="novice",
        max_acceptable_loss_pct=0.5,
    )
    obs = observe_investor_profile(
        declared,
        [
            BehaviorTradeSample("buy", 1.0, 3.0, False, impulsivity_flag=True),
            BehaviorTradeSample("buy", 2.0, 2.5, False, policy_breach=True),
            BehaviorTradeSample("sell", 3.0, 2.0, True, impulsivity_flag=True),
        ],
    )
    assert obs.sample_trade_count == 3
    assert obs.diverges_from_declared is True
    assert obs.diverges_from_policy is True
    assert declared.risk_tolerance == "low"  # intacto
    assert obs.impulsivity_score is not None and obs.impulsivity_score >= 0.35


def test_observed_aligned_when_disciplined():
    declared = DeclaredInvestorProfile(
        horizon="swing",
        objectives=("growth",),
        risk_tolerance="moderate",
        experience="intermediate",
        max_acceptable_loss_pct=1.5,
    )
    obs = observe_investor_profile(
        declared,
        [
            BehaviorTradeSample("buy", 48, 0.8, True),
            BehaviorTradeSample("sell", 72, 1.0, True),
        ],
    )
    assert obs.diverges_from_declared is False
    assert obs.diverges_from_policy is False
    assert obs.discipline_score is not None and obs.discipline_score >= 0.9


def test_effectiveness_summary_skill_band():
    log = TrialsLog(strategy_family_ref="fam")
    for i in range(10):
        log.record(f"h{i}", f"p{i}", sharpe_is=1.0)
    suite = StatisticalSuiteResult(
        trials_n=log.trials_n,
        walk_forward_efficiency=0.95,
        monte_carlo_p_value=0.01,
        psr=0.99,
        dsr=0.95,
        bootstrap_alpha_ci_lower=0.02,
        bootstrap_alpha_ci_upper=0.1,
        stress_survival_rate=0.95,
    )
    edge = build_edge_report("sig-1", suite)
    mem = [
        build_memory_entry(
            decision_id="d1",
            instrument_id="X",
            outcome="rejected",
            reasons=["blackout"],
            reevaluate_when=["window_closed"],
        )
    ]
    summary = build_effectiveness_summary(
        edge_report=edge,
        trials_log=log,
        memory_entries=mem,
    )
    assert summary.status == "ready"
    assert summary.band == "skill"
    assert summary.trials_n == 10
    assert summary.memory_rejected == 1
    assert summary.reevaluate_pending == 1
    assert "skill" in summary.headline.lower() or "Skill" in summary.headline


def test_effectiveness_empty_insufficient():
    s = build_effectiveness_summary()
    assert s.status == "insufficient_data"
    assert s.band is None
