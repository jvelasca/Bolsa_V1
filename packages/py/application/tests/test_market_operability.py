"""V2.77 · AUTO-MATERIAL-5 — journal de OPERABILIDAD del forward PAPER.

Contratos que se fijan aquí (puros, sin red ni PostgreSQL):

* Cada código de motivo del dueño único (``DecisionReasonCode`` de
  ``portfolio_decision_engine`` + ``TOP_N_EXCLUDED`` de ``opportunity_ranker``) tiene familia
  declarada; un código desconocido va a ``other`` y **no se descarta**.
* La familia separa el HECHO de mercado (``regime``) del PERMISO del gobernador (``governor``)
  y del tope de EVALUACIÓN (``top_n``): son tres causas distintas de no operar.
* ``pairCapable`` (arquitectura lista) y ``pairActive`` (dos versiones operando) son estados
  DISTINTOS: el smoke real da ``CAPABLE`` sin ``ACTIVE`` y el journal debe poder decirlo.
* ``no_signal`` **sólo** si no hubo ni propuestas ni vetos: un día con vetos se declara ``vetoed``.
"""

from __future__ import annotations

from typing import Any, get_args

from bolsa_analytics.cognitive.opportunity_ranker import TOP_N_EXCLUDED
from bolsa_application.market_operability import (
    BUCKET_DATA,
    BUCKET_GOVERNOR,
    BUCKET_LIQUIDITY,
    BUCKET_OTHER,
    BUCKET_REGIME,
    BUCKET_RISK,
    BUCKET_TOP_N,
    OPERABILITY_BUCKETS,
    STATE_NO_SIGNAL,
    STATE_OPERATED,
    STATE_VETOED,
    VETO_BUCKET_BY_REASON,
    build_operability_record,
    classify_veto_reasons,
    operability_state,
    pair_active,
    pair_capable,
    parse_journal_reasons,
    render_operability_table,
    symbols_operable,
    veto_counted,
)
from bolsa_application.portfolio_decision_engine import DecisionReasonCode

# ── Fixture: el forward smoke REAL de v2.76 (8 ticks, mercado cerrado, 0 fills) ────────────────

_WATCH_A = (
    "0a5dc12fd5a24f0a89a91d36a",
    "0cf0907837fc422db221b0149",
    "240a4ae01a944d3bba1cf1b24",
    "31f9a597d03249319ea0c9345",
)
_WATCH_B = (
    "381dd3b0699a44e8b9d13ac13",
    "49596ff25acb4294b265f321b",
    "4d24ea029283461cb9304421a",
    "54283bcb54674ec1b70b4db72",
)

_FORWARD_SMOKE: dict[str, Any] = {
    "phase": "V2.76 AUTO-MATERIAL-4 MARKET MATERIAL FORWARD",
    "account": "aace1382152544b3b7e6e12f2",
    "versionA": "v76-forward-c3d8",
    "versionB": "",
    "requestedVersions": ["v76-forward-c3d8"],
    "watchA": list(_WATCH_A),
    "watchB": list(_WATCH_B),
    "watchSize": 8,
    "pairAvailable": False,
    "secondaryActive": False,
    "ticks": 8,
    "journalReasons": ["regime_invalid:40", "top_n_excluded:24"],
    "lastGateReason": ["hold_no_op"],
    "marketRegime": {
        "aggregateTrialRegime": "trend_down",
        "operationalRegime": "BEAR_TREND",
        "entriesAllowedLong": False,
        "barsLoaded": 8,
        "bySymbol": {
            "0a5dc12fd5a24f0a89a91d36a": "range",
            "0cf0907837fc422db221b0149": "trend_down",
            "240a4ae01a944d3bba1cf1b24": "trend_down",
            "31f9a597d03249319ea0c9345": "range",
            "381dd3b0699a44e8b9d13ac13": "range",
            "49596ff25acb4294b265f321b": "trend_down",
            "4d24ea029283461cb9304421a": "range",
            "54283bcb54674ec1b70b4db72": "trend_down",
        },
        "counts": {"range": 4, "trend_down": 4},
    },
    "turnTotals": {
        "decided": 64,
        "proposals": 0,
        "vetoes": 64,
        "orders": 0,
        "fills": 0,
        "opened": 0,
        "closed": 0,
    },
    "priceSources": {symbol: "market_close" for symbol in (*_WATCH_A, *_WATCH_B)},
    "sample": {"measurableCycles": 0, "verdict": "BLOCKED"},
}


# ── El dueño único de los literales queda cubierto (no puede haber un código sin familia) ─────


