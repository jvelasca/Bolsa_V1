"""IO — filas extras CORE-R desde PnL DEMO/paper (espejo fetchPnlExtraRows TS)."""

from __future__ import annotations

import logging
from typing import Any

from bolsa_application.accounts import ListAccountSummaries
from bolsa_application.core_r_server_tick import (
    CORE_R_PNL_LIST_CAP,
    account_return_pct,
    build_paper_pnl_review_row,
    find_paper_for_top_slots,
)
from bolsa_application.lists import GetInstrumentList
from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
    SqlAlchemyInstrumentStrategyTopRepository,
)

logger = logging.getLogger(__name__)


def _slot_strategy_ids(slots: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        sid = slot.get("strategyDefinitionId") or slot.get("strategy_definition_id")
        if isinstance(sid, str) and sid.strip():
            out.append(sid.strip())
    return out


def _slot1_run_id(slots: list[dict[str, Any]]) -> str | None:
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        rank = slot.get("rank")
        if rank is not None and int(rank) != 1:
            continue
        run_id = slot.get("runId") or slot.get("run_id")
        if isinstance(run_id, str) and run_id.strip():
            return run_id.strip()
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        run_id = slot.get("runId") or slot.get("run_id")
        if isinstance(run_id, str) and run_id.strip():
            return run_id.strip()
    return None


async def fetch_core_r_pnl_extra_rows(
    *,
    list_id: str,
    get_list: GetInstrumentList,
    list_summaries: ListAccountSummaries,
    top_repo: SqlAlchemyInstrumentStrategyTopRepository,
    timeframe: str = "1d",
) -> list[dict[str, Any]]:
    """Best-effort: no TOP writes · no orders · swallow per-instrument errors."""
    extras: list[dict[str, Any]] = []
    try:
        detail = await get_list.execute(list_id)
        if detail is None:
            return []
        instrument_ids = list(detail.instrument_ids or [])[:CORE_R_PNL_LIST_CAP]
        if not instrument_ids:
            return []

        summaries = await list_summaries.execute()
        accounts = [
            {
                "id": s.account.id,
                "type": s.account.type,
                "status": s.account.status,
                "strategyDefinitionId": s.account.strategy_definition_id,
                "initialDeposit": s.account.initial_deposit,
                "totalEquity": s.total_equity,
                "totalUnrealizedPnl": s.total_unrealized_pnl,
            }
            for s in summaries
        ]
        summary_by_id = {a["id"]: a for a in accounts}

        tops = await top_repo.list_for_instruments(instrument_ids, timeframe)
        top_by_id = {t.instrument_id: t for t in tops}

        for instrument_id in instrument_ids:
            top = top_by_id.get(instrument_id)
            if top is None or not top.slots:
                continue
            strategy_ids = _slot_strategy_ids(top.slots)
            paper = find_paper_for_top_slots(accounts, strategy_ids)
            if paper is None:
                if strategy_ids:
                    logger.warning(
                        "CORE-R PnL extras: no paper account for instrument_id=%s strategy_ids=%s",
                        instrument_id,
                        strategy_ids,
                    )
                continue
            live = summary_by_id.get(str(paper["id"]))
            if live is None:
                logger.warning(
                    "CORE-R PnL extras: no live summary for paper account id=%s instrument_id=%s",
                    paper["id"],
                    instrument_id,
                )
                continue
            return_pct = account_return_pct(
                float(live["initialDeposit"]),
                float(live["totalEquity"]),
            )
            if return_pct is None:
                continue
            symbol = (top.symbol or instrument_id[:8]).strip() or instrument_id[:8]
            row = build_paper_pnl_review_row(
                instrument_id=instrument_id,
                symbol=symbol,
                timeframe=timeframe,
                return_pct=return_pct,
                slot1_run_id=_slot1_run_id(top.slots),
            )
            if row:
                extras.append(row)
    except Exception:
        logger.exception("CORE-R PnL extras failed for listId=%s", list_id)
    return extras
