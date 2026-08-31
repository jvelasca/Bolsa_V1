import type {
  InstrumentDto,
  InstrumentWithMetaDto,
  OhlcvBarDto,
} from "@bolsa/shared";
import { ENTRIES_BLOCKED_PROPOSE_MSG } from "@bolsa/shared";
import { useMesaEntriesBlocked } from "@/features/mesa/use-mesa-entries-blocked";
import { cn } from "@/lib/utils";

function barChangePct(bar: OhlcvBarDto): number | null {
  if (!bar.open) return null;
  return ((bar.close - bar.open) / bar.open) * 100;
}

export function instrumentForQuickTrade(
  instrument: InstrumentDto,
  bars: OhlcvBarDto[],
): InstrumentWithMetaDto {
  const last = bars.at(-1);
  const prev = bars.length > 1 ? bars.at(-2) : null;
  const changePct =
    last && prev && prev.close
      ? ((last.close - prev.close) / prev.close) * 100
      : last
        ? barChangePct(last)
        : null;

  return {
    ...instrument,
    meta: {
      barCount: bars.length,
      lastSync: null,
      lastClose: last?.close ?? null,
      changePct,
    },
  };
}

export function ChartQuickTradeButtons({
  onBuy,
  onSell,
}: {
  onBuy: () => void;
  onSell: () => void;
}) {
  const { entriesBlocked } = useMesaEntriesBlocked();
  return (
    <div className="flex shrink-0 items-center gap-1">
      <button
        type="button"
        title="Venta rápida"
        onClick={onSell}
        className="rounded border border-red-500/50 bg-red-600/90 px-2 py-0.5 text-[10px] font-semibold text-white hover:bg-red-600"
      >
        V
      </button>
      <button
        type="button"
        title={entriesBlocked ? ENTRIES_BLOCKED_PROPOSE_MSG : "Compra rápida"}
        disabled={entriesBlocked}
        onClick={onBuy}
        className={cn(
          "rounded border border-emerald-500/50 bg-emerald-600/90 px-2 py-0.5 text-[10px] font-semibold text-white hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-50",
        )}
      >
        C
      </button>
    </div>
  );
}
