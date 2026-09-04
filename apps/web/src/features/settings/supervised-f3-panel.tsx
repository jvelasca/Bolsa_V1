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
  brokerAdapterVenueCopy,
  buildConfirmPortfolioScenario,
  buildPortfolioRiskSnapshot,
  computeSignedPortfolioRiskPct,
  evaluateRiskSignature,
  evaluateExitRiskSignature,
  executeCtaLabel,
  executionOutcomeCopy,
  paperOrderStatusCopy,
  resolveSupervisedOpeningQuantity,
} from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  useActiveAccount,
  useActiveAccountSettings,
} from "@/features/accounts/use-active-account";
import { useEffectiveTradingPolicy } from "@/features/accounts/use-effective-trading-policy";
import { useEffectiveBrokerVenue } from "@/features/accounts/use-effective-broker-venue";
import { api } from "@/lib/api";
import { formatNumber0 } from "@/lib/format";
import { cn } from "@/lib/utils";
import { CABIN_TOUCH_TARGET } from "@/features/trading/cabin-visual";
import {
  resolveSupervisedQueueOrigin,
  supervisedQueueOriginLabel,
  type SupervisedProposePayload,
  useSupervisedF3QueueStore,
} from "@/stores/supervised-f3-queue-store";
import {
  demoBookAllowsExecute,
  loadDemoBookPrefs,
  type DemoBookCountryPrefer,
} from "@/features/trading/demo-book-prefs";
import {
  inferHomeCountry,
  optimalScoreFromPayload,
  rankByOptimalThenGeo,
} from "@/features/trading/demo-book-geo-rank";
import { recordSemiConfirmMandate } from "@/features/trading/semi-confirm-mandate";
import {
  protectPersistNote,
  protectStopNotApplied,
} from "@/features/settings/protect-persist-honesty";
import {
  conflictForActive,
  findHmConflicts,
} from "@/features/trading/semi-hm-conflict";
import { F3TicketPreviewBlock } from "@/features/trading/f3-ticket-preview-block";
import { F3TradePlanRiskFirstBlock } from "@/features/trading/f3-trade-plan-risk-first-block";
import { F3ConfirmWhatIfBlock } from "@/features/trading/f3-confirm-what-if-block";
import { F3RiskSignatureBlock } from "@/features/trading/f3-risk-signature-block";
import { F3ProtectStopBlock } from "@/features/trading/f3-protect-stop-block";
import { F3ExitPlanBlock } from "@/features/trading/f3-exit-plan-block";
import { F3ExitRiskSignatureBlock } from "@/features/trading/f3-exit-risk-signature-block";
import {
  f3TicketInputsStale,
  resolveF3PlanBaseline,
  resolveF3SignedPrice,
  resolveF3SignedStop,
} from "@/features/trading/f3-risk-input-baseline";
import { resolveF3TicketPreview } from "@/features/trading/f3-ticket-preview";
import {
  asOperativaExitMeta,
  asOperativaProtectMeta,
} from "@/features/operations/propose-position-exit";
import {
  CHART_SIGNED_STOP_PREFILL_EVENT,
  consumeChartSignedStopPrefill,
} from "@/features/charts/chart-signed-stop-prefill";
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
  const { settings, currency: accountCurrency } = useActiveAccountSettings();
  const { maxSectorExposurePct } = useEffectiveTradingPolicy();
  const [instrumentId, setInstrumentId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [price, setPrice] = useState("");
  const [stopField, setStopField] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [riskOverrideReason, setRiskOverrideReason] = useState("");
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
  const brokerVenue = useEffectiveBrokerVenue();

  const summaryQuery = useQuery({
    queryKey: ["account-summary", effectiveAccountId],
    queryFn: () => api.getAccountSummary(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 15_000,
  });
  const cash = summaryQuery.data?.data?.cash ?? 0;
  const equity = summaryQuery.data?.data?.totalEquity ?? null;
  const summary = summaryQuery.data?.data;

  const portfolioQuery = useQuery({
    queryKey: ["portfolio-confirm-whatif", effectiveAccountId],
    queryFn: () => api.getPortfolio(),
    enabled: Boolean(effectiveAccountId && pending),
    staleTime: 15_000,
  });

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
    setRiskOverrideReason("");
  }, [activeId, quantity, price, stopField]);

  useEffect(() => {
    if (!activeId) return;
    const item = queueItems.find((i) => i.id === activeId);
    if (item) {
      setPending(item.payload);
      setInstrumentId(item.payload.instrumentId);
      const px = item.payload.suggestedPrice ?? item.payload.lastClose ?? null;
      if (px != null) setPrice(String(px));
      const plan = item.payload.tradePlan;
      const planQty = resolveSupervisedOpeningQuantity({
        tradePlan: plan,
        serverSuggestedQuantity: item.payload.suggestedQuantity,
      });
      if (planQty != null) {
        setQuantity(String(planQty));
      } else if (item.payload.suggestedQuantity) {
        setQuantity(String(item.payload.suggestedQuantity));
      } else {
        setQuantity("1");
      }
      const planStop =
        typeof plan?.structuralStop === "number" &&
        Number.isFinite(plan.structuralStop)
          ? plan.structuralStop
          : null;
      const operativa = asOperativaProtectMeta(item.payload);
      const chartStop = consumeChartSignedStopPrefill(
        item.payload.instrumentId,
        {
          tradePlanId: item.payload.decisionId ?? plan?.decisionId ?? null,
          currentStop:
            operativa?.currentStop ??
            (typeof plan?.structuralStop === "number"
              ? plan.structuralStop
              : null),
        },
      );
      const protectStop = operativa?.suggestedStop;
      const stop =
        chartStop ??
        (typeof protectStop === "number" && Number.isFinite(protectStop)
          ? protectStop
          : null) ??
        planStop;
      setStopField(stop != null ? String(stop) : "");
    }
  }, [activeId, queueItems]);

  useEffect(() => {
    function onPrefill(event: Event) {
      const detail = (event as CustomEvent).detail as {
        instrumentId?: string;
        signedStop?: number;
      };
      if (
        !detail?.instrumentId ||
        typeof detail.signedStop !== "number" ||
        !Number.isFinite(detail.signedStop)
      ) {
        return;
      }
      if (instrumentId && detail.instrumentId !== instrumentId) return;
      setStopField(String(detail.signedStop));
    }
    window.addEventListener(CHART_SIGNED_STOP_PREFILL_EVENT, onPrefill);
    return () =>
      window.removeEventListener(CHART_SIGNED_STOP_PREFILL_EVENT, onPrefill);
  }, [instrumentId]);

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
        riskOverrideReason: riskOverrideReason.trim()
          ? riskOverrideReason.trim()
          : undefined,
        signedStop: signedStop ?? undefined,
      });
    },
    onSuccess: (res) => {
      const intent = res.data.intent;
      const trade = res.data.trade;
      const positionPersist = res.data.positionPersist as
        | { status?: string; reason?: string }
        | undefined;
      const executionRecord = res.data.executionRecord as
        | {
            outcome?: "not_executed" | "executed" | "error" | "unknown";
            reason?: string;
          }
        | undefined;
      const paperOrder = res.data.paperOrder as
        | {
            status?:
              | "CREATED"
              | "SUBMITTED"
              | "ACK"
              | "PARTIAL"
              | "FILLED"
              | "REJECTED"
              | "CANCELLED"
              | "EXPIRED"
              | "UNKNOWN";
          }
        | undefined;
      const brokerAdapter = res.data.brokerAdapter as
        | { venue?: "PAPER" | "LIVE"; adapter?: string; fillStatus?: string }
        | undefined;
      const sid = res.data.decisionSession?.sessionId;
      const stopNotApplied = protectStopNotApplied(trade, positionPersist);
      let mandateNote = "";
      if (
        pending &&
        effectiveAccountId &&
        (intent.status === "executed" || intent.status === "authorized") &&
        !stopNotApplied
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
      const outcomeNote =
        executionRecord?.outcome === "unknown"
          ? ` · ${executionOutcomeCopy("unknown")}`
          : executionRecord?.outcome === "error"
            ? ` · ${executionOutcomeCopy("error")}`
            : "";
      const paperNote =
        paperOrder?.status != null
          ? ` · ${paperOrderStatusCopy(paperOrder.status)}`
          : "";
      const adapterNote =
        brokerAdapter?.venue === "PAPER" || brokerAdapter?.venue === "LIVE"
          ? ` · ${brokerAdapterVenueCopy(brokerAdapter.venue)}`
          : "";
      setLog(
        `Intent ${intent.intentId} · ${intent.status}` +
          (trade
            ? ` · trade=${trade.status}${trade.reason ? ` (${trade.reason})` : ""}`
            : "") +
          outcomeNote +
          paperNote +
          adapterNote +
          protectPersistNote(positionPersist) +
          (sid ? ` · session=${sid}` : "") +
          mandateNote,
      );
      if (
        (intent.status === "executed" || intent.status === "authorized") &&
        !stopNotApplied
      ) {
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
        const trade = res.data.trade;
        const positionPersist = res.data.positionPersist as
          | { status?: string; reason?: string }
          | undefined;
        const stopNotApplied = protectStopNotApplied(trade, positionPersist);
        let tag = `${item.symbol ?? item.payload.instrumentId.slice(0, 6)}:${st}`;
        if (stopNotApplied) {
          tag += ":stop_no_aplicado";
        } else if (st === "executed" || st === "authorized") {
          const m = recordSemiConfirmMandate({
            accountId: effectiveAccountId,
            payload: item.payload,
            intentStatus: st,
            trade,
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

  /** U6 — preview ticket (margen/comisión); no ejecuta. */
  const ticketPreview = useMemo(() => {
    if (!pending) return null;
    const pkg = pending.decisionPackage as
      | Record<string, unknown>
      | null
      | undefined;
    const resolvedPrice =
      price.trim() ||
      (pending.suggestedPrice != null ? String(pending.suggestedPrice) : "") ||
      (pending.lastClose != null ? String(pending.lastClose) : "");
    return resolveF3TicketPreview({
      action: pending.action,
      packageAction: pkg?.action,
      quantity,
      price: resolvedPrice,
      notional: pending.notional,
      settings,
      currency: accountCurrency,
      leverage: account?.leverage,
      marginUsed: summary?.marginUsed,
      freeMargin: summary?.freeMargin,
    });
  }, [
    pending,
    quantity,
    price,
    settings,
    accountCurrency,
    account?.leverage,
    summary?.marginUsed,
    summary?.freeMargin,
  ]);

  const planBaseline = useMemo(
    () =>
      resolveF3PlanBaseline({
        tradePlan: pending?.tradePlan,
        suggestedPrice: pending?.suggestedPrice,
        lastClose: pending?.lastClose,
      }),
    [pending?.tradePlan, pending?.suggestedPrice, pending?.lastClose],
  );

  const ticketInputsStale = useMemo(
    () =>
      f3TicketInputsStale({
        quantity,
        priceField: price,
        stopField,
        baseline: planBaseline,
        suggestedPrice: pending?.suggestedPrice,
        lastClose: pending?.lastClose,
      }),
    [
      quantity,
      price,
      stopField,
      planBaseline,
      pending?.suggestedPrice,
      pending?.lastClose,
    ],
  );

  const signedStop = useMemo(
    () =>
      resolveF3SignedStop({
        stopField,
        baselineStop: planBaseline.stop,
      }),
    [stopField, planBaseline.stop],
  );

  const riskSignature = useMemo(() => {
    const qty = Number(quantity);
    const px = resolveF3SignedPrice({
      priceField: price,
      baselinePrice: planBaseline.price,
      suggestedPrice: pending?.suggestedPrice,
      lastClose: pending?.lastClose,
    });
    return evaluateRiskSignature({
      tradePlan: pending?.tradePlan,
      signedQty: Number.isFinite(qty) ? qty : NaN,
      signedPrice: px ?? NaN,
      signedStop,
      overrideReason: riskOverrideReason,
      requireTriggeredPlan:
        pending?.action === "recommend_long" ||
        pending?.action === "recommend_short",
    });
  }, [
    pending?.tradePlan,
    pending?.action,
    quantity,
    price,
    signedStop,
    planBaseline.price,
    pending?.suggestedPrice,
    pending?.lastClose,
    riskOverrideReason,
  ]);

  const displayRiskPct = useMemo(
    () =>
      computeSignedPortfolioRiskPct({
        signedLossAtStop: riskSignature.signedLossAtStop,
        equity,
        planRiskPct: pending?.tradePlan?.riskPct ?? null,
      }),
    [riskSignature.signedLossAtStop, equity, pending?.tradePlan?.riskPct],
  );

  const riskPerShare = useMemo(() => {
    const px = resolveF3SignedPrice({
      priceField: price,
      baselinePrice: planBaseline.price,
      suggestedPrice: pending?.suggestedPrice,
      lastClose: pending?.lastClose,
    });
    if (px == null || signedStop == null) return null;
    const dist = Math.abs(px - signedStop);
    return dist > 0 ? dist : null;
  }, [
    price,
    planBaseline.price,
    pending?.suggestedPrice,
    pending?.lastClose,
    signedStop,
  ]);

  const portfolioRisk = useMemo(() => {
    const positions = portfolioQuery.data?.data?.positions ?? [];
    return buildPortfolioRiskSnapshot({
      positions: positions.map((p) => ({
        avgCost: p.avgCost,
        quantity: p.quantity,
        lastPrice: p.lastPrice,
        marketValue: p.marketValue,
        sector: p.sector ?? null,
        operational: p.operational,
      })),
    });
  }, [portfolioQuery.data]);

  const confirmScenario = useMemo(() => {
    if (!pending) return null;
    const isOpening =
      pending.action === "recommend_long" ||
      pending.action === "recommend_short";
    if (!isOpening) return null;
    const qty = Number(quantity);
    const px = resolveF3SignedPrice({
      priceField: price,
      baselinePrice: planBaseline.price,
      suggestedPrice: pending.suggestedPrice,
      lastClose: pending.lastClose,
    });
    if (!Number.isFinite(qty) || qty <= 0 || px == null || px <= 0) {
      return null;
    }
    const symbol =
      activeItem?.symbol ??
      instrumentsForSelect.find((i) => i.id === pending.instrumentId)?.symbol ??
      pending.instrumentId.slice(0, 6);
    const positions = portfolioQuery.data?.data?.positions ?? [];
    return buildConfirmPortfolioScenario({
      symbol,
      instrumentId: pending.instrumentId,
      signedQty: qty,
      signedPrice: px,
      signedStop,
      tradePlan: pending.tradePlan,
      positions: positions.map((p) => ({
        avgCost: p.avgCost,
        quantity: p.quantity,
        lastPrice: p.lastPrice,
        marketValue: p.marketValue,
        sector: p.sector ?? null,
        operational: p.operational,
      })),
      equity: portfolioQuery.data?.data?.totalEquity ?? equity,
      cash,
      candidateSector:
        instrumentsForSelect.find((i) => i.id === pending.instrumentId)
          ?.sector ?? null,
      maxSectorExposurePct,
      portfolioRiskLimitR: portfolioRisk.portfolioRiskLimitR,
    });
  }, [
    pending,
    quantity,
    price,
    signedStop,
    planBaseline.price,
    activeItem?.symbol,
    instrumentsForSelect,
    portfolioQuery.data,
    equity,
    cash,
    portfolioRisk.portfolioRiskLimitR,
    maxSectorExposurePct,
  ]);

  const executeBlockedByRisk =
    Boolean(pending) &&
    (pending?.action === "recommend_long" ||
      pending?.action === "recommend_short") &&
    !riskSignature.allowed;

  const protectMeta = useMemo(() => asOperativaProtectMeta(pending), [pending]);
  const exitMeta = useMemo(() => asOperativaExitMeta(pending), [pending]);

  const exitRiskSignature = useMemo(() => {
    const qty = Number(quantity);
    return evaluateExitRiskSignature({
      plannedQty: exitMeta?.plannedQty ?? null,
      signedQty: Number.isFinite(qty) ? qty : NaN,
      overrideReason: riskOverrideReason,
    });
  }, [exitMeta?.plannedQty, quantity, riskOverrideReason]);

  const executeBlockedByExitRisk =
    Boolean(exitMeta) &&
    (pending?.action === "reduce" || pending?.action === "exit_hint") &&
    !exitRiskSignature.allowed;

  const executeBlockedByProtect =
    Boolean(protectMeta) &&
    protectMeta!.stopOverrideRequired &&
    !riskOverrideReason.trim();

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
          {cash > 0 ? ` Cash: ${formatNumber0(cash)}.` : ""}
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
                  ? executeCtaLabel(brokerVenue)
                  : "Pasa el libro a SEMI para ejecutar"
              }
              onClick={() => confirmSelected.mutate()}
            >
              {confirmSelected.isPending
                ? "Ejecutando lote…"
                : `${executeCtaLabel(brokerVenue)} (${selectedCount})`}
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
            Siguiente: {executeCtaLabel(brokerVenue)}.
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
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">
              Stop (técnico · editable)
            </span>
            <input
              className="rounded-md border border-border bg-background px-2 py-1.5"
              value={stopField}
              onChange={(e) => setStopField(e.target.value)}
              placeholder="plan"
              data-testid="f3-stop-field"
            />
          </label>
          {advancedOpen ? (
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
          ) : null}
        </div>
        {ticketPreview && pending ? (
          <>
            {exitMeta ? (
              <>
                <F3ExitPlanBlock
                  meta={exitMeta}
                  signedQty={
                    Number.isFinite(Number(quantity)) ? Number(quantity) : null
                  }
                />
                <F3ExitRiskSignatureBlock
                  signature={exitRiskSignature}
                  overrideReason={riskOverrideReason}
                  onOverrideReasonChange={setRiskOverrideReason}
                />
              </>
            ) : (
              <>
                <F3TradePlanRiskFirstBlock
                  ticket={ticketPreview}
                  stop={
                    signedStop ??
                    protectMeta?.suggestedStop ??
                    protectMeta?.currentStop ??
                    null
                  }
                  target1={pending.tradePlan?.target1 ?? null}
                  riskPct={displayRiskPct}
                  signedLossAtStop={riskSignature.signedLossAtStop}
                  signedR={riskSignature.signedR}
                  riskPerShare={riskPerShare}
                  inputsStale={ticketInputsStale}
                />
                {confirmScenario ? (
                  <F3ConfirmWhatIfBlock
                    scenario={confirmScenario}
                    candidateSector={
                      instrumentsForSelect.find(
                        (i) => i.id === pending.instrumentId,
                      )?.sector ?? null
                    }
                  />
                ) : null}
                <F3RiskSignatureBlock
                  signature={riskSignature}
                  currency={accountCurrency}
                  overrideReason={riskOverrideReason}
                  onOverrideReasonChange={setRiskOverrideReason}
                />
              </>
            )}
          </>
        ) : null}
        {/* V2.17 — protect/bootstrap stop must be visible without opening Avanzado (smoke V2.10). */}
        {protectMeta ? (
          <F3ProtectStopBlock
            meta={protectMeta}
            currency={accountCurrency}
            overrideReason={riskOverrideReason}
            onOverrideReasonChange={setRiskOverrideReason}
          />
        ) : null}
        <button
          type="button"
          className="text-[11px] font-medium text-primary underline-offset-2 hover:underline"
          onClick={() => setAdvancedOpen((v) => !v)}
          data-testid="f3-advanced-toggle"
        >
          {advancedOpen ? "Ocultar ajustes avanzados" : "Ajustes avanzados"}
        </button>
        {advancedOpen && ticketPreview ? (
          <F3TicketPreviewBlock ticket={ticketPreview} />
        ) : null}

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
            className={cn(
              CABIN_TOUCH_TARGET,
              "rounded-md border border-border px-3 hover:bg-accent disabled:opacity-50",
            )}
            data-testid="confirm-intent-cta"
            disabled={!pending || confirm.isPending}
            onClick={() => confirm.mutate(false)}
          >
            Confirmar Intent
          </button>
          {brokerVenue === "live" ? (
            <span
              className="inline-flex items-center rounded border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-900 dark:text-sky-100"
              data-testid="confirm-live-venue-badge"
              title="LIVE experimental · submitted ≠ fill · trading not accepted"
            >
              LIVE
            </span>
          ) : null}
          <button
            type="button"
            className={cn(
              CABIN_TOUCH_TARGET,
              "rounded-md border border-primary/40 px-3 text-primary hover:bg-accent disabled:opacity-50",
            )}
            data-testid="confirm-execute-cta"
            disabled={
              !pending ||
              confirm.isPending ||
              (!protectMeta && pending.action === "wait") ||
              !canExecute ||
              executeBlockedByRisk ||
              executeBlockedByExitRisk ||
              executeBlockedByProtect
            }
            title={
              executeBlockedByProtect
                ? "Stop empeora el actual: escribe un motivo de override"
                : executeBlockedByExitRisk
                  ? "Qty de salida supera el plan: escribe un motivo de override"
                  : executeBlockedByRisk
                    ? "Supera el plan: escribe un motivo de override"
                    : protectMeta
                      ? "Persistir stop operativo (≠ orden broker)"
                      : canExecute
                        ? executeCtaLabel(brokerVenue)
                        : "Cambia a SEMI en Libro DEMO"
            }
            onClick={() => confirm.mutate(true)}
          >
            {protectMeta
              ? executeCtaLabel(brokerVenue, "protect")
              : executeCtaLabel(brokerVenue)}
          </button>
        </div>

        {advancedOpen ? (
          <div className="space-y-3" data-testid="f3-advanced-section">
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
          </div>
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
