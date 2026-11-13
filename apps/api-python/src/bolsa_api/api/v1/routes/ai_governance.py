"""AI Governance (RFC-007) + Effectiveness / cognitive persist (RFC-008 D7+).

No hot path EXECUTION.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_ai import get_default_proxy
from bolsa_ai.schemas import validate_adaptation_proposal_payload
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
from bolsa_api.api.dependencies import (
    get_cognitive_repository,
    get_db_session,
    require_account_access,
    require_owned_account_if_present,
    resolve_account_scope_or_default,
)
from bolsa_api.schemas.ai_governance import (
    AdaptationProposeRequest,
    AdaptationValidateRequest,
    AiEffectivenessResponseDto,
    AiGovernanceStatusDto,
    AiGovernanceStatusResponseDto,
    AppendDecisionMemoryRequest,
    AppendEdgeReportRequest,
    AppendTrialRequest,
    BacktestCoachAnalyzeRequest,
    CloseSessionOutcomeRequest,
    ConfirmIntentRequest,
    CoreRReviewEvidenceRequest,
    DecisionSessionSummaryDto,
    DiaDSessionEvidenceRequest,
    FilingAskRequest,
    FilingSummarizeRequest,
    FundamentalExplainRequest,
    ListDecisionSessionsResponseDto,
    ProposeRecommendationRequest,
)
from bolsa_application.adaptation_proposals import (
    ADAPTATION_PROMPT_ID,
    propose_adaptations,
)
from bolsa_application.adaptation_store import (
    adaptation_root,
    iter_adaptation_records,
    load_adaptation_record,
    merge_adaptation_record,
    save_adaptation_record,
)
from bolsa_application.adaptation_validation import (
    preregistration_hash,
    validate_adaptation_proposal,
)
from bolsa_application.cognitive_persistence import (
    LoadEffectivenessFromStore,
    PersistDecisionMemory,
    PersistEdgeReport,
    PersistTrial,
)

router = APIRouter()

#: Raíz por defecto del bucle de adaptación (``AI_ADAPTATION_DIR`` la sobreescribe).
#: ``routes`` → ``v1`` → ``api`` → ``bolsa_api`` → ``src`` → ``api-python`` → ``apps`` → raíz.
_DEFAULT_ADAPTATION_DIR = (
    Path(__file__).resolve().parents[7] / "operability_runs" / "ai-adaptation"
)


def _adaptation_dir() -> Path:
    return adaptation_root(_DEFAULT_ADAPTATION_DIR, os.environ)


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
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    demo: bool = Query(False, description="Forzar resumen ilustrativo"),
    account_id: str | None = Query(None, alias="accountId"),
) -> AiEffectivenessResponseDto:
    # V2.15.4 A1: un recurso ACCOUNT_SCOPED sin account_id NO es global; se acota
    # a la cuenta por defecto del principal. Sin cuenta propia activa -> fail-closed.
    scope = await resolve_account_scope_or_default(request, account_id)
    if demo:
        return AiEffectivenessResponseDto(data=_demo_effectiveness())
    if scope is None and account_id is None:
        return AiEffectivenessResponseDto(
            data=build_effectiveness_summary(status="insufficient_data").to_dict()
        )
    from bolsa_api.api.dependencies import get_investor_profile_repository

    store = get_cognitive_repository(session)
    profile_store = get_investor_profile_repository(session)
    try:
        data = await LoadEffectivenessFromStore(store, profile_store).execute(
            account_id=scope,
            refresh_observed=True,
        )
    except Exception as exc:  # noqa: BLE001 — tablas no migradas / DB caída → fallback UI
        data = build_effectiveness_summary(status="insufficient_data").to_dict()
        data["source"] = "postgres_unavailable"
        data["notes"] = [*data.get("notes", []), f"PG: {exc.__class__.__name__}: {exc}"]
    return AiEffectivenessResponseDto(data=data)


@router.post("/ai/decision-memory", response_model=AiEffectivenessResponseDto)
async def append_decision_memory(
    request: Request,
    body: AppendDecisionMemoryRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiEffectivenessResponseDto:
    # V2.15.4 A1 (deuda #1): escritura acount-less NO queda huérfana/global; se
    # atribuye a la cuenta por defecto del principal. Sin cuenta propia activa -> 400.
    scope = await resolve_account_scope_or_default(request, body.account_id)
    if scope is None:
        raise HTTPException(
            status_code=400,
            detail="Decision memory requiere una cuenta operativa del principal",
        )
    store = get_cognitive_repository(session)
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
        account_id=scope,
    )
    return AiEffectivenessResponseDto(
        data={"id": rec.id, "outcome": rec.outcome, "decisionId": rec.decision_id}
    )


@router.get("/ai/decision-sessions", response_model=ListDecisionSessionsResponseDto)
async def list_decision_sessions(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Query(alias="accountId")] = None,
    instrument_id: Annotated[str | None, Query(alias="instrumentId")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 40,
) -> ListDecisionSessionsResponseDto:
    # V2.15.4 A1: account-scoped; sin account_id se acota a la cuenta por defecto
    # del principal (nunca global). Sin cuenta propia activa → vacío (fail-closed).
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return ListDecisionSessionsResponseDto(data=[])
    store = get_cognitive_repository(session)
    rows = await store.list_decision_sessions(
        limit=limit,
        account_id=scope,
        instrument_id=instrument_id,
    )
    return ListDecisionSessionsResponseDto(
        data=[
            DecisionSessionSummaryDto(
                session_id=r.id,
                kind=r.kind,
                status=r.status,
                instrument_id=r.instrument_id,
                symbol=r.symbol,
                account_id=r.account_id,
                recommendation_id=r.recommendation_id,
                decision_id=r.decision_id,
                created_at=r.created_at,
            )
            for r in rows
        ]
    )


@router.get("/ai/decision-sessions/learning-summary", response_model=AiEffectivenessResponseDto)
async def decision_session_learning_summary(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Query(alias="accountId")] = None,
    instrument_id: Annotated[str | None, Query(alias="instrumentId")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> dict[str, Any]:
    """Hit-rate agregado de Outcomes (no ajusta WeightRules). Debe ir antes de /{session_id}."""
    # V2.15.4 A1: account-scoped; sin account_id se acota al default del principal.
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return {"data": None}
    from bolsa_application.close_decision_session_outcome import LoadSessionLearningSummary

    store = get_cognitive_repository(session)
    data = await LoadSessionLearningSummary(store).execute(
        account_id=scope,
        instrument_id=instrument_id,
        limit=limit,
    )
    return {"data": data}


@router.get("/ai/decision-sessions/{session_id}", response_model=AiEffectivenessResponseDto)
async def get_decision_session(
    session_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    store = get_cognitive_repository(session)
    rec = await store.get_decision_session(session_id)
    if rec is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="DecisionSession no encontrada")
    # A1: si la sesión pertenece a una cuenta, solo visible si es del principal.
    await require_owned_account_if_present(request, rec.account_id)
    return {"data": rec.payload or {"sessionId": rec.id, "kind": rec.kind, "status": rec.status}}


@router.get("/ai/decision-sessions/{session_id}/replay", response_model=AiEffectivenessResponseDto)
async def get_decision_session_replay(
    session_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Caja negra: timeline a partir de la fotografía DecisionSession (sin re-ejecutar)."""
    from fastapi import HTTPException

    from bolsa_analytics.cognitive import build_decision_replay

    store = get_cognitive_repository(session)
    rec = await store.get_decision_session(session_id)
    if rec is None or not rec.payload:
        raise HTTPException(status_code=404, detail="DecisionSession no encontrada")
    # A1: sesión de cuenta ajena no legible.
    await require_owned_account_if_present(request, rec.account_id)
    replay = build_decision_replay(rec.payload)
    return {"data": replay.to_dict()}


