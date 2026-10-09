/**
 * PAPER-2 — superficie de primer nivel del contrato de evidencia durable PAPER.
 *
 * Pinta el veredicto reservado (`NO CONFIRMADO`) con sus **siete criterios**, el origen durable
 * de cada uno, su medición y sus bloqueos. El contenedor NO re-deriva nada: consume el hook
 * read-only (`useAutoPaperEvidence`), que a su vez mapea el DTO del endpoint al contrato puro.
 *
 * Invariantes de primer nivel:
 * - **El usuario distingue «Incumplido» de «Sin dato todavía».** El estado de cada criterio se
 *   expone en `data-status` y con el rótulo oficial (`absent-data`), nunca como un comodín.
 * - **Nunca se emite la confirmación reservada.** El veredicto es el literal de contrato; esta
 *   superficie no tiene rama que lo promocione.
 * - **La jerga de ingeniería vive en nivel 3.** Los tokens crudos del material (fuentes y
 *   contradicciones) sólo aparecen dentro del `AutoTechnicalDetail`; el primer nivel usa el
 *   vocabulario de usuario del contrato.
 *
 * @see docs/engineering/contrato-evidencia-paper-confirmacion-2026-10-09.md
 * @see apps/web/src/features/auto-monitor/paper-confirmation-contract.ts
 */

import type { components } from "@/api/schema";
import { absentDataLabel } from "@/components/absent-data";
import { cn } from "@/lib/utils";
import { AutoTechnicalDetail } from "@/features/auto/auto-technical-detail";
import { AUTO_USER_TEXT } from "@/features/auto/auto-typography";
import {
  type PaperConfirmationCriterionStatus,
  type PaperConfirmationVerdictV1,
} from "./paper-confirmation-contract";
import {
  PAPER_CONFIRMATION_CONTRACT_DESCRIPTION,
  PAPER_CONFIRMATION_CONTRACT_TITLE,
  PAPER_CONFIRMATION_GLOBAL_VERDICT_LABEL,
} from "./paper-confirmation-contract-labels";
import { useAutoPaperEvidence } from "./use-auto-paper-evidence";

type AutoPaperEvidenceDto = components["schemas"]["AutoPaperEvidenceDto"];

/** Punto de color por estado: verde cumplido, rojo incumplido, gris sin dato. */
const STATUS_DOT: Record<PaperConfirmationCriterionStatus, string> = {
  met: "bg-emerald-500",
  unmet: "bg-destructive",
  unknown: "bg-muted-foreground/40",
};

