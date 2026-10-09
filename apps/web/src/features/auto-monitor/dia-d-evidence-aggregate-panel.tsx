/**
 * S4-agregador-evidencia — ÚNICA superficie del veredicto agregado `NO CONFIRMADO`.
 *
 * El contenedor NO recalcula nada: lee los artefactos que ya leen las sub-vistas hijas
 * (feedback por ventana · sandbox por día) por sus MISMOS queryKey y los normaliza a hechos.
 * El read-model puro (`dia-d-evidence-aggregate.ts`) los compone; esta superficie sólo lo pinta.
 *
 * Reuso pasivo: los hooks se suscriben a la sub-vista activa (`enabled`), así que al abrir una
 * sub-vista comparten entrada de caché con su panel (cero llamadas extra) y una capa cuya
 * sub-vista no se ha visitado se declara «Sin dato todavía» —nunca un 0.
 *
 * Primer nivel sin jerga: los tokens crudos de contrato sólo viven dentro del `AutoTechnicalDetail`.
 *
 * @see docs/PROJECT_PREMISES.md §5.2
 */

import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { components } from "@/api/schema";
import { absentDataLabel } from "@/components/absent-data";
import { cn } from "@/lib/utils";
import { AUTO_USER_TEXT } from "@/features/auto/auto-typography";
import { AutoTechnicalDetail } from "@/features/auto/auto-technical-detail";
import {
  buildDiaDEvidenceAggregate,
  type DiaDEvidenceAggregateInput,
  type DiaDEvidenceAggregateV1,
} from "@/features/auto-monitor/dia-d-evidence-aggregate";
import {
  DIA_D_EVIDENCE_AGGREGATE_DESCRIPTION,
  DIA_D_EVIDENCE_AGGREGATE_TITLE,
  DIA_D_EVIDENCE_GLOBAL_VERDICT_LABEL,
} from "@/features/auto-monitor/dia-d-evidence-aggregate-labels";
import {
  useAutoDiaDFeedback,
  useAutoDiaDFeedbackList,
} from "@/features/auto-monitor/use-auto-dia-d-feedback";
import {
  useAutoDiaDReplay,
  useAutoDiaDReplayDays,
} from "@/features/auto-monitor/use-auto-dia-d-replay";

