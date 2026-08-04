"""R1 — Resumen operativo diario (cuenta + ledger + semana + F3 + canales).

@see docs/engineering/daily-ops-report-brief-2026-08-04.md
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from bolsa_application.accounts import GetAccountSummary, ListLedgerEntries
from bolsa_domain.entities.account import AccountSummary, LedgerEntry
from bolsa_infrastructure.alerts.estudio_opinion_email import map_opinion_to_channel
from bolsa_infrastructure.database.repositories.instrument_daily_opinion_repository import (
    SqlAlchemyInstrumentDailyOpinionRepository,
)
from bolsa_infrastructure.database.repositories.supervised_f3_repository import (
    SqlAlchemySupervisedF3Repository,
)

DAILY_OPS_REPORT_SCHEMA = "daily_ops_report_v1"
WEEK_DAYS = 7


def _day_key(iso: str) -> str | None:
    raw = (iso or "").strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    return None


@dataclass
class DailyOpsReportBundle:
    """Resultado interno del use-case (la ruta mapea a DTO HTTP)."""

    as_of: date
    generated_at: str
    account_id: str
    summary: AccountSummary
    ledger_today: list[LedgerEntry]
    trades_today: list[LedgerEntry]
    week: list[dict[str, Any]]
    f3_pending_count: int
    channels: dict[str, int]
    opinions: list[dict[str, Any]]
    notes: list[str] = field(default_factory=list)


class GetDailyOpsReport:
    """Compone el informe operativo del día para una cuenta DEMO."""

    def __init__(
        self,
        get_summary: GetAccountSummary,
        list_ledger: ListLedgerEntries,
        f3_repo: SqlAlchemySupervisedF3Repository,
        opinion_repo: SqlAlchemyInstrumentDailyOpinionRepository | None = None,
    ) -> None:
        self._get_summary = get_summary
        self._list_ledger = list_ledger
        self._f3_repo = f3_repo
        self._opinion_repo = opinion_repo

    async def execute(
        self,
        account_id: str,
        *,
        as_of: date | None = None,
        instrument_ids: list[str] | None = None,
        symbol_by_id: dict[str, str] | None = None,
    ) -> DailyOpsReportBundle:
        day = as_of or datetime.now(tz=UTC).date()
        as_of_s = day.isoformat()
        week_start = day - timedelta(days=WEEK_DAYS - 1)

        summary = await self._get_summary.execute(account_id=account_id)
        ledger_all = await self._list_ledger.execute(account_id, limit=400, offset=0)

        ledger_today: list[LedgerEntry] = []
        trades_today: list[LedgerEntry] = []
        by_day: dict[str, list[LedgerEntry]] = defaultdict(list)
        for entry in ledger_all:
            dk = _day_key(entry.executed_at)
            if not dk:
                continue
            d = date.fromisoformat(dk)
            if week_start <= d <= day:
                by_day[dk].append(entry)
            if dk == as_of_s:
                ledger_today.append(entry)
                if entry.type in {"buy", "sell"}:
                    trades_today.append(entry)

        week: list[dict[str, Any]] = []
        for i in range(WEEK_DAYS):
            d = week_start + timedelta(days=i)
            key = d.isoformat()
            rows = by_day.get(key, [])
            trades = [e for e in rows if e.type in {"buy", "sell"}]
            bal: float | None = None
            if rows:
                ordered = sorted(rows, key=lambda e: e.executed_at)
                bal = float(ordered[-1].balance_after)
            week.append(
                {
                    "date": key,
                    "tradeCount": len(trades),
                    "ledgerCount": len(rows),
                    "balanceAfter": bal,
                    "netAmount": float(sum(float(e.amount) for e in rows)),
                }
            )

        f3_state = await self._f3_repo.get(account_id)
        f3_count = len(f3_state.queue) if f3_state is not None else 0

        channels = {"alarma": 0, "aviso": 0, "none": 0}
        opinion_rows: list[dict[str, Any]] = []
        notes: list[str] = ["R1–R3: preview web + digest HTML (flag/prefs). PDF = R4."]
        ids = [i for i in (instrument_ids or []) if i]
        if ids and self._opinion_repo is not None:
            op_recs = await self._opinion_repo.list_for_instruments(ids, day, source="on_demand")
            if not op_recs:
                op_recs = await self._opinion_repo.list_for_instruments(
                    ids, day, source="eod_batch"
                )
            sym = symbol_by_id or {}
            for rec in op_recs:
                ch = map_opinion_to_channel(
                    stance=rec.stance, dictamen_stars=rec.dictamen_stars
                )
                if ch in channels:
                    channels[ch] += 1
                else:
                    channels["none"] += 1
                opinion_rows.append(
                    {
                        "instrumentId": rec.instrument_id,
                        "symbol": sym.get(rec.instrument_id),
                        "channel": ch,
                        "stance": rec.stance,
                        "dictamenStars": rec.dictamen_stars,
                        "reasons": list(rec.reasons or [])[:6],
                    }
                )
            if not op_recs:
                notes.append(
                    "Sin dictámenes cacheados para el Estudio en asOf (calcula en Opiniones)."
                )
        elif not ids:
            notes.append("Pasa instrumentIds del Estudio para Alarmas/Avisos del día.")

        return DailyOpsReportBundle(
            as_of=day,
            generated_at=datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
            account_id=account_id,
            summary=summary,
            ledger_today=ledger_today,
            trades_today=trades_today,
            week=week,
            f3_pending_count=f3_count,
            channels=channels,
            opinions=opinion_rows,
            notes=notes,
        )
