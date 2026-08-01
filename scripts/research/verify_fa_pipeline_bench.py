#!/usr/bin/env python3
"""Operativa FA planificada + micro-bench de eficiencia (offline).

Valida el flujo: snapshot → card → gate → Composite → Screener → Paper D → Weekly.
Mide latencias sintéticas y falla si superan presupuestos (regresión de perf).

Uso:
  python scripts/research/verify_fa_pipeline_bench.py
  pnpm test:fa   # fase 3/4 vía battery
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / "packages" / "py" / "market" / "src"),
    str(ROOT / "packages" / "py" / "analytics" / "src"),
    str(ROOT / "packages" / "py" / "application" / "src"),
]

# Presupuestos ms (sintético CPU-bound; holgados para CI Windows)
BUDGET_SNAPSHOT_MS = 25.0
BUDGET_CARD_MS = 15.0
BUDGET_COMPOSITE_MS = 20.0
BUDGET_SCREENER_N50_MS = 80.0
BUDGET_WEEKLY_MS = 50.0
N_WARM = 3
N_BENCH = 20


def _raw(n: float) -> dict:
    return {"raw": n, "fmt": str(n)}


def _rich_modules() -> dict:
    """Módulos Yahoo sintéticos con cobertura F2.1–F2.8."""
    bal_c = {
        "totalAssets": _raw(1.1e11),
        "totalCurrentAssets": _raw(5.5e10),
        "totalCurrentLiabilities": _raw(2.5e10),
        "longTermDebt": _raw(2.0e10),
        "ordinarySharesNumber": _raw(1.0e10),
        "retainedEarnings": _raw(3.0e10),
        "totalLiab": _raw(4.0e10),
        "totalStockholderEquity": _raw(7.0e10),
        "netReceivables": _raw(1.2e10),
        "netPPE": _raw(3.0e10),
    }
    bal_p = {
        "totalAssets": _raw(1.0e11),
        "totalCurrentAssets": _raw(4.0e10),
        "totalCurrentLiabilities": _raw(2.5e10),
        "longTermDebt": _raw(3.0e10),
        "ordinarySharesNumber": _raw(1.0e10),
        "netReceivables": _raw(9.0e9),
        "netPPE": _raw(2.8e10),
        "totalStockholderEquity": _raw(6.0e10),
    }
    inc_c = {
        "netIncome": _raw(1.2e10),
        "totalRevenue": _raw(1.2e11),
        "grossProfit": _raw(6.0e10),
        "ebit": _raw(1.8e10),
        "sellingGeneralAdministrative": _raw(1.5e10),
        "depreciationAndAmortization": _raw(4.0e9),
        "incomeTaxExpense": _raw(3.0e9),
        "incomeBeforeTax": _raw(1.5e10),
    }
    inc_p = {
        "netIncome": _raw(8.0e9),
        "totalRevenue": _raw(1.0e11),
        "grossProfit": _raw(4.5e10),
        "sellingGeneralAdministrative": _raw(1.2e10),
        "depreciationAndAmortization": _raw(3.5e9),
    }
    cf_c = {
        "totalCashFromOperatingActivities": _raw(1.5e10),
        "depreciationAndAmortization": _raw(4.0e9),
    }
    cf_p = {
        "totalCashFromOperatingActivities": _raw(1.2e10),
        "depreciationAndAmortization": _raw(3.5e9),
    }
    return {
        "summaryProfile": {"sector": "Technology"},
        "summaryDetail": {
            "marketCap": _raw(2e11),
            "trailingPE": _raw(28.0),
            "averageVolume": _raw(5e6),
            "regularMarketPrice": _raw(100.0),
        },
        "financialData": {
            "returnOnEquity": _raw(0.18),
            "operatingMargins": _raw(0.25),
            "revenueGrowth": _raw(0.1),
            "debtToEquity": _raw(80.0),
            "currentRatio": _raw(1.4),
            "freeCashflow": _raw(8e9),
            "ebitda": _raw(2e10),
            "totalRevenue": _raw(1.2e11),
            "totalDebt": _raw(2.5e10),
            "totalCash": _raw(1.5e10),
            "currentPrice": _raw(100.0),
        },
        "defaultKeyStatistics": {
            "trailingEps": _raw(12.0),
            "bookValue": _raw(40.0),
            "sharesOutstanding": _raw(2e9),
            "beta": _raw(1.15),
        },
        "balanceSheetHistory": {"balanceSheetStatements": [bal_c, bal_p]},
        "incomeStatementHistory": {"incomeStatementHistory": [inc_c, inc_p]},
        "cashflowStatementHistory": {"cashflowStatements": [cf_c, cf_p]},
    }


def _ms(fn, n: int) -> float:
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t0) * 1000.0 / n


def main() -> int:
    print("=== verify_fa_pipeline_bench (offline) ===")
    from bolsa_market.instrument_fundamentals import build_fundamentals_snapshot
    from bolsa_analytics.knowledge.fundamental_card import build_fundamental_card
    from bolsa_analytics.knowledge.composite_score import build_composite_card
    from bolsa_analytics.signals.fundamental_gate import build_fundamental_gate
    from bolsa_analytics.signals.fundamental_screener import evaluate_fundamental_candidate
    from bolsa_application.fa_weekly_pipeline import (
        FA_WEEKLY_PIPELINE_VERSION,
        RunFaWeeklyPipeline,
    )
    from bolsa_application.paper_d_propose import PAPER_D_PROPOSE_VERSION, ProposePaperDPlan
    from bolsa_application.run_fundamental_screener import RunFundamentalScreener

    modules = _rich_modules()
    for _ in range(N_WARM):
        build_fundamentals_snapshot(yahoo_modules=modules)

    snap_ms = _ms(lambda: build_fundamentals_snapshot(yahoo_modules=modules), N_BENCH)
    snap = build_fundamentals_snapshot(yahoo_modules=modules)
    snap["fetchedAt"] = datetime.now(timezone.utc).isoformat()

    # Contratos planificados F2.5–F2.8 + CAPM
    assert snap["beta"] is not None
    assert snap["waccMethod"] == "fund_capm_v1", snap["waccMethod"]
    assert snap["advUsd"] is not None and snap["advUsd"] > 0
    assert snap["roic"] is not None and snap["roicMethod"] == "roic_nopat_ic_v1"
    assert snap["beneishM"] is not None and snap["beneishMethod"] == "beneish_m_annual_v1"
    assert snap["dcfScenarios"]["method"] == "dcf_scenarios_v1"
    assert snap["piotroski"] == 9
    print(
        f"OK snapshot rich: CAPM beta={snap['beta']} roic={snap['roic']:.3f} "
        f"beneishM={snap['beneishM']:.2f} advUsd={snap['advUsd']:.0f}"
    )

    card_ms = _ms(
        lambda: build_fundamental_card(
            instrument_id="bench", ticker="BENCH", fundamentals=snap
        ),
        N_BENCH,
    )
    card = build_fundamental_card(instrument_id="bench", ticker="BENCH", fundamentals=snap)
    assert card["derived"]["roic"] == snap["roic"]
    assert card["derived"]["beneishM"] == snap["beneishM"]
    assert "bias" not in card
    assert card["scoreDisplay100"] is not None

    comp_ms = _ms(
        lambda: build_composite_card(
            instrument_id="bench",
            ticker="BENCH",
            fundamentals=snap,
            horizon="swing",
            regime="neutral",
        ),
        N_BENCH,
    )
    comp = build_composite_card(
        instrument_id="bench",
        ticker="BENCH",
        fundamentals=snap,
        horizon="swing",
        regime="neutral",
    )
    liq = next(L for L in comp["legs"] if L["key"] == "liquidity")
    assert str(liq.get("method") or "").startswith("adv_"), liq
    assert comp["metadata"]["paperDUnlocked"] is True
    print(f"OK composite liquidity={liq['method']} display={comp['scoreDisplay100']}")

    gate = build_fundamental_gate(min_roic=0.05, max_beneish_m=0.0, min_piotroski=7)
    assert gate is not None

    def _screen_50() -> None:
        for i in range(50):
            evaluate_fundamental_candidate(
                instrument_id=f"i{i}",
                symbol=f"T{i}",
                name=None,
                fundamentals=snap,
                gate=gate,
            )

    for _ in range(N_WARM):
        _screen_50()
    screen_ms = _ms(_screen_50, max(5, N_BENCH // 4))
    print(f"OK screener x50 avg {screen_ms:.2f}ms")

    # Pipeline weekly con fakes (contrato orquestación)
    class _Scr:
        async def execute(self, payload):
            return {
                "screenerVersion": "fund_screener_v1",
                "screenerId": "s1",
                "scannedCount": 1,
                "hitCount": 1,
                "skippedCount": 0,
                "fundamentalsRefreshedCount": 0,
                "listId": "uni",
                "persistedListId": "wl-1",
                "weekKey": "2026-W31",
                "hits": [{"instrumentId": "bench", "symbol": "BENCH"}],
                "skipped": [],
            }

    class _Prop:
        async def execute(self, payload):
            assert payload["universe"]["listId"] == "wl-1"
            assert PAPER_D_PROPOSE_VERSION == "paper_d_propose_v2"
            return {
                "proposeVersion": PAPER_D_PROPOSE_VERSION,
                "planId": "pd_bench",
                "weekKey": "2026-W31",
                "scannedCount": 1,
                "eligibleCount": 1,
                "candidates": [],
                "rankingReady": True,
                "executeAllowedByEnv": False,
                "executeRequested": False,
                "executeStatus": "dry_run",
                "execution": None,
                "notes": [],
            }

    import asyncio

    async def _run_weekly():
        return await RunFaWeeklyPipeline(_Scr(), _Prop()).execute(
            {
                "universe": {"listId": "uni"},
                "fundamentalGate": gate,
                "persist": {},
                "execute": False,
            }
        )

    for _ in range(N_WARM):
        asyncio.run(_run_weekly())
    t0 = time.perf_counter()
    for _ in range(N_BENCH):
        result = asyncio.run(_run_weekly())
    weekly_ms = (time.perf_counter() - t0) * 1000.0 / N_BENCH
    assert result["pipelineVersion"] == FA_WEEKLY_PIPELINE_VERSION
    assert result["status"] == "completed"
    assert result["propose"]["executeStatus"] == "dry_run"
    print(f"OK weekly pipeline {FA_WEEKLY_PIPELINE_VERSION} -> Paper D dry_run")

    # Paper D propose unitario (repos mínimos)
    class _Lists:
        async def get_by_id(self, list_id: str):
            return SimpleNamespace(id=list_id, instrument_ids=["bench"])

    class _Instr:
        async def get_by_id(self, iid: str):
            return SimpleNamespace(id=iid, symbol="BENCH")

        async def get_fundamentals(self, iid: str):
            return snap

        async def get_quotes_by_ids(self, ids: list[str]):
            return [SimpleNamespace(id=i, last_close=100.0) for i in ids]

    async def _propose():
        return await ProposePaperDPlan(_Instr(), _Lists()).execute(
            {
                "universe": {"listId": "wl-1"},
                "minScoreDisplay100": 0,
                "execute": False,
            }
        )

    pd = asyncio.run(_propose())
    assert pd["proposeVersion"] == "paper_d_propose_v2"
    assert pd["executeStatus"] == "dry_run"
    print(f"OK Paper D propose: elegibles={pd['eligibleCount']} status={pd['executeStatus']}")

    # Budgets
    budgets = [
        ("snapshot", snap_ms, BUDGET_SNAPSHOT_MS),
        ("card", card_ms, BUDGET_CARD_MS),
        ("composite", comp_ms, BUDGET_COMPOSITE_MS),
        ("screener_x50", screen_ms, BUDGET_SCREENER_N50_MS),
        ("weekly", weekly_ms, BUDGET_WEEKLY_MS),
    ]
    print("--- latencias avg (ms) ---")
    failed = False
    for name, got, budget in budgets:
        flag = "OK" if got <= budget else "SLOW"
        print(f"  {flag} {name}: {got:.2f} (budget {budget})")
        if got > budget:
            failed = True
    if failed:
        print("FAIL: presupuesto de eficiencia excedido")
        return 1

    # Smoke tipos application (import path)
    assert RunFundamentalScreener is not None
    print("OK: pipeline FA planificado + eficiencia")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1) from exc
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        raise SystemExit(1) from exc
