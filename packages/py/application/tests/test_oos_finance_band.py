"""`§8-c` — banda `K` medida del reporte financiero OOS (módulo puro `oos_finance_band`).

Contrato de honestidad, verificado aquí:

* Un hueco es ``None``/``NOT_MEASURED``; **nunca** se rellena con ``0``.
* Un cubo ausente en un sorteo baja ``drawsWithCell`` (no se inventa un valor).
* ``validity`` se **evalúa** (``crossesZeroNetReturn``/``pointCitable``), no se narra.
* El payload es **determinista** (no depende del orden de los sorteos ni de los grupos).
"""

from __future__ import annotations

from typing import Any

from bolsa_application.oos_finance_band import (
    AGGREGATE_KEY,
    METRICS,
    MIN_DRAWS_FOR_BAND,
    build_finance_band,
)


def _group(
    symbol: str,
    *,
    version: str | None = "ver-a",
    preset: str | None = None,
    **metrics: Any,
) -> dict[str, Any]:
    return {
        "strategyVersion": version,
        "strategyPresetKey": preset,
        "symbol": symbol,
        **metrics,
    }


def _report(
    groups: list[dict[str, Any]],
    *,
    aggregate: dict[str, Any] | None = None,
    min_trades: int = 10,
    stress: float = 2.0,
) -> dict[str, Any]:
    return {
        "minTrades": min_trades,
        "stressMultiplier": stress,
        "aggregate": aggregate or {},
        "groups": groups,
    }


def test_none_is_never_zero() -> None:
    """Un dato ausente viaja como ``None``; jamás como ``0`` (ni en la banda ni en el agregado)."""
    draws = [
        _report([_group("ACS", netReturnPct=None, trades=None)]),
        _report([_group("ACS", netReturnPct=None, trades=None)]),
    ]

    band = build_finance_band(draws=draws)

    cell = band["groups"][0]
    assert cell["bands"]["netReturnPct"] is None
    assert cell["bands"]["trades"] is None
    # La banda del agregado tampoco fabrica ceros.
    assert band["aggregate"]["bands"]["netReturnPct"] is None


def test_draws_with_cell_counts_a_missing_group() -> None:
    """Un grupo ausente en un sorteo baja ``drawsWithCell`` (no se inventa el valor faltante)."""
    draws = [
        _report([_group("ACS", netReturnPct=1.0), _group("ITX", netReturnPct=2.0)]),
        _report([_group("ACS", netReturnPct=3.0)]),  # ITX ausente
    ]

    band = build_finance_band(draws=draws)

    by_symbol = {cell["symbol"]: cell for cell in band["groups"]}
    assert by_symbol["ACS"]["drawsWithCell"] == 2
    assert by_symbol["ITX"]["drawsWithCell"] == 1
    assert band["coverage"]["drawsTotal"] == 2


def test_insufficient_draws_with_k_one() -> None:
    """Con un solo sorteo no hay dispersión que medir: se declara, no se cita un punto."""
    assert MIN_DRAWS_FOR_BAND == 2
    draws = [_report([_group("ACS", netReturnPct=5.0)])]

    band = build_finance_band(draws=draws)

    validity = band["groups"][0]["validity"]
    assert validity["pointCitable"] is False
    assert validity["note"] == "insufficient_draws"
    assert validity["se"] is None


def test_crosses_zero_blocks_citation_and_all_positive_allows_it() -> None:
    """La citabilidad se EVALÚA: cruzar cero la prohíbe; una banda alta y estrecha la permite."""
    crossing = build_finance_band(
        draws=[
            _report([_group("ACS", netReturnPct=-5.0)]),
            _report([_group("ACS", netReturnPct=5.0)]),
        ]
    )
    band = [cell for cell in crossing["groups"] if cell["symbol"] == "ACS"][0]
    assert band["validity"]["crossesZeroNetReturn"] is True
    assert band["validity"]["pointCitable"] is False

    citable = build_finance_band(
        draws=[
            _report([_group("ITX", netReturnPct=value)])
            for value in (10.0, 12.0, 14.0, 16.0)
        ]
    )
    ok = [cell for cell in citable["groups"] if cell["symbol"] == "ITX"][0]
    assert ok["validity"]["crossesZeroNetReturn"] is False
    assert ok["validity"]["pointCitable"] is True
    assert ok["validity"]["se"] is not None


