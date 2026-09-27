"""V2.83 · AUTO-MATERIAL-11 — AUDITORÍA de la ventana: contratos puros (sin red ni PostgreSQL).

Lo que se fija aquí:

* El TOTAL acumula **sólo** los días medidos y publica la cobertura de CADA campo: un hueco nunca se
  suma como ``0``, y un TOTAL sobre días incompletos se marca ``partial``.
* Las tasas se DERIVAN del funnel; sin días medidos (o con denominador ``0``) el ``rate`` es ``None``,
  nunca un ``0.0`` fabricado. La ``fillRate`` sólo existe con la evidencia del runner.
* Los avisos (contrato de razones, par A/B, precio faltante) se publican, no se ocultan.
* ``enrich_rows_with_evidence`` rellena **sólo** los huecos declarados y jamás sobrescribe lo medido.
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.market_operability import (
    ENTRY_DECISION_EVENT,
    STATE_UNRESOLVED,
)
from bolsa_application.operability_audit import (
    AUDIT_TOTAL_FIELDS,
    enrich_rows_with_evidence,
    render_window_audit,
    window_audit,
    window_rates,
    window_totals,
)
from bolsa_application.operability_window import build_window_row, window_gate


def _entry(*reason_codes: str) -> dict[str, Any]:
    return {"payload": {"event": ENTRY_DECISION_EVENT, "reasonCodes": list(reason_codes)}}


def _cycle(cycle_id: str, *, pnl: float = 10.0, risk: float = 5.0, regime: str = "trend_up") -> dict[str, Any]:
    return {
        "cycleId": cycle_id,
        "pnl": pnl,
        "riskAmount": risk,
        "regime": regime,
        "strategyVersion": "vA",
        "instrumentId": "AAA",
    }


_EVIDENCE = {
    "watchSize": 8,
    "priceSources": {"a": "market_close", "b": "market_live", "c": "missing"},
    "sample": {"pricesServed": 2},
    "marketRegime": {"counts": {"trend_down": 6, "range": 2}},
    "turnTotals": {"orders": 2},
    "pairActive": True,
}


# ── window_totals ──────────────────────────────────────────────────────────────────────────────


def test_window_totals_sums_only_measured_days_and_declares_coverage() -> None:
    rows = [
        build_window_row("2026-09-24", entries=[_entry("approved")], cycles=[_cycle("c1")], fills=1),
        build_window_row("2026-09-27"),  # día NO medido
    ]
    totals = window_totals(rows)
    assert totals["daysTotal"] == 2
    assert totals["daysMeasured"] == 1
    assert totals["counts"]["decided"] == 1
    assert totals["counts"]["fills"] == 1
    assert totals["counts"]["measurableCycles"] == 1
    assert totals["coverage"]["decided"] == {
        "days": 1,
        "ofDays": 1,
        "measured": True,
        "partial": False,
    }
    assert totals["regimes"] == ["trend_up"]
    assert totals["instruments"] == ["AAA"]


def test_window_totals_never_adds_a_gap_as_zero_and_marks_partial() -> None:
    """Un día medido sin ``fills`` NO aporta un ``0``: el campo queda declarado parcial, no cerrado."""
    rows = [
        build_window_row("2026-09-24", entries=[_entry("approved")], cycles=[_cycle("c1")], fills=1),
        build_window_row("2026-09-25", entries=[_entry("regime_invalid")], fills=None),
    ]
    totals = window_totals(rows)
    assert totals["daysMeasured"] == 2
    assert totals["counts"]["fills"] == 1  # sólo el día que lo midió
    assert totals["coverage"]["fills"] == {
        "days": 1,
        "ofDays": 2,
        "measured": True,
        "partial": True,
    }
    assert totals["coverage"]["measurableCycles"]["days"] == 2
    assert totals["coverage"]["measurableCycles"]["partial"] is False


def test_window_totals_without_any_measured_day_declares_the_gap() -> None:
    totals = window_totals([build_window_row("2026-09-27")])
    assert totals["daysMeasured"] == 0
    for field in AUDIT_TOTAL_FIELDS:
        assert totals["coverage"][field]["measured"] is False
    assert totals["rSum"] is None
    assert totals["coverage"]["rSum"]["measured"] is False


def test_window_totals_uses_the_same_measured_default_as_the_census() -> None:
    """Fila del censo (``v2_77``) SIN clave ``measured``: se lee como medida, igual que el instrumento."""
    census_row = {"day": "2026-09-26", "decided": 64, "vetoCounted": 64, "state": "vetoed"}
    totals = window_totals([census_row])
    assert totals["daysMeasured"] == 1
    assert totals["counts"]["decided"] == 64
    assert totals["coverage"]["decided"] == {
        "days": 1,
        "ofDays": 1,
        "measured": True,
        "partial": False,
    }


def test_window_totals_aggregates_the_funnel_step_by_step() -> None:
    evidence = dict(_EVIDENCE)
    rows = [
        build_window_row("2026-09-24", entries=[_entry("approved")], fills=0, evidence=evidence),
        build_window_row("2026-09-25", entries=[_entry("approved")], fills=0, evidence=evidence),
    ]
    funnel = window_totals(rows)["funnel"]
    assert funnel["universe"]["count"] == 16
    assert funnel["universe"]["days"] == 2
    assert funnel["orders"]["count"] == 4
    assert funnel["signals"]["count"] == 2


# ── window_rates ───────────────────────────────────────────────────────────────────────────────


def test_window_rates_follow_the_funnel_steps() -> None:
    rows = [
        build_window_row(
            "2026-09-24",
            entries=[
                _entry("regime_invalid", "top_n_excluded", "risk_budget_exceeded"),
                _entry("approved"),
            ],
            fills=0,
        )
    ]
    rates = window_rates(rows)
    # signals=4, topN=3, risk=2, reservation=2 (ningún veto de reserva)
    assert rates["topNExclusionRate"]["numerator"] == 1
    assert rates["topNExclusionRate"]["denominator"] == 4
    assert rates["topNExclusionRate"]["rate"] == pytest.approx(0.25)
    assert rates["riskRejectionRate"]["rate"] == pytest.approx(1 / 3)
    assert rates["reservationFailureRate"]["rate"] == 0.0
    assert rates["reservationFailureRate"]["coveredDays"] == 1
    assert rates["topNExclusionRate"]["source"].startswith("funnel")


def test_window_rates_are_none_without_a_measurable_denominator() -> None:
    """Un día no medido no aporta ni numerador ni denominador: hueco, no ``0.0``."""
    rates = window_rates([build_window_row("2026-09-27")])
    for name in ("topNExclusionRate", "riskRejectionRate", "reservationFailureRate"):
        assert rates[name]["rate"] is None
        assert rates[name]["numerator"] is None
        assert rates[name]["coveredDays"] == 0

    zero_day = window_rates([build_window_row("2026-09-27", entries=[], fills=0)])
    assert zero_day["topNExclusionRate"]["coveredDays"] == 1
    assert zero_day["topNExclusionRate"]["rate"] is None


def test_fill_rate_requires_the_runner_evidence() -> None:
    """Sin ``--forward`` no hay ``orders``: la ``fillRate`` se declara ``n/d``, no se inventa."""
    without = window_rates([build_window_row("2026-09-24", entries=[_entry("approved")], fills=1)])
    assert without["fillRate"]["rate"] is None
    assert without["fillRate"]["coveredDays"] == 0

    with_evidence = window_rates(
        [
            build_window_row(
                "2026-09-24", entries=[_entry("approved")], fills=1, evidence=dict(_EVIDENCE)
            )
        ]
    )
    assert with_evidence["fillRate"]["numerator"] == 1
    assert with_evidence["fillRate"]["denominator"] == 2
    assert with_evidence["fillRate"]["rate"] == pytest.approx(0.5)


def test_cycle_rate_and_unresolved_rate() -> None:
    row = build_window_row("2026-09-24", entries=[_entry("approved")], cycles=[], fills=0)
    assert row["state"] == STATE_UNRESOLVED
    rates = window_rates([row])
    assert rates["unresolvedRate"]["numerator"] == 1
    assert rates["unresolvedRate"]["denominator"] == 1
    assert rates["unresolvedRate"]["rate"] == pytest.approx(1.0)
    # fills=0 ⇒ denominador 0 ⇒ cycleRate declarada None (no un 0.0 fabricado)
    assert rates["cycleRate"]["rate"] is None
    assert rates["cycleRate"]["coveredDays"] == 1


# ── window_audit ───────────────────────────────────────────────────────────────────────────────


def test_window_audit_publishes_totals_rates_gate_and_funnel() -> None:
    rows = [
        build_window_row("2026-09-24", entries=[_entry("approved")], cycles=[_cycle("c1")], fills=1),
        build_window_row("2026-09-25", entries=[_entry("regime_invalid")], fills=0),
    ]
    audit = window_audit(rows)
    assert audit["daysTotal"] == 2
    assert audit["daysMeasured"] == 2
    assert set(audit) == {"daysTotal", "daysMeasured", "totals", "rates", "funnel", "gate", "warnings"}
    assert audit["gate"] == window_gate(rows)
    assert audit["gate"]["verdict"] == "INCONCLUSIVE"


def test_window_audit_warns_on_a_contract_violation_and_the_missing_pair() -> None:
    rows = [
        build_window_row("2026-09-24", entries=[_entry("nuevo_motivo")], fills=0),
    ]
    codes = {warning["code"] for warning in window_audit(rows)["warnings"]}
    assert "reason_contract" in codes
    assert "pair_unmeasured" in codes  # sin --forward: pairActive n/d (no se deduce de pairCapable)


def test_window_audit_warns_when_the_pair_is_capable_but_not_active() -> None:
    evidence = {**_EVIDENCE, "pairActive": False, "secondaryActive": False}
    row = build_window_row("2026-09-24", entries=[_entry("approved")], fills=0, evidence=evidence)
    warnings = window_audit([row])["warnings"]
    assert {warning["code"] for warning in warnings} == {"pair_not_active", "price_missing"}


def test_render_window_audit_is_deterministic_and_marks_the_holes() -> None:
    rows = [
        build_window_row("2026-09-24", entries=[_entry("approved")], cycles=[_cycle("c1")], fills=1),
        build_window_row("2026-09-27"),
    ]
    rendered = render_window_audit(rows, {"header": {"account": "acc-1", "versions": ["vA"]}})
    assert rendered == render_window_audit(rows, {"header": {"account": "acc-1", "versions": ["vA"]}})
    assert "D1" in rendered
    assert "D2" in rendered
    assert "TOTAL acumulado" in rendered
    assert "Funnel agregado" in rendered
    assert "Tasas de operabilidad" in rendered
    assert "AVISOS" in rendered
    assert "topNExclusionRate" in rendered
    assert "n/d" in rendered  # los huecos se declaran
    assert "acc-1" in rendered


# ── enrich_rows_with_evidence ──────────────────────────────────────────────────────────────────


def test_enrich_rows_fills_only_the_declared_gaps() -> None:
    row = build_window_row("2026-09-24", entries=[_entry("approved")], fills=1)
    assert row["funnel"]["orders"]["count"] is None
    assert row["pairActive"] is None

    enriched = enrich_rows_with_evidence([row], {"2026-09-24": dict(_EVIDENCE)})
    assert enriched[0]["funnel"]["orders"]["count"] == 2
    assert enriched[0]["pairActive"] is True
    assert enriched[0]["symbolsObserved"] == 8
    assert enriched[0]["priceSources"] == {"live": 1, "close": 1, "missing": 1}
    # lo medido no se toca
    assert enriched[0]["fills"] == 1
    assert enriched[0]["funnel"]["signals"]["count"] == 1


def test_enrich_rows_leaves_a_day_without_evidence_intact() -> None:
    row = build_window_row("2026-09-25", entries=[_entry("approved")], fills=0)
    enriched = enrich_rows_with_evidence([row], {})
    assert enriched[0]["funnel"]["orders"]["count"] is None
    assert enriched[0]["pairActive"] is None


def test_enrich_rows_never_overwrites_a_measured_pair() -> None:
    row = build_window_row(
        "2026-09-24", entries=[_entry("approved")], fills=0, evidence=dict(_EVIDENCE)
    )
    assert row["pairActive"] is True
    enriched = enrich_rows_with_evidence([row], {"2026-09-24": {"pairActive": False}})
    assert enriched[0]["pairActive"] is True


def test_enrich_rows_never_overwrites_a_measured_funnel() -> None:
    """El funnel YA medido no se pisa al re-enriquecer: sólo se rellenan los escalones ``None``.

    Regresión de ``OBS-6`` (auditoría externa de ``v2.83.1-beta``): ``enrich`` reconstruía el funnel
    ENTERO con la evidencia nueva, así que un escalón medido (``universe``/``orders``) se sobrescribía.
    """
    row = build_window_row(
        "2026-09-24", entries=[_entry("approved")], fills=0, evidence=dict(_EVIDENCE)
    )
    assert row["funnel"]["universe"]["count"] == 8
    assert row["funnel"]["orders"]["count"] == 2

    # Misma jornada, evidencia DISTINTA: los escalones ya medidos deben sobrevivir.
    enlarged = {"watchSize": 999, "turnTotals": {"orders": 99}}
    enriched = enrich_rows_with_evidence([row], {"2026-09-24": enlarged})
    assert enriched[0]["funnel"]["universe"]["count"] == 8
    assert enriched[0]["funnel"]["orders"]["count"] == 2
    assert enriched[0]["funnel"]["signals"]["count"] == 1


def test_window_totals_funnel_ignores_unmeasured_rows() -> None:
    """Un día NO medido con evidencia NO suma en el funnel agregado (coherente con ``counts``/``rSum``).

    Regresión de ``OBS-7``: el bloque ``funnel`` iteraba ``rows`` (todas) en vez de ``measured_rows``,
    así que los escalones superiores de un día ``measured=False`` engordaban el TOTAL.
    """
    measured = build_window_row(
        "2026-09-24", entries=[_entry("approved")], fills=0, evidence=dict(_EVIDENCE)
    )
    unmeasured = build_window_row("2026-09-25", evidence=dict(_EVIDENCE))
    assert unmeasured["measured"] is False
    assert unmeasured["funnel"]["universe"]["count"] == 8  # la fila SÍ trae el escalón...

    totals = window_totals([measured, unmeasured])
    assert totals["daysMeasured"] == 1
    assert totals["funnel"]["universe"]["count"] == 8  # ...pero NO se suma al TOTAL
    assert totals["funnel"]["universe"]["days"] == 1
    assert totals["funnel"]["orders"]["count"] == 2
