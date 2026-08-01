"""Observed Profile — refresh desde Decision Memory (no muta Declared)."""

from __future__ import annotations

from bolsa_application.investor_profiles import _samples_from_memory_payloads


def test_samples_from_accepted_and_rejected_memory():
    samples = _samples_from_memory_payloads(
        [
            {"outcome": "accepted", "reasons": ["Policy PASS"]},
            {"outcome": "rejected", "reasons": ["MaxRiskPerTrade: 3% vs 1%"]},
        ]
    )
    assert len(samples) == 2
    assert samples[0].followed_stop is True
    assert samples[1].policy_breach is True
    assert samples[1].impulsivity_flag is True
