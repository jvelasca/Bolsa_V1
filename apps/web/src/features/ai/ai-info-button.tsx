/**
 * Botón compacto «IA» → diálogo informativo (qué hace / qué no / enlace Ayuda).
 */

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import {
  AI_INFO_SURFACES,
  type AiInfoSurfaceId,
} from '@/features/ai/ai-info-catalog';
import { openHelpAiPlatform } from '@/stores/supervised-f3-queue-store';
import { cn } from '@/lib/utils';

type Props = {
  surface: AiInfoSurfaceId;
  className?: string;
  /** Etiqueta visible (default IA). */
  label?: string;
};

export function AiInfoButton({ surface, className, label = 'IA' }: Props) {
  const [open, setOpen] = useState(false);
  const info = AI_INFO_SURFACES[surface];

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className={cn(
          'h-6 shrink-0 px-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground hover:text-foreground',
          className,
        )}
        title={`Qué hace la IA aquí · ${info.title}`}
        aria-label={`Información IA: ${info.title}`}
        onClick={() => setOpen(true)}
      >
        {label}
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={info.title}
        description="Información de esta superficie IA (no lanza acciones)."
        className="max-w-md"
      >
        <div className="space-y-3 text-sm">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Qué hace
            </p>
            <p className="mt-1 text-foreground leading-snug">{info.does}</p>
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Qué no hace
            </p>
            <p className="mt-1 text-foreground leading-snug">{info.doesNot}</p>
          </div>
          <p className="rounded-md border border-border/60 bg-muted/20 px-2.5 py-2 text-[11px] text-muted-foreground">
            {info.engineHint}
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8"
              onClick={() => {
                setOpen(false);
                openHelpAiPlatform(
                  info.helpPanel ? { panel: info.helpPanel } : undefined,
                );
              }}
            >
              Abrir Ayuda · Plataforma IA
            </Button>
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
