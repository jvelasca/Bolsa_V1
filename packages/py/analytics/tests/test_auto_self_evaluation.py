"""AUTO-7 — tests de la autoevaluación pura por ``strategyVersion`` (read-only).

Se verifica lo que hace útil al módulo: que agregue de verdad por versión y que **declare
sus huecos** en vez de rellenarlos. Los casos límite son el punto: embudo abierto sin
medición, motivo ausente, precio ausente, ciclo repetido, ciclo sin identidad y ciclo sin
versión. Ninguno de ellos puede convertirse en un ``0`` silencioso.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from bolsa_analytics.cognitive.auto_self_evaluation import (
    AUTO_SELF_EVALUATION_KEY,
    SELF_EVAL_CYCLE_WITHOUT_IDENTITY,
    SELF_EVAL_DRAWDOWN_SHARE_PROXY,
    SELF_EVAL_DUPLICATE_CYCLE,
    SELF_EVAL_FUNNEL_DURABLE_MISMATCH,
    SELF_EVAL_FUNNEL_SEEN_MISMATCH,
    SELF_EVAL_FUNNEL_UNBALANCED,
    SELF_EVAL_FUNNEL_UNKNOWN,
    SELF_EVAL_MISSING_INPUTS,
    SELF_EVAL_OPPORTUNITY_STATUS_UNKNOWN,
    SELF_EVAL_REJECTION_COST_UNMEASURED,
    SELF_EVAL_REJECTION_WITHOUT_REASON,
    SELF_EVAL_RISK_UNMEASURED,
    SELF_EVAL_SLIPPAGE_UNMEASURED,
    SELF_EVAL_THIN_SAMPLE,
    SELF_EVAL_UNVERSIONED_CYCLE,
    evaluate_auto_self_evaluation,
)


def _cycle(
    version: str = "orb-1",
    *,
    pnl: str | None = "100",
    cycle_id: str | None = None,
    closed_at: str | None = None,
    r: float | None = None,
    mfe: float | None = None,
    mae: float | None = None,
    slippage: str | None = None,
) -> dict[str, object]:
    """Ciclo mínimo con SOLO lo que el test declara (el resto queda ausente)."""
    row: dict[str, object] = {"strategyVersion": version}
    if pnl is not None:
        row["pnl"] = pnl
    if cycle_id is not None:
        row["cycleId"] = cycle_id
    if closed_at is not None:
        row["closedAt"] = closed_at
    if r is not None:
        row["rMultiple"] = r
    if mfe is not None or mae is not None:
        row["mfeMae"] = {"mfeR": mfe, "maeR": mae}
    if slippage is not None:
        row["slippageCurrency"] = slippage
    return row


@dataclass(frozen=True, slots=True)
class _CycleObject:
    """Variante objeto del mismo contrato (dominio, no payload): el módulo la acepta."""

    strategy_version_id: str
    realized_pnl: str
    cycle_id: str | None = None
    r_multiple: float | None = None


# ── Agregación por estrategia ───────────────────────────────────────────────────────


def test_aggregates_results_and_cost_metrics_per_strategy_version() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="120", cycle_id="c1", r=1.2, mfe=1.5, mae=0.4, slippage="3"),
            _cycle(pnl="-80", cycle_id="c2", r=-0.8, mfe=0.3, mae=1.0, slippage="2"),
            _cycle("meanrev-2", pnl="-30", cycle_id="c3", r=-0.3),
        ]
    )

    assert [row.strategy_version for row in report.by_strategy] == ["meanrev-2", "orb-1"]
    orb = next(row for row in report.by_strategy if row.strategy_version == "orb-1")

    assert orb.trades == 2
    assert orb.wins == 1 and orb.losses == 1
    assert orb.realized_pnl == 40
    assert orb.expectancy_currency == 20
    assert orb.expectancy_r == pytest.approx(0.2)
    assert orb.win_rate == pytest.approx(0.5)
    assert orb.profit_factor == pytest.approx(1.5)
    assert orb.avg_win_currency == 120
    assert orb.avg_loss_currency == 80
    assert orb.mfe_r == pytest.approx(0.9)
    assert orb.mae_r == pytest.approx(0.7)
    assert orb.slippage_currency == 5
    assert orb.drawdown_currency == 80
    assert orb.results_measurement == "COMPLETE"
    assert report.trades == 3
    assert report.realized_pnl == 10
    assert report.read_only is True


def test_profit_factor_is_undefined_without_losses_and_breakeven_is_not_a_win() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="50", cycle_id="c1"), _cycle(pnl="0", cycle_id="c2")]
    )

    row = report.by_strategy[0]
    assert row.profit_factor is None, "sin pérdidas el ratio es indefinido, no infinito"
    assert (row.wins, row.losses, row.trades) == (1, 0, 2)
    assert row.win_rate == pytest.approx(0.5), "el breakeven no es una ganadora"


def test_drawdown_share_is_declared_as_an_additive_proxy() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="100", cycle_id="c1", closed_at="2026-09-15T10:00:00Z"),
            _cycle(pnl="-80", cycle_id="c2", closed_at="2026-09-15T11:00:00Z"),
            _cycle(
                "meanrev-2", pnl="-30", cycle_id="c3", closed_at="2026-09-15T12:00:00Z"
            ),
        ]
    )

    shares = {row.strategy_version: row.drawdown_share for row in report.by_strategy}
    assert shares == {"orb-1": 0.7273, "meanrev-2": 0.2727}
    assert SELF_EVAL_DRAWDOWN_SHARE_PROXY in report.notes
    assert report.drawdown_currency == 110, (
        "curva del informe en orden de cierre: 100 → 20 → -10 ⇒ caída de 110"
    )


def test_accepts_domain_objects_with_snake_case_fields() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[
            _CycleObject("orb-1", "120", cycle_id="c1", r_multiple=1.2),
            _CycleObject("orb-1", "-80", cycle_id="c2", r_multiple=-0.8),
        ]
    )

    row = report.by_strategy[0]
    assert row.realized_pnl == 40
    assert row.expectancy_r == pytest.approx(0.2)


# ── Embudo: cierra solo cuando está medido ──────────────────────────────────────────


def test_funnel_closes_only_when_every_state_is_catalogued_and_counted() -> None:
    report = evaluate_auto_self_evaluation(
        opportunities=[
            {"status": "traded", "strategy_version": "orb-1"},
            {"status": "rejected", "reason": "top_n_excluded", "strategyVersion": "orb-1"},
            {"status": "expired", "reason": "no_fill"},
        ],
        seen=3,
        durable_seen=3,
    )

    assert report.funnel_closed is True
    assert (report.seen, report.traded, report.rejected, report.expired, report.missed) == (
        3,
        1,
        1,
        1,
        0,
    )
    assert report.rejection_reasons == (("top_n_excluded", 1),)
    assert report.errors == ()


def test_funnel_stays_open_without_opportunities_instead_of_an_invented_zero() -> None:
    report = evaluate_auto_self_evaluation(cycles=[_cycle(cycle_id="c1")])

    assert report.funnel_closed is False
    assert report.seen is None, "no medir no es un 0"
    assert (report.traded, report.rejected, report.expired, report.missed) == (
        None,
        None,
        None,
        None,
    )
    assert SELF_EVAL_FUNNEL_UNKNOWN in report.notes
    assert report.funnel_measurement == "UNKNOWN"
    assert report.measurement != "COMPLETE"


def test_funnel_declares_declared_seen_and_durable_seen_mismatches() -> None:
    mismatched = evaluate_auto_self_evaluation(
        opportunities=[
            {"status": "traded", "strategy_version": "orb-1"},
            {"status": "rejected", "reason": "top_n_excluded"},
        ],
        seen=5,
        durable_seen=7,
    )

    assert SELF_EVAL_FUNNEL_SEEN_MISMATCH in mismatched.errors
    assert SELF_EVAL_FUNNEL_DURABLE_MISMATCH in mismatched.errors
    assert SELF_EVAL_FUNNEL_UNBALANCED in mismatched.errors
    assert mismatched.funnel_closed is False


def test_unknown_status_and_rejection_without_reason_leave_the_funnel_open() -> None:
    report = evaluate_auto_self_evaluation(
        opportunities=[
            {"status": "traded", "strategy_version": "orb-1"},
            {"status": "wishful", "reason": "?"},
            {"status": "rejected"},
        ]
    )

    assert SELF_EVAL_OPPORTUNITY_STATUS_UNKNOWN in report.errors
    assert SELF_EVAL_REJECTION_WITHOUT_REASON in report.errors
    assert report.funnel_closed is False
    assert report.seen == 3, "la fila no catalogada no desaparece: deja el embudo abierto"


def test_rejection_cost_is_measured_only_with_both_prices() -> None:
    measured = evaluate_auto_self_evaluation(
        opportunities=[
            {
                "status": "rejected",
                "reason": "top_n_excluded",
                "strategy_version": "orb-1",
                "reference_price": 100,
                "subsequent_price": 103,
            }
        ],
        seen=1,
    )
    assert measured.opportunity_cost_return == pytest.approx(0.03)
    assert measured.opportunity_cost_measurement == "COMPLETE"
    assert measured.by_strategy[0].rejection_cost_return == pytest.approx(0.03)
    assert SELF_EVAL_REJECTION_COST_UNMEASURED not in measured.notes

    unmeasured = evaluate_auto_self_evaluation(
        opportunities=[
            {"status": "rejected", "reason": "top_n_excluded", "reference_price": 100}
        ],
        seen=1,
    )
    assert unmeasured.opportunity_cost_return is None, "sin precio posterior no hay coste"
    assert unmeasured.opportunity_cost_measurement == "UNKNOWN"
    assert SELF_EVAL_REJECTION_COST_UNMEASURED in unmeasured.notes


# ── Identidad, unicidad y atribución ────────────────────────────────────────────────


def test_a_repeated_cycle_is_counted_once_and_declared() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="100", cycle_id="c1"),
            _cycle(pnl="100", cycle_id="c1"),
        ]
    )

    assert report.cycles == 1
    assert report.duplicate_cycles == 1
    assert report.realized_pnl == 100, "un doble conteo mentiría igual que un doble fill"
    assert SELF_EVAL_DUPLICATE_CYCLE in report.errors
    assert report.decisive is False


def test_cycles_without_identity_are_counted_and_declared_not_collapsed() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10"), _cycle(pnl="20")]
    )

    assert report.cycles == 2, "sin identidad no se puede deduplicar: son dos"
    assert report.cycles_without_identity == 2
    assert report.duplicate_cycles == 0
    assert SELF_EVAL_CYCLE_WITHOUT_IDENTITY in report.notes


def test_unversioned_cycles_are_not_spread_across_strategies() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[
            _cycle(pnl="100", cycle_id="c1"),
            _cycle("", pnl="50", cycle_id="c2"),
        ]
    )

    assert report.trades == 1, "solo el ciclo atribuible entra en el roll-up"
    assert report.unattributed_cycles == 1
    assert report.unattributed_pnl == 50
    assert report.realized_pnl == 100
    assert [row.strategy_version for row in report.by_strategy] == ["orb-1"]
    assert SELF_EVAL_UNVERSIONED_CYCLE in report.notes


# ── Muestras, huecos declarados y contrato de lectura ──────────────────────────────


def test_thin_sample_is_declared_and_blocks_the_decisive_flag() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10", cycle_id=f"c{i}") for i in range(9)],
        min_trades=10,
    )

    assert SELF_EVAL_THIN_SAMPLE in report.notes
    assert report.by_strategy[0].sample_quality == "insufficient"
    assert report.decisive is False

    enough = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10", cycle_id=f"c{i}") for i in range(10)],
        min_trades=10,
    )
    assert enough.decisive is True
    assert enough.by_strategy[0].sample_quality == "insufficient", (
        "10 ciclos siguen siendo muestra escasa para concluir (bandas de honestidad)"
    )
    useful = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10", cycle_id=f"c{i}") for i in range(20)],
        min_trades=10,
    )
    assert useful.by_strategy[0].sample_quality == "preliminary"


def test_missing_risk_and_slippage_are_declared_with_their_own_measurement() -> None:
    report = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10", cycle_id="c1"), _cycle(pnl="-5", cycle_id="c2")]
    )

    row = report.by_strategy[0]
    assert row.expectancy_r is None
    assert row.risk_measurement == "UNKNOWN"
    assert row.slippage_measurement == "UNKNOWN"
    assert SELF_EVAL_RISK_UNMEASURED in report.notes
    assert SELF_EVAL_SLIPPAGE_UNMEASURED in report.notes
    assert report.results_measurement == "COMPLETE", "el resultado SÍ se midió"
    assert report.measurement == "UNKNOWN", (
        "el agregado es tan fiable como su bloque menos fiable: aquí faltan R, "
        "excursiones, slippage y el embudo"
    )


def test_an_empty_report_is_unknown_not_complete() -> None:
    report = evaluate_auto_self_evaluation()

    assert report.cycles == 0
    assert report.results_measurement == "UNKNOWN"
    assert report.measurement == "UNKNOWN"
    assert report.decisive is False
    assert report.funnel_closed is False
    assert SELF_EVAL_MISSING_INPUTS in report.notes


def test_as_dict_is_serializable_and_declares_read_only() -> None:
    import json

    report = evaluate_auto_self_evaluation(
        cycles=[_cycle(pnl="10", cycle_id="c1", r=1.0)],
        opportunities=[{"status": "traded", "strategy_version": "orb-1"}],
        seen=1,
    )
    payload = report.as_dict()

    assert payload["key"] == AUTO_SELF_EVALUATION_KEY
    assert payload["readOnly"] is True
    assert payload["byStrategy"][0]["strategyVersion"] == "orb-1"
    assert payload["byStrategy"][0]["decisive"] is False
    assert json.loads(json.dumps(payload))["funnel"]["closed"] is True
