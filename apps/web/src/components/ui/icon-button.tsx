import { forwardRef, type ButtonHTMLAttributes } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: LucideIcon;
  title: string;
  active?: boolean;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  function IconButton(
    {
      icon: Icon,
      title,
      onClick,
      active,
      disabled,
      className,
      type = "button",
      ...rest
    },
    ref,
  ) {
    return (
      <button
        ref={ref}
        type={type}
        title={title}
        aria-label={title}
        disabled={disabled}
        onClick={onClick}
        className={cn(
          "inline-flex h-6 w-6 shrink-0 items-center justify-center rounded text-muted-foreground",
          "hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40",
          active && "bg-accent text-primary",
          className,
        )}
        {...rest}
      >
        <Icon className="h-3.5 w-3.5" aria-hidden />
      </button>
    );
  },
);
