/**
 * AUTO · ANÁLISIS (ADR-044) — DÍA-D · Evidencia · Estrategias · Investigación.
 *
 * Sub-pestañas con la pestaña activa en la URL (`?tab=`), de modo que la vista
 * es compartible. Reutiliza el panel DÍA-D y la sección de evidencia existentes;
 * Estrategias e Investigación enlazan a Laboratorio y Asesor (no se reimplementan).
 */

import { Link, useSearchParams } from "react-router-dom";
import {
  AutoSectionBlockHeading,
  AutoSectionHeading,
} from "@/components/layout/auto-workspace-layout";
import { DiaDAutoPanel } from "@/features/auto-monitor/dia-d-auto-panel";
import { OpsAutoEvidenceSection } from "@/features/operational-console/auto-evidence-section";
import { cn } from "@/lib/utils";

const ANALISIS_TABS = [
  { id: "dia-d", label: "DÍA-D" },
  { id: "evidencia", label: "Evidencia" },
  { id: "estrategias", label: "Estrategias" },
  { id: "investigacion", label: "Investigación" },
] as const;

type AnalisisTabId = (typeof ANALISIS_TABS)[number]["id"];

function readAnalisisTab(searchParams: URLSearchParams): AnalisisTabId {
  const raw = searchParams.get("tab");
  return (ANALISIS_TABS as readonly { id: string }[]).some((t) => t.id === raw)
    ? (raw as AnalisisTabId)
    : "dia-d";
}

export function AutoAnalisisPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = readAnalisisTab(searchParams);

  const setTab = (next: AnalisisTabId) => {
    setSearchParams(
      (prev) => {
        const params = new URLSearchParams(prev);
        params.set("tab", next);
        return params;
      },
      { replace: true },
    );
  };

  return (
    <div className="space-y-6" data-testid="auto-analisis-page">
      <AutoSectionHeading
        title="Análisis"
        description="Conocimiento cross-ciclo: DÍA-D, evidencia, estrategias e investigación. Explica; no opera."
      />

      <div
        role="tablist"
        aria-label="Secciones de análisis"
        className="flex flex-wrap gap-1 border-b border-border pb-2"
      >
        {ANALISIS_TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            data-testid={`auto-analisis-tab-${item.id}`}
            onClick={() => setTab(item.id)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground",
              tab === item.id && "bg-accent text-primary",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "dia-d" ? (
        <section className="space-y-2" aria-labelledby="auto-analisis-dia-d">
          <AutoSectionBlockHeading id="auto-analisis-dia-d">
            DÍA-D · feedback OOS
          </AutoSectionBlockHeading>
          <DiaDAutoPanel />
        </section>
      ) : null}

      {tab === "evidencia" ? (
        <section
          className="space-y-2"
          aria-labelledby="auto-analisis-evidencia"
        >
          <AutoSectionBlockHeading id="auto-analisis-evidencia">
            Evidencia AUTO
          </AutoSectionBlockHeading>
          <OpsAutoEvidenceSection />
        </section>
      ) : null}

      {tab === "estrategias" ? (
        <section
          className="space-y-2"
          aria-labelledby="auto-analisis-estrategias"
        >
          <AutoSectionBlockHeading id="auto-analisis-estrategias">
            Estrategias
          </AutoSectionBlockHeading>
          <p className="text-sm text-muted-foreground">
            Biblioteca de estrategias, pruebas y optimización viven en el{" "}
            <Link
              to="/backtests?tab=strategies"
              className="underline hover:text-primary"
            >
              Laboratorio · Biblioteca
            </Link>
            .
          </p>
        </section>
      ) : null}

      {tab === "investigacion" ? (
        <section
          className="space-y-2"
          aria-labelledby="auto-analisis-investigacion"
        >
          <AutoSectionBlockHeading id="auto-analisis-investigacion">
            Investigación
          </AutoSectionBlockHeading>
          <p className="text-sm text-muted-foreground">
            Dictamen y ledger científico viven en el{" "}
            <Link to="/research" className="underline hover:text-primary">
              Asesor
            </Link>
            .
          </p>
        </section>
      ) : null}
    </div>
  );
}
