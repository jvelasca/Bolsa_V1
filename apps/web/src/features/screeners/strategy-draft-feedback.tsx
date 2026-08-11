import {
  AlertTriangle,
  CheckCircle2,
  Filter,
  Info,
  ListOrdered,
  Sparkles,
} from "lucide-react";
import type { DraftStrategyFromPromptResultDto } from "@bolsa/shared";
import { cn } from "@/lib/utils";

interface StrategyDraftFeedbackProps {
  draft: DraftStrategyFromPromptResultDto;
  compact?: boolean;
}

function confidenceTone(confidence: number): string {
  if (confidence >= 0.72) return "bg-emerald-500";
  if (confidence >= 0.55) return "bg-amber-500";
  return "bg-destructive";
}

function confidenceLabel(confidence: number): string {
  if (confidence >= 0.72) return "Alta";
  if (confidence >= 0.55) return "Moderada";
  return "Baja";
}

export function StrategyDraftFeedback({
  draft,
  compact,
}: StrategyDraftFeedbackProps) {
  const feedback = draft.feedback;
  const summary = feedback?.summary ?? draft.explanation;
  const confidencePct = Math.round(draft.confidence * 100);

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-primary/20 bg-primary/5 px-3 py-2.5">
        <div className="flex items-start gap-2">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <div className="min-w-0 space-y-1">
            <p className="text-xs font-medium text-foreground">
              Lo que entendí
            </p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {summary}
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Confianza</span>
          <span className="font-medium">
            {confidencePct}% · {confidenceLabel(draft.confidence)}
          </span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              "h-full rounded-full transition-all",
              confidenceTone(draft.confidence),
            )}
            style={{ width: `${confidencePct}%` }}
          />
        </div>
      </div>

      {feedback?.detectedSignals && feedback.detectedSignals.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-foreground">
            Señales en tu mensaje
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {feedback.detectedSignals.map((signal) => (
              <li
                key={signal.id}
                className="rounded-md border border-border bg-muted/30 px-2 py-1 text-[11px]"
                title={signal.detail}
              >
                <span className="text-muted-foreground">{signal.label}: </span>
                <span className="font-medium text-foreground">
                  {signal.detail ?? "—"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {feedback?.fundamentalPreview?.enabled && (
        <div className="rounded-md border border-sky-500/25 bg-sky-500/5 px-3 py-2.5 text-xs">
          <div className="mb-2 flex items-center gap-1.5 font-medium text-foreground">
            <Filter className="h-3.5 w-3.5 text-sky-600 dark:text-sky-400" />
            Filtro fundamental (preview)
          </div>
          <ul className="space-y-1 text-[11px] text-muted-foreground">
            {feedback.fundamentalPreview.conditions.map((condition) => (
              <li key={`${condition.metric}-${condition.operator}`}>
                <span className="font-medium text-foreground">
                  {condition.label}
                </span>{" "}
                {condition.valueLabel}
              </li>
            ))}
            {feedback.fundamentalPreview.sectors.length > 0 && (
              <li>
                <span className="font-medium text-foreground">Sectores</span>{" "}
                {feedback.fundamentalPreview.sectors.join(", ")}
              </li>
            )}
            <li>
              Datos: {feedback.fundamentalPreview.dataSource} · máx.{" "}
              {feedback.fundamentalPreview.maxAgeDays} días
            </li>
          </ul>
          <p className="mt-2 text-[10px] leading-relaxed opacity-90">
            {feedback.fundamentalPreview.refreshNote}
          </p>
          <p className="mt-1 text-[10px] leading-relaxed opacity-80">
            {feedback.fundamentalPreview.rejectNote}
          </p>
        </div>
      )}

      {feedback?.warnings && feedback.warnings.length > 0 && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-950 dark:text-amber-100">
          <div className="mb-1 flex items-center gap-1.5 font-medium">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            Revisa antes de guardar
          </div>
          <ul className="list-inside list-disc space-y-0.5 text-[11px] opacity-90">
            {feedback.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {feedback?.alternatives && feedback.alternatives.length > 1 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-foreground">
            Alternativas consideradas
          </p>
          <ul className="space-y-1 text-[11px]">
            {feedback.alternatives.map((alt) => (
              <li
                key={alt.presetKey}
                className={cn(
                  "flex items-center justify-between rounded border px-2 py-1",
                  alt.selected
                    ? "border-primary/40 bg-primary/5 font-medium"
                    : "border-border text-muted-foreground",
                )}
              >
                <span>{alt.label}</span>
                <span className="tabular-nums">{alt.score} pts</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {feedback?.scanSteps && feedback.scanSteps.length > 0 && (
        <div className="space-y-1.5">
          <p className="flex items-center gap-1.5 text-xs font-medium text-foreground">
            <ListOrdered className="h-3.5 w-3.5" />
            Al ejecutar el rastreo
          </p>
          <ol className="list-inside list-decimal space-y-0.5 text-[11px] text-muted-foreground">
            {feedback.scanSteps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Info className="h-3 w-3" />
          Motor: {feedback?.engineLabel ?? draft.engine}
        </span>
        {draft.validated && (
          <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400">
            <CheckCircle2 className="h-3 w-3" />
            Definición validada
          </span>
        )}
        {!compact && feedback?.ambiguous && (
          <span className="text-amber-700 dark:text-amber-300">
            Interpretación ambigua
          </span>
        )}
      </div>
    </div>
  );
}
