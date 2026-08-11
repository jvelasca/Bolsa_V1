import type { AccountSettings } from "@bolsa/shared";
import { calculateTradeFees } from "@bolsa/shared";
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";

export interface TradeConfirmDetails {
  symbol: string;
  name?: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  instrumentCurrency: string;
  accountCurrency: string;
  accountName?: string | null;
  notional: number;
  settings: AccountSettings;
  isFxConversion?: boolean;
  orderLabel?: string;
}

interface TradeConfirmPanelProps {
  details: TradeConfirmDetails;
  error?: string | null;
  isPending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function TradeConfirmPanel({
  details,
  error,
  isPending = false,
  onConfirm,
  onCancel,
}: TradeConfirmPanelProps) {
  const {
    symbol,
    name,
    side,
    quantity,
    price,
    instrumentCurrency,
    accountCurrency,
    accountName,
    notional,
    settings,
    isFxConversion = false,
    orderLabel,
  } = details;

  const fees = calculateTradeFees(notional, side, settings, {
    currency: accountCurrency,
    isFxConversion,
  });
  const totalDebit =
    side === "buy" ? notional + fees.total : notional - fees.total;
  const sideLabel = side === "buy" ? "Compra" : "Venta";

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-primary/30 bg-primary/5 p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-primary">
          Confirmar {orderLabel ?? sideLabel.toLowerCase()}
        </p>
        <p className="mt-2 text-lg font-semibold">
          {sideLabel} {quantity} × {symbol}
        </p>
        {name && <p className="text-sm text-muted-foreground">{name}</p>}
        <p className="mt-1 text-sm tabular-nums">
          Precio: {formatPrice(price)} {instrumentCurrency}
          {accountName && (
            <span className="ml-2 text-muted-foreground">
              · Cuenta {accountName} ({accountCurrency})
            </span>
          )}
        </p>
      </div>

      <div className="space-y-1.5 rounded-md border border-border bg-muted/20 p-3 text-xs">
        <div className="flex justify-between gap-2">
          <span className="text-muted-foreground">Importe operación</span>
          <span className="tabular-nums">
            {formatPrice(notional)} {accountCurrency}
          </span>
        </div>
        {fees.commission > 0 && (
          <div className="flex justify-between gap-2">
            <span className="text-muted-foreground">Comisión</span>
            <span className="tabular-nums">{formatPrice(fees.commission)}</span>
          </div>
        )}
        {fees.vatOnCommission > 0 && (
          <div className="flex justify-between gap-2">
            <span className="text-muted-foreground">IVA comisión</span>
            <span className="tabular-nums">
              {formatPrice(fees.vatOnCommission)}
            </span>
          </div>
        )}
        {fees.stampDuty > 0 && (
          <div className="flex justify-between gap-2">
            <span className="text-muted-foreground">Transmisiones</span>
            <span className="tabular-nums">{formatPrice(fees.stampDuty)}</span>
          </div>
        )}
        {fees.fxConversion > 0 && (
          <div className="flex justify-between gap-2">
            <span className="text-muted-foreground">Conversión FX</span>
            <span className="tabular-nums">
              {formatPrice(fees.fxConversion)}
            </span>
          </div>
        )}
        <div className="flex justify-between gap-2 border-t border-border/60 pt-1.5 font-medium">
          <span>
            {side === "buy"
              ? "Total a debitar (est.)"
              : "Neto estimado en cuenta"}
          </span>
          <span className="tabular-nums">
            {formatPrice(side === "buy" ? notional + fees.total : totalDebit)}{" "}
            {accountCurrency}
          </span>
        </div>
        <p className="pt-1 text-[10px] text-muted-foreground">
          Perfil: {settings.commission.label} · Fiscal{" "}
          {settings.tax.jurisdiction}
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex gap-2">
        <button
          type="button"
          disabled={isPending}
          onClick={onCancel}
          className="flex-1 rounded-md border border-border px-4 py-2.5 text-sm hover:bg-accent disabled:opacity-50"
        >
          Cancelar
        </button>
        <button
          type="button"
          disabled={isPending}
          onClick={onConfirm}
          className={cn(
            "flex-1 rounded-md px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50",
            side === "buy"
              ? "bg-emerald-600 hover:bg-emerald-500"
              : "bg-red-600 hover:bg-red-500",
          )}
        >
          {isPending ? "Ejecutando…" : `Confirmar ${sideLabel.toLowerCase()}`}
        </button>
      </div>
    </div>
  );
}
