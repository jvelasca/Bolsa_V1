"""`P2` (sello 2) — pruebas de la auditoría por valor de ESTUDIO.

Muerden: la composición estrategia+porqué+señal+R+dinero; la unión por la clave EXACTA
`presetKey` (H1) y su declaración de AMBIGÜEDAD; que un valor solo se declara «medido» con
las dos mitades sobre su suelo de muestra; que nada se rellena con `0`; y el determinismo.
"""

from __future__ import annotations

from bolsa_application.estudio_audit import (
    ESTUDIO_AUDIT_KIND,
    build_estudio_audit_report,
)


def _value(
    symbol: str,
    *,
    measured_cycles: int = 8,
    expectancy_r: float | None = 0.4,
    verdict: str = "MIXED",
) -> dict:
    return {
        "symbol": symbol,
        "verdict": verdict,
        "verdictReason": "preliminary_sample",
        "evidenceQuality": "SUPPORTED",
        "expectancyR": expectancy_r,
        "hitRate": 0.55,
        "measuredCycles": measured_cycles,
        "daysCovered": 3,
        "realizedRTotal": 3.2,
    }


def _cycle(
    symbol: str,
    *,
    preset: str | None,
    version: str | None = "ver-1",
    r: float = 0.5,
    cycle_id: str | None = None,
) -> dict:
    return {
        "cycleId": cycle_id if cycle_id is not None else f"cyc-{symbol}-{preset}-{version}",
        "symbol": symbol,
        "entryDay": "2026-04-01",
        "exitDay": "2026-04-02",
        "strategyVersion": version,
        "strategyPresetKey": preset,
        "realizedR": r,
    }


def _group(symbol: str, *, preset: str | None, trades: int = 12, net: float | None = 2.5) -> dict:
    return {
        "symbol": symbol,
        "strategyVersion": "ver-1",
        "strategyPresetKey": preset,
        "trades": trades,
        "committedCapital": 1000.0,
        "netReturnPct": net,
        "netReturnPctAtStress": 1.8,
        "maxDrawdownPct": 3.0,
        "hitRate": 0.6,
    }


def test_both_halves_measured_and_joined_by_exact_preset_key() -> None:
    report = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[_cycle("ACS", preset="sma_crossover")],
        finance_groups=[_group("ACS", preset="sma_crossover")],
        why_by_symbol={"ACS": {"indicatorSpecs": [{"kind": "SMA"}], "recommendations": ["r1"]}},
    )
    entry = report.values[0]
    assert entry["symbol"] == "ACS"
    assert entry["strategy"]["presetKey"] == "sma_crossover"
    assert entry["strategy"]["version"] == "ver-1"
    assert entry["resultR"]["measured"] is True
    assert entry["money"]["measured"] is True
    assert entry["money"]["netReturnPct"] == 2.5
    assert entry["measured"] is True
    assert entry["why"]["indicatorSpecs"] == [{"kind": "SMA"}]
    assert entry["why"]["recommendations"] == ["r1"]
    assert entry["unmeasured"] == []
    assert report.summary == {
        "values": 1,
        "measured": 1,
        "unmeasured": 0,
        "withPresetKey": 1,
        "withoutPresetKey": 0,
    }
    assert report.point_citable is False
    assert report.to_dict()["kind"] == ESTUDIO_AUDIT_KIND


def test_missing_money_is_declared_never_zero() -> None:
    report = build_estudio_audit_report(
        values=[_value("ACS")], cycles=[_cycle("ACS", preset="sma_crossover")]
    )
    entry = report.values[0]
    assert entry["resultR"]["measured"] is True
    assert entry["money"]["measured"] is False
    assert entry["money"]["netReturnPct"] is None
    assert entry["money"]["trades"] == 0
    assert entry["measured"] is False
    assert any("sin grupo financiero" in gap for gap in entry["unmeasured"])


def test_money_below_floor_is_none_never_zero() -> None:
    report = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[_cycle("ACS", preset="sma_crossover")],
        finance_groups=[_group("ACS", preset="sma_crossover", trades=3, net=0.0)],
        min_trades=10,
    )
    entry = report.values[0]
    assert entry["money"]["trades"] == 3
    assert entry["money"]["netReturnPct"] == 0.0  # el dato bruto llega, pero…
    assert entry["money"]["measured"] is False  # …bajo el suelo NO se declara medido
    assert any("round-trips < suelo" in gap for gap in entry["unmeasured"])


def test_ambiguous_preset_key_is_declared_not_chosen() -> None:
    report = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[
            _cycle("ACS", preset="sma_crossover", version="a"),
            _cycle("ACS", preset="rsi_mean_reversion", version="b"),
        ],
    )
    entry = report.values[0]
    assert entry["strategy"]["presetKey"] is None
    assert any("ambigua" in gap for gap in entry["unmeasured"])
    assert report.summary["withPresetKey"] == 0
    assert report.summary["withoutPresetKey"] == 1


