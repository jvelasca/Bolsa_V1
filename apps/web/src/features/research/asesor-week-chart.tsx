/**
 * Asesor → Diario · gráfico y lista de la semana — slice A3.
 *
 * Barras = operaciones del día; línea = evolución del balance. Movido TAL CUAL
 * desde `asesor-daily-ops-panel.tsx` (mismo marcado, mismos textos).
 */

import type { DailyOpsWeekDayV1 } from "@bolsa/shared";
import { absentDataLabel } from "@/components/absent-data";
import { asDeclaredList } from "@/features/research/asesor-daily-ops-guards";

function WeekActivityChart({ week }: { week: readonly DailyOpsWeekDayV1[] }) {
  const maxT = Math.max(1, ...week.map((d) => d.tradeCount));
  const bals = week
    .map((d) => d.balanceAfter)
    .filter((v): v is number => v != null);
  const minB = bals.length ? Math.min(...bals) : 0;
  const maxB = bals.length ? Math.max(...bals) : 1;
  const span = Math.max(1e-6, maxB - minB);
  const w = 280;
  const h = 64;
  const pad = 4;
  const pts = week
    .map((d, i) => {
      if (d.balanceAfter == null) return null;
      const x = pad + (i / Math.max(1, week.length - 1)) * (w - pad * 2);
      const y = h - pad - ((d.balanceAfter - minB) / span) * (h - pad * 2);
      return `${x},${y}`;
    })
    .filter(Boolean)
    .join(" ");

  return (
    <div className="space-y-2">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-16 w-full"
        role="img"
        aria-label="Evolución semanal"
      >
        <defs>
          <linearGradient id="opsWeekFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(16 185 129)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="rgb(16 185 129)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {pts ? (
          <>
            <polyline
              fill="none"
              stroke="rgb(16 185 129)"
              strokeWidth="2"
              points={pts}
            />
          </>
        ) : null}
        {week.map((d, i) => {
          const x = pad + (i / Math.max(1, week.length - 1)) * (w - pad * 2);
          const barH = (d.tradeCount / maxT) * (h - 16);
          return (
            <rect
              key={d.date}
              x={x - 4}
              y={h - 8 - barH}
              width={8}
              height={Math.max(2, barH)}
              rx={1}
              className="fill-sky-500/50"
            />
          );
        })}
      </svg>
      <div className="flex justify-between text-[9px] tabular-nums text-muted-foreground">
        {week.map((d) => (
          <span key={d.date} className="w-8 text-center">
            {d.date.slice(8)}
          </span>
        ))}
      </div>
    </div>
  );
}

export function AsesorWeekChart({
  week,
}: {
  /** `null` = el parte no trajo la semana. No se dibuja un SVG inventando días. */
  week: readonly DailyOpsWeekDayV1[] | null | undefined;
}) {
  const days = asDeclaredList<DailyOpsWeekDayV1>(week);
  return (
    <section className="space-y-2 rounded-xl border border-border bg-card p-4 lg:col-span-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">
          Semana en curso
        </h3>
        <p className="text-[10px] text-muted-foreground">
          Barras = operaciones · línea = evolución del balance
        </p>
      </div>
      {days && days.length > 0 ? (
        <WeekActivityChart week={days} />
      ) : (
        <p
          className="text-xs text-muted-foreground"
          data-testid="asesor-week-absent"
        >
          {days
            ? "Sin movimientos registrados esta semana."
            : `${absentDataLabel()} · el parte del día no trajo la semana.`}
        </p>
      )}
    </section>
  );
}
