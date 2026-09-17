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
4. ``liquidity_insufficient``— liquidez/capacidad insuficiente (dato presente y nulo).
5. ``liquidity_unknown``     — liquidez NO conocida (V2.40.1: ``None`` no es "perfecta").
6. ``edge_below_threshold``  — score de oportunidad por debajo del umbral.
7. ``risk_budget_exceeded``  — presupuesto de riesgo restante agotado.
8. ``correlation_conflict``  — correlación con posiciones existentes por encima del tope.
9. ``correlation_unknown``   — correlación NO calculada con el tope activo (V2.40.1).
10. ``sector_unknown``/``sector_conflicting``/``sector_stale`` — sector del candidato NO
    resoluble de forma fiable (V2.40.1: la ausencia de sector NO se asume exenta).
11. ``sector_exposure_unverifiable`` — alguna posición abierta tiene sector no resoluble,
    así que la concentración sectorial de la cesta no puede comprobarse.
12. ``risk_measurement_partial``/``risk_measurement_unknown`` — el riesgo agregado de la
    cesta solo cubre parte de las posiciones (o ninguna): es un SUELO, no el total
    (V2.40.4).
13. ``exposure_measurement_partial``/``exposure_measurement_unknown`` — la exposición
    agregada no cubre todas las posiciones (V2.40.4).
14. ``open_orders_unmeasurable`` — hay órdenes pendientes cuyo capital/riesgo/exposición
    no se puede afirmar (o el libro no se pudo leer): no se añade riesgo sobre capital ya
    comprometido (V2.40.4).
15. ``concentration_exceeded``— concentración activo/sector por encima del límite.
16. ``risk_reward_below_threshold`` — R/R por debajo del mínimo.
17. ``atr_unknown``           — no hay geometría de riesgo: ni stop declarado ni ATR
    verificable (V2.42/2b, E2). Antes se reportaba como R/R insuficiente, que era un
    diagnóstico falso: el problema no es la relación, es que no hay nivel con el que
    calcularla.
18. ``plan_invalid``          — el ``TradePlan`` construido se contradice a sí mismo
    (V2.40.4): un plan incoherente no se emite, se veta con sus violaciones en el journal.

Todos los vetos de "dato ausente" (``*_unknown``, ``sector_*``, ``sector_exposure_unverifiable``,
``*_measurement_*``, ``open_orders_unmeasurable``) son ``fail-closed``: en AUTO un dato que no
se puede verificar NO autoriza entrada.

La DECISIÓN de tamaño la delega en ``RiskAllocator`` (la estrategia nunca fija lote);
los niveles SL/TP se derivan por ATR (``compute_atr_stop``/``compute_take_profit``) o
de los niveles que aporte la estrategia. El contrato de salida es un ``TradePlan``.

SIM-only / fail-closed: un fallo de cálculo o un input inválido ⇒ decisión HOLD/BLOCKED
(nunca una orden inventada).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from bolsa_analytics.cognitive.auto_portfolio_snapshot import AutoPortfolioSnapshot
from bolsa_analytics.cognitive.market_regime_gate import regime_allows_entry_for
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
)
from bolsa_analytics.cognitive.opportunity_ranker import OpportunityScore
from bolsa_analytics.cognitive.portfolio_fit import BasketPosition, compute_portfolio_fit
from bolsa_analytics.cognitive.portfolio_reservation import TradingCostModel
from bolsa_analytics.cognitive.risk_allocator import (
    RiskAllocatorConfig,
    compute_allocation,
    compute_atr_stop,
    compute_take_profit,
)
from bolsa_analytics.cognitive.trade_context import (
    SECTOR_CONFLICTING,
    SECTOR_KNOWN,
    SECTOR_STALE,
    SECTOR_UNKNOWN,
    UNKNOWN_SECTOR_VALUE,
    TradeContext,
)
from bolsa_analytics.cognitive.trade_plan import TradePlan, validate_trade_plan

logger = logging.getLogger(__name__)

PortfolioAction = Literal["ENTRY", "HOLD", "REDUCE", "EXIT"]
Direction = Literal["long", "short"]

