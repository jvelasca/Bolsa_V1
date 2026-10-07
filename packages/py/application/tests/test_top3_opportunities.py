"""V2.88 — TOP3 de oportunidades (activos) + adapter de evidencia (tests herméticos).

Certifica que el ranking cross-asset se alimenta de la evidencia de estrategia
(OOS/WFE/DSR/PBO/regime), que el board veta con motivo real y que el selector marca
las excluidas con ``TOP_N_EXCLUDED`` (motivo honesto, nunca un edge falso).
"""

from __future__ import annotations

import asyncio
from typing import Any

from bolsa_domain.entities.strategy_lifecycle import (
    GateResult,
    StrategyEvaluation,
)

from bolsa_application.opportunity_board import AssetEvidence, OpportunityBoard
from bolsa_application.opportunity_evidence_adapter import (
    StrategyEvidenceBundle,
    StrategyEvidenceSource,
    evidence_components,
    robustness_component,
)
from bolsa_application.strategy_top3_coach_phase import select_top3
from bolsa_application.top3_opportunities import select_top3_assets


def _evaluation(
    candidate_id: str,
    *,
    score: float,
    metrics: dict | None = None,
    gates: tuple[str, ...] = ("backtest", "oos", "walk_forward", "robustness"),
) -> StrategyEvaluation:
    return StrategyEvaluation(
        candidate_id=candidate_id,
        score=score,
        gates=tuple(GateResult.passed_gate(g) for g in gates),
        metrics={"instrument_id": "AAA", **(metrics or {})},
    )


# ── Adapter de evidencia ────────────────────────────────────────────────────────


def test_robustness_is_blend_of_wfe_dsr_1_minus_pbo() -> None:
    evaluation = _evaluation(
        "c1",
        score=2.0,
        metrics={"wfe": 0.8, "dsr": 0.6, "pbo": 0.4},
    )
    # media de (0.8, 0.6, 1 - 0.4) = 0.6667
    assert robustness_component(evaluation) == round((0.8 + 0.6 + 0.6) / 3, 4)


def test_robustness_missing_metrics_is_zero() -> None:
    evaluation = _evaluation("c1", score=2.0, metrics={})
    assert robustness_component(evaluation) == 0.0


def test_edge_prefers_oos_over_is() -> None:
    evaluation = _evaluation(
        "c1",
        score=9.0,  # IS alto (posible overfit)
        metrics={"is_score": 9.0, "oos_score": 1.0},
    )
    components = evidence_components(evaluation)
    # edge normalizado desde OOS (1.0 / EDGE_SCALE), no desde IS (9.0 saturaría a 1.0)
    assert components["edge"] == 0.1


def test_regime_fit_expected_match() -> None:
    evaluation = _evaluation("c1", score=2.0, metrics={"regime": "trend_up"})
    assert evidence_components(evaluation, expected_regime="trend_up")["regime_fit"] == 1.0
    assert evidence_components(evaluation, expected_regime="range")["regime_fit"] == 0.0


# ── Ranking TOP3 por evidencia OOS (no IS puro) ─────────────────────────────────


def test_top3_ranks_by_oos_not_is() -> None:
    selections = select_top3(
        instrument_id="AAA",
        run_id="run-1",
        evaluations=[
            _evaluation("c-high-is", score=9.0, metrics={"oos_score": 0.5}),
            _evaluation("c-high-oos", score=1.0, metrics={"oos_score": 3.0}),
        ],
    )
    # Aunque c-high-is tiene mayor IS, c-high-oos tiene mejor evidencia fuera de muestra.
    assert selections.top.candidate_ids == ("c-high-oos", "c-high-is")


# ── OpportunityBoard ─────────────────────────────────────────────────────────────


def test_board_ranks_and_vetoes_with_reason() -> None:
    evaluation = _evaluation("c1", score=2.0, metrics={"oos_score": 1.0, "regime": "trend_up"})
    board = OpportunityBoard(
        expected_regime="trend_up",
        veto=lambda asset: "liquidez_baja" if asset.instrument_id == "BBB" else None,
    )
    result = board.score(
        [
            AssetEvidence("AAA", evaluation=evaluation),
            AssetEvidence("BBB", evaluation=evaluation),
            AssetEvidence("CCC"),
        ]
    )
    assert [s.instrument_id for s in result.scores] == ["AAA"]
    assert {(e.instrument_id, e.reason) for e in result.excluded} == {
        ("BBB", "liquidez_baja"),
        ("CCC", "no_evidencia_campeon"),
    }


# ── Selector TOP3 ────────────────────────────────────────────────────────────────


