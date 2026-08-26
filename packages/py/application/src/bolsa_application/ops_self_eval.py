"""OE-1 — Autoevaluación operativa SEMI + AUTO (read-only; measure ≠ Accept).

Construye un scorecard PASS/FAIL/WARN. No inventa fills, no flip
``PAPER_D_EXECUTE``, no Accept estricto.
"""

from __future__ import annotations

from typing import Any, Literal

from bolsa_application.operational_readiness import derive_operational_readiness

GateMark = Literal["PASS", "FAIL", "WARN", "UNAVAILABLE"]


def _mark(ok: bool, *, warn: bool = False, unavailable: bool = False) -> GateMark:
    if unavailable:
        return "UNAVAILABLE"
    if ok:
        return "PASS"
    if warn:
        return "WARN"
    return "FAIL"


def build_ops_self_eval_report(
    *,
    account_id: str,
    lookback_days: int,
    paper_d_execute_env: bool,
    kill_switch_effective: bool,
    broker_venue: Literal["paper", "live"],
    account_venue_preference: Literal["paper", "live"] | None = None,
    days_with_opinions: int | None = None,
    buy_precision_5d: float | None = None,
    buy_recall_5d: float | None = None,
    alarma_buy_count: int | None = None,
    mature_buy_sample: int | None = None,
    confirm_seed: int | None = None,
    journal_seed: int | None = None,
    buys_seed: int | None = None,
    trade_like: int | None = None,
    cash_max_dd_frac: float | None = None,
    portfolio_reconciliation: dict[str, Any] | None = None,
    portfolio_reconciliation_status: Literal[
        "ok", "not_wired", "unavailable", "error", "drift"
    ] = "not_wired",
) -> dict[str, Any]:
    """Informe JSON-friendly: carriles SEMI y AUTO + honesty."""

    auto_unavailable = days_with_opinions is None
    p1 = days_with_opinions if days_with_opinions is not None else 0
    p1_mark = _mark(p1 >= 60, unavailable=auto_unavailable)

    # null precisión/recall con telemetría presente = FAIL (runbook), no UNAVAILABLE
    p3_ok = buy_precision_5d is not None and float(buy_precision_5d) >= 0.7
    p3_mark = _mark(p3_ok, unavailable=auto_unavailable)

    p4_ok = buy_recall_5d is not None and float(buy_recall_5d) >= 0.55
    p4_mark = _mark(p4_ok, unavailable=auto_unavailable)

    semi_unavailable = confirm_seed is None
    confirm_n = confirm_seed if confirm_seed is not None else 0
    buys_n = buys_seed if buys_seed is not None else 0
    # SEMI path operable: counts disponibles.
    semi_path_mark: GateMark = "UNAVAILABLE" if semi_unavailable else "PASS"
    p2_mark = _mark(confirm_n >= 50, unavailable=semi_unavailable)

    trade_n = trade_like if trade_like is not None else 0
    dd = cash_max_dd_frac if cash_max_dd_frac is not None else 0.0
    p5_ok = trade_n > 0 and dd <= 0.1
    p5_warn = trade_n == 0 and trade_like is not None
    p5_mark = _mark(
        p5_ok,
        warn=p5_warn,
        unavailable=trade_like is None,
    )

    auto_execute_allowed = bool(paper_d_execute_env)
    auto_gates = [p1_mark, p2_mark, p3_mark, p4_mark, p5_mark]
    auto_lane: GateMark
    if any(g == "UNAVAILABLE" for g in auto_gates):
        auto_lane = "UNAVAILABLE"
    elif all(g == "PASS" for g in auto_gates):
        auto_lane = "PASS"
    elif any(g == "FAIL" for g in auto_gates):
        auto_lane = "FAIL"
    elif any(g == "WARN" for g in auto_gates):
        auto_lane = "WARN"
    else:
        auto_lane = "FAIL"

    # SEMI: path OK pero sin evidencia fills → WARN
    semi_lane: GateMark = semi_path_mark
    if semi_lane == "PASS" and confirm_n == 0 and buys_n == 0:
        semi_lane = "WARN"

    recon = portfolio_reconciliation
    if portfolio_reconciliation_status != "ok":
        recon = {
            "status": portfolio_reconciliation_status,
            "note": "OI-6 detect/report; no heal · OR-4 opening veto if drift",
            **(portfolio_reconciliation or {}),
        }

    readiness = derive_operational_readiness(
        broker_venue=broker_venue,
        kill_switch_effective=kill_switch_effective,
        portfolio_reconciliation_status=portfolio_reconciliation_status,
        semi_path_mark=semi_lane,
    )

    return {
        "schemaVersion": "ops_self_eval_v0",
        "rule": "measure ≠ Accept estricto · ≠ flip PAPER_D_EXECUTE",
        "accountId": account_id,
        "lookbackDays": lookback_days,
        "lanes": {
            "semi": {
                "mark": semi_lane,
                "confirmSeed": confirm_seed,
                "journalSeed": journal_seed,
                "buysSeed": buys_seed,
                "tradeLike": trade_like,
                "pathAvailable": semi_path_mark == "PASS" or semi_path_mark == "WARN",
            },
            "auto": {
                "mark": auto_lane,
                "paperDExecuteEnv": paper_d_execute_env,
                "executeOptIn": auto_execute_allowed,
                "p1": {"daysWithOpinions": days_with_opinions, "mark": p1_mark, "need": 60},
                "p2": {"confirmSeed": confirm_seed, "mark": p2_mark, "need": 50},
                "p3": {
                    "buyPrecision5d": buy_precision_5d,
                    "alarmaBuyCount": alarma_buy_count,
                    "matureBuySample": mature_buy_sample,
                    "mark": p3_mark,
                    "need": 0.7,
                },
                "p4": {
                    "buyRecall5d": buy_recall_5d,
                    "mark": p4_mark,
                    "need": 0.55,
                },
                "p5": {
                    "tradeLike": trade_like,
                    "cashMaxDdFrac": cash_max_dd_frac,
                    "mark": p5_mark,
                    "note": (
                        "0 trades → cash DD not a valid trading MaxDD"
                        if p5_warn
                        else None
                    ),
                },
                "strictAcceptReady": auto_lane == "PASS",
            },
        },
        "runtime": {
            "killSwitchEffective": kill_switch_effective,
            "brokerVenue": broker_venue,
            "accountVenuePreference": account_venue_preference,
            "paperDExecuteEnv": paper_d_execute_env,
            "confirmPathHonesty": "SEMI Confirm = única firma; AUTO execute solo opt-in env",
        },
        "portfolioReconciliation": recon,
        "operationalReadiness": readiness,
    }
