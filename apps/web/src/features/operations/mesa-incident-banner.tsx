/**
 * DEX-3 — banner Mesa para incidentes operacionales activos.
 * Entradas bloqueadas; salidas permitidas; sin auto-heal.
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  canClear,
  operationalIncidentStatusCopy,
  type OperationalIncidentKindV1,
  type OperationalIncidentV1,
} from "@bolsa/shared";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SlideOver } from "@/components/ui/slide-over";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useActiveOperationalIncidents } from "@/features/operations/use-active-operational-incidents";

const INCIDENT_KIND_LABELS: Record<OperationalIncidentKindV1, string> = {
  portfolio_drift: "Deriva portfolio (OI-6)",
  live_drift: "Deriva live (LR-1)",
  live_unavailable: "Live no disponible",
};

function reconStatusForIncident(
  kind: OperationalIncidentKindV1,
  portfolioReconStatus: string | null | undefined,
): string | null {
  if (kind === "portfolio_drift") {
    if (portfolioReconStatus === "ok") return "clean";
    if (portfolioReconStatus === "drift") return "drift";
    return null;
  }
  return null;
}

function reconLabel(
  kind: OperationalIncidentKindV1,
  portfolioReconStatus: string | null | undefined,
): string {
  const mapped = reconStatusForIncident(kind, portfolioReconStatus);
  if (mapped === "clean") return "recon = clean";
  if (mapped === "drift") return "recon = drift";
  if (kind === "portfolio_drift") {
    return `recon portfolio: ${portfolioReconStatus ?? "desconocido"}`;
  }
  return "recon live: validar en Clear (server)";
}

export function MesaIncidentBanner({
  accountId,
  portfolioReconStatus,
  className,
  panelOpen: panelOpenProp,
  onPanelOpenChange,
  focusIncidentId,
  showBanner = true,
}: {
  accountId: string;
  portfolioReconStatus?: string | null;
  className?: string;
  panelOpen?: boolean;
  onPanelOpenChange?: (open: boolean) => void;
  focusIncidentId?: string | null;
  showBanner?: boolean;
}) {
  const qc = useQueryClient();
  const incidentsQuery = useActiveOperationalIncidents(accountId);
  const incidents = incidentsQuery.data?.data.incidents ?? [];
  const [internalPanelOpen, setInternalPanelOpen] = useState(false);
  const panelOpen = panelOpenProp ?? internalPanelOpen;
  const setPanelOpen = onPanelOpenChange ?? setInternalPanelOpen;
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!focusIncidentId) return;
    setSelectedId(focusIncidentId);
    const inc = incidents.find((row) => row.incidentId === focusIncidentId);
    if (inc) {
      setNote(inc.resolutionNote ?? "");
    }
  }, [focusIncidentId, incidents]);

  const selected = useMemo(
    () =>
      incidents.find((inc) => inc.incidentId === selectedId) ??
      incidents[0] ??
      null,
    [incidents, selectedId],
  );

  const resolveMut = useMutation({
    mutationFn: (input: { incidentId: string; resolutionNote: string }) =>
      api.resolveOperationalIncident(accountId, input.incidentId, {
        resolutionNote: input.resolutionNote,
      }),
    onSuccess: () => {
      setFormError(null);
      setNote("");
      void qc.invalidateQueries({
        queryKey: ["operational-incidents-active", accountId],
      });
      void qc.invalidateQueries({ queryKey: ["ops-self-eval", accountId] });
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const clearMut = useMutation({
    mutationFn: (incidentId: string) =>
      api.clearOperationalIncident(accountId, incidentId),
    onSuccess: () => {
      setFormError(null);
      setPanelOpen(false);
      void qc.invalidateQueries({
        queryKey: ["operational-incidents-active", accountId],
      });
      void qc.invalidateQueries({ queryKey: ["ops-self-eval", accountId] });
    },
    onError: (err: Error) => setFormError(err.message),
  });

  if (incidents.length === 0) {
    return null;
  }

  const showBannerUi = showBanner;

  const primary = selected ?? incidents[0];
  const statusCopy = operationalIncidentStatusCopy(primary.status);
  const reconForClear = reconStatusForIncident(
    primary.kind,
    portfolioReconStatus,
  );
  const clearAllowed = canClear(primary, reconForClear);

  function openPanel(incident: OperationalIncidentV1) {
    setSelectedId(incident.incidentId);
    setNote(incident.resolutionNote ?? "");
    setFormError(null);
    setPanelOpen(true);
  }

  function handleResolve() {
    const trimmed = note.trim();
    if (!trimmed) {
      setFormError("La nota de resolución es obligatoria.");
      return;
    }
    resolveMut.mutate({
      incidentId: primary.incidentId,
      resolutionNote: trimmed,
    });
  }

  return (
    <>
      {showBannerUi ? (
        <div
          className={cn(
            "flex flex-wrap items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs",
            className,
          )}
          data-testid="mesa-incident-banner"
        >
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-700 dark:text-amber-300" />
          <div className="min-w-0 flex-1">
            <p className="font-medium text-amber-950 dark:text-amber-100">
              Incidente operacional — entradas bloqueadas ({incidents.length})
            </p>
            <p className="text-amber-900/80 dark:text-amber-200/80">
              {INCIDENT_KIND_LABELS[primary.kind]} · {statusCopy} Salidas
              protectivas permitidas. Sin auto-heal.
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="border-amber-600/40"
            onClick={() => openPanel(primary)}
            data-testid="mesa-incident-manage"
          >
            Gestionar
          </Button>
        </div>
      ) : null}

      <SlideOver
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        title="Incidente operacional (DEX-3)"
        description="Resolve con nota humana. Clear solo si recon = clean. No muta libros."
        testId="mesa-incident-panel"
      >
        <div className="space-y-4 p-4">
          {incidents.length > 1 ? (
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              Incidente
              <select
                className="h-8 rounded-md border border-border bg-card px-2 text-xs text-foreground"
                value={primary.incidentId}
                onChange={(e) => setSelectedId(e.target.value)}
                data-testid="mesa-incident-select"
              >
                {incidents.map((inc) => (
                  <option key={inc.incidentId} value={inc.incidentId}>
                    {INCIDENT_KIND_LABELS[inc.kind]} — {inc.status}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs">
            <p className="font-medium">{INCIDENT_KIND_LABELS[primary.kind]}</p>
            <p className="mt-1 text-muted-foreground">{statusCopy}</p>
            <p className="mt-2 text-muted-foreground">
              {reconLabel(primary.kind, portfolioReconStatus)}
            </p>
            <p className="mt-2 text-muted-foreground">
              Veto aperturas:{" "}
              <code className="text-[10px]">incident:unresolved</code>. Distinto
              de <code className="text-[10px]">reconciliation:*</code>.
            </p>
          </div>

          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Nota de resolución (obligatoria)
            <textarea
              className="min-h-24 rounded-md border border-border bg-card px-2 py-1.5 text-xs text-foreground"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              data-testid="mesa-incident-note"
            />
          </label>

          {formError ? (
            <p
              className="text-xs text-destructive"
              data-testid="mesa-incident-error"
            >
              {formError}
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              disabled={
                resolveMut.isPending ||
                primary.status === "resolved" ||
                primary.status === "cleared"
              }
              onClick={handleResolve}
              data-testid="mesa-incident-resolve"
            >
              Resolver
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!clearAllowed || clearMut.isPending}
              title={
                clearAllowed
                  ? "Clear con recon clean"
                  : "Clear requiere status resolved + recon clean"
              }
              onClick={() => clearMut.mutate(primary.incidentId)}
              data-testid="mesa-incident-clear"
            >
              Clear
            </Button>
          </div>
        </div>
      </SlideOver>
    </>
  );
}
