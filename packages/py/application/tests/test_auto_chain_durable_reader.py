"""Evidencia funcional AUTO por valor de ESTUDIO — contratos PUROS del lector de cadena.

Invariantes que se fijan aquí (doctrina ``UNKNOWN ≠ 0``):

* Un paso ENCENDIDO por un hecho durable se proyecta ``1``; un paso sin traza es ``None``;
  **jamás** ``0`` (un ``0`` afirmaría "no ocurrió" sin evidencia).
* La identidad de la estrategia EJECUTADA se lee del hecho durable del ciclo; sin identidad se
  declara ``None`` (nunca se asume el #1).
* ``executed vs best scored`` solo afirma ``True``/``False`` con término de comparación; un hueco
  es ``None`` ("no se puede emparejar").
* El artefacto es determinista (mismo estado ⇒ mismo payload) y no rellena ceros.
"""

from __future__ import annotations

import json
from typing import Any

from bolsa_application.auto_chain_durable_reader import (
    CANONICAL_STEPS,
    best_scored_asset,
    build_chain_evidence_artifact,
    chain_gaps,
    dia_d_link,
    executed_identity,
    executed_rank,
    executed_vs_dia_d,
    pnl_reconciliation,
    project_cycle_steps,
    resolve_executed_vs_best,
    value_strategy,
)


