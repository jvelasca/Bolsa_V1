"""OR-RE — Risk Engine façade (pre-Camino D / pre-€).

Toda apertura automática (paper_auto / futuro AUTO Estudio) debe pasar por
``check_opening``. Reutiliza Policy Gate + long-only; añade kill switch,
tope Libro DEMO (maxOpen), **DS-05 Data Freshness Gate**, **DS-03 Account Mandate Gate**,
**OR-4 Reconciliation opening veto** y **DEX-3 OperationalIncident** cuando se aportan.

Prohibido: Research/dictamen → Broker sin este check.

@see docs/engineering/audit-ext-institutional-pre-auto-triage-2026-08-04.md §9.2
@see docs/engineering/camino-d-auto-thaw-checklist-2026-08-04.md OR-RE
@see docs/engineering/decision-spine-cadena-2026-08-24.md DS-05 · DS-03
@see docs/adr/035-operational-reliability.md OR-4
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from bolsa_market.sanity import sanity_opening_veto_reason
from bolsa_analytics.cognitive.edge_report import EdgeReport
from bolsa_analytics.cognitive.operational_incident import (
    IncidentOpeningStatus,
    incident_opening_veto_reason,
)
from bolsa_analytics.cognitive.portfolio_fit import BasketPosition
from bolsa_analytics.knowledge.models import TechnicalInputs
from bolsa_application.account_mandate_gate import account_mandate_veto_reason
from bolsa_application.reconciliation_opening_gate import (
    reconciliation_opening_veto_reason,
)
from bolsa_application.trading_policy_guard import (
    CognitiveGuardResult,
    enforce_cognitive_policy_for_opening,
)
from bolsa_domain.entities.investor_profile import InvestorProfileRecord
from bolsa_domain.entities.market_event import MarketEventCalendar
from bolsa_domain.ohlcv_time import parse_bar_timestamp

RISK_ENGINE_VERSION = "risk_engine_v0"
RiskVerdict = Literal["ALLOW", "DENY"]

# DS-05 — umbral fail-closed de frescura (alineado con EOD_STALE_MAX_DAYS=5).
# Cubre fin de semana / festivo corto sin tumbar D1 sano; bloquea barras viejas.
DATA_FRESHNESS_MAX_AGE_SECONDS = 5 * 24 * 60 * 60

_EXIT_SIGNAL_KINDS = frozenset({"exit", "exit_hint", "reduce"})


def data_freshness_veto_reason(
    last_bar_timestamp: str | None,
    *,
    max_age_seconds: int = DATA_FRESHNESS_MAX_AGE_SECONDS,
    require: bool = False,
    now: datetime | None = None,
) -> str | None:
    """Devuelve reason de VETO DS-05, o None si la barra es aceptable / gate off.

    - ``require=False`` y timestamp ausente → gate off (compat tests / wiring legado).
    - ``require=True`` y timestamp ausente → ``data_freshness:missing`` (fail-closed).
    - timestamp presente y edad > umbral → ``data_freshness:stale:...``.
    """
    if last_bar_timestamp is None or not str(last_bar_timestamp).strip():
        return "data_freshness:missing" if require else None
    try:
        latest = parse_bar_timestamp(str(last_bar_timestamp).strip())
    except (TypeError, ValueError):
        return "data_freshness:invalid_timestamp"
    moment = now if now is not None else datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    else:
        moment = moment.astimezone(UTC)
    age = (moment - latest).total_seconds()
    if age > max_age_seconds:
        return f"data_freshness:stale:age_s={int(age)}>{max_age_seconds}"
    return None


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Veredicto Risk Engine (ALLOW|DENY + reasons)."""

    verdict: RiskVerdict
    reasons: tuple[str, ...]
    engine_version: str = RISK_ENGINE_VERSION
    """Resultado del Cognitive Guard anidado (None si veto previo al Gate)."""
    guard: CognitiveGuardResult | None = None

    @property
    def allowed(self) -> bool:
        return self.verdict == "ALLOW"

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "engineVersion": self.engine_version,
            "cognitiveGate": None if self.guard is None else self.guard.to_dict(),
        }


