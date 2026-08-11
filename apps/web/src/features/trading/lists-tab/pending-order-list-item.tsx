import type { PendingOrderDto } from "@bolsa/shared";
import { formatPrice } from "@/features/charts/chart-utils";
import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/lib/utils";
import { usePendingOrders } from "@/features/trading/use-pending-orders";
import { X } from "lucide-react";

interface PendingOrderListItemProps {
  order: PendingOrderDto;
  isChartActive: boolean;
  onOpenChart: () => void;
}

export function PendingOrderListItem({
  order,
  isChartActive,
  onOpenChart,
}: PendingOrderListItemProps) {
  const { removePendingOrder } = usePendingOrders();
  const sideLabel = order.side === "buy" ? "Compra" : "Venta";

  return (
    <div
      className={cn(
        "flex items-center gap-0.5 border-b border-border/60 px-1 py-1",
        isChartActive && "bg-primary/5",
      )}
    >
      <button
        type="button"
        className="min-w-0 flex-1 text-left"
        onClick={onOpenChart}
      >
        <div className="flex items-baseline justify-between gap-1">
          <div className="min-w-0 truncate">
            <span className="text-xs font-semibold">{order.symbol}</span>
            <span className="ml-1 text-[10px] text-muted-foreground">
              {sideLabel} limitada · {order.quantity} @{" "}
              {formatPrice(order.limitPrice)}
            </span>
          </div>
          <span className="shrink-0 text-[10px] text-amber-400">Pendiente</span>
        </div>
      </button>
      <IconButton
        icon={X}
        title="Cancelar orden"
        className="text-muted-foreground hover:text-destructive"
        onClick={() => void removePendingOrder(order.id)}
      />
    </div>
  );
}