type DiaDFeedbackDto = components["schemas"]["DiaDFeedbackDto"];
type DiaDAutoReplayDto = components["schemas"]["DiaDAutoReplayDto"];

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function str(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function windowFacts(
  artifact: DiaDFeedbackDto | null,
): DiaDEvidenceAggregateInput["window"] {
  if (!artifact) return null;
  const gate = artifact.gate ?? {};
  const verdict = str(gate.verdict);
  return {
    loaded: artifact.available === true && verdict !== null,
    verdict,
    days: num(gate.days),
    episodes: num(gate.episodes),
    cycles: num(gate.cycles),
  };
}

function reconciliationFacts(
  replay: DiaDAutoReplayDto | null,
): DiaDEvidenceAggregateInput["reconciliation"] {
  if (!replay) return null;
  const summary = replay.summary ?? null;
  return {
    loaded: replay.available === true && summary !== null,
    verdict: str(summary?.verdict),
    match: num(summary?.match),
    divergent: num(summary?.divergent),
    notMeasured: num(summary?.notMeasured),
  };
}

function oosFacts(
  artifact: DiaDFeedbackDto | null,
): DiaDEvidenceAggregateInput["oos"] {
  if (!artifact) return null;
  const summary = artifact.summary ?? null;
  return {
    loaded: artifact.available === true && summary !== null,
    oosSupported: num(summary?.oosSupported),
    mixed: num(summary?.mixed),
    refuted: num(summary?.refuted),
    notMeasured: num(summary?.notMeasured),
  };
}

export function DiaDEvidenceAggregateView({
  aggregate,
}: {
  aggregate: DiaDEvidenceAggregateV1;
}) {
  return (
    <section
      className="space-y-3 rounded-xl border border-border bg-card p-4"
      aria-labelledby="dia-d-evidence-aggregate-heading"
      data-testid="dia-d-evidence-aggregate-panel"
      data-verdict={aggregate.verdict}
    >
      <div className="space-y-1">
        <h2
          id="dia-d-evidence-aggregate-heading"
          className={cn("font-semibold", AUTO_USER_TEXT)}
        >
          {DIA_D_EVIDENCE_AGGREGATE_TITLE}
        </h2>
        <p className="text-xs text-muted-foreground">
          {DIA_D_EVIDENCE_AGGREGATE_DESCRIPTION}
        </p>
        <p
          className={cn("font-medium", AUTO_USER_TEXT)}
          data-testid="dia-d-evidence-aggregate-verdict"
        >
          {DIA_D_EVIDENCE_GLOBAL_VERDICT_LABEL}
        </p>
        <p className="text-xs text-muted-foreground">{aggregate.summary}</p>
      </div>

      <ul className="space-y-2" data-testid="dia-d-evidence-aggregate-layers">
        {aggregate.layers.map((layer) => (
          <li
            key={layer.id}
            className="rounded-md border border-border/60 px-3 py-2"
            data-testid="dia-d-evidence-aggregate-layer"
            data-layer={layer.id}
            data-state={layer.state}
          >
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span
                aria-hidden="true"
                className={cn(
                  "mt-1 inline-block size-1.5 shrink-0 rounded-full",
                  layer.state === "measured"
                    ? "bg-sky-500"
                    : "bg-muted-foreground/40",
                )}
              />
              <span className={cn("font-medium", AUTO_USER_TEXT)}>
                {layer.title}
              </span>
              <span
                className="uppercase tracking-wide text-xs text-muted-foreground"
                data-testid="dia-d-evidence-aggregate-layer-state"
              >
                {layer.state === "measured"
                  ? layer.verdictLabel
                  : layer.gapLabel}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{layer.honestyNote}</p>
            {layer.measurement ? (
              <p className="text-xs tabular-nums text-muted-foreground">
                {layer.measurement}
              </p>
            ) : null}
            {layer.state === "gap" && layer.reason ? (
              <p className="text-xs text-muted-foreground">{layer.reason}</p>
            ) : null}
          </li>
        ))}
      </ul>

      <AutoTechnicalDetail testId="dia-d-evidence-aggregate-technical">
        <ul className="space-y-1">
          {aggregate.layers.map((layer) => (
            <li key={layer.id}>
              {layer.id}:{" "}
              {layer.state === "measured"
                ? [layer.verdictToken, layer.measurementToken]
                    .filter(Boolean)
                    .join(" · ")
                : `hueco · ${layer.gap}`}
            </li>
          ))}
        </ul>
        <p>
          Capa más fuerte medida:{" "}
          {aggregate.maxLayerReached ?? absentDataLabel()}
        </p>
        <p>{aggregate.confirmationBlockedReason}</p>
      </AutoTechnicalDetail>
    </section>
  );
}

export function DiaDEvidenceAggregatePanel({
  activeView,
}: {
  activeView: "sandbox" | "feedback";
}) {
  const [searchParams] = useSearchParams();
  const dayParam = searchParams.get("day");
  const windowParam = searchParams.get("window");
  const onFeedback = activeView === "feedback";
  const onSandbox = activeView === "sandbox";

  const listQuery = useAutoDiaDFeedbackList({ enabled: onFeedback });
  const latest = listQuery.data?.latest ?? null;
  const selectedWindow = windowParam ?? latest;
  const detailQuery = useAutoDiaDFeedback(selectedWindow, {
    enabled: onFeedback,
  });
  const artifact =
    detailQuery.data ??
    (selectedWindow !== null && selectedWindow === latest
      ? (listQuery.data?.artifact ?? null)
      : null);

  const daysQuery = useAutoDiaDReplayDays({ enabled: onSandbox });
  const days = daysQuery.data?.days ?? [];
  const selectedDay = dayParam ?? days[0] ?? null;
  const replayQuery = useAutoDiaDReplay(selectedDay, { enabled: onSandbox });
  const replay = replayQuery.data ?? null;

  const aggregate = useMemo(
    () =>
      buildDiaDEvidenceAggregate({
        window: windowFacts(artifact),
        reconciliation: reconciliationFacts(replay),
        oos: oosFacts(artifact),
      }),
    [artifact, replay],
  );

  return <DiaDEvidenceAggregateView aggregate={aggregate} />;
}
