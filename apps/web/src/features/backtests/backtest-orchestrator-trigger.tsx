/**
 * R2 — disparador GOBERNADO del embudo AUTO desde Finalistas (auditoría LAB 2026-11-16).
 *
 * El embudo (ESTUDIO → LAB → TOP3 → COACH → FINALISTA) solo era alcanzable de noche y
 * con un flag OFF. Este botón lo ejecuta a demanda con las reglas del contrato:
 *
 * - **`dryRun` visible y por defecto ON**: la simulación no escribe nada del lifecycle;
 *   el recibo declara qué se habría escrito.
 * - **Techo FINALISTA**: el recibo no puede traer `promoted`, y `phaseReached` es como
 *   máximo `finalista`. ACTIVE sigue pasando por `decide_promotion` (worker), nunca aquí.
 * - **Recibo, no promesa**: fase, gates evaluados, `runId` e idempotencia (`replayed`).
 *   Un `INCOMPLETE` se muestra como tal con sus motivos: `UNKNOWN ≠ 0`, `INCOMPLETE ≠ OK`.
 *
 * @see docs/adr/053-disparador-gobernado-embudo-auto.md
 */

import { useState } from "react";
import { Loader2, Play } from "lucide-react";
import { absentDataLabel } from "@/components/absent-data";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

type GateReceipt = {
  gate: string;
  status?: string | null;
  detail?: string | null;
};

type Receipt = {
  runId: string;
  instrumentId: string;
  accountId?: string | null;
  dryRun: boolean;
  status: string;
  phaseReached?: string | null;
  cycle: string;
  idempotencyKey: string;
  gates: GateReceipt[];
  candidates: number;
  evaluated: number;
  promoted: boolean;
  activeVersionId?: string | null;
  reasons: string[];
  writes: string[];
  replayed: boolean;
  auditEventId?: string | null;
  computedAt: string;
  notes: string[];
};

interface BacktestOrchestratorTriggerProps {
  instrumentId: string;
  symbol: string;
  className?: string;
}

/**
 * Rótulo de gate. ``not_evaluated`` NO es rojo ni verde: es «Sin dato todavía»
 * (fail-closed: un gate no evaluado no aprueba, pero tampoco se inventa un fallo).
 */
export function gateStatusLabel(status: string | null | undefined): string {
  switch (status) {
    case "pass":
      return "Cumple";
    case "fail":
      return "No cumple";
    case "not_evaluated":
    default:
      return absentDataLabel();
  }
}

function gateStatusClass(status: string | null | undefined): string {
  if (status === "pass") {
    return "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200";
  }
  if (status === "fail") {
    return "bg-rose-500/15 text-rose-900 dark:text-rose-100";
  }
  return "bg-muted text-muted-foreground";
}

export function BacktestOrchestratorTrigger({
  instrumentId,
  symbol,
  className,
}: BacktestOrchestratorTriggerProps) {
  const [dryRun, setDryRun] = useState(true);
  const [pending, setPending] = useState(false);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setPending(true);
    setError(null);
    try {
      const result = await api.runAutoOrchestrator({
        instrumentId,
        dryRun,
        toPhase: "finalista",
      });
      setReceipt(result as Receipt);
    } catch (err) {
      setReceipt(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <section
      className={cn(
        "rounded-lg border border-border/70 bg-muted/20 p-3",
        className,
      )}
      aria-label="Embudo del laboratorio"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-0.5">
          <p className="text-xs font-medium text-foreground">
            Embudo del laboratorio · {symbol || instrumentId}
          </p>
          <p className="text-[10px] leading-snug text-muted-foreground">
            ESTUDIO → LAB → TOP3 → COACH → FINALISTA. Techo FINALISTA: esta
            acción nunca escribe ACTIVE.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center gap-1.5 text-[11px] text-foreground">
            <input
              type="checkbox"
              className="h-3.5 w-3.5"
              checked={dryRun}
              onChange={(event) => setDryRun(event.target.checked)}
            />
            Simulación (dryRun)
          </label>
          <Button
            type="button"
            size="sm"
            className="h-7 gap-1 text-[11px]"
            onClick={() => void run()}
            disabled={pending || !instrumentId}
            title={
              dryRun
                ? "Ejecuta el embudo sin escribir evidencia del LAB (recibo con gates)"
                : "Ejecuta el embudo y guarda evidencia del LAB (nunca ACTIVE)"
            }
          >
            {pending ? (
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
            ) : (
              <Play className="h-3 w-3" aria-hidden />
            )}
            Ejecutar embudo
          </Button>
        </div>
      </div>

      <p className="mt-1 text-[10px] leading-snug text-muted-foreground">
        {dryRun
          ? "Simulación: no escribe nada del lifecycle; el recibo declara lo que habría escrito."
          : "Ejecución real: escribe candidatas/evaluaciones/finalista del LAB. ACTIVE queda fuera de alcance."}
      </p>

      {error ? (
        <p className="mt-2 rounded border border-destructive/40 bg-destructive/10 px-2 py-1 text-[11px] text-destructive">
          {error}
        </p>
      ) : null}

      {receipt ? (
        <div className="mt-2 space-y-1.5 rounded-md border border-border/60 bg-background px-2 py-2">
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span
              className={cn(
                "rounded px-1.5 py-0.5 font-medium",
                receipt.status === "COMPLETED"
                  ? "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200"
                  : "bg-amber-500/15 text-amber-900 dark:text-amber-100",
              )}
            >
              {receipt.status === "COMPLETED"
                ? "Completado"
                : "Incompleto (fail-closed)"}
            </span>
            <span className="text-muted-foreground">
              Fase:{" "}
              <span className="font-medium text-foreground">
                {receipt.phaseReached ?? absentDataLabel()}
              </span>
            </span>
            <span className="text-muted-foreground">
              {receipt.dryRun ? "dryRun" : "ejecución real"}
            </span>
            {receipt.replayed ? (
              <span className="rounded bg-muted px-1.5 py-0.5 text-muted-foreground">
                repetido (idempotente)
              </span>
            ) : null}
          </div>

          <p className="font-mono text-[10px] text-muted-foreground">
            {receipt.runId} · ciclo {receipt.cycle}
          </p>

          <div className="flex flex-wrap gap-1">
            {receipt.gates.length === 0 ? (
              <span className="text-[11px] text-muted-foreground">
                Gates: {absentDataLabel()}
              </span>
            ) : (
              receipt.gates.map((gate) => (
                <span
                  key={gate.gate}
                  className={cn(
                    "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium",
                    gateStatusClass(gate.status),
                  )}
                  title={gate.detail ?? undefined}
                >
                  {gate.gate} · {gateStatusLabel(gate.status)}
                </span>
              ))
            )}
          </div>

          <p className="text-[10px] leading-snug text-muted-foreground">
            {receipt.candidates} candidatas · {receipt.evaluated} evaluadas ·{" "}
            {receipt.dryRun
              ? `${receipt.writes.length} escrituras suprimidas`
              : "escritura real del LAB"}
            {receipt.promoted || receipt.activeVersionId
              ? " · contrato violado: ACTIVE escrito"
              : " · ACTIVE no escrito"}
          </p>

          {receipt.reasons.length > 0 ? (
            <p className="text-[10px] leading-snug text-amber-900 dark:text-amber-100">
              Motivos: {receipt.reasons.join(" · ")}
            </p>
          ) : null}
          {receipt.notes.length > 0 ? (
            <p className="text-[10px] leading-snug text-muted-foreground">
              {receipt.notes.join(" · ")}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
