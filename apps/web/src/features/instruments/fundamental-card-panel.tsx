/**
 * Tarjeta FA (F1–F3) — DTO + copiloto + filings RAG + Composite Monitor.
 * Derived: Altman, Piotroski, Graham, DCF (WACC). Composite: TA+FA+régimen…
 * Filings: disco; Traer SEC; Q&A TF-IDF. No altera Score_FUND.
 *
 * @see docs/engineering/fundamental-intelligence-engine-2026-07-30.md §10–§13
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, RefreshCw, Sparkles } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type {
  CompositeCardDto,
  FundamentalCardDto,
  FundamentalDataConfidence,
  FundamentalExplainResponseV1,
  FundamentalPillarsV1,
  InstrumentFilingAskResponseV1,
  InstrumentFilingMetaV1,
  InstrumentFilingSummarizeResponseV1,
} from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import { AiInfoButton } from "@/features/ai/ai-info-button";
import { formatCompositeLegMethod } from "@/features/instruments/composite-leg-labels";
import { useEnsureInstrumentFundamentals } from "@/features/instruments/use-ensure-instrument-fundamentals";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Props = {
  instrumentId: string;
  /** compact = franja bajo Finalistas en wizard Valor */
  compact?: boolean;
  className?: string;
  /** Backtesting DÍA D — corta FA/Composite a esta fecha (YYYY-MM-DD). */
  asOf?: string | null;
};

const PILLAR_LABELS: Record<keyof FundamentalPillarsV1, string> = {
  value: "Value",
  quality: "Quality",
  growth: "Growth",
  risk: "Risk",
};

