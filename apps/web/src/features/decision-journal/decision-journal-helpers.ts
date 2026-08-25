import type { JournalEventType } from "@bolsa/shared";

export function formatJournalDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatEventTypeLabel(eventType: string): string {
  return eventType.replace(/_/g, " ");
}

/** Ciclo 6 — línea Setup desde payload journal (si hay campos). */
export function formatJournalSetupLine(
  payload: Record<string, unknown> | null | undefined,
): string | null {
  if (!payload || typeof payload !== "object") return null;
  const parts: string[] = [];
  const entrySetup = payload.entrySetup;
  if (typeof entrySetup === "string" && entrySetup.trim()) {
    parts.push(entrySetup.trim());
  }
  const status = payload.tradePlanStatus;
  if (typeof status === "string" && status.trim()) {
    parts.push(status.trim());
  }
  const phase = payload.phase;
  if (typeof phase === "string" && phase.trim() && phase !== "none") {
    parts.push(`fase ${phase.trim()}`);
  }
  const effort = payload.effort;
  if (typeof effort === "string" && effort.trim() && effort !== "none") {
    parts.push(effort.trim().replaceAll("_", " "));
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

export function eventTypeBadgeClasses(eventType: string): string {
  switch (eventType as JournalEventType) {
    case "proposal_recorded":
      return "bg-sky-500/15 text-sky-800 dark:text-sky-200";
    case "gate_evaluated":
      return "bg-violet-500/15 text-violet-800 dark:text-violet-200";
    case "human_confirm":
    case "contract_verified":
    case "executed":
      return "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200";
    case "human_reject":
    case "risk_veto":
      return "bg-rose-500/15 text-rose-800 dark:text-rose-200";
    case "contract_absent":
      return "bg-amber-500/15 text-amber-900 dark:text-amber-200";
    case "session_verdict":
      return "bg-indigo-500/15 text-indigo-800 dark:text-indigo-200";
    default:
      return "bg-muted text-muted-foreground";
  }
}

export function actorBadgeClasses(actor: string): string {
  return actor === "human"
    ? "bg-indigo-500/15 text-indigo-800 dark:text-indigo-200"
    : "bg-muted text-muted-foreground";
}

/** Abre Decision Replay en Ayuda → Análisis de valor (patrón supervised-f3). */
export function openDecisionReplay(sessionId: string): void {
  window.dispatchEvent(
    new CustomEvent("bolsa:open-help", {
      detail: {
        section: "value-analysis",
        sessionId,
      },
    }),
  );
}
