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
from typing import Any, cast

from bolsa_analytics.cognitive.auto_portfolio_snapshot import (
    DATA_FRESH,
    PortfolioPosition,
    build_auto_portfolio_snapshot,
)
from bolsa_analytics.cognitive.market_regime_gate import (
    map_trial_regime,
    regime_is_exit_only,
)
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
)
from bolsa_analytics.cognitive.operational_governor import (
    DrawdownPolicy,
    GovernorPolicy,
    OperationalAssessment,
    assess_from_measurements,
)
from bolsa_analytics.cognitive.opportunity_ranker import (
    TOP_N_EXCLUDED,
    OpportunityScore,
    rank_opportunities,
    score_opportunity,
    select_top_opportunities,
)
from bolsa_analytics.cognitive.portfolio_reservation import (
    PortfolioReservation,
    PortfolioRiskState,
    ReservationLedger,
    TradingCostModel,
    build_portfolio_risk_state,
    build_reservation,
    coerce_trading_cost,
    sector_risk_from_positions,
)
from bolsa_analytics.cognitive.position_state import PositionState
from bolsa_analytics.cognitive.risk_allocator import RiskAllocatorConfig
from bolsa_analytics.cognitive.signal_identity import (
    SignalIdentity,
    bar_window,
    build_signal_identity,
)
from bolsa_analytics.cognitive.trade_context import DEFAULT_MAX_AGE_DAYS, TradeContext
from bolsa_analytics.indicators.compute import compute_atr
from bolsa_application.auto_investment_system import trade_plan_to_decision_package
from bolsa_application.auto_reason_codes import RESERVATION_FAILED
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.discovery_market_regime import (
    MATH_VERSION_MARKET_REGIME_V0,
    MATH_VERSION_MARKET_REGIME_V1,
    NO_REGIME,
    REGIME_HIGH_VOL,
    REGIME_LOW_VOL,
    REGIME_RANGE,
    REGIME_TREND_DOWN,
    REGIME_TREND_UP,
    classify_market_regime,
)
from bolsa_application.portfolio_decision_engine import (
    DecisionReasonCode,
    PortfolioDecision,
    PortfolioDecisionConfig,
    decide_portfolio,
)
from bolsa_application.position_manager import (
    PositionManagerResult,
    PositionManagerSkip,
    manage_position_outcome,
)
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


def _env_flag(name: str, default: bool) -> bool:
    """Flag de entorno booleano, con el default EXPLÍCITO de la casa.

    Familia "off" (``0/false/off/no/none``) ⇒ ``False``; familia "on"
    (``1/true/on/yes``) ⇒ ``True``; cualquier otra cosa (vacío incluido) ⇒ ``default``.
    Un valor basura NO activa un veto de dinero: se queda en el default.
    """
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    if raw in {"0", "false", "off", "no", "none"}:
        return False
    if raw in {"1", "true", "on", "yes"}:
        return True
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
    # V2.42 slice 2b (E2 · decisión D3): el veto por ATR real nace DESACTIVADO y detrás de
    # un tunable (``AUTO_ENGINE_SIM_V2_ATR_REQUIRED``). Primero se cablea y se MIDE qué
    # fracción de señales trae ATR real; el veto se flipea con el número delante, porque
    # ``NO ENTRY`` es un cambio de régimen en simulado. Con el flag ON, una señal sin ATR
    # real NO se sustituye por el sintético: cae por el camino normal de NO ENTRY.
    atr_required: bool = False
    # V2.40.1 (P0): NO existe ``default_edge``. El edge de una oportunidad es el que
    # declara la estrategia o el que aporta su EdgeReport persistido; si no hay ninguno
    # vale 0 (el ranker ya puntúa 0 el componente ausente) y el motor veta por
    # ``edge_below_threshold``. "No tengo edge" nunca puede leerse como "edge = 0.9".
    # Plantilla de salida (gradúa parciales de T1/T2). ``moderate`` reduce 30% en T1,
    # que es el estándar de la casa para gestión gradual; ``conservative`` (50%) y
    # ``aggressive_swing`` (0%: deja correr) quedan disponibles por env.
    exit_template: str = "moderate"
    regime_override: str | None = None
    # Timeframe de la señal (``signal_identity``): define la barra sobre la que se
    # deduplica. ``1d`` (default) evita re-emitir la MISMA señal intradía (el caso
    # real: worker cada 60s sobre una señal diaria); ``1m`` deduce a nivel de tick.
    signal_timeframe: str = "1d"
    # AUTO-1 — coste real de negociación. ACTIVO por defecto: el presupuesto de riesgo
    # debe cubrir el stop Y las fricciones (comisión + spread + slippage), no solo el stop.
    # ``AUTO_ENGINE_SIM_V2_COST_MODEL=0`` lo desactiva EXPLÍCITAMENTE y devuelve el sizing
    # histórico. ``None`` = sin modelo (mismo efecto que desactivarlo).
    cost_model: TradingCostModel | None = field(default_factory=TradingCostModel)

    # --- V2.43 / AUTO-3 — gobernador de riesgo y mercado (ENTRADAS) -------------------
    # Matemática del clasificador de régimen de barras. ``v0`` por defecto: el
    # comportamiento histórico no cambia. ``v1`` AÑADE el tramo ``low_vol`` (opt-in).
    regime_math_version: str = MATH_VERSION_MARKET_REGIME_V0
    # Flag del gobernador. OFF por defecto ⇒ el camino V2 es BYTE-IDÉNTICO: nada de lo de
    # abajo se consulta. Se flipea con el número delante (mismo patrón que el veto de ATR).
    governor_enabled: bool = False
    # Cortes de drawdown del día (% de caída desde la marca de referencia). Declarados y
    # calibrables; SIEMPRE presentes (el mecanismo no depende del flag, solo su uso).
    governor_drawdown_reduced_pct: float = 5.0
    governor_drawdown_half_pct: float = 10.0
    governor_drawdown_no_entry_pct: float = 15.0
    governor_drawdown_exit_only_pct: float = 20.0
    # Notional mínimo (estricto: ``>``) para considerar la liquidez suficiente.
    governor_min_liquidity_notional: float = 0.0
    # Factor sobre ``min_edge`` en ``ENTRY_RESTRICTED`` (>= 1: nunca relaja el listón).
    governor_restricted_edge_factor: float = 2.0

    def governor_policy(self) -> GovernorPolicy:
        """Política del gobernador derivada de los tunables (pura, sin env)."""
        return GovernorPolicy(
            drawdown=DrawdownPolicy(
                reduced_pct=self.governor_drawdown_reduced_pct,
                half_pct=self.governor_drawdown_half_pct,
                no_entry_pct=self.governor_drawdown_no_entry_pct,
                exit_only_pct=self.governor_drawdown_exit_only_pct,
            ),
            min_liquidity_notional=self.governor_min_liquidity_notional,
            restricted_edge_factor=self.governor_restricted_edge_factor,
        )

    def decision_config(
        self, governor: OperationalAssessment | None = None
    ) -> PortfolioDecisionConfig:
        """Configuración del motor para este tick.

        ``governor`` (V2.43/AUTO-3) es la lectura del gobernador: con ella el tamaño se
        ESCALA (``risk_scale`` del estado) y, en ``ENTRY_RESTRICTED``, el listón de edge
        sube por ``restricted_edge_factor``. El motor además lee el PERMISO de la propia
        lectura y veta ``EXIT_ONLY``/``HALTED``. Sin lectura (``None``, flag OFF) la
        configuración es exactamente la histórica: nada se escala.
        """
        scale = 1.0
        min_edge = self.min_edge
        if governor is not None and governor.allows_new_entry:
            scale = governor.risk_scale
            if governor.state == "ENTRY_RESTRICTED":
                min_edge = self.min_edge * self.governor_restricted_edge_factor
        return PortfolioDecisionConfig(
            min_edge=min_edge,
            min_risk_reward=1.0,
            max_correlation=self.max_correlation,
            max_sector_pct=self.max_sector_pct,
            atr_multiplier=self.atr_multiplier,
            target1_r=self.target1_r,
            target2_r=self.target2_r,
            allocator=RiskAllocatorConfig(
                max_risk_per_trade_pct=self.max_risk_per_trade_pct * scale,
                max_position_pct=self.max_position_pct,
            ),
            cost_model=self.cost_model,
            governor=governor,
        )