def test_every_decision_reason_code_has_a_declared_bucket() -> None:
    """Todo código del dueño (``DecisionReasonCode``) tiene familia declarada (aunque sea ``other``)."""
    declared = set(VETO_BUCKET_BY_REASON)
    for code in get_args(DecisionReasonCode):
        if code == "approved":  # no es un veto: es la aprobación.
            continue
        assert code in declared, f"codigo sin familia declarada: {code}"


def test_the_top_n_literal_is_read_from_its_owner() -> None:
    """``top_n_excluded`` se importa del dueño; su familia es ``top_n`` (no se duplica el literal)."""
    assert VETO_BUCKET_BY_REASON[TOP_N_EXCLUDED] == BUCKET_TOP_N


# ── parse_journal_reasons ──────────────────────────────────────────────────────────────────────


def test_journal_reasons_parse_the_runner_format() -> None:
    assert parse_journal_reasons(["regime_invalid:40", "top_n_excluded:24"]) == {
        "regime_invalid": 40,
        "top_n_excluded": 24,
    }


def test_journal_reasons_bare_code_counts_one_and_ignores_blank() -> None:
    assert parse_journal_reasons(["regime_invalid", "", "  ", "top_n_excluded:2"]) == {
        "regime_invalid": 1,
        "top_n_excluded": 2,
    }


def test_journal_reasons_sum_duplicate_codes() -> None:
    assert parse_journal_reasons(["regime_invalid:2", "regime_invalid:3"]) == {"regime_invalid": 5}


# ── classify_veto_reasons ──────────────────────────────────────────────────────────────────────


def test_classify_separates_regime_governor_top_n_liquidity_and_risk() -> None:
    """Las cinco causas no se mezclan: el operador ve POR QUÉ no se operó, no sólo que no se operó."""
    buckets = classify_veto_reasons(
        {
            "regime_invalid": 4,
            "governor_halted": 1,
            "top_n_excluded": 3,
            "liquidity_unknown": 2,
            "edge_below_threshold": 5,
            "sector_unknown": 1,
        }
    )
    assert buckets[BUCKET_REGIME] == {"regime_invalid": 4}
    assert buckets[BUCKET_GOVERNOR] == {"governor_halted": 1}
    assert buckets[BUCKET_TOP_N] == {"top_n_excluded": 3}
    assert buckets[BUCKET_LIQUIDITY] == {"liquidity_unknown": 2}
    assert buckets[BUCKET_RISK] == {"edge_below_threshold": 5}
    assert buckets[BUCKET_DATA] == {"sector_unknown": 1}


def test_classify_always_returns_every_bucket_even_when_empty() -> None:
    buckets = classify_veto_reasons({})
    assert tuple(buckets) == OPERABILITY_BUCKETS
    assert all(bucket == {} for bucket in buckets.values())


def test_unknown_reason_is_counted_in_other_and_never_dropped() -> None:
    """Un código sin familia conocida se declara en ``other``: la contabilidad no pierde entradas."""
    buckets = classify_veto_reasons({"reason_from_the_future": 7})
    assert buckets[BUCKET_OTHER] == {"reason_from_the_future": 7}
    assert veto_counted(buckets) == 7


def test_classify_accumulates_codes_within_the_same_family() -> None:
    buckets = classify_veto_reasons({"edge_below_threshold": 2, "plan_invalid": 3})
    assert buckets[BUCKET_RISK] == {"edge_below_threshold": 2, "plan_invalid": 3}
    assert veto_counted(buckets) == 5


# ── veto_counted ───────────────────────────────────────────────────────────────────────────────


def test_veto_counted_sums_all_families_including_other() -> None:
    buckets = classify_veto_reasons(
        {"regime_invalid": 40, TOP_N_EXCLUDED: 24, "unknown_code": 1}
    )
    assert veto_counted(buckets) == 65


# ── symbols_operable ───────────────────────────────────────────────────────────────────────────


def test_symbols_operable_counts_only_symbols_that_admit_long() -> None:
    """Del watch real: 4 ``range`` admiten LONG y 4 ``trend_down`` no (el agregado los veta todos)."""
    assert symbols_operable(_FORWARD_SMOKE["marketRegime"]) == 4


def test_symbols_operable_falls_back_to_counts_when_by_symbol_is_absent() -> None:
    regime = {"counts": {"range": 3, "trend_up": 2, "trend_down": 4}}
    assert symbols_operable(regime) == 5


def test_symbols_operable_is_none_when_unmeasured_never_zero() -> None:
    """Sin datos no se publica un ``0``: se declara no medido."""
    assert symbols_operable({}) is None


# ── pair_capable / pair_active ─────────────────────────────────────────────────────────────────


def test_pair_capable_is_true_even_when_the_pair_is_not_active() -> None:
    """El smoke real tiene la arquitectura LISTA (8 símbolos) pero sólo una versión operando."""
    assert pair_capable(_FORWARD_SMOKE) is True
    assert pair_active(_FORWARD_SMOKE) is False


