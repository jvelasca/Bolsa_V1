"""Policy Gate determinista (RFC-008 D1). Opportunity ≠ Permission."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bolsa_analytics.cognitive.trading_policy import TradingPolicy


@dataclass(frozen=True, slots=True)
class PolicyRuleResult:
    rule: str
    limit: str
    actual: str
    status: str  # PASSED | FAILED | SKIPPED
    message: str | None = None


@dataclass(frozen=True, slots=True)
class PolicyGateResult:
    passed: bool
    policy_id: str
    policy_version: str
    evaluated_rules: tuple[PolicyRuleResult, ...]
    veto_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "policyId": self.policy_id,
            "policyVersion": self.policy_version,
            "evaluatedRules": [
                {
                    "rule": r.rule,
                    "limit": r.limit,
                    "actual": r.actual,
                    "status": r.status,
                    "message": r.message,
                }
                for r in self.evaluated_rules
            ],
            "vetoReasons": list(self.veto_reasons),
        }


def _rule(name: str, limit: str, actual: str, ok: bool, message: str | None = None) -> PolicyRuleResult:
    return PolicyRuleResult(
        rule=name,
        limit=limit,
        actual=actual,
        status="PASSED" if ok else "FAILED",
        message=message,
    )


def _unmeasured(rule: str, limit: str, *, declared_optional: bool) -> PolicyRuleResult:
    """Resultado de una regla ACTIVA cuyo dato no vino.

    P2 (auditoría .183): antes la ausencia de dato se codificaba como ``SKIPPED`` y
    ``SKIPPED`` no veta, así que MinMarketCap, MinADV, MaxSpread, MaxSectorExposure y los
    circuit breakers de drawdown quedaban **muertos** en el camino AUTO: la política
    exigía un mínimo y el gate lo saltaba por no tener con qué compararlo.

    La regla es ahora: si la regla está activa y el dato falta, la respuesta es *no
    verificable* ⇒ ``FAILED`` con motivo ``<Regla>_unmeasured``. Solo las reglas que la
    POLÍTICA declara opcionales (``optional_measurements``) pueden quedar ``SKIPPED``, y
    ese ``SKIPPED`` viaja con su propio motivo para que nadie lo lea como "cumplida".
    """
    if declared_optional:
        return PolicyRuleResult(
            rule=rule,
            limit=limit,
            actual="n/a",
            status="SKIPPED",
            message=f"{rule}_unmeasured_declared",
        )
    return PolicyRuleResult(
        rule=rule,
        limit=limit,
        actual="n/a",
        status="FAILED",
        message=f"{rule}_unmeasured",
    )


def evaluate_policy_gate(
    policy: TradingPolicy,
    *,
    symbol: str,
    asset_class: str,
    market_cap_usd: float | None = None,
    average_daily_volume_usd: float | None = None,
    sector: str | None = None,
    spread_bps: float | None = None,
    risk_pct_of_account: float,
    reward_to_risk_ratio: float,
    leverage: float,
    has_stop_loss: bool,
    open_positions_count: int,
    portfolio_concentration_pct: float,
    hours_to_earnings: float | None = None,
    hours_since_earnings: float | None = None,
    high_impact_macro_active: bool = False,
    fed_fomc_active: bool = False,
    ecb_active: bool = False,
    credibility: float | None = None,
    walk_forward_efficiency: float | None = None,
    monte_carlo_p_value: float | None = None,
    edge_report_present: bool = False,
    auto_live: bool = False,
    enforce_edge_thresholds: bool = False,
    account_daily_drawdown_pct: float | None = None,
    account_weekly_drawdown_pct: float | None = None,
    account_max_drawdown_pct: float | None = None,
    basket_max_asset_weight_pct: float | None = None,
    basket_max_sector_weight_pct: float | None = None,
    basket_violating_asset: str | None = None,
    basket_violating_sector: str | None = None,
    optional_measurements: tuple[str, ...] | None = None,
) -> PolicyGateResult:
    """Evalúa la política sobre una propuesta concreta.

    ``optional_measurements``: reglas que la política declara NO medibles hoy y que por
    tanto pueden quedar ``SKIPPED`` con motivo. ``None`` (default) usa la declaración de
    la propia política —``policy.optional_measurements``— para que la decisión viaje con
    la política y no dependa de que cada llamador se acuerde de pasarla. Un valor
    explícito manda sobre el de la política (tests y caminos ad-hoc).

    ``optional_measurements=()`` ⇒ **todo** dato exigido es obligatorio: es el modo
    estricto y el default de una política que no declara excepciones.
    """
    declared_optional = frozenset(
        policy.optional_measurements if optional_measurements is None else optional_measurements
    )
    rules: list[PolicyRuleResult] = []
    vetos: list[str] = []

    def push(r: PolicyRuleResult) -> None:
        rules.append(r)
        if r.status == "FAILED":
            vetos.append(r.message or f"{r.rule}: {r.actual} vs {r.limit}")

    u = policy.universe
    push(
        _rule(
            "AssetClass",
            "|".join(u.allowed_asset_classes),
            asset_class,
            asset_class in u.allowed_asset_classes,
        )
    )
    if symbol.upper() in {t.upper() for t in u.excluded_tickers}:
        push(_rule("ExcludedTicker", "not in blacklist", symbol, False, f"Ticker excluido: {symbol}"))
    if sector and sector in u.excluded_sectors:
        push(_rule("ExcludedSector", f"not in {('|'.join(u.excluded_sectors))}", sector, False))

    if u.min_market_cap_usd is not None:
        if market_cap_usd is None:
            push(
                _unmeasured(
                    "MinMarketCap",
                    str(u.min_market_cap_usd),
                    declared_optional="MinMarketCap" in declared_optional,
                )
            )
        else:
            push(
                _rule(
                    "MinMarketCap",
                    str(u.min_market_cap_usd),
                    str(market_cap_usd),
                    market_cap_usd >= u.min_market_cap_usd,
                )
            )
    if u.min_average_daily_volume_usd is not None:
        if average_daily_volume_usd is None:
            push(
                _unmeasured(
                    "MinADV",
                    str(u.min_average_daily_volume_usd),
                    declared_optional="MinADV" in declared_optional,
                )
            )
        else:
            push(
                _rule(
                    "MinADV",
                    str(u.min_average_daily_volume_usd),
                    str(average_daily_volume_usd),
                    average_daily_volume_usd >= u.min_average_daily_volume_usd,
                )
            )
    if u.max_spread_bps is not None:
        if spread_bps is None:
            push(
                _unmeasured(
                    "MaxSpreadBps",
                    str(u.max_spread_bps),
                    declared_optional="MaxSpreadBps" in declared_optional,
                )
            )
        else:
            push(
                _rule(
                    "MaxSpreadBps",
                    str(u.max_spread_bps),
                    str(spread_bps),
                    spread_bps <= u.max_spread_bps,
                )
            )

    x = policy.exposure
    push(_rule("MaxLeverage", str(x.max_leverage), str(leverage), leverage <= x.max_leverage))
    push(
        _rule(
            "MaxOpenPositions",
            str(x.max_open_positions),
            str(open_positions_count),
            open_positions_count < x.max_open_positions,
        )
    )
    # Encaje de cesta (PortfolioFit v1): cuando la señal de cesta viene presente,
    # la concentración por ACTIVO se evalúa a nivel CESTA (no el `portfolio_concentration_pct`
    # del trade individual). La métrica de exceso por SECTOR es la regla `MaxSectorExposure`.
    if basket_max_asset_weight_pct is not None:
        push(
            _rule(
                "MaxConcentration",
                f"{x.max_portfolio_concentration_pct}% cesta",
                f"{basket_max_asset_weight_pct}% activo",
                basket_max_asset_weight_pct <= x.max_portfolio_concentration_pct,
                None
                if basket_max_asset_weight_pct <= x.max_portfolio_concentration_pct
                else f"Concentración cesta superada: {basket_violating_asset or '?'} ({basket_max_asset_weight_pct:.2f}%)",
            )
        )
    else:
        push(
            _rule(
                "MaxConcentration",
                f"{x.max_portfolio_concentration_pct}%",
                f"{portfolio_concentration_pct}%",
                portfolio_concentration_pct <= x.max_portfolio_concentration_pct,
            )
        )

    # MaxSectorExposure: usa `x.max_sector_exposure_pct` (ExposureConstraints). La regla
    # está SIEMPRE activa (el límite siempre existe); lo que puede faltar es la medición
    # del encaje de cesta. Sin ella, P2 (auditoría .183) la declara no verificable.
    if basket_max_sector_weight_pct is not None:
        push(
            _rule(
                "MaxSectorExposure",
                f"{x.max_sector_exposure_pct}%",
                f"{basket_max_sector_weight_pct}%",
                basket_max_sector_weight_pct <= x.max_sector_exposure_pct,
                None
                if basket_max_sector_weight_pct <= x.max_sector_exposure_pct
                else f"Exposición sector superada: {basket_violating_sector or '?'} ({basket_max_sector_weight_pct:.2f}%)",
            )
        )
    else:
        push(
            _unmeasured(
                "MaxSectorExposure",
                f"{x.max_sector_exposure_pct}%",
                declared_optional="MaxSectorExposure" in declared_optional,
            )
        )

    risk = policy.risk
    push(
        _rule(
            "MaxRiskPerTrade",
            f"{risk.max_risk_per_trade_pct}%",
            f"{risk_pct_of_account}%",
            risk_pct_of_account <= risk.max_risk_per_trade_pct,
        )
    )
    push(
        _rule(
            "MinRewardToRisk",
            str(risk.min_reward_to_risk_ratio),
            str(reward_to_risk_ratio),
            reward_to_risk_ratio >= risk.min_reward_to_risk_ratio,
        )
    )
    if risk.stop_loss_required:
        push(
            _rule(
                "StopLossRequired",
                "true",
                str(has_stop_loss),
                has_stop_loss,
                None if has_stop_loss else "Stop loss obligatorio",
            )
        )

    # Circuit breaker — drawdowns de cuenta (F4). Sin telemetría la regla es no
    # verificable: P2 (auditoría .183) la veta salvo declaración explícita en la política.
    if account_daily_drawdown_pct is not None:
        push(
            _rule(
                "HardDailyDrawdown",
                f"<= {risk.hard_daily_drawdown_limit_pct}%",
                f"{account_daily_drawdown_pct}%",
                account_daily_drawdown_pct <= risk.hard_daily_drawdown_limit_pct,
                "Circuit breaker: drawdown diario",
            )
        )
    else:
        push(
            _unmeasured(
                "HardDailyDrawdown",
                f"<= {risk.hard_daily_drawdown_limit_pct}%",
                declared_optional="HardDailyDrawdown" in declared_optional,
            )
        )
    if risk.hard_weekly_drawdown_limit_pct is not None:
        if account_weekly_drawdown_pct is not None:
            push(
                _rule(
                    "HardWeeklyDrawdown",
                    f"<= {risk.hard_weekly_drawdown_limit_pct}%",
                    f"{account_weekly_drawdown_pct}%",
                    account_weekly_drawdown_pct <= risk.hard_weekly_drawdown_limit_pct,
                    "Circuit breaker: drawdown semanal",
                )
            )
        else:
            push(
                _unmeasured(
                    "HardWeeklyDrawdown",
                    f"<= {risk.hard_weekly_drawdown_limit_pct}%",
                    declared_optional="HardWeeklyDrawdown" in declared_optional,
                )
            )
    if account_max_drawdown_pct is not None:
        push(
            _rule(
                "HardMaxDrawdown",
                f"<= {risk.hard_max_drawdown_limit_pct}%",
                f"{account_max_drawdown_pct}%",
                account_max_drawdown_pct <= risk.hard_max_drawdown_limit_pct,
                "Circuit breaker: max drawdown",
            )
        )
    else:
        push(
            _unmeasured(
                "HardMaxDrawdown",
                f"<= {risk.hard_max_drawdown_limit_pct}%",
                declared_optional="HardMaxDrawdown" in declared_optional,
            )
        )

    b = policy.blackouts
    if hours_to_earnings is not None and hours_to_earnings >= 0:
        push(
            _rule(
                "PreEarningsBlackout",
                f">= {b.block_pre_earnings_hours}h clear",
                f"{hours_to_earnings}h to earnings",
                hours_to_earnings >= b.block_pre_earnings_hours,
                "Blackout pre-earnings" if hours_to_earnings < b.block_pre_earnings_hours else None,
            )
        )
    if hours_since_earnings is not None and hours_since_earnings >= 0:
        push(
            _rule(
                "PostEarningsBlackout",
                f">= {b.block_post_earnings_hours}h clear",
                f"{hours_since_earnings}h since earnings",
                hours_since_earnings >= b.block_post_earnings_hours,
            )
        )
    if b.block_fed_fomc and fed_fomc_active:
        push(_rule("FedFomcBlackout", "clear", "active", False, "FOMC activo"))
    if b.block_ecb and ecb_active:
        push(_rule("EcbBlackout", "clear", "active", False, "ECB activo"))
    if b.block_high_impact_macro and high_impact_macro_active:
        push(_rule("HighImpactMacroBlackout", "clear", "active", False, "Macro high-impact activo"))

    ev = policy.evidence
    if auto_live or enforce_edge_thresholds:
        if ev.require_edge_report_for_auto_live:
            push(
                _rule(
                    "EdgeReportRequired",
                    "present",
                    "present" if edge_report_present else "missing",
                    edge_report_present,
                )
            )
        if credibility is not None:
            push(
                _rule(
                    "MinCredibility",
                    str(ev.minimum_required_credibility),
                    str(credibility),
                    credibility >= ev.minimum_required_credibility,
                )
            )
        if walk_forward_efficiency is not None:
            push(
                _rule(
                    "MinWFE",
                    str(ev.minimum_walk_forward_efficiency),
                    str(walk_forward_efficiency),
                    walk_forward_efficiency >= ev.minimum_walk_forward_efficiency,
                )
            )
        if monte_carlo_p_value is not None:
            push(
                _rule(
                    "MaxMonteCarloP",
                    str(ev.max_monte_carlo_p_value),
                    str(monte_carlo_p_value),
                    monte_carlo_p_value <= ev.max_monte_carlo_p_value,
                )
            )

    return PolicyGateResult(
        passed=len(vetos) == 0,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        evaluated_rules=tuple(rules),
        veto_reasons=tuple(vetos),
    )
