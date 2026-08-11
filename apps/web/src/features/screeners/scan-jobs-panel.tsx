import { useMutation } from "@tanstack/react-query";
import { FileJson, Loader2 } from "lucide-react";
import { useState } from "react";
import type { ScanJobDto, ScanManifestV1 } from "@bolsa/shared";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ScreenerPanelShell } from "@/features/screeners/screener-panel-shell";

const JOB_STATUS_LABELS: Record<string, string> = {
  pending: "Pendiente",
  processing: "Procesando",
  completed: "Completado",
  failed: "Fallido",
};

interface ScanJobsPanelProps {
  jobs: ScanJobDto[];
  onLoadResult: (job: ScanJobDto) => void;
  embedded?: boolean;
}

export function ScanJobsPanel({
  jobs,
  onLoadResult,
  embedded,
}: ScanJobsPanelProps) {
  const [manifestJobId, setManifestJobId] = useState<string | null>(null);
  const [manifest, setManifest] = useState<ScanManifestV1 | null>(null);

  const manifestMutation = useMutation({
    mutationFn: (scanId: string) => api.getScanManifest(scanId),
    onSuccess: (response, scanId) => {
      setManifestJobId(scanId);
      setManifest(response.data);
    },
    onError: () => {
      setManifestJobId(null);
      setManifest(null);
    },
  });

  const manifestError =
    manifestMutation.error instanceof ApiError
      ? manifestMutation.error.message
      : manifestMutation.error instanceof Error
        ? manifestMutation.error.message
        : null;

  if (jobs.length === 0) return null;

  return (
    <ScreenerPanelShell
      embedded={embedded}
      title="Tareas recientes"
      description={
        embedded
          ? undefined
          : "Cola async — carga resultados o consulta el manifiesto P4."
      }
    >
      <div className="space-y-3">
        <ul className="space-y-2 text-sm">
          {jobs.slice(0, 8).map((job) => (
            <li
              key={job.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded border border-border px-3 py-2"
            >
              <span className="font-mono text-xs">{job.id.slice(0, 10)}…</span>
              <span className="text-muted-foreground">
                {JOB_STATUS_LABELS[job.status] ?? job.status}
              </span>
              {job.result && (
                <span className="text-xs">
                  {job.result.hitCount} coincidencias
                </span>
              )}
              {job.cacheHits != null && (
                <span className="text-xs text-muted-foreground">
                  caché {job.cacheHits}/{job.cacheMisses}
                </span>
              )}
              <div className="flex gap-1">
                {job.status === "completed" && job.result && (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => onLoadResult(job)}
                  >
                    Ver coincidencias
                  </Button>
                )}
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  title="Manifiesto del rastreo"
                  disabled={
                    manifestMutation.isPending &&
                    manifestMutation.variables === job.id
                  }
                  onClick={() => manifestMutation.mutate(job.id)}
                >
                  {manifestMutation.isPending &&
                  manifestMutation.variables === job.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <FileJson className="h-3.5 w-3.5" />
                  )}
                </Button>
              </div>
            </li>
          ))}
        </ul>

        {manifest && manifestJobId && (
          <div className="rounded border border-border bg-muted/20 p-3 text-xs">
            <p className="mb-1 font-medium">
              Manifiesto · tarea {manifestJobId.slice(0, 10)}…
            </p>
            <p className="text-muted-foreground">
              Rastreo {manifest.scanId.slice(0, 8)}… · {manifest.hitCount}{" "}
              coincidencias · TF {manifest.timeframe}
            </p>
            {manifest.dataSnapshots?.[0]?.dataVersion && (
              <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                versión de datos{" "}
                {manifest.dataSnapshots[0].dataVersion.slice(0, 20)}…
              </p>
            )}
          </div>
        )}

        {manifestError && (
          <p className="text-xs text-destructive">{manifestError}</p>
        )}
      </div>
    </ScreenerPanelShell>
  );
}
