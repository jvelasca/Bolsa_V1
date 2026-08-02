from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_db_session,
    get_hypothesis_belief_repository,
    get_hypothesis_repository,
    get_knowledge_node_repository,
    get_mkl_sync_repository,
    get_research_evidence_repository,
    get_research_tree_repository,
    get_research_trial_repository,
)
from bolsa_api.schemas.research import (
    BeliefHistoryEntryDto,
    BeliefHistoryListResponseDto,
    ConsolidationEligibilityResponseDto,
    ConsolidationRequestDto,
    ConsolidationResultDto,
    ConsolidationResultResponseDto,
    DiaDSessionEvidencePersistRequestDto,
    EvidenceLevelParam,
    HypothesesListResponseDto,
    HypothesisBeliefDto,
    HypothesisBeliefResponseDto,
    HypothesisCreateRequestDto,
    HypothesisDetailResponseDto,
    HypothesisDto,
    HypothesisKindParam,
    HypothesisStatusParam,
    HypothesisUpdateRequestDto,
    InstrumentResearchSummaryDto,
    InstrumentResearchSummaryResponseDto,
    KnowledgeNodeDetailResponseDto,
    KnowledgeNodeDto,
    KnowledgeNodesListResponseDto,
    KnowledgeStageParam,
    LabByInstrumentDto,
    LabByOriginDto,
    LabByPresetDto,
    LabHealthCampaignDto,
    LabHealthDto,
    LabHealthMetricCoverageDto,
    LabHealthResponseDto,
    LaboratoryResearchSummaryDto,
    LaboratoryResearchSummaryResponseDto,
    LinkTrialHypothesisRequestDto,
    MklSyncEventDto,
    MklSyncEventsListResponseDto,
    MklSyncRequestDto,
    MklSyncResultDto,
    MklSyncResultResponseDto,
    ResearchEvidenceDetailResponseDto,
    ResearchEvidenceDto,
    ResearchEvidenceListResponseDto,
    ResearchTreeEdgeCreateRequestDto,
    ResearchTreeEdgeDetailResponseDto,
    ResearchTreeEdgeDto,
    ResearchTreeEdgesListResponseDto,
    ResearchTrialDetailResponseDto,
    ResearchTrialDto,
    ResearchTrialsListResponseDto,
    ResearchTrialSortParam,
)
from bolsa_application.belief_engine import GetHypothesisBelief, ListBeliefHistory
from bolsa_application.hypotheses import (
    CreateHypothesis,
    GetHypothesis,
    LinkTrialToHypothesis,
    ListHypotheses,
    UpdateHypothesis,
)
from bolsa_application.knowledge_consolidation import (
    ConsolidateHypothesis,
    DeprecateKnowledgeNode,
    EvaluateConsolidation,
    GetKnowledgeNode,
    ListKnowledgeNodes,
)
from bolsa_application.mkl_sync import ListMklSyncEvents, SyncKnowledgeToMkl
from bolsa_application.research_evidence import (
    GetResearchEvidence,
    ListResearchEvidence,
    emit_evidence_for_dia_d_session,
)
from bolsa_application.research_tree import (
    CreateResearchTreeEdge,
    ListResearchTreeEdges,
    SoftDeleteResearchTreeEdge,
)
from bolsa_application.research_trials import (
    GetInstrumentResearchSummary,
    GetLabHealth,
    GetLaboratoryResearchSummary,
    GetResearchTrial,
    ListResearchTrials,
)
from bolsa_domain.entities.hypothesis import Hypothesis
from bolsa_domain.entities.hypothesis_belief import BeliefHistoryEntry, HypothesisBelief
from bolsa_domain.entities.knowledge_node import KnowledgeNode
from bolsa_domain.entities.research_evidence import ResearchEvidence
from bolsa_domain.entities.research_tree import MklSyncEvent, ResearchTreeEdge
from bolsa_domain.entities.research_trial import ResearchTrial

router = APIRouter()


