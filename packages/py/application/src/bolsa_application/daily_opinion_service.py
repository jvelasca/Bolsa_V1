"""DailyOpinionService — dictamen on-demand + caché (O3-C / ADR-022)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from bolsa_application.daily_opinion_stance import (
    ENGINE_VERSION,
    StanceInput,
    compute_stance,
)
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_infrastructure.database.repositories.instrument_daily_opinion_repository import (
    InstrumentDailyOpinionRecord,
    SqlAlchemyInstrumentDailyOpinionRepository,
    make_idempotency_key,
)
from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
    SqlAlchemyInstrumentStrategyTopRepository,
)
from bolsa_infrastructure.database.repositories.ohlcv_repository import (
    SqlAlchemyOhlcvRepository,
)

SOURCE_ON_DEMAND = "on_demand"
SOURCE_EOD_BATCH = "eod_batch"
EOD_STALE_MAX_DAYS = 5


@dataclass(frozen=True, slots=True)
class OpinionHint:
    instrument_id: str
    io_score: float | None = None
    fa_score: float | None = None
    ta_score: float | None = None
    distress: bool = False
    position_open: bool = False
    allow_trading: bool = True
    has_eod_bar: bool | None = None


def _parse_bar_date(raw: str | None) -> date | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    # YYYY-MM-DD or ISO datetime
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _top_slot1_stars(slots: list[dict[str, Any]]) -> float | None:
    if not slots:
        return None
    ranked = sorted(
        slots,
        key=lambda s: int(s.get("rank") or 99),
    )
    stars = ranked[0].get("stars")
    if stars is None:
        return None
    try:
        return float(stars)
    except (TypeError, ValueError):
        return None


class DailyOpinionService:
    def __init__(
        self,
        opinion_repo: SqlAlchemyInstrumentDailyOpinionRepository,
        top_repo: SqlAlchemyInstrumentStrategyTopRepository,
        ohlcv_repo: SqlAlchemyOhlcvRepository,
    ) -> None:
        self._opinions = opinion_repo
        self._tops = top_repo
        self._ohlcv = ohlcv_repo

    async def query(
        self,
        *,
        instrument_ids: list[str],
        as_of_bar_date: date | None = None,
        account_id: str | None = None,
        force_refresh: bool = False,
        hints: list[OpinionHint] | None = None,
        timeframe: str = "1d",
        now: datetime | None = None,
        source: str = SOURCE_ON_DEMAND,
    ) -> list[InstrumentDailyOpinionRecord]:
        as_of = as_of_bar_date or datetime.now(UTC).date()
        ids = list(dict.fromkeys(i for i in instrument_ids if i))
        if not ids:
            return []
        src = source if source in (SOURCE_ON_DEMAND, SOURCE_EOD_BATCH, "manual") else SOURCE_ON_DEMAND

        hint_by_id = {h.instrument_id: h for h in (hints or [])}
        cached: dict[str, InstrumentDailyOpinionRecord] = {}
        if not force_refresh:
            for row in await self._opinions.list_for_instruments(ids, as_of, src):
                cached[row.instrument_id] = row

        out: list[InstrumentDailyOpinionRecord] = []
        for instrument_id in ids:
            if not force_refresh and instrument_id in cached:
                out.append(cached[instrument_id])
                continue
            hint = hint_by_id.get(instrument_id) or OpinionHint(instrument_id=instrument_id)
            row = await self._compute_and_upsert(
                instrument_id=instrument_id,
                as_of=as_of,
                account_id=account_id,
                hint=hint,
                timeframe=timeframe,
                now=now,
                source=src,
            )
            out.append(row)
        return out

    async def run_eod_batch(
        self,
        *,
        instrument_ids: list[str],
        as_of_bar_date: date | None = None,
        account_id: str | None = None,
        force: bool = True,
    ) -> list[InstrumentDailyOpinionRecord]:
        """Batch post-cierre (source=eod_batch). Siempre force_refresh salvo force=False."""
        return await self.query(
            instrument_ids=instrument_ids,
            as_of_bar_date=as_of_bar_date,
            account_id=account_id,
            force_refresh=force,
            hints=[],
            source=SOURCE_EOD_BATCH,
        )
    async def history(
        self,
        instrument_id: str,
        *,
        days: int = 30,
        ensure_days: int = 0,
        account_id: str | None = None,
        hint: OpinionHint | None = None,
        timeframe: str = "1d",
    ) -> list[InstrumentDailyOpinionRecord]:
        """Historial de dictámenes; opcionalmente rellena días laborables faltantes."""
        days = max(1, min(int(days), 90))
        ensure_days = max(0, min(int(ensure_days), 21))
        as_of_end = datetime.now(UTC).date()
        date_from = as_of_end - timedelta(days=days - 1)

        if ensure_days > 0:
            base_hint = hint or OpinionHint(instrument_id=instrument_id)
            # No forzar has_eod del cliente: cada día se valida por barra ≤ asOf.
            day_hint = OpinionHint(
                instrument_id=instrument_id,
                io_score=base_hint.io_score,
                fa_score=base_hint.fa_score,
                ta_score=base_hint.ta_score,
                distress=base_hint.distress,
                position_open=base_hint.position_open,
                allow_trading=base_hint.allow_trading,
                has_eod_bar=None,
            )
            ensure_from = as_of_end - timedelta(days=ensure_days - 1)
            existing = {
                r.as_of_bar_date
                for r in await self._opinions.list_history(
                    instrument_id,
                    date_from=ensure_from,
                    date_to=as_of_end,
                    source=SOURCE_ON_DEMAND,
                )
            }
            cursor = ensure_from
            while cursor <= as_of_end:
                if cursor.weekday() < 5 and cursor not in existing:
                    stance_now = datetime(
                        cursor.year, cursor.month, cursor.day, 18, 0, tzinfo=UTC
                    )
                    await self._compute_and_upsert(
                        instrument_id=instrument_id,
                        as_of=cursor,
                        account_id=account_id,
                        hint=day_hint,
                        timeframe=timeframe,
                        now=stance_now,
                        source=SOURCE_ON_DEMAND,
                    )
                cursor += timedelta(days=1)

        return await self._opinions.list_history(
            instrument_id,
            date_from=date_from,
            date_to=as_of_end,
            source=SOURCE_ON_DEMAND,
        )

    async def _resolve_has_eod(
        self,
        instrument_id: str,
        as_of: date,
        hint: OpinionHint,
    ) -> bool:
        if hint.has_eod_bar is not None:
            return bool(hint.has_eod_bar)
        bars = await self._ohlcv.get_bars(
            instrument_id,
            timeframe=TimeFrame.D1,
            limit=1,
            date_to=as_of.isoformat(),
        )
        if not bars:
            return False
        bar_date = _parse_bar_date(bars[-1].timestamp)
        if bar_date is None:
            return False
        return (as_of - bar_date) <= timedelta(days=EOD_STALE_MAX_DAYS)

    async def _compute_and_upsert(
        self,
        *,
        instrument_id: str,
        as_of: date,
        account_id: str | None,
        hint: OpinionHint,
        timeframe: str,
        now: datetime | None,
        source: str = SOURCE_ON_DEMAND,
    ) -> InstrumentDailyOpinionRecord:
        computed_at = datetime.now(UTC)
        stance_now = now or computed_at
        src = source if source in (SOURCE_ON_DEMAND, SOURCE_EOD_BATCH, "manual") else SOURCE_ON_DEMAND
        has_eod = await self._resolve_has_eod(instrument_id, as_of, hint)
        top = await self._tops.get(instrument_id, timeframe)
        has_top = top is not None and bool(top.slots)
        top_stars = _top_slot1_stars(top.slots) if top else None
        strategy_stars_int = int(round(top_stars)) if top_stars is not None else None

        result = compute_stance(
            StanceInput(
                has_eod_bar=has_eod,
                allow_trading=bool(hint.allow_trading),
                has_top=has_top,
                top_updated_at=top.updated_at if top else None,
                top_stars=top_stars,
                io_score=hint.io_score,
                fa_distress=bool(hint.distress),
                position_open=bool(hint.position_open),
            ),
            now=stance_now,
        )

        # Invariante: sell/reduce solo con largo (defensa en profundidad)
        stance = result.stance
        if stance in ("sell_exit", "reduce") and not hint.position_open:
            stance = "no_trade"
            reasons = list(result.reasons) + ["position_closed"]
            gate = result.gate_status
            stars = result.dictamen_stars
        else:
            reasons = list(result.reasons)
            gate = result.gate_status
            stars = result.dictamen_stars

        # FA distress: techo ★ ≤3 y nunca buy (engine ya cubre; refuerzo)
        if hint.distress:
            stars = min(stars, 3)
            if stance == "buy":
                stance = "no_trade" if not hint.position_open else "reduce"
                if "fa_distress" not in reasons:
                    reasons.append("fa_distress")

        payload = {
            "instrument_id": instrument_id,
            "account_id": account_id,
            "as_of_bar_date": as_of,
            "stance": stance,
            "dictamen_stars": stars,
            "strategy_stars": strategy_stars_int,
            "io_score": hint.io_score,
            "fa_score": hint.fa_score,
            "ta_score": hint.ta_score,
            "distress": bool(hint.distress),
            "reasons": reasons,
            "gate_status": gate,
            "top_id": top.id if top else None,
            "top_version": top.version if top else None,
            "source": src,
            "engine_version": ENGINE_VERSION,
            "idempotency_key": make_idempotency_key(instrument_id, as_of, src),
            "computed_at": computed_at,
        }
        return await self._opinions.upsert(payload)
