/**
 * Chip de universo LAB / TRADING — siempre visible en contextos ambiguos (ADR-019 U1).
 */

import { FlaskConical, LineChart } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  PRODUCT_UNIVERSE_LABEL,
  PRODUCT_UNIVERSE_SUBLABEL,
  productUniverseFromPath,
  type ProductUniverse,
} from '@/features/platform/product-universe';
import { useDiaDTradingSessionStore } from '@/stores/dia-d-trading-session-store';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import type { InvestmentAccountDto } from '@bolsa/shared';

function tradingSublabel(accountType: InvestmentAccountDto['type'] | undefined): string {
  if (accountType === 'paper') return 'PAPER';
  if (accountType === 'live') return 'LIVE';
  return PRODUCT_UNIVERSE_SUBLABEL.trading;
}

export function UniverseChip({
  force,
  className,
}: {
  /** Override detection from route (e.g. verify session on /backtests). */
  force?: ProductUniverse;
  className?: string;
}) {
  const { pathname } = useLocation();
  const session = useDiaDTradingSessionStore((s) => s.session);
  const { account } = useActiveAccount();
  const fromPath = productUniverseFromPath(pathname);
  const universe = force ?? fromPath;
  if (!universe) return null;

  const verifying = Boolean(session) && universe === 'lab';
  const Icon = universe === 'lab' ? FlaskConical : LineChart;
  const sub =
    universe === 'lab'
      ? verifying
        ? 'verificación'
        : PRODUCT_UNIVERSE_SUBLABEL.lab
      : tradingSublabel(account?.type);

  return (
    <span
      className={cn(
        'inline-flex max-w-[160px] items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide',
        universe === 'lab'
          ? 'border-sky-600/35 bg-sky-500/10 text-sky-950 dark:text-sky-50'
          : 'border-emerald-600/35 bg-emerald-500/10 text-emerald-950 dark:text-emerald-50',
        className,
      )}
      title={
        universe === 'lab'
          ? 'Universo LAB — investigación y simulaciones (no escribe DEMO)'
          : 'Universo TRADING — inversión diaria en la cuenta activa'
      }
      data-testid="universe-chip"
      data-universe={universe}
    >
      <Icon className="h-3 w-3 shrink-0" aria-hidden />
      <span className="truncate">
        {PRODUCT_UNIVERSE_LABEL[universe]}
        <span className="font-normal opacity-80"> · {sub}</span>
      </span>
    </span>
  );
}
