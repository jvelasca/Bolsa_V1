/**
 * Banner LAB · Verificar D→hoy — sandbox Cartera LAB ≠ DEMO.
 *
 * Selector Manual / Semi / Auto · Pantalla completa · Volver Finalistas · Salir.
 *
 * @see docs/adr/019-dual-universes-lab-vs-trading.md
 * @see docs/engineering/backtesting-dia-d-premises-2026-07-31.md §3c
 */

import { Link } from "react-router-dom";
import {
  DIA_D_MODE_LABELS,
  useDiaDTradingSessionStore,
  type DiaDTradingMode,
} from "@/stores/dia-d-trading-session-store";
import { Button } from "@/components/ui/button";
import { UniverseChip } from "@/features/platform/universe-chip";
import { cn } from "@/lib/utils";

const MODES: DiaDTradingMode[] = ["manual", "semi", "auto"];

/** @deprecated alias — prefer DiaDVerifyBanner */
export function TradingDiaDBanner() {
  return <DiaDVerifyBanner />;
}

export function DiaDVerifyBanner() {
  const session = useDiaDTradingSessionStore((s) => s.session);
  const setMode = useDiaDTradingSessionStore((s) => s.setMode);
  const setFullBleedMovie = useDiaDTradingSessionStore(
    (s) => s.setFullBleedMovie,
  );
  const exitSession = useDiaDTradingSessionStore((s) => s.exitSession);

  if (!session) return null;

  const fullBleed = Boolean(session.fullBleedMovie);

  return (
    <div
      className="flex shrink-0 flex-wrap items-center gap-2 border-b-2 border-red-600 bg-red-600 px-3 py-2 text-[11px] text-white shadow-sm"
      role="status"
      data-testid="dia-d-verify-banner"
    >
      <UniverseChip force="lab" />
      <span className="font-bold tracking-wide">Verificar D→hoy · DÍA D</span>
      <span className="opacity-95">
        {session.symbol} · #{session.rank} {session.strategyLabel} ·{" "}
        {session.diaD} → {session.endDate}
      </span>
      <span className="opacity-90">Cartera LAB · no escribe DEMO</span>

      <div className="flex items-center gap-0.5 rounded-md border border-white/35 bg-black/15 p-0.5">
        {MODES.map((mode) => (
          <button
            key={mode}
            type="button"
            className={cn(
              "rounded px-2 py-0.5 text-[10px] font-medium",
              session.mode === mode
                ? "bg-white text-red-700"
                : "text-white/90 hover:bg-white/15",
            )}
            title={
              mode === "auto"
                ? "Fills automáticos según #1"
                : mode === "semi"
                  ? "Pausa en señales → Aceptar/Rechazar (reescribe equity)"
                  : "▶ / pasos + gate Aceptar/Rechazar (reescribe equity)"
            }
            onClick={() => setMode(mode)}
          >
            {DIA_D_MODE_LABELS[mode]}
          </button>
        ))}
      </div>

      <span className="ml-auto flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant={fullBleed ? "default" : "outline"}
          className={cn(
            "h-6 px-2 text-[10px]",
            !fullBleed &&
              "border-white/50 bg-white/10 text-white hover:bg-white/20",
          )}
          title={
            fullBleed
              ? "Volver al layout del hub Backtesting"
              : "Película a pantalla completa"
          }
          onClick={() => setFullBleedMovie(!fullBleed)}
        >
          {fullBleed ? "Salir pantalla completa" : "Pantalla completa"}
        </Button>
        <Link
          to={`/backtests?tab=run&instrumentId=${encodeURIComponent(session.instrumentId)}&focus=finalists`}
          className="font-medium text-white underline-offset-2 hover:underline"
        >
          Volver a Finalistas
        </Link>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-6 border-white/50 bg-white/10 px-2 text-[10px] text-white hover:bg-white/20"
          onClick={() => exitSession()}
        >
          Salir verificación
        </Button>
      </span>
    </div>
  );
}
