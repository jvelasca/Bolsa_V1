/**
 * Estado de sesión — No operar / Selectivo / Operativo (NIVEL 1).
 */

import type { MesaSessionStateV1 } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { NoTradeSessionButton } from "@/features/operations/no-trade-session-button";

const TONE_CLASS: Record<MesaSessionStateV1["tone"], string> = {
  blocked: "border-rose-500/40 bg-rose-500/10 text-rose-950 dark:text-rose-100",
  selective:
    "border-amber-500/40 bg-amber-500/10 text-amber-950 dark:text-amber-100",
  operational:
    "border-emerald-500/40 bg-emerald-500/10 text-emerald-950 dark:text-emerald-100",
};

export function MesaSessionStateCard({
  session,
}: {
  session: MesaSessionStateV1;
}) {
  return (
    <div
      className={cn("rounded-md border px-4 py-3", TONE_CLASS[session.tone])}
      data-testid="mesa-session-state"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide opacity-80">
            Estado de la sesión
          </p>
          <p className="mt-1 text-base font-semibold">{session.headline}</p>
          <p className="mt-1 text-sm opacity-90">{session.detail}</p>
          {session.regimeHint ? (
            <p className="mt-1 text-xs opacity-75">
              Régimen: {session.regimeHint}
            </p>
          ) : null}
        </div>
        <NoTradeSessionButton />
      </div>
    </div>
  );
}
