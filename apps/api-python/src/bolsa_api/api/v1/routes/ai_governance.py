"""AI Governance (RFC-007) + Effectiveness / cognitive persist (RFC-008 D7+).

No hot path EXECUTION.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from bolsa_ai import get_default_proxy
from bolsa_analytics.cognitive import (
    BehaviorTradeSample,
    DeclaredInvestorProfile,
    StatisticalSuiteResult,
    TrialsLog,
    build_edge_report,
    build_effectiveness_summary,
    build_memory_entry,
    observe_investor_profile,
)
from bolsa_application.cognitive_persistence import (
    LoadEffectivenessFromStore,
    PersistDecisionMemory,
    PersistEdgeReport,
    PersistTrial,
)
from bolsa_infrastructure.database.repositories.cognitive_repository import (
    SqlAlchemyCognitiveRepository,
)
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import get_db_session

router = APIRouter()


class AiGovernanceStatusDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    preferred_provider: str = Field(alias="preferredProvider")
    ollama_available: bool = Field(alias="ollamaAvailable")
    openai_available: bool = Field(alias="openaiAvailable")
    calls_recorded: int = Field(alias="callsRecorded")
    mode: str
    audit_sink: str = Field(alias="auditSink")
    producer_version: str = Field(alias="producerVersion")


class AiGovernanceStatusResponseDto(BaseModel):
    data: AiGovernanceStatusDto


class AiEffectivenessResponseDto(BaseModel):
    data: dict[str, Any]


class AppendDecisionMemoryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    decision_id: str = Field(alias="decisionId")
    instrument_id: str = Field(alias="instrumentId")
    outcome: Literal["accepted", "rejected", "deferred"]
    reasons: list[str] = Field(default_factory=list)
    policy_rule_ids: list[str] = Field(default_factory=list, alias="policyRuleIds")
    reevaluate_when: list[str] = Field(default_factory=list, alias="reevaluateWhen")
    opportunity_intact: bool = Field(default=True, alias="opportunityIntact")
    policy_id: str | None = Field(default=None, alias="policyId")
    policy_version: str | None = Field(default=None, alias="policyVersion")
    account_id: str | None = Field(default=None, alias="accountId")


class AppendTrialRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    log_id: str = Field(alias="logId")
    strategy_family_ref: str = Field(alias="strategyFamilyRef")
    hypothesis_ref: str = Field(alias="hypothesisRef")
    params_hash: str = Field(alias="paramsHash")
    sharpe_is: float | None = Field(default=None, alias="sharpeIs")
    notes: str | None = None
    account_id: str | None = Field(default=None, alias="accountId")


class AppendEdgeReportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    strategy_or_signal_ref: str = Field(alias="strategyOrSignalRef")
    trials_n: int = Field(alias="trialsN", ge=0)
    walk_forward_efficiency: float | None = Field(default=None, alias="walkForwardEfficiency")
    monte_carlo_p_value: float | None = Field(default=None, alias="monteCarloPValue")
    psr: float | None = None
    dsr: float | None = None
    bootstrap_alpha_ci_lower: float | None = Field(default=None, alias="bootstrapAlphaCiLower")
    bootstrap_alpha_ci_upper: float | None = Field(default=None, alias="bootstrapAlphaCiUpper")
    stress_survival_rate: float | None = Field(default=None, alias="stressSurvivalRate")
    account_id: str | None = Field(default=None, alias="accountId")
    notes: list[str] = Field(default_factory=list)


@router.get("/ai/status", response_model=AiGovernanceStatusResponseDto)
async def ai_governance_status() -> AiGovernanceStatusResponseDto:
    status = get_default_proxy().get_status()
    return AiGovernanceStatusResponseDto(
        data=AiGovernanceStatusDto(
            preferred_provider=str(status["preferredProvider"]),
            ollama_available=bool(status["ollamaAvailable"]),
            openai_available=bool(status["openaiAvailable"]),
            calls_recorded=int(status["callsRecorded"]),
            mode=str(status["mode"]),
            audit_sink=str(status["auditSink"]),
            producer_version=str(status["producerVersion"]),
        ),
    )


def _demo_effectiveness() -> dict[str, Any]:
    log = TrialsLog(strategy_family_ref="demo-swing")
    for i in range(12):
        log.record(f"hyp-{i}", f"hash-{i}", sharpe_is=0.8 + i * 0.01)
    suite = StatisticalSuiteResult(
        trials_n=log.trials_n,
        walk_forward_efficiency=0.92,
        monte_carlo_p_value=0.01,
        psr=0.95,
        dsr=0.9,
        bootstrap_alpha_ci_lower=0.02,
        bootstrap_alpha_ci_upper=0.1,
        stress_survival_rate=0.9,
    )
    edge = build_edge_report("demo-swing-v1", suite, notes=("demo D7",))
    mem = [
        build_memory_entry(
            decision_id="DEC-demo1",
            instrument_id="AAPL",
            outcome="accepted",
            reasons=["Policy PASS"],
        ),
        build_memory_entry(
            decision_id="DEC-demo2",
            instrument_id="MSFT",
            outcome="rejected",
            reasons=["EarningsBlackout"],
            policy_rule_ids=["EarningsBlackout"],
            reevaluate_when=["earnings_window_closed"],
        ),
    ]
    declared = DeclaredInvestorProfile(
        horizon="swing",
        objectives=("growth",),
        risk_tolerance="moderate",
        experience="intermediate",
        max_acceptable_loss_pct=1.0,
    )
    observed = observe_investor_profile(
        declared,
        [
            BehaviorTradeSample("buy", 48, 0.8, True),
            BehaviorTradeSample("buy", 2, 2.5, False, impulsivity_flag=True),
            BehaviorTradeSample("sell", 72, 0.9, True),
        ],
    )
    data = build_effectiveness_summary(
        edge_report=edge,
        trials_log=log,
        memory_entries=mem,
        observed=observed,
        status="demo",
    ).to_dict()
    data["source"] = "demo"
    return data


@router.get("/ai/effectiveness", response_model=AiEffectivenessResponseDto)
async def ai_effectiveness(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    demo: bool = Query(False, description="Forzar resumen ilustrativo"),
    account_id: str | None = Query(None, alias="accountId"),
) -> AiEffectivenessResponseDto:
    if demo:
        return AiEffectivenessResponseDto(data=_demo_effectiveness())
    from bolsa_api.api.dependencies import get_investor_profile_repository

    store = SqlAlchemyCognitiveRepository(session)
    profile_store = get_investor_profile_repository(session)
    try:
        data = await LoadEffectivenessFromStore(store, profile_store).execute(
            account_id=account_id,
            refresh_observed=True,
        )
    except Exception as exc:  # noqa: BLE001 — tablas no migradas / DB caída → fallback UI
        data = build_effectiveness_summary(status="insufficient_data").to_dict()
        data["source"] = "postgres_unavailable"
        data["notes"] = [*data.get("notes", []), f"PG: {exc.__class__.__name__}: {exc}"]
    return AiEffectivenessResponseDto(data=data)


@router.post("/ai/decision-memory", response_model=AiEffectivenessResponseDto)
async def append_decision_memory(
    body: AppendDecisionMemoryRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiEffectivenessResponseDto:
    store = SqlAlchemyCognitiveRepository(session)
    rec = await PersistDecisionMemory(store).execute(
        decision_id=body.decision_id,
        instrument_id=body.instrument_id,
        outcome=body.outcome,
        reasons=body.reasons,
        policy_rule_ids=body.policy_rule_ids,
        reevaluate_when=body.reevaluate_when,
        opportunity_intact=body.opportunity_intact,
        policy_id=body.policy_id,
        policy_version=body.policy_version,
        account_id=body.account_id,
    )
    return AiEffectivenessResponseDto(
        data={"id": rec.id, "outcome": rec.outcome, "decisionId": rec.decision_id}
    )


class CloseSessionOutcomeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: Literal["auto", "manual"] = "auto"
    verdict: Literal["hit", "miss", "neutral", "invalid", "skipped"] | None = None
    return_pct: float | None = Field(default=None, alias="returnPct")
    price_at_eval: float | None = Field(default=None, alias="priceAtEval")
    notes: str | None = None
    force: bool = False


@router.get("/ai/decision-sessions")
async def list_decision_sessions(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Query(alias="accountId")] = None,
    instrument_id: Annotated[str | None, Query(alias="instrumentId")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 40,
) -> dict[str, Any]:
    store = SqlAlchemyCognitiveRepository(session)
    rows = await store.list_decision_sessions(
        limit=limit,
        account_id=account_id,
        instrument_id=instrument_id,
    )
    return {
        "data": [
            {
                "sessionId": r.id,
                "kind": r.kind,
                "status": r.status,
                "instrumentId": r.instrument_id,
                "symbol": r.symbol,
                "accountId": r.account_id,
                "recommendationId": r.recommendation_id,
                "decisionId": r.decision_id,
                "createdAt": r.created_at,
            }
            for r in rows
        ]
    }


@router.get("/ai/decision-sessions/learning-summary")
async def decision_session_learning_summary(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Query(alias="accountId")] = None,
    instrument_id: Annotated[str | None, Query(alias="instrumentId")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> dict[str, Any]:
    """Hit-rate agregado de Outcomes (no ajusta WeightRules). Debe ir antes de /{session_id}."""
    from bolsa_application.close_decision_session_outcome import LoadSessionLearningSummary

    store = SqlAlchemyCognitiveRepository(session)
    data = await LoadSessionLearningSummary(store).execute(
        account_id=account_id,
        instrument_id=instrument_id,
        limit=limit,
    )
    return {"data": data}


@router.get("/ai/decision-sessions/{session_id}")
async def get_decision_session(
    session_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    store = SqlAlchemyCognitiveRepository(session)
    rec = await store.get_decision_session(session_id)
    if rec is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="DecisionSession no encontrada")
    return {"data": rec.payload or {"sessionId": rec.id, "kind": rec.kind, "status": rec.status}}


@router.get("/ai/decision-sessions/{session_id}/replay")
async def get_decision_session_replay(
    session_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Caja negra: timeline a partir de la fotografía DecisionSession (sin re-ejecutar)."""
    from bolsa_analytics.cognitive import build_decision_replay
    from fastapi import HTTPException

    store = SqlAlchemyCognitiveRepository(session)
    rec = await store.get_decision_session(session_id)
    if rec is None or not rec.payload:
        raise HTTPException(status_code=404, detail="DecisionSession no encontrada")
    replay = build_decision_replay(rec.payload)
    return {"data": replay.to_dict()}


