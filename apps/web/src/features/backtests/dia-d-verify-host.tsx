/**
 * Host LAB para Verificar D→hoy (banner + película).
 * Montado en Backtesting · Análisis técnico (ADR-019 U2).
 */

import { DiaDVerifyBanner } from '@/features/trading/trading-dia-d-banner';
import { TradingDiaDReplayPanel } from '@/features/trading/trading-dia-d-replay-panel';
import { useDiaDTradingSessionStore } from '@/stores/dia-d-trading-session-store';

export function DiaDVerifyHost({
  fullBleed = false,
}: {
  /** Solo banner+replay (pantalla completa dentro del hub). */
  fullBleed?: boolean;
}) {
  const session = useDiaDTradingSessionStore((s) => s.session);
  if (!session) return null;

  if (fullBleed || session.fullBleedMovie) {
    return (
      <div
        className="flex min-h-0 flex-1 flex-col overflow-hidden"
        data-testid="dia-d-verify-full-bleed"
      >
        <DiaDVerifyBanner />
        <TradingDiaDReplayPanel />
      </div>
    );
  }

  return (
    <div
      className="flex min-h-0 flex-1 flex-col overflow-hidden"
      data-testid="dia-d-verify-host"
    >
      <DiaDVerifyBanner />
      <div className="min-h-0 flex-1 overflow-hidden">
        <TradingDiaDReplayPanel />
      </div>
    </div>
  );
}
