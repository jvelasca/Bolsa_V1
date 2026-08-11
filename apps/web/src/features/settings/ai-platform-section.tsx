import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { SettingsSection } from "@/features/settings/settings-section";
import { EffectivenessPanel } from "@/features/settings/effectiveness-panel";
import { SupervisedF3Panel } from "@/features/settings/supervised-f3-panel";
import {
  AI_COGNITIVE_PHASES,
  AI_DECISION_PIPELINE,
  AI_EXECUTION_PHASES,
  AI_OUT_OF_SCOPE,
  AI_PRINCIPLE,
  AI_PRODUCT_FROZEN,
  AI_PRODUCT_GOALS,
  AI_PRODUCT_NEXT,
  AI_STACK_SUMMARY,
  AI_STATUS_LABEL,
  AI_TECH_BUILDING_BLOCKS,
  AI_TRACKER_SYNC,
  AI_WHERE_KIND_LABEL,
  AI_WHERE_MAP,
  type AiTrackItem,
  type AiTrackStatus,
  type AiWhereKind,
} from "@/features/settings/ai-platform-tracker";

const STATUS_CLASS: Record<AiTrackStatus, string> = {
  done: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  partial: "border-amber-500/40 bg-amber-500/10 text-amber-400",
  next: "border-sky-500/40 bg-sky-500/10 text-sky-400",
  planned: "border-border bg-muted/30 text-muted-foreground",
  blocked: "border-red-500/40 bg-red-500/10 text-red-400",
};

const WHERE_KIND_CLASS: Record<AiWhereKind, string> = {
  local: "border-sky-500/40 bg-sky-500/10 text-sky-400",
  llm_optional: "border-violet-500/40 bg-violet-500/10 text-violet-300",
  deterministic: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  hybrid: "border-amber-500/40 bg-amber-500/10 text-amber-400",
};

function StatusBadge({ status }: { status: AiTrackStatus }) {
  return (
    <span
      className={cn(
        "shrink-0 rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        STATUS_CLASS[status],
      )}
    >
      {AI_STATUS_LABEL[status]}
    </span>
  );
}

function TrackList({ items }: { items: AiTrackItem[] }) {
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li
          key={item.id}
          className="flex flex-col gap-1 rounded-md border border-border/70 px-3 py-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3"
        >
          <div className="min-w-0 space-y-1">
            <p className="text-sm font-medium text-foreground">{item.title}</p>
            <p className="text-xs text-muted-foreground">
              <span className="text-foreground/80">Cómo: </span>
              {item.how}
            </p>
            {item.note ? (
              <p className="text-xs text-muted-foreground">
                <span className="text-foreground/80">Nota: </span>
                {item.note}
              </p>
            ) : null}
            {item.docRef ? (
              <p className="text-[10px] text-muted-foreground/80">
                {item.docRef}
              </p>
            ) : null}
          </div>
          <StatusBadge status={item.status} />
        </li>
      ))}
    </ul>
  );
}

