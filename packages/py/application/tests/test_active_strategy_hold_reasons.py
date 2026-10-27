"""B-5 — el HOLD de la ACTIVE declara POR QUÉ no operó (y deja de ser mudo).

Hallazgo de la auditoría 2026-10-26 (§3.7): la estrategia promovida exige dos flags
(``AUTO_ENGINE_SIM_ACTIVE_STRATEGY`` y ``..._ACTIVE_STRATEGY_SIGNAL``). Sin el segundo, el
decisor devolvía ``HOLD`` y **nada** lo declaraba: «no operó» y «no quiso operar» eran la
misma fila —y ninguna de las dos existía en el journal—.

Lo que se fija aquí:

1. Cada HOLD que NO viene de una señal evaluada lleva su motivo tipificado
   (``active_signal_disabled``, ``no_executable``, ``no_snapshot``, ``evaluation_failed``).
2. Un HOLD que SÍ evaluó la señal y no encontró nada se distingue (``no_signal``).
3. El plan del tick publica esas declaraciones **aparte** del embudo: no son oportunidades,
   no se cuentan como vistas y no consumen presupuesto.
4. El motivo es una declaración por ``(símbolo, motivo, barra)``, no una por señal repetida.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from bolsa_analytics.research.manifest import strategy_definition_from_preset
from bolsa_application.active_strategy_signal_evaluator import make_active_strategy_decider
from bolsa_application.auto_orchestrator import active_strategy_decider
from bolsa_application.auto_reason_codes import (
    ACTIVE_EVALUATION_FAILED,
    ACTIVE_HOLD_REASONS,
    ACTIVE_NO_EXECUTABLE,
    ACTIVE_NO_SIGNAL,
    ACTIVE_NO_SNAPSHOT,
    ACTIVE_SIGNAL_DISABLED,
    ACTIVE_STRATEGY_HOLD_EVENT,
    ACTIVE_WARMUP_UNMEASURABLE,
    WARMUP_INSUFFICIENT,
)
from bolsa_application.auto_v2_entry import (
    V2Signal,
    active_strategy_holds,
    build_active_strategy_hold_journal_entry,
    build_worker_snapshot,
    plan_v2_tick,
)
from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy

SYMBOL = "AAA"


@dataclass(frozen=True)
class _Bar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def _bars(count: int) -> list[_Bar]:
    return [
        _Bar(
            timestamp=f"2026-{1 + index // 28:02d}-{1 + index % 28:02d}",
            open=100.0 + 0.1 * index - 0.2,
            high=100.0 + 0.1 * index + 0.5,
            low=100.0 + 0.1 * index - 0.5,
            close=100.0 + 0.1 * index,
            volume=1000.0,
        )
        for index in range(count)
    ]


def _active(preset: str | None) -> ActiveStrategy:
    definition: dict[str, Any] = {"lot_qty": 100.0, "watch": [SYMBOL]}
    if preset is not None:
        definition["executable"] = strategy_definition_from_preset(preset, [SYMBOL])
    return ActiveStrategy(
        version_id="ver-b5",
        candidate_id="cand-b5",
        instrument_id=SYMBOL,
        name=preset or "sin-ejecutable",
        definition=definition,
    )


# ── el caso que pide la auditoría: ACTIVE cargada con la señal APAGADA ────────────────


def test_the_disabled_signal_declares_its_reason_instead_of_a_mute_hold() -> None:
    """``SIGNAL=0``: el decisor sigue en HOLD, pero ahora dice por qué."""
    decider = active_strategy_decider(
        active=_active("sma_crossover"),
        fallback=None,
        watch=(SYMBOL,),
        hold_reason=ACTIVE_SIGNAL_DISABLED,
    )

    decision = decider(SYMBOL)

    assert decision.action == "HOLD"
    assert decision.quantity == 0
    assert decision.hold_reason == ACTIVE_SIGNAL_DISABLED


def test_the_classic_decider_stays_silent_when_no_reason_is_declared() -> None:
    """Sin ``hold_reason`` el comportamiento histórico no cambia (Δ = 0)."""
    decider = active_strategy_decider(
        active=_active("sma_crossover"), fallback=None, watch=(SYMBOL,)
    )

    assert decider(SYMBOL).hold_reason is None


# ── los motivos del evaluador de señal real ──────────────────────────────────────────


def test_a_definition_without_executable_declares_no_executable() -> None:
    decider = make_active_strategy_decider(
        active=_active(None), watch=(SYMBOL,), bars_by_symbol=lambda _s: _bars(10)
    )

    decision = decider(SYMBOL)

    assert decision.action == "HOLD"
    assert decision.hold_reason == ACTIVE_NO_EXECUTABLE


def test_no_bar_loader_declares_no_snapshot() -> None:
    decider = make_active_strategy_decider(active=_active("sma_crossover"), watch=(SYMBOL,))

    decision = decider(SYMBOL)

    assert decision.action == "HOLD"
    assert decision.hold_reason == ACTIVE_NO_SNAPSHOT


def test_an_empty_window_declares_no_snapshot() -> None:
    """Sin barras no se evaluó: NO es «no había señal»."""
    decider = make_active_strategy_decider(
        active=_active("sma_crossover"), watch=(SYMBOL,), bars_by_symbol=lambda _s: []
    )

    decision = decider(SYMBOL)

    assert decision.action == "HOLD"
    assert decision.hold_reason == ACTIVE_NO_SNAPSHOT


def test_a_failed_evaluation_is_declared_not_dressed_as_no_signal() -> None:
    def _boom(_symbol: str) -> list[Any]:
        raise RuntimeError("el repo de barras falló")

    decider = make_active_strategy_decider(
        active=_active("sma_crossover"), watch=(SYMBOL,), bars_by_symbol=_boom
    )

    decision = decider(SYMBOL)

    assert decision.action == "HOLD"
    assert decision.hold_reason == ACTIVE_EVALUATION_FAILED


def test_the_warmup_shortfall_reuses_the_scan_literal() -> None:
    """La ventana corta es la MISMA causa que en el scan: un solo literal, de su dueño."""
    decider = make_active_strategy_decider(
        active=_active("golden_cross"), watch=(SYMBOL,), bars_by_symbol=lambda _s: _bars(120)
    )

    decision = decider(SYMBOL)

    assert decision.action == "HOLD"
    assert decision.hold_reason == WARMUP_INSUFFICIENT
    assert decision.hold_reason == decision.memo.split(":")[0]
    assert decision.memo.startswith(WARMUP_INSUFFICIENT)


# ── B-1 (ventana derivada): el warmup medido viaja con la decisión ────────────────────


def test_the_measured_warmup_travels_with_every_decision() -> None:
    """El número que dimensiona la ventana es un HECHO declarado, no un cálculo interno.

    Con 201 barras (la ventana que el worker debe pedir) el preset es evaluable y la
    decisión no es un HOLD por warmup, pero sigue declarando cuánto exige.
    """
    decider = make_active_strategy_decider(
        active=_active("golden_cross"),
        watch=(SYMBOL,),
        bars_by_symbol=lambda _s: _bars(201),
        signal_window_source="preset_warmup",
    )

    decision = decider(SYMBOL)

    assert decision.warmup_bars == 201
    assert decision.signal_window_source == "preset_warmup"
    assert decision.hold_reason != WARMUP_INSUFFICIENT


def test_a_light_preset_declares_its_single_bar_warmup() -> None:
    """``vwap_reclaim`` pide una barra: la ventana del entorno (120) ya la cubre."""
    decider = make_active_strategy_decider(
        active=_active("vwap_reclaim"),
        watch=(SYMBOL,),
        bars_by_symbol=lambda _s: _bars(120),
        signal_window_source="env",
    )

    decision = decider(SYMBOL)

    assert decision.warmup_bars == 1
    assert decision.signal_window_source == "env"


def test_an_unmeasurable_warmup_fails_closed_and_declares_it() -> None:
    """Un warmup que no se puede medir NO produce una ventana inventada.

    Se falla cerrado (``HOLD``, cantidad 0) y el motivo es ``warmup_unmeasurable``. El
    cargador de barras ni se consulta: sin número no hay ventana que pedir.
    """
    calls: list[str] = []

    def _loader(symbol: str) -> list[Any]:
        calls.append(symbol)
        return _bars(500)

    definition: dict[str, Any] = {
        "lot_qty": 100.0,
        "watch": [SYMBOL],
        "executable": {
            "indicatorSpecs": [{"definitionId": "sma", "parameters": {"period": 5000}}],
            "entries": {
                "operator": "all",
                "rules": [
                    {
                        "type": "indicator_compare",
                        "leftSpec": {"definitionId": "sma", "parameters": {"period": 5000}},
                        "operator": "gt",
                        "rightValue": 0,
                        "signalKind": "entry_long",
                    }
                ],
            },
        },
    }
    active = ActiveStrategy(
        version_id="ver-b1",
        candidate_id="cand-b1",
        instrument_id=SYMBOL,
        name="warmup-no-medible",
        definition=definition,
    )

    decision = make_active_strategy_decider(
        active=active, watch=(SYMBOL,), bars_by_symbol=_loader
    )(SYMBOL)

    assert decision.action == "HOLD"
    assert decision.quantity == 0
    assert decision.hold_reason == ACTIVE_WARMUP_UNMEASURABLE
    assert decision.warmup_bars is None
    assert calls == []


def test_an_evaluated_hold_is_declared_as_no_signal() -> None:
    """Se evaluó y no había señal: el HOLD legítimo, distinguible de los anteriores."""
    decider = make_active_strategy_decider(
        active=_active("vwap_reclaim"), watch=(SYMBOL,), bars_by_symbol=lambda _s: _bars(120)
    )

    decision = decider(SYMBOL)

    assert decision.action == "HOLD"
    assert decision.hold_reason == ACTIVE_NO_SIGNAL


def test_every_declared_reason_belongs_to_the_closed_vocabulary() -> None:
    assert {
        ACTIVE_SIGNAL_DISABLED,
        ACTIVE_NO_EXECUTABLE,
        ACTIVE_NO_SNAPSHOT,
        ACTIVE_EVALUATION_FAILED,
        ACTIVE_NO_SIGNAL,
        ACTIVE_WARMUP_UNMEASURABLE,
        WARMUP_INSUFFICIENT,
    } == set(ACTIVE_HOLD_REASONS)


# ── el plan del tick publica las declaraciones (y no las confunde con oportunidades) ──


def _snapshot() -> Any:
    return build_worker_snapshot(
        account_id="acc-1",
        equity=100_000.0,
        cash=80_000.0,
        open_positions={},
        entry_prices={},
        regime="BULL_TREND",
        risk_budget_pct=6.0,
    )


def _hold(*, reason: str | None, bar: str = "2026-09-15T00:00:00Z") -> V2Signal:
    return V2Signal(
        instrument_id=SYMBOL,
        action="HOLD",
        price=0.0,
        strategy_version="ver-b5",
        hold_reason=reason,
        bar_timestamp=bar,
    )


def _buy() -> V2Signal:
    return V2Signal(
        instrument_id=SYMBOL,
        action="BUY",
        price=100.0,
        atr=2.0,
        edge=0.9,
        sector="tech",
        liquidity_notional=1_000_000.0,
        strategy_version="ver-b5",
        signal_id="SIG-BUY",
        bar_timestamp="2026-09-15T00:00:00Z",
        valid_until="2026-09-16T00:00:00Z",
    )


def test_the_plan_publishes_the_hold_apart_from_the_funnel() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_hold(reason=ACTIVE_SIGNAL_DISABLED)],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )

    assert len(plan.active_strategy_holds) == 1, "el motivo SÍ se publica"
    # …pero un HOLD declarado NO es una oportunidad vista ni una decisión de entrada.
    assert plan.seen_signals == 0
    assert plan.opportunities == ()
    assert plan.journal_entries == ()


def test_the_plan_carries_the_declaration_and_the_reason() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_hold(reason=ACTIVE_NO_SNAPSHOT)],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )

    assert len(plan.active_strategy_holds) == 1
    hold = plan.active_strategy_holds[0]
    assert hold.instrument_id == SYMBOL
    assert hold.reason == ACTIVE_NO_SNAPSHOT
    assert hold.dedupe_key == (SYMBOL, ACTIVE_NO_SNAPSHOT, "2026-09-15T00:00:00Z")


def test_a_repeated_hold_on_the_same_bar_is_declared_once() -> None:
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_hold(reason=ACTIVE_SIGNAL_DISABLED), _hold(reason=ACTIVE_SIGNAL_DISABLED)],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )

    assert len(plan.active_strategy_holds) == 1, "una declaración por (símbolo, motivo, barra)"


def test_a_different_reason_or_bar_is_a_different_declaration() -> None:
    assert len(active_strategy_holds([_hold(reason=ACTIVE_NO_SNAPSHOT)])) == 1
    both = active_strategy_holds(
        [
            _hold(reason=ACTIVE_NO_SNAPSHOT),
            _hold(reason=ACTIVE_NO_EXECUTABLE),
            _hold(reason=ACTIVE_NO_SNAPSHOT, bar="2026-09-16T00:00:00Z"),
        ]
    )
    assert len(both) == 3


def test_an_uncatalogued_reason_is_not_published_as_if_it_were_known() -> None:
    assert active_strategy_holds([_hold(reason="lo_que_sea")]) == ()
    assert active_strategy_holds([_hold(reason=None)]) == ()


def test_a_hold_never_competes_for_the_portfolio() -> None:
    """Con una entrada real al lado, el HOLD declarado no altera el embudo ni la reserva."""
    plan = plan_v2_tick(
        snapshot=_snapshot(),
        signals=[_buy(), _hold(reason=ACTIVE_NO_SIGNAL)],
        regime="BULL_TREND",
        as_of="2026-09-15T09:00:00Z",
    )

    assert plan.approved_symbols == (SYMBOL,)
    assert plan.seen_signals == 1
    assert len(plan.active_strategy_holds) == 1


# ── el registro de journal ───────────────────────────────────────────────────────────


def test_the_journal_entry_uses_its_own_event_and_omits_absent_data() -> None:
    hold = active_strategy_holds([_hold(reason=ACTIVE_SIGNAL_DISABLED)])[0]

    entry = build_active_strategy_hold_journal_entry(
        hold, actor="auto-2.0", as_of="2026-09-15T09:00:00Z"
    )

    assert entry.payload["event"] == ACTIVE_STRATEGY_HOLD_EVENT
    assert entry.payload["event"] != "auto_entry_decision", "no es una entrada vetada"
    assert entry.payload["reasonCodes"] == [ACTIVE_SIGNAL_DISABLED]
    assert entry.payload["instrumentId"] == SYMBOL
    assert entry.payload["action"] == "HOLD"
    assert entry.payload["barTimestamp"] == "2026-09-15T00:00:00Z"
    assert entry.payload["strategyVersion"] == "ver-b5"
    # O-6: lo que no se midió no se rellena.
    assert "featureSource" not in entry.payload
    assert "signalWindowBars" not in entry.payload
    assert "holdDetail" not in entry.payload


def test_the_journal_entry_carries_the_warmup_sentence_and_the_window() -> None:
    signal = V2Signal(
        instrument_id=SYMBOL,
        action="HOLD",
        price=0.0,
        strategy_version="ver-b5",
        strategy_preset_key="golden_cross",
        hold_reason=WARMUP_INSUFFICIENT,
        hold_detail="warmup_insufficient: sma period=200 requiere >= 201 barras (ventana: 120)",
        feature_source="real",
        signal_window_bars=120,
        bar_timestamp="2026-09-15T00:00:00Z",
    )
    hold = active_strategy_holds([signal])[0]

    entry = build_active_strategy_hold_journal_entry(
        hold, actor="auto-2.0", as_of="2026-09-15T09:00:00Z"
    )

    assert entry.payload["strategyPresetKey"] == "golden_cross"
    assert entry.payload["featureSource"] == "real"
    assert entry.payload["signalWindowBars"] == 120
    assert entry.payload["holdDetail"].startswith(WARMUP_INSUFFICIENT)


@pytest.mark.parametrize(
    "reason",
    [ACTIVE_SIGNAL_DISABLED, ACTIVE_NO_EXECUTABLE, ACTIVE_NO_SNAPSHOT, ACTIVE_NO_SIGNAL],
)
def test_every_reason_survives_the_journal_round_trip(reason: str) -> None:
    hold = active_strategy_holds([_hold(reason=reason)])[0]

    entry = build_active_strategy_hold_journal_entry(
        hold, actor="auto-2.0", as_of="2026-09-15T09:00:00Z"
    )

    assert entry.payload["reasonCodes"] == [reason]