def _to_trial_dto(trial: ResearchTrial) -> ResearchTrialDto:
    return ResearchTrialDto(
        id=trial.id,
        instrument_id=trial.instrument_id,
        params=trial.params,
        is_metrics=trial.is_metrics,
        proposed_by=trial.proposed_by,
        k_contribution=trial.k_contribution,
        created_at=trial.created_at,
        hypothesis_id=trial.hypothesis_id,
        research_question_id=trial.research_question_id,
        backtest_run_id=trial.backtest_run_id,
        optimization_run_id=trial.optimization_run_id,
        strategy_definition_id=trial.strategy_definition_id,
        preset_key=trial.preset_key,
        strategy_name=trial.strategy_name,
        blocks=trial.blocks,
        is_score=trial.is_score,
        parent_trial_id=trial.parent_trial_id,
        fail_code=trial.fail_code,
        manifest_ref=trial.manifest_ref,
    )


def _to_evidence_dto(row: ResearchEvidence) -> ResearchEvidenceDto:
    return ResearchEvidenceDto(
        id=row.id,
        instrument_id=row.instrument_id,
        level=row.level,
        source=row.source,
        evidence_weight=row.evidence_weight,
        summary=row.summary,
        created_at=row.created_at,
        trial_id=row.trial_id,
        hypothesis_id=row.hypothesis_id,
        edge_report_id=row.edge_report_id,
        math_version=row.math_version,
    )


def _to_hypothesis_dto(row: Hypothesis) -> HypothesisDto:
    return HypothesisDto(
        id=row.id,
        kind=row.kind,
        statement=row.statement,
        falsifiers=row.falsifiers,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        domain=row.domain,
        context=row.context,
    )


