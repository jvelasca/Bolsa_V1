/**
 * B-5 / O-6 — representación ÚNICA de las declaraciones de HOLD, con su procedencia.
 *
 * Un solo componente para las dos superficies que explican el silencio de AUTO:
 * - el monitor experto (`/auto-monitor`, dentro de la historia de la operación);
 * - la sección Actividad (`/auto/actividad`, como primera capa de «Por qué AUTO no operó»).
 *
 * No duplica diagnósticos ni re-deriva el motivo: pinta el read-model puro
 * `buildAutoHoldDeclarations`. En primer nivel, símbolo, causa, motivo y día legible; debajo, la
 * procedencia declarada con su medición; y TODO lo crudo (ids, sellos, códigos y claves no
 * reconocidas) bajo el disclosure canónico `Detalle técnico` (`RT-04`). Un hueco se declara
 * hueco: nunca `0`, `false` ni «sin señal».
 *
 * @see apps/web/src/features/auto/auto-hold-declarations.ts
 * @see apps/web/src/lib/decision-silence.ts
 * @see apps/web/src/components/technical-detail.tsx
 */

import { useId } from "react";
import { MeasurementValue } from "@/components/measurement-value";
import { absentDataLabel } from "@/components/absent-data";
import { AutoTechnicalDetail } from "@/features/auto/auto-technical-detail";
import {
  AUTO_TECH_TEXT,
  AUTO_USER_TEXT,
} from "@/features/auto/auto-typography";
import { cn } from "@/lib/utils";
import {
  AUTO_HOLD_PROVENANCE_ABSENT,
  autoHoldReasonLabel,
  autoHoldSymbolLabel,
  buildAutoHoldDeclarations,
  type AutoHoldDeclarationInput,
  type AutoHoldDeclarationsRow,
} from "@/features/auto/auto-hold-declarations";

/** Testids históricos del monitor (`auto-decision-silence*`): no se renombran. */
export const AUTO_HOLD_DEFAULT_TEST_ID = "auto-decision-silence";

export type AutoHoldDeclarationsPanelProps = {
  holds: readonly AutoHoldDeclarationInput[] | null | undefined;
  /** Nivel del encabezado: `h2` en la sección, `h3` dentro de una capa. */
  headingLevel?: "h2" | "h3";
  /** Prefijo de `data-testid`; por defecto el histórico del monitor. */
  testIdPrefix?: string;
  title?: string;
  /** Alcance temporal leído (`YYYY-MM-DD`): filtra y declara lo que queda fuera. */
  day?: string | null;
  /** Declaraciones en curso: no se afirma «sin declaraciones». */
  loading?: boolean;
  /** Lectura fallida: se declara el fallo, no el vacío. */
  error?: boolean;
  className?: string;
};

export const AUTO_HOLD_PANEL_TITLE =
  "Decisiones sin operación (HOLD declarados)";

function technicalMeasurement(measurement: string | null | undefined): string {
  return measurement ?? "UNKNOWN";
}

/** Un grupo del detalle técnico por declaración: ids, sellos, motivo crudo y TODOS los hechos. */
function TechnicalRowGroup({
  row,
  prefix,
}: {
  row: AutoHoldDeclarationsRow;
  prefix: string;
}) {
  return (
    <div
      className="space-y-1"
      data-testid={`${prefix}-item-technical`}
      data-instrument-id={row.instrumentId ?? undefined}
    >
      <p className={cn("font-medium", AUTO_TECH_TEXT)}>
        {autoHoldSymbolLabel(row)} · {row.causeLabel}
      </p>
      <dl className="grid gap-x-3 gap-y-0.5 sm:grid-cols-2">
        <div data-testid={`${prefix}-technical-instrument`}>
          <dt className="text-muted-foreground">instrumentId</dt>
          <dd>{row.instrumentId ?? absentDataLabel()}</dd>
        </div>
        <div data-testid={`${prefix}-technical-at`}>
          <dt className="text-muted-foreground">at</dt>
          <dd>{row.at ?? absentDataLabel()}</dd>
        </div>
        <div data-testid={`${prefix}-technical-bar`}>
          <dt className="text-muted-foreground">barTimestamp</dt>
          <dd>{row.barTimestamp ?? absentDataLabel()}</dd>
        </div>
        <div data-testid={`${prefix}-technical-reason`}>
          <dt className="text-muted-foreground">reason</dt>
          <dd>{row.reasonCode ?? absentDataLabel()}</dd>
        </div>
        {row.technicalFacts.map((fact, index) => (
          <div
            key={`${fact.key}-${index}`}
            data-testid={`${prefix}-technical-fact`}
            data-fact-key={fact.key}
          >
            <dt className="text-muted-foreground">{fact.key}</dt>
            <dd>
              <MeasurementValue
                value={fact.value}
                measurement={technicalMeasurement(fact.measurement)}
              />
            </dd>
          </div>
        ))}
      </dl>
      {row.technicalFacts.length === 0 ? (
        <p
          className="text-muted-foreground"
          data-testid={`${prefix}-technical-empty`}
        >
          El productor no declaró ningún hecho de procedencia.
        </p>
      ) : null}
    </div>
  );
}

