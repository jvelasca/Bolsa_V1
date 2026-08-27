import { Link } from "react-router-dom";
import {
  operationalIncidentStatusCopy,
  type OperationalIncidentKindV1,
  type OperationalIncidentV1,
} from "@bolsa/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useActiveOperationalIncidents } from "@/features/operations/use-active-operational-incidents";

const INCIDENT_KIND_LABELS: Record<OperationalIncidentKindV1, string> = {
  portfolio_drift: "Deriva portfolio (OI-6)",
  live_drift: "Deriva live (LR-1)",
  live_unavailable: "Live no disponible",
};

export function OpsIncidentsSection({
  accountId,
  onManageIncident,
}: {
  accountId: string;
  onManageIncident: (incident: OperationalIncidentV1) => void;
}) {
  const incidentsQuery = useActiveOperationalIncidents(accountId);
  const incidents = incidentsQuery.data?.data.incidents ?? [];

  return (
    <Card data-testid="ops-incidents-section">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Incidentes activos (DEX-3)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {incidentsQuery.isLoading ? (
          <p className="text-muted-foreground">Cargando incidentes…</p>
        ) : null}
        {incidentsQuery.isError ? (
          <p className="text-destructive">No se pudieron cargar incidentes.</p>
        ) : null}
        {!incidentsQuery.isLoading && incidents.length === 0 ? (
          <p
            className="text-muted-foreground"
            data-testid="ops-incidents-empty"
          >
            Sin incidentes activos.
          </p>
        ) : null}
        {incidents.length > 0 ? (
          <ul className="space-y-2" data-testid="ops-incidents-list">
            {incidents.map((inc) => (
              <li
                key={inc.incidentId}
                className="rounded-md border border-border bg-muted/20 px-3 py-2"
                data-testid="ops-incident-row"
              >
                <p className="font-medium">{INCIDENT_KIND_LABELS[inc.kind]}</p>
                <p className="text-xs text-muted-foreground">
                  {operationalIncidentStatusCopy(inc.status)}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onManageIncident(inc)}
                    data-testid="ops-incident-resolve-link"
                  >
                    Resolver
                  </Button>
                  <Link
                    to="/mesa?view=posiciones"
                    className="inline-flex items-center text-xs text-primary hover:underline"
                  >
                    Ir a Cartera · Posiciones
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function OpsQuickLinksSection({
  pendingConfirm,
}: {
  pendingConfirm: number;
}) {
  const tiles = [
    {
      to: "/mesa?view=decisiones",
      label: "Decisiones",
      hint: "Oportunidades y gates (solo lectura)",
      testId: "ops-link-board",
    },
    {
      to: "/mesa?view=journal",
      label: "Journal",
      hint: "Tesis · Evolución · Historial técnico",
      testId: "ops-link-journal",
    },
    {
      to: "/mesa?view=confirmar",
      label: "Confirmar",
      hint: `Cola SEMI (${pendingConfirm} pendientes)`,
      testId: "ops-link-confirm",
    },
    {
      to: "/mesa?view=posiciones",
      label: "Cartera · Posiciones",
      hint: "Posiciones y CTAs de desriesgo",
      testId: "ops-link-operations",
    },
  ] as const;

  return (
    <Card data-testid="ops-quick-links-section">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Accesos rápidos</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-2 sm:grid-cols-2">
          {tiles.map((tile) => (
            <Link
              key={tile.to}
              to={tile.to}
              className="rounded-md border border-border bg-card/60 px-3 py-2 transition-colors hover:bg-muted/40"
              data-testid={tile.testId}
            >
              <p className="text-sm font-medium">{tile.label}</p>
              <p className="text-xs text-muted-foreground">{tile.hint}</p>
            </Link>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Consola read-only — Confirm sigue siendo la única firma.
        </p>
      </CardContent>
    </Card>
  );
}