def _cost_model_from_env() -> TradingCostModel | None:
    """Modelo de coste del sizing (AUTO-1); ``None`` si se desactiva explícitamente.

    Ausencia de ``AUTO_ENGINE_SIM_V2_COST_MODEL`` ⇒ modelo ACTIVO con los defaults de la
    casa (10 bps de comisión por lado, 2 bps de spread, 5 bps de slippage por lado). Un
    valor de la familia "off" lo desactiva; los bps son calibrables por env.
    """
    raw = (os.getenv("AUTO_ENGINE_SIM_V2_COST_MODEL") or "").strip().lower()
    if raw in {"0", "false", "off", "no", "none"}:
        return None
    base = TradingCostModel()
    return TradingCostModel(
        commission_bps=_env_float(
            "AUTO_ENGINE_SIM_V2_COMMISSION_BPS", base.commission_bps
        )
        or base.commission_bps,
        spread_bps=_env_float("AUTO_ENGINE_SIM_V2_SPREAD_BPS", base.spread_bps)
        or base.spread_bps,
        slippage_bps=_env_float("AUTO_ENGINE_SIM_V2_SLIPPAGE_BPS", base.slippage_bps)
        or base.slippage_bps,
        gap_bps=_env_float("AUTO_ENGINE_SIM_V2_GAP_BPS", base.gap_bps) or base.gap_bps,
        settings=base.settings,
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
        exit_template=(os.getenv("AUTO_ENGINE_SIM_V2_EXIT_TEMPLATE") or "").strip()
        or base.exit_template,
        regime_override=regime_raw or None,
        signal_timeframe=(os.getenv("AUTO_ENGINE_SIM_V2_TIMEFRAME") or "").strip()
        or base.signal_timeframe,
        # E2: el veto por ATR real es OPT-IN explícito (default OFF).
        atr_required=_env_flag("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", base.atr_required),
        # V2.43/AUTO-3 — matemática del régimen (``v0`` salvo petición explícita de ``v1``).
        regime_math_version=_regime_math_version_from_env(),
        # V2.43/AUTO-3 — gobernador de riesgo y mercado: OPT-IN explícito (default OFF) y
        # umbrales SANEADOS como bloque (ver ``_governor_env_overrides``).
        governor_enabled=_env_flag("AUTO_ENGINE_SIM_V2_GOVERNOR", base.governor_enabled),
        **_governor_env_overrides(base),
        cost_model=_cost_model_from_env(),
    )


def _governor_env_overrides(base: V2Tunables) -> dict[str, Any]:
    """Umbrales del gobernador leídos de env, saneados como POLÍTICA completa.

    Env es entrada no confiable y ``governor_policy()`` se construye en CADA tick (también
    con el flag OFF), así que un valor incoherente no puede llegar a la política: un corte
    de drawdown no estrictamente creciente, un número no finito o un
    ``restricted_edge_factor`` que RELAJARÍA el listón harían fallar el tick por una env
    mal puesta. Regla: se valida el bloque entero y, si algo no cuadra, se descartan los
    umbrales de env y quedan los defaults declarados (fail-closed, nunca a medias).
    """
    default_cuts = [
        base.governor_drawdown_reduced_pct,
        base.governor_drawdown_half_pct,
        base.governor_drawdown_no_entry_pct,
        base.governor_drawdown_exit_only_pct,
    ]
    env_cuts = [
        _env_float("AUTO_ENGINE_SIM_V2_GOV_DD_REDUCED_PCT", base.governor_drawdown_reduced_pct),
        _env_float("AUTO_ENGINE_SIM_V2_GOV_DD_HALF_PCT", base.governor_drawdown_half_pct),
        _env_float("AUTO_ENGINE_SIM_V2_GOV_DD_NO_ENTRY_PCT", base.governor_drawdown_no_entry_pct),
        _env_float("AUTO_ENGINE_SIM_V2_GOV_DD_EXIT_ONLY_PCT", base.governor_drawdown_exit_only_pct),
    ]
    # Se valida el BLOQUE: cuatro números finitos y no negativos, estrictamente crecientes.
    # Cualquier otra cosa descarta TODOS los cortes de env (no se mezcla env con defaults).
    cuts: list[float] = default_cuts
    if all(value is not None and _is_finite_non_negative(value) for value in env_cuts):
        candidate = [float(value) for value in env_cuts if value is not None]
        if all(a < b for a, b in zip(candidate, candidate[1:], strict=False)):
            cuts = candidate

    min_liquidity = _env_float(
        "AUTO_ENGINE_SIM_V2_GOV_MIN_LIQUIDITY", base.governor_min_liquidity_notional
    )
    if min_liquidity is None or not _is_finite_non_negative(min_liquidity):
        min_liquidity = base.governor_min_liquidity_notional
    else:
        min_liquidity = float(min_liquidity)

    factor = _env_float(
        "AUTO_ENGINE_SIM_V2_GOV_RESTRICTED_EDGE_FACTOR",
        base.governor_restricted_edge_factor,
    )
    if factor is None or not _is_finite_non_negative(factor) or float(factor) < 1.0:
        factor = base.governor_restricted_edge_factor
    else:
        factor = float(factor)

    reduced, half, no_entry, exit_only = cuts
    return {
        "governor_drawdown_reduced_pct": reduced,
        "governor_drawdown_half_pct": half,
        "governor_drawdown_no_entry_pct": no_entry,
        "governor_drawdown_exit_only_pct": exit_only,
        "governor_min_liquidity_notional": float(min_liquidity),
        "governor_restricted_edge_factor": float(factor),
    }


def _is_finite_non_negative(value: Any) -> bool:
    """True si ``value`` es un número finito ``>= 0`` (``bool`` excluido: no es medida)."""
    if value is None or isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and abs(number) != float("inf") and number >= 0


