"""V2.47 — identidad formal de señales: la política de colisión deja de ser silenciosa.

Hasta V2.46, ``_dedupe_candidates`` colapsaba las señales del mismo instrumento a UNA por
clave canónica **sin dejar rastro**: la descartada desaparecía. Esta fase hace la política
EXPLÍCITA:

* Por defecto (``allow_distinct_strategies`` OFF) se conserva el comportamiento (mejor
  candidata gana), pero cada superada se journaliza con
  ``signal_superseded_by_candidate`` incluyendo AMBOS ``signal_id`` y ``strategy_version``.
* Con ``allow_distinct_strategies`` ON, dos ``strategy_version`` distintas sobre el mismo
  instrumento/barra NO se colapsan: compiten como oportunidades separadas y la cartera
  decide (capital/correlación). Como el libro del worker sostiene UNA posición por
  instrumento, si ambas ganan la segunda se declara
  ``signal_distinct_strategy_not_representable`` (nunca dos entradas sobre el mismo símbolo).

Módulo puro: sin I/O, sin reloj real, sin PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bolsa_application.auto_v2_entry import (
    SIGNAL_DISTINCT_STRATEGY_NOT_REPRESENTABLE,
    SIGNAL_SUPERSEDED_BY_CANDIDATE,
    V2Signal,
    V2Tunables,
    build_worker_snapshot,
    candidate_key,
    plan_v2_tick,
    signal_identity_for_bar,
    tunables_from_env,
)

_MOMENT = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)


def _snapshot(*, cash: float = 80_000.0):
    return build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=cash,
        open_positions={},
        entry_prices={},
        regime="BULL_TREND",
        risk_budget_pct=6.0,
    )


def _signal(
    symbol: str,
    *,
    version: str = "v42",
    edge: float | None = 0.9,
    price: float = 100.0,
    atr: float | None = 2.0,
) -> V2Signal:
    identity = signal_identity_for_bar(
        instrument_id=symbol,
        action="BUY",
        strategy_version=version,
        timeframe="1d",
        moment=_MOMENT,
    )
    assert identity is not None
    return V2Signal(
        symbol,
        "BUY",
        price=price,
        atr=atr,
        edge=edge,
        sector="tech",
        liquidity_notional=1_000_000.0,
        strategy_version=version,
        signal_id=identity.signal_id,
        bar_timestamp=identity.bar_timestamp,
        valid_until=identity.valid_until,
    )


def _reason_codes(plan) -> list[str]:
    out: list[str] = []
    for entry in plan.journal_entries:
        payload = entry.payload or {}
        out.extend(str(code) for code in payload.get("reasonCodes", ()))
    return out


# ── Clave de candidata ────────────────────────────────────────────────────────


def test_candidate_key_is_the_instrument_by_default() -> None:
    assert candidate_key(_signal("AAA", version="v42")) == "AAA"
    assert candidate_key(_signal("AAA", version="v43")) == "AAA"


def test_candidate_key_distinguishes_strategy_versions_when_allowed() -> None:
    assert (
        candidate_key(_signal("AAA", version="v42"), allow_distinct_strategies=True)
        == "AAA#v42"
    )
    assert (
        candidate_key(_signal("AAA", version="v43"), allow_distinct_strategies=True)
        == "AAA#v43"
    )
    # Sin versión declarada no se fabrica una: la clave sigue siendo el instrumento.
    blank = V2Signal(
        "AAA",
        "BUY",
        price=100.0,
        atr=2.0,
        edge=0.9,
        sector="tech",
        liquidity_notional=1_000_000.0,
        strategy_version="",
        signal_id="sig-blank",
        bar_timestamp="2026-09-15T00:00:00Z",
        valid_until="2026-09-15T23:59:59Z",
    )
    assert candidate_key(blank, allow_distinct_strategies=True) == "AAA"


# ── Política por defecto: colapso EXPLÍCITO ───────────────────────────────────


def test_the_default_policy_collapses_but_journals_the_superseded_candidate() -> None:
    lower = _signal("AAA", version="v42", edge=0.9)
    higher = _signal("AAA", version="v43", edge=0.95)
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[lower, higher],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )

    # Una sola candidata decide (comportamiento histórico)...
    assert len(plan.ranked) == 1
    # ...pero la descartada YA NO desaparece: queda con motivo tipificado y ambos ids.
    superseded = [
        entry.payload or {}
        for entry in plan.journal_entries
        if SIGNAL_SUPERSEDED_BY_CANDIDATE in (entry.payload or {}).get("reasonCodes", ())
    ]
    assert len(superseded) == 1
    payload = superseded[0]
    assert payload["signalId"] == lower.signal_id
    assert payload["supersededBySignalId"] == higher.signal_id
    assert payload["supersededStrategyVersion"] == "v42"
    assert payload["supersededByStrategyVersion"] == "v43"
    assert payload["distinctStrategies"] is True


def test_the_canonical_winner_is_the_best_edge_regardless_of_arrival_order() -> None:
    lower = _signal("AAA", version="v42", edge=0.5)
    higher = _signal("AAA", version="v43", edge=0.95)
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[higher, lower],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )
    payloads = [
        entry.payload or {}
        for entry in plan.journal_entries
        if SIGNAL_SUPERSEDED_BY_CANDIDATE in (entry.payload or {}).get("reasonCodes", ())
    ]
    assert len(payloads) == 1
    # El ganador es la mejor candidata (edge más alto), no la primera que llegó.
    assert payloads[0]["supersededBySignalId"] == higher.signal_id


def test_duplicate_same_strategy_instrument_still_collapses_with_a_journal_trail() -> None:
    """Dos señales de la MISMA versión son la misma candidata: se supera, no se duplica."""
    first = _signal("AAA", version="v42", edge=0.9)
    second = _signal("AAA", version="v42", edge=0.9)
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[first, second],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )
    assert len(plan.ranked) == 1
    payloads = [
        entry.payload or {}
        for entry in plan.journal_entries
        if SIGNAL_SUPERSEDED_BY_CANDIDATE in (entry.payload or {}).get("reasonCodes", ())
    ]
    assert len(payloads) == 1
    assert payloads[0]["distinctStrategies"] is False


# ── Política opt-in: competencia por la cartera, nunca dos entradas silenciosas ─


def test_distinct_strategies_compete_as_two_candidates_when_allowed() -> None:
    left = _signal("AAA", version="v42", edge=0.9)
    right = _signal("AAA", version="v43", edge=0.8)
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[left, right],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(allow_distinct_strategies=True),
    )

    # Las DOS versiones compiten: el ranking las distingue por su clave de candidata.
    assert len(plan.ranked) == 2
    assert {score.instrument_id for score in plan.ranked} == {"AAA#v42", "AAA#v43"}
    # Ninguna se descarta por el dedupe ciego.
    assert SIGNAL_SUPERSEDED_BY_CANDIDATE not in _reason_codes(plan)


def test_two_selected_strategies_on_one_instrument_are_not_double_emitted() -> None:
    left = _signal("AAA", version="v42", edge=0.9)
    right = _signal("AAA", version="v43", edge=0.8)
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[left, right],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(allow_distinct_strategies=True),
    )

    # El libro del worker sostiene una posición por instrumento: solo UNA propuesta.
    assert set(plan.entry_packages) == {"AAA"}
    # La segunda NO se pisa en silencio: queda un rechazo declarado. En el camino normal
    # la foto de trabajo ya la veta (``position_exists``: la primera reserva se proyecta
    # como posición); la guarda de representabilidad es la red defensiva que declararía el
    # motivo tipificado si esa proyección no bastara.
    reasons = _reason_codes(plan)
    assert "position_exists" in reasons or (
        SIGNAL_DISTINCT_STRATEGY_NOT_REPRESENTABLE in reasons
    )
    # Y no queda capital comprometido en vano: una sola reserva viva.
    assert len([row for row in plan.reservations if row.is_live]) == 1


def test_the_representability_guard_declares_a_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Red defensiva: si la foto de trabajo NO proyecta la reserva, la guarda declara.

    Con la proyección normal el motor ya veta la segunda candidata (``position_exists``);
    esta prueba aísla la guarda de representabilidad quitando es proyección, para que la
    segunda aprobación llegue viva y se vea que NO se emite: ni dos entradas sobre el mismo
    símbolo, ni capital reservado en vano.
    """
    monkeypatch.setattr(
        "bolsa_application.auto_v2_entry._working_snapshot",
        lambda snapshot, ledger: snapshot,
    )
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_signal("AAA", version="v42", edge=0.9), _signal("AAA", version="v43", edge=0.8)],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
        tunables=V2Tunables(allow_distinct_strategies=True),
    )

    assert SIGNAL_DISTINCT_STRATEGY_NOT_REPRESENTABLE in _reason_codes(plan)
    assert set(plan.entry_packages) == {"AAA"}
    assert len([row for row in plan.reservations if row.is_live]) == 1


def test_the_option_is_off_by_default_and_reads_its_env(monkeypatch: pytest.MonkeyPatch) -> None:
    assert V2Tunables().allow_distinct_strategies is False
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_ALLOW_DISTINCT_STRATEGIES", "1")
    assert tunables_from_env().allow_distinct_strategies is True
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_ALLOW_DISTINCT_STRATEGIES", "0")
    assert tunables_from_env().allow_distinct_strategies is False
