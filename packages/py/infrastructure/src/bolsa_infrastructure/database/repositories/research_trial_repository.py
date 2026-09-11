from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import Float, and_, asc, case, cast, desc, func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import ColumnElement

from bolsa_application.discovery_param_region import compose_granularity_key
from bolsa_domain.entities.research_trial import ResearchTrial
from bolsa_infrastructure.database.models import (
    InstrumentRow,
    ResearchEvidenceRow,
    ResearchTrialRow,
)
from bolsa_infrastructure.ids import new_id

ResearchTrialSort = Literal[
    "created_at",
    "sharpe",
    "pnl",
    "commission",
    "k_contribution",
]


def _normalized_region(value: Any) -> str | None:
    """V2.38 (incremento 3): normaliza la region de un trial agregado.

    ``None``/vacío ⇒ ``None`` (sin region: la clave compuesta colapsa a la familia).
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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
            param_region=row.param_region,
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
        param_region: str | None = None,
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
            param_region=param_region,
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

    async def latest_trial_at(self) -> str | None:
        """V2.36 (incremento 1): ``created_at`` del trial más reciente (o ``None``).

        Es el corte temporal *dato-dependiente* del snapshot de evidencia: usar el
        reloj haría que cada ejecución del job produjese un hash distinto sobre los
        mismos datos, rompiendo la idempotencia. Con el último trial como corte, dos
        ejecuciones sobre la misma evidencia comparten ``snapshot_hash``.
        """
        stmt = select(func.max(ResearchTrialRow.created_at))
        value = (await self._session.execute(stmt)).scalar()
        return None if value is None else value.isoformat()

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

    async def family_evidence_summary(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """V2.36 (incremento 1) + V2.37/P2-01: agrega la evidencia del LAB por familia H0.

        Devuelve, por ``preset_key`` (familia normalizada), un resumen determinista con
        el número de trials, el score medio/máximo, y —desde V2.37— la **cobertura
        completa** de métricas ya persistidas en ``is_metrics`` que la señal compuesta
        del snapshot necesita: Sharpe, profit factor y drawdown máximos medios. Las
        métricas ausentes se devuelven como ``None`` (nunca 0: un dato ausente no es un
        mal dato) y su cobertura se reporta en ``metricCoverage``.

        Orden canónico por ``preset_key`` ascendente para que el resultado sea
        reproducible con independencia del plan de ejecución de la BD. Solo lectura.
        """
        sharpe = self._metric_float("sharpeRatio")
        profit_factor = self._metric_float("profitFactor")
        max_dd = self._metric_float("maxDrawdownPct")
        trade_count = cast(ResearchTrialRow.is_metrics["tradeCount"].as_string(), Float)

        filters = []
        if date_from:
            filters.append(ResearchTrialRow.created_at >= datetime.fromisoformat(date_from))
        if date_to:
            filters.append(ResearchTrialRow.created_at <= datetime.fromisoformat(date_to))

        stmt = (
            select(
                ResearchTrialRow.preset_key.label("preset"),
                ResearchTrialRow.param_region.label("region"),
                func.count().label("trials"),
                func.coalesce(func.sum(ResearchTrialRow.k_contribution), 0).label("k"),
                func.avg(ResearchTrialRow.is_score).label("avg_score"),
                func.max(ResearchTrialRow.is_score).label("best_score"),
                func.avg(sharpe).label("avg_sharpe"),
                func.avg(profit_factor).label("avg_profit_factor"),
                func.avg(max_dd).label("avg_max_dd"),
                func.count(sharpe).label("sharpe_n"),
                func.count(profit_factor).label("profit_factor_n"),
                func.count(max_dd).label("max_dd_n"),
                func.sum(
                    case((and_(trade_count.isnot(None), trade_count == 0.0), 1), else_=0)
                ).label("zero_trade"),
                func.sum(
                    case(
                        (
                            and_(
                                ResearchTrialRow.fail_code.isnot(None),
                                ResearchTrialRow.fail_code != "",
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("failures"),
            )
            .where(ResearchTrialRow.preset_key.isnot(None))
            .group_by(ResearchTrialRow.preset_key, ResearchTrialRow.param_region)
            .order_by(asc(ResearchTrialRow.preset_key), asc(ResearchTrialRow.param_region))
        )
        if filters:
            stmt = stmt.where(*filters)

        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "presetKey": str(row.preset),
                # V2.38 (incremento 3): granularidad por region. ``None``/``""`` cuando
                # no hay region (flag OFF o trials historicos): la clave compuesta que
                # deriva el snapshot es entonces la propia familia (compatibilidad).
                "paramRegion": _normalized_region(row.region),
                "trials": int(row.trials or 0),
                "kConsumed": int(row.k or 0),
                "avgScore": None if row.avg_score is None else float(row.avg_score),
                "bestScore": None if row.best_score is None else float(row.best_score),
                "avgSharpe": None if row.avg_sharpe is None else float(row.avg_sharpe),
                "avgProfitFactor": None
                if row.avg_profit_factor is None
                else float(row.avg_profit_factor),
                "avgMaxDrawdownPct": None if row.avg_max_dd is None else float(row.avg_max_dd),
                "metricCoverage": {
                    "sharpeRatio": int(row.sharpe_n or 0),
                    "profitFactor": int(row.profit_factor_n or 0),
                    "maxDrawdownPct": int(row.max_dd_n or 0),
                },
                "zeroTrade": int(row.zero_trade or 0),
                "failures": int(row.failures or 0),
            }
            for row in rows
        ]

    async def posterior_evidence_summary(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        levels: tuple[str, ...] = ("A", "B", "C", "D"),
    ) -> dict[str, dict[str, float]]:
        """V2.37/P2-01: evidencia **posterior** por familia (shadow / paper forward).

        Agrega ``research_evidence`` por la familia H0 del trial asociado y por nivel
        ADR-012, devolviendo por familia la suma ponderada por nivel
        (``posteriorWeighted``), el número de evidencias (``posteriorCount``) y el
        desglose por nivel. El join con ``research_trials`` es el único modo de atar la
        evidencia posterior a una familia (``research_evidence`` no guarda ``preset_key``).

        Solo lectura y determinista (orden canónico). Fail-closed: familias sin evidencia
        posterior simplemente no aparecen (la señal compuesta las trata como cobertura
        ausente, no como 0).
        """
        level_weight = {"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.25}
        filters = []
        if date_from:
            filters.append(ResearchEvidenceRow.created_at >= datetime.fromisoformat(date_from))
        if date_to:
            filters.append(ResearchEvidenceRow.created_at <= datetime.fromisoformat(date_to))
        if levels:
            filters.append(ResearchEvidenceRow.level.in_(tuple(levels)))

        weighted = func.sum(
            ResearchEvidenceRow.evidence_weight
            * case(
                {level: weight for level, weight in level_weight.items()},
                value=ResearchEvidenceRow.level,
                else_=0.0,
            )
        ).label("weighted")
        stmt = (
            select(
                ResearchTrialRow.preset_key.label("preset"),
                ResearchTrialRow.param_region.label("region"),
                func.count().label("n"),
                weighted,
            )
            .join(ResearchTrialRow, ResearchTrialRow.id == ResearchEvidenceRow.trial_id)
            .where(ResearchTrialRow.preset_key.isnot(None))
            .group_by(ResearchTrialRow.preset_key, ResearchTrialRow.param_region)
            .order_by(asc(ResearchTrialRow.preset_key), asc(ResearchTrialRow.param_region))
        )
        if filters:
            stmt = stmt.where(*filters)

        rows = (await self._session.execute(stmt)).all()
        out: dict[str, dict[str, float]] = {}
        for row in rows:
            family = str(row.preset or "").strip()
            if not family:
                continue
            # V2.38 (incremento 3): clave compuesta canónica (familia o familia|region).
            key = compose_granularity_key(family, _normalized_region(row.region) or "")
            out[key] = {
                "posteriorWeighted": float(row.weighted or 0.0),
                "posteriorCount": float(row.n or 0),
            }
        return out

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
