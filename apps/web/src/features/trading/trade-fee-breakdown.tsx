import type { AccountSettings, TradeFeeBreakdownDto } from '@bolsa/shared';
import { calculateTradeFees } from '@bolsa/shared';
import { formatPrice } from '@/features/charts/chart-utils';
import { cn } from '@/lib/utils';

interface TradeFeeBreakdownProps {
  notional: number;
  settings: AccountSettings;
  currency: string;
  isFxConversion?: boolean;
  className?: string;
}

function FeeLine({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: number;
  emphasis?: boolean;
}) {
  if (value <= 0) return null;
  return (
    <div className="flex justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn('tabular-nums', emphasis && 'font-medium text-foreground')}>
        {formatPrice(value)}
      </span>
    </div>
  );
}

function SideBlock({
  side,
  fees,
  notional,
  currency,
}: {
  side: 'buy' | 'sell';
  fees: TradeFeeBreakdownDto;
  notional: number;
  currency: string;
}) {
  const totalDebit = side === 'buy' ? notional + fees.total : fees.total;
  return (
    <div className="rounded border border-border/80 bg-background/50 p-2">
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {side === 'buy' ? 'Compra' : 'Venta'}
      </p>
      <div className="space-y-0.5">
        {side === 'buy' && (
          <div className="flex justify-between gap-2">
            <span className="text-muted-foreground">Importe operación</span>
            <span className="tabular-nums">{formatPrice(notional)}</span>
          </div>
        )}
        <FeeLine label="Comisión" value={fees.commission} />
        <FeeLine label="IVA comisión" value={fees.vatOnCommission} />
        <FeeLine label="Transmisiones" value={fees.stampDuty} />
        <FeeLine label="Conversión FX" value={fees.fxConversion} />
        <div className="mt-1 flex justify-between gap-2 border-t border-border/60 pt-1">
          <span className="text-muted-foreground">
            {side === 'buy' ? 'Coste total estimado' : 'Comisiones'}
          </span>
          <span className="font-medium tabular-nums text-foreground">
            {formatPrice(side === 'buy' ? totalDebit : fees.total)} {currency}
          </span>
        </div>
      </div>
    </div>
  );
}

export function TradeFeeBreakdown({
  notional,
  settings,
  currency,
  isFxConversion = false,
  className,
}: TradeFeeBreakdownProps) {
  if (!Number.isFinite(notional) || notional <= 0) {
    return (
      <p className={cn('text-xs text-muted-foreground', className)}>
        Indica volumen para ver comisiones estimadas.
      </p>
    );
  }

  const buyFees = calculateTradeFees(notional, 'buy', settings, {
    currency,
    isFxConversion,
  });
  const sellFees = calculateTradeFees(notional, 'sell', settings, {
    currency,
    isFxConversion,
  });

  return (
    <div className={cn('space-y-2 text-xs', className)}>
      <p className="text-muted-foreground">
        Perfil: <span className="text-foreground">{settings.commission.label}</span>
        {' · '}
        Fiscal {settings.tax.jurisdiction}
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        <SideBlock side="buy" fees={buyFees} notional={notional} currency={currency} />
        <SideBlock side="sell" fees={sellFees} notional={notional} currency={currency} />
      </div>
    </div>
  );
}
