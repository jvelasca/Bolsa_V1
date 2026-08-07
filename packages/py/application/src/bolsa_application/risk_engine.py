"""OR-RE — Risk Engine façade (pre-Camino D / pre-€).

Toda apertura automática (paper_auto / futuro AUTO Estudio) debe pasar por
``check_opening``. Reutiliza Policy Gate + long-only; añade kill switch y
tope Libro DEMO (maxOpen) cuando se aportan.

Prohibido: Research/dictamen → Broker sin este check.

@see docs/engineering/audit-ext-institutional-pre-auto-triage-2026-08-04.md §9.2
@see docs/engineering/camino-d-auto-thaw-checklist-2026-08-04.md OR-RE
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.cognitive.edge_report import EdgeReport
from bolsa_analytics.cognitive.market_events import MarketEventCalendar
from bolsa_analytics.knowledge.models import TechnicalInputs
from bolsa_application.trading_policy_guard import (
    CognitiveGuardResult,
    enforce_cognitive_policy_for_opening,
)
from bolsa_domain.entities.investor_profile import InvestorProfileRecord

RISK_ENGINE_VERSION = "risk_engine_v0"
RiskVerdict = Literal["ALLOW", "DENY"]


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
    technical_inputs: TechnicalInputs | dict | None = None,
    sector: str | None = None,
    market_cap_usd: float | None = None,
    average_daily_volume_usd: float | None = None,
    account_daily_drawdown_pct: float | None = None,
    account_weekly_drawdown_pct: float | None = None,
    account_max_drawdown_pct: float | None = None,
    kill_switch: bool = False,
    book_max_open_positions: int | None = None,
) -> RiskDecision:
    """Evalúa una apertura. Exits siguen el bypass del Cognitive Guard."""
    if kill_switch:
        return RiskDecision(
            verdict="DENY",
            reasons=("kill_switch_active",),
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
