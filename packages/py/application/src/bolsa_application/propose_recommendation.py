"""F3 — Propose: OHLCV → Assessment[] → DecisionRuntime → Recommendation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from bolsa_analytics.cognitive.edge_report import EdgeReport
from bolsa_analytics.cognitive.macro_inputs import MacroInputs
from bolsa_analytics.cognitive.market_events import MarketEventCalendar
from bolsa_analytics.cognitive.recommendation import (
    Recommendation,
    recommendation_from_decision_package,
)
from bolsa_analytics.features.compute_bridge import materialize_feature_snapshot
from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.knowledge.assessment import Assessment
from bolsa_analytics.knowledge.decision_package_ta import DecisionPackageTa
from bolsa_analytics.knowledge.decision_runtime import (
    DecisionRuntimeResult,
    run_decision_runtime,
)
from bolsa_analytics.knowledge.evidence_assessment import (
    EvidenceAssessment,
    build_evidence_assessment,
)
from bolsa_analytics.knowledge.fundamental_assessment import (
    FundamentalAssessment,
    build_fundamental_assessment,
)
from bolsa_analytics.knowledge.fundamental_inputs import FundamentalInputs
from bolsa_analytics.knowledge.macro_assessment import (
    MacroAssessment,
    build_macro_assessment,
)
from bolsa_analytics.knowledge.models import TechnicalInputs
from bolsa_analytics.knowledge.news_assessment import (
    NewsAssessment,
    build_news_assessment,
)
from bolsa_analytics.knowledge.technical_assessment import (
    TechnicalAssessment,
    build_technical_assessment,
)
from bolsa_domain.value_objects.timeframe import TimeFrame


class OhlcvBarsPort(Protocol):
    async def get_bars(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame,
        limit: int,
    ) -> list[Any]: ...


class FeaturePortLike(Protocol):
    def get_latest(self, instrument_id: str, feature_set_id: str) -> Any: ...


class InstrumentLookupPort(Protocol):
    async def get_by_id(self, instrument_id: str) -> Any | None: ...


class FundamentalsPort(Protocol):
    async def get_fundamentals(self, instrument_id: str) -> dict | None: ...


class MacroSnapshotPort(Protocol):
    async def get_macro(self) -> dict | None: ...


class EdgeReportLookupPort(Protocol):
    async def latest_edge_report(
        self,
        *,
        strategy_or_signal_ref: str | None = None,
        account_id: str | None = None,
    ) -> EdgeReport | None: ...


class NewsEventRefreshPort(Protocol):
    async def refresh_for_symbol(self, yahoo_symbol: str) -> int: ...


@dataclass(frozen=True, slots=True)
class ProposeRecommendationResult:
    recommendation: Recommendation
    package: DecisionPackageTa
    technical_assessment: TechnicalAssessment
    assessments: tuple[Assessment, ...]
    policy_gate: dict[str, Any] | None
    last_close: float | None
    source: str
    fundamental_assessment: FundamentalAssessment | None = None
    macro_assessment: MacroAssessment | None = None
    evidence_assessment: EvidenceAssessment | None = None
    news_assessment: NewsAssessment | None = None
    decision_session: dict[str, Any] | None = None
    combined_score: float | None = None
    weight_context: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = self.recommendation.to_dict()
        data["decisionPackage"] = self.package.to_dict()
        data["technicalAssessment"] = self.technical_assessment.to_dict()
        data["assessments"] = [a.to_assessment_dict() for a in self.assessments]
        if self.fundamental_assessment is not None:
            data["fundamentalAssessment"] = self.fundamental_assessment.to_dict()
        if self.macro_assessment is not None:
            data["macroAssessment"] = self.macro_assessment.to_dict()
        if self.evidence_assessment is not None:
            data["evidenceAssessment"] = self.evidence_assessment.to_dict()
        if self.news_assessment is not None:
            data["newsAssessment"] = self.news_assessment.to_dict()
        data["policyGate"] = self.policy_gate
        data["lastClose"] = self.last_close
        data["source"] = self.source
        if self.decision_session is not None:
            data["decisionSession"] = self.decision_session
        if self.combined_score is not None:
            data["combinedScore"] = self.combined_score
        if self.weight_context is not None:
            data["weightContext"] = self.weight_context
        return data


class ProposeRecommendationFromTa:
    """Pipeline F3: Assessments (colección) → Runtime decide; Gate no decide."""

    def __init__(
        self,
        ohlcv: OhlcvBarsPort,
        feature_port: FeaturePortLike,
        instruments: InstrumentLookupPort | None = None,
        fundamentals: FundamentalsPort | None = None,
        macro_port: MacroSnapshotPort | None = None,
        edge_reports: EdgeReportLookupPort | None = None,
        event_calendar: MarketEventCalendar | None = None,
        news_port: NewsEventRefreshPort | None = None,
        cognitive_store: Any | None = None,
        prediction_store: Any | None = None,
    ) -> None:
        self._ohlcv = ohlcv
        self._feature_port = feature_port
        self._instruments = instruments
        self._fundamentals = fundamentals
        self._macro_port = macro_port
        self._edge_reports = edge_reports
        self._event_calendar = event_calendar
        self._news_port = news_port
        self._cognitive_store = cognitive_store
        self._prediction_store = prediction_store

    async def execute(
        self,
        *,
        instrument_id: str,
        suggested_quantity: float,
        suggested_price: float | None = None,
        account_id: str | None = None,
        symbol: str | None = None,
        action_override: str | None = None,
        timeframe: str = "1d",
        bar_limit: int = 120,
        feature_set_id: str = "fset_core_v1",
        profile_snapshot_ref: str | None = None,
        policy_version: str | None = None,
        fundamental: FundamentalInputs | dict | None = None,
        include_fundamentals: bool = True,
        macro: MacroInputs | dict | None = None,
        include_macro: bool = True,
        include_evidence: bool = True,
        include_news: bool = True,
        include_predictions: bool = True,
        strategy_or_signal_ref: str | None = None,
        horizon: str = "swing",
    ) -> ProposeRecommendationResult:
        if suggested_quantity <= 0:
            raise ValueError("suggested_quantity debe ser > 0")

        resolved_symbol = symbol
        yahoo_symbol: str | None = None
        if self._instruments is not None:
            inst = await self._instruments.get_by_id(instrument_id)
            if inst is not None:
                if resolved_symbol is None:
                    resolved_symbol = getattr(inst, "symbol", None) or getattr(inst, "ticker", None)
                yahoo_symbol = getattr(inst, "yahoo_symbol", None) or resolved_symbol
        if yahoo_symbol is None:
            yahoo_symbol = resolved_symbol

        try:
            tf = TimeFrame(timeframe)
        except ValueError as exc:
            raise ValueError(f"timeframe inválido: {timeframe}") from exc

        bars = await self._ohlcv.get_bars(instrument_id, timeframe=tf, limit=bar_limit)
        if not bars:
            raise ValueError("Sin OHLCV para el instrumento — sincroniza datos antes de proponer")

        ohlcv_bars = [
            OhlcvBar(
                timestamp=bar.timestamp,
                open=float(bar.open),
                high=float(bar.high),
                low=float(bar.low),
                close=float(bar.close),
                volume=float(bar.volume or 0),
            )
            for bar in bars
        ]
        last_close = float(ohlcv_bars[-1].close)

        snap = materialize_feature_snapshot(
            self._feature_port,
            instrument_id=instrument_id,
            bars=ohlcv_bars,
            feature_set_id=feature_set_id,
        )
        if snap is None:
            raise ValueError("No se pudo materializar el FeatureSet")

        inputs = TechnicalInputs.from_feature_map(dict(snap.values))
        assessment, _, _ = build_technical_assessment(instrument_id, inputs)
        bag: list[Any] = [assessment]

        fund_assess: FundamentalAssessment | None = None
        fund_in: FundamentalInputs | dict | None = fundamental
        if fund_in is None and include_fundamentals and self._fundamentals is not None:
            raw = await self._fundamentals.get_fundamentals(instrument_id)
            from bolsa_analytics.signals.fundamental_gate import (
                fundamentals_need_refresh,
                fundamentals_thin_for_cognitive,
            )

            # Snapshot pobre (v1 PE/mcap) o caducado → refresh Yahoo best-effort
            if fundamentals_need_refresh(raw, 30) or fundamentals_thin_for_cognitive(raw):
                if self._instruments is not None:
                    try:
                        from bolsa_application.refresh_instrument_fundamentals import (
                            RefreshInstrumentFundamentals,
                        )

                        refreshed = await RefreshInstrumentFundamentals(self._instruments).execute(
                            instrument_id
                        )
                        if refreshed:
                            raw = refreshed
                    except Exception:  # noqa: BLE001 — propose no tumba por Yahoo
                        pass
            if raw:
                fund_in = FundamentalInputs.from_dict(raw)
        if fund_in is not None:
            parsed = (
                fund_in
                if isinstance(fund_in, FundamentalInputs)
                else FundamentalInputs.from_dict(fund_in)
            )
            if any(
                v is not None
                for v in (
                    parsed.market_cap,
                    parsed.trailing_pe,
                    parsed.forward_pe,
                    parsed.roe,
                    parsed.roic,
                    parsed.operating_margin,
                    parsed.revenue_growth,
                    parsed.eps_growth,
                    parsed.debt_to_equity,
                    parsed.current_ratio,
                    parsed.altman_z,
                )
            ):
                fund_assess, _, _ = build_fundamental_assessment(instrument_id, parsed)
                bag.append(fund_assess)

        macro_assess: MacroAssessment | None = None
        macro_in: MacroInputs | dict | None = macro
        if macro_in is None and include_macro and self._macro_port is not None:
            raw_m = await self._macro_port.get_macro()
            if raw_m:
                macro_in = MacroInputs.from_dict(raw_m)
        if macro_in is not None:
            parsed_m = (
                macro_in if isinstance(macro_in, MacroInputs) else MacroInputs.from_dict(macro_in)
            )
            if any(
                v is not None
                for v in (
                    parsed_m.vix,
                    parsed_m.yield_curve_10y2y_bps,
                    parsed_m.credit_spread_oas_bps,
                    parsed_m.breadth_pct_above_ma50,
                )
            ):
                macro_assess, _, _ = build_macro_assessment(instrument_id, parsed_m)
                bag.append(macro_assess)

        evidence_assess: EvidenceAssessment | None = None
        edge_ref: str | None = None
        if include_evidence and self._edge_reports is not None:
            report = await self._edge_reports.latest_edge_report(
                strategy_or_signal_ref=strategy_or_signal_ref,
                account_id=account_id,
            )
            if report is not None:
                evidence_assess = build_evidence_assessment(instrument_id, report)
                bag.append(evidence_assess)
                edge_ref = report.edge_report_id

        news_assess: NewsAssessment | None = None
        if include_news:
            if self._news_port is not None and yahoo_symbol:
                try:
                    await self._news_port.refresh_for_symbol(str(yahoo_symbol))
                except Exception:  # noqa: BLE001 — news best-effort
                    pass
            news_assess = build_news_assessment(
                instrument_id,
                calendar=self._event_calendar,
                symbol=resolved_symbol,
            )
            if news_assess.event_count > 0:
                bag.append(news_assess)

        override = None
        if action_override in {"recommend_long", "recommend_short", "wait"}:
            override = action_override  # type: ignore[assignment]

        hz = horizon if horizon in {"intraday", "swing", "position", "long_term"} else "swing"
        regime = "neutral"
        if macro_assess is not None:
            regime = macro_assess.regime

        runtime: DecisionRuntimeResult = run_decision_runtime(
            instrument_id=instrument_id,
            assessments=bag,
            horizon=hz,  # type: ignore[arg-type]
            regime=regime,  # type: ignore[arg-type]
            profile_snapshot_ref=profile_snapshot_ref,
            policy_version=policy_version,
            action_override=override,
            evaluate_policy_gate=False,
        )

        price = suggested_price if suggested_price is not None else last_close
        rec = recommendation_from_decision_package(
            runtime.package,
            suggested_quantity=suggested_quantity,
            suggested_price=price,
            account_id=account_id,
            symbol=resolved_symbol,
            status="awaiting_human",
            edge_report_ref=edge_ref,
        )

        present_types = {a.assessment_type for a in runtime.assessments}
        missing = [
            t
            for t in ("fundamental", "macro", "news")
            if t not in present_types
        ]
        from bolsa_analytics.cognitive.decision_session import build_propose_session

        from bolsa_application.cognitive_persistence import decision_session_to_record

        # Prediction: fotografía auxiliar — NUNCA entra en WeightRules / Runtime.
        prediction_dicts: list[dict[str, Any]] = []
        if include_predictions:
            try:
                from bolsa_analytics.prediction import PredictionService

                pred = PredictionService().predict(
                    instrument_id=instrument_id,
                    bars=ohlcv_bars,
                    snapshot=snap,
                    horizon="1d" if hz == "intraday" else "5d",
                )
                prediction_dicts.append(pred.to_dict())
                if self._prediction_store is not None:
                    from bolsa_application.prediction_persistence import PersistPredictionArtifacts

                    await PersistPredictionArtifacts(self._prediction_store).persist_prediction(
                        pred,
                        also_model=PredictionService().get_model(pred.model_id),
                    )
            except Exception:  # noqa: BLE001 — prediction best-effort
                pass

        session = build_propose_session(
            instrument_id=instrument_id,
            symbol=resolved_symbol,
            account_id=account_id,
            timeframe=timeframe,
            horizon=hz,
            market_regime=regime,
            profile_snapshot_ref=profile_snapshot_ref,
            policy_version=policy_version,
            weight_rules=runtime.weights,
            missing_assessments=missing,
            assessments=[a.to_assessment_dict() for a in runtime.assessments],
            evidence=None if evidence_assess is None else evidence_assess.to_dict(),
            predictions=prediction_dicts,
            runtime={
                "combinedScore": runtime.combined_score,
                "decisionPackage": runtime.package.to_dict(),
                "lastClose": last_close,
                "predictionsDoNotDecide": True,
            },
            recommendation=rec.to_dict(),
            policy_gate=runtime.policy_gate,
            lineage={
                "featureSetId": feature_set_id,
                "source": "decision_runtime_v1.1",
                "edgeReportRef": edge_ref,
                "predictionCount": len(prediction_dicts),
            },
            decision_id=runtime.package.decision_id,
        )
        session_dict = session.to_dict()
        if self._cognitive_store is not None:
            try:
                await self._cognitive_store.append_decision_session(
                    decision_session_to_record(session)
                )
            except Exception:  # noqa: BLE001 — propose no tumba por audit
                pass

        weight_ctx = None if session.weight_context is None else session.weight_context.to_dict()

        return ProposeRecommendationResult(
            recommendation=rec,
            package=runtime.package,
            technical_assessment=assessment,
            assessments=runtime.assessments,
            policy_gate=runtime.policy_gate,
            last_close=last_close,
            source="decision_runtime_v1.1",
            fundamental_assessment=fund_assess,
            macro_assessment=macro_assess,
            evidence_assessment=evidence_assess,
            news_assessment=news_assess,
            decision_session=session_dict,
            combined_score=runtime.combined_score,
            weight_context=weight_ctx,
        )
