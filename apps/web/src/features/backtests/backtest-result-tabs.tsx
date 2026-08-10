import { cn } from "@/lib/utils";
import type { BacktestTradeReasonDto } from "@bolsa/shared";

type ResultPane = "metrics" | "equity" | "trades" | "replay";

const PANES: { id: ResultPane; label: string }[] = [
  { id: "metrics", label: "Métricas" },
  { id: "equity", label: "Equity" },
  { id: "trades", label: "Trades" },
  { id: "replay", label: "Replay" },
];

export function BacktestResultTabs({
  value,
  onChange,
}: {
  value: ResultPane;
  onChange: (pane: ResultPane) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1 rounded-lg border border-border p-0.5">
      {PANES.map((pane) => (
        <button
          key={pane.id}
          type="button"
          onClick={() => onChange(pane.id)}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm transition-colors",
            value === pane.id
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-muted hover:text-foreground",
          )}
        >
          {pane.label}
        </button>
      ))}
    </div>
  );
}

export type { ResultPane };

export function TradeReasonPanel({
  reason,
  tradeType,
  timestamp,
}: {
  reason?: BacktestTradeReasonDto | null;
  tradeType: string;
  timestamp: string;
}) {
  const dateLabel = (() => {
    const day = timestamp.slice(0, 10);
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
    return m ? `${m[3]}/${m[2]}/${m[1]}` : timestamp;
  })();

  if (!reason) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/20 p-3 text-sm text-muted-foreground">
        No hay explicación guardada para esta{" "}
        {tradeType === "buy" ? "compra" : "venta"} ({dateLabel}). Las pruebas
        nuevas sí la incluyen — vuelve a pulsar «Probar».
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border border-border bg-muted/20 p-3">
      <div>
        <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Por qué se abrió / cerró
        </p>
        <p className="mt-1 text-sm text-foreground">{reason.summary}</p>
      </div>
      <p className="text-xs text-muted-foreground">
        {reason.presetKey ? `Preset ${reason.presetKey}` : "Estrategia custom"}
        {reason.signalKind ? ` · ${reason.signalKind}` : ""}
        {reason.side ? ` · ${reason.side}` : ""}
        {typeof reason.price === "number" ? ` · mid ${reason.price}` : ""}
      </p>
      {reason.rules && reason.rules.length > 0 && (
        <ul className="space-y-1 border-t border-border/60 pt-2">
          {reason.rules.map((rule, index) => (
            <li key={index} className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">
                {typeof rule.summary === "string"
                  ? rule.summary
                  : `Regla ${index + 1}`}
              </span>
              {typeof rule.type === "string" ? ` · ${rule.type}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
