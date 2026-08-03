"""Use-cases de trackers de producto."""

from dataclasses import dataclass
from typing import Any

from bolsa_application.execution_router import ExecutionRouter
from bolsa_application.scan_jobs import EnqueueScanJob
from bolsa_application.scans import RunScan, ScanRunResult
from bolsa_application.tracker_alarms import execution_route_to_dict, route_tracker_alarms
from bolsa_domain.entities.tracker_definition import TrackerDefinitionRecord
from bolsa_domain.platform_kernel import (
    KERNEL_EVALUATION_MODES,
    validate_kernel_timeframe,
    validate_scan_bar_limit,
    validate_scan_max_results,
)
from bolsa_domain.repositories.execution_policy_repository import ExecutionPolicyRepository
from bolsa_domain.repositories.strategy_definition_repository import StrategyDefinitionRepository
from bolsa_domain.repositories.tracker_definition_repository import TrackerDefinitionRepository
from bolsa_infrastructure.database.repositories.scan_job_repository import ScanJobRecord


def _validate_universe(universe: dict[str, Any]) -> None:
    list_id = universe.get("listId")
    instrument_ids = universe.get("instrumentIds")
    if not list_id and not instrument_ids:
        raise ValueError("universe.listId o universe.instrumentIds es obligatorio")


def build_tracker_definition_dict(
    *,
    tracker_id: str,
    name: str,
    strategy_definition_id: str,
    strategy_version: int | None,
    universe: dict[str, Any],
    timeframe: str,
    bar_limit: int,
    max_results: int,
    evaluation_mode: str,
    rank_by: dict[str, Any] | None,
    default_execution_policy_id: str | None,
    schedule: dict[str, Any] | None,
    origin: str,
    source_prompt: str | None,
    enabled: bool,
    created_at: str,
    updated_at: str,
) -> dict[str, Any]:
    definition: dict[str, Any] = {
        "id": tracker_id,
        "name": name,
        "strategyDefinitionId": strategy_definition_id,
        "strategyVersion": strategy_version,
        "universe": universe,
        "timeframe": timeframe,
        "barLimit": bar_limit,
        "maxResults": max_results,
        "evaluationMode": evaluation_mode,
        "origin": origin,
        "enabled": enabled,
        "createdAt": created_at,
        "updatedAt": updated_at,
    }
    if rank_by is not None:
        definition["rankBy"] = rank_by
    if default_execution_policy_id is not None:
        definition["defaultExecutionPolicyId"] = default_execution_policy_id
    if schedule is not None:
        definition["schedule"] = schedule
    if source_prompt is not None:
        definition["sourcePrompt"] = source_prompt
    return definition


def tracker_to_scan_payload(tracker: TrackerDefinitionRecord) -> dict[str, Any]:
    definition = tracker.definition
    universe = definition.get("universe") or {}
    return {
        "trackerDefinitionId": tracker.id,
        "strategyDefinitionId": tracker.strategy_definition_id,
        "universe": universe,
        "timeframe": tracker.timeframe,
        "barLimit": int(definition.get("barLimit") or 500),
        "maxResults": int(definition.get("maxResults") or 100),
    }


class ListTrackerDefinitions:
    """Lista Tracker Definitions."""
    def __init__(self, repository: TrackerDefinitionRepository) -> None:
        self._repository = repository

    async def execute(self, *, limit: int = 50, enabled_only: bool = False) -> list[TrackerDefinitionRecord]:
        return await self._repository.list_trackers(limit=limit, enabled_only=enabled_only)


class ListTrackerDefinitionsForList:
    """Lista Tracker Definitions For List."""
    def __init__(self, repository: TrackerDefinitionRepository) -> None:
        self._repository = repository

    async def execute(self, list_id: str, *, limit: int = 50) -> list[TrackerDefinitionRecord]:
        return await self._repository.list_trackers_for_list(list_id, limit=limit)


class GetTrackerDefinition:
    """Obtiene Tracker Definition."""
    def __init__(self, repository: TrackerDefinitionRepository) -> None:
        self._repository = repository

    async def execute(self, tracker_id: str) -> TrackerDefinitionRecord | None:
        return await self._repository.get_tracker(tracker_id)


