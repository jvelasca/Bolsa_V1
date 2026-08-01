"""FIE F2.2 — sector bands + allowlist sector."""

from bolsa_analytics.signals.fundamental_gate import (
    build_fundamental_gate,
    passes_fundamental_gate,
)
from bolsa_analytics.signals.sector_bands import (
    FUND_SECTOR_BANDS_VERSION,
    apply_sector_bands_to_conditions,
    resolve_sector_band_profile,
)
from datetime import datetime, timezone


def _fresh(**overrides):
    base = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "sector": "Technology",
        "trailingPe": 30.0,
        "marketCap": 5e9,
        "roe": 0.15,
        "debtToEquity": 0.5,
        "altmanZ": 3.5,
        "fcfYield": 0.04,
        "currentRatio": 1.5,
        "operatingMargin": 0.15,
    }
    base.update(overrides)
    return base


def test_resolve_technology_overlay():
    known, profile, key = resolve_sector_band_profile("Technology")
    assert known and key == "Technology"
    assert profile["trailingPe"]["value"] == 40.0
    assert profile["roe"]["value"] == 0.12


def test_financial_skips_altman():
    known, profile, _ = resolve_sector_band_profile("Financial Services")
    assert known
    assert profile["altmanZ"] == "skip"
    assert profile["debtToEquity"] == "skip"


def test_apply_bands_skips_and_rewrites():
    conditions = [
        {"metric": "trailingPe", "operator": "lte", "value": 25},
        {"metric": "altmanZ", "operator": "gte", "value": 1.8},
        {"metric": "piotroski", "operator": "gte", "value": 7},
    ]
    out = apply_sector_bands_to_conditions(
        conditions,
        sector="Financial Services",
        sector_bands_version=FUND_SECTOR_BANDS_VERSION,
    )
    metrics = {c["metric"] for c in out}
    assert "altmanZ" not in metrics
    assert "piotroski" in metrics
    pe = next(c for c in out if c["metric"] == "trailingPe")
    assert pe["value"] == 15.0
    assert pe.get("sectorBand") is True


def test_unknown_sector_keeps_ui_thresholds():
    conditions = [{"metric": "trailingPe", "operator": "lte", "value": 18}]
    out = apply_sector_bands_to_conditions(
        conditions,
        sector="Unknown Sector XYZ",
        sector_bands_version=FUND_SECTOR_BANDS_VERSION,
    )
    assert out[0]["value"] == 18


def test_build_gate_use_sector_bands_seeds_defaults():
    gate = build_fundamental_gate(use_sector_bands=True)
    assert gate is not None
    assert gate["sectorBandsVersion"] == FUND_SECTOR_BANDS_VERSION
    metrics = {c["metric"] for c in gate["conditions"]}
    assert "roe" in metrics and "trailingPe" in metrics


def test_tech_passes_with_higher_pe_under_bands():
    """PE=30 falla con umbral UI 25, pero Technology band permite ≤40."""
    gate = {
        "operator": "all",
        "conditions": [{"metric": "trailingPe", "operator": "lte", "value": 25}],
        "maxAgeDays": 30,
        "sectorBandsVersion": FUND_SECTOR_BANDS_VERSION,
    }
    definition = {"hybrid": {"fundamentalGate": gate}}
    ok, reason = passes_fundamental_gate(definition, _fresh(trailingPe=30, sector="Technology"))
    assert ok and reason is None


def test_tech_fails_same_pe_without_bands():
    gate = {
        "operator": "all",
        "conditions": [{"metric": "trailingPe", "operator": "lte", "value": 25}],
        "maxAgeDays": 30,
    }
    definition = {"hybrid": {"fundamentalGate": gate}}
    ok, _ = passes_fundamental_gate(definition, _fresh(trailingPe=30, sector="Technology"))
    assert not ok


def test_bank_skips_altman_condition():
    gate = {
        "operator": "all",
        "conditions": [
            {"metric": "altmanZ", "operator": "gte", "value": 2.99},
            {"metric": "roe", "operator": "gte", "value": 0.05},
        ],
        "maxAgeDays": 30,
        "sectorBandsVersion": FUND_SECTOR_BANDS_VERSION,
    }
    definition = {"hybrid": {"fundamentalGate": gate}}
    # Altman bajo / null — con bandas Financial se omite Altman
    ok, _ = passes_fundamental_gate(
        definition,
        _fresh(sector="Financial Services", altmanZ=0.5, roe=0.1, operatingMargin=0.2),
    )
    assert ok


def test_sector_allowlist():
    gate = build_fundamental_gate(min_roe=0.1, sectors=["Technology", "Healthcare"])
    definition = {"hybrid": {"fundamentalGate": gate}}
    ok, _ = passes_fundamental_gate(definition, _fresh(sector="Technology"))
    assert ok
    ok2, reason = passes_fundamental_gate(definition, _fresh(sector="Energy"))
    assert not ok2 and reason and "Sector" in reason
