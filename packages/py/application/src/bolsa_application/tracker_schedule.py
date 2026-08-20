"""P9 — evalúa rastreadores programados (on_bar_close 1d/1wk) y encola scan jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from bolsa_application.scan_universe import resolve_scan_universe_instrument_ids
from bolsa_application.sync_scheduler import is_post_market_window
from bolsa_application.trackers import EnqueueTrackerScanJob
from bolsa_domain.repositories.ohlcv_repository import OhlcvRepository
from bolsa_domain.repositories.tracker_definition_repository import TrackerDefinitionRepository
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_infrastructure.database.repositories.list_repository import SqlAlchemyListRepository

TrackerScheduleStatus = Literal["enqueued", "skipped", "no_bars", "not_due", "error"]


def schedule_kind(definition: dict[str, Any]) -> str | None:
    schedule = definition.get("schedule")
    if not schedule or not isinstance(schedule, dict):
        return None
    kind = schedule.get("kind")
    return str(kind) if kind else None


def is_bar_close_window(timeframe: str, *, now: datetime | None = None) -> bool:
    """Ventana operativa post-cierre — daily exige post-market EU; weekly más laxo."""
    if timeframe == "1wk":
        moment = (now or datetime.now(UTC)).astimezone()
        # Viernes tarde en adelante hasta domingo — captura cierre semanal
        if moment.weekday() >= 4:
            return True
        return is_post_market_window(now)
    return is_post_market_window(now)


def is_tracker_due_for_bar(
    *,
    latest_bar_timestamp: str,
    schedule: dict[str, Any],
    timeframe: str,
    now: datetime | None = None,
) -> bool:
    if not is_bar_close_window(timeframe, now=now):
        return False
    last_processed = schedule.get("lastBarTimestamp")
    if last_processed is None:
        return True
    return str(latest_bar_timestamp) > str(last_processed)


def merge_schedule_run_state(
    definition: dict[str, Any],
    *,
    latest_bar_timestamp: str,
    run_at: str,
) -> dict[str, Any]:
    schedule = dict(definition.get("schedule") or {})
    schedule["lastBarTimestamp"] = latest_bar_timestamp
    schedule["lastRunAt"] = run_at
    return {**definition, "schedule": schedule}


@dataclass(frozen=True, slots=True)
class TrackerScheduleRunResult:
    """Resultado de Tracker Schedule Run."""
    tracker_id: str
    tracker_name: str
    status: TrackerScheduleStatus
    scan_job_id: str | None = None
    latest_bar_timestamp: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessTrackerSchedulesResult:
    """Procesa Tracker Schedules Result."""
    checked_count: int
    enqueued_count: int
    runs: list[TrackerScheduleRunResult] = field(default_factory=list)


class ProcessTrackerSchedules:
    """Procesa Tracker Schedules."""
    def __init__(
        self,
        tracker_repository: TrackerDefinitionRepository,
        list_repository: SqlAlchemyListRepository,
        ohlcv_repository: OhlcvRepository,
        enqueue_tracker_scan: EnqueueTrackerScanJob,
    ) -> None:
        self._trackers = tracker_repository
        self._lists = list_repository
        self._ohlcv = ohlcv_repository
        self._enqueue = enqueue_tracker_scan

    async def _probe_instrument_id(self, definition: dict[str, Any]) -> str | None:
        universe = definition.get("universe") or {}
        list_id = universe.get("listId")
        instrument_ids = universe.get("instrumentIds")
        try:
            resolved = await resolve_scan_universe_instrument_ids(
                self._lists,
                list_id=list_id,
                instrument_ids=instrument_ids,
                async_job=True,
            )
        except ValueError:
            return None
        return resolved[0] if resolved else None

    async def execute(
        self,
        *,
        tracker_id: str | None = None,
        force: bool = False,
    ) -> ProcessTrackerSchedulesResult:
        if tracker_id is not None:
            tracker = await self._trackers.get_tracker(tracker_id)
            candidates = [tracker] if tracker is not None else []
        else:
            candidates = await self._trackers.list_trackers(limit=200, enabled_only=True)

        runs: list[TrackerScheduleRunResult] = []
        enqueued = 0
        now = datetime.now(UTC)

        for tracker in candidates:
            if tracker is None:
                continue
            if not tracker.enabled:
                continue

            definition = dict(tracker.definition)
            kind = schedule_kind(definition)
            if kind is None:
                continue
            if kind == "manual":
                continue
            if kind == "cron":
                runs.append(
                    TrackerScheduleRunResult(
                        tracker_id=tracker.id,
                        tracker_name=tracker.name,
                        status="skipped",
                        reason="cron no implementado en P9 — usa on_bar_close",
                    )
                )
                continue
            if kind != "on_bar_close":
                runs.append(
                    TrackerScheduleRunResult(
                        tracker_id=tracker.id,
                        tracker_name=tracker.name,
                        status="skipped",
                        reason=f"schedule.kind desconocido: {kind}",
                    )
                )
                continue

            schedule = dict(definition.get("schedule") or {})
            probe_id = await self._probe_instrument_id(definition)
            if probe_id is None:
                runs.append(
                    TrackerScheduleRunResult(
                        tracker_id=tracker.id,
                        tracker_name=tracker.name,
                        status="error",
                        reason="No se pudo resolver universo del rastreador",
                    )
                )
                continue

            tf = TimeFrame.W1 if tracker.timeframe == "1wk" else TimeFrame.D1
            latest_bar = await self._ohlcv.get_latest_bar_date(probe_id, timeframe=tf)
            if latest_bar is None:
                runs.append(
                    TrackerScheduleRunResult(
                        tracker_id=tracker.id,
                        tracker_name=tracker.name,
                        status="no_bars",
                        reason="Sin OHLCV para instrumento sonda",
                    )
                )
                continue

            due = force or is_tracker_due_for_bar(
                latest_bar_timestamp=latest_bar,
                schedule=schedule,
                timeframe=tracker.timeframe,
                now=now,
            )
            if not due:
                runs.append(
                    TrackerScheduleRunResult(
                        tracker_id=tracker.id,
                        tracker_name=tracker.name,
                        status="not_due",
                        latest_bar_timestamp=latest_bar,
                        reason="Barra ya procesada o fuera de ventana post-cierre",
                    )
                )
                continue

            try:
                job = await self._enqueue.execute(tracker.id)
            except ValueError as exc:
                runs.append(
                    TrackerScheduleRunResult(
                        tracker_id=tracker.id,
                        tracker_name=tracker.name,
                        status="error",
                        latest_bar_timestamp=latest_bar,
                        reason=str(exc),
                    )
                )
                continue

            run_at = now.isoformat()
            updated_definition = merge_schedule_run_state(
                definition,
                latest_bar_timestamp=latest_bar,
                run_at=run_at,
            )
            await self._trackers.update_tracker(tracker.id, definition=updated_definition)

            enqueued += 1
            runs.append(
                TrackerScheduleRunResult(
                    tracker_id=tracker.id,
                    tracker_name=tracker.name,
                    status="enqueued",
                    scan_job_id=job.id,
                    latest_bar_timestamp=latest_bar,
                )
            )

        scheduled_kinds = ("on_bar_close",)
        checked = sum(
            1
            for item in candidates
            if item is not None and schedule_kind(item.definition) in scheduled_kinds
        )

        return ProcessTrackerSchedulesResult(
            checked_count=checked,
            enqueued_count=enqueued,
            runs=runs,
        )
