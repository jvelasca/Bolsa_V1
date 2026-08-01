#!/usr/bin/env python3
"""Operativa FA offline (sin API): snapshot → card → gate → valuation → F2b++ RAG.

Uso (repo root):
  python scripts/research/verify_fa_operativa.py
  pnpm test:fa   # incluye este script vía battery
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / "packages" / "py" / "market" / "src"),
    str(ROOT / "packages" / "py" / "analytics" / "src"),
    str(ROOT / "packages" / "py" / "application" / "src"),
]


def _raw(n: float) -> dict:
    return {"raw": n, "fmt": str(n)}


def _piotroski_modules() -> dict:
    # Escalas coherentes (mcap ~200B, assets ~100B) para Altman/FCF/ROIC/Beneish.
    balance_curr = {
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
    balance_prev = {
        "totalAssets": _raw(1.0e11),
        "totalCurrentAssets": _raw(4.0e10),
        "totalCurrentLiabilities": _raw(2.5e10),
        "longTermDebt": _raw(3.0e10),
        "ordinarySharesNumber": _raw(1.0e10),
        "totalStockholderEquity": _raw(6.0e10),
        "netReceivables": _raw(9.0e9),
        "netPPE": _raw(2.8e10),
    }
    income_curr = {
        "netIncome": _raw(1.2e10),
        "totalRevenue": _raw(1.2e11),
        "grossProfit": _raw(6.0e10),
        "ebit": _raw(1.8e10),
        "sellingGeneralAdministrative": _raw(1.5e10),
        "depreciationAndAmortization": _raw(4.0e9),
        "incomeTaxExpense": _raw(3.0e9),
        "incomeBeforeTax": _raw(1.5e10),
    }
    income_prev = {
        "netIncome": _raw(8.0e9),
        "totalRevenue": _raw(1.0e11),
        "grossProfit": _raw(4.5e10),
        "sellingGeneralAdministrative": _raw(1.2e10),
        "depreciationAndAmortization": _raw(3.5e9),
    }
    cashflow_curr = {
        "totalCashFromOperatingActivities": _raw(1.5e10),
        "depreciationAndAmortization": _raw(4.0e9),
    }
    cashflow_prev = {
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
        "balanceSheetHistory": {
            "balanceSheetStatements": [balance_curr, balance_prev],
        },
        "incomeStatementHistory": {
            "incomeStatementHistory": [income_curr, income_prev],
        },
        "cashflowStatementHistory": {
            "cashflowStatements": [cashflow_curr, cashflow_prev],
        },
    }


def main() -> int:
    print("=== verify_fa_operativa (offline) ===")
    from bolsa_market.instrument_fundamentals import (
        FUNDAMENTALS_SOURCE_VERSION,
        build_fundamentals_snapshot,
    )
    from bolsa_analytics.knowledge.fundamental_card import build_fundamental_card
    from bolsa_analytics.signals.fundamental_gate import (
        build_fundamental_gate,
        passes_fundamental_gate,
    )
    from bolsa_analytics.signals.sector_bands import FUND_SECTOR_BANDS_VERSION

    snap = build_fundamentals_snapshot(yahoo_modules=_piotroski_modules())
    assert snap["sourceVersion"] == FUNDAMENTALS_SOURCE_VERSION
    assert snap["piotroski"] == 9, f"expected F=9 got {snap['piotroski']}"
    assert snap["piotroskiMethod"] == "piotroski_f_annual_v1"
    assert snap["fcfYield"] is not None
    assert snap["altmanZ"] is not None
    assert snap["dcfEquityValue"] is not None and snap["dcfMethod"] == "dcf_fcf_2stage_wacc_v1"
    assert snap["grahamNumber"] is not None and snap["grahamMethod"] == "graham_number_v1"
    assert snap["beta"] is not None
    assert snap["wacc"] is not None and snap["waccMethod"] == "fund_capm_v1"
    assert snap["advUsd"] is not None and snap["advUsd"] > 0
    assert snap["roic"] is not None and snap["roicMethod"] == "roic_nopat_ic_v1"
    assert snap["beneishM"] is not None and snap["beneishMethod"] == "beneish_m_annual_v1"
    sc = snap.get("dcfScenarios")
    assert isinstance(sc, dict) and sc.get("method") == "dcf_scenarios_v1"
    assert sc["bull"]["upside"] > sc["base"]["upside"] > sc["bear"]["upside"]
    assert sc["base"]["upside"] == snap["dcfUpside"]
    print(
        f"OK snapshot: piotroski={snap['piotroski']} altmanZ={snap['altmanZ']:.2f} "
        f"fcfYield={snap['fcfYield']:.4f} wacc={snap['wacc']:.3f}({snap['waccMethod']}) "
        f"roic={snap['roic']:.3f} beneishM={snap['beneishM']:.2f} advUsd={snap['advUsd']:.0f} "
        f"dcfUpside={snap['dcfUpside']:.3f} grahamUpside={snap['grahamUpside']:.3f} "
        f"dcfScenarios=bear/base/bull"
    )

    # fetchedAt for gate freshness
    snap["fetchedAt"] = datetime.now(timezone.utc).isoformat()

    card = build_fundamental_card(
        instrument_id="ops-test",
        ticker="TEST",
        fundamentals=snap,
    )
    assert card["derived"]["piotroski"] == 9
    assert card["derived"]["piotroskiMethod"] == "piotroski_f_annual_v1"
    assert card["derived"]["dcfMethod"] == "dcf_fcf_2stage_wacc_v1"
    assert card["derived"]["wacc"] == snap["wacc"]
    assert card["derived"]["waccMethod"] == "fund_capm_v1"
    assert card["derived"]["roic"] == snap["roic"]
    assert card["derived"]["beneishM"] == snap["beneishM"]
    assert card["derived"]["grahamNumber"] is not None
    assert card["scoreDisplay100"] is not None
    assert "bias" not in card
    print(
        f"OK card: scoreDisplay100={card['scoreDisplay100']} "
        f"confidence={card['metadata']['confidence']} "
        f"wacc={card['derived']['wacc']} roic={card['derived']['roic']} "
        f"dcfUpside={card['derived']['dcfUpside']}"
    )

    # Gate sin bandas: PE 28 > 25 → fail
    gate_strict = build_fundamental_gate(max_trailing_pe=25, min_piotroski=7)
    ok, reason = passes_fundamental_gate(
        {"hybrid": {"fundamentalGate": gate_strict}}, snap
    )
    assert not ok, "expected PE filter fail without bands"
    print(f"OK gate strict reject: {reason}")

    # Gate con bandas Technology: PE ≤40 → pass
    gate_bands = build_fundamental_gate(
        max_trailing_pe=25,
        min_piotroski=7,
        use_sector_bands=True,
    )
    assert gate_bands["sectorBandsVersion"] == FUND_SECTOR_BANDS_VERSION
    ok2, reason2 = passes_fundamental_gate(
        {"hybrid": {"fundamentalGate": gate_bands}}, snap
    )
    assert ok2 and reason2 is None, f"expected pass with sector bands, got {reason2}"
    print("OK gate sector bands (Technology PE<=40 + Piotroski>=7)")

    # Financial: Altman skip
    bank = dict(snap)
    bank["sector"] = "Financial Services"
    bank["altmanZ"] = 0.2
    bank["roe"] = 0.12
    bank["operatingMargin"] = 0.2
    bank["trailingPe"] = 12
    gate_fin = build_fundamental_gate(min_altman_z=2.99, min_roe=0.05, use_sector_bands=True)
    ok3, _ = passes_fundamental_gate({"hybrid": {"fundamentalGate": gate_fin}}, bank)
    assert ok3, "Financial Services should skip Altman under sector bands"
    print("OK Financial Services skips Altman under bands")

    gate_dcf = build_fundamental_gate(min_dcf_upside=-0.5)
    ok4, _ = passes_fundamental_gate({"hybrid": {"fundamentalGate": gate_dcf}}, snap)
    assert ok4, "DCF upside gate should pass with loose floor"
    print("OK DCF upside gate")

    gate_rq = build_fundamental_gate(min_roic=0.05, max_beneish_m=2.0)
    ok_rq, reason_rq = passes_fundamental_gate(
        {"hybrid": {"fundamentalGate": gate_rq}}, snap
    )
    assert ok_rq and reason_rq is None, f"ROIC/Beneish gate expected pass, got {reason_rq}"
    print("OK ROIC + Beneish gate")

    # F2b: filing store offline (disco; no toca snap)
    import os
    import tempfile

    from bolsa_market.filing_store import list_filings, read_filing_text, save_filing
    from bolsa_analytics.knowledge.filing_summary import heuristic_filing_summary

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["BOLSA_FILINGS_DIR"] = tmp
        meta = save_filing(
            instrument_id="ops-test",
            kind="10-K",
            original_name="demo-10k.txt",
            content_type="text/plain",
            content=(
                b"ITEM 1A. RISK FACTORS\nCompetition and FX.\n"
                b"ITEM 7. MD&A\nCash flow remained positive.\n"
            ),
        )
        assert meta["extractStatus"] == "ok"
        assert len(list_filings("ops-test")) == 1
        summary = heuristic_filing_summary(
            ticker="TEST",
            filing=meta,
            text=read_filing_text("ops-test", meta["id"]),
        )
        assert len(summary["paragraphs"]) == 3
        print("OK F2b filing store + heuristic summary")

        from bolsa_market.filing_rag import (
            FILING_RAG_VERSION,
            ensure_chunk_index,
            retrieve_chunks,
        )
        from bolsa_analytics.knowledge.filing_ask import heuristic_filing_answer

        idx = ensure_chunk_index("ops-test", meta["id"])
        assert idx and idx["indexVersion"] == FILING_RAG_VERSION
        assert int(meta.get("chunkCount") or 0) >= 1
        hits = retrieve_chunks(idx, "competition risk cash flow", top_k=2)
        assert hits
        ans = heuristic_filing_answer(ticker="TEST", question="risks", hits=hits)
        assert ans["answer"]
        print("OK F2b++ filing RAG TF-IDF + heuristic ask")

    from bolsa_market.sec_edgar import (
        SecEdgarClient,
        html_to_text,
        us_ticker_from_yahoo_symbol,
    )

    assert us_ticker_from_yahoo_symbol("AAPL") == "AAPL"
    assert us_ticker_from_yahoo_symbol("SAN.MC") is None
    assert "RISK" in html_to_text("<p>ITEM 1A RISK</p>").upper()
    hit = SecEdgarClient().pick_latest_filing(
        {
            "cik": "320193",
            "name": "Apple Inc.",
            "tickers": ["AAPL"],
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "accessionNumber": ["0000320193-23-000106"],
                    "primaryDocument": ["aapl.htm"],
                    "filingDate": ["2023-11-03"],
                }
            },
        },
        form="10-K",
    )
    assert hit is not None and hit.form == "10-K"
    print("OK F2b+ SEC EDGAR helpers (offline)")

    from bolsa_analytics.knowledge.composite_score import (
        COMPOSITE_SCORE_VERSION,
        build_composite_card,
    )
    from bolsa_analytics.knowledge.models import TechnicalInputs

    comp = build_composite_card(
        instrument_id="ops-test",
        ticker="TEST",
        fundamentals=snap,
        technical=TechnicalInputs(
            rsi=60,
            adx=28,
            plus_di=26,
            minus_di=16,
            obv_slope=1.0,
            price_slope=1.0,
            close=110,
            sma_20=105,
            sma_50=100,
            atr_percentile=45,
        ),
        horizon="swing",
        regime="neutral",
    )
    assert comp["metadata"]["scoreVersion"] == COMPOSITE_SCORE_VERSION
    assert comp["metadata"]["paperDUnlocked"] is True
    assert comp["combinedScore"] is not None
    assert comp["scoreDisplay100"] is not None
    print(
        f"OK F3 Composite: display={comp['scoreDisplay100']} "
        f"combined={comp['combinedScore']:.3f} conf={comp['metadata']['confidence']}"
    )

    from bolsa_analytics.signals.fundamental_screener import (
        FUNDAMENTAL_SCREENER_VERSION,
        evaluate_fundamental_candidate,
        week_key_utc,
    )

    gate_fa = build_fundamental_gate(max_trailing_pe=30, min_roe=0.05, min_piotroski=7)
    assert gate_fa is not None
    hit_fa, skip_fa = evaluate_fundamental_candidate(
        instrument_id="ops-test",
        symbol="TEST",
        name="Ops",
        fundamentals=snap,
        gate=gate_fa,
    )
    assert hit_fa is not None and skip_fa is None
    assert week_key_utc()
    print(f"OK F4 Screener FA evaluate ({FUNDAMENTAL_SCREENER_VERSION}) hit={hit_fa['symbol']}")

    from bolsa_application.paper_d_propose import PAPER_D_PROPOSE_VERSION, paper_d_execute_allowed

    assert PAPER_D_PROPOSE_VERSION == "paper_d_propose_v2"
    _ = paper_d_execute_allowed()
    print("OK Paper D propose helpers (execute off-by-default)")

    from zoneinfo import ZoneInfo

    from bolsa_application.fa_weekly_pipeline import (
        FA_WEEKLY_PIPELINE_VERSION,
        default_fa_weekly_gate,
        is_fa_weekly_window,
    )

    assert FA_WEEKLY_PIPELINE_VERSION == "fa_weekly_pipeline_v1"
    assert default_fa_weekly_gate()["conditions"]
    madrid = ZoneInfo("Europe/Madrid")
    assert is_fa_weekly_window(
        datetime(2026, 7, 31, 18, 0, tzinfo=madrid), weekday=4, hour=18
    )
    print("OK FA weekly pipeline helpers (cron off-by-default)")

    print("OK: operativa FA offline completa")
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