export function PaperEvidenceView({
  verdict,
  dto,
  accountId,
}: {
  verdict: PaperConfirmationVerdictV1;
  dto: AutoPaperEvidenceDto | null;
  accountId?: string | null;
}) {
  const blocked = verdict.criteria.filter((item) => item.status !== "met");
  const contradictions = dto?.contradictions ?? [];
  const notes = dto?.notes ?? [];

  return (
    <section
      className="space-y-3 rounded-xl border border-border bg-card p-4"
      aria-labelledby="paper-evidence-heading"
      data-testid="paper-evidence-panel"
      data-verdict={verdict.verdict}
    >
      <div className="space-y-1">
        <h2
          id="paper-evidence-heading"
          className={cn("font-semibold", AUTO_USER_TEXT)}
        >
          {PAPER_CONFIRMATION_CONTRACT_TITLE}
        </h2>
        <p className="text-xs text-muted-foreground">
          {PAPER_CONFIRMATION_CONTRACT_DESCRIPTION}
        </p>
        <p
          className={cn("font-medium", AUTO_USER_TEXT)}
          data-testid="paper-evidence-verdict"
        >
          {PAPER_CONFIRMATION_GLOBAL_VERDICT_LABEL}
        </p>
        <p className="text-xs text-muted-foreground">{verdict.summary}</p>
      </div>

      <ul className="space-y-2" data-testid="paper-evidence-criteria">
        {verdict.criteria.map((criterion) => (
          <li
            key={criterion.id}
            className="rounded-md border border-border/60 px-3 py-2"
            data-testid="paper-evidence-criterion"
            data-criterion={criterion.id}
            data-status={criterion.status}
          >
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span
                aria-hidden="true"
                className={cn(
                  "mt-1 inline-block size-1.5 shrink-0 rounded-full",
                  STATUS_DOT[criterion.status],
                )}
              />
              <span className={cn("font-medium", AUTO_USER_TEXT)}>
                {criterion.title}
              </span>
              <span
                className="uppercase tracking-wide text-xs text-muted-foreground"
                data-testid="paper-evidence-criterion-status"
              >
                {criterion.statusLabel}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              {criterion.requirement}
            </p>
            <p className="text-xs text-muted-foreground">
              Origen: {criterion.sourceLabel}
            </p>
            {criterion.measurement ? (
              <p className="text-xs tabular-nums text-muted-foreground">
                {criterion.measurement}
              </p>
            ) : null}
            {criterion.status !== "met" && criterion.reason ? (
              <p
                className="text-xs text-muted-foreground"
                data-testid="paper-evidence-criterion-reason"
              >
                {criterion.reason}
              </p>
            ) : null}
          </li>
        ))}
      </ul>

      {blocked.length > 0 ? (
        <div
          className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2"
          data-testid="paper-evidence-blockers"
        >
          <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
            Bloqueos declarados
          </p>
          <p className="text-xs text-muted-foreground">
            {blocked.length} de {verdict.criteria.length} criterios impiden
            cerrar el contrato hoy.
          </p>
        </div>
      ) : null}

      <AutoTechnicalDetail testId="paper-evidence-technical">
        <ul className="space-y-1">
          {verdict.criteria.map((criterion) => (
            <li key={criterion.id}>
              {criterion.id}: {criterion.status}
              {criterion.measurement ? ` · ${criterion.measurement}` : ""}
            </li>
          ))}
        </ul>
        <p>Esquema: {dto?.schemaVersion ?? absentDataLabel()}</p>
        <p>Cuenta: {accountId ?? absentDataLabel()}</p>
        <p>
          Contradicciones:{" "}
          {contradictions.length > 0
            ? contradictions.join(", ")
            : "ninguna declarada"}
        </p>
        <p>
          Huecos declarados: {notes.length > 0 ? notes.join(", ") : "ninguno"}
        </p>
      </AutoTechnicalDetail>
    </section>
  );
}

/**
 * Contenedor read-only: resuelve la cuenta, lee el DTO y pinta el contrato. Sin cuenta visible
 * se declara el hueco (fail-closed), nunca se lee un material global.
 */
export function PaperEvidencePanel() {
  const { verdict, dto, accountId, isLoading, isError } =
    useAutoPaperEvidence();

  if (!accountId) {
    return (
      <section
        className="rounded-xl border border-dashed border-border bg-card p-4"
        data-testid="paper-evidence-no-account"
      >
        <p className={cn("font-medium", AUTO_USER_TEXT)}>
          {PAPER_CONFIRMATION_CONTRACT_TITLE}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {absentDataLabel("not_available")}: sin cuenta activa no se puede leer
          la evidencia durable.
        </p>
      </section>
    );
  }

  if (isError || (!isLoading && !verdict)) {
    return (
      <section
        className="rounded-xl border border-destructive/30 bg-destructive/5 p-4"
        data-testid="paper-evidence-error"
      >
        <p className={cn("font-medium", AUTO_USER_TEXT)}>
          {PAPER_CONFIRMATION_CONTRACT_TITLE}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          No se pudo leer la evidencia PAPER durable.
        </p>
      </section>
    );
  }

  if (!verdict) {
    return (
      <p
        className="text-sm text-muted-foreground"
        data-testid="paper-evidence-loading"
      >
        Cargando evidencia PAPER…
      </p>
    );
  }

  return (
    <PaperEvidenceView verdict={verdict} dto={dto} accountId={accountId} />
  );
}
