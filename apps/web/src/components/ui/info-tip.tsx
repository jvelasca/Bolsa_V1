import { cn } from "@/lib/utils";

type InfoTipProps = {
  text: string;
  className?: string;
};

/** Inline (i) with native title tooltip — keeps the wizard copy simple. */
export function InfoTip({ text, className }: InfoTipProps) {
  return (
    <span
      className={cn(
        "ml-1 inline-flex h-4 w-4 shrink-0 cursor-help items-center justify-center rounded-full",
        "border border-muted-foreground/40 text-[10px] font-semibold leading-none text-muted-foreground",
        "align-middle hover:border-foreground/50 hover:text-foreground",
        className,
      )}
      title={text}
      aria-label={text}
      role="img"
    >
      i
    </span>
  );
}