function WhereWeUseAiCard() {
  return (
    <Card id="ai-where-map">
      <CardHeader>
        <CardTitle>Dónde usamos IA</CardTitle>
        <CardDescription>
          Aclara ranking local, LLM narrador, Lab determinista y Decision
          Engine. El LLM nunca escribe TOP ni PnL.
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full min-w-[36rem] border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="py-2 pr-3 font-medium">Punto de la app</th>
              <th className="py-2 pr-3 font-medium">Tipo</th>
              <th className="py-2 pr-3 font-medium">Rol</th>
              <th className="py-2 font-medium">Ranking / órdenes</th>
            </tr>
          </thead>
          <tbody>
            {AI_WHERE_MAP.map((row) => (
              <tr key={row.id} className="border-b border-border/60 align-top">
                <td className="py-2.5 pr-3 font-medium text-foreground">
                  {row.surface}
                </td>
                <td className="py-2.5 pr-3">
                  <span
                    className={cn(
                      "inline-block rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                      WHERE_KIND_CLASS[row.kind],
                    )}
                  >
                    {AI_WHERE_KIND_LABEL[row.kind]}
                  </span>
                </td>
                <td className="py-2.5 pr-3 text-muted-foreground">
                  {row.role}
                </td>
                <td className="py-2.5 text-muted-foreground">
                  {row.rankingOrOrders}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-[10px] text-muted-foreground/80">
          Narración LLM Coach ON/OFF → rail del Asistente. CORE-P / CORE A /
          CORE B → objetivos abajo.
        </p>
      </CardContent>
    </Card>
  );
}

function LiveRuntimeCard() {
  const statusQuery = useQuery({
    queryKey: ["ai-status"],
    queryFn: async () => (await api.getAiStatus()).data,
    refetchInterval: 30_000,
    retry: 1,
  });

  const catalogQuery = useQuery({
    queryKey: ["features-catalog"],
    queryFn: async () => (await api.getFeatureCatalog()).data,
    staleTime: 60_000,
    retry: 1,
  });

  const status = statusQuery.data;
  const defCount = catalogQuery.data?.defs?.length ?? null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Runtime en este entorno</CardTitle>
        <CardDescription>
          Lectura en vivo de <code className="text-xs">GET /api/ai/status</code>{" "}
          y catálogo de features
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {statusQuery.isLoading && (
          <p className="text-muted-foreground">Consultando governance…</p>
        )}
        {statusQuery.isError && (
          <p className="text-destructive">
            No se pudo leer /api/ai/status — ¿API en marcha con bolsa_ai
            arrancado?
          </p>
        )}
        {status && (
          <dl className="grid gap-2 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-muted-foreground">
                Modo / proveedor preferido
              </dt>
              <dd className="font-medium">
                {status.mode} · {status.preferredProvider}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Audit sink</dt>
              <dd className="font-medium">{status.auditSink}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Ollama</dt>
              <dd
                className={
                  status.ollamaAvailable
                    ? "text-emerald-400"
                    : "text-muted-foreground"
                }
              >
                {status.ollamaAvailable ? "Disponible" : "No disponible"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">OpenAI</dt>
              <dd
                className={
                  status.openaiAvailable
                    ? "text-emerald-400"
                    : "text-muted-foreground"
                }
              >
                {status.openaiAvailable
                  ? "Disponible"
                  : "No configurado / offline"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">
                Llamadas registradas (proceso)
              </dt>
              <dd className="font-medium tabular-nums">
                {status.callsRecorded}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Producer</dt>
              <dd className="font-mono text-xs">{status.producerVersion}</dd>
            </div>
          </dl>
        )}
        <p className="text-xs text-muted-foreground">
          Feature Registry (catálogo):{" "}
          {catalogQuery.isError
            ? "error al cargar"
            : defCount == null
              ? "…"
              : `${defCount} definiciones bootstrap`}
        </p>
      </CardContent>
    </Card>
  );
}

export function AiPlatformSection({
  compact = false,
  focusPanel = null,
}: {
  compact?: boolean;
  /** Scroll al panel F3 tras Proponer desde Finalistas/chart/scan. */
  focusPanel?: "supervised-f3" | null;
}) {
  useEffect(() => {
    if (focusPanel !== "supervised-f3") return;
    const t = window.setTimeout(() => {
      document
        .getElementById("supervised-f3-panel")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
    return () => window.clearTimeout(t);
  }, [focusPanel]);

  const body = (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Seguimiento plataforma IA</CardTitle>
          <CardDescription>
            Información alineada con{" "}
            <code className="text-xs">{AI_TRACKER_SYNC.solutionDoc}</code> ·{" "}
            {AI_TRACKER_SYNC.asOf}. Al avanzar F1–F6, actualiza el tracker TS y
            el encabezado del doc. Los ajustes de sync/cuenta están en
            Configuración, no aquí.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="rounded-md border border-primary/30 bg-primary/5 p-3">
            <p className="font-medium text-foreground">{AI_PRINCIPLE.title}</p>
            <p className="mt-1 text-muted-foreground">{AI_PRINCIPLE.body}</p>
          </div>
          <div className="rounded-md border border-border bg-muted/20 p-3 space-y-2">
            <p className="font-medium text-foreground">
              {AI_DECISION_PIPELINE.title}
            </p>
            <ol className="list-decimal space-y-1 pl-4 text-xs text-muted-foreground">
              {AI_DECISION_PIPELINE.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
              {AI_DECISION_PIPELINE.rules.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
            <p className="text-[10px] text-muted-foreground/80">
              {AI_DECISION_PIPELINE.docRef}
            </p>
          </div>
          <p className="text-xs text-muted-foreground">
            RFCs:{" "}
            <code className="text-[10px]">{AI_TRACKER_SYNC.rfcIndex}</code> ·
            Governance{" "}
            <code className="text-[10px]">{AI_TRACKER_SYNC.governanceRfc}</code>{" "}
            · Features{" "}
            <code className="text-[10px]">{AI_TRACKER_SYNC.featureRfc}</code> ·
            Cognitive{" "}
            <code className="text-[10px]">{AI_TRACKER_SYNC.cognitiveRfc}</code>
          </p>
        </CardContent>
      </Card>

      <WhereWeUseAiCard />

      <LiveRuntimeCard />

      <Card>
        <CardHeader>
          <CardTitle>Qué queremos conseguir</CardTitle>
          <CardDescription>
            Capacidades de producto · badge Hecho / Parcial / Planificado.
            Congelados ≠ pendientes accionables.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <TrackList items={AI_PRODUCT_GOALS} />
          <div className="rounded-md border border-sky-500/30 bg-sky-500/5 p-3">
            <p className="text-sm font-medium text-foreground">
              Siguiente (accionable)
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
              {AI_PRODUCT_NEXT.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
          <div className="rounded-md border border-border bg-muted/20 p-3">
            <p className="text-sm font-medium text-foreground">
              Congelado (sin decisión)
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
              {AI_PRODUCT_FROZEN.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Núcleo cognitivo (RFC-008)</CardTitle>
          <CardDescription>
            Decision Engine — Profile / Policy / Evidence. Configuración →
            Perfil inversor.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <TrackList items={AI_COGNITIVE_PHASES} />
        </CardContent>
      </Card>

      <EffectivenessPanel compact={compact} />

      <SupervisedF3Panel />

      <Card>
        <CardHeader>
          <CardTitle>Fases de ejecución</CardTitle>
          <CardDescription>
            Post-constitución — orden en AI_PLATFORM_SOLUTION §8
          </CardDescription>
        </CardHeader>
        <CardContent>
          <TrackList items={AI_EXECUTION_PHASES} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Cómo lo hacemos (piezas técnicas)</CardTitle>
          <CardDescription>Proxy, registries, audit, drafts</CardDescription>
        </CardHeader>
        <CardContent>
          <TrackList items={AI_TECH_BUILDING_BLOCKS} />
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Stack cerrado (D1–D10)</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {AI_STACK_SUMMARY.map((row) => (
                <li key={row.layer}>
                  <span className="font-medium text-foreground">
                    {row.layer}:{" "}
                  </span>
                  <span className="text-muted-foreground">{row.choice}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Fuera de alcance ahora</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
              {AI_OUT_OF_SCOPE.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </>
  );

  if (compact) {
    return <div className="space-y-4">{body}</div>;
  }

  return (
    <SettingsSection
      id="ai-platform"
      title="IA"
      description="Objetivos, método y estado de la plataforma de inteligencia artificial."
    >
      {body}
    </SettingsSection>
  );
}