def _regime_math_version_from_env() -> str:
    """Matemática del clasificador de régimen pedida por env (``v0`` si no se entiende).

    Familia "off"/vacío/ausente ⇒ ``v0`` (el comportamiento histórico). Familia "v1"
    (``v1``/``1``/``latest``) ⇒ ``v1``. Cualquier otro valor ⇒ ``v0``: una matemática
    desconocida no puede activarse por error, y ``v0`` es el contrato ya auditado.
    """
    raw = (os.getenv("AUTO_ENGINE_SIM_V2_REGIME_MATH") or "").strip().lower()
    if raw in {"v1", "1", "latest"}:
        return MATH_VERSION_MARKET_REGIME_V1
    return MATH_VERSION_MARKET_REGIME_V0


def edge_from_package(pkg: Any) -> float | None:
    """Edge declarado por una propuesta (``memo`` estilo ``edge=0.85``) o ``None``.

    El ``DecisionPackage`` no porta confianza; se admite un canal explícito y opcional
    en ``memo``. **Sin dato devuelve ``None``** (V2.40.1/P0: el motor AUTO no tiene
    valor de reserva — inventar un edge convierte "no sé" en "oportunidad excelente").
    El llamante decide la fuente alternativa legítima (el EdgeReport persistido de la
    estrategia); si tampoco la hay, el componente vale 0 y el motor veta.
    """
    raw = _memo_field(pkg, "edge")
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if value != value:  # NaN
        return None
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
    # V2.40.1 — estado EXPLÍCITO de los gates de cartera (sector/liquidez/correlación).
    # Si se aporta, manda sobre ``sector``/``liquidity_notional`` sueltos: es la vía por
    # la que el worker comunica KNOWN/STALE/CONFLICTING/UNKNOWN sin perder información.
    trade_context: TradeContext | None = None


