/**
 * AUTO UI REFACTOR 4.0 (P3) — panel «TOP 3 OPORTUNIDADES».
 *
 * Pinta el TOP3 persistido por el motor con lenguaje de tres niveles. Mantiene la distancia
 * `ranking ≠ decisión` en todo momento y declara los estados honestos (carga/error/vacío/
 * degradado). No recalcula el score.
 *
 * @see docs/engineering/spec-auto-ui-definitiva-2026-10-07.md §4 §5
 */

import { AutoTechnicalDetail } from "@/features/auto/auto-technical-detail";
import {
  AUTO_TOP3_TITLE,
  type AutoTop3ViewV1,
} from "@/features/auto/auto-top3-opportunities";
import {
  AUTO_USER_TEXT,
  AUTO_USER_TITLE,
} from "@/features/auto/auto-typography";
import { cn } from "@/lib/utils";

export function AutoTop3Panel({
  view,
  isLoading,
  isError,
  testId = "auto-top3",
  compact = false,
}: {
  view: AutoTop3ViewV1 | null;
  isLoading?: boolean;
  isError?: boolean;
  testId?: string;
  /**
   * Resumen de primer nivel (HOME): menos peso que la vista completa de Operar
   * (`UI5-06`: el TOP3 vive en tres niveles, sin duplicar densidad entre HOME y OPERAR).
   */
  compact?: boolean;
}) {
  return (
    <section
      className="space-y-3"
      aria-labelledby={`${testId}-heading`}
      data-testid={testId}
      data-compact={compact ? "1" : "0"}
    >
      <div className="space-y-1">
        <h3
          id={`${testId}-heading`}
          className={cn("font-semibold", AUTO_USER_TITLE)}
        >
          {AUTO_TOP3_TITLE}
        </h3>
        <p className={cn("text-muted-foreground", AUTO_USER_TEXT)}>
          Las 3 oportunidades que AUTO ha situado en los primeros puestos de su
          último análisis.
          {/*
           * `ranking ≠ decisión` (`UI5-12`) se declara una sola vez en cada superficie: el
           * resumen compacto (HOME) lo deja a la sección «Decisión de cartera», que ya lo dice;
           * la vista completa (Operar) lo lleva aquí, en su propio panel.
           */}
          {!compact && view?.rankNote ? ` ${view.rankNote}` : null}
        </p>
      </div>

      {isLoading ? (
        <p className={AUTO_USER_TEXT} data-testid={`${testId}-loading`}>
          Cargando oportunidades…
        </p>
      ) : null}

      {isError ? (
        <p
          className={cn(AUTO_USER_TEXT, "text-destructive")}
          data-testid={`${testId}-error`}
        >
          No se pudieron cargar las oportunidades.
        </p>
      ) : null}

      {!isLoading && !isError && view?.isEmpty ? (
        <p
          className={cn(AUTO_USER_TEXT, "text-muted-foreground")}
          data-testid={`${testId}-empty`}
        >
          {view.emptyLabel}
        </p>
      ) : null}

      {!isLoading && !isError && view && !view.isEmpty ? (
        <ol className="space-y-2" data-testid={`${testId}-list`}>
          {view.slots.map((slot) => (
            <li
              key={`${slot.rank}-${slot.assetId}`}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 rounded-md border border-border px-3 py-2"
              data-testid={`${testId}-slot`}
              data-rank={slot.rank}
              data-degraded={slot.reasonLabel ? "1" : "0"}
            >
              <span className="text-muted-foreground tabular-nums">
                #{slot.rank}
              </span>
              <span className={cn("font-semibold", AUTO_USER_TITLE)}>
                {slot.assetId}
              </span>
              <span className={cn("tabular-nums", AUTO_USER_TEXT)}>
                {slot.scoreLabel}
              </span>
              {!compact ? (
                <span className={cn(AUTO_USER_TEXT, "text-muted-foreground")}>
                  {slot.strengthLabel}
                </span>
              ) : null}
              {slot.reasonLabel ? (
                <span
                  className={cn(
                    AUTO_USER_TEXT,
                    "text-amber-600 dark:text-amber-400",
                  )}
                  data-testid={`${testId}-slot-reason`}
                >
                  {slot.reasonLabel}
                </span>
              ) : null}
              <span className={cn("ml-auto", AUTO_USER_TEXT, "font-medium")}>
                {slot.stateLabel}
              </span>
            </li>
          ))}
        </ol>
      ) : null}

      {view && !view.isEmpty && !compact ? (
        <AutoTechnicalDetail testId={`${testId}-technical`}>
          <dl className="space-y-1">
            <div className="flex gap-2">
              <dt className="text-muted-foreground">runId</dt>
              <dd className="font-mono">{view.runId}</dd>
            </div>
            {view.slots.map((slot) => (
              <div
                key={`tech-${slot.rank}-${slot.assetId}`}
                className="flex gap-2"
              >
                <dt className="text-muted-foreground">#{slot.rank}</dt>
                <dd className="font-mono">
                  {slot.assetId} · {slot.scoreLabel}
                  {slot.regimeLabel ? ` · régimen ${slot.regimeLabel}` : ""}
                </dd>
              </div>
            ))}
          </dl>
        </AutoTechnicalDetail>
      ) : null}
    </section>
  );
}
