import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { OpsSelfEvalReport } from "@/features/operational-console/use-ops-self-eval";
import type { EstudioAutoTelemetry } from "@/features/operational-console/use-estudio-auto-telemetry";

function markClasses(mark: string): string {
  if (mark === "PASS") {
    return "border-emerald-500/40 text-emerald-800 dark:text-emerald-200";
  }
  if (mark === "WARN") {
    return "border-amber-500/40 text-amber-900 dark:text-amber-200";
  }
  if (mark === "UNAVAILABLE") {
    return "border-border text-muted-foreground";
  }
  return "border-rose-500/40 text-rose-800 dark:text-rose-200";
}

export function OpsReadinessSection({
  report,
}: {
  report: OpsSelfEvalReport | undefined;
}) {
  const readiness = report?.operationalReadiness;
  if (!readiness) {
    return (
      <Card data-testid="ops-readiness-section">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Readiness OR-6</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Sin datos de readiness.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="ops-readiness-section">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Readiness OR-6</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p
          className={cn(
            "inline-flex rounded-md border px-2 py-1 font-medium",
            readiness.state === "PAPER_READY"
              ? "border-emerald-500/40 text-emerald-800 dark:text-emerald-200"
              : readiness.state === "LIVE_EXPERIMENTAL"
                ? "border-sky-500/40 text-sky-900 dark:text-sky-100"
                : readiness.state === "LIVE_BLOCKED"
                  ? "border-rose-500/40 text-rose-800 dark:text-rose-200"
                  : "border-amber-500/40 text-amber-900 dark:text-amber-200",
          )}
          data-testid="ops-readiness-state"
        >
          {readiness.state}
        </p>
        <p className="text-xs text-muted-foreground">{readiness.rule}</p>
        {readiness.reasons.length > 0 ? (
          <ul className="list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
            {readiness.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : null}
        {readiness.notes.length > 0 ? (
          <p className="text-xs text-muted-foreground">
            {readiness.notes.join(" · ")}
          </p>
        ) : null}
        {readiness.venue === "live" ? (
          <p className="text-xs font-medium text-amber-800 dark:text-amber-200">
            Venue LIVE — experimental; nunca «accepted» en consola.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function OpsSelfEvalSection({
  report,
}: {
  report: OpsSelfEvalReport | undefined;
}) {
  if (!report) {
    return (
      <Card data-testid="ops-self-eval-section">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Autoeval OE-1</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Sin scorecard.</p>
        </CardContent>
      </Card>
    );
  }

  const { lanes, rule } = report;

  return (
    <Card data-testid="ops-self-eval-section">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Autoeval OE-1</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-xs text-muted-foreground">{rule}</p>
        <p className="text-xs font-medium text-muted-foreground">
          PASS ≠ permiso operar · measure ≠ Accept estricto.
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          <div
            className={cn(
              "rounded-md border px-3 py-2",
              markClasses(lanes.semi.mark),
            )}
            data-testid="ops-semi-lane"
          >
            <p className="text-[10px] uppercase tracking-wide opacity-80">
              SEMI
            </p>
            <p className="text-lg font-semibold">{lanes.semi.mark}</p>
            <p className="mt-1 text-xs opacity-80">
              confirm {lanes.semi.confirmSeed ?? "—"} · journal{" "}
              {lanes.semi.journalSeed ?? "—"}
            </p>
          </div>
          <div
            className={cn(
              "rounded-md border px-3 py-2",
              markClasses(lanes.auto.mark),
            )}
            data-testid="ops-auto-lane"
          >
            <p className="text-[10px] uppercase tracking-wide opacity-80">
              AUTO
            </p>
            <p className="text-lg font-semibold">{lanes.auto.mark}</p>
            <p className="mt-1 text-xs opacity-80">
              PAPER_D_EXECUTE env {lanes.auto.paperDExecuteEnv ? "on" : "off"}
            </p>
          </div>
        </div>
        <div className="space-y-1 text-xs">
          <p className="font-medium text-muted-foreground">Checks AUTO</p>
          <ul className="grid gap-1 sm:grid-cols-2">
            {(
              [
                ["P1 días opiniones", lanes.auto.p1],
                ["P2 confirm seed", lanes.auto.p2],
                ["P3 precisión 5d", lanes.auto.p3],
                ["P4 recall 5d", lanes.auto.p4],
                ["P5 cash DD", lanes.auto.p5],
              ] as const
            ).map(([label, gate]) => (
              <li
                key={label}
                className={cn(
                  "rounded border px-2 py-1",
                  markClasses(gate.mark),
                )}
              >
                {label}: {gate.mark}
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}

export function OpsReconSection({
  report,
}: {
  report: OpsSelfEvalReport | undefined;
}) {
  const recon = (report?.portfolioReconciliation ?? {}) as Record<
    string,
    unknown
  >;
  const status = typeof recon.status === "string" ? recon.status : "unknown";
  const note = typeof recon.note === "string" ? recon.note : null;

  return (
    <Card data-testid="ops-recon-section">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Reconciliación OI-6 / LR-1</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p
          className={cn(
            "inline-flex rounded-md border px-2 py-1 font-medium",
            status === "ok"
              ? "border-emerald-500/40 text-emerald-800 dark:text-emerald-200"
              : status === "drift"
                ? "border-rose-500/40 text-rose-800 dark:text-rose-200"
                : "border-amber-500/40 text-amber-900 dark:text-amber-200",
          )}
          data-testid="ops-recon-status"
        >
          Portfolio: {status}
        </p>
        {note ? <p className="text-xs text-muted-foreground">{note}</p> : null}
        {status === "drift" ? (
          <p className="text-xs text-muted-foreground">
            OR-4 veta aperturas con{" "}
            <code className="text-[10px]">reconciliation:portfolio_drift</code>.
            Informe only — sin auto-heal. Resuelve vía OperationalIncident
            (DEX-3).
          </p>
        ) : null}
        <p className="text-xs text-muted-foreground">
          Live recon (LR-1) se evalúa en venue Live; consola no inventa estado.
        </p>
        <Link
          to="/mesa?view=posiciones"
          className="text-xs font-medium text-primary hover:underline"
        >
          Libro · Operaciones (posiciones)
        </Link>
      </CardContent>
    </Card>
  );
}

export function OpsRuntimeSection({
  report,
}: {
  report: OpsSelfEvalReport | undefined;
}) {
  const runtime = report?.runtime;
  if (!runtime) {
    return (
      <Card data-testid="ops-runtime-section">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Runtime (read-only)</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Sin runtime.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="ops-runtime-section">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Runtime (read-only)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p>
          Kill switch:{" "}
          <span
            className={cn(
              "font-medium",
              runtime.killSwitchEffective
                ? "text-rose-700 dark:text-rose-300"
                : "text-muted-foreground",
            )}
            data-testid="ops-kill-switch"
          >
            {runtime.killSwitchEffective ? "ON" : "off"}
          </span>
        </p>
        <p>
          Venue efectivo:{" "}
          <span className="font-medium capitalize">{runtime.brokerVenue}</span>
          {runtime.accountVenuePreference ? (
            <span className="text-muted-foreground">
              {" "}
              (pref cuenta: {runtime.accountVenuePreference})
            </span>
          ) : null}
        </p>
        <p className="text-xs text-muted-foreground">
          {runtime.confirmPathHonesty}
        </p>
        <p className="text-xs text-muted-foreground">
          Cambiar venue/kill: mesa bar o{" "}
          <Link to="/accounts" className="text-primary hover:underline">
            Cuentas
          </Link>
          . Consola no duplica toggles peligrosos.
        </p>
      </CardContent>
    </Card>
  );
}

export function OpsEstudioAutoSection({
  report,
  isLoading,
  isError,
}: {
  report: EstudioAutoTelemetry | undefined;
  isLoading?: boolean;
  isError?: boolean;
}) {
  if (isLoading) {
    return (
      <Card data-testid="ops-estudio-auto-section">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">
            Telemetría A6 · Estudio AUTO
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Cargando embudo…</p>
        </CardContent>
      </Card>
    );
  }
  if (isError || !report) {
    return (
      <Card data-testid="ops-estudio-auto-section">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">
            Telemetría A6 · Estudio AUTO
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Sin embudo A6. Measure ≠ ampliar Radar/Hoy.
          </p>
        </CardContent>
      </Card>
    );
  }

  const { funnel, gates, lastPropose, edgeReport, recentProposes } = report;
  const skipped = Object.entries(lastPropose?.skippedByReason ?? {});
  const recentCount = recentProposes?.length ?? 0;
  const durabilityLabel =
    lastPropose?.durability === "jsonl"
      ? "persistido JSONL"
      : lastPropose?.durability === "process_memory"
        ? "memoria de proceso"
        : (lastPropose?.durability ?? "");

  return (
    <Card data-testid="ops-estudio-auto-section">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">
          Telemetría A6 · Estudio AUTO
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p className="text-xs text-muted-foreground">{report.rule}</p>
        <p
          className={cn(
            "inline-flex rounded-md border px-2 py-1 font-medium",
            gates.expandSourcesReady
              ? "border-emerald-500/40 text-emerald-800 dark:text-emerald-200"
              : "border-rose-500/40 text-rose-800 dark:text-rose-200",
          )}
          data-testid="ops-a6-expand-gate"
        >
          Ampliar fuentes: {gates.expandSourcesReady ? "listo" : "bloqueado"}
        </p>
        <p className="text-xs tabular-nums text-muted-foreground">
          Embudo {funnel.daysWithOpinions}d · {funnel.candidatesAlarma} alarma ·{" "}
          {funnel.candidatesDictamen} dictamen · {funnel.notCandidate} fuera
        </p>
        <p className="text-xs text-muted-foreground">
          Fuentes permitidas: {funnel.allowedSources.join(" · ")}. Fuera:{" "}
          {funnel.excludedSources.join(" · ")}.
        </p>
        <p className="text-xs text-muted-foreground">
          EdgeReport paridad SEMI: {edgeReport.mark}
          {gates.paperDExecuteEnv ? " · execute env on" : " · execute env off"}
        </p>
        {gates.blockers.length > 0 ? (
          <p className="text-xs text-muted-foreground">
            Blockers: {gates.blockers.join(" · ")}
          </p>
        ) : null}
        {lastPropose ? (
          <p
            className="text-xs tabular-nums text-muted-foreground"
            data-testid="ops-a6-last-propose"
          >
            Último auto-propose: {lastPropose.executeStatus} ·{" "}
            {lastPropose.hitCount} hit(s) / {lastPropose.candidateCount} cand.
            {skipped.length > 0
              ? ` · skip ${skipped.map(([k, n]) => `${k}×${n}`).join(", ")}`
              : ""}
            {" · "}
            {durabilityLabel}
            {recentCount > 1 ? ` · ${recentCount} en histórico` : ""}
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">
            Sin lastPropose — corre POST auto-propose dry-run en esta API.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
