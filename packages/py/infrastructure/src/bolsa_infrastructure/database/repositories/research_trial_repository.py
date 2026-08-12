from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import Float, and_, asc, cast, desc, func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import ColumnElement

from bolsa_domain.entities.research_trial import ResearchTrial
from bolsa_infrastructure.database.models import InstrumentRow, ResearchTrialRow
from bolsa_infrastructure.ids import new_id

ResearchTrialSort = Literal[
    "created_at",
    "sharpe",
    "pnl",
    "commission",
    "k_contribution",
]


class SqlAlchemyResearchTrialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: ResearchTrialRow) -> ResearchTrial:
        return ResearchTrial(
            id=row.id,
            instrument_id=row.instrument_id,
            params=row.params if isinstance(row.params, dict) else {},
            is_metrics=row.is_metrics if isinstance(row.is_metrics, dict) else {},
            proposed_by=row.proposed_by,
            k_contribution=row.k_contribution,
            created_at=row.created_at.isoformat(),
            hypothesis_id=row.hypothesis_id,
            research_question_id=row.research_question_id,
            backtest_run_id=row.backtest_run_id,
            optimization_run_id=row.optimization_run_id,
            strategy_definition_id=row.strategy_definition_id,
            preset_key=row.preset_key,
            strategy_name=row.strategy_name,
            blocks=row.blocks if isinstance(row.blocks, dict) else None,
            is_score=None if row.is_score is None else float(row.is_score),
            parent_trial_id=row.parent_trial_id,
            fail_code=row.fail_code,
            manifest_ref=row.manifest_ref if isinstance(row.manifest_ref, dict) else None,
        )

    async def insert_trial(
        self,
        *,
        instrument_id: str,
        params: dict[str, Any],
        is_metrics: dict[str, Any],
        proposed_by: str,
        k_contribution: int = 1,
        hypothesis_id: str | None = None,
        research_question_id: str | None = None,
        backtest_run_id: str | None = None,
        optimization_run_id: str | None = None,
        strategy_definition_id: str | None = None,
        preset_key: str | None = None,
        strategy_name: str | None = None,
        blocks: dict[str, Any] | None = None,
        is_score: float | None = None,
        parent_trial_id: str | None = None,
        fail_code: str | None = None,
        manifest_ref: dict[str, Any] | None = None,
        trial_id: str | None = None,
    ) -> ResearchTrial:
        resolved_id = trial_id or new_id()
        row = ResearchTrialRow(
            id=resolved_id,
            instrument_id=instrument_id,
            hypothesis_id=hypothesis_id,
            research_question_id=research_question_id,
            backtest_run_id=backtest_run_id,
            optimization_run_id=optimization_run_id,
            strategy_definition_id=strategy_definition_id,
            preset_key=preset_key,
            strategy_name=strategy_name,
            params=params,
            blocks=blocks,
            is_metrics=is_metrics,
            is_score=None if is_score is None else Decimal(str(is_score)),
            k_contribution=k_contribution,
            proposed_by=proposed_by,
            parent_trial_id=parent_trial_id,
            fail_code=fail_code,
            manifest_ref=manifest_ref,
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def get_by_id(self, trial_id: str) -> ResearchTrial | None:
        stmt = select(ResearchTrialRow).where(ResearchTrialRow.id == trial_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return None if row is None else self._map(row)

    async def set_hypothesis_id(
        self, trial_id: str, hypothesis_id: str | None
    ) -> ResearchTrial | None:
        stmt = select(ResearchTrialRow).where(ResearchTrialRow.id == trial_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.hypothesis_id = hypothesis_id
        await self._session.flush()
        return self._map(row)

    def _metric_float(self, key: str) -> ColumnElement[float]:
        return cast(ResearchTrialRow.is_metrics[key].as_string(), Float)

    async def list_trials(
        self,
        *,
        instrument_id: str | None = None,
        hypothesis_id: str | None = None,
        proposed_by: str | None = None,
        preset_key: str | None = None,
        strategy_name: str | None = None,
        strategy_definition_id: str | None = None,
        optimization_run_id: str | None = None,
        backtest_run_id: str | None = None,
        fail_code: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort: ResearchTrialSort = "created_at",
        sort_dir: Literal["asc", "desc"] = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResearchTrial], int]:
        filters = []
        if instrument_id:
            filters.append(ResearchTrialRow.instrument_id == instrument_id)
        if hypothesis_id:
            filters.append(ResearchTrialRow.hypothesis_id == hypothesis_id)
        if proposed_by:
            filters.append(ResearchTrialRow.proposed_by == proposed_by)
        if preset_key:
            filters.append(ResearchTrialRow.preset_key == preset_key)
        if strategy_name:
            filters.append(ResearchTrialRow.strategy_name == strategy_name)
        if strategy_definition_id:
            filters.append(ResearchTrialRow.strategy_definition_id == strategy_definition_id)
        if optimization_run_id:
            filters.append(ResearchTrialRow.optimization_run_id == optimization_run_id)
        if backtest_run_id:
            filters.append(ResearchTrialRow.backtest_run_id == backtest_run_id)
        if fail_code:
            filters.append(ResearchTrialRow.fail_code == fail_code)
        if date_from:
            filters.append(ResearchTrialRow.created_at >= datetime.fromisoformat(date_from))
        if date_to:
            filters.append(ResearchTrialRow.created_at <= datetime.fromisoformat(date_to))

        count_stmt = select(func.count()).select_from(ResearchTrialRow)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one())

        order_col: Any
        metric_sort = False
        if sort == "sharpe":
            order_col = self._metric_float("sharpeRatio")
            metric_sort = True
        elif sort == "pnl":
            order_col = self._metric_float("totalReturnPct")
            metric_sort = True
        elif sort == "commission":
            order_col = self._metric_float("totalCommission")
            metric_sort = True
        elif sort == "k_contribution":
            order_col = ResearchTrialRow.k_contribution
        else:
            order_col = ResearchTrialRow.created_at

        # Observatory friction-fix: optional IS metrics sort with NULLS LAST
        # so empty / no-trade trials do not pollute Top/Bottom lists (ADR-017).
        base_order = asc(order_col) if sort_dir == "asc" else desc(order_col)
        order_expr = nulls_last(base_order) if metric_sort else base_order
        stmt = select(ResearchTrialRow)
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(order_expr, desc(ResearchTrialRow.created_at)).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [self._map(row) for row in result.scalars().all()], total

    async def sum_k_by_instrument(self, instrument_id: str) -> int:
        stmt = select(func.coalesce(func.sum(ResearchTrialRow.k_contribution), 0)).where(
            ResearchTrialRow.instrument_id == instrument_id
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_by_instrument(
        self,
        instrument_id: str,
        *,
        limit: int = 50,
    ) -> list[ResearchTrial]:
        trials, _ = await self.list_trials(instrument_id=instrument_id, limit=limit, offset=0)
        return trials

    async def instrument_summary(self, instrument_id: str) -> dict[str, Any] | None:
        inst_stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        inst = (await self._session.execute(inst_stmt)).scalar_one_or_none()
        if inst is None:
            return None

        sharpe = self._metric_float("sharpeRatio")
        sortino = self._metric_float("sortinoRatio")
        max_dd = self._metric_float("maxDrawdownPct")

        agg_stmt = select(
            func.count().label("trials"),
            func.coalesce(func.sum(ResearchTrialRow.k_contribution), 0).label("k"),
            func.avg(sharpe).label("avg_sharpe"),
            func.avg(sortino).label("avg_sortino"),
            func.avg(max_dd).label("avg_max_dd"),
            func.max(sharpe).label("best_sharpe"),
            func.max(ResearchTrialRow.created_at).label("last_trial_at"),
        ).where(ResearchTrialRow.instrument_id == instrument_id)
        agg = (await self._session.execute(agg_stmt)).one()

        by_origin_stmt = (
            select(
                ResearchTrialRow.proposed_by,
                func.count().label("n"),
                func.coalesce(func.sum(ResearchTrialRow.k_contribution), 0).label("k"),
            )
            .where(ResearchTrialRow.instrument_id == instrument_id)
            .group_by(ResearchTrialRow.proposed_by)
        )
        proposed_by: dict[str, int] = {}
        for row in (await self._session.execute(by_origin_stmt)).all():
            proposed_by[str(row.proposed_by)] = int(row.n)

        return {
            "instrumentId": instrument_id,
            "symbol": inst.symbol,
            "name": inst.name,
            "trials": int(agg.trials or 0),
            "kConsumed": int(agg.k or 0),
            "avgSharpe": None if agg.avg_sharpe is None else float(agg.avg_sharpe),
            "avgSortino": None if agg.avg_sortino is None else float(agg.avg_sortino),
            "avgMaxDD": None if agg.avg_max_dd is None else float(agg.avg_max_dd),
            "bestSharpe": None if agg.best_sharpe is None else float(agg.best_sharpe),
            "lastTrialAt": None if agg.last_trial_at is None else agg.last_trial_at.isoformat(),
            "proposedBy": proposed_by,
        }

    async def laboratory_summary(self) -> dict[str, Any]:
        sharpe = self._metric_float("sharpeRatio")
        pf = self._metric_float("profitFactor")
        max_dd = self._metric_float("maxDrawdownPct")

        totals = (
            await self._session.execute(
                select(
                    func.count().label("trials"),
                    func.coalesce(func.sum(ResearchTrialRow.k_contribution), 0).label("k"),
                    func.count(func.distinct(ResearchTrialRow.instrument_id)).label("instruments"),
                    func.avg(sharpe).label("avg_sharpe"),
                    func.avg(pf).label("avg_pf"),
                    func.avg(max_dd).label("avg_max_dd"),
                    func.max(ResearchTrialRow.created_at).label("last_trial_at"),
                )
            )
        ).one()

        by_instrument_stmt = (
            select(
                ResearchTrialRow.instrument_id,
                InstrumentRow.symbol,
                func.count().label("trials"),
                func.coalesce(func.sum(ResearchTrialRow.k_contribution), 0).label("k"),
                func.avg(sharpe).label("avg_sharpe"),
            )
            .join(InstrumentRow, InstrumentRow.id == ResearchTrialRow.instrument_id)
            .group_by(ResearchTrialRow.instrument_id, InstrumentRow.symbol)
            .order_by(desc("trials"))
            .limit(20)
        )
        by_instrument = [
            {
                "instrumentId": row.instrument_id,
                "symbol": row.symbol,
                "trials": int(row.trials),
                "kConsumed": int(row.k),
                "avgSharpe": None if row.avg_sharpe is None else float(row.avg_sharpe),
            }
            for row in (await self._session.execute(by_instrument_stmt)).all()
        ]

        by_preset_stmt = (
            select(
                ResearchTrialRow.preset_key.label("preset"),
                func.count().label("trials"),
                func.coalesce(func.sum(ResearchTrialRow.k_contribution), 0).label("k"),
            )
            .group_by(ResearchTrialRow.preset_key)
            .order_by(desc("trials"))
            .limit(20)
        )
        by_preset = [
            {
                "presetKey": row.preset or "unknown",
                "trials": int(row.trials),
                "kConsumed": int(row.k),
            }
            for row in (await self._session.execute(by_preset_stmt)).all()
        ]

        by_origin_stmt = (
            select(
                ResearchTrialRow.proposed_by,
                func.count().label("trials"),
                func.coalesce(func.sum(ResearchTrialRow.k_contribution), 0).label("k"),
            )
            .group_by(ResearchTrialRow.proposed_by)
            .order_by(desc("trials"))
        )
        by_origin = [
            {
                "proposedBy": row.proposed_by,
                "trials": int(row.trials),
                "kConsumed": int(row.k),
            }
            for row in (await self._session.execute(by_origin_stmt)).all()
        ]

        return {
            "totalTrials": int(totals.trials or 0),
            "totalK": int(totals.k or 0),
            "activeInstruments": int(totals.instruments or 0),
            "avgSharpe": None if totals.avg_sharpe is None else float(totals.avg_sharpe),
            "avgProfitFactor": None if totals.avg_pf is None else float(totals.avg_pf),
            "avgMaxDD": None if totals.avg_max_dd is None else float(totals.avg_max_dd),
            "lastTrialAt": None
            if totals.last_trial_at is None
            else totals.last_trial_at.isoformat(),
            "byInstrument": by_instrument,
            "byPreset": by_preset,
            "byOrigin": by_origin,
        }

    def _metric_present(self, key: str) -> ColumnElement[bool]:
        raw = ResearchTrialRow.is_metrics[key].as_string()
        return and_(raw.isnot(None), raw != "null", raw != "")

    async def lab_health(self) -> dict[str, Any]:
        """Q0.1 aggregates: metric coverage, zero-trades, campaigns, instrument coverage."""
        total = int(
            (await self._session.execute(select(func.count()).select_from(ResearchTrialRow))).scalar_one()
        )

        def _pct(n: int) -> float:
            return 0.0 if total == 0 else round(100.0 * n / total, 2)

        sharpe_n = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(ResearchTrialRow).where(
                        self._metric_present("sharpeRatio")
                    )
                )
            ).scalar_one()
        )
        sortino_n = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(ResearchTrialRow).where(
                        self._metric_present("sortinoRatio")
                    )
                )
            ).scalar_one()
        )
        calmar_n = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(ResearchTrialRow).where(
                        self._metric_present("calmarRatio")
                    )
                )
            ).scalar_one()
        )

        trade_count = cast(ResearchTrialRow.is_metrics["tradeCount"].as_string(), Float)
        zero_n = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(ResearchTrialRow).where(trade_count == 0.0)
                )
            ).scalar_one()
        )

        campaign_expr = func.coalesce(
            ResearchTrialRow.params["campaign"].as_string(),
            ResearchTrialRow.manifest_ref["campaign"].as_string(),
        )
        campaign_rows = (
            await self._session.execute(
                select(campaign_expr.label("campaign"), func.count().label("trials"))
                .where(
                    and_(
                        campaign_expr.isnot(None),
                        campaign_expr != "null",
                        campaign_expr != "",
                    )
                )
                .group_by(campaign_expr)
                .order_by(desc("trials"))
                .limit(40)
            )
        ).all()
        campaigns = [
            {"campaignId": str(row.campaign), "trials": int(row.trials)}
            for row in campaign_rows
        ]

        instruments_with_trials = int(
            (
                await self._session.execute(
                    select(func.count(func.distinct(ResearchTrialRow.instrument_id)))
                )
            ).scalar_one()
        )
        active_instruments = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(InstrumentRow)
                    .where(InstrumentRow.is_active.is_(True))
                )
            ).scalar_one()
        )

        return {
            "totalTrials": total,
            "coverage": {
                "sharpeRatio": {"present": sharpe_n, "pct": _pct(sharpe_n)},
                "sortinoRatio": {"present": sortino_n, "pct": _pct(sortino_n)},
                "calmarRatio": {"present": calmar_n, "pct": _pct(calmar_n)},
            },
            "zeroTradeCount": zero_n,
            "zeroTradePct": _pct(zero_n),
            "campaigns": campaigns,
            "campaignCount": len(campaigns),
            "instrumentsWithTrials": instruments_with_trials,
            "activeInstruments": active_instruments,
            "instrumentsWithoutTrials": max(0, active_instruments - instruments_with_trials),
            "caveat": (
                "Sharpe mediano cross-family ≠ verdad científica; "
                "revisar tradeCount y Calmar (Q0.4)."
            ),
        }
