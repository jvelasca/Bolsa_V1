import { Eye, EyeOff, Lock, LockOpen, Magnet } from "lucide-react";
import { cn } from "@/lib/utils";

const BTN =
  "flex h-7 w-7 shrink-0 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-30";

export function ChartDrawingGlobalToggles({
  magnetOn,
  onMagnetToggle,
  drawingsHidden,
  onDrawingsHiddenToggle,
  drawingsLocked,
  onDrawingsLockedToggle,
  className,
}: {
  magnetOn: boolean;
  onMagnetToggle: () => void;
  drawingsHidden: boolean;
  onDrawingsHiddenToggle: () => void;
  drawingsLocked: boolean;
  onDrawingsLockedToggle: () => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-0.5", className)}>
      <button
        type="button"
        title={magnetOn ? "Imán activo (ajuste OHLC)" : "Imán desactivado"}
        onClick={onMagnetToggle}
        className={cn(BTN, magnetOn && "bg-accent text-primary")}
      >
        <Magnet className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        title={drawingsHidden ? "Mostrar dibujos" : "Ocultar todos los dibujos"}
        onClick={onDrawingsHiddenToggle}
        className={cn(BTN, drawingsHidden && "text-amber-500")}
      >
        {drawingsHidden ? (
          <EyeOff className="h-3.5 w-3.5" />
        ) : (
          <Eye className="h-3.5 w-3.5" />
        )}
      </button>
      <button
        type="button"
        title={
          drawingsLocked ? "Desbloquear dibujos" : "Bloquear todos los dibujos"
        }
        onClick={onDrawingsLockedToggle}
        className={cn(BTN, drawingsLocked && "text-primary")}
      >
        {drawingsLocked ? (
          <Lock className="h-3.5 w-3.5" />
        ) : (
          <LockOpen className="h-3.5 w-3.5" />
        )}
      </button>
    </div>
  );
}
