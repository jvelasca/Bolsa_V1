/**
 * F3 — Assessments → DecisionRuntime → Recommendation (supervisado).
 *
 * Cola cliente (`useSupervisedF3QueueStore`) con badges de origen
 * (Finalistas / Scan / Gráfico / Manual). Callout Confirm reforzado si origen Finalistas.
 * Ancla DOM: `id="supervised-f3-panel"` para scroll desde Ayuda.
 *
 * Entrada Finalistas = Camino C (`PAPER_PATH_SUPERVISED`); ≠ Desplegar en demo (A).
 *
 * @see docs/engineering/backtesting-funnel-handoff-2026-07-29.md
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type {
  AssessmentV1,
  EvidenceAssessmentV1,
  FundamentalAssessmentV1,
  MacroAssessmentV1,
  NewsAssessmentV1,
  TechnicalAssessmentV1,
} from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  resolveSupervisedQueueOrigin,
  supervisedQueueOriginLabel,
  type SupervisedProposePayload,
  useSupervisedF3QueueStore,
} from "@/stores/supervised-f3-queue-store";
import {
  demoBookAllowsExecute,
  loadDemoBookPrefs,
  suggestQuantityFromCash,
  type DemoBookCountryPrefer,
} from "@/features/trading/demo-book-prefs";
import {
  inferHomeCountry,
  optimalScoreFromPayload,
  rankByOptimalThenGeo,
} from "@/features/trading/demo-book-geo-rank";
import { recordSemiConfirmMandate } from "@/features/trading/semi-confirm-mandate";
import {
  conflictForActive,
  findHmConflicts,
} from "@/features/trading/semi-hm-conflict";
import { PAPER_PATH_SUPERVISED } from "@/features/settings/paper-paths-copy";

type ProposePayload = SupervisedProposePayload;

function BiasBadge({ bias }: { bias: string }) {
  const cls =
    bias === "bullish"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
      : bias === "bearish"
        ? "border-red-500/40 bg-red-500/10 text-red-400"
        : "border-border bg-muted/40 text-muted-foreground";
  return (
    <span
      className={cn(
        "rounded border px-2 py-0.5 text-[10px] font-semibold uppercase",
        cls,
      )}
    >
      {bias}
    </span>
  );
}

function ComponentBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(((value + 1) / 2) * 100);
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{label}</span>
        <span>{value.toFixed(2)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full",
            value > 0.1
              ? "bg-emerald-500/70"
              : value < -0.1
                ? "bg-red-500/70"
                : "bg-muted-foreground/40",
          )}
          style={{ width: `${Math.max(4, pct)}%` }}
        />
      </div>
    </div>
  );
}

function AssessmentBlock({
  title,
  bias,
  score,
  confidence,
  coverage,
  facts,
  warnings,
  components,
  extra,
}: {
  title: string;
  bias?: string;
  score: number;
  confidence: number;
  coverage?: number;
  facts?: string[];
  warnings?: string[];
  components?: Record<string, number | undefined>;
  extra?: string;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/20 px-3 py-2 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-foreground">{title}</span>
        {bias ? <BiasBadge bias={bias} /> : null}
        <span className="text-[10px] text-muted-foreground">
          score {score.toFixed(3)} · conf {confidence.toFixed(2)}
          {coverage != null ? ` · cov ${coverage.toFixed(2)}` : ""}
          {extra ? ` · ${extra}` : ""}
        </span>
      </div>
      {components ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {Object.entries(components)
            .filter(([, v]) => typeof v === "number")
            .slice(0, 4)
            .map(([k, v]) => (
              <ComponentBar key={k} label={k} value={v as number} />
            ))}
        </div>
      ) : null}
      {facts?.length ? (
        <ul className="list-disc pl-4 text-[11px] text-muted-foreground">
          {facts.slice(0, 5).map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      ) : null}
      {warnings?.length ? (
        <p className="text-[11px] text-amber-700 dark:text-amber-400">
          {warnings.join(" · ")}
        </p>
      ) : null}
    </div>
  );
}

export function SupervisedF3Panel() {
  const { account, effectiveAccountId } = useActiveAccount();
  const [instrumentId, setInstrumentId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [price, setPrice] = useState("");
  const [includeFund, setIncludeFund] = useState(true);
  const [includeMacro, setIncludeMacro] = useState(true);
  const [includeEvidence, setIncludeEvidence] = useState(true);
  const [includeNews, setIncludeNews] = useState(true);
  const [pending, setPending] = useState<ProposePayload | null>(null);
  const [log, setLog] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [bookMode, setBookMode] = useState(() => loadDemoBookPrefs().mode);
  const [countryPrefer, setCountryPrefer] = useState<DemoBookCountryPrefer>(
    () => loadDemoBookPrefs().countryPrefer,
  );

  const queueItems = useSupervisedF3QueueStore((s) => s.items);
  const activeId = useSupervisedF3QueueStore((s) => s.activeId);
  const setActive = useSupervisedF3QueueStore((s) => s.setActive);
  const removeFromQueue = useSupervisedF3QueueStore((s) => s.remove);
  const clearQueue = useSupervisedF3QueueStore((s) => s.clear);
  const enqueue = useSupervisedF3QueueStore((s) => s.enqueue);
  const activeItem = queueItems.find((i) => i.id === activeId) ?? null;
  const activeOrigin = activeItem
    ? resolveSupervisedQueueOrigin(activeItem)
    : null;
  const canExecute = demoBookAllowsExecute(bookMode);

  const summaryQuery = useQuery({
    queryKey: ["account-summary", effectiveAccountId],
    queryFn: () => api.getAccountSummary(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 15_000,
  });
  const cash = summaryQuery.data?.data?.cash ?? 0;

  useEffect(() => {
    function refreshBookPrefs() {
      const p = loadDemoBookPrefs();
      setBookMode(p.mode);
      setCountryPrefer(p.countryPrefer);
    }
    refreshBookPrefs();
    window.addEventListener("storage", refreshBookPrefs);
    const id = window.setInterval(refreshBookPrefs, 2000);
    return () => {
      window.removeEventListener("storage", refreshBookPrefs);
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    if (!activeId) return;
    const item = queueItems.find((i) => i.id === activeId);
    if (item) {
      setPending(item.payload);
      setInstrumentId(item.payload.instrumentId);
      const px = item.payload.suggestedPrice ?? item.payload.lastClose ?? null;
      if (px != null) setPrice(String(px));
      const book = loadDemoBookPrefs();
      if (px != null && cash > 0) {
        const q = suggestQuantityFromCash({
          cash,
          price: Number(px),
          sizePctOfCash: book.defaultSizePctOfCash,
        });
        if (q > 0) setQuantity(String(q));
        else if (item.payload.suggestedQuantity)
          setQuantity(String(item.payload.suggestedQuantity));
      } else if (item.payload.suggestedQuantity) {
        setQuantity(String(item.payload.suggestedQuantity));
      }
    }
  }, [activeId, queueItems, cash]);

  const selectedCount = useMemo(
    () => queueItems.filter((i) => selectedIds.has(i.id)).length,
    [queueItems, selectedIds],
  );

  const instrumentsQuery = useQuery({
    queryKey: ["instruments-brief"],
    queryFn: async () => (await api.getInstruments()).data,
    staleTime: 60_000,
  });

  const countryByInstrumentId = useMemo(() => {
    const m = new Map<string, string>();
    for (const inst of instrumentsQuery.data ?? []) {
      if (inst.country) m.set(inst.id, inst.country);
    }
    return m;
  }, [instrumentsQuery.data]);

  const homeCountry = useMemo(
    () => inferHomeCountry({ accountCurrency: account?.currency }),
    [account?.currency],
  );

  /** Cola mostrada: óptimo primero, luego preferencia geo (suave; no filtra). */
  const rankedQueueItems = useMemo(
    () =>
      rankByOptimalThenGeo(
        queueItems.map((item) => ({
          ...item,
          instrumentId: item.payload.instrumentId,
          optimalScore: optimalScoreFromPayload(item.payload),
          country: item.payload.country ?? null,
          tieBreak: item.enqueuedAt,
        })),
        {
          prefer: countryPrefer,
          homeCountry,
          countryByInstrumentId,
        },
      ),
    [queueItems, countryPrefer, homeCountry, countryByInstrumentId],
  );

  const instrumentsForSelect = useMemo(
    () => (instrumentsQuery.data ?? []).slice(0, 40),
    [instrumentsQuery.data],
  );

  const hmConflicts = useMemo(() => findHmConflicts(queueItems), [queueItems]);
  const activeHm = useMemo(
    () => conflictForActive(hmConflicts, activeId),
    [hmConflicts, activeId],
  );

  useEffect(() => {
    if (!instrumentId && instrumentsForSelect[0]?.id) {
      setInstrumentId(instrumentsForSelect[0].id);
    }
  }, [instrumentId, instrumentsForSelect]);

  const propose = useMutation({
    mutationFn: async () => {
      if (!instrumentId.trim()) throw new Error("Indica instrumentId");
      const qty = Number(quantity);
      if (!Number.isFinite(qty) || qty <= 0)
        throw new Error("Cantidad inválida");
      const parsedPrice = price.trim() ? Number(price) : null;
      const res = await api.proposeRecommendation({
        instrumentId: instrumentId.trim(),
        accountId: effectiveAccountId ?? undefined,
        suggestedQuantity: qty,
        suggestedPrice:
          parsedPrice != null && Number.isFinite(parsedPrice)
            ? parsedPrice
            : null,
        includeFundamentals: includeFund,
        includeMacro,
        includeEvidence,
        includeNews,
      });
      return res.data as ProposePayload;
    },
    onSuccess: (rec) => {
      setPending(rec);
      enqueue(rec, { origin: "manual" });
      if (rec.lastClose != null && !price.trim()) {
        setPrice(String(rec.lastClose));
      }
      const n = rec.assessments?.length ?? 1;
      setLog(
        `${rec.recommendationId} · ${rec.action} · ${n} assessment(s) · ${rec.source ?? "v1.1"}`,
      );
    },
    onError: (e: Error) => setLog(e.message),
  });

  const confirm = useMutation({
    mutationFn: async (execute: boolean) => {
      if (!pending || !effectiveAccountId)
        throw new Error("Falta recommendation o cuenta");
      if (execute && !demoBookAllowsExecute(loadDemoBookPrefs().mode)) {
        throw new Error(
          "Libro no está en SEMI: no se puede ejecutar. Cambia el modo en el rail Coach.",
        );
      }
      const qty = Number(quantity);
      const parsedPrice = price.trim() ? Number(price) : null;
      const recommendation: ProposePayload = {
        ...pending,
        suggestedQuantity:
          Number.isFinite(qty) && qty > 0 ? qty : pending.suggestedQuantity,
        suggestedPrice:
          parsedPrice != null && Number.isFinite(parsedPrice)
            ? parsedPrice
            : pending.suggestedPrice,
      };
      return api.confirmOrderIntent({
        recommendation,
        accountId: effectiveAccountId,
        execute,
        sessionId: recommendation.decisionSession?.sessionId,
      });
    },
    onSuccess: (res) => {
      const intent = res.data.intent;
      const trade = res.data.trade;
      const sid = res.data.decisionSession?.sessionId;
      let mandateNote = "";
      if (
        pending &&
        effectiveAccountId &&
        (intent.status === "executed" || intent.status === "authorized")
      ) {
        const m = recordSemiConfirmMandate({
          accountId: effectiveAccountId,
          payload: pending,
          intentStatus: intent.status,
          trade,
        });
        if (m.mandateTenureId) {
          mandateNote = ` · mandato=${m.mandateTenureId.slice(0, 8)}${m.linked ? "+link" : ""}`;
        }
      }
      setLog(
        `Intent ${intent.intentId} · ${intent.status}` +
          (trade
            ? ` · trade=${trade.status}${trade.reason ? ` (${trade.reason})` : ""}`
            : "") +
          (sid ? ` · session=${sid}` : "") +
          mandateNote,
      );
      if (intent.status === "executed" || intent.status === "authorized") {
        if (activeId) {
          removeFromQueue(activeId);
          setSelectedIds((prev) => {
            const next = new Set(prev);
            next.delete(activeId);
            return next;
          });
        }
        setPending(null);
      }
    },
    onError: (e: Error) => setLog(e.message),
  });

  const confirmSelected = useMutation({
    mutationFn: async () => {
      if (!effectiveAccountId) throw new Error("Sin cuenta DEMO");
      if (!demoBookAllowsExecute(loadDemoBookPrefs().mode)) {
        throw new Error("Libro no está en SEMI");
      }
      const selected = new Set(selectedIds);
      const targets = rankedQueueItems.filter((i) => selected.has(i.id));
      if (targets.length === 0) throw new Error("No hay propuestas marcadas");
      const results: string[] = [];
      for (const item of targets) {
        const res = await api.confirmOrderIntent({
          recommendation: item.payload,
          accountId: effectiveAccountId,
          execute: true,
          sessionId: item.payload.decisionSession?.sessionId,
        });
        const st = res.data.intent.status;
        let tag = `${item.symbol ?? item.payload.instrumentId.slice(0, 6)}:${st}`;
        if (st === "executed" || st === "authorized") {
          const m = recordSemiConfirmMandate({
            accountId: effectiveAccountId,
            payload: item.payload,
            intentStatus: st,
            trade: res.data.trade,
          });
          if (m.mandateTenureId) tag += "+M";
          removeFromQueue(item.id);
        }
        results.push(tag);
      }
      return results;
    },
    onSuccess: (results) => {
      setSelectedIds(new Set());
      setLog(`Lote SEMI · ${results.join(" · ")}`);
      void summaryQuery.refetch();
    },
    onError: (e: Error) => setLog(e.message),
  });

  const ta = pending?.technicalAssessment as TechnicalAssessmentV1 | undefined;
  const fa = pending?.fundamentalAssessment as
    | FundamentalAssessmentV1
    | undefined;
  const ma = pending?.macroAssessment as MacroAssessmentV1 | undefined;
  const ea = pending?.evidenceAssessment as EvidenceAssessmentV1 | undefined;
  const na = pending?.newsAssessment as NewsAssessmentV1 | undefined;

  return (
    <Card id="supervised-f3-panel">
      <CardHeader>
        <CardTitle>{PAPER_PATH_SUPERVISED.shortTitle}</CardTitle>
        <CardDescription>
          SEMI · Assessment(s) → Recommendation → Confirm. Cola: Finalistas,
          Radar, Scan, Gráfico.
          {account
            ? ` Cuenta: ${account.name}.`
            : " Selecciona una cuenta activa."}
          {` Modo libro: ${bookMode.toUpperCase()}.`}
          {cash > 0
            ? ` Cash: ${cash.toLocaleString("es-ES", { maximumFractionDigits: 0 })}.`
            : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {rankedQueueItems.length > 0 ? (
          <div className="rounded-md border border-border px-3 py-2 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-medium">
                Cola supervisada ({rankedQueueItems.length})
                {selectedCount > 0 ? ` · ${selectedCount} marcadas` : ""}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="text-[10px] text-muted-foreground hover:underline"
                  onClick={() =>
                    setSelectedIds(new Set(rankedQueueItems.map((i) => i.id)))
                  }
                >
                  Marcar todas
                </button>
                <button
                  type="button"
                  className="text-[10px] text-muted-foreground hover:underline"
                  onClick={() => clearQueue()}
                >
                  Vaciar
                </button>
              </div>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Orden: óptimo → geo ({countryPrefer.replace("_", " ")} · home{" "}
              {homeCountry})
            </p>
            <ul className="max-h-36 space-y-1 overflow-y-auto text-[11px]">
              {rankedQueueItems.map((item) => {
                const origin = resolveSupervisedQueueOrigin(item);
                const checked = selectedIds.has(item.id);
                const country =
                  item.payload.country ??
                  countryByInstrumentId.get(item.payload.instrumentId) ??
                  null;
                return (
                  <li key={item.id} className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        setSelectedIds((prev) => {
                          const next = new Set(prev);
                          if (next.has(item.id)) next.delete(item.id);
                          else next.add(item.id);
                          return next;
                        });
                      }}
                      aria-label={`Marcar ${item.symbol ?? item.payload.instrumentId}`}
                    />
                    <button
                      type="button"
                      className={cn(
                        "min-w-0 flex-1 rounded px-2 py-1 text-left hover:bg-accent",
                        item.id === activeId && "bg-accent",
                      )}
                      onClick={() => setActive(item.id)}
                    >
                      <span className="font-medium text-foreground">
                        {item.symbol ?? item.payload.instrumentId.slice(0, 8)}
                      </span>
                      {country ? (
                        <span className="text-muted-foreground">
                          {" "}
                          · {country}
                        </span>
                      ) : null}
                      {" · "}
                      {item.payload.action}
                      {" · "}
                      <span className="text-muted-foreground">
                        {supervisedQueueOriginLabel(origin)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            <button
              type="button"
              className="w-full rounded-md border border-primary/40 px-2 py-1.5 text-[11px] text-primary hover:bg-accent disabled:opacity-50"
              disabled={
                selectedCount === 0 ||
                confirmSelected.isPending ||
                !canExecute ||
                !effectiveAccountId
              }
              title={
                canExecute
                  ? "Ejecuta en DEMO las propuestas marcadas (SEMI)"
                  : "Pasa el libro a SEMI para ejecutar"
              }
              onClick={() => confirmSelected.mutate()}
            >
              {confirmSelected.isPending
                ? "Ejecutando lote…"
                : `Confirmar seleccionadas + ejecutar (${selectedCount})`}
            </button>
          </div>
        ) : null}

        {activeHm && pending ? (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 space-y-2 text-[11px]">
            <p className="leading-snug text-foreground">
              <strong>H ≠ M</strong> en{" "}
              {activeHm.symbol ?? activeHm.instrumentId.slice(0, 8)}: Finalistas{" "}
              <strong>{activeHm.h.payload.action}</strong> vs Radar{" "}
              <strong>{activeHm.m.payload.action}</strong>. Elige cuál Confirm.
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="rounded border border-primary/40 px-2 py-1 text-primary hover:bg-accent"
                onClick={() => setActive(activeHm.h.id)}
              >
                Elegir H · Finalistas
              </button>
              <button
                type="button"
                className="rounded border border-amber-500/40 px-2 py-1 text-amber-800 hover:bg-accent dark:text-amber-300"
                onClick={() => setActive(activeHm.m.id)}
              >
                Elegir M · Radar
              </button>
            </div>
          </div>
        ) : null}

        {activeOrigin === "finalists" && pending && !activeHm ? (
          <p className="rounded-md border border-primary/35 bg-primary/5 px-3 py-2 text-[11px] leading-snug text-foreground">
            <strong>H · Finalistas</strong> (Camino C / SEMI). Si el momento
            Radar discrepa, elige en Confirm (aceptar, ajustar qty o rechazar).
            Siguiente: Confirmar + ejecutar.
          </p>
        ) : null}
        {activeOrigin === "alarm" && pending && !activeHm ? (
          <p className="rounded-md border border-amber-500/35 bg-amber-500/5 px-3 py-2 text-[11px] leading-snug text-foreground">
            <strong>M · Momento (Radar)</strong>. Contrasta con Finalistas del
            valor si los hay. Tú decides en Confirm.
          </p>
        ) : null}

        {!canExecute ? (
          <p className="rounded-md border border-border px-3 py-2 text-[11px] text-muted-foreground">
            Libro en <strong>{bookMode.toUpperCase()}</strong>: puedes proponer
            e inspeccionar, pero la ejecución DEMO solo en <strong>SEMI</strong>{" "}
            (rail Coach → Libro DEMO).
          </p>
        ) : null}

        <div className="grid gap-2 sm:grid-cols-3">
          <label className="flex flex-col gap-1 sm:col-span-3">
            <span className="text-xs text-muted-foreground">Instrumento</span>
            <select
              className="rounded-md border border-border bg-background px-2 py-1.5"
              value={instrumentId}
              onChange={(e) => setInstrumentId(e.target.value)}
            >
              {instrumentsForSelect.map((inst) => (
                <option key={inst.id} value={inst.id}>
                  {inst.symbol}
                  {inst.name ? ` — ${inst.name}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Cantidad</span>
            <input
              className="rounded-md border border-border bg-background px-2 py-1.5"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">
              Precio (vacío = último close)
            </span>
            <input
              className="rounded-md border border-border bg-background px-2 py-1.5"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="auto"
            />
          </label>
          <div className="flex flex-col gap-1 pt-4 text-xs text-muted-foreground sm:col-span-3">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeFund}
                onChange={(e) => setIncludeFund(e.target.checked)}
              />
              FundamentalAssessment (Yahoo cache)
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeMacro}
                onChange={(e) => setIncludeMacro(e.target.checked)}
              />
              MacroAssessment (Yahoo ^VIX / curva live)
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeEvidence}
                onChange={(e) => setIncludeEvidence(e.target.checked)}
              />
              EvidenceAssessment (último EdgeReport)
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeNews}
                onChange={(e) => setIncludeNews(e.target.checked)}
              />
              NewsAssessment (Yahoo news + calendario)
            </label>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-md border border-border px-3 py-1.5 hover:bg-accent disabled:opacity-50"
            disabled={propose.isPending || !effectiveAccountId || !instrumentId}
            onClick={() => propose.mutate()}
          >
            {propose.isPending ? "Evaluando…" : "Proponer Recommendation"}
          </button>
          <button
            type="button"
            className="rounded-md border border-border px-3 py-1.5 hover:bg-accent disabled:opacity-50"
            disabled={!pending || confirm.isPending}
            onClick={() => confirm.mutate(false)}
          >
            Confirmar Intent
          </button>
          <button
            type="button"
            className="rounded-md border border-primary/40 px-3 py-1.5 text-primary hover:bg-accent disabled:opacity-50"
            disabled={
              !pending ||
              confirm.isPending ||
              pending.action === "wait" ||
              !canExecute
            }
            title={
              canExecute
                ? "Ejecutar en DEMO (SEMI)"
                : "Cambia a SEMI en Libro DEMO"
            }
            onClick={() => confirm.mutate(true)}
          >
            Confirmar + ejecutar
          </button>
        </div>

        {ta ? (
          <AssessmentBlock
            title="Technical Assessment"
            bias={ta.bias}
            score={ta.score}
            confidence={ta.confidence}
            coverage={ta.coverage}
            facts={ta.narrativeFacts ?? ta.facts}
            warnings={ta.warnings}
            components={ta.components}
          />
        ) : null}
        {fa ? (
          <AssessmentBlock
            title="Fundamental Assessment"
            bias={fa.bias}
            score={fa.score}
            confidence={fa.confidence}
            coverage={fa.coverage}
            facts={fa.narrativeFacts ?? fa.facts}
            warnings={fa.warnings}
            components={fa.components}
          />
        ) : null}
        {ma ? (
          <AssessmentBlock
            title="Macro Assessment"
            bias={ma.bias}
            score={ma.score}
            confidence={ma.confidence}
            coverage={ma.coverage}
            facts={ma.narrativeFacts ?? ma.facts}
            warnings={ma.warnings}
            components={ma.components}
            extra={`${ma.regime} / ${ma.tradability}`}
          />
        ) : null}
        {ea ? (
          <AssessmentBlock
            title="Evidence Assessment"
            score={ea.score}
            confidence={ea.confidence}
            facts={ea.narrativeFacts ?? ea.facts}
            warnings={ea.warnings}
            extra={`band=${ea.band} · cred=${ea.credibility}`}
          />
        ) : null}
        {na && na.eventCount > 0 ? (
          <AssessmentBlock
            title="News Assessment"
            bias={na.bias}
            score={na.score}
            confidence={na.confidence}
            coverage={na.coverage}
            facts={na.narrativeFacts ?? na.facts}
            warnings={na.warnings}
            extra={`${na.eventCount} evento(s) · sent ${na.sentiment.toFixed(2)}`}
          />
        ) : null}

        {pending ? (
          <div className="rounded-md border border-dashed border-border px-3 py-2 text-xs space-y-1">
            <p>
              <span className="font-medium text-foreground">
                Recommendation
              </span>
              {" · "}
              {pending.recommendationId} · <strong>{pending.action}</strong>
              {pending.suggestedPrice != null
                ? ` @ ${pending.suggestedPrice}`
                : ""}
            </p>
            {pending.weightContext ? (
              <div className="rounded border border-border/60 bg-muted/30 px-2 py-1.5 space-y-1">
                <p className="font-medium text-foreground">
                  Fusión Runtime
                  {pending.combinedScore != null
                    ? ` · score ${pending.combinedScore.toFixed(3)}`
                    : ""}
                </p>
                <p className="text-muted-foreground">
                  {pending.weightContext.horizon} ·{" "}
                  {pending.weightContext.regime}
                  {" · "}v{pending.weightContext.ruleVersion}
                </p>
                <p className="text-muted-foreground">
                  TA {(pending.weightContext.weights.ta * 100).toFixed(0)}% ·
                  FUND {(pending.weightContext.weights.fund * 100).toFixed(0)}%
                  · Macro{" "}
                  {(pending.weightContext.weights.macro * 100).toFixed(0)}% ·
                  News {(pending.weightContext.weights.news * 100).toFixed(0)}%
                </p>
                {pending.weightContext.rationale ? (
                  <p className="text-[10px] text-muted-foreground/90">
                    {pending.weightContext.rationale}
                  </p>
                ) : null}
                {pending.weightContext.missingAssessments?.length ? (
                  <p className="text-[10px] text-amber-700 dark:text-amber-400">
                    Faltan:{" "}
                    {pending.weightContext.missingAssessments.join(", ")} (peso
                    redistribuido)
                  </p>
                ) : null}
              </div>
            ) : null}
            {pending.decisionSession?.sessionId ? (
              <p className="text-muted-foreground">
                DecisionSession:{" "}
                <code className="text-[10px]">
                  {pending.decisionSession.sessionId}
                </code>
                {" · "}
                {pending.decisionSession.kind}/{pending.decisionSession.status}
                {" · "}
                <button
                  type="button"
                  className="text-[10px] text-primary underline-offset-2 hover:underline"
                  onClick={() => {
                    const sessionId = pending.decisionSession?.sessionId;
                    if (!sessionId) return;
                    window.dispatchEvent(
                      new CustomEvent("bolsa:open-help", {
                        detail: {
                          section: "value-analysis",
                          sessionId,
                        },
                      }),
                    );
                  }}
                >
                  Abrir Replay
                </button>
              </p>
            ) : null}
            {pending.policyGate?.status ? (
              <p className="text-muted-foreground">
                Policy Gate: {pending.policyGate.status}
                {pending.policyGate.message
                  ? ` — ${pending.policyGate.message}`
                  : ""}
              </p>
            ) : null}
            {(pending.assessments as AssessmentV1[] | undefined)?.length ? (
              <p className="text-muted-foreground">
                Assessments:{" "}
                {(pending.assessments as AssessmentV1[])
                  .map((a) => a.type)
                  .join(", ")}
              </p>
            ) : null}
            {pending.decisionSession?.predictions?.length ? (
              <p className="text-muted-foreground">
                Prediction: {pending.decisionSession.predictions.length} (no
                decide) ·{" "}
                {String(
                  (
                    pending.decisionSession.predictions[0] as {
                      modelId?: string;
                    }
                  )?.modelId ?? "model",
                )}
              </p>
            ) : null}
          </div>
        ) : null}
        {log ? <p className="text-xs text-foreground/80">{log}</p> : null}
      </CardContent>
    </Card>
  );
}