def test_pair_capable_reads_the_explicit_flag_without_confusing_it_with_active() -> None:
    """Un payload v2.77 con ``pairCapable=true`` y ``pairActive=false`` NO se lee como activo."""
    payload = {"pairCapable": True, "pairActive": False, "secondaryActive": False}
    assert pair_capable(payload) is True
    assert pair_active(payload) is False


def test_pair_capable_is_false_with_a_single_symbol_watch() -> None:
    assert pair_capable({"watchSize": 1}) is False


def test_pair_active_requires_a_second_version_and_its_watch() -> None:
    payload = {"secondaryActive": True, "versionB": "active-v1", "watchB": ["BBB"]}
    assert pair_active(payload) is True
    assert pair_active({**payload, "versionB": ""}) is False
    assert pair_active({**payload, "watchB": []}) is False
    assert pair_active({**payload, "secondaryActive": False}) is False


def test_pair_active_reads_the_legacy_pair_available_alias() -> None:
    assert pair_active({"pairAvailable": True}) is True


# ── operability_state ──────────────────────────────────────────────────────────────────────────


def test_state_no_signal_only_without_proposals_and_without_vetoes() -> None:
    assert operability_state({"proposals": 0, "vetoes": 0, "fills": 0, "closed": 0}) == STATE_NO_SIGNAL


def test_state_vetoed_when_there_were_vetoes_even_without_proposals() -> None:
    """Con vetos NO se puede leer "no hay señal": hubo una causa (régimen, TOP_N, ...)."""
    assert operability_state({"proposals": 0, "vetoes": 64, "fills": 0, "closed": 0}) == STATE_VETOED


def test_state_operated_when_there_was_a_fill_or_a_close() -> None:
    assert operability_state({"proposals": 1, "vetoes": 0, "fills": 1, "closed": 0}) == STATE_OPERATED
    assert operability_state({"proposals": 1, "vetoes": 0, "fills": 0, "closed": 1}) == STATE_OPERATED


# ── build_operability_record (el smoke real de punta a punta) ───────────────────────────────────


def test_record_from_the_real_forward_smoke() -> None:
    record = build_operability_record(_FORWARD_SMOKE, day="2026-09-26")
    assert record["day"] == "2026-09-26"
    assert record["regime"] == "trend_down"
    assert record["operationalRegime"] == "BEAR_TREND"
    assert record["entriesAllowedLong"] is False
    assert record["watchSize"] == 8
    assert record["symbolsOperable"] == 4
    assert record["decided"] == 64
    assert record["proposals"] == 0
    assert record["vetoes"] == 64
    assert record["fills"] == 0
    assert record["measurableCycles"] == 0
    assert record["state"] == STATE_VETOED
    assert record["vetoCounted"] == 64
    assert record["vetoByBucket"][BUCKET_REGIME] == {"regime_invalid": 40}
    assert record["vetoByBucket"][BUCKET_TOP_N] == {"top_n_excluded": 24}
    assert record["vetoByBucket"][BUCKET_LIQUIDITY] == {}
    assert record["topVetoCodes"] == [("regime_invalid", 40), ("top_n_excluded", 24)]
    assert record["priceSources"] == {"live": 0, "close": 8, "missing": 0}
    assert record["pairCapable"] is True
    assert record["pairActive"] is False
    assert record["secondaryActive"] is False
    assert record["versions"] == ["v76-forward-c3d8"]


def test_record_veto_counted_matches_the_declared_vetoes() -> None:
    """La contabilidad por familias cuadra con los vetos del turno (no se pierde ningún código)."""
    record = build_operability_record(_FORWARD_SMOKE, day="2026-09-26")
    assert record["vetoCounted"] == record["vetoes"]


def test_record_without_journal_reasons_declares_empty_buckets_not_invented() -> None:
    payload = {**_FORWARD_SMOKE, "journalReasons": []}
    record = build_operability_record(payload, day="2026-09-27")
    assert record["vetoCounted"] == 0
    assert tuple(record["vetoByBucket"]) == OPERABILITY_BUCKETS


# ── render_operability_table ───────────────────────────────────────────────────────────────────


def test_render_table_is_deterministic_and_declares_the_families() -> None:
    records = [
        build_operability_record(_FORWARD_SMOKE, day="2026-09-26"),
        build_operability_record(_FORWARD_SMOKE, day="2026-09-27"),
    ]
    rendered = render_operability_table(records)
    assert "2026-09-26" in rendered
    assert "BEAR_TREND" in rendered
    assert "4/8" in rendered
    assert "CAPAZ" in rendered
    assert "regime=40" in rendered
    assert "top_n=24" in rendered
    assert rendered == render_operability_table(records)
