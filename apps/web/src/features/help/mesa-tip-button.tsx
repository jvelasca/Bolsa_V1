/**
 * Coach-mark compacto «?» → diálogo de tip de mesa operativa (no branding IA).
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { getMesaTip, type MesaTipId } from "@/features/help/mesa-tip-catalog";
import { cn } from "@/lib/utils";

type Props = {
  tip: MesaTipId;
  className?: string;
};

export function MesaTipButton({ tip, className }: Props) {
  const [open, setOpen] = useState(false);
  const info = getMesaTip(tip);

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className={cn(
          "h-5 w-5 shrink-0 p-0 text-[11px] font-semibold text-muted-foreground hover:text-foreground",
          className,
        )}
        title={info.title}
        aria-label={`Ayuda mesa: ${info.title}`}
        data-testid={`mesa-tip-${tip}`}
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
      >
        ?
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={info.title}
        description="Tip de mesa operativa (no lanza acciones)."
        className="max-w-md"
      >
        <div className="space-y-3 text-sm">
          <p className="text-foreground leading-snug whitespace-pre-line">
            {info.body}
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            {info.linkTo && info.linkLabel ? (
              <Link
                to={info.linkTo}
                className={cn(
                  buttonVariants({ variant: "outline", size: "sm" }),
                  "h-8",
                )}
                onClick={() => setOpen(false)}
              >
                {info.linkLabel}
              </Link>
            ) : null}
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-8"
              onClick={() => setOpen(false)}
            >
              Cerrar
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  );
}