def _step(step_id: str, state: str, facts: list[tuple[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": step_id,
        "state": state,
        "facts": [{"key": k, "value": v} for k, v in (facts or [])],
    }


def _cycle(
    *,
    cycle_id: str = "cyc-1",
    instrument_id: str = "inst-1",
    preset: str | None = "trend_v1",
    version: str | None = "v-42",
    rank: int | None = 1,
    reached: set[str] | None = None,
    closed: bool | None = True,
) -> dict[str, Any]:
    on = CANONICAL_STEPS if reached is None else reached
    steps = []
    for step_id in CANONICAL_STEPS:
        state = "reached" if step_id in on else "unknown"
        facts = None
        if step_id == "TOP_N" and rank is not None:
            facts = [("rank", rank), ("score", 0.87)]
        steps.append(_step(step_id, state, facts))
    return {
        "cycleId": cycle_id,
        "instrumentId": instrument_id,
        "strategyPresetKey": preset,
        "strategyVersion": version,
        "opportunityId": f"opp-{cycle_id}",
        "direction": "long",
        "closed": closed,
        "steps": steps,
        "result": {"pnl": 12.5} if closed else None,
        "notes": [],
    }


def test_project_cycle_steps_marks_reached_as_one_and_gaps_as_none_never_zero() -> None:
    cycle = _cycle(reached={"SIGNAL", "TOP_N", "RISK"})
    projection = project_cycle_steps(cycle)
    assert projection["SIGNAL"] == 1
    assert projection["TOP_N"] == 1
    assert projection["RISK"] == 1
    assert projection["FILL"] is None
    assert projection["SETTLEMENT"] is None
    assert 0 not in projection.values()


def test_chain_gaps_reports_reached_and_not_reached_without_silent_unknown() -> None:
    cycle = _cycle(
        reached={
            "SIGNAL",
            "TOP_N",
            "RISK",
            "RESERVATION",
            "ORDER",
            "FILL",
            "PROTECTION",
            "SETTLEMENT",
            "CYCLE_CLOSED",
        }
    )
    gaps = chain_gaps(cycle)
    assert gaps["complete"] is True
    assert gaps["notReached"] == {}
    assert gaps["steps"] == len(CANONICAL_STEPS)

    partial = chain_gaps(_cycle(reached={"SIGNAL"}))
    assert partial["complete"] is False
    assert "FILL" in partial["notReached"]


def test_executed_rank_reads_durable_fact_and_declares_gap() -> None:
    assert executed_rank(_cycle(rank=2)) == 2
    assert executed_rank(_cycle(rank=None)) is None
    # Un rank 0/negativo no es un puesto válido: se declara hueco, no se devuelve.
    assert executed_rank(_cycle(rank=0)) is None


def test_executed_identity_never_invents_a_strategy() -> None:
    identity = executed_identity(_cycle())
    assert identity["strategyPresetKey"] == "trend_v1"
    assert identity["strategyVersion"] == "v-42"
    assert identity["rank"] == 1
    assert identity["measurement"] == "COMPLETE"

    empty = executed_identity({"cycleId": "cyc-x", "steps": []})
    assert empty["strategyPresetKey"] is None
    assert empty["rank"] is None
    assert empty["measurement"] == "UNKNOWN"

    # Solo preset: la identidad está PARCIAL, nunca COMPLETA (falta el otro término).
    only_preset = executed_identity(_cycle(version=None))
    assert only_preset["strategyPresetKey"] == "trend_v1"
    assert only_preset["strategyVersion"] is None
    assert only_preset["measurement"] == "PARTIAL"

    # Sin identidad declarada pero con puesto medido: PARCIAL (el puesto NO completa la
    # identidad, pero el bloque no queda sin ninguna medición).
    rank_only = executed_identity(_cycle(preset=None, version=None))
    assert rank_only["strategyPresetKey"] is None
    assert rank_only["strategyVersion"] is None
    assert rank_only["rank"] == 1
    assert rank_only["measurement"] == "PARTIAL"


def test_best_scored_asset_is_the_rank_one_row_or_none() -> None:
    snapshot = {
        "runId": "top3-acc-bar",
        "rows": [
            {"assetId": "b", "rank": 2, "combined": 0.5},
            {"assetId": "a", "rank": 1, "combined": 0.9},
        ],
    }
    assert best_scored_asset(snapshot)["assetId"] == "a"
    assert best_scored_asset({"runId": "x", "rows": [{"assetId": "b", "rank": 2}]}) is None
    assert best_scored_asset(None) is None


def test_resolve_executed_vs_best_never_asserts_false_without_comparison() -> None:
    # rank 1 ejecutado + activo mejor puntuado: se afirma True/True.
    same = resolve_executed_vs_best(
        executed={"rank": 1, "instrumentId": "a"},
        best_scored={"assetId": "a"},
    )
    assert same["executedIsTopRanked"] is True
    assert same["executedIsBestScoredAsset"] is True

    # rank 3: la ejecutada NO fue la mejor puntuada del valor (afirmable).
    not_top = resolve_executed_vs_best(
        executed={"rank": 3, "instrumentId": "a"},
        best_scored={"assetId": "b"},
    )
    assert not_top["executedIsTopRanked"] is False
    assert not_top["executedIsBestScoredAsset"] is False

    # Sin rank ni foto: no se puede emparejar (None), nunca un False fabricado.
    unknown = resolve_executed_vs_best(executed={}, best_scored=None)
    assert unknown["executedIsTopRanked"] is None
    assert unknown["executedIsBestScoredAsset"] is None
    assert unknown["measurement"] == "UNKNOWN"


def test_identity_match_is_true_false_or_none_and_never_inferred() -> None:
    """V2.88.153 — ``presetMatch``/``versionMatch``: verdadero, falso y hueco."""
    base_executed = {"rank": 1, "instrumentId": "a"}
    matched = resolve_executed_vs_best(
        executed={**base_executed, "strategyPresetKey": "trend_v1", "strategyVersion": "v-42"},
        best_scored={
            "assetId": "a",
            "rank": 1,
            "strategyPresetKey": "trend_v1",
            "strategyVersion": "v-42",
        },
    )
    assert matched["bestScoredPresetKey"] == "trend_v1"
    assert matched["bestScoredStrategyVersion"] == "v-42"
    assert matched["presetMatch"] is True
    assert matched["versionMatch"] is True
    assert matched["strategyMeasurement"] == "COMPLETE"

    different = resolve_executed_vs_best(
        executed={**base_executed, "strategyPresetKey": "trend_v1", "strategyVersion": "v-42"},
        best_scored={
            "assetId": "a",
            "rank": 1,
            "strategyPresetKey": "mean_reversion",
            "strategyVersion": "v-7",
        },
    )
    assert different["presetMatch"] is False
    assert different["versionMatch"] is False

    # La foto histórica (pre-057) no declara identidad: hueco declarado, nunca False.
    historical = resolve_executed_vs_best(
        executed={**base_executed, "strategyPresetKey": "trend_v1", "strategyVersion": "v-42"},
        best_scored={"assetId": "a", "rank": 1},
    )
    assert historical["bestScoredPresetKey"] is None
    assert historical["bestScoredStrategyVersion"] is None
    assert historical["presetMatch"] is None
    assert historical["versionMatch"] is None
    # El veredicto rank/activo SÍ se pudo medir: no se degrada por el hueco de identidad.
    assert historical["measurement"] == "COMPLETE"
    assert historical["strategyMeasurement"] == "UNKNOWN"

    # Una versión distinta con el mismo preset: coincide el preset, no la versión.
    same_preset_other_version = resolve_executed_vs_best(
        executed={**base_executed, "strategyPresetKey": "trend_v1", "strategyVersion": "v-1"},
        best_scored={
            "assetId": "a",
            "rank": 1,
            "strategyPresetKey": "trend_v1",
            "strategyVersion": "v-2",
        },
    )
    assert same_preset_other_version["presetMatch"] is True
    assert same_preset_other_version["versionMatch"] is False


def test_strategy_measurement_is_tri_state_and_never_complete_with_half_identity() -> None:
    """``strategyMeasurement``: ``COMPLETE`` exige preset Y versión contrastados.

    ``COMPLETE`` se lee como «la identidad está medida». Declararlo con medio término
    afirmaría una cobertura que no existe: media identidad es ``PARTIAL``, y ningún término
    es ``UNKNOWN``. El veredicto rank/activo (``measurement``) NO se degrada por el hueco.
    """
    base_executed = {"rank": 1, "instrumentId": "a"}
    full_photo = {
        "assetId": "a",
        "rank": 1,
        "strategyPresetKey": "trend_v1",
        "strategyVersion": "v-42",
    }

    both = resolve_executed_vs_best(
        executed={
            **base_executed,
            "strategyPresetKey": "trend_v1",
            "strategyVersion": "v-42",
        },
        best_scored=full_photo,
    )
    assert both["presetMatch"] is True
    assert both["versionMatch"] is True
    assert both["strategyMeasurement"] == "COMPLETE"

    # Solo preset: la comparación del preset SÍ se midió; la versión no se pudo afirmar.
    only_preset = resolve_executed_vs_best(
        executed={**base_executed, "strategyPresetKey": "trend_v1"},
        best_scored=full_photo,
    )
    assert only_preset["presetMatch"] is True
    assert only_preset["versionMatch"] is None
    assert only_preset["strategyMeasurement"] == "PARTIAL"

    # Solo versión: el simétrico. Ningún término se fabrica a partir del otro.
    only_version = resolve_executed_vs_best(
        executed={**base_executed, "strategyVersion": "v-42"},
        best_scored=full_photo,
    )
    assert only_version["presetMatch"] is None
    assert only_version["versionMatch"] is True
    assert only_version["strategyMeasurement"] == "PARTIAL"

    # Sin ningún término comparable: UNKNOWN, y el veredicto rank/activo sigue medido.
    none = resolve_executed_vs_best(
        executed=base_executed,
        best_scored={"assetId": "a", "rank": 1},
    )
    assert none["presetMatch"] is None
    assert none["versionMatch"] is None
    assert none["strategyMeasurement"] == "UNKNOWN"
    assert none["measurement"] == "COMPLETE"


def test_artifact_groups_by_estudio_value_and_declares_missing_cycles() -> None:
    cycles = [
        _cycle(cycle_id="cyc-1", instrument_id="i-1"),
        _cycle(cycle_id="cyc-2", instrument_id="i-2", reached={"SIGNAL"}),
        _cycle(cycle_id="cyc-3", instrument_id="i-outside"),
    ]
    artifact = build_chain_evidence_artifact(
        account_id="acc",
        estudio={"status": "ok", "instrumentIds": ["i-1", "i-2", "i-3"]},
        cycles=cycles,
        best_scored={"assetId": "i-1", "rank": 1, "combined": 0.9},
    )
    assert artifact["readOnly"] is True
    assert artifact["summary"]["values"] == 3
    assert artifact["summary"]["measured"] == 2  # i-1 e i-2 con ciclos; i-3 sin ciclos
    assert artifact["summary"]["complete"] == 1  # solo i-1 con cadena completa
    by_id = {value["instrumentId"]: value for value in artifact["values"]}
    assert by_id["i-3"]["cycles"] == []
    assert by_id["i-3"]["unmeasured"] == ["no_cycles_for_value"]
    # Un ciclo de un valor FUERA de ESTUDIO no se descarta en silencio: se declara.
    assert [c["cycleId"] for c in artifact["cyclesOutsideEstudio"]] == ["cyc-3"]


def test_pnl_reconciliation_requires_both_sides_and_uses_money_quantum() -> None:
    # Cierre y liquidación con el MISMO realizado ⇒ conciliado.
    cycle = _cycle()
    steps = cycle["steps"]
    for step in steps:
        if step["id"] == "CYCLE_CLOSED":
            step["facts"] = [{"key": "pnl", "value": 12.5}]
        if step["id"] == "SETTLEMENT":
            step["facts"] = [{"key": "pnl", "value": 12.5}]
    rec = pnl_reconciliation(cycle)
    assert rec["reconciled"] is True
    assert rec["measurement"] == "COMPLETE"

    # Un lado ausente NO se puede afirmar: hueco declarado (nunca ``True`` optimista).
    gap = pnl_reconciliation(_cycle(reached={"SIGNAL"}))
    assert gap["reconciled"] is None
    assert gap["measurement"] == "UNKNOWN"


def test_artifact_is_deterministic_and_free_of_fabricated_zeros() -> None:
    kwargs: dict[str, Any] = {
        "account_id": "acc",
        "estudio": {"status": "ok", "instrumentIds": ["i-1"]},
        "cycles": [_cycle(instrument_id="i-1", reached={"SIGNAL", "TOP_N"})],
        "as_of": "2026-10-14T00:00:00Z",
    }
    first = build_chain_evidence_artifact(**kwargs)
    second = build_chain_evidence_artifact(**kwargs)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    # La proyección del lado ejecutado nunca viaja un 0.
    steps = first["values"][0]["cycles"][0]["steps"]
    assert steps["SIGNAL"] == 1
    assert steps["FILL"] is None


def test_value_strategy_reuses_canonical_resolver_and_declares_ambiguity() -> None:
    # Dos ciclos del valor con la MISMA identidad ⇒ se declara sin ambigüedad.
    same = value_strategy([_cycle(cycle_id="cyc-2"), _cycle(cycle_id="cyc-10")])
    assert same["presetKey"] == "trend_v1"
    assert same["version"] == "v-42"
    assert same["presetKeyAmbiguous"] is False
    # Orden NATURAL por cycleId (cyc-2 antes que cyc-10) y lista canónica enlazable.
    assert [row["cycleId"] for row in same["cycles"]] == ["cyc-2", "cyc-10"]
    assert same["unlinkedCycles"] == 0
    assert same["duplicateCycles"] == 0

    # Identidades distintas ⇒ NO se elige «ganadora»: hueco ambiguo declarado.
    ambiguous = value_strategy(
        [_cycle(cycle_id="cyc-1", preset="trend_v1"), _cycle(cycle_id="cyc-2", preset="mean_v2")]
    )
    assert ambiguous["presetKey"] is None
    assert ambiguous["presetKeyAmbiguous"] is True

    # Un ciclo sin identidad declarada no aporta clave y no rompe la lista canónica.
    empty = value_strategy([{"cycleId": "cyc-x"}])
    assert empty["presetKey"] is None
    assert empty["presetKeyAmbiguous"] is False
    assert empty["cycles"][0]["cycleId"] == "cyc-x"


def test_executed_vs_dia_d_requires_both_durable_sides() -> None:
    cycle = {"strategyPresetKey": "trend_v1", "strategyVersion": "v-42"}
    verification = {"strategyPresetKey": "trend_v1", "strategyVersion": "v-42"}
    same = executed_vs_dia_d(executed=cycle, verification=verification)
    assert same["matches"] is True
    assert same["measurement"] == "COMPLETE"

    # Identidad distinta entre las dos fuentes durables ⇒ divergencia afirmable.
    diverge = executed_vs_dia_d(executed=cycle, verification={"strategyPresetKey": "mean_v2"})
    assert diverge["matches"] is False

    # Sin verificación NO se fabrica un ``False`` a partir de una sola parte: hueco declarado.
    gap = executed_vs_dia_d(executed=cycle, verification=None)
    assert gap["matches"] is None
    assert gap["measurement"] == "UNKNOWN"
    assert executed_vs_dia_d(executed=None, verification=verification)["matches"] is None


def test_dia_d_link_reuses_draft_builder_and_declares_gap() -> None:
    cycle = {"cycleId": "cyc-1", "instrumentId": "inst-1", "strategyPresetKey": "trend_v1"}
    complete = dia_d_link(
        cycle=cycle,
        verification={
            "symbol": "SAN",
            "diaD": "2026-10-14",
            "endDate": "2026-10-20",
            "mode": "replay",
            "strategyPresetKey": "trend_v1",
            "strategyVersion": "v-42",
            "result": {"ok": True},
        },
    )
    assert complete["linkable"] is True
    assert complete["draft"]["cycle_id"] == "cyc-1"
    assert complete["draft"]["symbol"] == "SAN"
    assert complete["measurement"] == "COMPLETE"

    # Sin verificación durable el borrador NO se fabrica: se declara el hueco.
    gap = dia_d_link(cycle=cycle, verification=None)
    assert gap["linkable"] is False
    assert gap["draft"] is None
    assert gap["measurement"] == "UNKNOWN"


def test_artifact_declares_best_scored_preset_gap_and_dia_d_cross_check() -> None:
    cycle = _cycle(instrument_id="i-1")
    cycle["entryDay"] = "2026-10-01"
    cycle["diaD"] = {
        "symbol": "SAN",
        "diaD": "2026-10-14",
        "endDate": "2026-10-20",
        "mode": "replay",
        "strategyPresetKey": "trend_v1",
        "strategyVersion": "v-42",
    }
    artifact = build_chain_evidence_artifact(
        account_id="acc",
        estudio={"status": "ok", "instrumentIds": ["i-1"]},
        cycles=[cycle],
        best_scored={"assetId": "i-1", "rank": 1, "combined": 0.9},
        as_of="2026-10-14T00:00:00Z",
    )
    # La foto cross-asset no sella identidad: el preset de la mejor puntuada es un hueco DECLARADO.
    assert artifact["bestScored"]["bestScoredPresetKey"] is None
    assert artifact["bestScored"]["strategyMeasurement"] == "UNKNOWN"
    view = artifact["values"][0]
    assert view["cycles"][0]["executedVsBest"]["presetMatch"] is None
    assert view["strategy"]["presetKey"] == "trend_v1"
    assert view["strategyDiaD"]["presetKey"] == "trend_v1"
    # Contraste independiente: el ciclo ejecutado y su verificación DÍA-D coinciden.
    assert view["cycles"][0]["executedVsDiaD"]["matches"] is True
    assert view["cycles"][0]["diaDLink"]["linkable"] is True


def test_artifact_publishes_the_winning_identity_when_the_photo_declares_it() -> None:
    """Desde la 057 la foto sella preset/versión: el artefacto los publica y contrasta."""
    cycle = _cycle(instrument_id="i-1", preset="trend_v1", version="v-42")
    artifact = build_chain_evidence_artifact(
        account_id="acc",
        estudio={"status": "ok", "instrumentIds": ["i-1"]},
        cycles=[cycle],
        best_scored={
            "assetId": "i-1",
            "rank": 1,
            "combined": 0.9,
            "strategyPresetKey": "trend_v1",
            "strategyVersion": "v-42",
        },
        as_of="2026-10-14T00:00:00Z",
    )
    assert artifact["bestScored"]["bestScoredPresetKey"] == "trend_v1"
    assert artifact["bestScored"]["bestScoredStrategyVersion"] == "v-42"
    assert artifact["bestScored"]["strategyMeasurement"] == "COMPLETE"
    compare = artifact["values"][0]["cycles"][0]["executedVsBest"]
    assert compare["presetMatch"] is True
    assert compare["versionMatch"] is True
    # Una divergencia declarada por la foto es un False medido, no un hueco.
    divergent = build_chain_evidence_artifact(
        account_id="acc",
        estudio={"status": "ok", "instrumentIds": ["i-1"]},
        cycles=[cycle],
        best_scored={
            "assetId": "i-1",
            "rank": 1,
            "combined": 0.9,
            "strategyPresetKey": "mean_reversion",
            "strategyVersion": "v-9",
        },
    )
    diff = divergent["values"][0]["cycles"][0]["executedVsBest"]
    assert diff["presetMatch"] is False
    assert diff["versionMatch"] is False


def test_artifact_declares_partial_identity_when_the_photo_only_seals_the_preset() -> None:
    """Media identidad en la foto NO es identidad completa: ``PARTIAL``, no ``COMPLETE``."""
    cycle = _cycle(instrument_id="i-1", preset="trend_v1", version="v-42")
    artifact = build_chain_evidence_artifact(
        account_id="acc",
        estudio={"status": "ok", "instrumentIds": ["i-1"]},
        cycles=[cycle],
        best_scored={
            "assetId": "i-1",
            "rank": 1,
            "combined": 0.9,
            "strategyPresetKey": "trend_v1",
        },
        as_of="2026-10-14T00:00:00Z",
    )
    block = artifact["bestScored"]
    assert block["bestScoredPresetKey"] == "trend_v1"
    assert block["bestScoredStrategyVersion"] is None
    assert block["strategyMeasurement"] == "PARTIAL"
    compare = artifact["values"][0]["cycles"][0]["executedVsBest"]
    assert compare["presetMatch"] is True
    assert compare["versionMatch"] is None
    assert compare["strategyMeasurement"] == "PARTIAL"

    # Y el simétrico: solo versión en la foto tampoco es identidad completa.
    only_version = build_chain_evidence_artifact(
        account_id="acc",
        estudio={"status": "ok", "instrumentIds": ["i-1"]},
        cycles=[cycle],
        best_scored={
            "assetId": "i-1",
            "rank": 1,
            "combined": 0.9,
            "strategyVersion": "v-42",
        },
    )
    assert only_version["bestScored"]["strategyMeasurement"] == "PARTIAL"
