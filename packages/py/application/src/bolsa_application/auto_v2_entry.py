"""AUTO 2.0 — capa de decisión V2 para el worker SIM (env-gated, default OFF).

Inserta el pipeline del Investment Operating System (OpportunityRanker →
PortfolioDecisionEngine → TradePlan) entre la señal cruda de la estrategia y la
liquidación SIM del ``AutoSimulationWorker``, **sin tocar** ledger, secuenciación por
cuenta, reconciliación ni idempotencia: el worker conserva su camino de settlement y
esta capa solo decide QUÉ propuesta emitir (o ninguna).

Activación: ``AUTO_ENGINE_SIM_V2=1`` (default OFF = comportamiento v2.39.x intacto).

Separación de responsabilidades:

* **Entradas** — los candidatos se rankean (TOP N) y se decide cada uno contra el
  snapshot de cartera con vetos fail-closed (stale/régimen/liquidez/edge/presupuesto/
  correlación/concentración/RR). El tamaño lo fija el ``RiskAllocator`` (nunca
  ``lot_qty``) y el resultado es un ``TradePlan`` que se convierte en propuesta.
* **Posiciones** — ``PositionManager`` (PositionState + ExitPlan + PositionDecision)
  sustituye la política global ``ProtectionConfig`` por geometría POR OPERACIÓN.

Fail-closed: sin snapshot fiable, sin geometría (stop) o sin edge, no se emite
propuesta. Nada aquí abre la vía LIVE (las propuestas siguen pasando por el RiskGate
y la Simulation Gate del worker).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from bolsa_analytics.cognitive.auto_portfolio_snapshot import (
    DATA_FRESH,
    PortfolioPosition,
    build_auto_portfolio_snapshot,
)
from bolsa_analytics.cognitive.market_regime_gate import (
    map_trial_regime,
    regime_is_exit_only,
)
from bolsa_analytics.cognitive.opportunity_ranker import (
    OpportunityScore,
    rank_opportunities,
    score_opportunity,
    select_top_opportunities,
)
from bolsa_analytics.cognitive.position_state import PositionState
from bolsa_analytics.cognitive.risk_allocator import RiskAllocatorConfig
from bolsa_analytics.cognitive.signal_identity import (
    SignalIdentity,
    bar_window,
    build_signal_identity,
)
from bolsa_application.auto_investment_system import trade_plan_to_decision_package
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.discovery_market_regime import (
    MATH_VERSION_MARKET_REGIME_V0,
    NO_REGIME,
    REGIME_HIGH_VOL,
    REGIME_RANGE,
    REGIME_TREND_DOWN,
    REGIME_TREND_UP,
    classify_market_regime,
)
from bolsa_application.portfolio_decision_engine import (
    PortfolioDecision,
    PortfolioDecisionConfig,
    decide_portfolio,
)
from bolsa_application.position_manager import PositionManagerResult, manage_position
from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

logger = logging.getLogger(__name__)

V2_ENGINE_ENV = "AUTO_ENGINE_SIM_V2"

_OPERATIONAL_REGIMES: frozenset[str] = frozenset(
    {
        "BULL_TREND",
        "BEAR_TREND",
        "SIDEWAYS",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "RISK_OFF",
        "UNKNOWN",
    }
)


def v2_engine_enabled() -> bool:
    """Env de habilitación del pipeline AUTO 2.0 (default OFF, fail-closed)."""
    return (os.getenv(V2_ENGINE_ENV) or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _env_float(name: str, default: float | None) -> float | None:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class V2Tunables:
    """Umbrales del pipeline V2 (env; defaults conservadores)."""

    top_n: int = 5
    # Umbral sobre la escala del OpportunityRanker (media ponderada 0..1). Una señal
    # que solo aporta edge (peso 0.30) + liquidez (0.10) alcanza como máximo 0.40, así
    # que el techo operativo realista está en esa banda: 0.30 exige edge sólido y
    # descarta señales tibias sin inventar componentes que la señal no aporta.
    min_edge: float = 0.30
    max_risk_per_trade_pct: float = 1.0
    max_position_pct: float = 20.0
    max_sector_pct: float | None = 40.0
    max_correlation: float | None = None
    atr_multiplier: float = 1.5
    target1_r: float = 1.0
    target2_r: float = 2.0
    # Presupuesto de riesgo abierto total, como % de equity (estado de cartera).
    risk_budget_pct: float = 6.0
    # ATR de reserva cuando la señal no lo aporta (fracción del precio).
    atr_pct_fallback: float = 0.02
    # Edge de reserva cuando la propuesta no declara confianza. El contrato actual
    # (``DecisionPackage``) no porta edge, así que el pipeline V2 necesita un valor con
    # el que poder rankear; es explícito y configurable (no se inventa por señal).
    default_edge: float = 0.9
    # Plantilla de salida (gradúa parciales de T1/T2). ``moderate`` reduce 30% en T1,
    # que es el estándar de la casa para gestión gradual; ``conservative`` (50%) y
    # ``aggressive_swing`` (0%: deja correr) quedan disponibles por env.
    exit_template: str = "moderate"
    regime_override: str | None = None
    # Timeframe de la señal (``signal_identity``): define la barra sobre la que se
    # deduplica. ``1d`` (default) evita re-emitir la MISMA señal intradía (el caso
    # real: worker cada 60s sobre una señal diaria); ``1m`` deduce a nivel de tick.
    signal_timeframe: str = "1d"

    def decision_config(self) -> PortfolioDecisionConfig:
        return PortfolioDecisionConfig(
            min_edge=self.min_edge,
            min_risk_reward=1.0,
            max_correlation=self.max_correlation,
            max_sector_pct=self.max_sector_pct,
            atr_multiplier=self.atr_multiplier,
            target1_r=self.target1_r,
            target2_r=self.target2_r,
            allocator=RiskAllocatorConfig(
                max_risk_per_trade_pct=self.max_risk_per_trade_pct,
                max_position_pct=self.max_position_pct,
            ),
        )


def tunables_from_env() -> V2Tunables:
    """Lee los umbrales del pipeline V2 de env (valores inválidos ⇒ default seguro)."""
    base = V2Tunables()
    raw_top = (os.getenv("AUTO_ENGINE_SIM_V2_TOP_N") or "").strip()
    try:
        top_n = int(raw_top) if raw_top else base.top_n
    except ValueError:
        top_n = base.top_n
    regime_raw = (os.getenv("AUTO_ENGINE_SIM_V2_REGIME") or "").strip()
    return V2Tunables(
        top_n=top_n if top_n > 0 else base.top_n,
        min_edge=_env_float("AUTO_ENGINE_SIM_V2_MIN_EDGE", base.min_edge) or base.min_edge,
        max_risk_per_trade_pct=_env_float(
            "AUTO_ENGINE_SIM_V2_RISK_PER_TRADE_PCT", base.max_risk_per_trade_pct
        )
        or base.max_risk_per_trade_pct,
        max_position_pct=_env_float(
            "AUTO_ENGINE_SIM_V2_MAX_POSITION_PCT", base.max_position_pct
        )
        or base.max_position_pct,
        max_sector_pct=_env_float(
            "AUTO_ENGINE_SIM_V2_MAX_SECTOR_PCT", base.max_sector_pct
        ),
        max_correlation=_env_float(
            "AUTO_ENGINE_SIM_V2_MAX_CORRELATION", base.max_correlation
        ),
        atr_multiplier=_env_float(
            "AUTO_ENGINE_SIM_V2_ATR_MULT", base.atr_multiplier
        )
        or base.atr_multiplier,
        risk_budget_pct=_env_float(
            "AUTO_ENGINE_SIM_V2_RISK_BUDGET_PCT", base.risk_budget_pct
        )
        or base.risk_budget_pct,
        atr_pct_fallback=_env_float(
            "AUTO_ENGINE_SIM_V2_ATR_PCT", base.atr_pct_fallback
        )
        or base.atr_pct_fallback,
        default_edge=_env_float(
            "AUTO_ENGINE_SIM_V2_DEFAULT_EDGE", base.default_edge
        )
        or base.default_edge,
        exit_template=(os.getenv("AUTO_ENGINE_SIM_V2_EXIT_TEMPLATE") or "").strip()
        or base.exit_template,
        regime_override=regime_raw or None,
        signal_timeframe=(os.getenv("AUTO_ENGINE_SIM_V2_TIMEFRAME") or "").strip()
        or base.signal_timeframe,
    )


def edge_from_package(pkg: Any, *, default: float) -> float:
    """Extrae el edge declarado por una propuesta (``memo`` estilo ``edge=0.85``).

    El ``DecisionPackage`` no porta confianza, así que se admite un canal explícito y
    opcional en ``memo`` para cuando la estrategia pueda aportarlo. Sin dato ⇒ el
    ``default`` configurado (nunca se inventa por señal).
    """
    raw = _memo_field(pkg, "edge")
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value != value:  # NaN
        return default
    return min(1.0, max(0.0, value))


def sector_from_package(pkg: Any) -> str | None:
    """Extrae el sector declarado por la propuesta (``memo`` estilo ``sector=tech``).

    El contrato actual no porta sector, así que la concentración sectorial solo puede
    evaluarse cuando la fuente lo declara. Sin dato ⇒ ``None`` (el motor lo trata como
    sector desconocido, nunca como "sin exposición").
    """
    raw = _memo_field(pkg, "sector")
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _memo_field(pkg: Any, key: str) -> str | None:
    """Lee ``clave=valor`` del ``memo`` de la propuesta (canal explícito y opcional)."""
    memo = getattr(pkg, "memo", None)
    if not isinstance(memo, str) or not memo:
        return None
    prefix = f"{key}="
    for chunk in memo.replace(",", " ").replace(";", " ").split():
        if chunk.startswith(prefix):
            return chunk[len(prefix) :] or None
    return None


def _coerce_operational_regime(regime: str | None) -> str:
    """Normaliza el régimen: acepta el eje operativo o la etiqueta de barras (v0)."""
    value = str(regime or "").strip().upper()
    if value in _OPERATIONAL_REGIMES:
        return value
    return map_trial_regime(regime)


@dataclass(frozen=True, slots=True)
class V2Signal:
    """Señal cruda de la estrategia para un símbolo en un tick."""

    instrument_id: str
    action: str  # "BUY" | "SELL" | "HOLD" (contrato del DecisionProvider)
    price: float
    atr: float | None = None
    edge: float | None = None  # confianza/edge de la estrategia (0..1).
    sector: str | None = None
    liquidity_notional: float | None = None
    strategy_version: str | None = None
    # Identidad/frescura de la señal (``signal_identity``): evita que la MISMA señal
    # sobre la MISMA barra se re-emita en cada turno (worker 60s vs señal D1).
    signal_id: str = ""
    bar_timestamp: str = ""
    valid_until: str = ""


@dataclass(frozen=True, slots=True)
class V2TickPlan:
    """Plan de decisión del tick: propuestas de entrada + journal auditable."""

    entry_packages: dict[str, DecisionPackage] = field(default_factory=dict)
    decisions: tuple[PortfolioDecision, ...] = ()
    ranked: tuple[OpportunityScore, ...] = ()
    journal_entries: tuple[DecisionJournalEntryRecord, ...] = ()
    regime: str = "UNKNOWN"
    as_of: str = ""

    @property
    def approved_symbols(self) -> tuple[str, ...]:
        return tuple(self.entry_packages.keys())


def build_worker_snapshot(
    *,
    account_id: str,
    equity: float,
    cash: float,
    open_positions: dict[str, float],
    entry_prices: dict[str, float],
    marks: dict[str, float] | None = None,
    stops: dict[str, float] | None = None,
    strategies: tuple[str, ...] = (),
    regime: str | None = None,
    risk_budget_pct: float | None = None,
    reconciliation_ok: bool = True,
    data_freshness: str = DATA_FRESH,
) -> Any:
    """Construye el ``AutoPortfolioSnapshot`` desde el libro del worker (SIM).

    La foto agregada sirve de base para TODAS las decisiones del tick. El riesgo ya
    consumido se deriva de la distancia al stop de cada posición (``stops`` cuando se
    conoce, si no la implícita por ATR) y el presupuesto total de ``risk_budget_pct``
    sobre equity, de modo que el motor puede vetar por presupuesto agotado.
    """
    marks = marks or {}
    stops = stops or {}
    budget = None
    if risk_budget_pct is not None and risk_budget_pct > 0:
        budget = equity * risk_budget_pct / 100.0
    positions: list[PortfolioPosition] = []
    for symbol, qty in open_positions.items():
        if qty <= 0:
            continue
        entry = entry_prices.get(symbol)
        mark = marks.get(symbol, entry)
        mv = float(mark) * float(qty) if mark is not None else None
        unrealized = None
        if entry is not None and mark is not None:
            unrealized = (float(mark) - float(entry)) * float(qty)
        risk_amount = None
        stop = stops.get(symbol)
        if stop is not None and entry is not None:
            risk_amount = max(0.0, (float(entry) - float(stop)) * float(qty))
        positions.append(
            PortfolioPosition(
                instrument_id=symbol,
                quantity=float(qty),
                market_value=mv,
                unrealized_pnl=unrealized,
                risk_amount=risk_amount,
            )
        )
    return build_auto_portfolio_snapshot(
        account_id=account_id,
        capital=equity,
        cash=cash,
        equity=equity,
        buying_power=cash,
        positions=positions,
        risk_budget=budget,
        active_strategies=strategies,
        market_regime=regime,
        last_reconciliation="clean" if reconciliation_ok else "attention",
        data_freshness=data_freshness,
    )


def signal_identity_for_bar(
    *,
    instrument_id: str,
    action: str,
    strategy_version: str | None,
    timeframe: str,
    moment: Any,
    extra: tuple[Any, ...] = (),
) -> SignalIdentity | None:
    """Identidad de la señal sobre la barra que contiene ``moment`` (fail-closed).

    ``None`` si el timeframe no se entiende, ``moment`` no tiene zona o falta el
    instrumento/acción: sin identidad no hay deduplicación posible, y el llamante debe
    tratarlo como "no verificable" (no como "libre de repetir").
    """
    window = bar_window(moment, timeframe)
    if window is None:
        return None
    bar_start, bar_close = window
    return build_signal_identity(
        instrument_id=instrument_id,
        strategy_version=strategy_version or "",
        timeframe=str(timeframe).strip(),
        bar_timestamp=bar_start,
        action=action,
        generated_at=moment.isoformat(),
        valid_until=bar_close,
        extra=extra,
    )


def _score_from_signal(signal: V2Signal) -> OpportunityScore:
    """Score de oportunidad de una señal (componentes derivados de la señal).

    Solo ``edge``/``liquidity``/``robustness`` tienen fuente directa en la señal; el
    resto queda a 0 (fail-closed: no se inventa evidencia que la señal no aporta).
    ``regime_fit`` lo aporta el llamante vía el gate de régimen (no aquí).
    """
    edge = signal.edge
    return score_opportunity(
        signal.instrument_id,
        edge=edge,
        liquidity=(
            1.0
            if signal.liquidity_notional is None
            else min(1.0, max(0.0, signal.liquidity_notional / 1_000_000.0))
        ),
    )


def plan_v2_tick(
    *,
    snapshot: Any,
    signals: list[V2Signal],
    regime: str | None = None,
    tunables: V2Tunables | None = None,
    as_of: str = "",
    actor: str = "auto-2.0",
    consumed_signal_ids: Iterable[str] = (),
) -> V2TickPlan:
    """Planifica las entradas del tick: rankeo → decisión → TradePlan → propuesta.

    Solo las señales de entrada (``BUY``) compiten por el TOP N; las de salida se
    gestionan aparte (``plan_v2_position_decision``). Cada decisión (aprobada o no)
    deja una entrada de journal con sus ``reason_codes``.

    ``consumed_signal_ids`` son las identidades de señal YA consumidas (oportunidades
    que este worker ya emitió sobre esa misma barra). Una señal repetida se descarta
    con ``signal_duplicate`` y una señal expirada (``valid_until < as_of``) con
    ``signal_stale``; ambas quedan en el journal con su motivo, nunca en silencio.
    """
    cfg = tunables if tunables is not None else V2Tunables()
    resolved_regime = _coerce_operational_regime(
        cfg.regime_override if cfg.regime_override is not None else regime
    )

    entry_signals = [s for s in signals if str(s.action).upper() == "BUY"]
    # Un símbolo, una señal: la primera manda (determinista, sin depender del orden).
    deduped: dict[str, V2Signal] = {}
    for s in entry_signals:
        deduped.setdefault(s.instrument_id, s)
    entry_signals = list(deduped.values())

    # Identidad y frescura ANTES del rankeo: no se rankea ni se le asigna presupuesto a
    # una oportunidad que ya se emitió en esta barra o que ha caducado.
    consumed = {str(x).strip() for x in consumed_signal_ids if str(x).strip()}
    blocked: list[DecisionJournalEntryRecord] = []
    eligible: list[V2Signal] = []
    for candidate in entry_signals:
        reason = _signal_rejection(candidate, consumed=consumed, as_of=as_of)
        if reason is None:
            eligible.append(candidate)
        else:
            blocked.append(
                _rejected_signal_entry(candidate, reason, actor=actor, as_of=as_of)
            )
    entry_signals = eligible

    scored: list[OpportunityScore] = [_score_from_signal(s) for s in entry_signals]
    ranked = rank_opportunities(scored)
    top = select_top_opportunities(ranked, top_n=cfg.top_n)
    score_by_symbol = {s.instrument_id: s for s in top}

    # Se evalúa en ORDEN DE RANK (el mejor reclama presupuesto/exposición primero) y las
    # aprobaciones del propio tick se ACUMULAN en la foto: sin esto, N candidatos del
    # mismo sector cada uno al 20% se aprobarían todos y el sector acabaría al 60%
    # saltándose su límite. El vetado por top-N (score None) se evalúa después y queda
    # registrado en el journal con su motivo.
    ordered: list[V2Signal] = []
    for score in top:
        signal = deduped.get(score.instrument_id)
        if signal is not None:
            ordered.append(signal)
    approved_ids = {s.instrument_id for s in ordered}
    ordered.extend(s for s in entry_signals if s.instrument_id not in approved_ids)

    packages: dict[str, DecisionPackage] = {}
    decisions: list[PortfolioDecision] = []
    journal: list[DecisionJournalEntryRecord] = []
    committed: list[PortfolioPosition] = []

    for signal in ordered:
        entry_score = score_by_symbol.get(signal.instrument_id)
        atr = signal.atr
        if atr is None and signal.price > 0:
            atr = signal.price * cfg.atr_pct_fallback
        working_snapshot = snapshot
        if committed:
            working_snapshot = replace(
                snapshot, positions=tuple(snapshot.positions) + tuple(committed)
            )
        decision = decide_portfolio(
            instrument_id=signal.instrument_id,
            direction="long",
            entry_price=signal.price if signal.price > 0 else None,
            atr=atr,
            opportunity_score=entry_score,
            snapshot=working_snapshot,
            regime=resolved_regime,
            liquidity_notional=signal.liquidity_notional,
            sector=signal.sector,
            config=cfg.decision_config(),
            as_of=as_of,
        )
        decisions.append(decision)
        package = trade_plan_to_decision_package(
            decision.trade_plan,
            source=(
                f"auto-2.0:{signal.strategy_version}"
                if signal.strategy_version
                else "auto-2.0"
            ),
            proposed_at=_stamp(as_of),
        )
        if package is not None:
            packages[signal.instrument_id] = package
            committed.append(_committed_position(signal, decision))
        journal.append(_journal_entry(decision, actor=actor, as_of=as_of))

    return V2TickPlan(
        entry_packages=packages,
        decisions=tuple(decisions),
        ranked=tuple(ranked),
        journal_entries=tuple((*blocked, *journal)),
        regime=resolved_regime,
        as_of=as_of,
    )


def plan_v2_position_decision(
    position: PositionState | None,
    *,
    mark_price: float,
    regime: str | None = None,
    thesis_invalid: bool = False,
    portfolio_recon_status: str | None = None,
    expires_at: str | None = None,
    now: str | None = None,
    exit_template: str | None = None,
    at: str | None = None,
) -> PositionManagerResult | None:
    """Decisión de gestión de una posición abierta vía ``PositionManager``.

    Devuelve ``None`` si no hay posición gestionable. La intención (hold/reduce/sell)
    la consume el worker por el MISMO spine de settlement (nunca un atajo).
    """
    return manage_position(
        position,
        mark_price=mark_price,
        regime=_coerce_operational_regime(regime),
        thesis_invalid=thesis_invalid,
        portfolio_recon_status=portfolio_recon_status,
        expires_at=expires_at,
        now=now,
        template_id=exit_template or None,
        at=at,
    )


def position_manager_package(
    result: PositionManagerResult | None,
    *,
    source_prefix: str = "auto-2.0-position",
) -> DecisionPackage | None:
    """Convierte el resultado del PositionManager en propuesta (o ``None`` si hold)."""
    if result is None:
        return None
    if result.order_action == "hold":
        return None
    qty = result.order_qty
    if qty is None or qty <= 0:
        return None
    reasons = ",".join(result.exit_reasons) or "managed"
    return DecisionPackage(
        action="SELL",
        instrument_id=result.position.instrument_id,
        quantity=float(qty),
        suggested_price=float(result.position.current_stop or 0.0),
        source=f"{source_prefix}:{reasons}",
    )


def _committed_position(
    signal: V2Signal, decision: PortfolioDecision
) -> PortfolioPosition:
    """Posición comprometida en ESTE tick (para que los siguientes candidatos la vean)."""
    allocation = decision.allocation or {}
    return PortfolioPosition(
        instrument_id=signal.instrument_id,
        quantity=float(allocation.get("quantity") or 0.0),
        market_value=float(allocation.get("positionValue") or 0.0) or None,
        sector=signal.sector,
    )


def _stamp(as_of: str) -> str:
    if as_of:
        return as_of
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# Motivos de descarte de una señal ANTES de decidir (auditables en el journal).
SIGNAL_DUPLICATE = "signal_duplicate"
SIGNAL_STALE = "signal_stale"


def _signal_rejection(
    signal: V2Signal, *, consumed: set[str], as_of: str
) -> str | None:
    """Motivo por el que la señal no debe generar una oportunidad nueva (o ``None``).

    Dos reglas, en este orden:

    1. ``signal_duplicate`` — la identidad (instrumento+versión+timeframe+barra+acción)
       ya se consumió: es la MISMA señal sobre la MISMA barra re-emitida por el turno
       siguiente (worker 60s sobre señal D1), no una oportunidad nueva.
    2. ``signal_stale`` — la señal caducó (``valid_until < as_of``): alimentar una
       decisión con una barra vieja sería decidir sobre datos que ya no rigen.

    Sin identidad (``signal_id`` vacío) no se puede deduplicar y NO se descarta: el
    dedupe es anti-*churn*, no un gate de riesgo, y bloquear entradas porque el reloj o
    el timeframe no se entienden convertiría un fallo de formato en una parada del motor.
    Queda auditado en el journal con ``signalId: ""``.
    """
    signal_id = str(signal.signal_id or "").strip()
    if not signal_id:
        return None
    if signal_id in consumed:
        return SIGNAL_DUPLICATE
    valid_until = str(signal.valid_until or "").strip()
    if valid_until and as_of and str(as_of) > valid_until:
        return SIGNAL_STALE
    return None


def _rejected_signal_entry(
    signal: V2Signal, reason: str, *, actor: str, as_of: str
) -> DecisionJournalEntryRecord:
    """Entrada de journal de una señal descartada por identidad/frescura."""
    from uuid import uuid4

    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=f"REJ-{uuid4().hex[:12]}",
        event_type="auto_entry_decision",
        actor=actor,
        created_at=_stamp(as_of),
        instrument_id=signal.instrument_id,
        payload={
            "event": "auto_entry_decision",
            "instrumentId": signal.instrument_id,
            "action": "BUY",
            "approved": False,
            "reasonCodes": [reason],
            "regime": None,
            "sector": signal.sector,
            "tradePlan": None,
            "risk": None,
            "signalId": signal.signal_id,
            "barTimestamp": signal.bar_timestamp,
            "validUntil": signal.valid_until,
            "indicator": "strategy",
        },
    )


def _journal_entry(
    decision: PortfolioDecision, *, actor: str, as_of: str
) -> DecisionJournalEntryRecord:
    from uuid import uuid4

    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=decision.decision_id,
        event_type="auto_entry_decision",
        actor=actor,
        created_at=_stamp(as_of),
        instrument_id=decision.instrument_id,
        payload={
            "event": "auto_entry_decision",
            "instrumentId": decision.instrument_id,
            "action": decision.action,
            "approved": decision.approved,
            "reasonCodes": list(decision.reason_codes),
            "regime": decision.regime,
            "sector": decision.sector,
            "tradePlan": None if decision.trade_plan is None else decision.trade_plan.to_dict(),
            "risk": decision.allocation,
        },
    )


def regime_exit_only(regime: str | None) -> bool:
    """True si el régimen (operativo o de barras) fuerza modo exit-only."""
    return regime_is_exit_only(_coerce_operational_regime(regime))


# ── Régimen operativo real desde el clasificador de barras de discovery ───────────
#
# ``discovery_market_regime_v0`` es determinista, as-of y sin red: clasifica un tramo de
# barras en ``trend_up/trend_down/range/high_vol`` (o vacío). Es exactamente la fuente
# que AUTO necesita para no inventar régimen, y ya es la que etiqueta los trials del LAB.

# Prioridad del agregado del universo: gana el veredicto MÁS CONSERVADOR presente. Un
# solo instrumento en ``high_vol`` basta para que el mercado se lea como revuelto, y un
# solo ``trend_down`` impide declarar ``trend_up`` global (nunca se pinta de verde un
# universo mixto).
_REGIME_CONSERVATIVE_PRIORITY: tuple[str, ...] = (
    REGIME_HIGH_VOL,
    REGIME_TREND_DOWN,
    REGIME_RANGE,
    REGIME_TREND_UP,
)


def aggregate_trial_regime(regimes: Iterable[str | None]) -> str:
    """Régimen agregado del universo: el veredicto más conservador presente.

    Sin ningún régimen clasificable devuelve ``NO_REGIME`` (fail-closed ⇒ el eje
    operativo lo lee como ``UNKNOWN`` ⇒ exit-only).
    """
    present = {str(r or "").strip() for r in regimes}
    for label in _REGIME_CONSERVATIVE_PRIORITY:
        if label in present:
            return label
    return NO_REGIME


@dataclass
class DiscoveryRegimeSource:
    """Fuente de régimen operativo respaldada por barras (as-of, determinista).

    ``refresh()`` es la parte async (trae barras del universo y clasifica cada una);
    ``__call__()`` es la lectura síncrona que el hot path usa en el tick, de modo que
    decidir no depende de I/O. Un fallo al leer barras deja el régimen en ``NO_REGIME``
    (⇒ ``UNKNOWN`` ⇒ exit-only): nunca se asume un mercado operable por error.
    """

    bars_provider: Callable[[], Awaitable[Mapping[str, Sequence[Any]]]]
    math_version: str = MATH_VERSION_MARKET_REGIME_V0
    _trial_regime: str = field(default=NO_REGIME, init=False, repr=False)

    async def refresh(self) -> str:
        """Recalcula el régimen agregado desde las barras del universo."""
        try:
            bars_by_symbol = await self.bars_provider() or {}
        except Exception:  # noqa: BLE001 — sin barras no hay régimen (fail-closed).
            logger.exception("auto_v2 regime refresh failed (regimen UNKNOWN)")
            self._trial_regime = NO_REGIME
            return self._trial_regime
        regimes = [
            classify_market_regime(list(bars or []), math_version=self.math_version)
            for bars in bars_by_symbol.values()
        ]
        self._trial_regime = aggregate_trial_regime(regimes)
        return self._trial_regime

    def trial_regime(self) -> str:
        """Régimen de barras crudo (``trend_up``… o ``""``). Informativo/auditoría."""
        return self._trial_regime

    def __call__(self) -> str:
        """Régimen operativo cacheado (``BULL_TREND``… o ``UNKNOWN``)."""
        return map_trial_regime(self._trial_regime)


__all__ = [
    "V2_ENGINE_ENV",
    "DiscoveryRegimeSource",
    "V2Signal",
    "V2TickPlan",
    "V2Tunables",
    "aggregate_trial_regime",
    "build_worker_snapshot",
    "edge_from_package",
    "plan_v2_position_decision",
    "plan_v2_tick",
    "position_manager_package",
    "regime_exit_only",
    "sector_from_package",
    "tunables_from_env",
    "v2_engine_enabled",
]
