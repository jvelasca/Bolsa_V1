"""PortfolioDecisionEngine — decisión operativa de cartera (AUTO 2.0 · P0).

Núcleo del "Investment Operating System": dado el mercado actual, el snapshot de
cartera, el capital, el riesgo y una oportunidad concreta, decide la mejor acción
(ENTRY/HOLD/REDUCE/EXIT) y produce el ``TradePlan`` resultante.

Separa las cuatro decisiones que hoy están mezcladas en el hot path::

    SIGNAL → OPPORTUNITY → PORTFOLIO DECISION → EXECUTION

Secuencia de veto (fail-closed; cada veto registra su ``reason_code`` en el
``DecisionJournal`` para que sea auditable por qué AUTO NO operó):

1. ``stale_data``            — datos de mercado/cartera no frescos.
2. ``position_exists``       — ya hay posición abierta (HOLD, sin nueva entrada).
3. ``regime_invalid``        — régimen operativo no permite entrada (UNKNOWN/RISK_OFF).
4. ``liquidity_insufficient``— liquidez/capacidad insuficiente.
5. ``edge_below_threshold``  — score de oportunidad por debajo del umbral.
6. ``risk_budget_exceeded``  — presupuesto de riesgo restante agotado.
7. ``correlation_conflict``  — correlación con posiciones existentes por encima del tope.
8. ``concentration_exceeded``— concentración activo/sector por encima del límite.
9. ``risk_reward_below_threshold`` — R/R por debajo del mínimo.

La DECISIÓN de tamaño la delega en ``RiskAllocator`` (la estrategia nunca fija lote);
los niveles SL/TP se derivan por ATR (``compute_atr_stop``/``compute_take_profit``) o
de los niveles que aporte la estrategia. El contrato de salida es un ``TradePlan``.

SIM-only / fail-closed: un fallo de cálculo o un input inválido ⇒ decisión HOLD/BLOCKED
(nunca una orden inventada).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from bolsa_analytics.cognitive.auto_portfolio_snapshot import AutoPortfolioSnapshot
from bolsa_analytics.cognitive.market_regime_gate import regime_allows_entry_for
from bolsa_analytics.cognitive.opportunity_ranker import OpportunityScore
from bolsa_analytics.cognitive.portfolio_fit import BasketPosition, compute_portfolio_fit
from bolsa_analytics.cognitive.risk_allocator import (
    RiskAllocatorConfig,
    compute_allocation,
    compute_atr_stop,
    compute_take_profit,
)
from bolsa_analytics.cognitive.trade_plan import TradePlan

PortfolioAction = Literal["ENTRY", "HOLD", "REDUCE", "EXIT"]
Direction = Literal["long", "short"]

DecisionReasonCode = Literal[
    "approved",
    "position_exists",
    "regime_invalid",
    "liquidity_insufficient",
    "risk_budget_exceeded",
    "concentration_exceeded",
    "correlation_conflict",
    "stale_data",
    "edge_below_threshold",
    "risk_reward_below_threshold",
]

# Códigos que se registran como NO-TRADE en el journal (el resto es aprobado).
_NO_TRADE_REASONS: frozenset[str] = frozenset(
    {
        "position_exists",
        "regime_invalid",
        "liquidity_insufficient",
        "risk_budget_exceeded",
        "concentration_exceeded",
        "correlation_conflict",
        "stale_data",
        "edge_below_threshold",
        "risk_reward_below_threshold",
    }
)


@dataclass(frozen=True, slots=True)
class PortfolioDecisionConfig:
    """Umbrales del motor de decisión (calibrables; defaults conservadores)."""

    min_edge: float = 0.5  # score combinado mínimo de oportunidad.
    min_risk_reward: float = 1.0  # R/R mínimo contra el target primario.
    max_correlation: float | None = None  # correlación máxima con posiciones abiertas.
    max_sector_pct: float | None = None  # límite de concentración por sector (as-if).
    atr_multiplier: float = 1.5  # k para el stop por ATR.
    target1_r: float = 1.0  # R del T1 (si la estrategia no aporta target).
    target2_r: float = 2.0  # R del T2.
    allocator: RiskAllocatorConfig = field(default_factory=RiskAllocatorConfig)


@dataclass(frozen=True, slots=True)
class PortfolioDecision:
    """Veredicto operativo auditable de una oportunidad."""

    decision_id: str
    instrument_id: str
    action: PortfolioAction
    direction: Direction
    approved: bool
    reason_codes: tuple[DecisionReasonCode, ...]
    opportunity_score: float | None
    trade_plan: TradePlan | None
    allocation: dict[str, Any] | None
    regime: str | None
    as_of: str
    # Sector ASUMIDO por el gate de concentración (auditoría: sin él no se puede
    # reconstruir por qué una decisión pasó o no el límite sectorial).
    sector: str | None = None

    @property
    def is_no_trade(self) -> bool:
        """True si la decisión NO produce operación (rechazo/HOLD), para el journal."""
        return bool(set(self.reason_codes) & _NO_TRADE_REASONS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisionId": self.decision_id,
            "instrumentId": self.instrument_id,
            "action": self.action,
            "direction": self.direction,
            "approved": self.approved,
            "reasonCodes": list(self.reason_codes),
            "opportunityScore": self.opportunity_score,
            "tradePlan": None if self.trade_plan is None else self.trade_plan.to_dict(),
            "allocation": self.allocation,
            "regime": self.regime,
            "asOf": self.as_of,
        }


def _round4(value: float) -> float:
    return round(value * 10000) / 10000


def _holds_position(snapshot: AutoPortfolioSnapshot | None, instrument_id: str) -> bool:
    if snapshot is None:
        return False
    return any(
        p.instrument_id == instrument_id and p.quantity > 0 for p in snapshot.positions
    )


def _correlation_conflict(
    correlation: float | None,
    max_correlation: float | None,
) -> bool:
    if correlation is None or max_correlation is None:
        return False
    return correlation > max_correlation


def _concentration_violates(
    *,
    snapshot: AutoPortfolioSnapshot | None,
    instrument_id: str,
    sector: str | None,
    position_value: float,
    config: PortfolioDecisionConfig,
) -> bool:
    """Concentración as-if por SECTOR: puesta propuesta + posiciones existentes.

    La concentración por ACTIVO ya la acota el ``RiskAllocator`` (``max_position_pct``
    capa la posición nueva); aquí se evalúa la concentración de SECTOR, que es
    portfolio-wide y solo puede verse sumando la puesta al resto de la cesta.

    Sin snapshot, sin ``max_sector_pct`` o sin equidad evaluable ⇒ no se veta (no se
    inventa una violación; el resto del motor ya es fail-closed).
    """
    if snapshot is None or config.max_sector_pct is None:
        return False
    existing = [
        BasketPosition(
            instrument_id=p.instrument_id,
            market_value=p.market_value,
            sector=p.sector,
        )
        for p in snapshot.positions
        if p.instrument_id != instrument_id
    ]
    proposal = BasketPosition(
        instrument_id=instrument_id, market_value=position_value, sector=sector
    )
    fit = compute_portfolio_fit(
        proposal=proposal,
        existing=existing,
        equity=snapshot.equity,
        max_sector_weight_pct=config.max_sector_pct,
    )
    return fit.violating_sector is not None


def _build_trade_plan(
    *,
    decision_id: str,
    instrument_id: str,
    direction: Direction,
    entry: float,
    stop: float,
    target1: float | None,
    target2: float | None,
    allocation: dict[str, Any],
    opportunity_score: float | None,
    expires_at: str | None,
) -> TradePlan:
    """Construye el ``TradePlan`` (contrato de salida) desde una decisión aprobada."""
    qty = float(allocation["quantity"])
    initial_risk_r = allocation.get("stopDistance")
    return TradePlan(
        decision_id=decision_id,
        instrument_id=instrument_id,
        direction=direction,
        status="TRIGGERED",
        quantity=qty,
        risk_pct=float(allocation["riskPct"]) if allocation.get("riskPct") is not None else 0.0,
        why_not=(),
        execution_allowed=qty > 0,
        opportunity_score=opportunity_score,
        actionability=0.95 if qty > 0 else 0.0,
        entry=entry,
        structural_stop=stop,
        expires_at=expires_at,
        entry_setup="none",
        thesis_id=decision_id,
        entry_condition="ready",
        target1=target1,
        target2=target2,
        initial_risk_r=initial_risk_r,
        risk_amount=allocation.get("riskAmount"),
        position_value=allocation.get("positionValue"),
        expected_rr=None,
        portfolio_fit=None,
        execution_constraints={"expiresAt": expires_at} if expires_at else None,
    )


def decide_portfolio(
    *,
    instrument_id: str,
    direction: Direction = "long",
    entry_price: float | None = None,
    stop_price: float | None = None,
    atr: float | None = None,
    target_price: float | None = None,
    opportunity_score: OpportunityScore | None = None,
    snapshot: AutoPortfolioSnapshot | None = None,
    regime: str | None = None,
    liquidity_notional: float | None = None,
    sector: str | None = None,
    correlation_with_portfolio: float | None = None,
    config: PortfolioDecisionConfig | None = None,
    decision_id: str = "",
    expires_at: str | None = None,
    as_of: str = "",
) -> PortfolioDecision:
    """Decide la acción operativa para UNA oportunidad y produce el TradePlan.

    Devuelve una ``PortfolioDecision`` con ``approved=True`` solo si la entrada es
    operable. Cualquier veto se refleja en ``reason_codes`` y NO se inventa tamaño.
    """
    cfg = config if config is not None else PortfolioDecisionConfig()
    did = decision_id.strip() if decision_id.strip() else f"dec-{uuid4().hex[:12]}"
    score = opportunity_score.combined if opportunity_score is not None else None

    def _reject(action: PortfolioAction, *codes: DecisionReasonCode) -> PortfolioDecision:
        return PortfolioDecision(
            decision_id=did,
            instrument_id=instrument_id,
            action=action,
            direction=direction,
            approved=False,
            reason_codes=codes,
            opportunity_score=score,
            trade_plan=None,
            allocation=None,
            regime=regime,
            as_of=as_of,
            sector=sector,
        )

    # 1) Frescura de datos.
    if snapshot is not None and not snapshot.data_is_fresh:
        return _reject("HOLD", "stale_data")

    # 2) Posición ya abierta ⇒ HOLD (sin nueva entrada).
    if _holds_position(snapshot, instrument_id):
        return _reject("HOLD", "position_exists")

    # 3) Régimen operativo (DIRECCIONAL: un LONG no se abre en tendencia bajista).
    if not regime_allows_entry_for(regime, direction):
        return _reject("HOLD", "regime_invalid")

    # 4) Liquidez / capacidad.
    if liquidity_notional is not None and liquidity_notional <= 0:
        return _reject("HOLD", "liquidity_insufficient")

    # 5) Edge esperado.
    if score is None or score < cfg.min_edge:
        return _reject("HOLD", "edge_below_threshold")

    # 6) Presupuesto de riesgo restante.
    if snapshot is not None and snapshot.risk_remaining is not None and snapshot.risk_remaining <= 0:
        return _reject("HOLD", "risk_budget_exceeded")

    # 7) Correlación con posiciones existentes.
    if _correlation_conflict(correlation_with_portfolio, cfg.max_correlation):
        return _reject("HOLD", "correlation_conflict")

    # Geometría: entry/stop/targets (ATR o niveles de la estrategia).
    entry = entry_price
    if entry is None or entry <= 0:
        return _reject("HOLD", "stale_data")  # sin precio ⇒ no operable.
    stop = stop_price
    if stop is None and atr is not None:
        stop = compute_atr_stop(
            entry=entry, atr=atr, atr_multiplier=cfg.atr_multiplier, direction=direction
        )
    if stop is None:
        return _reject("HOLD", "risk_reward_below_threshold")  # sin stop ⇒ no operable.

    # Tamaño por riesgo (delegado al RiskAllocator).
    risk_budget = snapshot.risk_remaining if snapshot is not None else None
    equity = snapshot.equity if snapshot is not None else None
    if equity is None or equity <= 0:
        return _reject("HOLD", "risk_budget_exceeded")
    allocation = compute_allocation(
        equity=equity,
        entry=entry,
        stop=stop,
        direction=direction,
        risk_budget=risk_budget,
        config=cfg.allocator,
        buying_power=snapshot.buying_power if snapshot is not None else None,
    )
    if not allocation.approved:
        return _reject("HOLD", "risk_budget_exceeded")

    # 8) Concentración (as-if fill con el tamaño calculado).
    position_value = allocation.position_value or 0.0
    if _concentration_violates(
        snapshot=snapshot,
        instrument_id=instrument_id,
        sector=sector,
        position_value=position_value,
        config=cfg,
    ):
        return _reject("HOLD", "concentration_exceeded")

    # 9) R/R contra target primario (solo si la estrategia aporta target).
    if target_price is not None:
        distance = allocation.stop_distance
        if distance is not None and distance > 0:
            reward = (
                target_price - entry if direction == "long" else entry - target_price
            )
            if reward / distance < cfg.min_risk_reward:
                return _reject("HOLD", "risk_reward_below_threshold")

    target1 = target_price if target_price is not None else compute_take_profit(
        entry=entry, stop=stop, r_multiple=cfg.target1_r, direction=direction
    )
    target2 = compute_take_profit(
        entry=entry, stop=stop, r_multiple=cfg.target2_r, direction=direction
    )

    plan = _build_trade_plan(
        decision_id=did,
        instrument_id=instrument_id,
        direction=direction,
        entry=entry,
        stop=stop,
        target1=target1,
        target2=target2,
        allocation=allocation.to_dict(),
        opportunity_score=score,
        expires_at=expires_at,
    )
    return PortfolioDecision(
        decision_id=did,
        instrument_id=instrument_id,
        action="ENTRY",
        direction=direction,
        approved=True,
        reason_codes=("approved",),
        opportunity_score=score,
        trade_plan=plan,
        allocation=allocation.to_dict(),
        regime=regime,
        as_of=as_of,
        sector=sector,
    )
