/**
 * Buscador de índices mundiales + Suscribir (job+poll L2).
 */

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  CatalogIndexEntryDto,
  IndexSubscribeJobDto,
  InstrumentListSummaryDto,
  MarketIndexHitDto,
  SubscribeMarketIndexResultDto,
} from "@bolsa/shared";
import { catalogListIdForIndex } from "@bolsa/shared";
import { Search } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { inputClassName } from "@/components/ui/dialog";
import { listConfigForSelection } from "@/lib/list-sync";
import { setManualListSelection } from "@/lib/list-selection-guard";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { cn } from "@/lib/utils";

type Props = {
  apiLists: InstrumentListSummaryDto[];
  onError: (message: string | null) => void;
};

type StepStatus = "pending" | "active" | "done" | "warn" | "error";
type ProgressStep = {
  id: string;
  label: string;
  detail?: string;
  status: StepStatus;
};

const ASYNC_THRESHOLD = 40;

function statusMark(status: StepStatus): string {
  if (status === "done") return "✓";
  if (status === "active") return "…";
  if (status === "warn") return "!";
  if (status === "error") return "×";
  return "·";
}

function sleep(ms: number) {
  return new Promise((r) => window.setTimeout(r, ms));
}

export function ListHubIndexSearch({ apiLists, onError }: Props) {
  const queryClient = useQueryClient();
  const listConfig = useWorkspaceStore((s) => s.workspace.list);
  const updateListConfig = useWorkspaceStore((s) => s.updateListConfig);
  const save = useWorkspaceStore((s) => s.save);
  const activeChartId = useWorkspaceStore((s) => s.workspace.activeChartId);

  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [steps, setSteps] = useState<ProgressStep[]>([]);
  const [extraNotes, setExtraNotes] = useState<string[]>([]);

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(query.trim()), 280);
    return () => window.clearTimeout(t);
  }, [query]);

  const searchQuery = useQuery({
    queryKey: ["market-indices-search", debounced],
    queryFn: () => api.searchMarketIndices(debounced, 10),
    enabled: debounced.length >= 2,
    staleTime: 60_000,
  });

  const catalogQuery = useQuery({
    queryKey: ["market-indices-catalog"],
    queryFn: () => api.getMarketIndexCatalog(),
    staleTime: 120_000,
  });

  const hits = searchQuery.data?.data ?? [];
  const catalog = catalogQuery.data?.data ?? [];

  function initSteps(displayName: string) {
    setExtraNotes([]);
    setSteps([
      {
        id: "resolve",
        label: `Resolver constitutivos de ${displayName}`,
        status: "active",
      },
      { id: "count", label: "Contar miembros del índice", status: "pending" },
      {
        id: "hydrate",
        label: "Comprobar BD e importar faltantes",
        status: "pending",
      },
      {
        id: "result",
        label: "Materializar lista (altas / bajas)",
        status: "pending",
      },
    ]);
  }

  function patchStep(id: string, patch: Partial<ProgressStep>) {
    setSteps((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  function applyListSelection(data: {
    listId: string;
    displayName: string;
    instrumentIds: string[];
  }) {
    void queryClient.invalidateQueries({ queryKey: ["lists"] });
    void queryClient.invalidateQueries({ queryKey: ["instruments"] });
    const summary: InstrumentListSummaryDto = {
      id: data.listId,
      name: data.displayName,
      source: "catalog",
      itemCount: data.instrumentIds.length,
      updatedAt: new Date().toISOString(),
      kind: "linked_universe",
    };
    const carouselListIds = [
      ...new Set([...(listConfig.carouselListIds ?? []), summary.id]),
    ];
    const carouselPinnedListNames = [
      ...new Set([...(listConfig.carouselPinnedListNames ?? []), summary.name]),
    ];
    updateListConfig({
      ...listConfigForSelection(summary.id, [...apiLists, summary]),
      carouselListIds,
      carouselPinnedListNames,
      carouselInitialized: true,
      watchlistTab: "values",
    });
    setManualListSelection(summary.id, activeChartId);
    save();
    setQuery("");
  }

  function finishFromSyncResult(data: SubscribeMarketIndexResultDto) {
    const { progress } = data;
    const linked = data.instrumentIds.length;
    const missingAfter = Math.max(0, progress.total - linked);
    const isPartial =
      data.status !== "ready" || missingAfter > 0 || progress.failed.length > 0;
    patchStep("hydrate", {
      status: progress.failed.length ? "warn" : "done",
      label: `BD: ${progress.alreadyPresent} ya estaban · +${progress.imported} importados`,
      detail: progress.failed.length
        ? `${progress.failed.length} no se pudieron importar`
        : missingAfter
          ? `${missingAfter} aún sin instrumento tras el pase`
          : "Todos los constitutivos con instrumento en BD",
    });
    const joinN = progress.joined?.length ?? 0;
    const leaveN = progress.left?.length ?? 0;
    patchStep("result", {
      status: isPartial ? "warn" : "done",
      label: `Lista «${data.displayName}»: ${linked}/${progress.total} vinculados`,
      detail: [
        joinN ? `+${joinN} altas` : null,
        leaveN
          ? `−${leaveN} bajas (salen del índice; NO se borran de BD)`
          : null,
        !joinN && !leaveN ? "Membresía sin cambios de alta/baja" : null,
        `estado ${data.status}`,
      ]
        .filter(Boolean)
        .join(" · "),
    });
    const notes: string[] = [];
    if (missingAfter > 0)
      notes.push(`Falta vincular ${missingAfter} constitutivos.`);
    if (progress.failed.length) {
      notes.push(
        `Fallos (muestra): ${progress.failed.slice(0, 6).join(", ")}${
          progress.failed.length > 6 ? ` …(+${progress.failed.length - 6})` : ""
        }`,
      );
    }
    if (!isPartial)
      notes.push("Listo: puedes usar la lista en el carrusel / watchlist.");
    setExtraNotes(notes);
    applyListSelection(data);
  }

  async function pollJob(jobId: string): Promise<IndexSubscribeJobDto> {
    for (;;) {
      const res = await api.getIndexSubscribeJob(jobId);
      const job = res.data;
      const checked = Number(job.result?.checked ?? 0);
      const total = Number(job.result?.total ?? 0);
      const imported = Number(job.result?.imported ?? 0);
      const already = Number(job.result?.alreadyPresent ?? 0);
      const current =
        typeof job.result?.currentSymbol === "string"
          ? job.result.currentSymbol
          : null;
      if (job.status === "processing" || job.status === "pending") {
        patchStep("hydrate", {
          status: "active",
          label:
            total > 0
              ? `Importando ${checked}/${total}`
              : "En cola de suscripción (segundo plano)…",
          detail: [
            already || imported
              ? `${already} en BD · +${imported} importados`
              : null,
            current ? `actual ${current}` : null,
            "Job async · no bloquea la UI",
          ]
            .filter(Boolean)
            .join(" · "),
        });
      }
      if (job.status === "completed" || job.status === "failed") return job;
      await sleep(1500);
    }
  }

  async function runSubscribe(hit: MarketIndexHitDto | CatalogIndexEntryDto) {
    const indexKey = hit.code || hit.yahooSymbol;
    const key = indexKey;
    const displayName = hit.displayName;
    onError(null);
    setBusyKey(key);
    initSteps(displayName);
    try {
      const preview = await api.getMarketIndexConstituents(indexKey);
      const total = preview.data.members.length;
      const provider = preview.data.provider;
      const sample = preview.data.members
        .slice(0, 4)
        .map((m) => m.yahooSymbol)
        .join(", ");
      patchStep("resolve", {
        status: "done",
        detail: `provider ${provider}${preview.data.asOf ? ` · asOf ${preview.data.asOf}` : ""}`,
      });
      patchStep("count", {
        status: "done",
        label: `${total} constitutivos detectados`,
        detail: sample ? `ej. ${sample}${total > 4 ? "…" : ""}` : undefined,
      });

      const useAsync = total >= ASYNC_THRESHOLD;
      patchStep("hydrate", {
        status: "active",
        label: useAsync
          ? `Cola async (≈${total} · progreso en segundo plano)`
          : "Comprobar BD e importar faltantes",
        detail: useAsync
          ? "Job L2: puedes seguir usando Trading mientras importa"
          : "Si partes de 0, se importa cada símbolo ausente",
      });

      if (useAsync) {
        const enqueued = await api.enqueueIndexSubscribeJob({
          indexKey,
          syncBars: false,
        });
        const job = await pollJob(enqueued.data.id);
        if (job.status === "failed") {
          throw new ApiError(
            job.error || "Falló la suscripción del índice",
            500,
          );
        }
        const instrumentIds =
          (job.result?.instrumentIds as string[] | undefined) ?? [];
        const fake: SubscribeMarketIndexResultDto = {
          listId: String(job.result?.listId ?? ""),
          indexCode: String(job.result?.indexCode ?? indexKey),
          displayName: String(job.result?.displayName ?? displayName),
          yahooIndexSymbol: String(job.result?.yahooIndexSymbol ?? ""),
          contentHash: String(job.result?.contentHash ?? ""),
          instrumentIds,
          progress: {
            total: Number(job.result?.total ?? total),
            alreadyPresent: Number(job.result?.alreadyPresent ?? 0),
            imported: Number(job.result?.imported ?? 0),
            failed: (job.result?.failed as string[] | undefined) ?? [],
            joined: (job.result?.joined as string[] | undefined) ?? [],
            left: (job.result?.left as string[] | undefined) ?? [],
          },
          status: String(job.result?.status ?? "partial"),
        };
        finishFromSyncResult(fake);
      } else {
        const response = await api.subscribeMarketIndex({
          indexKey,
          syncBars: false,
        });
        finishFromSyncResult(response.data);
      }
    } catch (err) {
      setSteps((prev) =>
        prev.map((s) =>
          s.status === "active"
            ? {
                ...s,
                status: "error",
                detail: err instanceof ApiError ? err.message : "Error",
              }
            : s,
        ),
      );
      setExtraNotes([]);
      onError(
        err instanceof ApiError
          ? err.message
          : "No se pudo suscribir el índice",
      );
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <section className="shrink-0 space-y-1.5 border-b border-border bg-muted/10 p-2">
      <p className="text-[11px] font-medium text-foreground">
        Índices mundiales
      </p>
      <p className="text-[10px] leading-snug text-muted-foreground">
        Catálogo estándar + búsqueda. Suscribir usa la misma tubería para todos
        (IBEX, S&P, DAX…): constitutivos → import faltantes → lista vinculada.
      </p>
      {catalog.length > 0 ? (
        <ul className="flex flex-wrap gap-1">
          {catalog.map((entry) => {
            const already = apiLists.some(
              (l) => l.id === entry.listId && l.source === "catalog",
            );
            const isBusy = busyKey === entry.code;
            return (
              <li key={entry.code}>
                <Button
                  type="button"
                  size="sm"
                  variant={
                    entry.constituentReady
                      ? already
                        ? "outline"
                        : "default"
                      : "ghost"
                  }
                  className="h-6 text-[10px]"
                  disabled={!entry.constituentReady || Boolean(busyKey)}
                  title={
                    entry.constituentReady
                      ? already
                        ? "Re-sincronizar"
                        : `Suscribir ${entry.displayName}`
                      : "Provider de constitutivos pendiente (misma tubería cuando esté listo)"
                  }
                  onClick={() => void runSubscribe(entry)}
                >
                  {isBusy
                    ? "…"
                    : already
                      ? `${entry.displayName} · Sync`
                      : entry.displayName}
                </Button>
              </li>
            );
          })}
        </ul>
      ) : null}
      <div className="relative">
        <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          className={cn(inputClassName, "pl-7")}
          value={query}
          placeholder="Buscar: IBEX, SP500, DAX…"
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Buscar índice"
          disabled={Boolean(busyKey)}
        />
      </div>
      {debounced.length >= 2 && searchQuery.isFetching ? (
        <p className="text-[10px] text-muted-foreground">Buscando…</p>
      ) : null}
      {hits.length > 0 ? (
        <ul className="max-h-36 space-y-1 overflow-auto rounded-md border border-border/70 bg-background p-1">
          {hits.map((hit) => {
            const key = hit.code ?? hit.yahooSymbol;
            const listId = hit.code ? catalogListIdForIndex(hit.code) : null;
            const already = Boolean(
              listId &&
              apiLists.some((l) => l.id === listId && l.source === "catalog"),
            );
            const isBusy = busyKey === key;
            return (
              <li
                key={key}
                className="flex items-center justify-between gap-2 rounded px-1.5 py-1 text-[11px]"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-foreground">
                    {hit.displayName}
                  </p>
                  <p className="truncate text-[10px] text-muted-foreground">
                    {hit.yahooSymbol}
                    {hit.region ? ` · ${hit.region}` : ""}
                    {hit.constituentReady
                      ? " · Suscribir activo"
                      : " · constitutivos pronto"}
                  </p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant={hit.constituentReady ? "default" : "outline"}
                  className="h-7 shrink-0 text-[10px]"
                  disabled={!hit.constituentReady || Boolean(busyKey)}
                  onClick={() => void runSubscribe(hit)}
                >
                  {isBusy ? "…" : already ? "Sync" : "Suscribir"}
                </Button>
              </li>
            );
          })}
        </ul>
      ) : null}
      {steps.length > 0 ? (
        <div className="max-h-40 space-y-1 overflow-auto rounded-md border border-border/60 bg-background/80 px-2 py-1.5 text-[10px] leading-snug">
          <p className="font-medium text-foreground">Proceso de suscripción</p>
          <ol className="space-y-1 text-muted-foreground">
            {steps.map((step) => (
              <li key={step.id} className="flex gap-1.5">
                <span
                  className={cn(
                    "w-3 shrink-0 font-semibold",
                    step.status === "done" && "text-emerald-600",
                    step.status === "active" && "text-foreground",
                    step.status === "warn" && "text-amber-600",
                    step.status === "error" && "text-destructive",
                  )}
                  aria-hidden
                >
                  {statusMark(step.status)}
                </span>
                <span>
                  <span
                    className={cn(
                      step.status === "active" || step.status === "done"
                        ? "text-foreground"
                        : undefined,
                    )}
                  >
                    {step.label}
                  </span>
                  {step.detail ? (
                    <span className="mt-0.5 block opacity-80">
                      {step.detail}
                    </span>
                  ) : null}
                </span>
              </li>
            ))}
          </ol>
          {extraNotes.length > 0 ? (
            <ul className="mt-1 space-y-0.5 border-t border-border/50 pt-1 text-muted-foreground">
              {extraNotes.map((note) => (
                <li key={note}>→ {note}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