class CreateTrackerDefinition:
    """Crea Tracker Definition."""
    def __init__(
        self,
        repository: TrackerDefinitionRepository,
        strategy_repository: StrategyDefinitionRepository,
    ) -> None:
        self._repository = repository
        self._strategies = strategy_repository

    async def execute(
        self,
        *,
        name: str,
        strategy_definition_id: str,
        universe: dict[str, Any],
        strategy_version: int | None = None,
        timeframe: str = "1d",
        bar_limit: int = 500,
        max_results: int = 100,
        evaluation_mode: str = "bar_close",
        rank_by: dict[str, Any] | None = None,
        default_execution_policy_id: str | None = None,
        schedule: dict[str, Any] | None = None,
        origin: str = "manual",
        source_prompt: str | None = None,
        enabled: bool = True,
    ) -> TrackerDefinitionRecord:
        strategy = await self._strategies.get_definition(strategy_definition_id)
        if strategy is None:
            raise ValueError("Estrategia no encontrada")

        _validate_universe(universe)
        timeframe = validate_kernel_timeframe(timeframe)
        bar_limit = validate_scan_bar_limit(bar_limit)
        max_results = validate_scan_max_results(max_results)
        if evaluation_mode not in KERNEL_EVALUATION_MODES:
            raise ValueError(f"evaluationMode inválido: {evaluation_mode}")

        record = await self._repository.create_tracker(
            name=name,
            definition={},
            strategy_definition_id=strategy_definition_id,
            strategy_version=strategy_version,
            timeframe=timeframe,
            evaluation_mode=evaluation_mode,
            origin=origin,
            enabled=enabled,
        )
        definition = build_tracker_definition_dict(
            tracker_id=record.id,
            name=name,
            strategy_definition_id=strategy_definition_id,
            strategy_version=strategy_version,
            universe=universe,
            timeframe=timeframe,
            bar_limit=bar_limit,
            max_results=max_results,
            evaluation_mode=evaluation_mode,
            rank_by=rank_by,
            default_execution_policy_id=default_execution_policy_id,
            schedule=schedule,
            origin=origin,
            source_prompt=source_prompt,
            enabled=enabled,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        updated = await self._repository.update_tracker(record.id, definition=definition, name=name)
        return updated or record


class UpdateTrackerDefinition:
    """Actualiza Tracker Definition."""
    def __init__(
        self,
        repository: TrackerDefinitionRepository,
        strategy_repository: StrategyDefinitionRepository,
    ) -> None:
        self._repository = repository
        self._strategies = strategy_repository

    async def execute(
        self,
        tracker_id: str,
        *,
        name: str | None = None,
        strategy_definition_id: str | None = None,
        strategy_version: int | None = None,
        universe: dict[str, Any] | None = None,
        timeframe: str | None = None,
        bar_limit: int | None = None,
        max_results: int | None = None,
        evaluation_mode: str | None = None,
        rank_by: dict[str, Any] | None = None,
        default_execution_policy_id: str | None = None,
        schedule: dict[str, Any] | None = None,
        origin: str | None = None,
        source_prompt: str | None = None,
        enabled: bool | None = None,
    ) -> TrackerDefinitionRecord | None:
        existing = await self._repository.get_tracker(tracker_id)
        if existing is None:
            return None

        current = dict(existing.definition)
        resolved_name = name if name is not None else existing.name
        resolved_strategy_id = strategy_definition_id or existing.strategy_definition_id
        if strategy_definition_id is not None:
            strategy = await self._strategies.get_definition(strategy_definition_id)
            if strategy is None:
                raise ValueError("Estrategia no encontrada")

        resolved_universe = universe if universe is not None else dict(current.get("universe") or {})
        _validate_universe(resolved_universe)

        resolved_timeframe = validate_kernel_timeframe(timeframe or existing.timeframe)
        resolved_bar_limit = validate_scan_bar_limit(
            bar_limit if bar_limit is not None else int(current.get("barLimit") or 500),
        )
        resolved_max_results = validate_scan_max_results(
            max_results if max_results is not None else int(current.get("maxResults") or 100),
        )
        resolved_evaluation_mode = evaluation_mode or existing.evaluation_mode
        if resolved_evaluation_mode not in KERNEL_EVALUATION_MODES:
            raise ValueError(f"evaluationMode inválido: {resolved_evaluation_mode}")

        resolved_strategy_version = (
            strategy_version if strategy_version is not None else existing.strategy_version
        )
        resolved_rank_by = rank_by if rank_by is not None else current.get("rankBy")
        resolved_default_policy = (
            default_execution_policy_id
            if default_execution_policy_id is not None
            else current.get("defaultExecutionPolicyId")
        )
        resolved_schedule = schedule if schedule is not None else current.get("schedule")
        resolved_origin = origin if origin is not None else existing.origin
        resolved_source_prompt = (
            source_prompt if source_prompt is not None else current.get("sourcePrompt")
        )
        resolved_enabled = enabled if enabled is not None else existing.enabled

        definition = build_tracker_definition_dict(
            tracker_id=tracker_id,
            name=resolved_name,
            strategy_definition_id=resolved_strategy_id,
            strategy_version=resolved_strategy_version,
            universe=resolved_universe,
            timeframe=resolved_timeframe,
            bar_limit=resolved_bar_limit,
            max_results=resolved_max_results,
            evaluation_mode=resolved_evaluation_mode,
            rank_by=resolved_rank_by,
            default_execution_policy_id=resolved_default_policy,
            schedule=resolved_schedule,
            origin=resolved_origin,
            source_prompt=resolved_source_prompt,
            enabled=resolved_enabled,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
        return await self._repository.update_tracker(
            tracker_id,
            name=resolved_name,
            definition=definition,
            strategy_definition_id=strategy_definition_id,
            strategy_version=strategy_version,
            timeframe=resolved_timeframe,
            evaluation_mode=resolved_evaluation_mode,
            origin=origin,
            enabled=enabled,
        )


class DeleteTrackerDefinition:
    """Elimina Tracker Definition."""
    def __init__(self, repository: TrackerDefinitionRepository) -> None:
        self._repository = repository

    async def execute(self, tracker_id: str) -> bool:
        return await self._repository.delete_tracker(tracker_id)


@dataclass(frozen=True, slots=True)
class TrackerScanOutcome:
    """Use-case / tipo: Tracker Scan Outcome."""
    scan: ScanRunResult
    alarm_route: dict[str, Any] | None = None


class RunTrackerScan:
    """Ejecuta Tracker Scan."""
    def __init__(
        self,
        repository: TrackerDefinitionRepository,
        run_scan: RunScan,
        policy_repository: ExecutionPolicyRepository | None = None,
        execution_router: ExecutionRouter | None = None,
    ) -> None:
        self._repository = repository
        self._run_scan = run_scan
        self._policies = policy_repository
        self._router = execution_router

    async def execute(self, tracker_id: str) -> TrackerScanOutcome:
        tracker = await self._repository.get_tracker(tracker_id)
        if tracker is None:
            raise ValueError("Rastreador no encontrado")
        payload = tracker_to_scan_payload(tracker)
        universe = payload["universe"]
        result = await self._run_scan.execute(
            universe_list_id=universe.get("listId"),
            universe_instrument_ids=universe.get("instrumentIds"),
            strategy_definition_id=payload.get("strategyDefinitionId"),
            timeframe=str(payload.get("timeframe") or "1d"),
            bar_limit=int(payload.get("barLimit") or 500),
            max_results=int(payload.get("maxResults") or 100),
            async_job=False,
        )
        alarm_route = None
        if self._policies is not None and self._router is not None:
            route = await route_tracker_alarms(
                tracker=tracker,
                hits=result.hits,
                policies=self._policies,
                router=self._router,
            )
            if route is not None:
                alarm_route = execution_route_to_dict(route)
        return TrackerScanOutcome(scan=result, alarm_route=alarm_route)


class EnqueueTrackerScanJob:
    """Encola Tracker Scan Job."""
    def __init__(
        self,
        repository: TrackerDefinitionRepository,
        enqueue_scan: EnqueueScanJob,
    ) -> None:
        self._repository = repository
        self._enqueue_scan = enqueue_scan

    async def execute(self, tracker_id: str) -> ScanJobRecord:
        tracker = await self._repository.get_tracker(tracker_id)
        if tracker is None:
            raise ValueError("Rastreador no encontrado")
        payload = tracker_to_scan_payload(tracker)
        return await self._enqueue_scan.execute(payload, tracker_definition_id=tracker.id)
