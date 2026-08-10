import { AiInfoButton } from "@/features/ai/ai-info-button";
import { confidenceLabel, type CoachAuditResultV1, type CoachConfidence, type PriorCoachAuditHint } from "@/features/backtests/coach-dual-audit";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Props {
  /** Etiqueta de contexto del deep-note (símbolo · periodo · TF). */
  contextLabel: string;
  running?: boolean;
  okCount: number;
  /** Auditoría del deep-note vivo (`deepNote.audit`). Opcional si no hay aún. */
  audit?: CoachAuditResultV1;
  confidence: CoachConfidence;
  engineLabel: string;
  /** Pref CORE A de narración LLM (deshabilita Reanalizar si OFF). */
  llmNarrate: boolean;
  llmBusy: boolean;
  /** Habilita el botón Guardar TOP/Finalistas (orquestador computa). */
  saveEnabled: boolean;
  /** Habilita el botón Reanalizar (orquestador computa). */
  reanalyzeEnabled: boolean;
  postLab: boolean;
  saveMsg: string | null;
  /** Línea de estado sobre el TOP guardado en BD (orquestador formatea). */
  savedTopFooter?: string;
  priorAuditHint: PriorCoachAuditHint | null;
  /** Guardar TOP-3 semifinal / Finalistas (orquestador: saveTopMutation). */
  onSaveTop: () => void;
  /** Reanalizar con IA (orquestador: llmMutation + reset fingerprint). */
  onReanalyze: () => void;
}

/** Cabecera del panel Coach: título + quorum, badge de confianza, motor y
 * acciones de guardado/reanálisis + avisos de estado y pasada anterior.
 * Extraído de `backtest-explore-panel.tsx` (feature-slicing M5, frente
 * `backtest-explore-panel`). Diseño B: los handlers de guardado/reanálisis y
 * el estado del ciclo (`saveTopMutation`, `llmMutation`, refs) permanecen en el
 * orquestador como props-closure; aquí solo vive el JSX presentacional. */
export function BacktestExploreHeader({
  contextLabel,
  running,
  okCount,
  audit,
  confidence,
  engineLabel,
  llmNarrate,
  llmBusy,
  saveEnabled,
  reanalyzeEnabled,
  postLab,
  saveMsg,
  savedTopFooter,
  priorAuditHint,
  onSaveTop,
  onReanalyze,
}: Props) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-1.5">
          <p
            className="text-[11px] font-semibold text-foreground"
            title="Ranking local (A) + auditor (B) + gate. La IA puede vetar tipado; no inventa el TOP."
          >
            Coach · TOP a futuro
          </p>
          <AiInfoButton surface="backtest_coach" />
        </div>
        <p className="text-[10px] text-muted-foreground">{contextLabel}</p>
        <p className="mt-0.5 text-[10px] leading-snug text-muted-foreground">
          Quorum: <strong className="font-medium text-foreground/80">A</strong> ranking ·{' '}
          <strong className="font-medium text-foreground/80">A2</strong> shadow ·{' '}
          <strong className="font-medium text-foreground/80">B</strong> auditor ·{' '}
          <strong className="font-medium text-foreground/80">C</strong> adversario · red-team
          pre-guardar.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {!running && okCount > 0 && audit && (
          <span
            className={cn(
              'rounded-md border px-1.5 py-0.5 text-[10px] font-medium',
              confidence === 'consensus' &&
                'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
              confidence === 'discrepancy' &&
                'border-amber-500/40 bg-amber-500/10 text-amber-200',
              confidence === 'weak' && 'border-amber-500/40 bg-amber-500/10 text-amber-200',
              confidence === 'no_auditor' && 'border-border text-muted-foreground',
            )}
            title={
              audit.challenge.passed
                ? audit.shadowDisagreement || audit.auditorCDisagreement
                  ? `Discrepancia A/A2/C · ack para guardar`
                  : 'Quorum B + red-team OK'
                : audit.challenge.checks
                    .filter((c) => !c.passed && c.severity === 'hard')
                    .map((c) => c.detail)
                    .join(' · ') || 'TOP débil — ack para guardar'
            }
          >
            {confidenceLabel(confidence)}
          </span>
        )}
        <span className="text-[10px] text-muted-foreground">
          {llmBusy ? 'IA A+C…' : engineLabel}
        </span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 text-[11px]"
          disabled={!saveEnabled}
          onClick={onSaveTop}
          title={
            postLab
              ? 'Guarda Finalistas (active + lab_validated) tras el Lab. Sustituye el TOP del valor.'
              : 'Guarda TOP-3 semifinal (sin Lab). No escribe lab_validated.'
          }
        >
          {postLab ? 'Guardar Finalistas' : 'Guardar TOP-3'}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 text-[11px]"
          disabled={!reanalyzeEnabled}
          onClick={onReanalyze}
          title={
            llmNarrate
              ? 'Vuelve a pedir narrativa IA (el ranking ★ es local-AT)'
              : 'Activa «Narración LLM Coach» en (…) del Asistente'
          }
        >
          Reanalizar
        </Button>
      </div>

      {(saveMsg || savedTopFooter) && (
        <p className="text-[10px] text-muted-foreground">
          {saveMsg ? `${saveMsg}. ` : ''}
          {savedTopFooter}
        </p>
      )}

      {priorAuditHint && !running && (
        <p
          className={cn(
            'rounded-md border px-2 py-1.5 text-[10px]',
            priorAuditHint.confidence === 'weak' || priorAuditHint.softWeak
              ? 'border-amber-500/30 bg-amber-500/5 text-amber-100/90'
              : priorAuditHint.confidence === 'discrepancy'
                ? 'border-amber-500/25 bg-amber-500/5 text-muted-foreground'
                : 'border-border/70 bg-muted/20 text-muted-foreground',
          )}
          title="Contexto de la pasada guardada (CORE A). No cambia el ranking ★ actual."
        >
          Pasada anterior · {confidenceLabel(priorAuditHint.confidence)}
          {priorAuditHint.softWeak ? ' · soft-débil' : ''}
          {priorAuditHint.coachPass === 'post_lab' ? ' · post-Lab' : ''}
          {' · '}
          no modula el TOP actual (solo contexto).
        </p>
      )}
    </div>
  );
}
