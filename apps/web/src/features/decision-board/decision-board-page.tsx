/**
 * F0.6 — Decision Board (web, solo lectura).
 * V1.19: página redirige a Mesa; el panel vive en decision-spine-detail-panel.
 * Se mantiene el componente de página para tests hasta el redirect.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { DecisionSpineDetailPanel } from "@/features/mesa/decision-spine-detail-panel";

export function DecisionBoardPage() {
  const { effectiveAccountId } = useActiveAccount();

  const boardQuery = useQuery({
    queryKey: ["decision-board", effectiveAccountId],
    enabled: Boolean(effectiveAccountId),
    queryFn: () => api.getDecisionBoard(effectiveAccountId!),
    refetchInterval: 60_000,
  });

  const board = boardQuery.data?.data;

  return (
    <div className="space-y-4 p-4 sm:p-6" data-testid="decision-board">
      <div>
        <h1 className="font-serif text-2xl font-semibold text-foreground sm:text-3xl">
          Decision Board
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Tablero de solo lectura de oportunidades pendientes del Decision
          Spine.
        </p>
      </div>
      <DecisionSpineDetailPanel
        board={board}
        isLoading={boardQuery.isLoading}
        isError={boardQuery.isError}
        showEntryQueue={false}
      />
    </div>
  );
}