@router.post("/ai/decision-sessions/{session_id}/outcome", response_model=AiEffectivenessResponseDto)
async def close_decision_session_outcome(
    session_id: str,
    request: Request,
    body: CloseSessionOutcomeRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Cierra DecisionSession con Outcome (Learning). auto_mark = close D1 +N horizonte."""
    from fastapi import HTTPException

    from bolsa_api.api.dependencies import get_ohlcv_repository
    from bolsa_application.close_decision_session_outcome import CloseDecisionSessionOutcome

    store = get_cognitive_repository(session)
    rec = await store.get_decision_session(session_id)
    # A1: no cerrar learning de una sesión de cuenta ajena.
    if rec is not None:
        await require_owned_account_if_present(request, rec.account_id)
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
    request: Request,
    body: AppendTrialRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiEffectivenessResponseDto:
    # V2.15.4 A1 (deuda #1): trial acount-less no queda huérfano/global.
    scope = await resolve_account_scope_or_default(request, body.account_id)
    if scope is None:
        raise HTTPException(
            status_code=400,
            detail="Trial requiere una cuenta operativa del principal",
        )
    store = get_cognitive_repository(session)
    rec = await PersistTrial(store).execute(
        log_id=body.log_id,
        strategy_family_ref=body.strategy_family_ref,
        hypothesis_ref=body.hypothesis_ref,
        params_hash=body.params_hash,
        sharpe_is=body.sharpe_is,
        notes=body.notes,
        account_id=scope,
    )
    return AiEffectivenessResponseDto(
        data={"id": rec.id, "logId": rec.log_id, "strategyFamilyRef": rec.strategy_family_ref}
    )


@router.post("/ai/edge-reports", response_model=AiEffectivenessResponseDto)
async def append_edge_report(
    request: Request,
    body: AppendEdgeReportRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiEffectivenessResponseDto:
    # V2.15.4 A1 (deuda #1): edge report acount-less no queda huérfano/global.
    scope = await resolve_account_scope_or_default(request, body.account_id)
    if scope is None:
        raise HTTPException(
            status_code=400,
            detail="Edge report requiere una cuenta operativa del principal",
        )
    store = get_cognitive_repository(session)
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
        account_id=scope,
    )
    return AiEffectivenessResponseDto(
        data={
            "id": rec.id,
            "band": rec.band,
            "credibility": rec.credibility,
            "strategyOrSignalRef": rec.strategy_or_signal_ref,
        }
    )


@router.post("/ai/recommendations/propose", response_model=AiEffectivenessResponseDto)
async def propose_recommendation(
    request: Request,
    body: ProposeRecommendationRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """F3 — OHLCV → Assessments → DecisionRuntime → Recommendation."""
    # V2.15.4 A1 (deuda #1): acount-less se acota al default del principal
    # (la sesión/recommendación debe quedar atribuida y visible, no huérfana).
    scope = await resolve_account_scope_or_default(request, body.account_id)
    if scope is None:
        raise HTTPException(
            status_code=400,
            detail="Propose requiere una cuenta operativa del principal",
        )
    from bolsa_api.api.dependencies import (
        get_investor_profile_repository,
        get_propose_recommendation_use_case,
    )

    profile_ref = None
    policy_version = None
    profile_store = get_investor_profile_repository(session)
    profile = await profile_store.get_for_account(scope)
    if profile is not None:
        profile_ref = profile.id
        policy_version = profile.selected_policy_template_id

    use_case = get_propose_recommendation_use_case(session)
    try:
        result = await use_case.execute(
            instrument_id=body.instrument_id,
            suggested_quantity=body.suggested_quantity,
            suggested_price=body.suggested_price,
            account_id=scope,
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": result.to_dict()}


@router.post("/ai/intents/confirm", response_model=AiEffectivenessResponseDto)
async def confirm_intent(
    body: ConfirmIntentRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """F3 — humano confirma Recommendation → OrderIntent (+ opcional ExecuteTrade) + Session.

    Gate de aislamiento (P1 A1): la ruta puede ejecutar sobre ``account_id`` del body,
    así que se exige que la cuenta sea visible para el principal antes de tocar use-case.
    """
    await require_account_access(request, body.account_id)
    from bolsa_api.api.dependencies import get_confirm_intent_use_case

    use_case = await get_confirm_intent_use_case(session)
    result = await use_case.execute(
        recommendation_raw=body.recommendation,
        account_id=body.account_id,
        execute=body.execute,
        session_id=body.session_id,
        risk_override_reason=body.risk_override_reason,
        signed_stop=body.signed_stop,
    )
    return {"data": result}


@router.post("/ai/backtest-coach/analyze", response_model=AiEffectivenessResponseDto)
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
    from bolsa_ai.schemas import validate_backtest_coach_payload

    payload_errors = validate_backtest_coach_payload(completion.payload)
    if payload_errors:
        return {
            "data": {
                "engine": "heuristic",
                "payload": None,
                "provider": completion.provider,
                "model": completion.model_name,
                "validationErrors": payload_errors,
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


@router.post("/ai/fundamentals/explain", response_model=AiEffectivenessResponseDto)
async def explain_instrument_fundamentals(
    body: FundamentalExplainRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    F1b — copiloto FA. Solo interpreta FundamentalCardDto ya calculado.
    Proxy First; si Ollama no responde → engine=heuristic (prosa desde facts).
    """
    from fastapi import HTTPException

    from bolsa_api.api.dependencies import get_instrument_fundamentals_use_case
    from bolsa_application.explain_instrument_fundamentals import ExplainInstrumentFundamentals

    use_case = ExplainInstrumentFundamentals(get_instrument_fundamentals_use_case(session))
    result = await use_case.execute(body.instrument_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return {"data": result}


@router.post("/ai/dia-d/session-evidence", response_model=AiEffectivenessResponseDto)
async def explain_dia_d_session_evidence(body: DiaDSessionEvidenceRequest) -> dict[str, Any]:
    """
    Informe Evidence sesión C (DÍA D). Solo interpreta métricas ya calculadas.
    No FA ni Coach. Proxy First; sin LLM → engine=heuristic.
    """
    from bolsa_application.explain_dia_d_session_evidence import ExplainDiaDSessionEvidence

    result = await ExplainDiaDSessionEvidence().execute(body.model_dump(by_alias=True))
    return {"data": result}


@router.post("/ai/core-r/review-evidence", response_model=AiEffectivenessResponseDto)
async def explain_core_r_review_evidence(body: CoreRReviewEvidenceRequest) -> dict[str, Any]:
    """
    Informe Evidence cola CORE-R. Solo interpreta veredictos ya calculados.
    No FA ni Coach ni pisa TOP. Proxy First; sin LLM → engine=heuristic.
    """
    from bolsa_application.explain_core_r_review import ExplainCoreRReviewEvidence

    result = await ExplainCoreRReviewEvidence().execute(body.model_dump(by_alias=True))
    return {"data": result}


@router.post("/ai/fundamentals/filings/summarize", response_model=AiEffectivenessResponseDto)
async def summarize_instrument_filing(
    body: FilingSummarizeRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    F2b — resumen narrativo de un filing subido.
    No recalcula ratios ni escribe profile_snapshot.fundamentals.
    """
    from fastapi import HTTPException

    from bolsa_api.api.dependencies import get_instrument_repository
    from bolsa_application.instrument_filings import SummarizeInstrumentFiling

    result = await SummarizeInstrumentFiling(get_instrument_repository(session)).execute(
        body.instrument_id,
        body.filing_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument or filing not found")
    return {"data": result}


@router.post("/ai/fundamentals/filings/ask", response_model=AiEffectivenessResponseDto)
async def ask_instrument_filing(
    body: FilingAskRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    F2b++ — Q&A con retrieval TF-IDF local sobre el extracto del filing.
    Sin vectores/Chroma. No altera Score_FUND.
    """
    from fastapi import HTTPException

    from bolsa_api.api.dependencies import get_instrument_repository
    from bolsa_application.instrument_filings import AskInstrumentFiling

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


# ── bucle de adaptación gobernado (ADR-049) ─────────────────────────────────


class _AdaptationProxyAdapter:
    """Adapta ``AIGovernanceProxy`` al contrato de ``propose_adaptations``.

    Guarda provider/model de la última llamada para que el lote los declare. Si el proxy
    falla o no devuelve payload, se propaga para que el caso de uso caiga a heurística.
    """

    def __init__(self) -> None:
        self.provider: str | None = None
        self.model: str | None = None

    def __call__(self, evidence: Any, thresholds: Any, constraints: Any) -> Any:
        import json

        proxy = get_default_proxy()
        completion = proxy.complete_structured(
            prompt_template_id=ADAPTATION_PROMPT_ID,
            variables={
                "evidence": json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                "thresholds": json.dumps(thresholds, ensure_ascii=False, sort_keys=True),
                "constraints": json.dumps(constraints, ensure_ascii=False, sort_keys=True),
            },
        )
        if completion is None:
            raise RuntimeError("proxy_unavailable")
        self.provider = completion.provider
        self.model = completion.model_name
        return completion.payload


@router.post("/ai/adaptation/propose", response_model=AiEffectivenessResponseDto)
async def propose_adaptation(body: AdaptationProposeRequest) -> dict[str, Any]:
    """Evidencia medida → propuestas tipadas. La IA propone; no autoriza nada.

    Sin proxy (o con schema inválido) el lote sale con ``source=heuristic_fallback`` y su
    motivo. Con evidencia no medida sale vacío con ``evidence_not_measured``: no se adivina.
    """
    adapter = _AdaptationProxyAdapter() if body.use_proxy else None
    batch = propose_adaptations(
        body.evidence,
        proxy=adapter,
        thresholds=body.thresholds,
        constraints=body.constraints,
        validator=validate_adaptation_proposal_payload,
        provider=adapter.provider if adapter else None,
        model=adapter.model if adapter else None,
    )

    artifacts_dir = _adaptation_dir()
    created_at = datetime.now(UTC).isoformat()
    stored: list[str] = []
    for proposal in batch.proposals:
        record = {
            "id": proposal.id,
            "proposal": proposal.to_dict(),
            "evidenceHash": batch.evidence_hash,
            "preregistrationHash": batch.preregistration_hash,
            "source": batch.source,
            "reasonCodes": list(batch.reason_codes),
            "gaps": list(batch.gaps),
            "instrumentId": body.instrument_id,
            "thresholds": dict(body.thresholds or {}),
            "status": "proposed",
            "createdAt": created_at,
        }
        save_adaptation_record(artifacts_dir, record)
        stored.append(proposal.id)

    return {
        "data": {
            "batch": batch.to_dict(),
            "stored": stored,
            "governance": {
                "activationAllowed": False,
                "note": "Las propuestas no modifican estrategia, mandato ni umbrales.",
            },
        }
    }


@router.get("/ai/adaptation", response_model=AiEffectivenessResponseDto)
async def list_adaptations(
    status: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    """Propuestas persistidas, más recientes primero. Los ficheros corruptos se omiten."""
    rows = [
        record
        for record in iter_adaptation_records(_adaptation_dir())
        if status is None or str(record.get("status") or "") == status
    ]
    return {
        "data": {"items": rows[:limit], "count": min(len(rows), limit), "total": len(rows)}
    }


@router.post("/ai/adaptation/{proposal_id}/validate", response_model=AiEffectivenessResponseDto)
async def validate_adaptation(
    proposal_id: str, body: AdaptationValidateRequest
) -> dict[str, Any]:
    """LAB + as-run → veredicto ``AdaptationVerdictV1``, fail-closed.

    Un veredicto en verde solo habilita la aprobación humana: ``activationAllowed`` es siempre
    ``False`` en esta ruta.
    """
    artifacts_dir = _adaptation_dir()
    record = load_adaptation_record(artifacts_dir, proposal_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Proposal not found")

    thresholds = record.get("thresholds") or None
    verdict = validate_adaptation_proposal(
        proposal_id=proposal_id,
        candidate_id=body.candidate_id,
        lab=body.lab,
        as_run_artifacts=body.as_run_artifacts,
        thresholds=thresholds,
        declared_preregistration_hash=body.declared_preregistration_hash,
    )
    expected = preregistration_hash(thresholds)
    merge_adaptation_record(
        artifacts_dir,
        proposal_id,
        {
            "status": verdict.verdict,
            "candidateId": body.candidate_id,
            "verdict": verdict.to_dict(),
            "validatedAt": datetime.now(UTC).isoformat(),
        },
    )
    return {
        "data": {
            "verdict": verdict.to_dict(),
            "preregistrationHash": expected,
            "governance": {
                "activationAllowed": False,
                "autoActivationAllowed": False,
                "humanApprovalRequired": True,
                "reasons": list(verdict.reasons),
                "note": (
                    "Requiere aprobación humana explícita. LAB y DÍA-D se miden por separado: "
                    "ambos deben estar en verde y el as-run certificado. Aun así, solo habilita "
                    "la decisión humana; ninguna propuesta de IA ni un DÍA-D positivo autorizan "
                    "AUTO ni dinero real."
                ),
            },
        }
    }


