import { forwardRef } from "react";
import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";

/** Panel flotante con fondo sólido (legible sobre tablas con scroll). */
export const OpaqueMenuPanel = forwardRef<
  HTMLDivElement,
  {
    children: React.ReactNode;
    className?: string;
    align?: "left" | "right";
    style?: CSSProperties;
  }
>(function OpaqueMenuPanel(
  { children, className, align = "right", style },
  ref,
) {
  return (
    <div
      ref={ref}
      style={style}
      className={cn(
        "absolute top-full z-50 mt-1 min-w-[180px] rounded-md border border-border bg-card py-1 text-sm text-foreground shadow-xl ring-1 ring-border/80",
        !style?.position && align === "right" && "right-0",
        !style?.position && align === "left" && "left-0",
        className,
      )}
    >
      {children}
    </div>
  );
});

export function OpaqueMenuItem({
  children,
  onClick,
  disabled,
  destructive,
  className,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  destructive?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-accent disabled:pointer-events-none disabled:opacity-40",
        destructive && "text-destructive hover:bg-destructive/10",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function OpaqueMenuLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="truncate px-3 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
      {children}
    </p>
  );
}
