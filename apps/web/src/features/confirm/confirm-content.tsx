/**
 * Contenido compartido Confirmar (página + drawer U3).
 * Misma cola F3 / SEMI — no reescribe contrato ni API.
 */

import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";
import { MesaTipButton } from "@/features/help/mesa-tip-button";
import {
  CONFIRM_FULL_PAGE_LINK_LABEL,
  confirmFullPagePath,
} from "@/features/confirm/confirm-drawer";
import { SupervisedF3Panel } from "@/features/settings/supervised-f3-panel";
import { cn } from "@/lib/utils";

type ConfirmContentProps = {
  /** En drawer: enlace a `/confirm` sin cortocircuitar firma. */
  showFullPageLink?: boolean;
  /** Tras navegar a página completa (p. ej. cerrar drawer). */
  onFullPageNavigate?: () => void;
  /**
   * `compact`: el chrome del SlideOver ya muestra el título;
   * solo subtítulo SEMI + tip + panel.
   */
  compact?: boolean;
  className?: string;
};

export function ConfirmContent({
  showFullPageLink = false,
  onFullPageNavigate,
  compact = false,
  className,
}: ConfirmContentProps) {
  return (
    <div className={cn("space-y-6", className)} data-testid="confirm-content">
      <div>
        <div className="flex flex-wrap items-center gap-1.5">
          {!compact ? (
            <h2 className="text-2xl font-semibold tracking-tight">Confirmar</h2>
          ) : null}
          <MesaTipButton tip="confirm-firmar" />
          {showFullPageLink ? (
            <MesaTipButton tip="operativa-confirm-drawer" />
          ) : null}
        </div>
        <p className="text-sm text-muted-foreground">
          La app propone operaciones sobre tu Universo. Tú las firmas aquí.
          Nunca se envían solas.
        </p>
        {showFullPageLink ? (
          <Link
            to={confirmFullPagePath()}
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              "mt-2 h-8",
            )}
            data-testid="confirm-drawer-full-page"
            onClick={() => onFullPageNavigate?.()}
          >
            {CONFIRM_FULL_PAGE_LINK_LABEL}
          </Link>
        ) : null}
      </div>
      <SupervisedF3Panel />
    </div>
  );
}
