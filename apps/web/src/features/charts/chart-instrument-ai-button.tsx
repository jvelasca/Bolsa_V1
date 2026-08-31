/**
 * Botón IA en la barra del gráfico: propose del valor activo → cola F3 → Ayuda Plataforma IA.
 * Gates SEMI / Estudio / sizing (misma disciplina que Operativa y Alarm).
 * Incluye botón informativo «IA» (qué hace / qué no).
 */

import { useMutation } from "@tanstack/react-query";
import { BrainCircuit, Loader2 } from "lucide-react";

import { useActiveAccount } from "@/features/accounts/use-active-account";
import { IconButton } from "@/components/ui/icon-button";
import { AiInfoButton } from "@/features/ai/ai-info-button";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";
import { useMesaEntriesBlocked } from "@/features/mesa/use-mesa-entries-blocked";
import { proposeInstrumentSupervised } from "@/features/trading/propose-instrument-supervised";
import { useAlertsStore } from "@/stores/alerts-store";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";
import { cn } from "@/lib/utils";
import { ENTRIES_BLOCKED_PROPOSE_MSG } from "@bolsa/shared";

export function ChartInstrumentAiButton({
  instrumentId,
  symbol,
  className,
}: {
  instrumentId?: string;
  symbol: string;
  className?: string;
}) {
  const { effectiveAccountId } = useActiveAccount();
  const { entriesBlocked } = useMesaEntriesBlocked();
  const pushToast = useAlertsStore((s) => s.pushToast);
  const enqueue = useSupervisedF3QueueStore((s) => s.enqueue);
  const setActive = useSupervisedF3QueueStore((s) => s.setActive);

  const study = useMutation({
    mutationFn: async () => {
      if (!instrumentId) throw new Error("Sin instrumento");
      if (!effectiveAccountId) throw new Error("Sin cuenta DEMO activa");
      return proposeInstrumentSupervised({
        instrumentId,
        symbol,
        accountId: effectiveAccountId,
        source: "chart",
        entriesBlocked,
      });
    },
    onSuccess: (payload) => {
      const id = enqueue(payload, {
        symbol: payload.symbol ?? symbol,
        origin: "chart",
      });
      setActive(id);
      pushToast(
        `IA · ${payload.symbol ?? symbol}: ${payload.action} → Supervisado F3`,
      );
      openConfirmDrawer();
    },
    onError: (e: Error) => {
      pushToast(`IA · ${symbol}: ${e.message}`);
    },
  });

  const pending = study.isPending;
  const disabled = !instrumentId || pending || entriesBlocked;

  return (
    <div className={cn("inline-flex items-center gap-0.5", className)}>
      <AiInfoButton surface="chart_propose" className="h-7 px-1" />
      <IconButton
        icon={pending ? Loader2 : BrainCircuit}
        title={
          pending
            ? `Evaluando IA · ${symbol}…`
            : entriesBlocked
              ? ENTRIES_BLOCKED_PROPOSE_MSG
              : !instrumentId
                ? "Información IA del valor (carga el instrumento)"
                : `Estudio IA · ${symbol} (propose → Supervisado F3)`
        }
        disabled={disabled}
        onClick={() => study.mutate()}
        className={cn(pending && "[&_svg]:animate-spin")}
      />
    </div>
  );
}