def test_missing_preset_key_is_a_declared_gap() -> None:
    report = build_estudio_audit_report(
        values=[_value("ACS")], cycles=[_cycle("ACS", preset=None)]
    )
    entry = report.values[0]
    assert entry["strategy"]["presetKey"] is None
    assert any("no declara presetKey" in gap for gap in entry["unmeasured"])


def test_money_group_selected_by_exact_preset_key_when_several_share_symbol() -> None:
    report = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[_cycle("ACS", preset="rsi_mean_reversion")],
        finance_groups=[
            _group("ACS", preset="sma_crossover", net=9.9),
            _group("ACS", preset="rsi_mean_reversion", net=1.1),
        ],
    )
    entry = report.values[0]
    # Se atribuye a la estrategia EXACTA, no al primero del símbolo.
    assert entry["money"]["netReturnPct"] == 1.1


def test_single_group_with_other_preset_is_not_attributed() -> None:
    """Un solo grupo con OTRA identidad NO se atribuye: hueco declarado, nunca dinero cruzado."""
    report = build_estudio_audit_report(
        values=[_value("TEF")],
        cycles=[_cycle("TEF", preset="breakout_v3", version="ver-breakout")],
        finance_groups=[_group("TEF", preset="mean_reversion_v1", net=2.5)],
    )
    entry = report.values[0]
    assert entry["strategy"]["presetKey"] == "breakout_v3"
    assert entry["money"]["measured"] is False
    assert entry["money"]["netReturnPct"] is None
    assert entry["measured"] is False
    assert any("no declaran la identidad" in gap for gap in entry["unmeasured"])


def test_single_keyless_group_still_used_when_value_declares_preset() -> None:
    """Fallback documentado: si el único grupo NO declara clave, sí se usa (las identidades no chocan)."""
    report = build_estudio_audit_report(
        values=[_value("TEF")],
        cycles=[_cycle("TEF", preset="breakout_v3")],
        finance_groups=[_group("TEF", preset=None, net=2.5)],
    )
    entry = report.values[0]
    assert entry["money"]["measured"] is True
    assert entry["money"]["netReturnPct"] == 2.5


def test_result_r_below_floor_is_declared() -> None:
    report = build_estudio_audit_report(
        values=[_value("ACS", measured_cycles=2, expectancy_r=0.3)],
        cycles=[_cycle("ACS", preset="sma_crossover")],
        finance_groups=[_group("ACS", preset="sma_crossover")],
        min_cycles=5,
    )
    entry = report.values[0]
    assert entry["resultR"]["measured"] is False
    assert entry["resultR"]["expectancyR"] == 0.3  # el dato bruto llega…
    assert entry["measured"] is False  # …pero bajo el suelo no se declara medido
    assert any("ciclos medidos < suelo" in gap for gap in entry["unmeasured"])


def test_missing_why_is_a_declared_gap() -> None:
    report = build_estudio_audit_report(
        values=[_value("ACS")], cycles=[_cycle("ACS", preset="sma_crossover")]
    )
    entry = report.values[0]
    assert entry["why"]["indicatorSpecs"] is None
    assert any("porqué" in gap for gap in entry["unmeasured"])


def test_deterministic_and_ordered_by_symbol() -> None:
    values = [_value("ITX"), _value("ACS")]
    cycles = [_cycle("ACS", preset="p"), _cycle("ITX", preset="q")]
    first = build_estudio_audit_report(values=values, cycles=cycles).to_dict()
    second = build_estudio_audit_report(values=list(reversed(values)), cycles=cycles).to_dict()
    assert first == second
    assert [row["symbol"] for row in first["values"]] == ["ACS", "ITX"]


def test_cycles_are_listed_per_value_ordered_by_cycle_id() -> None:
    """Cada valor lista sus ciclos con la clave canónica (cycleId) para enlazar la operación."""
    report = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[
            _cycle("ACS", preset="sma_crossover", r=0.7, cycle_id="cyc-b"),
            _cycle("ACS", preset="sma_crossover", r=-0.3, cycle_id="cyc-a"),
        ],
    )
    entry = report.values[0]
    assert [row["cycleId"] for row in entry["cycles"]] == ["cyc-a", "cyc-b"]
    assert entry["cycles"][0] == {
        "cycleId": "cyc-a",
        "entryDay": "2026-04-01",
        "exitDay": "2026-04-02",
        "strategyPresetKey": "sma_crossover",
        "strategyVersion": "ver-1",
        "realizedR": -0.3,
    }
    # El orden es determinista bajo permutación de entrada (mismo estado ⇒ mismo payload).
    permuted = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[
            _cycle("ACS", preset="sma_crossover", r=-0.3, cycle_id="cyc-a"),
            _cycle("ACS", preset="sma_crossover", r=0.7, cycle_id="cyc-b"),
        ],
    )
    assert permuted.values[0]["cycles"] == entry["cycles"]