def _to_belief_dto(row: HypothesisBelief) -> HypothesisBeliefDto:
    return HypothesisBeliefDto(
        id=row.id,
        hypothesis_id=row.hypothesis_id,
        belief=row.belief,
        belief_ci_low=row.belief_ci_low,
        belief_ci_high=row.belief_ci_high,
        n_experiments=row.n_experiments,
        evidence_weight=row.evidence_weight,
        contexts_ok=row.contexts_ok,
        contexts_fail=row.contexts_fail,
        evidence_ids=row.evidence_ids,
        trial_ids=row.trial_ids,
        math_version=row.math_version,
        last_reviewed_at=row.last_reviewed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_belief_history_dto(row: BeliefHistoryEntry) -> BeliefHistoryEntryDto:
    return BeliefHistoryEntryDto(
        id=row.id,
        hypothesis_id=row.hypothesis_id,
        belief_id=row.belief_id,
        belief=row.belief,
        belief_ci_low=row.belief_ci_low,
        belief_ci_high=row.belief_ci_high,
        n_experiments=row.n_experiments,
        evidence_weight=row.evidence_weight,
        math_version=row.math_version,
        created_at=row.created_at,
        trigger_evidence_id=row.trigger_evidence_id,
        delta=row.delta,
    )


def _to_knowledge_dto(row: KnowledgeNode) -> KnowledgeNodeDto:
    return KnowledgeNodeDto(
        id=row.id,
        hypothesis_id=row.hypothesis_id,
        stage=row.stage,
        statement=row.statement,
        knowledge_confidence=row.knowledge_confidence,
        validity_context=row.validity_context,
        evidence_ids=row.evidence_ids,
        belief_snapshot=row.belief_snapshot,
        consolidation_report=row.consolidation_report,
        math_version=row.math_version,
        consolidated_at=row.consolidated_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        notes=row.notes,
    )


def _to_tree_edge_dto(row: ResearchTreeEdge) -> ResearchTreeEdgeDto:
    return ResearchTreeEdgeDto(
        id=row.id,
        from_ref_type=row.from_ref_type,
        from_ref_id=row.from_ref_id,
        to_ref_type=row.to_ref_type,
        to_ref_id=row.to_ref_id,
        edge_type=row.edge_type,
        created_at=row.created_at,
        notes=row.notes,
        payload=row.payload,
        deleted_at=row.deleted_at,
    )


def _to_mkl_event_dto(row: MklSyncEvent) -> MklSyncEventDto:
    return MklSyncEventDto(
        id=row.id,
        knowledge_node_id=row.knowledge_node_id,
        status=row.status,
        fact_payload=row.fact_payload,
        math_version=row.math_version,
        created_at=row.created_at,
        notes=row.notes,
    )


def _consolidation_use_case(session: AsyncSession) -> ConsolidateHypothesis:
    return ConsolidateHypothesis(
        get_hypothesis_repository(session),
        get_hypothesis_belief_repository(session),
        get_research_evidence_repository(session),
        get_knowledge_node_repository(session),
        get_research_tree_repository(session),
    )


@router.get("/research/trials", response_model=ResearchTrialsListResponseDto)
async def list_research_trials(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    instrument_id: Annotated[str | None, Query(alias="instrumentId")] = None,
    hypothesis_id: Annotated[str | None, Query(alias="hypothesisId")] = None,
    proposed_by: Annotated[str | None, Query(alias="proposedBy")] = None,
    preset_key: Annotated[str | None, Query(alias="presetKey")] = None,
    strategy_name: Annotated[str | None, Query(alias="strategy")] = None,
    strategy_definition_id: Annotated[str | None, Query(alias="strategyDefinitionId")] = None,
    optimization_run_id: Annotated[str | None, Query(alias="optimizationRunId")] = None,
    backtest_run_id: Annotated[str | None, Query(alias="backtestRunId")] = None,
    fail_code: Annotated[str | None, Query(alias="failCode")] = None,
    date_from: Annotated[str | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[str | None, Query(alias="dateTo")] = None,
    sort: Annotated[ResearchTrialSortParam, Query()] = "created_at",
    sort_dir: Annotated[Literal["asc", "desc"], Query(alias="sortDir")] = "desc",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ResearchTrialsListResponseDto:
    use_case = ListResearchTrials(get_research_trial_repository(session))
    trials, total = await use_case.execute(
        instrument_id=instrument_id,
        hypothesis_id=hypothesis_id,
        proposed_by=proposed_by,
        preset_key=preset_key,
        strategy_name=strategy_name,
        strategy_definition_id=strategy_definition_id,
        optimization_run_id=optimization_run_id,
        backtest_run_id=backtest_run_id,
        fail_code=fail_code,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return ResearchTrialsListResponseDto(
        data=[_to_trial_dto(t) for t in trials],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/research/trials/{trial_id}", response_model=ResearchTrialDetailResponseDto)
async def get_research_trial(
    trial_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResearchTrialDetailResponseDto:
    use_case = GetResearchTrial(get_research_trial_repository(session))
    trial = await use_case.execute(trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="Research trial not found")
    return ResearchTrialDetailResponseDto(data=_to_trial_dto(trial))


@router.patch(
    "/research/trials/{trial_id}/hypothesis",
    response_model=ResearchTrialDetailResponseDto,
)
async def link_trial_hypothesis(
    trial_id: str,
    body: LinkTrialHypothesisRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResearchTrialDetailResponseDto:
    use_case = LinkTrialToHypothesis(
        get_hypothesis_repository(session),
        get_research_trial_repository(session),
    )
    try:
        trial = await use_case.execute(
            trial_id=trial_id,
            hypothesis_id=body.hypothesis_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ResearchTrialDetailResponseDto(data=_to_trial_dto(trial))


@router.get("/research/hypotheses", response_model=HypothesesListResponseDto)
async def list_hypotheses(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    status: Annotated[HypothesisStatusParam | None, Query()] = None,
    kind: Annotated[HypothesisKindParam | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HypothesesListResponseDto:
    use_case = ListHypotheses(get_hypothesis_repository(session))
    try:
        rows, total = await use_case.execute(
            status=status, kind=kind, limit=limit, offset=offset
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return HypothesesListResponseDto(
        data=[_to_hypothesis_dto(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/research/hypotheses", response_model=HypothesisDetailResponseDto, status_code=201)
async def create_hypothesis(
    body: HypothesisCreateRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HypothesisDetailResponseDto:
    use_case = CreateHypothesis(
        get_hypothesis_repository(session),
        get_hypothesis_belief_repository(session),
    )
    try:
        row = await use_case.execute(
            statement=body.statement,
            falsifiers=body.falsifiers,
            kind=body.kind,
            domain=body.domain,
            context=body.context,
            status=body.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return HypothesisDetailResponseDto(data=_to_hypothesis_dto(row))


@router.get("/research/hypotheses/{hypothesis_id}", response_model=HypothesisDetailResponseDto)
async def get_hypothesis(
    hypothesis_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HypothesisDetailResponseDto:
    use_case = GetHypothesis(get_hypothesis_repository(session))
    row = await use_case.execute(hypothesis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return HypothesisDetailResponseDto(data=_to_hypothesis_dto(row))


@router.get(
    "/research/hypotheses/{hypothesis_id}/belief",
    response_model=HypothesisBeliefResponseDto,
)
async def get_hypothesis_belief(
    hypothesis_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HypothesisBeliefResponseDto:
    # Ensure hypothesis exists for clearer 404s.
    hyp = await GetHypothesis(get_hypothesis_repository(session)).execute(hypothesis_id)
    if hyp is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    belief = await GetHypothesisBelief(get_hypothesis_belief_repository(session)).execute(
        hypothesis_id
    )
    if belief is None:
        raise HTTPException(status_code=404, detail="Belief not found")
    return HypothesisBeliefResponseDto(data=_to_belief_dto(belief))


@router.get(
    "/research/hypotheses/{hypothesis_id}/belief/history",
    response_model=BeliefHistoryListResponseDto,
)
async def list_hypothesis_belief_history(
    hypothesis_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> BeliefHistoryListResponseDto:
    hyp = await GetHypothesis(get_hypothesis_repository(session)).execute(hypothesis_id)
    if hyp is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    rows, total = await ListBeliefHistory(get_hypothesis_belief_repository(session)).execute(
        hypothesis_id, limit=limit, offset=offset
    )
    return BeliefHistoryListResponseDto(
        data=[_to_belief_history_dto(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/research/hypotheses/{hypothesis_id}", response_model=HypothesisDetailResponseDto)
async def update_hypothesis(
    hypothesis_id: str,
    body: HypothesisUpdateRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HypothesisDetailResponseDto:
    use_case = UpdateHypothesis(get_hypothesis_repository(session))
    try:
        row = await use_case.execute(
            hypothesis_id,
            statement=body.statement,
            falsifiers=body.falsifiers,
            kind=body.kind,
            domain=body.domain,
            context=body.context,
            status=body.status,
            clear_domain=body.clear_domain,
            clear_context=body.clear_context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return HypothesisDetailResponseDto(data=_to_hypothesis_dto(row))


@router.get(
    "/research/hypotheses/{hypothesis_id}/consolidation",
    response_model=ConsolidationEligibilityResponseDto,
)
async def get_consolidation_eligibility(
    hypothesis_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    acknowledge_landscape_gap: Annotated[
        bool, Query(alias="acknowledgeLandscapeGap")
    ] = False,
) -> ConsolidationEligibilityResponseDto:
    use_case = EvaluateConsolidation(
        get_hypothesis_repository(session),
        get_hypothesis_belief_repository(session),
        get_research_evidence_repository(session),
        get_knowledge_node_repository(session),
    )
    report = await use_case.execute(
        hypothesis_id,
        acknowledge_landscape_gap=acknowledge_landscape_gap,
    )
    if report.get("failReasons") == ["hypothesis_exists"]:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return ConsolidationEligibilityResponseDto(data=report)


@router.post(
    "/research/hypotheses/{hypothesis_id}/consolidate",
    response_model=ConsolidationResultResponseDto,
)
async def consolidate_hypothesis(
    hypothesis_id: str,
    body: ConsolidationRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConsolidationResultResponseDto:
    use_case = _consolidation_use_case(session)
    try:
        result = await use_case.execute(
            hypothesis_id,
            acknowledge_landscape_gap=body.acknowledge_landscape_gap,
            notes=body.notes,
            validity_context=body.validity_context,
            dry_run=body.dry_run,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    node = result.get("node")
    return ConsolidationResultResponseDto(
        data=ConsolidationResultDto(
            created=bool(result.get("created")),
            node=None if node is None else _to_knowledge_dto(node),
            report=result.get("report") or {},
        )
    )


@router.get("/research/knowledge", response_model=KnowledgeNodesListResponseDto)
async def list_knowledge_nodes(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    hypothesis_id: Annotated[str | None, Query(alias="hypothesisId")] = None,
    stage: Annotated[KnowledgeStageParam | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> KnowledgeNodesListResponseDto:
    use_case = ListKnowledgeNodes(get_knowledge_node_repository(session))
    try:
        rows, total = await use_case.execute(
            hypothesis_id=hypothesis_id,
            stage=stage,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KnowledgeNodesListResponseDto(
        data=[_to_knowledge_dto(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/research/knowledge/{node_id}", response_model=KnowledgeNodeDetailResponseDto)
async def get_knowledge_node(
    node_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> KnowledgeNodeDetailResponseDto:
    row = await GetKnowledgeNode(get_knowledge_node_repository(session)).execute(node_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found")
    return KnowledgeNodeDetailResponseDto(data=_to_knowledge_dto(row))


@router.post(
    "/research/knowledge/{node_id}/deprecate",
    response_model=KnowledgeNodeDetailResponseDto,
)
async def deprecate_knowledge_node(
    node_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> KnowledgeNodeDetailResponseDto:
    row = await DeprecateKnowledgeNode(get_knowledge_node_repository(session)).execute(
        node_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found")
    return KnowledgeNodeDetailResponseDto(data=_to_knowledge_dto(row))


@router.post(
    "/research/knowledge/{node_id}/sync-mkl",
    response_model=MklSyncResultResponseDto,
)
async def sync_knowledge_to_mkl(
    node_id: str,
    body: MklSyncRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MklSyncResultResponseDto:
    use_case = SyncKnowledgeToMkl(
        get_knowledge_node_repository(session),
        get_mkl_sync_repository(session),
    )
    try:
        result = await use_case.execute(
            node_id,
            dry_run=body.dry_run,
            promote_to_accepted=body.promote_to_accepted,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MklSyncResultResponseDto(
        data=MklSyncResultDto(
            synced=bool(result["synced"]),
            dry_run=bool(result["dryRun"]),
            event=_to_mkl_event_dto(result["event"]),
            node=_to_knowledge_dto(result["node"]),
            fact_payload=result["factPayload"],
        )
    )


@router.get(
    "/research/knowledge/{node_id}/mkl-sync",
    response_model=MklSyncEventsListResponseDto,
)
async def list_mkl_sync_events(
    node_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MklSyncEventsListResponseDto:
    node = await GetKnowledgeNode(get_knowledge_node_repository(session)).execute(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found")
    rows, total = await ListMklSyncEvents(get_mkl_sync_repository(session)).execute(
        node_id, limit=limit, offset=offset
    )
    return MklSyncEventsListResponseDto(
        data=[_to_mkl_event_dto(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/research/tree/edges", response_model=ResearchTreeEdgesListResponseDto)
async def list_research_tree_edges(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    from_ref_type: Annotated[str | None, Query(alias="fromRefType")] = None,
    from_ref_id: Annotated[str | None, Query(alias="fromRefId")] = None,
    to_ref_type: Annotated[str | None, Query(alias="toRefType")] = None,
    to_ref_id: Annotated[str | None, Query(alias="toRefId")] = None,
    edge_type: Annotated[str | None, Query(alias="edgeType")] = None,
    include_deleted: Annotated[bool, Query(alias="includeDeleted")] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ResearchTreeEdgesListResponseDto:
    use_case = ListResearchTreeEdges(get_research_tree_repository(session))
    try:
        rows, total = await use_case.execute(
            from_ref_type=from_ref_type,
            from_ref_id=from_ref_id,
            to_ref_type=to_ref_type,
            to_ref_id=to_ref_id,
            edge_type=edge_type,
            include_deleted=include_deleted,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResearchTreeEdgesListResponseDto(
        data=[_to_tree_edge_dto(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/research/tree/edges",
    response_model=ResearchTreeEdgeDetailResponseDto,
    status_code=201,
)
async def create_research_tree_edge(
    body: ResearchTreeEdgeCreateRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResearchTreeEdgeDetailResponseDto:
    use_case = CreateResearchTreeEdge(get_research_tree_repository(session))
    try:
        row = await use_case.execute(
            from_ref_type=body.from_ref_type,
            from_ref_id=body.from_ref_id,
            to_ref_type=body.to_ref_type,
            to_ref_id=body.to_ref_id,
            edge_type=body.edge_type,
            notes=body.notes,
            payload=body.payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResearchTreeEdgeDetailResponseDto(data=_to_tree_edge_dto(row))


@router.delete(
    "/research/tree/edges/{edge_id}",
    response_model=ResearchTreeEdgeDetailResponseDto,
)
async def soft_delete_research_tree_edge(
    edge_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResearchTreeEdgeDetailResponseDto:
    row = await SoftDeleteResearchTreeEdge(get_research_tree_repository(session)).execute(
        edge_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Research tree edge not found")
    return ResearchTreeEdgeDetailResponseDto(data=_to_tree_edge_dto(row))


@router.get(
    "/research/instruments/{instrument_id}/summary",
    response_model=InstrumentResearchSummaryResponseDto,
)
async def get_instrument_research_summary(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentResearchSummaryResponseDto:
    use_case = GetInstrumentResearchSummary(get_research_trial_repository(session))
    summary = await use_case.execute(instrument_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return InstrumentResearchSummaryResponseDto(
        data=InstrumentResearchSummaryDto.model_validate(summary)
    )


@router.get("/research/evidence", response_model=ResearchEvidenceListResponseDto)
async def list_research_evidence(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    instrument_id: Annotated[str | None, Query(alias="instrumentId")] = None,
    trial_id: Annotated[str | None, Query(alias="trialId")] = None,
    hypothesis_id: Annotated[str | None, Query(alias="hypothesisId")] = None,
    level: Annotated[EvidenceLevelParam | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ResearchEvidenceListResponseDto:
    use_case = ListResearchEvidence(get_research_evidence_repository(session))
    rows, total = await use_case.execute(
        instrument_id=instrument_id,
        trial_id=trial_id,
        hypothesis_id=hypothesis_id,
        level=level,
        limit=limit,
        offset=offset,
    )
    return ResearchEvidenceListResponseDto(
        data=[_to_evidence_dto(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/research/dia-d-session-evidence",
    response_model=ResearchEvidenceDetailResponseDto,
)
async def persist_dia_d_session_evidence(
    body: DiaDSessionEvidencePersistRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResearchEvidenceDetailResponseDto:
    """
    Guarda Evidence sesión C DÍA D en Fase 2 (append-only).
    source=dia_d_session · sin Belief · sandbox ≠ DEMO.
    Ruta fuera de /research/evidence/{id} para no colisionar con GET.
    """
    row = await emit_evidence_for_dia_d_session(
        get_research_evidence_repository(session),
        body.model_dump(by_alias=True),
    )
    if row is None:
        raise HTTPException(status_code=400, detail="Invalid DÍA D evidence payload")
    await session.commit()
    return ResearchEvidenceDetailResponseDto(data=_to_evidence_dto(row))


@router.get("/research/evidence/{evidence_id}", response_model=ResearchEvidenceDetailResponseDto)
async def get_research_evidence(
    evidence_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResearchEvidenceDetailResponseDto:
    use_case = GetResearchEvidence(get_research_evidence_repository(session))
    row = await use_case.execute(evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Research evidence not found")
    return ResearchEvidenceDetailResponseDto(data=_to_evidence_dto(row))


@router.get("/research/summary", response_model=LaboratoryResearchSummaryResponseDto)
async def get_laboratory_research_summary(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LaboratoryResearchSummaryResponseDto:
    use_case = GetLaboratoryResearchSummary(get_research_trial_repository(session))
    summary = await use_case.execute()
    return LaboratoryResearchSummaryResponseDto(
        data=LaboratoryResearchSummaryDto(
            total_trials=summary["totalTrials"],
            total_k=summary["totalK"],
            active_instruments=summary["activeInstruments"],
            avg_sharpe=summary["avgSharpe"],
            avg_profit_factor=summary["avgProfitFactor"],
            avg_max_dd=summary["avgMaxDD"],
            last_trial_at=summary["lastTrialAt"],
            by_instrument=[LabByInstrumentDto.model_validate(x) for x in summary["byInstrument"]],
            by_preset=[LabByPresetDto.model_validate(x) for x in summary["byPreset"]],
            by_origin=[LabByOriginDto.model_validate(x) for x in summary["byOrigin"]],
        )
    )


@router.get("/research/lab-health", response_model=LabHealthResponseDto)
async def get_lab_health(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LabHealthResponseDto:
    """Q0.1 — sanidad del laboratorio (cobertura Sharpe/Sortino/Calmar, zero-trades)."""
    use_case = GetLabHealth(get_research_trial_repository(session))
    health = await use_case.execute()
    coverage = {
        key: LabHealthMetricCoverageDto.model_validate(val)
        for key, val in health["coverage"].items()
    }
    return LabHealthResponseDto(
        data=LabHealthDto(
            total_trials=health["totalTrials"],
            coverage=coverage,
            zero_trade_count=health["zeroTradeCount"],
            zero_trade_pct=health["zeroTradePct"],
            campaigns=[LabHealthCampaignDto.model_validate(c) for c in health["campaigns"]],
            campaign_count=health["campaignCount"],
            instruments_with_trials=health["instrumentsWithTrials"],
            active_instruments=health["activeInstruments"],
            instruments_without_trials=health["instrumentsWithoutTrials"],
            caveat=health["caveat"],
        )
    )
