/**
 * AUTO-20D/AUTO-22 — sección de cabina con la PROCEDENCIA y los TRES NIVELES de evidencia AUTO.
 *
 * Presenta el artefacto `auto20c_evidence_artifact_v1` (el que guarda `auto_evidence_run.py`)
 * importado a mano, con un badge de procedencia imposible de malinterpretar (PAPER REAL / FIXTURE
 * SINTÉTICO / SIN MATERIAL / DESCONOCIDA) y los niveles que pide la cabina: **1) MATERIAL**,
 * **2) GLOBAL EVIDENCE + CALIBRATION** y **3) CONTEXTO** (régimen actual, evidencia por estrategia
 * y correlación entre pares), cerrando con **ALLOCATION congelado**. No recalcula ninguna métrica:
 * lee el `report` verbatim y muestra "NO MEDIDO" donde el instrumento no midió (nunca un cero
 * inventado), también para una correlación no medida.
 *
 * @see features/operational-console/auto-evidence-report.ts
 */

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  EVIDENCE_ARTIFACT_DISCLAIMER,
  buildEvidenceView,
  parseAutoEvidenceArtifact,
  type AutoEvidenceArtifact,
  type EvidenceRow,
  type EvidenceSourceTone,
} from "@/features/operational-console/auto-evidence-report";
import { useAutoEvidenceArchiveStore } from "@/stores/auto-evidence-archive-store";

function toneClasses(tone: EvidenceSourceTone): string {
  if (tone === "ok") {
    return "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200";
  }
  if (tone === "warn") {
    return "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200";
  }
  if (tone === "danger") {
    return "border-rose-500/40 bg-rose-500/10 text-rose-800 dark:text-rose-200";
  }
  return "border-border bg-muted/40 text-muted-foreground";
}

function originLabel(kind: string): string {
  if (kind === "paper_real")
    return "PAPER real (datos reales de la cuenta PAPER)";
  if (kind === "synthetic_fixture") return "Fixture sintético (NO real)";
  if (kind === "sin_material") return "Sin material";
  return "Desconocido";
}

function executionLabel(artifact: AutoEvidenceArtifact): string {
  if (artifact.executionReality === null) return "NO MEDIDO";
  if (artifact.executionReality === "virtual_paper_only") {
    return "virtual / sin dinero real";
  }
  return artifact.executionReality;
}

function moneyAtRiskLabel(artifact: AutoEvidenceArtifact): string {
  if (artifact.realMoneyAtRisk === false) return "no";
  if (artifact.realMoneyAtRisk === true) return "SÍ (revisar)";
  return "NO MEDIDO";
}

