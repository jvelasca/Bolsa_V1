/**
 * Banner + badge LIVE VIRTUAL · SIMULADO (Confirm / ticket manual).
 * Obligatorio cuando venue live o camino execute LIVE.
 */

import { cn } from "@/lib/utils";

export const LIVE_VIRTUAL_BANNER_TEXT =
  "LIVE VIRTUAL · SIMULADO · no capital real";

export const LIVE_VIRTUAL_BANNER_SUB =
  "Respuesta del broker = simulada · submitted ≠ fill real";

export const LIVE_VIRTUAL_BADGE_LABEL = "LIVE VIRTUAL · SIMULADO";

export const LIVE_VIRTUAL_BADGE_TITLE =
  "LIVE VIRTUAL · SIMULADO · no capital real · submitted ≠ fill · trading not accepted";

type LiveVirtualBannerProps = {
  className?: string;
  /** Compact: una línea (drawer / badge row). */
  compact?: boolean;
};

export function LiveVirtualBanner({
  className,
  compact = false,
}: LiveVirtualBannerProps) {
  return (
    <div
      className={cn(
        "rounded-md border border-sky-500/45 bg-sky-500/10 px-3 py-2 text-sky-950 dark:text-sky-50",
        className,
      )}
      data-testid="live-virtual-banner"
      role="status"
    >
      <p className="text-[11px] font-semibold uppercase tracking-wide">
        {LIVE_VIRTUAL_BANNER_TEXT}
      </p>
      {!compact ? (
        <p className="mt-0.5 text-[10px] opacity-90">
          {LIVE_VIRTUAL_BANNER_SUB}
        </p>
      ) : null}
    </div>
  );
}

type LiveVirtualVenueBadgeProps = {
  className?: string;
  /** testid: confirm-live-venue-badge | manual-live-venue-badge */
  testId?: string;
};

export function LiveVirtualVenueBadge({
  className,
  testId = "confirm-live-venue-badge",
}: LiveVirtualVenueBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-900 dark:text-sky-100",
        className,
      )}
      data-testid={testId}
      title={LIVE_VIRTUAL_BADGE_TITLE}
    >
      {LIVE_VIRTUAL_BADGE_LABEL}
    </span>
  );
}