def test_absent_group_has_no_sample_but_is_declared() -> None:
    """Sin banda ⇒ ``crossesZeroNetReturn = None`` y motivo ``sin_muestra`` (nunca un cero)."""
    draws = [_report([_group("ACS", netReturnPct=None)])]

    band = build_finance_band(draws=draws)

    validity = band["groups"][0]["validity"]
    assert validity["crossesZeroNetReturn"] is None
    assert validity["pointCitable"] is False
    assert validity["note"] == "sin_muestra"


def test_payload_is_deterministic_under_permutation() -> None:
    """Mismo estado ⇒ mismo payload: el orden de sorteos y grupos no puede cambiar la banda."""
    draw_a = _report([_group("ITX", netReturnPct=2.0), _group("ACS", netReturnPct=1.0)])
    draw_b = _report([_group("ACS", netReturnPct=3.0), _group("ITX", netReturnPct=4.0)])

    forward = build_finance_band(draws=[draw_a, draw_b])
    reversed_order = build_finance_band(draws=[draw_b, draw_a])

    assert forward == reversed_order
    # El agregado va primero y los grupos por (versión, símbolo) estable.
    symbols = [cell["symbol"] for cell in forward["groups"]]
    assert symbols == ["ACS", "ITX"]
    assert forward["aggregate"]["symbol"] == AGGREGATE_KEY[1]


def test_declared_scalars_and_identity_are_propagated() -> None:
    """``minTrades``/``stressMultiplier`` y la identidad exacta (H1) viajan declarados."""
    draws = [
        _report([_group("ACS", preset="preset-x", netReturnPct=1.0)], min_trades=7, stress=3.0),
    ]

    band = build_finance_band(draws=draws)

    assert band["minTrades"] == 7
    assert band["stressMultiplier"] == 3.0
    assert band["groups"][0]["strategyPresetKey"] == "preset-x"
    assert band["groups"][0]["strategyPresetKeyAmbiguous"] is False
    assert band["groups"][0]["strategyPresetKeys"] == ["preset-x"]
    assert set(band["groups"][0]["bands"]) == set(METRICS)


def test_preset_identity_consistent_across_draws_is_kept() -> None:
    """H2 — si TODOS los sorteos del cubo declaran la MISMA clave, la identidad se conserva."""
    draws = [
        _report([_group("ACS", preset="breakout_v3", netReturnPct=float(value))])
        for value in (1.0, 3.0)
    ]

    cell = build_finance_band(draws=draws)["groups"][0]

    assert cell["strategyPresetKey"] == "breakout_v3"
    assert cell["strategyPresetKeyAmbiguous"] is False
    assert cell["strategyPresetKeys"] == ["breakout_v3"]


def test_preset_identity_ambiguous_across_draws_is_declared_not_chosen() -> None:
    """H2 — claves DISTINTAS en el mismo cubo ⇒ identidad ambigua (None), ninguna «ganadora»."""
    draw_a = _report([_group("ACS", preset="breakout_v3", netReturnPct=1.0)])
    draw_b = _report([_group("ACS", preset="mean_reversion_v1", netReturnPct=2.0)])

    band = build_finance_band(draws=[draw_a, draw_b])

    cell = band["groups"][0]
    assert cell["strategyPresetKey"] is None
    assert cell["strategyPresetKeyAmbiguous"] is True
    assert cell["strategyPresetKeys"] == ["breakout_v3", "mean_reversion_v1"]
    # Permutar los sorteos NO cambia el veredicto ni elige una clave por orden de llegada.
    assert build_finance_band(draws=[draw_b, draw_a]) == band


def test_preset_identity_absent_is_a_gap_never_ambiguous() -> None:
    """H2 — sin ``presetKey`` no hay identidad ni ambigüedad: hueco declarado, nunca fabricado."""
    cell = build_finance_band(draws=[_report([_group("ACS", netReturnPct=1.0)])])["groups"][0]

    assert cell["strategyPresetKey"] is None
    assert cell["strategyPresetKeyAmbiguous"] is False
    assert cell["strategyPresetKeys"] == []


def test_aggregate_declares_no_identity() -> None:
    """H2 — el cubo agregado no tiene identidad de estrategia: ``None`` y sin ambigüedad."""
    band = build_finance_band(draws=[_report([_group("ACS", preset="preset-x", netReturnPct=1.0)])])

    aggregate = band["aggregate"]
    assert aggregate["strategyPresetKey"] is None
    assert aggregate["strategyPresetKeyAmbiguous"] is False
    assert aggregate["strategyPresetKeys"] == []