function EvidenceTable({
  rows,
  testId,
}: {
  rows: EvidenceRow[];
  testId?: string;
}) {
  if (rows.length === 0) return null;
  return (
    <dl className="space-y-1" data-testid={testId}>
      {rows.map((row) => (
        <div
          key={row.label}
          className="flex items-baseline justify-between gap-3 text-sm"
          data-inconclusive={row.inconclusive ? "true" : "false"}
        >
          <dt className="text-muted-foreground">{row.label}</dt>
          <dd
            className={cn(
              "text-right tabular-nums",
              row.inconclusive && "text-muted-foreground",
            )}
          >
            {row.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function ImportControls({
  onLoaded,
}: {
  onLoaded: (artifact: AutoEvidenceArtifact, label: string) => void;
}) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [pasted, setPasted] = useState("");
  const [error, setError] = useState<string | null>(null);

  function ingest(raw: unknown, label: string) {
    const result = parseAutoEvidenceArtifact(raw);
    if (!result.ok) {
      setError(result.error);
      return false;
    }
    setError(null);
    onLoaded(result.artifact, label);
    return true;
  }

  async function handleFile(file: File | undefined | null) {
    if (!file) return;
    try {
      const text = await file.text();
      ingest(JSON.parse(text) as unknown, file.name);
    } catch {
      setError("No es JSON válido.");
    }
  }

  return (
    <div className="space-y-2" data-testid="ops-auto-evidence-import">
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          className="hidden"
          data-testid="ops-auto-evidence-file"
          onChange={(event) => {
            void handleFile(event.target.files?.[0]);
          }}
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => fileRef.current?.click()}
          data-testid="ops-auto-evidence-file-cta"
        >
          Importar JSON
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => {
            setPasted("");
            setError(null);
            useAutoEvidenceArchiveStore.getState().clear();
          }}
          data-testid="ops-auto-evidence-clear"
        >
          Limpiar archivo
        </Button>
      </div>
      <textarea
        value={pasted}
        onChange={(event) => setPasted(event.target.value)}
        placeholder="…o pega aquí el JSON de AUTO20C_REAL_PAPER_REPORT.json"
        className="min-h-[72px] w-full rounded-md border border-border bg-transparent p-2 font-mono text-xs"
        data-testid="ops-auto-evidence-paste"
      />
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={pasted.trim() === ""}
        onClick={() => {
          try {
            ingest(JSON.parse(pasted) as unknown, "artefacto pegado");
          } catch {
            setError("No es JSON válido.");
          }
        }}
        data-testid="ops-auto-evidence-paste-cta"
      >
        Cargar pegado
      </Button>
      {error ? (
        <p
          className="text-xs text-destructive"
          data-testid="ops-auto-evidence-import-error"
        >
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function OpsAutoEvidenceSection() {
  const items = useAutoEvidenceArchiveStore((state) => state.items);
  const saveArtifact = useAutoEvidenceArchiveStore(
    (state) => state.saveArtifact,
  );
  const latest = items[0] ?? null;
  const artifact = latest?.artifact ?? null;
  const view = buildEvidenceView(artifact);

  return (
    <Card data-testid="ops-auto-evidence-section">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">AUTO EVIDENCE (AUTO-22)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div
          className={cn(
            "rounded-md border-2 px-3 py-2 font-semibold tracking-tight",
            toneClasses(view.source.tone),
          )}
          data-testid="ops-auto-evidence-badge"
          data-source-kind={view.source.kind}
        >
          <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
            SOURCE
          </span>
          <div className="text-lg font-bold uppercase tracking-tight">
            {view.source.label}
          </div>
          {view.source.subtitle ? (
            <div
              className="mt-1 text-xs font-bold uppercase tracking-wide"
              data-testid="ops-auto-evidence-source-subtitle"
            >
              {view.source.subtitle}
            </div>
          ) : null}
          {view.source.caveat ? (
            <div className="mt-1 text-xs font-normal">{view.source.caveat}</div>
          ) : null}
        </div>

        <div
          className={cn(
            "rounded-md border-2 px-3 py-2 font-semibold tracking-tight",
            toneClasses(view.execution.tone),
          )}
          data-testid="ops-auto-evidence-execution-reality"
          data-execution-kind={view.execution.kind}
        >
          <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
            EXECUTION REALITY
          </span>
          <div className="text-lg font-bold uppercase tracking-tight">
            {view.execution.label}
          </div>
          {view.execution.realMoneyAtRisk !== null ? (
            <div className="mt-1 text-xs font-normal">
              Dinero real en riesgo:{" "}
              {view.execution.realMoneyAtRisk ? "SÍ (revisar)" : "no"}
            </div>
          ) : null}
          {view.execution.caveat ? (
            <div className="mt-1 text-xs font-normal">
              {view.execution.caveat}
            </div>
          ) : null}
        </div>

        {view.warnings.map((warning) => (
          <p
            key={warning}
            className="rounded-md border border-rose-500/40 bg-rose-500/10 px-2 py-1.5 text-xs font-medium text-rose-800 dark:text-rose-200"
            data-testid="ops-auto-evidence-warning"
          >
            {warning}
          </p>
        ))}

        {artifact ? (
          <>
            <dl className="grid gap-2 sm:grid-cols-3">
              <div>
                <dt className="text-xs text-muted-foreground">Origen</dt>
                <dd data-testid="ops-auto-evidence-origin">
                  {originLabel(view.source.kind)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Ejecución</dt>
                <dd data-testid="ops-auto-evidence-execution">
                  {executionLabel(artifact)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">
                  Dinero real en riesgo
                </dt>
                <dd data-testid="ops-auto-evidence-money-at-risk">
                  {moneyAtRiskLabel(artifact)}
                </dd>
              </div>
            </dl>

            <div>
              <h4 className="text-xs font-semibold uppercase text-muted-foreground">
                Nivel 1 — Material
              </h4>
              <EvidenceTable
                rows={view.material}
                testId="ops-auto-evidence-material"
              />
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase text-muted-foreground">
                Nivel 2 — Global evidence
              </h4>
              <EvidenceTable
                rows={view.global}
                testId="ops-auto-evidence-global"
              />
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase text-muted-foreground">
                Nivel 2 — Calibration
              </h4>
              <EvidenceTable
                rows={view.calibration}
                testId="ops-auto-evidence-calibration"
              />
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase text-muted-foreground">
                Nivel 3 — Current regime
              </h4>
              <EvidenceTable
                rows={view.currentRegime}
                testId="ops-auto-evidence-current-regime"
              />
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase text-muted-foreground">
                Nivel 3 — Regime evidence
              </h4>
              <EvidenceTable
                rows={view.regimeEvidence}
                testId="ops-auto-evidence-regime-evidence"
              />
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase text-muted-foreground">
                Nivel 3 — Cross-strategy
              </h4>
              <EvidenceTable
                rows={view.crossStrategy}
                testId="ops-auto-evidence-cross-strategy"
              />
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase text-muted-foreground">
                Allocation
              </h4>
              <EvidenceTable
                rows={view.allocation}
                testId="ops-auto-evidence-allocation"
              />
            </div>

            {view.perimeter.length > 0 ? (
              <div>
                <h4 className="text-xs font-semibold uppercase text-muted-foreground">
                  Perímetro
                </h4>
                <EvidenceTable
                  rows={view.perimeter}
                  testId="ops-auto-evidence-perimeter"
                />
              </div>
            ) : null}
          </>
        ) : (
          <p className="text-xs text-muted-foreground">
            Sin artefacto importado: la corrida PAPER real (AUTO-22) sigue
            siendo un paso operativo. Ejecuta{" "}
            <code className="text-[0.7rem]">
              auto_evidence_run.py --account-id &lt;uuid&gt; --strategy-version
              &lt;v&gt;
            </code>{" "}
            y después importa{" "}
            <code className="text-[0.7rem]">artifact.json</code> aquí.
          </p>
        )}

        <ImportControls
          onLoaded={(next, label) => {
            saveArtifact(next, { label });
          }}
        />

        <p className="text-xs text-muted-foreground">
          {EVIDENCE_ARTIFACT_DISCLAIMER}
        </p>
      </CardContent>
    </Card>
  );
}