DecisionReasonCode = Literal[
    "approved",
    "position_exists",
    "regime_invalid",
    "liquidity_insufficient",
    "liquidity_unknown",
    "risk_budget_exceeded",
    "concentration_exceeded",
    "correlation_conflict",
    "correlation_unknown",
    "sector_unknown",
    "sector_conflicting",
    "sector_stale",
    "sector_exposure_unverifiable",
    "stale_data",
    "edge_below_threshold",
    "atr_unknown",
    "risk_reward_below_threshold",
    "risk_measurement_partial",
    "risk_measurement_unknown",
    "exposure_measurement_partial",
    "exposure_measurement_unknown",
    "open_orders_unmeasurable",
    "plan_invalid",
    # AUTO-1 — no se pudo materializar la reserva de una aprobación (no existe aprobación
    # sin reserva): la decisión se degrada a veto con este motivo.
    "reservation_failed",
]

# Códigos que se registran como NO-TRADE en el journal (el resto es aprobado).
_NO_TRADE_REASONS: frozenset[str] = frozenset(
    {
        "position_exists",
        "regime_invalid",
        "liquidity_insufficient",
        "liquidity_unknown",
        "risk_budget_exceeded",
        "concentration_exceeded",
        "correlation_conflict",
        "correlation_unknown",
        "sector_unknown",
        "sector_conflicting",
        "sector_stale",
        "sector_exposure_unverifiable",
        "stale_data",
        "edge_below_threshold",
        "atr_unknown",
        "risk_reward_below_threshold",
        "risk_measurement_partial",
        "risk_measurement_unknown",
        "exposure_measurement_partial",
        "exposure_measurement_unknown",
        "open_orders_unmeasurable",
        "plan_invalid",
        # AUTO-1 — aprobación que no pudo materializarse en reserva.
        "reservation_failed",
    }
)

# Estado de sector ⇒ motivo de veto auditable (V2.40.1: nunca "exento" por ausencia).
_SECTOR_REJECTION_CODE: dict[str, DecisionReasonCode] = {
    SECTOR_UNKNOWN: "sector_unknown",
    SECTOR_CONFLICTING: "sector_conflicting",
    SECTOR_STALE: "sector_stale",
}

# V2.40.4 — estado de MEDICIÓN ⇒ motivo de veto auditable. Un agregado que solo suma lo
# que sabe medir es un SUELO: "sé 100" no autoriza a tratar el total como 100.
_MEASUREMENT_REJECTION_CODE: dict[str, DecisionReasonCode] = {
    MEASUREMENT_PARTIAL: "risk_measurement_partial",
    MEASUREMENT_UNKNOWN: "risk_measurement_unknown",
}


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
    # V2.40.1 (fail-closed): un dato de cartera NO verificable NO autoriza entrada.
    # ``require_sector`` exige sector resoluble del candidato y de las posiciones
    # abiertas; ``require_liquidity`` exige liquidez conocida. Desactivarlos es una
    # decisión EXPLÍCITA del llamante (herramientas manuales/legacy), nunca el default.
    require_sector: bool = True
    require_liquidity: bool = True
    # V2.40.4 (fail-closed): un agregado de cartera INCOMPLETO no autoriza aumentar
    # exposición. ``risk_used`` derivado de posiciones que no todas declaran su riesgo
    # es un SUELO, y una exposición que no pudo valorar todas las posiciones es un
    # ``>=``, no un total. Desactivarlo es una decisión EXPLÍCITA del llamante.
    require_complete_measurement: bool = True
    allocator: RiskAllocatorConfig = field(default_factory=RiskAllocatorConfig)
    # AUTO-1 — coste real de negociación. Con modelo, el sizing reserva presupuesto para
    # ``stop loss + comisión + spread + slippage`` y publica ``riskReal``. ``None``
    # mantiene el sizing histórico (solo stop) para no cambiar el contrato de golpe.
    cost_model: TradingCostModel | None = None


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
    # V2.40.4 — violaciones de coherencia del ``TradePlan`` que motivaron ``plan_invalid``.
    # El journal las publica tal cual: un veto por plan incoherente debe decir QUÉ campo
    # se contradecía, no solo que "algo no cuadraba".
    plan_violations: tuple[str, ...] = ()

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
            "planViolations": list(self.plan_violations),
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


