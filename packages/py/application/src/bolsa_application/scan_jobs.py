import logging
from dataclasses import dataclass
from typing import Any

from bolsa_analytics.signals.feature_cache import FeatureCache, get_preset_feature_cache
from bolsa_application.execution_router import ExecutionRouter
from bolsa_application.scan_chunking import (
    JOB_KIND_CHUNK,
    JOB_KIND_PARENT,
    chunk_scan_payload,
    merge_scan_result_dicts,
    parent_scan_payload,
    should_chunk_universe,
    split_instrument_chunks,
)
from bolsa_application.scan_manifests import PersistScanManifest
from bolsa_application.scan_universe import (
    resolve_scan_universe_instrument_ids,
    universe_from_payload,
)
from bolsa_application.scans import RunScan, scan_run_result_to_dict
from bolsa_application.tracker_alarms import execution_route_to_dict, route_tracker_alarms
from bolsa_domain.platform_kernel import validate_kernel_timeframe
from bolsa_domain.repositories.execution_policy_repository import ExecutionPolicyRepository
from bolsa_domain.repositories.tracker_definition_repository import TrackerDefinitionRepository
from bolsa_infrastructure.database.repositories.list_repository import SqlAlchemyListRepository
from bolsa_infrastructure.database.repositories.scan_job_repository import (
    ScanJobRecord,
    SqlAlchemyScanJobRepository,
)
from bolsa_infrastructure.queue.scan_job_arq import ScanJobArqQueue
from bolsa_infrastructure.queue.scan_job_redis import ScanJobRedisQueue

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProcessScanJobResult:
    processed: bool
    job_id: str | None = None
    status: str | None = None
    error: str | None = None


class EnqueueScanJob:
    def __init__(
        self,
        job_repo: SqlAlchemyScanJobRepository,
        list_repository: SqlAlchemyListRepository,
        redis_queue: ScanJobRedisQueue | None = None,
        arq_queue: ScanJobArqQueue | None = None,
    ) -> None:
        self._jobs = job_repo
        self._lists = list_repository
        self._redis_queue = redis_queue
        self._arq_queue = arq_queue

    async def execute(
        self,
        payload: dict[str, Any],
        *,
        tracker_definition_id: str | None = None,
    ) -> ScanJobRecord:
        if not payload.get("universe"):
            raise ValueError("payload.universe es obligatorio")
        validate_kernel_timeframe(str(payload.get("timeframe") or "1d"))

        resolved_tracker_id = tracker_definition_id or payload.get("trackerDefinitionId")
        if resolved_tracker_id is not None:
            payload = {**payload, "trackerDefinitionId": resolved_tracker_id}

        list_id, instrument_ids = universe_from_payload(payload)
        resolved_ids = await resolve_scan_universe_instrument_ids(
            self._lists,
            list_id=list_id,
            instrument_ids=instrument_ids,
            async_job=True,
        )

        if not should_chunk_universe(len(resolved_ids)):
            job = await self._jobs.create(payload, tracker_definition_id=resolved_tracker_id)
            await self._enqueue_job(job.id)
            return job

        parent = await self._jobs.create(
            parent_scan_payload(payload, child_job_ids=[], total_instruments=len(resolved_ids)),
            status="processing",
            tracker_definition_id=resolved_tracker_id,
        )

        child_job_ids: list[str] = []
        chunks = split_instrument_chunks(resolved_ids)
        for index, chunk_ids in enumerate(chunks):
            child = await self._jobs.create(
                chunk_scan_payload(
                    payload,
                    parent_job_id=parent.id,
                    chunk_index=index,
                    chunk_total=len(chunks),
                    instrument_ids=chunk_ids,
                ),
                tracker_definition_id=resolved_tracker_id,
            )
            child_job_ids.append(child.id)
            await self._enqueue_job(child.id)

        updated = await self._jobs.update_payload(
            parent.id,
            parent_scan_payload(
                payload,
                child_job_ids=child_job_ids,
                total_instruments=len(resolved_ids),
            ),
        )
        return updated or parent

    async def _enqueue_job(self, job_id: str) -> None:
        if self._arq_queue is not None:
            await self._arq_queue.enqueue(job_id)
        elif self._redis_queue is not None:
            await self._redis_queue.push(job_id)