def check_opening(
    *,
    profile: InvestorProfileRecord | None,
    instrument_id: str,
    symbol: str,
    trade_type: str,
    quantity: float,
    price: float,
    signal_kind: str | None = None,
    equity: float | None = None,
    open_positions_count: int = 0,
    event_calendar: MarketEventCalendar | None = None,
    auto_live: bool = False,
    edge_report: EdgeReport | None = None,
    technical_inputs: TechnicalInputs | dict[str, Any] | None = None,
    sector: str | None = None,
    market_cap_usd: float | None = None,
    average_daily_volume_usd: float | None = None,
    account_daily_drawdown_pct: float | None = None,
    account_weekly_drawdown_pct: float | None = None,
    account_max_drawdown_pct: float | None = None,
    kill_switch: bool = False,
    book_max_open_positions: int | None = None,
    portfolio_positions: list[BasketPosition] | None = None,
    proposal_sector: str | None = None,
    last_bar_timestamp: str | None = None,
    max_bar_age_seconds: int | None = None,
    require_fresh_data: bool = False,
    freshness_now: datetime | None = None,
    has_open_mandate: bool = False,
    mandate_strategy_id: str | None = None,
    require_account_mandate: bool = False,
    proposal_strategy_id: str | None = None,
    portfolio_recon_status: Literal["clean", "drift"] | None = None,
    live_recon_status: Literal["clean", "drift", "unavailable"] | None = None,
    broker_venue: Literal["paper", "live"] | str | None = None,
    require_recon_veto: bool = False,
    incident_status: IncidentOpeningStatus | None = None,
    require_incident_veto: bool = False,
    sanity_warnings: tuple[str, ...] | list[str] | None = None,
) -> RiskDecision:
    """Evalúa una apertura. Exits siguen el bypass del Cognitive Guard.

    DS-05: si ``require_fresh_data`` o se aporta ``last_bar_timestamp``, VETO
    fail-closed cuando la barra/quote supera el umbral (o falta el timestamp).
    DS-03: si ``require_account_mandate``, VETO sin tenure abierto o mismatch
    de estrategia (AUTO). OR-4: drift paper o live unavailable/drift (venue live)
    VETO aperturas. DEX-3: incidente activo → ``incident:unresolved``. Sin auto-heal.
    No aplica a ``exit`` / ``exit_hint`` / ``reduce``.
    """
    if kill_switch:
        return RiskDecision(
            verdict="DENY",
            reasons=("kill_switch_active",),
            guard=None,
        )

    kind = (signal_kind or "").lower()
    if kind not in _EXIT_SIGNAL_KINDS and (
        require_fresh_data or last_bar_timestamp is not None
    ):
        age_cap = (
            DATA_FRESHNESS_MAX_AGE_SECONDS
            if max_bar_age_seconds is None
            else max_bar_age_seconds
        )
        freshness_reason = data_freshness_veto_reason(
            last_bar_timestamp,
            max_age_seconds=age_cap,
            require=require_fresh_data,
            now=freshness_now,
        )
        if freshness_reason is not None:
            return RiskDecision(
                verdict="DENY",
                reasons=(freshness_reason,),
                guard=None,
            )
        if sanity_warnings:
            sanity_reason = sanity_opening_veto_reason(sanity_warnings)
            if sanity_reason is not None:
                return RiskDecision(
                    verdict="DENY",
                    reasons=(sanity_reason,),
                    guard=None,
                )

    if kind not in _EXIT_SIGNAL_KINDS and require_account_mandate:
        mandate_reason = account_mandate_veto_reason(
            has_open_tenure=has_open_mandate,
            require=True,
            mandate_strategy_id=mandate_strategy_id,
            proposal_strategy_id=proposal_strategy_id,
        )
        if mandate_reason is not None:
            return RiskDecision(
                verdict="DENY",
                reasons=(mandate_reason,),
                guard=None,
            )

    if kind not in _EXIT_SIGNAL_KINDS and (
        require_recon_veto
        or portfolio_recon_status is not None
        or live_recon_status is not None
    ):
        recon_reason = reconciliation_opening_veto_reason(
            portfolio_recon_status=portfolio_recon_status,
            live_recon_status=live_recon_status,
            broker_venue=broker_venue,
            require=require_recon_veto
            or portfolio_recon_status is not None
            or live_recon_status is not None,
        )
        if recon_reason is not None:
            return RiskDecision(
                verdict="DENY",
                reasons=(recon_reason,),
                guard=None,
            )

    if kind not in _EXIT_SIGNAL_KINDS and (
        require_incident_veto or incident_status is not None
    ):
        incident_reason = incident_opening_veto_reason(
            incident_status=incident_status,
            require=require_incident_veto or incident_status is not None,
        )
        if incident_reason is not None:
            return RiskDecision(
                verdict="DENY",
                reasons=(incident_reason,),
                guard=None,
            )

    if (
        book_max_open_positions is not None
        and book_max_open_positions > 0
        and open_positions_count >= book_max_open_positions
        and (signal_kind or "").lower() != "exit"
        and trade_type.lower() == "buy"
    ):
        return RiskDecision(
            verdict="DENY",
            reasons=(
                f"book_max_open_positions:{open_positions_count}>={book_max_open_positions}",
            ),
            guard=None,
        )

    guard = enforce_cognitive_policy_for_opening(
        profile=profile,
        instrument_id=instrument_id,
        symbol=symbol,
        trade_type=trade_type,
        quantity=quantity,
        price=price,
        signal_kind=signal_kind,
        equity=equity,
        open_positions_count=open_positions_count,
        event_calendar=event_calendar,
        auto_live=auto_live,
        edge_report=edge_report,
        technical_inputs=technical_inputs,
        sector=sector,
        market_cap_usd=market_cap_usd,
        average_daily_volume_usd=average_daily_volume_usd,
        account_daily_drawdown_pct=account_daily_drawdown_pct,
        account_weekly_drawdown_pct=account_weekly_drawdown_pct,
        account_max_drawdown_pct=account_max_drawdown_pct,
        portfolio_positions=portfolio_positions,
        proposal_sector=proposal_sector,
    )
    if not guard.allowed:
        return RiskDecision(
            verdict="DENY",
            reasons=guard.reasons,
            guard=guard,
        )
    return RiskDecision(
        verdict="ALLOW",
        reasons=guard.reasons,
        guard=guard,
    )
