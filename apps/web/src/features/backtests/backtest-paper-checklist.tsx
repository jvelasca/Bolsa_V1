import { useEffect, useMemo, useState } from 'react';
import type { BacktestRunDetailDto, ResearchTrialDto } from '@bolsa/shared';
import {
  oosEvidenceToPaperLabSnapshot,
  resolveOosEvidence,
} from '@/features/backtests/backtest-oos-evidence';
import {
  buildPaperGate,
  requiredAckIds,
  type PaperCheckId,
} from '@/features/backtests/backtest-paper-gate';
import { Button } from '@/components/ui/button';
import { PAPER_PATH_LAB } from '@/features/settings/paper-paths-copy';
import { cn } from '@/lib/utils';
import type { PaperLabEvidenceSnapshot } from '@bolsa/shared';

type Props = {
  detail: BacktestRunDetailDto;
  excessReturnPct: number | null;
  buyHoldReturnPct: number | null;
  linkedTrial?: ResearchTrialDto | null;
  deploying?: boolean;
  onDeploy: (payload: { labEvidence: PaperLabEvidenceSnapshot }) => void;
};

function statusDot(status: string) {
  if (status === 'pass') return 'bg-success';
  if (status === 'fail') return 'bg-destructive';
  if (status === 'warn') return 'bg-amber-500';
  return 'bg-sky-500';
}

export function BacktestPaperChecklist({
  detail,
  excessReturnPct,
  buyHoldReturnPct,
  linkedTrial = null,
  deploying,
  onDeploy,
}: Props) {
  const oosEvidence = useMemo(
    () =>
      resolveOosEvidence({
        trial: linkedTrial,
        strategyId: detail.strategyDefinitionId,
      }),
    [detail.strategyDefinitionId, linkedTrial],
  );
  const gate = useMemo(
    () => buildPaperGate({ detail, excessReturnPct, buyHoldReturnPct, oosEvidence }),
    [buyHoldReturnPct, detail, excessReturnPct, oosEvidence],
  );
  const needAck = useMemo(() => requiredAckIds(gate.checks), [gate.checks]);
  const [acks, setAcks] = useState<Partial<Record<PaperCheckId, boolean>>>({});

  useEffect(() => {
    setAcks({});
  }, [detail.id]);

  const allAcked = needAck.every((id) => acks[id]);
  const ready = gate.canDeploy && allAcked;

  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/15 px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p
            className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
            title="Puerta de servicio: no declara la estrategia lista para invertir. Solo evita desplegar a ciegas."
          >
            {PAPER_PATH_LAB.checklistTitle}
          </p>
          <p className="mt-1 text-sm text-foreground">
            {PAPER_PATH_LAB.blurb}
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          disabled={!ready || deploying}
          onClick={() =>
            onDeploy({
              labEvidence: oosEvidenceToPaperLabSnapshot(oosEvidence, {
                sourceBacktestRunId: detail.id,
                trialId: linkedTrial?.id,
              }),
            })
          }
        >
          {deploying ? 'Creando…' : PAPER_PATH_LAB.cta}
        </Button>
      </div>

      <ul className="space-y-2">
        {gate.checks.map((check) => (
          <li
            key={check.id}
            className="flex gap-2 rounded-md border border-border/60 bg-background/40 px-2 py-2 text-xs"
          >
            <span
              className={cn('mt-1 h-2 w-2 shrink-0 rounded-full', statusDot(check.status))}
              aria-hidden
            />
            <div className="min-w-0 flex-1">
              <p className="font-medium text-foreground">{check.label}</p>
              <p className="text-muted-foreground">{check.detail}</p>
              {check.requiresAck && (
                <label className="mt-1.5 flex cursor-pointer items-start gap-2 text-muted-foreground">
                  <input
                    type="checkbox"
                    className="mt-0.5 rounded border-border"
                    checked={Boolean(acks[check.id])}
                    onChange={(event) =>
                      setAcks((prev) => ({ ...prev, [check.id]: event.target.checked }))
                    }
                  />
                  <span>Lo entiendo y quiero continuar</span>
                </label>
              )}
            </div>
          </li>
        ))}
      </ul>

      {!gate.canDeploy && (
        <p className="text-xs text-destructive">
          Hay bloqueos duros (p. ej. sin operaciones). Corrige el run antes de paper.
        </p>
      )}
      {gate.canDeploy && !allAcked && (
        <p className="text-xs text-muted-foreground">
          Marca las casillas de aviso para habilitar el despliegue.
        </p>
      )}
    </div>
  );
}