class GetScanJob:
    def __init__(self, job_repo: SqlAlchemyScanJobRepository) -> None:
        self._jobs = job_repo

    async def execute(self, job_id: str) -> ScanJobRecord | None:
        return await self._jobs.get_by_id(job_id)


class ListScanJobs:
    def __init__(self, job_repo: SqlAlchemyScanJobRepository) -> None:
        self._jobs = job_repo

    async def execute(self, *, limit: int = 20) -> list[ScanJobRecord]:
        return await self._jobs.list_recent(limit=limit)


class ProcessScanJob:
    def __init__(
        self,
        job_repo: SqlAlchemyScanJobRepository,
        run_scan: RunScan,
        feature_cache: FeatureCache | None = None,
        persist_manifest: PersistScanManifest | None = None,
        tracker_repository: TrackerDefinitionRepository | None = None,
        policy_repository: ExecutionPolicyRepository | None = None,
        execution_router: ExecutionRouter | None = None,
    ) -> None:
        self._jobs = job_repo
        self._run_scan = run_scan
        self._feature_cache = feature_cache or get_preset_feature_cache()
        self._persist_manifest = persist_manifest
        self._trackers = tracker_repository
        self._policies = policy_repository
        self._router = execution_router

    async def execute(self, job_id: str | None = None) -> ProcessScanJobResult:
        if job_id is not None:
            job = await self._jobs.claim_by_id(job_id)
        else:
            job = await self._jobs.claim_next()
        if job is None:
            return ProcessScanJobResult(processed=False)

        if job.payload.get("jobKind") == JOB_KIND_PARENT:
            await self._jobs.mark_failed(job.id, error="Los jobs parent no se procesan directamente")
            return ProcessScanJobResult(
                processed=True,
                job_id=job.id,
                status="failed",
                error="Los jobs parent no se procesan directamente",
            )

        cache_before_hits = self._feature_cache.hits
        cache_before_misses = self._feature_cache.misses

        try:
            result = await self._run_scan_from_payload(job.payload)
        except ValueError as exc:
            await self._jobs.mark_failed(job.id, error=str(exc))
            await self._maybe_finalize_parent(job.payload.get("parentJobId"))
            return ProcessScanJobResult(processed=True, job_id=job.id, status="failed", error=str(exc))
        except Exception as exc:
            await self._jobs.mark_failed(job.id, error=str(exc))
            await self._maybe_finalize_parent(job.payload.get("parentJobId"))
            return ProcessScanJobResult(processed=True, job_id=job.id, status="failed", error=str(exc))

        cache_hits = self._feature_cache.hits - cache_before_hits
        cache_misses = self._feature_cache.misses - cache_before_misses
        result_dict = scan_run_result_to_dict(result)
        result_dict["scanId"] = job.id
        alarm_route = await self._maybe_route_tracker_alarms(job, result.hits)
        if alarm_route is not None:
            result_dict["alarmRoute"] = alarm_route
        await self._jobs.mark_completed(
            job.id,
            result=result_dict,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
        )
        if self._persist_manifest is not None and job.payload.get("parentJobId") is None:
            try:
                await self._persist_manifest.execute(
                    scan_id=job.id,
                    result=result_dict,
                    payload=job.payload,
                    scan_job_id=job.id,
                    cache_stats={"hits": cache_hits, "misses": cache_misses},
                )
            except Exception:
                logger.exception("No se pudo persistir ScanManifest (job %s)", job.id)
        await self._maybe_finalize_parent(job.payload.get("parentJobId"))
        return ProcessScanJobResult(processed=True, job_id=job.id, status="completed")

    async def _maybe_route_tracker_alarms(self, job: ScanJobRecord, hits) -> dict[str, Any] | None:
        tracker_id = job.tracker_definition_id or (job.payload or {}).get("trackerDefinitionId")
        if not tracker_id or self._trackers is None or self._policies is None or self._router is None:
            return None
        # Chunks hijos: no auto-alarmar; el parent mergeado sí (abajo).
        if (job.payload or {}).get("jobKind") == JOB_KIND_CHUNK:
            return None
        tracker = await self._trackers.get_tracker(str(tracker_id))
        if tracker is None:
            return None
        route = await route_tracker_alarms(
            tracker=tracker,
            hits=hits,
            policies=self._policies,
            router=self._router,
        )
        return execution_route_to_dict(route) if route is not None else None

    async def _run_scan_from_payload(self, payload: dict[str, Any]):
        universe = payload.get("universe") or {}
        scan_request = payload.get("scanRequest") if payload.get("jobKind") == JOB_KIND_PARENT else payload
        source = scan_request if isinstance(scan_request, dict) else payload
        req_universe = source.get("universe") or universe
        return await self._run_scan.execute(
            universe_list_id=req_universe.get("listId"),
            universe_instrument_ids=req_universe.get("instrumentIds"),
            strategy_definition_id=source.get("strategyDefinitionId"),
            definition=source.get("definition"),
            preset_key=source.get("presetKey"),
            timeframe=str(source.get("timeframe") or "1d"),
            bar_limit=int(source.get("barLimit") or 500),
            max_results=int(source.get("maxResults") or 100),
            async_job=True,
        )

    async def _maybe_finalize_parent(self, parent_job_id: str | None) -> None:
        if not parent_job_id:
            return

        parent = await self._jobs.get_by_id(parent_job_id)
        if parent is None or parent.payload.get("jobKind") != JOB_KIND_PARENT:
            return
        if parent.status in ("completed", "failed"):
            return

        child_ids = list(parent.payload.get("childJobIds") or [])
        if not child_ids:
            return

        children = await self._jobs.get_many(child_ids)
        if len(children) != len(child_ids):
            return

        if any(child.status in ("pending", "processing") for child in children):
            return

        failed = [child for child in children if child.status == "failed"]
        if failed:
            await self._jobs.mark_failed(
                parent.id,
                error=f"{len(failed)} chunk(s) fallaron de {len(children)}",
            )
            return

        scan_request = dict(parent.payload.get("scanRequest") or {})
        req_universe = scan_request.get("universe") or {}
        merged = merge_scan_result_dicts(
            [child.result for child in children if child.result is not None],
            parent_scan_id=parent.id,
            max_results=int(scan_request.get("maxResults") or 100),
            list_id=req_universe.get("listId"),
            strategy_definition_id=scan_request.get("strategyDefinitionId"),
            timeframe=str(scan_request.get("timeframe") or "1d"),
        )
        cache_hits = sum(int(child.cache_hits or 0) for child in children)
        cache_misses = sum(int(child.cache_misses or 0) for child in children)
        tracker_id = parent.tracker_definition_id or (parent.payload or {}).get("trackerDefinitionId")
        if (
            tracker_id
            and self._trackers is not None
            and self._policies is not None
            and self._router is not None
        ):
            tracker = await self._trackers.get_tracker(str(tracker_id))
            if tracker is not None:
                route = await route_tracker_alarms(
                    tracker=tracker,
                    hits=list(merged.get("hits") or []),
                    policies=self._policies,
                    router=self._router,
                )
                if route is not None:
                    merged["alarmRoute"] = execution_route_to_dict(route)
        await self._jobs.mark_completed(
            parent.id,
            result=merged,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
        )
        if self._persist_manifest is not None:
            try:
                await self._persist_manifest.execute(
                    scan_id=parent.id,
                    result=merged,
                    payload=parent.payload,
                    scan_job_id=parent.id,
                    cache_stats={"hits": cache_hits, "misses": cache_misses},
                )
            except Exception:
                logger.exception("No se pudo persistir ScanManifest (parent job %s)", parent.id)


# Alias retrocompatible SC-5
ProcessNextScanJob = ProcessScanJob