@router.post("/ai/decision-sessions/{session_id}/outcome")
async def close_decision_session_outcome(
    session_id: str,
    body: CloseSessionOutcomeRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Cierra DecisionSession con Outcome (Learning). auto_mark = close D1 +N horizonte."""
    from bolsa_application.close_decision_session_outcome import CloseDecisionSessionOutcome
    from fastapi import HTTPException

    from bolsa_api.api.dependencies import get_ohlcv_repository

    store = SqlAlchemyCognitiveRepository(session)
    use_case = CloseDecisionSessionOutcome(store, ohlcv=get_ohlcv_repository(session))
    try:
        payload = await use_case.execute(
            session_id,
            mode=body.mode,
            verdict=body.verdict,
            return_pct=body.return_pct,
            price_at_eval=body.price_at_eval,
            notes=body.notes,
            force=body.force,
        )
    except ValueError as exc:
        msg = str(exc)
        code = 404 if "no encontrada" in msg.lower() else 400
        raise HTTPException(status_code=code, detail=msg) from exc
    return {"data": payload}


@router.post("/ai/trials", response_model=AiEffectivenessResponseDto)
async def append_trial(
    body: AppendTrialRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiEffectivenessResponseDto:
    store = SqlAlchemyCognitiveRepository(session)
    rec = await PersistTrial(store).execute(
        log_id=body.log_id,
        strategy_family_ref=body.strategy_family_ref,
        hypothesis_ref=body.hypothesis_ref,
        params_hash=body.params_hash,
        sharpe_is=body.sharpe_is,
        notes=body.notes,
        account_id=body.account_id,
    )
    return AiEffectivenessResponseDto(
        data={"id": rec.id, "logId": rec.log_id, "strategyFamilyRef": rec.strategy_family_ref}
    )


@router.post("/ai/edge-reports", response_model=AiEffectivenessResponseDto)
async def append_edge_report(
    body: AppendEdgeReportRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiEffectivenessResponseDto:
    store = SqlAlchemyCognitiveRepository(session)
    suite = StatisticalSuiteResult(
        trials_n=body.trials_n,
        walk_forward_efficiency=body.walk_forward_efficiency,
        monte_carlo_p_value=body.monte_carlo_p_value,
        psr=body.psr,
        dsr=body.dsr,
        bootstrap_alpha_ci_lower=body.bootstrap_alpha_ci_lower,
        bootstrap_alpha_ci_upper=body.bootstrap_alpha_ci_upper,
        stress_survival_rate=body.stress_survival_rate,
    )
    rec = await PersistEdgeReport(store).execute(
        strategy_or_signal_ref=body.strategy_or_signal_ref,
        suite=suite,
        notes=tuple(body.notes),
        account_id=body.account_id,
    )
    return AiEffectivenessResponseDto(
        data={
            "id": rec.id,
            "band": rec.band,
            "credibility": rec.credibility,
            "strategyOrSignalRef": rec.strategy_or_signal_ref,
        }
    )


class ProposeRecommendationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    symbol: str | None = None
    account_id: str | None = Field(default=None, alias="accountId")
    suggested_quantity: float = Field(alias="suggestedQuantity", gt=0)
    suggested_price: float | None = Field(default=None, alias="suggestedPrice")
    action: Literal["recommend_long", "recommend_short", "wait"] | None = None
    include_fundamentals: bool = Field(default=True, alias="includeFundamentals")
    include_macro: bool = Field(default=True, alias="includeMacro")
    include_evidence: bool = Field(default=True, alias="includeEvidence")
    include_news: bool = Field(default=True, alias="includeNews")
    include_predictions: bool = Field(default=True, alias="includePredictions")
    strategy_or_signal_ref: str | None = Field(default=None, alias="strategyOrSignalRef")
    horizon: Literal["intraday", "swing", "position", "long_term"] = "swing"
    macro: dict[str, Any] | None = None


class _EdgeReportAdapter:
    def __init__(self, store: Any) -> None:
        self._store = store

    async def latest_edge_report(
        self,
        *,
        strategy_or_signal_ref: str | None = None,
        account_id: str | None = None,
    ) -> Any:
        from bolsa_application.cognitive_persistence import record_to_edge_report

        rec = await self._store.latest_edge_report(
            strategy_or_signal_ref=strategy_or_signal_ref,
            account_id=account_id,
        )
        if rec is None and strategy_or_signal_ref and account_id:
            # Fallback: último del account si no hay match por estrategia
            rec = await self._store.latest_edge_report(account_id=account_id)
        if rec is None:
            return None
        return record_to_edge_report(rec)


@router.post("/ai/recommendations/propose")
async def propose_recommendation(
    body: ProposeRecommendationRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """F3 — OHLCV → Assessments → DecisionRuntime → Recommendation."""
    from bolsa_application.propose_recommendation import ProposeRecommendationFromTa

    from bolsa_api.api.dependencies import (
        get_cognitive_repository,
        get_feature_port,
        get_instrument_repository,
        get_investor_profile_repository,
        get_ohlcv_repository,
        get_prediction_repository,
    )

    profile_ref = None
    policy_version = None
    if body.account_id:
        profile_store = get_investor_profile_repository(session)
        profile = await profile_store.get_for_account(body.account_id)
        if profile is not None:
            profile_ref = profile.id
            policy_version = profile.selected_policy_template_id

    instruments = get_instrument_repository(session)
    cognitive = get_cognitive_repository(session)
    from bolsa_application.shared_event_calendar import get_shared_market_event_calendar
    from bolsa_market.macro_snapshot import YahooMacroSnapshotPort
    from bolsa_market.news_snapshot import YahooNewsEventPort

    calendar = get_shared_market_event_calendar()
    use_case = ProposeRecommendationFromTa(
        get_ohlcv_repository(session),
        get_feature_port(),
        instruments,
        fundamentals=instruments,
        macro_port=YahooMacroSnapshotPort() if body.include_macro and body.macro is None else None,
        edge_reports=_EdgeReportAdapter(cognitive),
        event_calendar=calendar,
        news_port=YahooNewsEventPort(calendar) if body.include_news else None,
        cognitive_store=cognitive,
        prediction_store=get_prediction_repository(session),
    )
    try:
        result = await use_case.execute(
            instrument_id=body.instrument_id,
            suggested_quantity=body.suggested_quantity,
            suggested_price=body.suggested_price,
            account_id=body.account_id,
            symbol=body.symbol,
            action_override=body.action,
            profile_snapshot_ref=profile_ref,
            policy_version=policy_version,
            include_fundamentals=body.include_fundamentals,
            include_macro=body.include_macro,
            include_evidence=body.include_evidence,
            include_news=body.include_news,
            include_predictions=body.include_predictions,
            strategy_or_signal_ref=body.strategy_or_signal_ref,
            horizon=body.horizon,
            macro=body.macro,
        )
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": result.to_dict()}


class ConfirmIntentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recommendation: dict[str, Any]
    account_id: str = Field(alias="accountId")
    execute: bool = False
    session_id: str | None = Field(default=None, alias="sessionId")


@router.post("/ai/intents/confirm")
async def confirm_intent(
    body: ConfirmIntentRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """F3 — humano confirma Recommendation → OrderIntent (+ opcional ExecuteTrade) + Session."""
    from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent

    from bolsa_api.api.dependencies import get_cognitive_repository, get_execute_trade_use_case

    use_case = ConfirmRecommendationIntent(
        cognitive_store=get_cognitive_repository(session),
        execute_trade=get_execute_trade_use_case(session) if body.execute else None,
    )
    result = await use_case.execute(
        recommendation_raw=body.recommendation,
        account_id=body.account_id,
        execute=body.execute,
        session_id=body.session_id,
    )
    return {"data": result}


class BacktestCoachAnalyzeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    context: str
    battery: str
    local_summary: str = Field(default="", alias="localSummary")
    facts: dict[str, Any] | None = None
    """narrate = coach narrador+auditor; adversary = auditor C (solo findings tipados)."""
    mode: str = "narrate"


@router.post("/ai/backtest-coach/analyze")
async def analyze_backtest_coach(body: BacktestCoachAnalyzeRequest) -> dict[str, Any]:
    """
    Coach profundo de batería de backtests (AT + perfil/TF).
    Proxy First: LLM estructurado; si no hay provider → engine=heuristic y payload vacío
    (el cliente usa su coach local).
    mode=adversary → prompt adversario C (vetos tipados, temperature baja).
    """
    import json

    facts_json = json.dumps(body.facts, ensure_ascii=False) if body.facts else "{}"
    prompt_id = (
        "prompt_backtest_coach_adversary_v1"
        if (body.mode or "narrate").strip().lower() == "adversary"
        else "prompt_backtest_coach_v1"
    )
    proxy = get_default_proxy()
    completion = proxy.complete_structured(
        prompt_template_id=prompt_id,
        variables={
            "context": body.context,
            "battery": body.battery,
            "local_summary": body.local_summary,
            "facts": facts_json,
        },
    )
    if completion is None:
        return {
            "data": {
                "engine": "heuristic",
                "payload": None,
                "provider": None,
                "model": None,
            }
        }
    return {
        "data": {
            "engine": f"{completion.provider}_structured_v1",
            "payload": completion.payload,
            "provider": completion.provider,
            "model": completion.model_name,
        }
    }


class FundamentalExplainRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    instrument_id: str = Field(alias="instrumentId", min_length=1)


@router.post("/ai/fundamentals/explain")
async def explain_instrument_fundamentals(
    body: FundamentalExplainRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    F1b — copiloto FA. Solo interpreta FundamentalCardDto ya calculado.
    Proxy First; si Ollama no responde → engine=heuristic (prosa desde facts).
    """
    from bolsa_application.explain_instrument_fundamentals import ExplainInstrumentFundamentals
    from fastapi import HTTPException

    from bolsa_api.api.dependencies import get_instrument_fundamentals_use_case

    use_case = ExplainInstrumentFundamentals(get_instrument_fundamentals_use_case(session))
    result = await use_case.execute(body.instrument_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return {"data": result}


class DiaDSessionEvidenceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    mode: str
    symbol: str
    strategy_label: str = Field(alias="strategyLabel")
    dia_d: str = Field(alias="diaD")
    end_date: str = Field(alias="endDate")
    initial_cash: float = Field(default=10_000, alias="initialCash")
    auto: dict[str, Any]
    gated: dict[str, Any]
    gate: dict[str, Any]


@router.post("/ai/dia-d/session-evidence")
async def explain_dia_d_session_evidence(body: DiaDSessionEvidenceRequest) -> dict[str, Any]:
    """
    Informe Evidence sesión C (DÍA D). Solo interpreta métricas ya calculadas.
    No FA ni Coach. Proxy First; sin LLM → engine=heuristic.
    """
    from bolsa_application.explain_dia_d_session_evidence import ExplainDiaDSessionEvidence

    result = await ExplainDiaDSessionEvidence().execute(body.model_dump(by_alias=True))
    return {"data": result}


class CoreRReviewEvidenceRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    verdict: str
    reason: str = ""


class CoreRReviewEvidenceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    list_id: str = Field(alias="listId")
    timeframe: str = "1d"
    rows: list[CoreRReviewEvidenceRow]


@router.post("/ai/core-r/review-evidence")
async def explain_core_r_review_evidence(body: CoreRReviewEvidenceRequest) -> dict[str, Any]:
    """
    Informe Evidence cola CORE-R. Solo interpreta veredictos ya calculados.
    No FA ni Coach ni pisa TOP. Proxy First; sin LLM → engine=heuristic.
    """
    from bolsa_application.explain_core_r_review import ExplainCoreRReviewEvidence

    result = await ExplainCoreRReviewEvidence().execute(body.model_dump(by_alias=True))
    return {"data": result}


class FilingSummarizeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    filing_id: str = Field(alias="filingId")


@router.post("/ai/fundamentals/filings/summarize")
async def summarize_instrument_filing(
    body: FilingSummarizeRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    F2b — resumen narrativo de un filing subido.
    No recalcula ratios ni escribe profile_snapshot.fundamentals.
    """
    from bolsa_application.instrument_filings import SummarizeInstrumentFiling
    from fastapi import HTTPException

    from bolsa_api.api.dependencies import get_instrument_repository

    result = await SummarizeInstrumentFiling(get_instrument_repository(session)).execute(
        body.instrument_id,
        body.filing_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument or filing not found")
    return {"data": result}


class FilingAskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    filing_id: str = Field(alias="filingId")
    question: str = Field(min_length=1, max_length=800)
    top_k: int | None = Field(default=None, alias="topK", ge=1, le=8)


@router.post("/ai/fundamentals/filings/ask")
async def ask_instrument_filing(
    body: FilingAskRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    F2b++ — Q&A con retrieval TF-IDF local sobre el extracto del filing.
    Sin vectores/Chroma. No altera Score_FUND.
    """
    from bolsa_application.instrument_filings import AskInstrumentFiling
    from fastapi import HTTPException

    from bolsa_api.api.dependencies import get_instrument_repository

    try:
        result = await AskInstrumentFiling(get_instrument_repository(session)).execute(
            body.instrument_id,
            body.filing_id,
            body.question,
            top_k=body.top_k or 4,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument or filing not found")
    return {"data": result}