def _sector_exposure_unverifiable(
    snapshot: AutoPortfolioSnapshot | None,
    *,
    config: PortfolioDecisionConfig,
) -> bool:
    """True si la concentración sectorial de la cesta NO puede comprobarse.

    V2.40.1: con ``require_sector``, una posición abierta cuyo sector no es resoluble
    (o el sentinel ``<unknown>``) hace que la exposición sectorial sea opaca. En AUTO
    eso NO autoriza aumentar exposición: se veta con ``sector_exposure_unverifiable``
    en vez de agrupar toda la cesta en un cajón y evaluar el candidato contra sí mismo.
    """
    if not config.require_sector or snapshot is None:
        return False
    for position in snapshot.positions:
        sector = position.sector
        if not isinstance(sector, str) or not sector.strip():
            return True
        if sector.strip() == UNKNOWN_SECTOR_VALUE:
            return True
    return False


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

    Esta función es aritmética: sin snapshot, sin ``max_sector_pct`` o sin equidad
    evaluable no afirma violación. La política *fail-closed* (V2.40.1) NO vive aquí sino
    en ``decide_portfolio``, que antes de llegar a este punto veta con
    ``sector_unknown``/``sector_conflicting``/``sector_stale`` si el sector del candidato
    no es fiable y con ``sector_exposure_unverifiable`` si alguna posición de la cesta
    tiene sector opaco (sin eso, todas caerían en el cajón ``<unknown>`` y el candidato
    se compararía solo consigo mismo).
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
    trade_context: TradeContext | None = None,
    config: PortfolioDecisionConfig | None = None,
    decision_id: str = "",
    expires_at: str | None = None,
    as_of: str = "",
) -> PortfolioDecision:
    """Decide la acción operativa para UNA oportunidad y produce el TradePlan.

    Devuelve una ``PortfolioDecision`` con ``approved=True`` solo si la entrada es
    operable. Cualquier veto se refleja en ``reason_codes`` y NO se inventa tamaño.

    ``trade_context`` (V2.40.1) es la vía preferente: aporta el **estado explícito** de
    sector/liquidez/correlación (``KNOWN``/``STALE``/``CONFLICTING``/``UNKNOWN``). Si no
    se aporta, se sintetiza desde los parámetros sueltos con ``TradeContext.from_legacy``:
    un valor presente es ``KNOWN`` y un ``None`` es ``UNKNOWN`` ⇒ veto, nunca "exento".
    """
    cfg = config if config is not None else PortfolioDecisionConfig()
    did = decision_id.strip() if decision_id.strip() else f"dec-{uuid4().hex[:12]}"
    score = opportunity_score.combined if opportunity_score is not None else None
    ctx = (
        trade_context
        if trade_context is not None
        else TradeContext.from_legacy(
            sector=sector,
            liquidity_notional=liquidity_notional,
            correlation=correlation_with_portfolio,
        )
    )
    # El sector que publica la decisión es el ya resuelto (o el declarado si el contexto
    # lo dio por CONFLICTING/STALE: se publica para que el journal muestre lo que se vio).
    resolved_sector = ctx.sector if ctx.sector is not None else sector

    def _reject(
        action: PortfolioAction,
        *codes: DecisionReasonCode,
        plan_violations: tuple[str, ...] = (),
    ) -> PortfolioDecision:
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
            sector=resolved_sector,
            plan_violations=plan_violations,
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

    # 4) Liquidez / capacidad. V2.40.1: desconocida NO es "perfecta" ⇒ fail-closed.
    if cfg.require_liquidity and not ctx.liquidity_is_known:
        return _reject("HOLD", "liquidity_unknown")
    if ctx.liquidity_notional is not None and ctx.liquidity_notional <= 0:
        return _reject("HOLD", "liquidity_insufficient")

    # 5) Edge esperado.
    if score is None or score < cfg.min_edge:
        return _reject("HOLD", "edge_below_threshold")

    # 6) Presupuesto de riesgo restante.
    if snapshot is not None and snapshot.risk_remaining is not None and snapshot.risk_remaining <= 0:
        return _reject("HOLD", "risk_budget_exceeded")

    # 7) Sector del candidato (V2.40.1). Con ``require_sector``, solo un sector KNOWN es
    # operable: desconocido / en conflicto con el catálogo / caducado ⇒ NO ENTRY.
    if cfg.require_sector and ctx.sector_status != SECTOR_KNOWN:
        return _reject("HOLD", _SECTOR_REJECTION_CODE.get(ctx.sector_status, "sector_unknown"))

    # 8) Correlación con posiciones existentes. Con tope activo, solo un valor CALCULADO
    # permite entrar; no hay valor ⇒ ``correlation_unknown`` (antes pasaba "sin problema").
    if cfg.max_correlation is not None:
        if not ctx.correlation_is_calculated:
            return _reject("HOLD", "correlation_unknown")
        if _correlation_conflict(ctx.correlation, cfg.max_correlation):
            return _reject("HOLD", "correlation_conflict")
    elif _correlation_conflict(ctx.correlation, cfg.max_correlation):
        return _reject("HOLD", "correlation_conflict")

    # 9) Exposición sectorial de la cesta verificable (V2.40.1): si alguna posición
    # abierta tiene sector opaco, la concentración NO puede comprobarse ⇒ NO ENTRY.
    if _sector_exposure_unverifiable(snapshot, config=cfg):
        return _reject("HOLD", "sector_exposure_unverifiable")

    # 10) Medición COMPLETA del riesgo y de la exposición agregados (V2.40.4). Colocado
    # DESPUÉS del gate sectorial para no cambiar el motivo reportado en los casos ya
    # cubiertos, y ANTES de dimensionar: decidir tamaño contra un riesgo que es un suelo
    # (o una exposición que es un ">=") es exactamente lo que hay que impedir.
    if cfg.require_complete_measurement and snapshot is not None:
        if snapshot.risk_measurement != MEASUREMENT_COMPLETE:
            return _reject(
                "HOLD",
                _MEASUREMENT_REJECTION_CODE.get(snapshot.risk_measurement, "risk_measurement_unknown"),
            )
        if snapshot.exposure.measurement != MEASUREMENT_COMPLETE:
            return _reject(
                "HOLD",
                "exposure_measurement_partial"
                if snapshot.exposure.measurement == MEASUREMENT_PARTIAL
                else "exposure_measurement_unknown",
            )
        # 10.b) Libro de órdenes pendientes MEDIBLE (V2.40.4): si no se puede afirmar
        # cuánto capital/riesgo/exposición hay comprometido en órdenes sin materializar
        # (o si ni siquiera se pudo leer el libro), NO se añade riesgo nuevo. "No hay
        # pendientes" solo se puede afirmar cuando la lectura fue COMPLETA.
        if not snapshot.order_book_is_complete:
            return _reject("HOLD", "open_orders_unmeasurable")

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
        # V2.42/2b (E2 · D3): sin stop declarado NI ATR verificable no hay geometría de
        # riesgo. Antes se reportaba como R/R insuficiente, que es un diagnóstico falso
        # (no se puede calcular una relación sin niveles): el ATR sintético ya no tapa
        # esta rama cuando la política exige precisión (``AUTO_ENGINE_SIM_V2_ATR_REQUIRED``).
        return _reject("HOLD", "atr_unknown")

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
        # ``buying_power`` es BRUTO; el capital reservado por órdenes pendientes se le
        # resta dentro del allocator (V2.40.4), que además lo registra con su propio
        # motivo (``CAP_RESERVED_CASH``) para que el journal distinga "no hay dinero" de
        # "el dinero está comprometido en órdenes sin materializar".
        buying_power=(
            snapshot.buying_power if snapshot is not None else None
        ),
        reserved_cash=(snapshot.reserved_cash if snapshot is not None else None),
        cost_model=cfg.cost_model,
    )
    if not allocation.approved:
        return _reject("HOLD", "risk_budget_exceeded")

    # 10) Concentración (as-if fill con el tamaño calculado).
    position_value = allocation.position_value or 0.0
    if _concentration_violates(
        snapshot=snapshot,
        instrument_id=instrument_id,
        sector=ctx.sector,
        position_value=position_value,
        config=cfg,
    ):
        return _reject("HOLD", "concentration_exceeded")

    # 11) R/R contra target primario (solo si la estrategia aporta target).
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
    # V2.40.4 — el plan que sale de aquí dimensiona una orden real: si se contradice a
    # sí mismo, NADA aguas abajo lo detecta (viaja serializado hasta el worker). Se
    # valida aquí, en el último punto donde todavía se puede vetar con motivo.
    plan_violations = validate_trade_plan(plan)
    if plan_violations:
        logger.error(
            "portfolio decision plan_invalid instrument=%s decision=%s violations=%s",
            instrument_id,
            did,
            list(plan_violations),
        )
        return _reject("HOLD", "plan_invalid", plan_violations=plan_violations)
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
        sector=resolved_sector,
    )