function fmtNum(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

function fmtPctRatio(n: number | null | undefined, digits = 1): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

function fmtPe(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toFixed(1);
}

function fmtMcap(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n) || n <= 0) return "—";
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)} T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)} B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(0)} M`;
  return n.toFixed(0);
}

function scoreTone(score100: number | null): string {
  if (score100 == null) return "text-muted-foreground";
  if (score100 >= 70) return "text-emerald-600 dark:text-emerald-400";
  if (score100 >= 45) return "text-amber-600 dark:text-amber-400";
  return "text-destructive";
}

function confidenceClass(c: FundamentalDataConfidence): string {
  if (c === "HIGH")
    return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300";
  if (c === "MEDIUM")
    return "bg-amber-500/15 text-amber-800 dark:text-amber-300";
  return "bg-destructive/15 text-destructive";
}

function confidenceLabel(c: FundamentalDataConfidence): string {
  if (c === "HIGH") return "Alta confianza";
  if (c === "MEDIUM") return "Confianza media";
  return "Baja confianza";
}

/** Pilar [-1,1] → ancho de barra 0–100%. */
function pillarBarPct(v: number): number {
  return Math.max(0, Math.min(100, ((v + 1) / 2) * 100));
}

function freshnessLabel(card: FundamentalCardDto): string {
  const { fetchedAt, staleDays, isStale } = card.metadata;
  if (!fetchedAt) return "Sin fecha de datos";
  if (isStale) {
    return staleDays != null
      ? `Datos hace ${staleDays} d (obsoletos)`
      : "Datos obsoletos";
  }
  if (staleDays == null) return "Datos recientes";
  if (staleDays <= 0) return "Datos de hoy";
  if (staleDays === 1) return "Datos hace 1 día";
  return `Datos hace ${staleDays} días`;
}

function PillarBars({ pillars }: { pillars: FundamentalPillarsV1 }) {
  return (
    <div className="space-y-1.5">
      {(Object.keys(PILLAR_LABELS) as (keyof FundamentalPillarsV1)[]).map(
        (key) => {
          const v = pillars[key];
          return (
            <div
              key={key}
              className="grid grid-cols-[4.5rem_1fr_2.25rem] items-center gap-2"
            >
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                {PILLAR_LABELS[key]}
              </span>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className={cn(
                    "h-full rounded-full transition-[width]",
                    v >= 0.25
                      ? "bg-emerald-500/80"
                      : v >= -0.25
                        ? "bg-amber-500/70"
                        : "bg-destructive/70",
                  )}
                  style={{ width: `${pillarBarPct(v)}%` }}
                />
              </div>
              <span className="text-right text-[11px] tabular-nums text-muted-foreground">
                {fmtNum(v, 2)}
              </span>
            </div>
          );
        },
      )}
    </div>
  );
}

function MetricCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border/50 bg-background/40 px-2 py-1.5">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 text-sm tabular-nums text-foreground">{value}</p>
    </div>
  );
}

/** Sección colapsable — densifica la Tarjeta Valor sin cards de marketing. */
function CardSection({
  title,
  defaultOpen = true,
  children,
  trailing,
}: {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
  trailing?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="space-y-1.5 border-t border-border/50 pt-2 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          className="flex items-center gap-1.5 text-left text-[10px] font-semibold uppercase tracking-wide text-muted-foreground hover:text-foreground"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <span aria-hidden className="tabular-nums text-muted-foreground/80">
            {open ? "▾" : "▸"}
          </span>
          {title}
        </button>
        {trailing}
      </div>
      {open ? children : null}
    </div>
  );
}

function MoreMetrics({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-1.5">
      <button
        type="button"
        className="text-[10px] font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Ocultar más métricas" : "Más métricas (valoración, liquidez…)"}
      </button>
      {open ? children : null}
    </div>
  );
}

export function FundamentalCardPanel({
  instrumentId,
  compact = false,
  className,
  asOf = null,
}: Props) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [copilot, setCopilot] = useState<FundamentalExplainResponseV1 | null>(
    null,
  );
  const [filingSummary, setFilingSummary] =
    useState<InstrumentFilingSummarizeResponseV1 | null>(null);
  const [askFilingId, setAskFilingId] = useState<string | null>(null);
  const [askQuestion, setAskQuestion] = useState("");
  const [filingAsk, setFilingAsk] =
    useState<InstrumentFilingAskResponseV1 | null>(null);
  const asOfNorm = asOf?.trim() || undefined;

  useEffect(() => {
    setCopilot(null);
    setFilingSummary(null);
    setAskFilingId(null);
    setAskQuestion("");
    setFilingAsk(null);
  }, [instrumentId, asOfNorm]);

  const {
    card: ensuredCard,
    status: ensureStatus,
    statusLabel: ensureLabel,
    isRefreshing: ensureRefreshing,
    refreshNow,
    query,
  } = useEnsureInstrumentFundamentals(instrumentId, { asOf: asOfNorm });

  const filingsQuery = useQuery({
    queryKey: ["instrument-filings", instrumentId],
    queryFn: () => api.listInstrumentFilings(instrumentId),
    enabled: Boolean(instrumentId) && !compact,
    staleTime: 30_000,
  });

  const compositeQuery = useQuery({
    queryKey: ["instrument-composite", instrumentId, asOfNorm ?? null],
    queryFn: () =>
      api.getInstrumentComposite(instrumentId, {
        horizon: "swing",
        ...(asOfNorm ? { asOf: asOfNorm } : {}),
      }),
    enabled: Boolean(instrumentId) && !compact && ensureStatus === "ready",
    staleTime: 60_000,
  });

  const explainMutation = useMutation({
    mutationFn: () => api.explainInstrumentFundamentals(instrumentId),
    onSuccess: (res) => {
      setCopilot(res.data);
    },
  });

  const uploadFilingMutation = useMutation({
    mutationFn: (file: File) =>
      api.uploadInstrumentFiling(instrumentId, file, "10-K"),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["instrument-filings", instrumentId],
      });
      setFilingSummary(null);
    },
  });

  const secFetchMutation = useMutation({
    mutationFn: () => api.fetchInstrumentFilingFromSec(instrumentId, "10-K"),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["instrument-filings", instrumentId],
      });
      setFilingSummary(null);
    },
  });

  const summarizeFilingMutation = useMutation({
    mutationFn: (filingId: string) =>
      api.summarizeInstrumentFiling(instrumentId, filingId),
    onSuccess: async (res) => {
      setFilingSummary(res.data);
      await queryClient.invalidateQueries({
        queryKey: ["instrument-filings", instrumentId],
      });
    },
  });

  const deleteFilingMutation = useMutation({
    mutationFn: (filingId: string) =>
      api.deleteInstrumentFiling(instrumentId, filingId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["instrument-filings", instrumentId],
      });
      setFilingSummary(null);
      setFilingAsk(null);
    },
  });

  const askFilingMutation = useMutation({
    mutationFn: ({
      filingId,
      question,
    }: {
      filingId: string;
      question: string;
    }) => api.askInstrumentFiling(instrumentId, filingId, question),
    onSuccess: (res) => {
      setFilingAsk(res.data);
    },
  });

  const card = ensuredCard ?? query.data?.data ?? null;
  const filings: InstrumentFilingMetaV1[] = filingsQuery.data?.data ?? [];
  const composite: CompositeCardDto | null = compositeQuery.data?.data ?? null;
  const askTargetId =
    askFilingId ??
    filings.find((f) => (f.charCount ?? 0) > 0)?.id ??
    filings[0]?.id ??
    null;
  const ensureBusy =
    ensureStatus === "loading" || ensureStatus === "refreshing";

  if (ensureBusy && !card) {
    return (
      <div
        className={cn(
          "rounded-lg border border-border/60 bg-muted/15 px-3 py-2.5 text-xs text-muted-foreground",
          className,
        )}
      >
        <span className="inline-flex items-center gap-1.5">
          <RefreshCw
            className="h-3.5 w-3.5 shrink-0 animate-spin"
            aria-hidden
          />
          {ensureLabel || "Cargando fundamentales…"}
        </span>
      </div>
    );
  }

  if ((ensureStatus === "error" || ensureStatus === "empty") && !card) {
    return (
      <div
        className={cn(
          "space-y-2 rounded-lg border px-3 py-2.5 text-xs",
          ensureStatus === "error"
            ? "border-destructive/40 bg-destructive/5 text-destructive"
            : "border-border/60 bg-muted/15 text-muted-foreground",
          className,
        )}
      >
        <p>{ensureLabel || "Sin datos de análisis fundamental."}</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 gap-1.5 text-[10px]"
          disabled={ensureRefreshing}
          onClick={() => refreshNow()}
        >
          <RefreshCw
            className={cn("h-3 w-3", ensureRefreshing && "animate-spin")}
          />
          Reintentar Yahoo
        </Button>
      </div>
    );
  }

  if (!card) return null;

  const pe = card.facts.forwardPe ?? card.facts.trailingPe;
  const sector = card.facts.sector ?? "—";

  if (compact) {
    return (
      <div
        className={cn(
          "flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border border-border/60 bg-muted/15 px-3 py-2",
          className,
        )}
      >
        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          FA
        </span>
        {ensureBusy ? (
          <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
            <RefreshCw className="h-3 w-3 animate-spin" aria-hidden />
            {ensureStatus === "refreshing" ? "Actualizando…" : "Cargando…"}
          </span>
        ) : (
          <>
            <span
              className={cn(
                "text-lg font-semibold tabular-nums",
                scoreTone(card.scoreDisplay100),
              )}
            >
              {card.scoreDisplay100 != null ? `${card.scoreDisplay100}` : "—"}
              <span className="ml-0.5 text-[10px] font-normal text-muted-foreground">
                /100
              </span>
            </span>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-medium",
                confidenceClass(card.metadata.confidence),
              )}
            >
              {card.metadata.confidence}
            </span>
            {card.distress ? (
              <span className="rounded-full bg-destructive/15 px-2 py-0.5 text-[10px] text-destructive">
                Distress
              </span>
            ) : null}
            <span className="text-[10px] text-muted-foreground">
              {freshnessLabel(card)}
            </span>
            <span className="text-[10px] tabular-nums text-muted-foreground">
              ROE {fmtPctRatio(card.facts.roe)} · D/E{" "}
              {fmtNum(card.facts.debtToEquity)} · Z{" "}
              {fmtNum(card.derived.altmanZ)}
            </span>
          </>
        )}
        {(ensureStatus === "empty" || ensureStatus === "error") && (
          <span
            className={cn(
              "text-[10px]",
              ensureStatus === "error"
                ? "text-destructive"
                : "text-muted-foreground",
            )}
            title={ensureLabel}
          >
            {ensureStatus === "empty" ? "Sin datos FA" : "Error FA"}
          </span>
        )}
      </div>
    );
  }

  return (
    <section
      className={cn(
        "shrink-0 space-y-3 rounded-lg border border-border bg-muted/15 px-3 py-3",
        className,
      )}
      aria-label="Análisis fundamental"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-baseline gap-2">
            <h3 className="text-sm font-medium text-foreground">
              {card.ticker}
              <span className="ml-1.5 font-normal text-muted-foreground">
                · Fundamental
              </span>
            </h3>
            <span className="text-[11px] text-muted-foreground">
              Sector: {sector}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <p
              className={cn(
                "text-2xl font-semibold tabular-nums leading-none",
                scoreTone(card.scoreDisplay100),
              )}
            >
              {card.scoreDisplay100 != null ? card.scoreDisplay100 : "—"}
              <span className="ml-1 text-sm font-normal text-muted-foreground">
                /100
              </span>
            </p>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[11px] font-medium",
                confidenceClass(card.metadata.confidence),
              )}
            >
              {confidenceLabel(card.metadata.confidence)}
            </span>
            {card.distress ? (
              <span className="rounded-full bg-destructive/15 px-2 py-0.5 text-[11px] text-destructive">
                Distress
              </span>
            ) : null}
          </div>
          <p className="text-[11px] text-muted-foreground">
            {ensureBusy ? ensureLabel : freshnessLabel(card)}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <AiInfoButton surface="fa_copilot" />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 gap-1.5"
            disabled={explainMutation.isPending || ensureBusy}
            onClick={() => explainMutation.mutate()}
            title="Explica Score_FUND y facts (Ollama o heurística). No recalcula."
          >
            <Sparkles
              className={cn(
                "h-3.5 w-3.5",
                explainMutation.isPending && "animate-pulse",
              )}
            />
            Copiloto
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 gap-1.5"
            disabled={ensureRefreshing}
            onClick={() => refreshNow()}
            title="Sincroniza el valor (Yahoo) y recarga Score_FUND"
          >
            <RefreshCw
              className={cn("h-3.5 w-3.5", ensureRefreshing && "animate-spin")}
            />
            Refresh
          </Button>
        </div>
      </div>

      {(ensureStatus === "empty" || ensureStatus === "error" || ensureBusy) && (
        <div
          className={cn(
            "rounded-md border px-2.5 py-2 text-[11px] leading-snug",
            ensureStatus === "error"
              ? "border-destructive/40 bg-destructive/5 text-destructive"
              : "border-border/60 bg-background/40 text-muted-foreground",
          )}
        >
          {ensureLabel}
        </div>
      )}

      {explainMutation.isError ? (
        <p className="text-[11px] text-destructive">
          No se pudo generar la explicación.
        </p>
      ) : null}
      {copilot?.payload?.paragraphs?.length ? (
        <div className="space-y-2 rounded-md border border-border/60 bg-background/50 px-2.5 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Copiloto
            <span className="ml-1.5 font-normal normal-case">
              · {copilot.engine}
              {copilot.model ? ` · ${copilot.model}` : ""}
            </span>
          </p>
          {copilot.payload.paragraphs.map((p, i) => (
            <p
              key={`${i}-${p.slice(0, 24)}`}
              className="text-xs leading-relaxed text-foreground/90"
            >
              {p}
            </p>
          ))}
          {copilot.payload.disclaimer ? (
            <p className="text-[10px] italic text-muted-foreground">
              {copilot.payload.disclaimer}
            </p>
          ) : null}
        </div>
      ) : null}

      {card.pillars ? (
        <CardSection title="Pilares" defaultOpen>
          <PillarBars pillars={card.pillars} />
        </CardSection>
      ) : (
        <p className="text-xs text-muted-foreground">
          Sin puntuación (faltan datos fundamentales).
        </p>
      )}

      <CardSection title="Métricas clave" defaultOpen>
        <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCell label="PE" value={fmtPe(pe)} />
          <MetricCell label="ROE" value={fmtPctRatio(card.facts.roe)} />
          <MetricCell label="Altman Z" value={fmtNum(card.derived.altmanZ)} />
          <MetricCell
            label="Piotroski"
            value={
              card.derived.piotroski != null
                ? `${card.derived.piotroski}/9`
                : "—"
            }
          />
          <MetricCell label="ROIC" value={fmtPctRatio(card.derived.roic)} />
          <MetricCell label="Beneish M" value={fmtNum(card.derived.beneishM)} />
        </div>
        <MoreMetrics>
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-5">
            <MetricCell label="D/E" value={fmtNum(card.facts.debtToEquity)} />
            <MetricCell
              label="FCF Yield"
              value={fmtPctRatio(card.derived.fcfYield)}
            />
            <MetricCell
              label="DCF upside"
              value={fmtPctRatio(card.derived.dcfUpside)}
            />
            <MetricCell
              label="WACC/ke"
              value={fmtPctRatio(card.derived.wacc)}
            />
            <MetricCell label="Beta" value={fmtNum(card.derived.beta)} />
            <MetricCell
              label="Graham upside"
              value={fmtPctRatio(card.derived.grahamUpside)}
            />
            <MetricCell label="ADV $" value={fmtMcap(card.derived.advUsd)} />
            <MetricCell label="Mcap" value={fmtMcap(card.facts.marketCap)} />
            <MetricCell
              label="Op. margin"
              value={fmtPctRatio(card.facts.operatingMargin)}
            />
            <MetricCell
              label="Rev. growth"
              value={fmtPctRatio(card.facts.revenueGrowth)}
            />
            <MetricCell
              label="Current"
              value={fmtNum(card.facts.currentRatio)}
            />
          </div>
          {card.derived.dcfScenarios ? (
            <div className="mt-1.5 grid grid-cols-3 gap-1.5">
              <MetricCell
                label="DCF bear"
                value={fmtPctRatio(card.derived.dcfScenarios.bear.upside)}
              />
              <MetricCell
                label="DCF base"
                value={fmtPctRatio(card.derived.dcfScenarios.base.upside)}
              />
              <MetricCell
                label="DCF bull"
                value={fmtPctRatio(card.derived.dcfScenarios.bull.upside)}
              />
            </div>
          ) : null}
          {card.derived.altmanEbitSource === "financial_ebitda_proxy" ? (
            <p className="mt-1 text-[10px] text-amber-700 dark:text-amber-400">
              Altman usa proxy EBITDA (no EBIT de income statement).
            </p>
          ) : null}
          {card.derived.piotroski == null &&
          card.derived.beneishM == null &&
          card.derived.altmanZ == null ? (
            <p className="mt-1 text-[10px] text-muted-foreground">
              Piotroski / Beneish / Altman omitidos si faltan current
              assets/liabilities (típico bancos; null-if-incomplete).
            </p>
          ) : null}
          {card.derived.dcfMethod ? (
            <p className="mt-1 text-[10px] text-muted-foreground">
              DCF {card.derived.dcfMethod ?? "—"}: FCF 5y + Gordon (r=
              {card.derived.waccMethod === "fund_capm_v1"
                ? "CAPM ke"
                : "WACC sector"}
              {card.derived.wacc != null
                ? ` ${fmtPctRatio(card.derived.wacc)}`
                : ""}
              {card.derived.waccMethod ? ` · ${card.derived.waccMethod}` : ""},
              g_term=2.5%); simplificación equity.
              {card.derived.dcfScenarios
                ? ` Escenarios ${card.derived.dcfScenarios.method}: g±3pp · r±1pp.`
                : ""}
            </p>
          ) : null}
          {card.derived.waccMethod === "fund_capm_v1" &&
          card.derived.capmRf != null &&
          card.derived.capmErp != null &&
          card.derived.beta != null ? (
            <p className="mt-1 text-[10px] text-muted-foreground">
              CAPM: ke = rf {fmtPctRatio(card.derived.capmRf)} + β{" "}
              {fmtNum(card.derived.beta)} × ERP{" "}
              {fmtPctRatio(card.derived.capmErp)}
              {card.derived.wacc != null
                ? ` → ${fmtPctRatio(card.derived.wacc)}`
                : ""}
              . rf/ERP versionados ({card.derived.waccMethod}); no son tasas
              live.
            </p>
          ) : null}
          {card.derived.grahamMethod && card.derived.grahamNumber != null ? (
            <p className="mt-1 text-[10px] text-muted-foreground">
              Graham {card.derived.grahamMethod}:{" "}
              {fmtNum(card.derived.grahamNumber)} / acción.
            </p>
          ) : null}
        </MoreMetrics>
      </CardSection>

      {card.warnings.length > 0 ? (
        <ul className="space-y-0.5 text-[11px] text-muted-foreground">
          {card.warnings.slice(0, 4).map((w) => (
            <li key={w}>· {w}</li>
          ))}
        </ul>
      ) : null}

      <CardSection
        title="Composite (F3)"
        defaultOpen
        trailing={
          composite ? (
            <p className="text-xs tabular-nums">
              <span
                className={cn(
                  "font-semibold",
                  scoreTone(composite.scoreDisplay100),
                )}
              >
                {composite.scoreDisplay100 ?? "—"}
              </span>
              <span className="text-muted-foreground">
                /100 · {composite.metadata.confidence}
                {composite.metadata.paperDUnlocked ? " · Paper D listo" : ""}
              </span>
            </p>
          ) : null
        }
      >
        {compositeQuery.isLoading ? (
          <p className="text-[11px] text-muted-foreground">
            Calculando Composite…
          </p>
        ) : compositeQuery.isError ? (
          <p className="text-[11px] text-destructive">
            No se pudo cargar el Composite.
          </p>
        ) : composite ? (
          <>
            <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
              {composite.legs.map((leg) => {
                const methodLabel = formatCompositeLegMethod(leg.method);
                return (
                  <div
                    key={leg.key}
                    className="rounded-md border border-border/50 bg-background/40 px-2 py-1.5"
                  >
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {leg.label}
                    </p>
                    <p className="mt-0.5 text-sm tabular-nums text-foreground">
                      {leg.score != null ? fmtNum(leg.score, 2) : "—"}
                      <span className="ml-1 text-[10px] text-muted-foreground">
                        · {leg.status}
                        {leg.weight > 0 ? ` · w${fmtNum(leg.weight, 2)}` : ""}
                        {methodLabel ? ` · ${methodLabel}` : ""}
                      </span>
                    </p>
                  </div>
                );
              })}
            </div>
            <p className="text-[10px] text-muted-foreground">
              {composite.metadata.scoreVersion} · {composite.weights.rationale}
              {composite.metadata.technicalMethod
                ? ` · TA ${composite.metadata.technicalMethod}`
                : " · sin TA"}
            </p>
          </>
        ) : null}
      </CardSection>

      <CardSection
        title="Docs USA (F2b)"
        defaultOpen={false}
        trailing={<AiInfoButton surface="fa_filings" />}
      >
        <div className="flex flex-wrap gap-1.5">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,application/pdf,text/plain"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) uploadFilingMutation.mutate(file);
            }}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 gap-1.5"
            disabled={uploadFilingMutation.isPending}
            onClick={() => fileInputRef.current?.click()}
            title="Sube PDF o TXT (10-K). No altera Score_FUND."
          >
            <FileText
              className={cn(
                "h-3.5 w-3.5",
                uploadFilingMutation.isPending && "animate-pulse",
              )}
            />
            Subir 10-K
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 gap-1.5"
            disabled={secFetchMutation.isPending}
            onClick={() => secFetchMutation.mutate()}
            title="Descarga el último 10-K desde SEC EDGAR (solo tickers US). Sin RAG."
          >
            <FileText
              className={cn(
                "h-3.5 w-3.5",
                secFetchMutation.isPending && "animate-pulse",
              )}
            />
            Traer SEC
          </Button>
        </div>
        <p className="text-[10px] text-muted-foreground">
          Almacén local · SEC EDGAR (US) · resumen / Q&A TF-IDF · no entra en
          Score_FUND. Para SEC: env BOLSA_SEC_USER_AGENT (contacto real).
        </p>
        {uploadFilingMutation.isError ? (
          <p className="text-[11px] text-destructive">
            No se pudo subir el documento.
          </p>
        ) : null}
        {secFetchMutation.isError ? (
          <p className="text-[11px] text-destructive">
            {(secFetchMutation.error as Error)?.message ||
              "No se pudo traer el filing desde SEC (¿ticker US? ¿User-Agent?)."}
          </p>
        ) : null}
        {filings.length === 0 ? (
          <p className="text-[11px] text-muted-foreground">
            Sin documentos adjuntos.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {filings.slice(0, 5).map((f) => (
              <li
                key={f.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/50 bg-background/40 px-2 py-1.5 text-[11px]"
              >
                <span className="min-w-0 truncate">
                  <span className="font-medium">{f.kind}</span>
                  <span className="text-muted-foreground">
                    {" "}
                    · {f.source === "sec_edgar" ? "SEC" : "manual"} ·{" "}
                    {f.originalName}
                  </span>
                  <span className="text-muted-foreground">
                    {" "}
                    · {f.extractStatus}
                    {f.filingDate ? ` · ${f.filingDate}` : ""}
                    {f.charCount ? ` · ${f.charCount} chars` : ""}
                  </span>
                </span>
                <span className="flex shrink-0 gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2"
                    disabled={
                      summarizeFilingMutation.isPending || f.charCount === 0
                    }
                    onClick={() => summarizeFilingMutation.mutate(f.id)}
                  >
                    Resumir
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className={cn(
                      "h-7 px-2",
                      askTargetId === f.id && "bg-muted text-foreground",
                    )}
                    disabled={(f.charCount ?? 0) === 0}
                    onClick={() => setAskFilingId(f.id)}
                    title="Usar este filing para Preguntar"
                  >
                    Preguntar
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-destructive"
                    disabled={deleteFilingMutation.isPending}
                    onClick={() => deleteFilingMutation.mutate(f.id)}
                  >
                    Quitar
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        )}
        {filingSummary?.payload?.paragraphs?.length ? (
          <div className="space-y-2 rounded-md border border-border/60 bg-background/50 px-2.5 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Resumen filing
              <span className="ml-1.5 font-normal normal-case">
                · {filingSummary.engine}
                {filingSummary.model ? ` · ${filingSummary.model}` : ""}
              </span>
            </p>
            {filingSummary.payload.paragraphs.map((p, i) => (
              <p
                key={`${i}-${p.slice(0, 24)}`}
                className="text-xs leading-relaxed text-foreground/90"
              >
                {p}
              </p>
            ))}
            {filingSummary.payload.disclaimer ? (
              <p className="text-[10px] italic text-muted-foreground">
                {filingSummary.payload.disclaimer}
              </p>
            ) : null}
          </div>
        ) : null}
        {filings.some((f) => (f.charCount ?? 0) > 0) ? (
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-1.5">
              <input
                type="text"
                value={askQuestion}
                onChange={(e) => setAskQuestion(e.target.value)}
                placeholder="Pregunta al filing (riesgos, deuda, MD&A…)"
                className="h-8 min-w-[12rem] flex-1 rounded-md border border-border/60 bg-background px-2 text-xs"
                maxLength={800}
                disabled={!askTargetId || askFilingMutation.isPending}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && askTargetId && askQuestion.trim()) {
                    e.preventDefault();
                    askFilingMutation.mutate({
                      filingId: askTargetId,
                      question: askQuestion.trim(),
                    });
                  }
                }}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8"
                disabled={
                  !askTargetId ||
                  !askQuestion.trim() ||
                  askFilingMutation.isPending
                }
                onClick={() => {
                  if (!askTargetId || !askQuestion.trim()) return;
                  askFilingMutation.mutate({
                    filingId: askTargetId,
                    question: askQuestion.trim(),
                  });
                }}
                title="Retrieval TF-IDF local + LLM/heurística"
              >
                {askFilingMutation.isPending ? "Buscando…" : "Preguntar"}
              </Button>
            </div>
            {askFilingMutation.isError ? (
              <p className="text-[11px] text-destructive">
                {(askFilingMutation.error as Error)?.message ||
                  "No se pudo responder sobre el filing."}
              </p>
            ) : null}
            {filingAsk?.payload?.answer ? (
              <div className="space-y-1.5 rounded-md border border-border/60 bg-background/50 px-2.5 py-2">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Q&A filing
                  <span className="ml-1.5 font-normal normal-case">
                    · {filingAsk.engine}
                    {filingAsk.model ? ` · ${filingAsk.model}` : ""}
                    {filingAsk.hits?.length
                      ? ` · ${filingAsk.hits.length} pasajes`
                      : ""}
                  </span>
                </p>
                <p className="text-[10px] text-muted-foreground">
                  «{filingAsk.question}»
                </p>
                <p className="whitespace-pre-wrap text-xs leading-relaxed text-foreground/90">
                  {filingAsk.payload.answer}
                </p>
                {filingAsk.payload.disclaimer ? (
                  <p className="text-[10px] italic text-muted-foreground">
                    {filingAsk.payload.disclaimer}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
      </CardSection>

      <p className="text-[10px] text-muted-foreground">
        {card.metadata.provider} · {card.metadata.sourceVersion ?? "—"} ·{" "}
        {card.metadata.scoreVersion}
        {card.scoreFund != null ? (
          <span className="tabular-nums">
            {" "}
            · Score_FUND {card.scoreFund.toFixed(2)}
          </span>
        ) : null}
      </p>
    </section>
  );
}
