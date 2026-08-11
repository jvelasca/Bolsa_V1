import type { BacktestRunDetailDto } from "@bolsa/shared";
import { formatDateDdMmYyyy } from "@/features/backtests/backtest-date-format";
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";

interface Props {
  detail: BacktestRunDetailDto | null | undefined;
  /** Cursor de la película: las operaciones posteriores aparecen atenuadas. */
  replayCursor: string | null;
  /** Timestamp de la operación con foco (resaltada en la tabla). */
  focusTimestamp: string | null;
  /** Pedir foco a una operación (orquestador). */
  onFocusTimestamp: (ts: string) => void;
}

/** Tabla «Operaciones» del panel DÍA D: lista de trades con reveal por
 * replay-cursor y foco en la operación destacada.
 * Extraído de `trading-dia-d-replay-panel.tsx` (feature-slicing M5). Los
 * callbacks/estado del orquestador (`replayCursor`, `focusTimestamp`,
 * `setFocusTimestamp`) se pasan como props (Diseño B), de modo que la lógica
 * de la película/gate se mantiene donde está. */
export function DiaDTradesPanel({
  detail,
  replayCursor,
  focusTimestamp,
  onFocusTimestamp,
}: Props) {
  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col gap-1 overflow-hidden p-2 text-[11px]">
      <div className="flex shrink-0 items-center justify-between gap-2">
        <h3 className="font-medium text-foreground">Operaciones</h3>
        <span className="tabular-nums text-muted-foreground">
          {detail?.tradeCount ?? 0}
          {replayCursor ? ` · hasta ${formatDateDdMmYyyy(replayCursor)}` : ""}
        </span>
      </div>
      <div className="scroll-area min-h-0 flex-1 overflow-auto rounded border border-border/60">
        <table className="w-full text-left text-[10px]">
          <thead className="sticky top-0 bg-card text-muted-foreground">
            <tr>
              <th className="px-1.5 py-1 font-medium">Fecha</th>
              <th className="px-1.5 py-1 font-medium">Tipo</th>
              <th className="px-1.5 py-1 font-medium">Precio</th>
              <th className="px-1.5 py-1 font-medium">Motivo</th>
            </tr>
          </thead>
          <tbody>
            {(detail?.trades ?? []).map((t) => {
              const revealed = !replayCursor || t.timestamp <= replayCursor;
              const focused = focusTimestamp === t.timestamp;
              return (
                <tr
                  key={t.id}
                  className={cn(
                    "cursor-pointer border-t border-border/40 tabular-nums",
                    !revealed && "opacity-40",
                    focused && "bg-amber-500/15",
                  )}
                  onClick={() => onFocusTimestamp(t.timestamp)}
                  onDoubleClick={() => onFocusTimestamp(t.timestamp)}
                >
                  <td className="px-1.5 py-0.5">
                    {formatDateDdMmYyyy(t.timestamp)}
                  </td>
                  <td
                    className={cn(
                      "px-1.5 py-0.5 font-medium uppercase",
                      t.type === "buy" ? "text-emerald-600" : "text-red-600",
                    )}
                  >
                    {t.type}
                  </td>
                  <td className="px-1.5 py-0.5">{formatPrice(t.price)}</td>
                  <td
                    className="max-w-[10rem] truncate px-1.5 py-0.5 text-muted-foreground"
                    title={
                      typeof t.reason === "string"
                        ? t.reason
                        : (t.reason?.summary ?? undefined)
                    }
                  >
                    {typeof t.reason === "string"
                      ? t.reason
                      : (t.reason?.summary ?? "—")}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!detail?.trades?.length ? (
          <p className="p-2 text-muted-foreground">
            Sin operaciones en este tramo.
          </p>
        ) : null}
      </div>
    </section>
  );
}
