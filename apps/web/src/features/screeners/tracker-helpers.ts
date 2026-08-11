import {
  isKernelTimeframe,
  type CreateTrackerDefinitionDto,
  type ScanJobDto,
  type ScanRunResultDto,
  type TrackerDefinitionDetailDto,
  type TrackerScheduleKind,
  type UpdateTrackerDefinitionDto,
} from "@bolsa/shared";
import {
  defaultScanRunnerConfig,
  type ScanRunnerConfig,
} from "@/features/screeners/scan-runner-form";

export function scanConfigFromTracker(
  tracker: TrackerDefinitionDetailDto,
): ScanRunnerConfig {
  const def = tracker.definition;
  const timeframe = isKernelTimeframe(tracker.timeframe)
    ? tracker.timeframe
    : "1d";
  return {
    ...defaultScanRunnerConfig(),
    scanSource: "saved",
    savedStrategyId: tracker.strategyDefinitionId,
    listId: def.universe?.listId ?? "",
    maxResults: def.maxResults ?? 50,
    timeframe,
  };
}

export function buildCreateTrackerDto(
  config: ScanRunnerConfig,
  options: {
    name: string;
    strategyDefinitionId: string;
    scheduleKind: TrackerScheduleKind;
    defaultExecutionPolicyId?: string | null;
  },
): CreateTrackerDefinitionDto {
  const timeframe = isKernelTimeframe(config.timeframe)
    ? config.timeframe
    : "1d";
  return {
    name: options.name,
    strategyDefinitionId: options.strategyDefinitionId,
    universe: { listId: config.listId },
    timeframe,
    maxResults: config.maxResults,
    schedule:
      options.scheduleKind === "on_bar_close"
        ? { kind: "on_bar_close" }
        : { kind: "manual" },
    defaultExecutionPolicyId: options.defaultExecutionPolicyId ?? null,
    enabled: true,
  };
}

export function trackerScheduleKindFromTracker(
  tracker: TrackerDefinitionDetailDto,
): TrackerScheduleKind {
  const kind = tracker.definition.schedule?.kind;
  return kind === "on_bar_close" ? "on_bar_close" : "manual";
}

export function buildUpdateTrackerDto(
  config: ScanRunnerConfig,
  options: {
    name: string;
    scheduleKind: TrackerScheduleKind;
    defaultExecutionPolicyId?: string | null;
    enabled?: boolean;
  },
): UpdateTrackerDefinitionDto {
  const timeframe = isKernelTimeframe(config.timeframe)
    ? config.timeframe
    : "1d";
  return {
    name: options.name,
    universe: { listId: config.listId },
    timeframe,
    maxResults: config.maxResults,
    schedule:
      options.scheduleKind === "on_bar_close"
        ? { kind: "on_bar_close" }
        : { kind: "manual" },
    defaultExecutionPolicyId: options.defaultExecutionPolicyId ?? null,
    enabled: options.enabled,
  };
}

export function trackerScheduleLabel(
  tracker: TrackerDefinitionDetailDto,
): string | null {
  const kind = tracker.definition.schedule?.kind;
  if (!kind || kind === "manual") return null;
  if (kind === "on_bar_close") return "Auto · cierre barra";
  if (kind === "cron") return "Cron";
  return kind;
}

export function latestCompletedScanResultForTracker(
  jobs: ScanJobDto[],
  trackerId: string,
): ScanRunResultDto | null {
  const completed = jobs.filter(
    (job) =>
      job.trackerDefinitionId === trackerId &&
      job.status === "completed" &&
      job.result != null,
  );
  if (completed.length === 0) return null;

  completed.sort((left, right) => {
    const leftTime = new Date(left.completedAt ?? left.updatedAt).getTime();
    const rightTime = new Date(right.completedAt ?? right.updatedAt).getTime();
    return rightTime - leftTime;
  });

  return completed[0]!.result!;
}