def test_cycle_without_cycle_id_is_declared_not_silently_dropped() -> None:
    """Un ciclo sin cycleId no es enlazable: se declara el hueco, nunca se descarta en silencio."""
    report = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[_cycle("ACS", preset="sma_crossover", cycle_id="")],
    )
    entry = report.values[0]
    assert entry["cycles"] == []
    assert any("sin cycleId" in gap for gap in entry["unmeasured"])


def test_value_without_cycles_lists_empty_never_invented() -> None:
    report = build_estudio_audit_report(values=[_value("ACS")])
    entry = report.values[0]
    assert entry["cycles"] == []
    assert not any("cycleId" in gap for gap in entry["unmeasured"])


def test_signal_counts_linked_and_unlinked_and_matches_listing() -> None:
    """Los recuentos de la señal cuadran: ``linkedCycles == len(cycles[])`` y el total se desglosa."""
    report = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[
            _cycle("ACS", preset="sma_crossover", r=0.7, cycle_id="cyc-1"),
            _cycle("ACS", preset="sma_crossover", r=-0.3, cycle_id="cyc-2"),
            _cycle("ACS", preset="sma_crossover", r=0.1, cycle_id=""),
        ],
    )
    entry = report.values[0]
    signal = entry["signal"]
    assert signal["cycles"] == 3
    assert signal["linkedCycles"] == 2
    assert signal["unlinkedCycles"] == 1
    assert signal["duplicateCycles"] == 0
    # Invariante: el recuento «enlazable» es EXACTAMENTE lo listado (nunca diverge).
    assert signal["linkedCycles"] == len(entry["cycles"]) == 2
    assert (
        signal["linkedCycles"] + signal["unlinkedCycles"] + signal["duplicateCycles"]
        == signal["cycles"]
    )
    assert any("sin cycleId" in gap for gap in entry["unmeasured"])


def test_duplicate_cycle_id_is_deduplicated_and_declared() -> None:
    """Un ``cycleId`` repetido no duplica el enlace: se deduplica y se declara el hueco."""
    report = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[
            _cycle("ACS", preset="sma_crossover", r=0.5, cycle_id="cyc-x"),
            _cycle("ACS", preset="sma_crossover", r=0.9, cycle_id="cyc-x"),
        ],
    )
    entry = report.values[0]
    assert len(entry["cycles"]) == 1
    assert entry["signal"]["duplicateCycles"] == 1
    assert entry["signal"]["linkedCycles"] == 1
    assert any("repetido" in gap for gap in entry["unmeasured"])
    # Determinista bajo permutación de entrada (no elige «ganadora» por orden de llegada).
    permuted = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[
            _cycle("ACS", preset="sma_crossover", r=0.9, cycle_id="cyc-x"),
            _cycle("ACS", preset="sma_crossover", r=0.5, cycle_id="cyc-x"),
        ],
    )
    assert permuted.values[0]["cycles"] == entry["cycles"]


def test_cycles_are_sorted_naturally_not_lexicographically() -> None:
    """``cyc-2`` debe ir antes que ``cyc-10``: orden natural, no lexicográfico."""
    report = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[
            _cycle("ACS", preset="sma_crossover", cycle_id="cyc-10"),
            _cycle("ACS", preset="sma_crossover", cycle_id="cyc-2"),
        ],
    )
    assert [row["cycleId"] for row in report.values[0]["cycles"]] == ["cyc-2", "cyc-10"]


def test_illegal_realized_r_is_a_declared_gap_not_zero() -> None:
    report = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[_cycle("ACS", preset="sma_crossover")],
    )
    report_illegal = build_estudio_audit_report(
        values=[_value("ACS")],
        cycles=[
            {
                "cycleId": "cyc-ils",
                "symbol": "ACS",
                "entryDay": "2026-04-01",
                "exitDay": None,
                "strategyVersion": "ver-1",
                "strategyPresetKey": "sma_crossover",
                "realizedR": "no-numero",
            }
        ],
    )
    row = report_illegal.values[0]["cycles"][0]
    assert row["realizedR"] is None  # hueco, nunca 0
    assert row["exitDay"] is None
    # El caso con dato válido no se altera.
    assert report.values[0]["cycles"][0]["realizedR"] == 0.5