@dataclass(frozen=True, slots=True)
class V2TickPlan:
    """Plan de decisión del tick: propuestas de entrada + journal auditable.

    AUTO-1 — además de las propuestas, publica las **reservas vivas** del tick (identidad
    y dimensiones comprometidas) y el ``PortfolioRiskState`` resultante. Sin esto, el
    compromiso del tick solo existía como una lista local que moría al volver de la
    función: no se podía auditar qué se reservó, ni liberarlo, ni reproducirlo.
    """

    entry_packages: dict[str, DecisionPackage] = field(default_factory=dict)
    decisions: tuple[PortfolioDecision, ...] = ()
    ranked: tuple[OpportunityScore, ...] = ()
    journal_entries: tuple[DecisionJournalEntryRecord, ...] = ()
    regime: str = "UNKNOWN"
    as_of: str = ""
    reservations: tuple[PortfolioReservation, ...] = ()
    risk_state: PortfolioRiskState | None = None
    # V2.43/AUTO-3 — estado operativo EFECTIVO por candidata evaluada (``símbolo →
    # ENTRY_ALLOWED/…``), en el orden de evaluación. Es por candidata y no por tick porque
    # las bandas de volatilidad (ATR de la señal) y liquidez (su ``TradeContext``) son
    # datos DE LA CANDIDATA; el detalle completo de las tres dimensiones vive en la entrada
    # de journal de cada decisión. Vacío con el governor OFF (comportamiento actual).
    governor_states: tuple[tuple[str, str], ...] = ()

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
    sectors: dict[str, str] | None = None,
    open_orders: Any = (),
    order_book_measurement: Any = None,
    drawdown_pct: float | None = None,
) -> Any:
    """Construye el ``AutoPortfolioSnapshot`` desde el libro del worker (SIM).

    La foto agregada sirve de base para TODAS las decisiones del tick. El riesgo ya
    consumido se deriva de la distancia al stop de cada posición (``stops`` cuando se
    conoce, si no la implícita por ATR) y el presupuesto total de ``risk_budget_pct``
    sobre equity, de modo que el motor puede vetar por presupuesto agotado.

    ``sectors`` (V2.40.1) transmite el sector de las posiciones ABIERTAS. Sin él todas
    caían al cajón ``<unknown>``, la concentración sectorial dejaba de ser verificable y
    el motor podía evaluar un candidato solo contra sí mismo; con él, el gate
    ``sector_exposure_unverifiable`` puede distinguir "cesta opaca" de "cesta conocida".

    ``open_orders`` (V2.40.4) es el libro de órdenes PENDIENTES (fills no materializados) y
    ``order_book_measurement`` declara si ese libro se pudo leer y cuantificar del todo.
    Ambos se reenvían tal cual: el snapshot deriva de ellos ``reserved_cash`` /
    ``available_cash`` / ``pending_risk`` / ``pending_exposure``.

    ``drawdown_pct`` (V2.43/AUTO-3) es la caída MEDIDA de la cuenta desde la marca de
    referencia del día (``EquityMarkBook``), en %. El contrato es: un número SOLO se
    publica cuando la medición es completa; ``None`` significa "no medido" (y el
    gobernador lo lee como ``UNKNOWN``, nunca como 0). Con el governor OFF se pasa
    ``None``, así que el snapshot es idéntico al histórico.
    """
    marks = marks or {}
    stops = stops or {}
    sectors = sectors or {}
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
        sector = sectors.get(symbol)
        positions.append(
            PortfolioPosition(
                instrument_id=symbol,
                quantity=float(qty),
                market_value=mv,
                unrealized_pnl=unrealized,
                risk_amount=risk_amount,
                sector=sector if isinstance(sector, str) and sector.strip() else None,
            )
        )
    return build_auto_portfolio_snapshot(
        account_id=account_id,
        capital=equity,
        cash=cash,
        equity=equity,
        buying_power=cash,
        positions=positions,
        open_orders=open_orders,
        order_book_measurement=order_book_measurement,
        risk_budget=budget,
        active_strategies=strategies,
        market_regime=regime,
        drawdown_pct=drawdown_pct,
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

    V2.40.1: ni el edge ni la liquidez tienen valor de reserva. Un ``edge`` ausente vale
    0 (el ranker no redistribuye pesos) y una liquidez desconocida también vale 0, en vez
    del antiguo ``1.0`` que convertía "no sé" en "liquidez perfecta". El motor, además,
    veta explícitamente por ``liquidity_unknown``/``edge_below_threshold``.
    """
    liquidity = (
        None
        if signal.liquidity_notional is None
        else min(1.0, max(0.0, signal.liquidity_notional / 1_000_000.0))
    )
    return score_opportunity(
        signal.instrument_id,
        edge=signal.edge,
        liquidity=liquidity,
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

    V2.40.4 — el TOP N es un **tope de evaluación**: solo ese subconjunto se decide
    contra la cartera (``TOP_N = máximo de oportunidades evaluadas``). Las candidatas
    fuera del TOP se journalizan con ``top_n_excluded`` y su score real, nunca con un
    ``edge_below_threshold`` que sería falso, y no pueden operar aunque las del TOP se
    veten.

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
    # Un símbolo, UNA oportunidad por tick, elegida de forma determinista. El antiguo
    # ``setdefault`` hacía ganar "la primera que llegue", y el orden de entrada lo fija
    # el proveedor de señales (no es contractual): dos ticks con el mismo conjunto podían
    # aprobar instrumentos distintos. ``_dedupe_candidates`` elige por clave canónica.
    deduped = _dedupe_candidates(entry_signals)
    entry_signals = sorted(deduped.values(), key=canonical_candidate_key)

    # Identidad y frescura ANTES del rankeo: no se rankea ni se le asigna presupuesto a
    # una oportunidad que ya se emitió en esta barra, que ha caducado o que no tiene
    # identidad verificable (V2.40.1: sin identidad no hay idempotencia ni auditoría).
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

    # V2.40.4 — TOP_N es un TOPE DE EVALUACIÓN, no una prioridad. Solo el TOP se decide
    # contra la cartera; una candidata fuera del TOP **no se evalúa** y por tanto NO
    # puede llevar un motivo de decisión (``edge_below_threshold`` sería FALSO: su score
    # es válido, simplemente no compitió). Se journaliza con ``TOP_N_EXCLUDED`` y su
    # score/rank reales, de modo que el motivo del no-trade es el verdadero y el ranking
    # completo queda auditable. ``approved <= top_n`` es invariante de esta función.
    ordered: list[V2Signal] = []
    for score in top:
        signal = deduped.get(score.instrument_id)
        if signal is not None:
            ordered.append(signal)
    excluded: list[DecisionJournalEntryRecord] = [
        _rejected_signal_entry(
            deduped[score.instrument_id],
            TOP_N_EXCLUDED,
            actor=actor,
            as_of=as_of,
            score=score,
        )
        for score in ranked
        if score.instrument_id not in score_by_symbol and score.instrument_id in deduped
    ]

    packages: dict[str, DecisionPackage] = {}
    decisions: list[PortfolioDecision] = []
    journal: list[DecisionJournalEntryRecord] = []
    # V2.43/AUTO-3 — el gobernador se consulta SOLO si el flag está ON. La política se
    # resuelve UNA vez por tick; la lectura se resuelve por candidata porque las bandas de
    # volatilidad (ATR de la señal) y liquidez (su ``TradeContext``) son datos suyos.
    governor_policy = cfg.governor_policy()
    governor_states: list[tuple[str, str]] = []
    tick_drawdown_pct = getattr(snapshot, "drawdown_pct", None)
    # AUTO-1 — libro de reservas del tick. Cada aprobación RESERVA con identidad y la
    # candidata siguiente decide contra las reservas VIVAS (capital, riesgo, exposición y
    # sector ya comprometidos). Es el sustituto explícito de la lista local ``committed``:
    # mismo freno intra-tick, pero auditable, reversible y reproducible.
    ledger = ReservationLedger(
        account_id=str(getattr(snapshot, "account_id", "") or ""), tick_id=as_of
    )

    for signal in ordered:
        entry_score = score_by_symbol.get(signal.instrument_id)
        atr = signal.atr
        if atr is None and signal.price > 0 and not cfg.atr_required:
            # E2: con ``AUTO_ENGINE_SIM_V2_ATR_REQUIRED`` el sintético NO entra. La
            # reserva sigue existiendo para el régimen histórico (flag OFF), pero cuando
            # la política exige precisión de riesgo un ``None`` se queda ``None`` y el
            # candidato cae por el camino normal de NO ENTRY.
            atr = signal.price * cfg.atr_pct_fallback
        # Foto de trabajo: base + lo YA reservado en este tick (riesgo, capital y
        # exposición). Cada candidato se evalúa contra la foto reservada, no contra la
        # foto inicial: A → reserva → B → reserva → C.
        working_snapshot = _working_snapshot(snapshot, ledger)
        signal_ctx = _context_for_signal(signal)
        governor: OperationalAssessment | None = None
        if cfg.governor_enabled:
            governor = assess_from_measurements(
                operational_regime=resolved_regime,
                drawdown_pct=tick_drawdown_pct,
                # Un drawdown publicado es una medición COMPLETA por contrato; su
                # ausencia es UNKNOWN (nunca 0).
                drawdown_measurement=(
                    MEASUREMENT_COMPLETE if tick_drawdown_pct is not None else MEASUREMENT_UNKNOWN
                ),
                atr_known=atr is not None,
                liquidity_known=signal_ctx.liquidity_is_known,
                liquidity_notional=signal_ctx.liquidity_notional,
                policy=governor_policy,
            )
            governor_states.append((signal.instrument_id, governor.state))
        decision = decide_portfolio(
            instrument_id=signal.instrument_id,
            direction="long",
            entry_price=signal.price if signal.price > 0 else None,
            atr=atr,
            opportunity_score=entry_score,
            snapshot=working_snapshot,
            regime=resolved_regime,
            trade_context=signal_ctx,
            config=cfg.decision_config(governor=governor),
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
            # No existe aprobación sin reserva: la propuesta emitida se materializa en
            # reserva en el MISMO acto. Si la reserva no se puede construir (la cantidad
            # final no es reservable), la aprobación se DEGRADA a veto con su motivo en vez
            # de emitir una orden sin compromiso trazable.
            reservation = _reservation_for(
                signal,
                decision,
                account_id=str(getattr(snapshot, "account_id", "") or ""),
                tick_id=as_of,
                created_at=as_of,
            )
            reserved = ledger.reserve(reservation) if reservation is not None else None
            if reserved is None:
                decision = replace(
                    decision,
                    approved=False,
                    action="HOLD",
                    reason_codes=cast(
                        "tuple[DecisionReasonCode, ...]", (RESERVATION_FAILED,)
                    ),
                )
                decisions[-1] = decision
            else:
                packages[signal.instrument_id] = package
        journal.append(_journal_entry(decision, actor=actor, as_of=as_of))

    return V2TickPlan(
        entry_packages=packages,
        decisions=tuple(decisions),
        ranked=tuple(ranked),
        journal_entries=tuple((*blocked, *excluded, *journal)),
        regime=resolved_regime,
        as_of=as_of,
        reservations=ledger.live(),
        risk_state=_risk_state_for(snapshot, ledger),
        governor_states=tuple(governor_states),
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
    trail_hint: bool = False,
    trail_stop: float | None = None,
    at: str | None = None,
) -> PositionManagerResult | None:
    """Decisión de gestión de una posición abierta vía ``PositionManager``.

    Devuelve ``None`` si no hay posición gestionable. La intención (hold/reduce/sell)
    la consume el worker por el MISMO spine de settlement (nunca un atajo).

    AUTO-1A: colapsa también los skips (mark rechazado / decisión no construible). El
    worker con journal usa ``plan_v2_position_outcome`` para distinguirlos.
    """
    outcome = plan_v2_position_outcome(
        position,
        mark_price=mark_price,
        regime=regime,
        thesis_invalid=thesis_invalid,
        portfolio_recon_status=portfolio_recon_status,
        expires_at=expires_at,
        now=now,
        exit_template=exit_template,
        trail_hint=trail_hint,
        trail_stop=trail_stop,
        at=at,
    )
    return outcome if isinstance(outcome, PositionManagerResult) else None


def plan_v2_position_outcome(
    position: PositionState | None,
    *,
    mark_price: float,
    regime: str | None = None,
    thesis_invalid: bool = False,
    portfolio_recon_status: str | None = None,
    expires_at: str | None = None,
    now: str | None = None,
    exit_template: str | None = None,
    trail_hint: bool = False,
    trail_stop: float | None = None,
    at: str | None = None,
) -> PositionManagerResult | PositionManagerSkip | None:
    """AUTO-1A — como ``plan_v2_position_decision`` pero conservando el motivo del skip.

    El worker journaliza ``mark_rejected`` / ``decision_unavailable`` en vez de dejar el
    tick mudo: la posición sigue viva y sin gestión, y eso es un estado operativo.

    AUTO-2: acepta y propaga ``trail_hint``/``trail_stop`` (el ratchet de stop en R). Sin
    esto, ``manage_position_outcome`` usaba los defaults ``False``/``None`` y el
    ``stop_update`` de un ``PROTECT`` nacía siempre nulo.
    """
    return manage_position_outcome(
        position,
        mark_price=mark_price,
        regime=_coerce_operational_regime(regime),
        thesis_invalid=thesis_invalid,
        portfolio_recon_status=portfolio_recon_status,
        expires_at=expires_at,
        now=now,
        template_id=exit_template or None,
        trail_hint=trail_hint,
        trail_stop=trail_stop,
        at=at,
    )


def position_manager_package(
    result: PositionManagerResult | None,
    *,
    source_prefix: str = "auto-2.0-position",
) -> DecisionPackage | None:
    """Convierte el resultado del PositionManager en propuesta (o ``None`` si hold).

    AUTO-2: un ``PROTECT`` (trailing/break-even) colapsa aquí a ``None`` **a propósito**
    — un ratchet no vende y no debe inventar una orden — pero ya NO se pierde: el stop
    propuesto se surface con ``position_manager_stop_update`` y el worker lo aplica y lo
    journaliza. ``suggested_price`` sigue siendo el stop vigente, que ahora sí avanza.
    """
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


def position_manager_stop_update(
    result: PositionManagerResult | None,
) -> float | None:
    """Stop propuesto por la gestión (``PROTECT``), o ``None`` si no hay ninguno válido.

    AUTO-2: el ``stop_update`` que ``manage_position_outcome`` calculaba se DESCARTABA
    en ``position_manager_package`` (que sólo leía ``order_action``/``order_qty``) y
    ``current_stop`` quedaba congelado en el valor de nacimiento: break-even nunca se
    protegía y el trailing no existía en AUTO. Este es el único surface del stop
    propuesto; aplicarlo es responsabilidad del llamante (con monotonía H2).
    """
    if result is None:
        return None
    raw = result.stop_update
    try:
        stop = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
    if stop is None or stop != stop or stop <= 0:
        return None
    return stop


def build_position_management_journal_entry(
    *,
    instrument_id: str,
    reason_code: str,
    actor: str,
    as_of: str,
    detail: Mapping[str, Any] | None = None,
) -> DecisionJournalEntryRecord:
    """AUTO-2 — journal de la gestión de posición (ratchet, transiciones, degradación).

    El worker V2 no journalizaba la decisión de posición: un ``PROTECT`` sin efecto, un
    rechazo de transición o una protección ausente quedaban mudos. Este evento los hace
    observables sin convertirlos en una orden (un ratchet no vende).
    """
    from uuid import uuid4

    payload: dict[str, Any] = {
        "event": "auto_position_management",
        "instrumentId": instrument_id,
        "reasonCodes": [reason_code],
    }
    if detail:
        payload.update(dict(detail))
    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=f"POS-{uuid4().hex[:12]}",
        event_type="auto_position_management",
        actor=actor,
        created_at=_stamp(as_of),
        instrument_id=instrument_id,
        payload=payload,
    )


def canonical_candidate_key(signal: V2Signal) -> tuple[Any, ...]:
    """Clave canónica de una candidata: orden TOTAL y estable, no el de llegada.

    Orden de prioridad (V2.40.1): edge más alto primero, después versión de estrategia,
    instante de barra, identidad de señal e instrumento. Sirve para dos cosas:

    1. **Deduplicar** señales del mismo instrumento dentro del tick sin depender del orden
       en que el proveedor las entregue (antes ganaba "la primera", que no es determinista).
    2. **Iterar** de forma reproducible, de modo que dos ejecuciones con el mismo conjunto
       de señales produzcan exactamente las mismas decisiones.
    """
    edge = signal.edge
    return (
        -(float(edge)) if edge is not None else 0.0,
        -1.0 if edge is None else 0.0,
        str(signal.strategy_version or ""),
        str(signal.bar_timestamp or ""),
        str(signal.signal_id or ""),
        str(signal.instrument_id or ""),
    )


def _dedupe_candidates(signals: Iterable[V2Signal]) -> dict[str, V2Signal]:
    """Una candidata por instrumento: la de clave canónica MENOR (la mejor/estable)."""
    best: dict[str, V2Signal] = {}
    for signal in signals:
        current = best.get(signal.instrument_id)
        if current is None or canonical_candidate_key(signal) < canonical_candidate_key(current):
            best[signal.instrument_id] = signal
    return best


def _context_for_signal(signal: V2Signal) -> TradeContext:
    """Estado explícito de los gates de cartera para una señal del tick.

    Con ``trade_context`` el llamante ya resolvió estado y frescura (vía preferente). Sin
    él se sintetiza desde los valores sueltos: un valor presente es ``KNOWN`` y un ausente
    es ``UNKNOWN`` ⇒ el motor lo veta. Nunca "exento por no saber".
    """
    if signal.trade_context is not None:
        return signal.trade_context
    return TradeContext.from_legacy(
        sector=signal.sector,
        liquidity_notional=signal.liquidity_notional,
        correlation=None,
    )


def _working_snapshot(snapshot: Any, ledger: ReservationLedger) -> Any:
    """Foto de trabajo del tick: base + las reservas VIVAS, con su riesgo reservado.

    La fuente es el ``ReservationLedger`` del tick (AUTO-1), no una lista local: cada
    aprobación reserva con identidad y aquí se proyecta como posición comprometida para
    que ``risk_used`` incluya el riesgo ya reservado y la exposición (total/sector/activo)
    se recalcule con él. Sin esto, N candidatos del mismo tick se decidían cada uno
    creyendo ``risk_used = 0`` y el presupuesto de riesgo se podía multiplicar por N (el
    hallazgo más grave de la auditoría de v2.40-beta).

    ``risk_used`` solo se sobrescribe cuando alguna reserva **declara** su riesgo: si no
    hay dato, se conserva el de la base (nunca un 0 engañoso).

    El notional ya reservado tampoco es poder de compra: se descuenta de
    ``cash``/``buying_power``. Sin esta resta, N candidatas del mismo tick decidían cada
    una contra la caja completa (``cash = 80k`` ⇒ 4 × 20k con 25k disponibles). Es una
    reserva de CAPITAL, complementaria a la de riesgo.
    """
    committed = ledger.committed_positions()
    if not committed or snapshot is None:
        return snapshot
    committed_risk = 0.0
    has_committed_risk = False
    committed_notional = 0.0
    for position in committed:
        if position.risk_amount is not None:
            has_committed_risk = True
            committed_risk += max(0.0, float(position.risk_amount))
        if position.market_value is not None:
            committed_notional += max(0.0, float(position.market_value))
    risk_used = snapshot.risk_used
    if has_committed_risk:
        risk_used = round(((snapshot.risk_used or 0.0) + committed_risk) * 10000) / 10000
    cash, buying_power = _reserve_committed_cash(
        cash=snapshot.cash,
        buying_power=snapshot.buying_power,
        committed_notional=committed_notional,
    )
    return build_auto_portfolio_snapshot(
        account_id=snapshot.account_id,
        capital=snapshot.capital,
        cash=cash,
        equity=snapshot.equity,
        buying_power=buying_power,
        positions=tuple(snapshot.positions) + tuple(committed),
        open_orders=snapshot.open_orders,
        order_book_measurement=snapshot.order_book_measurement,
        daily_pnl=snapshot.daily_pnl,
        realized_pnl=snapshot.realized_pnl,
        unrealized_pnl=snapshot.unrealized_pnl,
        risk_used=risk_used,
        risk_budget=snapshot.risk_budget,
        drawdown_pct=snapshot.drawdown_pct,
        active_strategies=snapshot.active_strategies,
        market_regime=snapshot.market_regime,
        last_reconciliation=snapshot.last_reconciliation,
        data_freshness=snapshot.data_freshness,
        as_of=snapshot.as_of,
    )


def _reserve_committed_cash(
    *, cash: float | None, buying_power: float | None, committed_notional: float
) -> tuple[float | None, float | None]:
    """Descuenta el notional comprometido en el tick del cash y del poder de compra.

    Nunca ``None`` → número: sin dato se conserva la ausencia (fail-closed aguas abajo).
    El clamp a 0 evita publicar un poder de compra negativo, que no es un hecho.
    """
    if committed_notional <= 0:
        return cash, buying_power

    def _net(value: float | None) -> float | None:
        if value is None:
            return None
        return round(max(0.0, float(value) - committed_notional) * 10000) / 10000

    return _net(cash), _net(buying_power)


def _reservation_for(
    signal: V2Signal,
    decision: PortfolioDecision,
    *,
    account_id: str,
    tick_id: str,
    created_at: str,
) -> PortfolioReservation | None:
    """Reserva del tick para una aprobación: identidad + dimensiones comprometidas.

    ``reserved_cash`` es el notional comprometido y ``reserved_risk`` el presupuesto de
    riesgo consumido (``riskAmount``), que es lo que el motor compromete — no la pérdida
    del stop, que con coste real es menor. El ``TradingCost`` viaja aparte para que el
    journal pueda mostrar la pérdida esperada real (stop + fricciones).

    La reserva lleva la CUENTA del snapshot (AUTO-1b): sin ella la fila durable quedaría
    con ``account_id`` NULL y la lectura "reservas vivas de ESTA cuenta" no la vería —
    el compromiso se perdería en el arranque siguiente.

    ``None`` si la aprobación no trae una cantidad reservable: el llamante lo trata como
    veto (``reservation_failed``), nunca como reserva de 0.
    """
    allocation = decision.allocation or {}
    quantity = allocation.get("quantity")
    try:
        reservable = float(quantity) if quantity is not None else 0.0
    except (TypeError, ValueError):
        reservable = 0.0
    if reservable <= 0:
        return None
    plan = decision.trade_plan
    entry = plan.entry if plan is not None and plan.entry else signal.price
    stop = plan.structural_stop if plan is not None else None
    return build_reservation(
        reservation_id=f"RES-{decision.decision_id}",
        account_id=account_id,
        tick_id=tick_id,
        instrument_id=signal.instrument_id,
        side="buy",
        sector=decision.sector if decision.sector is not None else signal.sector,
        strategy_version_id=signal.strategy_version,
        quantity=reservable,
        entry=entry,
        stop=stop,
        reserved_cash=allocation.get("positionValue"),
        reserved_risk=allocation.get("riskAmount"),
        cost=coerce_trading_cost(allocation.get("tradingCost")),
        created_at=created_at or None,
    )


def _risk_state_for(snapshot: Any, ledger: ReservationLedger) -> PortfolioRiskState:
    """Estado de riesgo del tick: posiciones abiertas + reservas vivas.

    El desglose sectorial de las posiciones se mide aquí (una posición sin ``risk_amount``
    no aporta 0: cuenta como NO medida y degrada el ``measurement``) y el de las reservas
    lo aporta el libro. Es la foto con la que se puede responder "cuánto riesgo tenía el
    tick comprometido" sin reconstruir nada a mano.

    Traducción de "medido 0" vs "no medido": el snapshot deja ``risk_used`` a ``None``
    también cuando no hay NINGUNA posición que medir (cartera vacía), que es un 0 medido y
    exacto, no una ausencia. Si se pasara ``None`` tal cual, el estado publicaría
    ``gross_risk = None`` sobre un total conocido. Solo se traduce a 0 cuando no queda
    ninguna posición sin medir: con una sola posición sin ``risk_amount`` el total sigue
    siendo desconocido y se publica ``None`` (fail-closed).
    """
    positions = getattr(snapshot, "positions", ()) or ()
    by_sector, unmeasured = sector_risk_from_positions(positions)
    risk_used = getattr(snapshot, "risk_used", None)
    if risk_used is None and unmeasured == 0:
        risk_used = 0.0
    return build_portfolio_risk_state(
        ledger=ledger,
        position_risk_total=risk_used,
        position_risk_by_sector=by_sector,
        unmeasured_positions=unmeasured,
        pending_risk=getattr(snapshot, "pending_risk", 0.0),
    )


def _stamp(as_of: str) -> str:
    if as_of:
        return as_of
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# Motivos de descarte de una señal ANTES de decidir (auditables en el journal).
SIGNAL_DUPLICATE = "signal_duplicate"
SIGNAL_STALE = "signal_stale"
# V2.40.1: sin identidad no hay idempotencia, deduplicación, auditoría ni replay posibles.
SIGNAL_IDENTITY_MISSING = "signal_identity_missing"


def _signal_rejection(
    signal: V2Signal, *, consumed: set[str], as_of: str
) -> str | None:
    """Motivo por el que la señal no debe generar una oportunidad nueva (o ``None``).

    Tres reglas, en este orden:

    0. ``signal_identity_missing`` — la señal no trae identidad verificable. V2.40.1: en
       AUTO la ausencia de identidad es un VETO, no una degradación aceptable. Sin
       identidad no se puede garantizar idempotencia (no re-operar la misma barra),
       deduplicación, auditoría ni replay; sacrificar eso por disponibilidad es
       exactamente lo que un sistema autónomo no debe hacer. La causa raíz (timeframe mal
       configurado, reloj sin zona, instrumento vacío) se arregla en la fuente, no
       relajando el gate.
    1. ``signal_duplicate`` — la identidad (instrumento+versión+timeframe+barra+acción)
       ya se consumió: es la MISMA señal sobre la MISMA barra re-emitida por el turno
       siguiente (worker 60s sobre señal D1), no una oportunidad nueva.
    2. ``signal_stale`` — la señal caducó (``valid_until < as_of``): alimentar una
       decisión con una barra vieja sería decidir sobre datos que ya no rigen.
    """
    signal_id = str(signal.signal_id or "").strip()
    if not signal_id:
        return SIGNAL_IDENTITY_MISSING
    if signal_id in consumed:
        return SIGNAL_DUPLICATE
    valid_until = str(signal.valid_until or "").strip()
    if valid_until and as_of and str(as_of) > valid_until:
        return SIGNAL_STALE
    return None


def _rejected_signal_entry(
    signal: V2Signal,
    reason: str,
    *,
    actor: str,
    as_of: str,
    score: OpportunityScore | None = None,
) -> DecisionJournalEntryRecord:
    """Entrada de journal de una señal descartada por identidad/frescura.

    ``score`` (V2.40.4) solo llega para las candidatas descartadas DESPUÉS del rankeo
    (``top_n_excluded``): el score es el REAL del ranking y se publica porque
    "no la evalué" no es lo mismo que "no tenía edge". Para los descartes previos al
    ranking (identidad/frescura) no existe score y la clave se omite.
    """
    from uuid import uuid4

    payload: dict[str, Any] = {
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
    }
    if score is not None:
        payload["opportunityScore"] = score.combined
        payload["rank"] = score.rank

    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=f"REJ-{uuid4().hex[:12]}",
        event_type="auto_entry_decision",
        actor=actor,
        created_at=_stamp(as_of),
        instrument_id=signal.instrument_id,
        payload=payload,
    )


def _journal_entry(
    decision: PortfolioDecision, *, actor: str, as_of: str
) -> DecisionJournalEntryRecord:
    from uuid import uuid4

    payload: dict[str, Any] = {
        "event": "auto_entry_decision",
        "instrumentId": decision.instrument_id,
        "action": decision.action,
        "approved": decision.approved,
        "reasonCodes": list(decision.reason_codes),
        "regime": decision.regime,
        "sector": decision.sector,
        "tradePlan": None if decision.trade_plan is None else decision.trade_plan.to_dict(),
        "risk": decision.allocation,
        # V2.40.4 — violaciones de coherencia del TradePlan (vacío si fue válido).
        "planViolations": list(decision.plan_violations),
    }
    # V2.43/AUTO-3 — las TRES dimensiones del gobernador en TODA decisión no-trade
    # (criterio de salida del roadmap): ``marketRegime``/``riskRegime`` son HECHOS con
    # fuente y ``operationalState`` es el PERMISO derivado. Se emiten SOLO cuando el
    # gobernador se consultó, para que con el flag OFF el payload sea el histórico.
    if decision.operational_state is not None:
        payload["marketRegime"] = decision.market_regime
        payload["riskRegime"] = decision.risk_regime
        payload["operationalState"] = decision.operational_state

    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=decision.decision_id,
        event_type="auto_entry_decision",
        actor=actor,
        created_at=_stamp(as_of),
        instrument_id=decision.instrument_id,
        payload=payload,
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
    # V2.43/AUTO-3: ``low_vol`` (solo lo produce la matematica ``v1``, opt-in) es el
    # veredicto MENOS conservador: un mercado calmado y sin direccion no puede pintar de
    # riesgo un universo mixto, así que va el ultimo. No es "libre": el eje operativo lo
    # lee como ``LOW_VOLATILITY`` (permite entrada) y el gobernador lo lee como
    # ``VolatilityBand.LOW``.
    REGIME_LOW_VOL,
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


def _as_ohlcv_bar(raw: Any) -> Any | None:
    """Normaliza una barra a ``OhlcvBar`` (o ``None`` si no es utilizable).

    ``compute_atr`` accede por atributo; un ``Mapping`` (los seams de test del repo
    sirven dicts) se convierte aquí, explícitamente. Barra malformada ⇒ ``None``: el
    llamante la descarta y el ATR queda sin calcular, nunca inventado.
    """
    if hasattr(raw, "high") and hasattr(raw, "low") and hasattr(raw, "close"):
        return raw
    if not isinstance(raw, Mapping):
        return None
    try:
        from bolsa_domain.entities.ohlcv_bar import OhlcvBar  # noqa: PLC0415

        close = float(raw["close"])
        return OhlcvBar(
            timestamp=str(raw.get("timestamp") or raw.get("date") or ""),
            open=float(raw.get("open", close)),
            high=float(raw["high"]),
            low=float(raw["low"]),
            close=close,
            volume=int(raw.get("volume", 0) or 0),
        )
    except Exception:  # noqa: BLE001 — barra incompleta ⇒ no hay barra.
        return None


@dataclass
class AtrSource:
    """ATR real por símbolo respaldado por barras (as-of, determinista).

    V2.42 slice 2b (E2 · decisión D3). ``refresh()`` es la parte async (trae barras del
    universo y calcula el ATR de cada una); ``__call__()`` es la lectura SÍNCRONA del hot
    path, de modo que decidir no depende de I/O.

    Fail-closed: un fallo de lectura, barras insuficientes o un ATR no finito dejan el
    símbolo SIN valor ⇒ el llamante cae al fallback DECLARADO (``atr_source=fallback``) y
    con ``AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1`` la candidata no entra. Nunca se inventa un
    ATR para poder abrir.

    Las barras se aceptan en las DOS formas que circulan por el repo (``OhlcvBar`` del
    repositorio y ``Mapping`` de los seams de test): ``compute_atr`` exige atributos, así
    que un mapping se CONVIERTE explícitamente. Sin esa conversión el ATR real quedaría
    mudo en cualquier camino que sirviera dicts —fail-closed, sí, pero indistinguible de
    "no hay barras"— y la reserva sintética parecería obligatoria sin serlo.
    """

    bars_provider: Callable[[], Awaitable[Mapping[str, Sequence[Any]]]]
    period: int = 14
    _atr_by_symbol: dict[str, float] = field(default_factory=dict, init=False, repr=False)

    async def refresh(self) -> int:
        """Recalcula el ATR por símbolo. Devuelve cuántos símbolos tienen ATR real."""
        try:
            bars_by_symbol = await self.bars_provider() or {}
        except Exception:  # noqa: BLE001 — sin barras no hay ATR (fail-closed).
            logger.exception("auto_v2 atr refresh failed (atr_source=missing)")
            self._atr_by_symbol = {}
            return 0
        computed: dict[str, float] = {}
        for symbol, bars in bars_by_symbol.items():
            rows = [bar for bar in (_as_ohlcv_bar(raw) for raw in (bars or [])) if bar is not None]
            if len(rows) < self.period + 1:
                continue
            try:
                series = compute_atr(rows, self.period)
            except Exception:  # noqa: BLE001 — barras malformadas ≠ ATR inventado.
                continue
            value = next((v for v in reversed(series) if v is not None), None)
            if value is None or value != value or value <= 0 or value in (float("inf"), float("-inf")):
                continue
            key = str(symbol or "").strip()
            if key:
                computed[key] = float(value)
        self._atr_by_symbol = computed
        return len(computed)

    def atr_for(self, symbol: str) -> float | None:
        """Lectura síncrona del ATR cacheado (``None`` si no hay dato verificable)."""
        return self._atr_by_symbol.get(str(symbol or "").strip())

    def __call__(self, symbol: str) -> float | None:
        return self.atr_for(symbol)


def _observed_field(observed: Any, name: str) -> Any:
    """Lee un campo de una observación (dataclass, Mapping o atributo)."""
    if observed is None:
        return None
    if isinstance(observed, Mapping):
        return observed.get(name)
    return getattr(observed, name, None)


@dataclass
class CatalogTradeContextSource:
    """Contexto de cartera (sector + liquidez) respaldado por el catálogo.

    V2.40.1: es la pieza que convierte "no tengo dato" en un VETO en vez de en una
    entrada. ``refresh()`` es la parte async (UNA query por tick sobre el catálogo de
    instrumentos); ``context_for()`` es la lectura SÍNCRONA del hot path, de modo que
    decidir no depende de I/O. Un fallo de lectura deja el contexto vacío ⇒ el motor
    veta por ``sector_unknown``/``liquidity_unknown`` (jamás asume que el instrumento
    es operable "porque no se pudo comprobar").

    La frescura la aporta el propio dato (``observed_at`` = ``fetchedAt`` de los
    fundamentales) frente al ``as_of`` del tick: sin instantes parseables no se afirma
    antigüedad, pero tampoco se inventa un dato.
    """

    reader: Callable[[Sequence[str]], Awaitable[Mapping[str, Any]]]
    max_age_days: int = DEFAULT_MAX_AGE_DAYS
    _by_symbol: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _as_of: str = field(default="", init=False, repr=False)

    async def refresh(self, symbols: Iterable[str], *, as_of: str = "") -> None:
        """Recarga el contexto de los símbolos del tick (una sola lectura)."""
        wanted = [str(s).strip() for s in symbols if str(s).strip()]
        self._as_of = as_of or ""
        self._by_symbol = {}
        if not wanted:
            return
        try:
            observed = await self.reader(wanted) or {}
        except Exception:  # noqa: BLE001 — sin catálogo no hay contexto (fail-closed).
            logger.exception("auto_v2 trade context read failed")
            return
        if isinstance(observed, Mapping):
            self._by_symbol = {
                str(symbol).strip(): value
                for symbol, value in observed.items()
                if str(symbol).strip()
            }

    def context_for(
        self,
        symbol: str,
        *,
        declared_sector: Any = None,
        liquidity_fallback: float | None = None,
        correlation: float | None = None,
        as_of: str = "",
    ) -> TradeContext:
        """Contexto de UN candidato: catálogo + lo declarado por la estrategia."""
        observed = self._by_symbol.get(str(symbol).strip())
        catalog_sector = _observed_field(observed, "sector")
        adv_usd = _observed_field(observed, "adv_usd")
        if adv_usd is None:
            adv_usd = liquidity_fallback
        observed_at = _observed_field(observed, "observed_at")
        return TradeContext.from_observation(
            sector_declared=declared_sector,
            sector_catalog=catalog_sector,
            adv_usd=adv_usd,
            correlation=correlation,
            observed_at=observed_at,
            as_of=as_of or self._as_of,
            max_age_days=self.max_age_days,
        )

    def known_sectors(
        self, symbols: Iterable[str], *, declared: Mapping[str, Any] | None = None
    ) -> dict[str, str]:
        """Sector por símbolo SOLO si su estado es ``KNOWN``.

        Es lo que alimenta el snapshot de la cartera: una posición cuyo sector no es
        fiable se omite del mapa (queda opaca) en vez de publicarse como si fuera
        verificable. Esa opacidad es justo lo que el motor detecta para no aumentar
        exposición sobre estado que no puede comprobar.
        """
        overrides = declared or {}
        out: dict[str, str] = {}
        for symbol in symbols:
            key = str(symbol).strip()
            if not key:
                continue
            context = self.context_for(key, declared_sector=overrides.get(key))
            if context.sector_is_known and context.sector:
                out[key] = context.sector
        return out


@dataclass
class EdgeReportSource:
    """Edge REAL por versión de estrategia (``EdgeReport`` persistido).

    V2.40.1: sustituye al antiguo ``default_edge = 0.9``, que convertía "la estrategia no
    declara edge" en "oportunidad excelente". Aquí el edge es un dato persistido y
    auditable (``EdgeReportRow.edge_score`` de la versión de estrategia), y su ausencia
    se propaga como ``None`` (el componente vale 0 y el motor veta).

    ``refresh()`` (async) precarga por tick las versiones observadas; ``edge_for()`` es la
    lectura síncrona del hot path. Un fallo deja el edge ausente, nunca inventado.
    """

    reader: Callable[[str, str | None], Awaitable[float | None]]
    _by_version: dict[str, float] = field(default_factory=dict, init=False, repr=False)

    async def refresh(
        self, strategy_versions: Iterable[str], *, account_id: str | None = None
    ) -> None:
        versions = sorted({str(v).strip() for v in strategy_versions if str(v).strip()})
        self._by_version = {}
        for version in versions:
            try:
                value = await self.reader(version, account_id)
            except Exception:  # noqa: BLE001 — sin edge no se inventa uno.
                logger.exception("auto_v2 edge report read failed version=%s", version)
                continue
            if value is None:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if number != number:
                continue
            self._by_version[version] = min(1.0, max(0.0, number))

    def edge_for(self, strategy_version: str | None) -> float | None:
        key = str(strategy_version or "").strip()
        if not key:
            return None
        return self._by_version.get(key)


__all__ = [
    "V2_ENGINE_ENV",
    "CatalogTradeContextSource",
    "DiscoveryRegimeSource",
    "AtrSource",
    "EdgeReportSource",
    "SIGNAL_DUPLICATE",
    "SIGNAL_IDENTITY_MISSING",
    "SIGNAL_STALE",
    "V2Signal",
    "V2TickPlan",
    "V2Tunables",
    "aggregate_trial_regime",
    "build_worker_snapshot",
    "canonical_candidate_key",
    "edge_from_package",
    "plan_v2_position_decision",
    "plan_v2_position_outcome",
    "plan_v2_tick",
    "position_manager_package",
    "regime_exit_only",
    "sector_from_package",
    "tunables_from_env",
    "v2_engine_enabled",
]