function HoldRow({
  row,
  prefix,
}: {
  row: AutoHoldDeclarationsRow;
  prefix: string;
}) {
  return (
    <li
      className="space-y-1 border-t border-border/40 pt-1.5 first:border-t-0 first:pt-0"
      data-testid={`${prefix}-item`}
      data-instrument-id={row.instrumentId ?? undefined}
      data-cause={row.cause}
      data-measurement={row.measurement}
    >
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span
          className={cn("font-medium", AUTO_USER_TEXT)}
          data-testid={`${prefix}-item-symbol`}
        >
          {autoHoldSymbolLabel(row)}
        </span>
        <span
          className={cn(
            "uppercase tracking-wide text-muted-foreground",
            AUTO_USER_TEXT,
          )}
          data-testid={`${prefix}-item-cause`}
        >
          {row.causeLabel}
        </span>
        <span
          className={cn("text-muted-foreground", AUTO_USER_TEXT)}
          data-testid={`${prefix}-item-reason`}
        >
          {autoHoldReasonLabel(row)}
        </span>
        {row.barLabel ? (
          <span
            className={cn("text-muted-foreground", AUTO_USER_TEXT)}
            data-testid={`${prefix}-item-bar`}
            title={row.barTimestamp ?? undefined}
          >
            barra {row.barLabel}
          </span>
        ) : null}
      </div>

      {row.provenance.length > 0 ? (
        <dl
          className={cn("flex flex-wrap gap-x-3 gap-y-0.5", AUTO_USER_TEXT)}
          data-testid={`${prefix}-provenance`}
        >
          {row.provenance.map((item) => (
            <div
              key={item.key}
              className="flex items-baseline gap-x-1"
              data-testid={`${prefix}-provenance-item`}
              data-fact-key={item.key}
            >
              <dt className="text-muted-foreground">{item.label}:</dt>
              <dd>
                <MeasurementValue
                  value={item.value}
                  measurement={item.measurement}
                  testId={`${prefix}-provenance-value`}
                />
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p
          className={cn("text-muted-foreground", AUTO_USER_TEXT)}
          data-testid={`${prefix}-provenance-absent`}
        >
          {AUTO_HOLD_PROVENANCE_ABSENT}
        </p>
      )}
    </li>
  );
}

/** Aviso ámbar de los huecos: acotado para no convertir el titular en una lista. */
function attentionCopy(
  rows: readonly AutoHoldDeclarationsRow[],
  total: number,
): string {
  const listed = rows
    .slice(0, 3)
    .map((row) => ` ${autoHoldSymbolLabel(row)} (${autoHoldReasonLabel(row)})`)
    .join(" ·");
  const rest = rows.length - 3;
  const suffix = rest > 0 ? ` · y ${rest} más` : "";
  return `${rows.length} de ${total} no se pudieron evaluar:${listed}${suffix}`;
}

/**
 * Titular honesto reutilizable en Resumen y Operar, para no duplicar el copy del silencio.
 * La carga y el error los declara cada página: aquí sólo se pinta el hecho ya leído.
 */
export function AutoHoldSummaryLine({
  holds,
  day,
  testId,
  className,
}: {
  holds: readonly AutoHoldDeclarationInput[] | null | undefined;
  day?: string | null;
  testId?: string;
  className?: string;
}) {
  const { summary } = buildAutoHoldDeclarations(holds, { day });
  return (
    <p
      className={cn(AUTO_USER_TEXT, "text-muted-foreground", className)}
      data-testid={testId}
      data-silence-headline={summary.headline}
      data-silence-total={summary.total}
    >
      {summary.headline}
      {summary.detail ? ` — ${summary.detail}` : null}
    </p>
  );
}

export function AutoHoldDeclarationsPanel({
  holds,
  headingLevel = "h2",
  testIdPrefix = AUTO_HOLD_DEFAULT_TEST_ID,
  title = AUTO_HOLD_PANEL_TITLE,
  day = null,
  loading = false,
  error = false,
  className,
}: AutoHoldDeclarationsPanelProps) {
  const headingId = `${useId()}-hold-heading`;
  const { rows, summary, attention, scopeNote } = buildAutoHoldDeclarations(
    holds,
    { day },
  );
  const Heading = headingLevel;

  return (
    <section
      className={cn(
        "space-y-2 rounded-xl border border-dashed border-border bg-card p-4",
        className,
      )}
      aria-labelledby={headingId}
      data-testid={testIdPrefix}
      data-silence-headline={summary.headline}
      data-silence-total={summary.total}
    >
      <Heading id={headingId} className={cn("font-semibold", AUTO_USER_TEXT)}>
        {title}
      </Heading>

      {loading ? (
        <p
          className={cn("text-muted-foreground", AUTO_USER_TEXT)}
          data-testid={`${testIdPrefix}-loading`}
        >
          Cargando declaraciones de HOLD…
        </p>
      ) : null}
      {!loading && error ? (
        <p
          className={cn("text-destructive", AUTO_USER_TEXT)}
          data-testid={`${testIdPrefix}-error`}
        >
          No se pudieron leer las declaraciones de HOLD.
        </p>
      ) : null}

      {!loading && !error ? (
        <>
          <p
            className={cn("text-muted-foreground", AUTO_USER_TEXT)}
            data-testid={`${testIdPrefix}-headline`}
          >
            {summary.headline}
            {summary.detail ? ` — ${summary.detail}` : null}
          </p>

          {rows.length === 0 ? (
            <p
              className={cn("text-muted-foreground", AUTO_USER_TEXT)}
              data-testid={`${testIdPrefix}-empty`}
            >
              Esto <strong>no</strong> significa que el motor no haya descartado
              operar: significa que no consta el motivo.
            </p>
          ) : (
            <ul className="space-y-1.5" data-testid={`${testIdPrefix}-list`}>
              {rows.map((row) => (
                <HoldRow key={row.key} row={row} prefix={testIdPrefix} />
              ))}
            </ul>
          )}

          {attention.length > 0 ? (
            <p
              className={cn(
                "text-amber-600 dark:text-amber-400",
                AUTO_TECH_TEXT,
              )}
              data-testid={`${testIdPrefix}-attention`}
            >
              {attentionCopy(attention, summary.total)}
            </p>
          ) : null}

          {scopeNote ? (
            <p
              className={cn("text-muted-foreground", AUTO_TECH_TEXT)}
              data-testid={`${testIdPrefix}-scope`}
            >
              {scopeNote}
            </p>
          ) : null}

          {/* RT-04 — un único disclosure canónico por bloque: todo lo crudo (ids, sellos,
              códigos del vocabulario y hechos no reconocidos) vive aquí, no en el primer nivel. */}
          {rows.length > 0 ? (
            <AutoTechnicalDetail testId={`${testIdPrefix}-technical`}>
              <div className="space-y-3">
                {rows.map((row) => (
                  <TechnicalRowGroup
                    key={row.key}
                    row={row}
                    prefix={testIdPrefix}
                  />
                ))}
              </div>
            </AutoTechnicalDetail>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