def test_select_top3_assets_marks_top_n_excluded() -> None:
    evaluation = _evaluation("c1", score=2.0, metrics={"oos_score": 1.0})
    board = OpportunityBoard(expected_regime=None)
    result = board.score(
        [
            AssetEvidence("A", evaluation=evaluation),
            AssetEvidence("B", evaluation=_evaluation("c2", score=1.5, metrics={"oos_score": 0.5})),
            AssetEvidence("C", evaluation=_evaluation("c3", score=1.0, metrics={"oos_score": 0.2})),
            AssetEvidence("D", evaluation=_evaluation("c4", score=0.5, metrics={"oos_score": 0.1})),
        ]
    )
    selection = select_top3_assets(list(result.scores), run_id="run-x", excluded=result.excluded)
    assert [o.instrument_id for o in selection.selected] == ["A", "B", "C"]
    assert all(o.rank in (1, 2, 3) for o in selection.selected)
    assert [o.instrument_id for o in selection.top_n_excluded] == ["D"]
    assert all(o.reason == "top_n_excluded" for o in selection.top_n_excluded)
    records = selection.to_records()
    assert len(records) == 3
    assert records[0].instrument_id == "A"
    assert records[0].to_dict()["assetId"] == "A"


# ── StrategyEvidenceSource (hot path SIM) ───────────────────────────────────────


def test_evidence_source_preloads_and_reads_sync() -> None:
    """El reader async se precarga una vez; ``components_for`` lee síncrono (fail-closed)."""
    evaluation = _evaluation("c1", score=2.0, metrics={"oos_score": 1.0, "regime": "trend_up"})

    async def _run() -> None:
        async def reader(symbols, regime):  # noqa: ANN001 — firma del reader inyectable.
            return {
                "AAA": StrategyEvidenceBundle(evaluation=evaluation),
                "BBB": StrategyEvidenceBundle(),
            }

        source = StrategyEvidenceSource(reader=reader)
        await source.refresh(["AAA", "BBB"], regime="trend_up")
        aaa = source.components_for("AAA")
        assert aaa is not None
        assert aaa["regime_fit"] == 1.0
        # Sin evaluación ni salud ⇒ todos los componentes a 0 (fail-closed).
        bbb = source.components_for("BBB")
        assert bbb is not None
        assert all(v == 0.0 for v in bbb.values())
        # Símbolo no observado ⇒ None (el motor conserva el scoring histórico).
        assert source.components_for("ZZZ") is None

    asyncio.run(_run())


def test_evidence_source_failure_degrades_to_none() -> None:
    """Un reader que lanza deja el mapa vacío: ``components_for`` ⇒ None (nunca inventa)."""

    async def _run() -> None:
        async def broken_reader(symbols, regime):  # noqa: ANN001, ARG001
            raise RuntimeError("store down")

        source = StrategyEvidenceSource(reader=broken_reader)
        await source.refresh(["AAA"])
        assert source.components_for("AAA") is None

    asyncio.run(_run())


# ── PostgresTop3OpportunitySink (glue durable) ─────────────────────────────────


class _FakeSession:
    """AsyncSession mínimo: registra las filas que el repositorio añade."""

    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None


def test_postgres_sink_maps_records_to_rows() -> None:
    """El sink traduce ``Top3OpportunityRecord`` a ``Top3OpportunityRow`` con régimen."""
    from bolsa_infrastructure.database.models.tables import Top3OpportunityRow

    from bolsa_application.top3_opportunities import Top3OpportunityRecord
    from bolsa_application.top3_opportunity_store import PostgresTop3OpportunitySink

    session = _FakeSession()
    sink = PostgresTop3OpportunitySink(session, regime="trend_up")

    async def _run() -> None:
        await sink.save(
            [
                Top3OpportunityRecord(
                    run_id="run-1",
                    rank=1,
                    instrument_id="AAA",
                    combined=0.7,
                    components={"edge": 0.9, "robustness": 0.8},
                    reason=None,
                ),
                Top3OpportunityRecord(
                    run_id="run-1",
                    rank=2,
                    instrument_id="BBB",
                    combined=0.5,
                    components={"edge": 0.6},
                    reason="top_n_excluded",
                ),
            ]
        )

    asyncio.run(_run())
    assert len(session.added) == 2
    first, second = session.added
    assert isinstance(first, Top3OpportunityRow)
    assert first.run_id == "run-1"
    assert first.rank == 1
    assert first.asset_id == "AAA"
    assert first.combined == 0.7
    assert first.components == {"edge": 0.9, "robustness": 0.8}
    assert first.regime == "trend_up"
    assert first.reasons == []
    # Un motivo singular viaja como lista de un elemento en ``reasons``.
    assert second.reasons == ["top_n_excluded"]


def test_postgres_sink_empty_records_is_noop() -> None:
    """Una lista vacía no escribe un run sin TOP3."""
    from bolsa_application.top3_opportunity_store import PostgresTop3OpportunitySink

    session = _FakeSession()
    sink = PostgresTop3OpportunitySink(session)

    async def _run() -> None:
        await sink.save([])

    asyncio.run(_run())
    assert session.added == []
