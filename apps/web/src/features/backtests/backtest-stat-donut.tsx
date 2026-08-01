/** Compact win/loss or money donut with legend captions. */
export function BacktestStatDonut({
  positive,
  negative,
  positiveCaption,
  negativeCaption,
  centerLabel,
  title,
  size = 44,
}: {
  positive: number;
  negative: number;
  positiveCaption: string;
  negativeCaption: string;
  centerLabel?: string;
  title: string;
  size?: number;
}) {
  const total = positive + negative;
  const stroke = size >= 44 ? 7 : 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const posFrac = total > 0 ? positive / total : 0;
  const posLen = posFrac * c;
  const posPct = total > 0 ? Math.round((positive / total) * 100) : 0;
  const negPct = total > 0 ? 100 - posPct : 0;

  return (
    <div className="flex items-center gap-1.5" title={title}>
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={total > 0 ? '#f43f5e' : 'rgba(148,163,184,0.25)'}
            strokeWidth={stroke}
          />
          {total > 0 && posLen > 0 && (
            <circle
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke="#34d399"
              strokeWidth={stroke}
              strokeDasharray={`${posLen} ${c - posLen}`}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
            />
          )}
        </svg>
        {centerLabel != null && (
          <span className="pointer-events-none absolute inset-0 flex items-center justify-center text-[9px] font-semibold tabular-nums text-foreground">
            {centerLabel}
          </span>
        )}
      </div>
      <div className="min-w-0 text-[11px] leading-tight">
        <p className="tabular-nums text-emerald-400">
          {positiveCaption}{' '}
          <span className="text-emerald-300/90">({posPct}%)</span>
        </p>
        <p className="tabular-nums text-rose-400">
          {negativeCaption}{' '}
          <span className="text-rose-300/90">({negPct}%)</span>
        </p>
      </div>
    </div>
  );
}
