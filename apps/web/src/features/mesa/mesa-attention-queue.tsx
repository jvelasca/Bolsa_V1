/**
 * Cola de atención urgente (NIVEL 3 + V1.16 una CTA).
 */

import { Link } from "react-router-dom";
import type { MesaAttentionItemV1 } from "@bolsa/shared";
import { mapMesaNextAction } from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import { buildInstrumentIdBySymbol } from "@bolsa/shared";
import type { DecisionBoardV1 } from "@bolsa/shared";
import { mesaJournalTesisHref } from "@/features/mesa/mesa-nav-links";

function primaryCtaForAttention(item: MesaAttentionItemV1) {
  const next = mapMesaNextAction({
    attentionKind: item.kind,
    protectPlan: item.protectPlan,
    exitSuggestedAction:
      item.exitRadar?.status === "exit_hint" ? "full_exit" : null,
  });

  const instrumentId = item.symbol;

  if (next.kind === "protect" || next.kind === "review") {
    return (
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => openConfirmDrawer()}
        data-testid={`mesa-attention-cta-${instrumentId}`}
      >
        {next.label}
      </Button>
    );
  }
  if (next.kind === "review_proposal") {
    return (
      <Link
        to={CONFIRM_PATH}
        className="inline-flex h-8 items-center rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:bg-primary/90"
        data-testid={`mesa-attention-cta-${instrumentId}`}
      >
        {next.label}
      </Link>
    );
  }
  if (next.kind === "review_filter") {
    return <span className="text-xs text-muted-foreground">{next.label}</span>;
  }
  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      onClick={() => openConfirmDrawer()}
      data-testid={`mesa-attention-cta-${instrumentId}`}
    >
      Revisar
    </Button>
  );
}

export function MesaAttentionQueue({
  items,
  board,
}: {
  items: MesaAttentionItemV1[];
  board: DecisionBoardV1 | null | undefined;
}) {
  if (items.length === 0) return null;

  const bySymbol = buildInstrumentIdBySymbol(board);

  return (
    <Card data-testid="mesa-attention-queue" role="status" aria-live="polite">
      <CardHeader className="pb-2">
        <CardTitle className="text-base text-rose-700 dark:text-rose-300">
          Requiere atención
        </CardTitle>
        <CardDescription>
          {items.length} acción{items.length === 1 ? "" : "es"} urgente
          {items.length === 1 ? "" : "s"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 p-0 pb-4">
        {items.map((item) => {
          const instrumentId = bySymbol.get(item.symbol.toUpperCase()) ?? null;
          return (
            <div
              key={item.id ?? `${item.symbol}-${item.kind ?? "attn"}`}
              className="border-t border-border px-4 pt-3 first:border-t-0 first:pt-0"
              data-testid={`mesa-attention-${item.symbol}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{item.symbol}</p>
                  <p className="text-sm text-muted-foreground">{item.reason}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {primaryCtaForAttention(item)}
                  {instrumentId ? (
                    <Link
                      to={mesaJournalTesisHref(instrumentId, { ficha: true })}
                      className="text-[10px] text-primary hover:underline"
                    >
                      Ver tesis
                    </Link>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
