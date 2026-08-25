"""F3 — Propose: OHLCV → Assessment[] → DecisionRuntime → Recommendation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast

from bolsa_analytics.cognitive.edge_report import EdgeReport
from bolsa_analytics.cognitive.exit_radar import (
    EXIT_RADAR_KEY,
    build_exit_radar_dict,
)
from bolsa_analytics.cognitive.expectancy import (
    EXPECTANCY_KEY,
    build_expectancy_dict,
)
from bolsa_analytics.cognitive.macro_inputs import MacroInputs
from bolsa_analytics.cognitive.mfe_mae import (
    MFE_MAE_KEY,
    build_mfe_mae_dict,
)
from bolsa_analytics.cognitive.protect_plan import (
    PROTECT_PLAN_KEY,
    build_protect_plan_dict,
)
from bolsa_analytics.cognitive.recommendation import (
    Recommendation,
    recommendation_from_decision_package,
)
from bolsa_analytics.cognitive.thesis_health import (
    THESIS_HEALTH_KEY,
    build_thesis_health_dict,
)
from bolsa_analytics.cognitive.trade_plan import (
    WYCKOFF_SPRING_ANCHOR_KEY,
    build_v0_trade_plan_dict,
    parse_wyckoff_spring_anchor,
    snapshot_wyckoff_spring_anchor,
)
from bolsa_analytics.features.compute_bridge import materialize_feature_snapshot
from bolsa_analytics.features.online_adapter import OnlineFeatureAdapter
from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.knowledge.assessment import Assessment
from bolsa_analytics.knowledge.decision_package_ta import DecisionAction, DecisionPackageTa
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
from bolsa_domain.entities.market_event import MarketEventCalendar
from bolsa_domain.repositories.instrument_repository import InstrumentRepository
from bolsa_domain.value_objects.timeframe import TimeFrame

from bolsa_application.cognitive_persistence import decision_session_to_record
from bolsa_application.journal_writer import (
    append_journal_event,
    attribution_setup_payload,
)

# Overrides de acción que ProposeRecommendation acepta del cliente (subconjunto de DecisionAction).
_PROPOSE_OVERRIDE_OPTIONS = frozenset({"recommend_long", "recommend_short", "wait"})


def _risk_pct_for_policy(policy_version: str | None) -> float:
    """``max_risk_per_trade_pct`` de la plantilla; unknown → moderate."""
    from bolsa_analytics.cognitive.trading_policy_templates import get_policy_template

    key = (policy_version or "moderate").strip() or "moderate"
    try:
        return float(get_policy_template(key).risk.max_risk_per_trade_pct)
    except KeyError:
        return float(get_policy_template("moderate").risk.max_risk_per_trade_pct)


async def _wyckoff_prior_for_decision(
    store: Any | None,
    *,
    decision_id: str,
    instrument_id: str,
) -> dict[str, object] | None:
    """Ciclo 4.7: última sesión del mismo decision_id con anchor en runtime."""
    if store is None or not decision_id:
        return None
    list_fn = getattr(store, "list_decision_sessions", None)
    if list_fn is None:
        return None
    try:
        rows = await list_fn(limit=50, instrument_id=instrument_id)
    except Exception:  # noqa: BLE001 — propose no tumba por audit
        return None
    for row in rows:
        if getattr(row, "decision_id", None) != decision_id:
            continue
        payload = getattr(row, "payload", None)
        if not isinstance(payload, dict):
            continue
        runtime = payload.get("runtime")
        if not isinstance(runtime, dict):
            continue
        anchor = parse_wyckoff_spring_anchor(runtime.get(WYCKOFF_SPRING_ANCHOR_KEY))
        if anchor is not None:
            return anchor
    return None


class OhlcvBarsPort(Protocol):
    """Puerto (interfaz) Ohlcv Bars Port."""
    async def get_bars(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame,
        limit: int,
    ) -> list[Any]: ...


class FeaturePortLike(Protocol):
    """Puerto (interfaz) Feature Port Like."""
    def get_latest(self, instrument_id: str, feature_set_id: str) -> Any: ...


class InstrumentLookupPort(Protocol):
    """Puerto (interfaz) Instrument Lookup Port."""
    async def get_by_id(self, instrument_id: str) -> Any | None: ...


class FundamentalsPort(Protocol):
    """Puerto (interfaz) Fundamentals Port."""
    async def get_fundamentals(self, instrument_id: str) -> dict[str, Any] | None: ...


class MacroSnapshotPort(Protocol):
    """Puerto (interfaz) Macro Snapshot Port."""
    async def get_macro(self) -> dict[str, Any] | None: ...


class EdgeReportLookupPort(Protocol):
    """Puerto (interfaz) Edge Report Lookup Port."""
    async def latest_edge_report(
        self,
        *,
        strategy_or_signal_ref: str | None = None,
        account_id: str | None = None,
    ) -> EdgeReport | None: ...


class NewsEventRefreshPort(Protocol):
    """Puerto (interfaz) News Event Refresh Port."""
    async def refresh_for_symbol(self, yahoo_symbol: str) -> int: ...


@dataclass(frozen=True, slots=True)
class ProposeRecommendationResult:
    """Resultado de Propose Recommendation."""
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
    trade_plan: dict[str, Any] | None = None
    # Ciclo 4.8 — echo thin para F3/Hoy (no TradePlan / no contract:gen).
    wyckoff_spring_anchor: dict[str, Any] | None = None
    # Ciclo 5.0 — Thesis Health advisory (Golden F); no fill gate.
    thesis_health: dict[str, Any] | None = None
    # Ciclo 5.1 — Protect/T1 advisory (Golden E); no stop mutate.
    protect_plan: dict[str, Any] | None = None
    # Ciclo 5.2 — Exit Radar advisory; no auto-exit.
    exit_radar: dict[str, Any] | None = None
    # Ciclo 5.3 — MFE/MAE metrics advisory; no expectancy.
    mfe_mae: dict[str, Any] | None = None
    # Ciclo 8.0 — Expectancy thin advisory; ≠ permiso.
    expectancy: dict[str, Any] | None = None

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
        if self.trade_plan is not None:
            data["tradePlan"] = self.trade_plan
        if self.wyckoff_spring_anchor is not None:
            data[WYCKOFF_SPRING_ANCHOR_KEY] = self.wyckoff_spring_anchor
        if self.thesis_health is not None:
            data[THESIS_HEALTH_KEY] = self.thesis_health
        if self.protect_plan is not None:
            data[PROTECT_PLAN_KEY] = self.protect_plan
        if self.exit_radar is not None:
            data[EXIT_RADAR_KEY] = self.exit_radar
        if self.mfe_mae is not None:
            data[MFE_MAE_KEY] = self.mfe_mae
        if self.expectancy is not None:
            data[EXPECTANCY_KEY] = self.expectancy
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
        journal_writer: Any | None = None,
        portfolio_summary: Any | None = None,
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
        self._journal_writer = journal_writer
        self._portfolio_summary = portfolio_summary

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
        fundamental: FundamentalInputs | dict[str, Any] | None = None,
        include_fundamentals: bool = True,
        macro: MacroInputs | dict[str, Any] | None = None,
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
        resolved_country: str | None = None
        if self._instruments is not None:
            inst = await self._instruments.get_by_id(instrument_id)
            if inst is not None:
                if resolved_symbol is None:
                    resolved_symbol = getattr(inst, "symbol", None) or getattr(inst, "ticker", None)
                yahoo_symbol = getattr(inst, "yahoo_symbol", None) or resolved_symbol
                raw_country = getattr(inst, "country", None)
                if isinstance(raw_country, str) and raw_country.strip():
                    resolved_country = raw_country.strip().upper()[:2]
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
            cast(OnlineFeatureAdapter, self._feature_port),
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
        fund_in: FundamentalInputs | dict[str, Any] | None = fundamental
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

                        refreshed = await RefreshInstrumentFundamentals(
                            cast(InstrumentRepository, self._instruments)
                        ).execute(
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
        macro_in: MacroInputs | dict[str, Any] | None = macro
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

        override: DecisionAction | None = None
        if action_override in _PROPOSE_OVERRIDE_OPTIONS:
            override = cast(DecisionAction, action_override)

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
            country=resolved_country,
            status="awaiting_human",
            edge_report_ref=edge_ref,
        )
        wyckoff_prior = await _wyckoff_prior_for_decision(
            self._cognitive_store,
            decision_id=runtime.package.decision_id,
            instrument_id=instrument_id,
        )
        trade_plan_dict = build_v0_trade_plan_dict(
            decision_id=runtime.package.decision_id,
            instrument_id=instrument_id,
            action=str(runtime.package.action),
            compliance_check=runtime.package.compliance_check,
            entry=price,
            opportunity_score=runtime.combined_score,
            expires_at=rec.expires_at,
            expired=False,
            atr=inputs.atr,
            bars=ohlcv_bars,
            bias=assessment.bias,
            exhaustion=bool(assessment.exhaustion),
            equity=await self._equity_for_account(account_id),
            risk_pct=_risk_pct_for_policy(policy_version),
            market_regime=regime,
            wyckoff_prior=wyckoff_prior,
        )
        wyckoff_anchor = snapshot_wyckoff_spring_anchor(
            direction=(
                "long"
                if str(runtime.package.action) == "recommend_long"
                else "short"
                if str(runtime.package.action) == "recommend_short"
                else "none"
            ),
            bars=ohlcv_bars,
            atr=inputs.atr,
            prior=wyckoff_prior,
        )
        plan_direction = (
            "long"
            if str(runtime.package.action) == "recommend_long"
            else "short"
            if str(runtime.package.action) == "recommend_short"
            else "none"
        )
        structural_stop_raw = (
            trade_plan_dict.get("structuralStop")
            if isinstance(trade_plan_dict, dict)
            else None
        )
        try:
            structural_stop = (
                float(structural_stop_raw)
                if structural_stop_raw is not None
                else None
            )
        except (TypeError, ValueError):
            structural_stop = None
        thesis_health = build_thesis_health_dict(
            confidence=float(runtime.package.overall_confidence),
            direction=plan_direction,
            last_close=float(last_close) if last_close is not None else None,
            structural_stop=structural_stop,
            hard_exit=str(runtime.package.action) == "exit_hint",
        )
        entry_raw = (
            trade_plan_dict.get("entry") if isinstance(trade_plan_dict, dict) else None
        )
        try:
            entry_px = float(entry_raw) if entry_raw is not None else None
        except (TypeError, ValueError):
            entry_px = None
        protect_plan = build_protect_plan_dict(
            direction=plan_direction,
            entry=entry_px,
            structural_stop=structural_stop,
            last_close=float(last_close) if last_close is not None else None,
        )
        expires_raw = (
            trade_plan_dict.get("expiresAt") if isinstance(trade_plan_dict, dict) else None
        )
        expires_at = expires_raw if isinstance(expires_raw, str) else None
        exit_radar = build_exit_radar_dict(
            direction=plan_direction,
            entry=entry_px,
            structural_stop=structural_stop,
            last_close=float(last_close) if last_close is not None else None,
            expires_at=expires_at,
            thesis_hint=str(thesis_health.get("hint")) if isinstance(thesis_health, dict) else None,
            target1=protect_plan.get("target1") if isinstance(protect_plan, dict) else None,
            r_multiple=protect_plan.get("rMultiple") if isinstance(protect_plan, dict) else None,
        )
        mfe_mae = build_mfe_mae_dict(
            direction=plan_direction,
            entry=entry_px,
            structural_stop=structural_stop,
            last_close=float(last_close) if last_close is not None else None,
            bars=ohlcv_bars,
        )
        entry_setup_raw = (
            trade_plan_dict.get("entrySetup")
            if isinstance(trade_plan_dict, dict)
            else None
        )
        if not isinstance(entry_setup_raw, str):
            entry_setup_raw = (
                trade_plan_dict.get("entry_setup")
                if isinstance(trade_plan_dict, dict)
                else None
            )
        entry_setup = (
            entry_setup_raw.strip()
            if isinstance(entry_setup_raw, str) and entry_setup_raw.strip()
            else None
        )
        current_r_raw = mfe_mae.get("currentR") if isinstance(mfe_mae, dict) else None
        try:
            current_r = float(current_r_raw) if current_r_raw is not None else None
        except (TypeError, ValueError):
            current_r = None
        expectancy_samples: list[dict[str, Any]] = []
        if (
            entry_setup is not None
            and entry_setup != "none"
            and current_r is not None
        ):
            expectancy_samples.append(
                {"entrySetup": entry_setup, "rMultiple": current_r}
            )
        expectancy = build_expectancy_dict(
            samples=expectancy_samples,
            focus_setup=entry_setup,
            current_r=current_r,
        )

        present_types = {a.assessment_type for a in runtime.assessments}
        missing = [
            t
            for t in ("fundamental", "macro", "news")
            if t not in present_types
        ]
        from bolsa_analytics.cognitive.decision_session import build_propose_session

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

        session_runtime: dict[str, Any] = {
            "combinedScore": runtime.combined_score,
            "decisionPackage": runtime.package.to_dict(),
            "lastClose": last_close,
            "predictionsDoNotDecide": True,
            "tradePlan": trade_plan_dict,
            THESIS_HEALTH_KEY: thesis_health,
            PROTECT_PLAN_KEY: protect_plan,
            EXIT_RADAR_KEY: exit_radar,
            MFE_MAE_KEY: mfe_mae,
            EXPECTANCY_KEY: expectancy,
        }
        if wyckoff_anchor is not None:
            session_runtime[WYCKOFF_SPRING_ANCHOR_KEY] = wyckoff_anchor

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
            runtime=session_runtime,
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
                await append_journal_event(
                    self._journal_writer,
                    event_type="proposal_recorded",
                    decision_id=runtime.package.decision_id,
                    session_id=session.session_id,
                    account_id=account_id,
                    instrument_id=instrument_id,
                    payload=attribution_setup_payload(
                        trade_plan_dict if isinstance(trade_plan_dict, dict) else None,
                        anchor=wyckoff_anchor if isinstance(wyckoff_anchor, dict) else None,
                        base={"status": "open"},
                    ),
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
            trade_plan=trade_plan_dict,
            wyckoff_spring_anchor=wyckoff_anchor,
            thesis_health=thesis_health,
            protect_plan=protect_plan,
            exit_radar=exit_radar,
            mfe_mae=mfe_mae,
            expectancy=expectancy,
        )

    async def _equity_for_account(self, account_id: str | None) -> float:
        """Equity de cartera (mismo SoT que confirm). Fallo o sin cuenta → 0."""
        if not account_id or self._portfolio_summary is None:
            return 0.0
        try:
            summary = await self._portfolio_summary.execute(account_id=account_id)
        except Exception:  # noqa: BLE001 — propose no tumba por summary
            return 0.0
        try:
            return float(getattr(summary, "total_equity", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
