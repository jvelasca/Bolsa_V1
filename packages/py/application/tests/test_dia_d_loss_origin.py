"""V2.88.44 · DÍA-D AUTO — contratos del DIAGNÓSTICO DE DÓNDE NACE LA PÉRDIDA (pura).

Invariantes que se fijan aquí:

* El clasificador de mecanismos es **total** y con precedencia determinista; sin motivo declara
  ``SIN_MECANISMO`` y un token no catalogado cae en ``EXIT_REQUESTED`` (nunca se inventa).
* El ledger v2 registra el mecanismo, la fricción en R y el R **neto**; con fricción ``PARTIAL``
  el neto es ``None`` (jamás el bruto disfrazado de neto).
* La excursión adversa TEMPRANA viaja con su ventana y su hueco declarado.
* El plegado de los ``K`` ledgers publica dispersión entre sorteos y fragilidad por causa.
* El artefacto es determinista (mismos ledgers ⇒ payload byte a byte idéntico) y declara contrato.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_application.dia_d_exit_mechanism import (
    EXIT_MECHANISM_EXIT_REQUESTED,
    EXIT_MECHANISM_SIN_MECANISMO,
    EXIT_MECHANISM_STOP,
    EXIT_MECHANISM_TARGET_1,
    EXIT_MECHANISM_TRAILING,
    classify_exit_mechanism,
)
from bolsa_application.dia_d_loss_origin import (
    KIND,
    SCHEMA_VERSION,
    build_loss_origin_artifact,
)
from bolsa_application.dia_d_multi_sampling import build_cycle_ledger

# ── Utilidades de muestra (sin I/O) ──────────────────────────────────────────────


def _fill(
    execution_id: str,
    cycle_id: str,
    side: str,
    price: float,
    quantity: float,
    reference_mid: float | None,
) -> Any:
    return SimpleNamespace(
        execution_id=execution_id,
        cycle_id=cycle_id,
        side=side,
        price=price,
        quantity=quantity,
        reference_mid=reference_mid,
    )


_TRIP: dict[str, Any] = {
    "symbol": "AAA",
    "entryDay": "2022-01-05",
    "exitDay": "2022-01-07",
    "entryPrice": 11.0,
    "exitPrice": 9.0,
    "stop": 10.0,
    "realizedR": -1.0,
    "cycleId": "C1",
}


def _early(mae: float | None = -0.8, reason: str | None = None) -> dict[str, Any]:
    return {
        "symbol": "AAA",
        "entryDay": "2022-01-05",
        "exitDay": "2022-01-07",
        "maeR": mae,
        "mfeR": 0.4,
        "measured": mae is not None,
        "reason": reason,
    }


# ── Clasificador de mecanismos ───────────────────────────────────────────────────


def test_classifier_is_total_with_declared_precedence():
    assert classify_exit_mechanism("structural_stop")[0] == EXIT_MECHANISM_STOP
    assert classify_exit_mechanism("t1_exit")[0] == EXIT_MECHANISM_TARGET_1
    assert classify_exit_mechanism("trailing_stop")[0] == EXIT_MECHANISM_TRAILING
    # Precedencia: stop > trailing > target_1 (el hecho mas severo gana).
    assert classify_exit_mechanism("t1_exit,protective_stop")[0] == EXIT_MECHANISM_STOP
    # Sin motivo: hueco declarado (nunca una etiqueta inventada).
    mechanism, evidence = classify_exit_mechanism("")
    assert mechanism == EXIT_MECHANISM_SIN_MECANISMO
    assert evidence == ""
    # Token no catalogado: generico declarado, con el crudo como evidencia.
    mechanism, evidence = classify_exit_mechanism("rarisimo")
    assert mechanism == EXIT_MECHANISM_EXIT_REQUESTED
    assert evidence == "rarisimo"


# ── Ledger v2: mecanismo, fricción, neto y excursión temprana ────────────────────


def test_ledger_v2_records_mechanism_friction_net_and_entry_quality():
    ledger = build_cycle_ledger(
        round_trips=[_TRIP],
        entry_excursions_rows=[_early()],
        cost_rows=[
            _fill("E-BUY", "C1", "buy", 11.0, 100.0, 10.0),
            _fill("E-SELL", "C1", "sell", 9.0, 100.0, 10.0),
        ],
        close_rows=[{"executionId": "E-SELL", "reason": "structural_stop"}],
    )
    row = ledger["cycles"][0]
    assert ledger["schemaVersion"] == "dia-d-multi-cycle-ledger-v6"
    assert row["exitMechanism"] == EXIT_MECHANISM_STOP
    assert row["exitReason"] == "structural_stop"
    # Friccion total = |11-10|*100 + |10-9|*100 = 200; riesgo = |11-10|*100 = 100 => 2R.
    assert row["frictionCost"] == pytest.approx(200.0)
    assert row["frictionR"] == pytest.approx(2.0)
    assert row["frictionMeasurement"] == "COMPLETE"
    assert row["netRealizedR"] == pytest.approx(-3.0)
    assert row["entryAdverseR"] == -0.8
    assert row["entryAdverseWindowDays"] == 3
    assert row["entryAdverseGap"] is None
    assert row["entrySlippageBps"] == pytest.approx(1000.0)
    assert row["entrySlippageGap"] is None


def test_partial_friction_never_publishes_a_net_r():
    ledger = build_cycle_ledger(
        round_trips=[_TRIP],
        cost_rows=[_fill("E-BUY", "C1", "buy", 11.0, 100.0, 10.0)],
        close_rows=[{"executionId": "E-BUY", "reason": "time_exit"}],
    )
    row = ledger["cycles"][0]
    # Falta la pata de salida: la ida y vuelta no esta probada.
    assert row["frictionMeasurement"] == "PARTIAL"
    # La friccion medida sigue siendo un dato (suelo), pero el NETO no se afirma.
    assert row["frictionR"] == pytest.approx(1.0)
    assert row["netRealizedR"] is None


def test_missing_cycle_identity_and_close_reason_are_declared_gaps():
    trip = {key: value for key, value in _TRIP.items() if key != "cycleId"}
    ledger = build_cycle_ledger(round_trips=[trip])
    row = ledger["cycles"][0]
    assert row["exitMechanism"] == EXIT_MECHANISM_SIN_MECANISMO
    assert row["frictionMeasurement"] == "UNKNOWN"
    assert row["frictionR"] is None
    assert row["netRealizedR"] is None
    assert row["entryAdverseR"] is None
    assert row["entrySlippageGap"] == "sin_fills_del_ciclo"


def test_entry_adverse_gap_declares_its_reason_when_unmeasured():
    ledger = build_cycle_ledger(
        round_trips=[_TRIP],
        entry_excursions_rows=[_early(mae=None, reason="sin_barras_en_rango")],
    )
    row = ledger["cycles"][0]
    assert row["entryAdverseR"] is None
    assert row["entryAdverseGap"] == "sin_barras_en_rango"


# ── Plegado del artefacto ────────────────────────────────────────────────────────


def _ledger(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"cycles": rows}


def _row(mechanism: str, realized: float, *, net: float | None, measurement: str) -> dict[str, Any]:
    return {
        "symbol": "AAA",
        "entryDay": "2022-01-05",
        "exitDay": "2022-01-07",
        "realizedR": realized,
        "netRealizedR": net,
        "frictionCost": 1.0 if net is not None else None,
        "frictionR": (realized - net) if net is not None else None,
        "frictionMeasurement": measurement,
        "exitMechanism": mechanism,
        "entryAdverseR": -0.6,
        "entryAdverseWindowDays": 3,
        "entrySlippageBps": 50.0,
        "year": "2022",
    }


def test_artifact_folds_mechanisms_and_declares_fragility():
    ledgers = [
        _ledger([_row(EXIT_MECHANISM_STOP, -1.0, net=-2.0, measurement="COMPLETE")]),
        _ledger(
            [
                _row(EXIT_MECHANISM_STOP, -0.5, net=-1.5, measurement="COMPLETE"),
                _row(EXIT_MECHANISM_TARGET_1, 1.0, net=0.5, measurement="COMPLETE"),
            ]
        ),
    ]
    artifact = build_loss_origin_artifact(draw_ledgers=ledgers)
    rows = {row["mechanism"]: row for row in artifact["byExitMechanism"]}
    assert set(rows) == {EXIT_MECHANISM_STOP, EXIT_MECHANISM_TARGET_1}
    assert rows[EXIT_MECHANISM_STOP]["drawsWithCell"] == 2
    assert rows[EXIT_MECHANISM_STOP]["cycles"] == 2
    assert rows[EXIT_MECHANISM_STOP]["realizedRGross"]["total"]["mean"] == pytest.approx(-0.75)
    assert rows[EXIT_MECHANISM_TARGET_1]["drawsWithCell"] == 1
    # Un mecanismo presente en un solo sorteo y con pocos ciclos es fragil, y se declara.
    assert rows[EXIT_MECHANISM_TARGET_1]["fragility"]["fragile"] is True
    assert "insufficient_draws" in rows[EXIT_MECHANISM_TARGET_1]["fragility"]["reasons"]


def test_cost_impact_marks_partial_net_as_lower_bound():
    ledgers = [
        _ledger([_row(EXIT_MECHANISM_STOP, -1.0, net=None, measurement="PARTIAL")]),
        _ledger([_row(EXIT_MECHANISM_STOP, -1.0, net=None, measurement="PARTIAL")]),
    ]
    artifact = build_loss_origin_artifact(draw_ledgers=ledgers)
    costs = artifact["costImpact"]
    assert costs["netIsLowerBound"] is True
    assert costs["netUnmeasuredCycles"] == 2
    assert costs["frictionMeasurement"]["PARTIAL"] == 2
    assert costs["realizedRNetTotal"] is None


def test_entry_quality_shares_and_window():
    ledgers = [
        _ledger([_row(EXIT_MECHANISM_STOP, -1.0, net=-1.5, measurement="COMPLETE")]),
    ]
    entry = build_loss_origin_artifact(draw_ledgers=ledgers)["entryQuality"]
    assert entry["windowDays"] == 3
    assert entry["adverseExcursion"]["measured"] == 1
    assert entry["adverseExcursion"]["shareBelowHalfR"] == 1.0
    assert entry["adverseExcursion"]["shareBelowOneR"] == 0.0


def test_artifact_is_deterministic_and_declares_its_contract():
    ledgers = [
        _ledger([_row(EXIT_MECHANISM_STOP, -1.0, net=-2.0, measurement="COMPLETE")]),
        _ledger([_row(EXIT_MECHANISM_TARGET_1, 1.0, net=0.5, measurement="COMPLETE")]),
    ]
    first = build_loss_origin_artifact(draw_ledgers=ledgers)
    again = build_loss_origin_artifact(draw_ledgers=ledgers)
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
    assert first["schemaVersion"] == SCHEMA_VERSION == "dia-d-loss-origin-v1"
    assert first["kind"] == KIND == "DIA_D_AUTO_LOSS_ORIGIN"
    assert first["readOnly"] is True
    assert first["axes"] == ["exit_mechanism", "costs", "entry"]
    assert first["limits"]
