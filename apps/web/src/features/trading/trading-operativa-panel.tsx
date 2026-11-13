/**
 * Panel DECISIÓN (Mercado) — CONTEXTO → ESTADO → ACCIÓN + ¿Por qué? colapsado.
 * Ids de código `operativa*` se conservan; chrome de producto = DECISIÓN (ADR-042).
 *
 * Manual/SEMI/AUTO = cuenta entera → barra de estado / Cuentas (no aquí).
 * Supervisión Lab lista Estudio = banner Estudio.
 *
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md
 * @see docs/adr/042-operating-excellence.md
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { absentDataLabel } from "@/components/absent-data";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { instrumentTopBacktestsHref } from "@/features/backtests/instrument-strategy-top-panel";
import {
  finalistsStabilityWarnTitle,
  formatFinalistsStabilityBadge,
  readLabEvidenceFromCoachFacts,
} from "@/features/backtests/finalists-stability-summary";
import { readRecommendationReasons } from "@/features/backtests/instrument-strategy-top-panel";
import { OperativaAnalisisDiario } from "@/features/trading/operativa-analisis-diario";
import { MarketStructureReadout } from "@/features/market-structure/market-structure-readout";
import { useInstrumentOperationalContext } from "@/features/trading/use-instrument-operational-context";
import { formatFueraUniversoOperativaCopy } from "@/features/confirm/daily-nav";
import {
  diaDVerifyHref,
  VERIFY_DIA_D_CTA,
} from "@/features/platform/product-universe";
import {
  STRATEGY_ADOPTION_LABELS,
  getAdoptionState,
  type StrategyAdoptionState,
} from "@/features/platform/strategy-adoption";
import { MandateTimelinePanel } from "@/features/trading/mandate-timeline-panel";
import {
  demoBookAllowsEnqueueConfirm,
  demoBookRequiresEstudioMembership,
} from "@/features/trading/demo-book-prefs";
import { useDemoBookPrefs } from "@/features/trading/use-demo-book-prefs";
import { MesaTipButton } from "@/features/help/mesa-tip-button";
import { proposeInstrumentSupervised } from "@/features/trading/propose-instrument-supervised";
import { OperativaCockpitCard } from "@/features/trading/operativa-cockpit-card";
import {
  useAddToEstudioAction,
  useRefreshStudyAction,
} from "@/features/trading/use-operativa-study-actions";
import { useMesaEntriesBlocked } from "@/features/mesa/use-mesa-entries-blocked";
import { TradingOperativaSection } from "@/features/trading/trading-operativa-section";
import { OperativaRecomendacionPrincipal } from "@/features/trading/operativa-recomendacion-principal";
import { resolveOperativaActionHint } from "@/features/trading/operativa-action-hint";
import { useEstudioMembershipStore } from "@/stores/estudio-membership-store";
import { OperativaPulseBlock } from "@/features/trading/operativa-pulse";
import { OperativaDictamenBlock } from "@/features/trading/operativa-dictamen";
import { OperativaOutcomesBlock } from "@/features/trading/operativa-outcomes";
import { OperativaAutoPanel } from "@/features/trading/operativa-auto-panel";
import { useInstrumentDailyOpinions } from "@/features/trading/use-instrument-daily-opinions";
import type { OperativaDensity } from "@/features/trading/operativa-density";
import {
  rankIndiceOperativo,
  resolveIndiceOperativo,
  type OperativaScoreRow,
} from "@/features/trading/operativa-index";
import { useInstrumentsHubScores } from "@/features/instruments/use-instruments-hub-scores";
import { getDiaDExperimentTop1 } from "@/features/backtests/dia-d-experiment-top";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";
import {
  effectiveDiaD,
  isDiaDInPast,
  todayIsoDate,
} from "@/features/backtests/backtest-period";
import { loadBacktestRunContext } from "@/features/backtests/backtest-run-context";
import { useDiaDTradingSessionStore } from "@/stores/dia-d-trading-session-store";
import { useAlertsStore } from "@/stores/alerts-store";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";
import { DecisionPackageChipsBar } from "@/features/trading/decision-package-chips-bar";
import { useDecisionPackageChips } from "@/features/trading/use-decision-package-chips";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";
import { cn } from "@/lib/utils";
import {
  useEffect,
  useMemo,
  useSyncExternalStore,
} from "react";
import {
  buildInstrumentDailyAnalysis,
  classifyAsesorCarteraState,
  JOURNAL_STUDY_STRENGTH_BAND_LABELS,
} from "@bolsa/shared";
import {
  getMandateStoreSnapshot,
  subscribeMandateStore,
  summarizeMandateChurn,
} from "@/features/platform/operating-mandate";
import { ensureMandateHydrated } from "@/features/platform/operating-mandate-sync";

function formatAdoption(state: StrategyAdoptionState): string {
  return STRATEGY_ADOPTION_LABELS[state];
}

export function TradingOperativaPanel({
  className,
  maximized = false,
  surface = "dock",
}: {
  className?: string;
  /** Área completa (maximizada o ventana estrecha): el contenido respira y se reparte en columnas. */
  maximized?: boolean;
  /**
   * S4 — superficie de lectura. `maximized` (escritorio maximizado) es la única
   * que antepone la recomendación principal; `dock` y `narrow` conservan la
   * composición anterior.
   */
  surface?: "dock" | "maximized" | "narrow";
}) {
  const navigate = useNavigate();
  const enterSession = useDiaDTradingSessionStore((s) => s.enterSession);
  const charts = useWorkspaceStore((s) => s.workspace.charts);
  const activeChartId = useWorkspaceStore((s) => s.workspace.activeChartId);
  const active = charts.find((c) => c.id === activeChartId) ?? charts[0];
  const instrumentId = active?.instrumentId ?? null;
  const symbol = active?.label ?? absentDataLabel();
  const timeframe = (active?.timeframe as string) || "1d";
  const { effectiveAccountId } = useActiveAccount();
  const accountScope = useActiveAccountQueryKey();
  const { entriesBlocked } = useMesaEntriesBlocked();
  const bookPrefs = useDemoBookPrefs();
  const pushToast = useAlertsStore((s) => s.pushToast);
  const enqueueSupervised = useSupervisedF3QueueStore((s) => s.enqueue);
  const setActiveSupervised = useSupervisedF3QueueStore((s) => s.setActive);
  const mandateRev = useSyncExternalStore(
    subscribeMandateStore,
    getMandateStoreSnapshot,
    () => 0,
  );
  const diaD = loadBacktestRunContext().diaD;
  const canVerify = isDiaDInPast(diaD);

  const studyEntries = useEstudioMembershipStore((s) => s.members);
  const studyContains = useEstudioMembershipStore((s) => s.contains);
  const upsertStudyMembers = useEstudioMembershipStore((s) => s.upsertMembers);
  const studyIds = useMemo(
    () => studyEntries.map((entry) => entry.instrumentId),
    [studyEntries],
  );
  const inEstudio = instrumentId ? studyContains(instrumentId) : false;
  const requiresEstudio = demoBookRequiresEstudioMembership(bookPrefs.mode);
  const canEnqueueConfirm = demoBookAllowsEnqueueConfirm(bookPrefs.mode);

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", accountScope],
    queryFn: () => api.getPortfolio(),
    staleTime: 15_000,
  });
  const instrumentsCatalogQuery = useQuery({
    queryKey: ["instruments"],
    queryFn: api.getInstruments,
    enabled: false,
    staleTime: 60_000,
  });
  const markPrice = useMemo(() => {
    if (!instrumentId) return null;
    const fromCatalog = instrumentsCatalogQuery.data?.data.find(
      (item) => item.id === instrumentId,
    )?.meta.lastClose;
    if (typeof fromCatalog === "number" && Number.isFinite(fromCatalog)) {
      return fromCatalog;
    }
    const fromPosition = (portfolioQuery.data?.data.positions ?? []).find(
      (row) => row.instrumentId === instrumentId,
    )?.lastPrice;
    return typeof fromPosition === "number" && Number.isFinite(fromPosition)
      ? fromPosition
      : null;
  }, [instrumentId, instrumentsCatalogQuery.data, portfolioQuery.data]);
  // C-1 — tri-estado: `?? []` convertía «cartera cargando/fallida» en «sin posición».
  // La postura del dictamen ya NO se envía desde el cliente: la mide el servidor.

  const { faByInstrument, taByInstrument, scoresLoading } =
    useInstrumentsHubScores(studyIds);

  const scoreRows: OperativaScoreRow[] = useMemo(
    () =>
      studyIds.map((id) => {
        const ta = taByInstrument.get(id);
        const fa = faByInstrument.get(id);
        return {
          instrumentId: id,
          io: resolveIndiceOperativo({
            indiceOperativo: ta?.indiceOperativo,
            compositeDisplay100: ta?.compositeDisplay100,
            distress: fa?.distress,
          }),
          ta: ta?.technicalDisplay100 ?? null,
          fa: fa?.scoreDisplay100 ?? null,
          distress: fa?.distress,
        };
      }),
    [studyIds, taByInstrument, faByInstrument],
  );

  const rankResult = useMemo(
    () => (instrumentId ? rankIndiceOperativo(scoreRows, instrumentId) : null),
    [scoreRows, instrumentId],
  );

  const opinionsQuery = useInstrumentDailyOpinions(
    instrumentId ? [instrumentId] : [],
    {
      enabled: Boolean(instrumentId),
      accountId: effectiveAccountId,
    },
  );
  const activeOpinion = opinionsQuery.data?.[0];
  const packageChips = useDecisionPackageChips({
    instrumentId,
    opinionGateStatus: activeOpinion?.gateStatus ?? null,
  });

  useEffect(() => {
    if (!effectiveAccountId) return;
    void ensureMandateHydrated(effectiveAccountId);
  }, [effectiveAccountId]);

  const churn = useMemo(
    () =>
      summarizeMandateChurn({
        instrumentId,
        accountId: effectiveAccountId,
      }),
    // mandateRev es señal de refresco (recalcular tenures/churn al escribir mandato)
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [instrumentId, effectiveAccountId, mandateRev],
  );

  const topQuery = useQuery({
    queryKey: ["instrument-strategy-top", instrumentId, timeframe],
    queryFn: () => api.getInstrumentStrategyTop(instrumentId!, timeframe),
    enabled: Boolean(instrumentId),
    staleTime: 60_000,
    retry: false,
  });

  const top = topQuery.data?.data ?? null;
  const slot1 = top?.slots?.slice().sort((a, b) => a.rank - b.rank)[0] ?? null;

  // ── Análisis diario (banda sobre la tarjeta de decisión) ────────────────
  // Fuente única: contexto operativo (fase/plan/trailing) + definición de la
  // estrategia #1 (indicadores optimizados) + coachFacts (razón/estabilidad).
  const queryClient = useQueryClient();
  const operationalContext = useInstrumentOperationalContext(instrumentId);
  const topStrategyDefinitionId = slot1?.strategyDefinitionId ?? null;
  const definitionQuery = useQuery({
    queryKey: ["strategy", topStrategyDefinitionId],
    queryFn: () => api.getStrategy(topStrategyDefinitionId!),
    enabled: Boolean(topStrategyDefinitionId),
    staleTime: 60_000,
  });
  const strategyDefinition = definitionQuery.data?.data?.definition ?? null;
  const recommendationReasons = useMemo(
    () =>
      readRecommendationReasons(
        top?.coachFacts as Record<string, unknown> | null | undefined,
        slot1?.rank ?? 1,
      ),
    [top?.coachFacts, slot1?.rank],
  );

  // Evidencia de estabilidad del Lab (misma fuente que ¿Por qué? y TOP).
  const labEvidence = readLabEvidenceFromCoachFacts(
    top?.coachFacts as Record<string, unknown> | null | undefined,
  );
  const stabilityBadge = formatFinalistsStabilityBadge(labEvidence);
  const stabilityWarn = finalistsStabilityWarnTitle(labEvidence);

  const handleRefreshStudyAction = useRefreshStudyAction({
    instrumentId,
    symbol,
    pushToast,
    invalidate: () =>
      queryClient.invalidateQueries({ queryKey: ["decision-studies"] }),
    refetch: () => topQuery.refetch(),
  });
  const refreshingStudy = handleRefreshStudyAction.refreshPending;
  const handleRefreshStudy = handleRefreshStudyAction.refreshStudy;

  const handleAddToEstudioAction = useAddToEstudioAction({
    instrumentId,
    symbol,
    pushToast,
    upsertMembers: upsertStudyMembers,
  });
  const addToEstudioPending = handleAddToEstudioAction.addToEstudioPending;
  const handleAddToEstudio = handleAddToEstudioAction.addToEstudio;

  const dailyAnalysis = useMemo(
    () =>
      buildInstrumentDailyAnalysis({
        instrumentId: instrumentId ?? "",
        inEstudio: operationalContext.inEstudio,
        study: operationalContext.study,
        phase: operationalContext.phase,
        showsPlanLevels: operationalContext.showsPlanLevels,
        plan: operationalContext.plan,
        trailing: operationalContext.trailing,
        markPrice,
        slot: slot1,
        definition: strategyDefinition,
        reasons: recommendationReasons,
        evidenceLevel: top?.evidenceLevel ?? null,
        stabilityLabel: stabilityBadge,
      }),
    [
      instrumentId,
      operationalContext.inEstudio,
      operationalContext.study,
      operationalContext.phase,
      operationalContext.showsPlanLevels,
      operationalContext.plan,
      operationalContext.trailing,
      markPrice,
      slot1,
      strategyDefinition,
      recommendationReasons,
      top?.evidenceLevel,
      stabilityBadge,
    ],
  );

  // S2 — niveles del plan que ya manda el contexto operativo. Solo se usan para
  // DECLARAR coincidencias en el readout: el nivel operativo conserva la autoridad.
  const planLevelPrices = useMemo(() => {
    const plan = operationalContext.plan;
    if (!plan || !operationalContext.showsPlanLevels) {
      return [] as { price: number; title: string }[];
    }
    const rows: { price: number; title: string }[] = [];
    if (typeof plan.entry === "number") rows.push({ price: plan.entry, title: "Entrada" });
    if (typeof plan.stopVigente === "number") {
      rows.push({ price: plan.stopVigente, title: "Stop" });
    }
    if (typeof plan.target1 === "number") rows.push({ price: plan.target1, title: "T1" });
    if (typeof plan.target2 === "number") rows.push({ price: plan.target2, title: "T2" });
    return rows;
  }, [operationalContext.plan, operationalContext.showsPlanLevels]);

  const structureStudyStrength = useMemo(() => {
    const study = operationalContext.study;
    if (!study) return null;
    const band = study.strengthBand
      ? JOURNAL_STUDY_STRENGTH_BAND_LABELS[study.strengthBand]
      : null;
    return {
      value: study.strength,
      max: 10 as const,
      band,
    };
  }, [operationalContext.study]);

  const proposeMutation = useMutation({
    mutationFn: async () => {
      if (!instrumentId) throw new Error("Sin instrumento");
      if (!effectiveAccountId) throw new Error("Sin cuenta DEMO activa");
      const topSlot =
        topQuery.data?.data?.slots
          ?.slice()
          .sort((a, b) => a.rank - b.rank)[0] ?? null;
      return proposeInstrumentSupervised({
        instrumentId,
        symbol,
        accountId: effectiveAccountId,
        source: "operativa",
        strategyDefinitionId: topSlot?.strategyDefinitionId ?? null,
        strategyLabel: topSlot?.label ?? symbol,
        entriesBlocked,
      });
    },
    onSuccess: (payload) => {
      const id = enqueueSupervised(payload, {
        symbol: payload.symbol ?? symbol,
        origin: "operativa",
      });
      setActiveSupervised(id);
      pushToast(
        `DECISIÓN · ${payload.symbol ?? symbol}: ${payload.action} → Confirm`,
      );
      openConfirmDrawer();
    },
    onError: (e: Error) => {
      pushToast(`DECISIÓN · ${symbol}: ${e.message}`);
    },
  });

  const adoption = instrumentId
    ? getAdoptionState(instrumentId, effectiveAccountId)
    : "none";

  // ── S4 · Estado de cartera (clasificador S3) y vía de actuación ───────────
  // El clasificador solo mira dictamen + cartera medida + causa de no_trade:
  // tendencia, fuerza y niveles no pueden promover la fila a «comprar».
  const hasOpenPosition = useMemo(() => {
    const position = operationalContext.position;
    return Boolean(position && Math.abs(Number(position.quantity ?? 0)) > 0);
  }, [operationalContext.position]);

  const carteraState = useMemo(
    () =>
      classifyAsesorCarteraState({
        opinion: activeOpinion ?? null,
        position: {
          measured: operationalContext.positionMeasured,
          hasOpenPosition,
        },
      }),
    [activeOpinion, operationalContext.positionMeasured, hasOpenPosition],
  );

  const actionHint = useMemo(
    () =>
      resolveOperativaActionHint({
        carteraStateId: carteraState.id,
        hasOpenPosition,
        hasAccount: Boolean(effectiveAccountId),
        positionMeasured: operationalContext.positionMeasured,
        studiesMeasured: operationalContext.studiesMeasured,
        canEnqueueConfirm,
        entriesBlocked,
        requiresEstudio,
        inEstudio,
      }),
    [
      carteraState.id,
      hasOpenPosition,
      effectiveAccountId,
      operationalContext.positionMeasured,
      operationalContext.studiesMeasured,
      canEnqueueConfirm,
      entriesBlocked,
      requiresEstudio,
      inEstudio,
    ],
  );

  if (!instrumentId) {
    return (
      <div
        className={cn(
          "flex h-full min-h-0 flex-col gap-2 overflow-y-auto p-2 text-[11px] text-muted-foreground",
          className,
        )}
        data-testid="trading-operativa-panel-empty"
        data-maximized={maximized ? "true" : "false"}
      >
        <p className="font-medium text-foreground">Sin valor activo</p>
        <p>
          Abre un instrumento en el gráfico para ver recomendación, info y
          configuración.
        </p>
      </div>
    );
  }

  function startVerify() {
    if (!instrumentId) return;
    const asOf = effectiveDiaD(diaD);
    const exp1 = isDiaDInPast(diaD)
      ? getDiaDExperimentTop1(instrumentId, timeframe, asOf)
      : null;
    const strategyDefinitionId =
      exp1?.strategyDefinitionId ?? slot1?.strategyDefinitionId ?? null;
    if (!strategyDefinitionId) return;
    enterSession({
      instrumentId,
      symbol,
      strategyDefinitionId,
      strategyLabel: exp1?.label ?? slot1?.label ?? "Finalista",
      rank: exp1?.rank ?? slot1?.rank ?? 1,
      diaD: asOf,
      endDate: todayIsoDate(),
      mode: "auto",
      accountId: effectiveAccountId ?? null,
    });
    navigate(diaDVerifyHref(instrumentId));
  }

  const labHref = instrumentTopBacktestsHref(instrumentId, timeframe);
  const evidenciaSummary = (
    <span className="text-[10px] tabular-nums text-muted-foreground">
      {rankResult?.io != null ? `IO ${Math.round(rankResult.io)}` : "Sin pulso"}
    </span>
  );

  // ── S4 · Bloques compartidos por las tres superficies ─────────────────────
  // Se construyen una sola vez para que el dock, la ventana estrecha y la
  // maximizada declaren exactamente el mismo contenido. Lo único que cambia es
  // el orden y dónde vive la recomendación principal.

  const unmeasuredBanner =
    !operationalContext.loading &&
    (!operationalContext.positionMeasured ||
      !operationalContext.studiesMeasured) ? (
      <p
        className="rounded-md border border-amber-700/40 bg-amber-500/10 px-2 py-1 text-[10px] leading-snug text-foreground"
        data-testid="operativa-panel-unmeasured"
      >
        {!operationalContext.positionMeasured
          ? operationalContext.portfolioError
            ? "Cartera no medida (la lectura falló): no se habilita proponer."
            : "Cartera sin medir: esperando posiciones antes de proponer."
          : operationalContext.studiesError
            ? "Estudios no medidos (la lectura falló): no se habilita proponer."
            : "Estudios sin medir: esperando planes antes de proponer."}
      </p>
    ) : null;

  const cockpitCard = (
    <OperativaCockpitCard
      instrumentId={instrumentId}
      symbol={symbol}
      markPrice={markPrice}
      opinion={activeOpinion ?? null}
      opinionLoading={opinionsQuery.isLoading}
      canPropose={
        Boolean(effectiveAccountId) &&
        operationalContext.positionMeasured &&
        operationalContext.studiesMeasured &&
        canEnqueueConfirm &&
        !entriesBlocked &&
        !(requiresEstudio && !inEstudio)
      }
      proposePending={proposeMutation.isPending}
      onPropose={() => proposeMutation.mutate()}
      addToEstudioPending={addToEstudioPending}
      onAddToEstudio={handleAddToEstudio}
    />
  );

  const fueraEstudioBanner =
    requiresEstudio && !inEstudio ? (
      <div
        className="shrink-0 rounded-md border border-amber-600/40 bg-amber-500/10 px-2 py-1.5 text-[10px]"
        data-testid="operativa-fuera-estudio"
      >
        <p className="font-medium text-amber-950 dark:text-amber-50">
          {formatFueraUniversoOperativaCopy(bookPrefs.mode.toUpperCase())}
        </p>
        <p className="mt-0.5 text-amber-900/80 dark:text-amber-100/80">
          El alta se firma en ACCIÓN, arriba.
        </p>
      </div>
    ) : null;

  const analisisDiarioBlock = (
    part: "all" | "tecnico" | "seguimiento" = "all",
    density: OperativaDensity = "compact",
  ) => (
    <OperativaAnalisisDiario
      analysis={dailyAnalysis}
      symbol={symbol}
      timeframe={timeframe}
      labHref={labHref}
      loading={operationalContext.loading}
      error={operationalContext.studiesError}
      refreshPending={refreshingStudy}
      onRefreshStudy={handleRefreshStudy}
      part={part}
      density={density}
    />
  );

  const estructuraBlock = (
    density: OperativaDensity = "compact",
    showHeading = true,
  ) => (
    <MarketStructureReadout
      instrumentId={instrumentId}
      timeframe={timeframe}
      studyStrength={structureStudyStrength}
      planLevels={planLevelPrices}
      density={density}
      showHeading={showHeading}
    />
  );

  const labTopCard = topQuery.isLoading ? (
    <p className="text-muted-foreground">Cargando TOP…</p>
  ) : slot1 ? (
    <div className="rounded-md border border-border/70 bg-muted/20 px-2 py-1.5">
      <p className="font-medium text-foreground">
        TOP #{slot1.rank} {slot1.label}
      </p>
      <p className="text-muted-foreground">
        {slot1.source}
        {slot1.totalReturnPct != null
          ? ` · ret ${slot1.totalReturnPct.toFixed(1)}%`
          : ""}
      </p>
      {stabilityBadge ? (
        <p
          className="mt-0.5 text-[10px] text-muted-foreground"
          title={stabilityWarn ?? undefined}
          data-testid="operativa-stability"
        >
          {stabilityBadge}
        </p>
      ) : null}
    </div>
  ) : (
    <p className="text-muted-foreground">Sin Finalistas TOP aún.</p>
  );

  const canOpenVerify =
    canVerify &&
    Boolean(
      slot1?.strategyDefinitionId ||
        (instrumentId &&
          getDiaDExperimentTop1(
            instrumentId,
            timeframe,
            effectiveDiaD(diaD),
          )?.strategyDefinitionId),
    );

  const labLinks = (
    <div className="flex flex-col gap-1">
      <Link
        to={labHref}
        className="rounded-md border border-sky-600/30 bg-sky-500/10 px-2 py-1 font-medium text-sky-950 hover:bg-sky-500/20 dark:text-sky-50"
      >
        Abrir estudio (LAB)
      </Link>
      {canOpenVerify ? (
        <button
          type="button"
          className="rounded-md border border-amber-600/30 bg-amber-500/10 px-2 py-1 text-left font-medium text-amber-950 hover:bg-amber-500/20 dark:text-amber-50"
          onClick={startVerify}
        >
          {VERIFY_DIA_D_CTA}
        </button>
      ) : null}
    </div>
  );

  const labSection = (
    <TradingOperativaSection
      sectionId="lab"
      title="Seguimiento Lab"
      summary={
        <span className="text-[10px] text-muted-foreground">
          {slot1 ? `#${slot1.rank} ${slot1.label}` : "Sin Finalista"}
        </span>
      }
    >
      {labTopCard}
      {labLinks}
    </TradingOperativaSection>
  );

  const mandatoBody = (
    <div data-testid="operativa-mandate-review" className="space-y-2">
      <p className="text-[10px] leading-snug text-muted-foreground">
        Un mandato es la estrategia que sigues en este valor con esta cuenta:
        el compromiso vigente hasta que la cambies o la cierres. No es una
        orden de compra.
      </p>
      {adoption !== "none" ? (
        <p className="text-[10px] text-muted-foreground">
          Adopción:{" "}
          <span className="font-medium text-foreground">
            {formatAdoption(adoption)}
          </span>
        </p>
      ) : null}
      <MandateTimelinePanel
        instrumentId={instrumentId}
        accountId={effectiveAccountId}
        compact
      />
    </div>
  );

  const mandatoSection = (
    <TradingOperativaSection
      sectionId="mandato"
      title="Mandato"
      summary={
        <span className="text-[10px] text-muted-foreground">
          {churn.openCount === 0
            ? "Sin estrategia activa"
            : `${churn.openCount} activa${churn.openCount === 1 ? "" : "s"}`}
        </span>
      }
    >
      {mandatoBody}
    </TradingOperativaSection>
  );

  const chipsDetails = (
    <div className="flex flex-wrap items-center justify-between gap-1">
      <details className="w-full">
        <summary
          className="cursor-pointer text-[10px] font-medium text-muted-foreground underline-offset-2 hover:underline"
          data-testid="decision-package-chips-advanced"
        >
          Detalle técnico (avanzado)
        </summary>
        <div className="mt-1 flex flex-wrap items-center justify-between gap-1">
          <DecisionPackageChipsBar
            action={packageChips.action}
            fit={packageChips.fit}
          />
          <div className="flex items-center gap-0.5">
            <MesaTipButton tip="operativa-fit-chip" />
            <MesaTipButton tip="chart-f3-projection" />
            <MesaTipButton tip="operativa-recomendacion" />
          </div>
        </div>
      </details>
    </div>
  );

  const evidenciaSection = (
    <TradingOperativaSection
      sectionId="evidencia"
      title="Evidencia"
      summary={evidenciaSummary}
    >
      <OperativaPulseBlock
        io={rankResult?.io ?? null}
        ta={rankResult?.ta ?? null}
        fa={rankResult?.fa ?? null}
        rank={rankResult?.rank ?? null}
        total={rankResult?.total ?? studyIds.length}
        loading={scoresLoading}
      />

      {/* S4: en la maximizada el dictamen ya es el titular del hero. Repetirlo
          aquí sería una segunda recomendación en la misma pantalla. */}
      {surface === "maximized" ? null : (
        <OperativaDictamenBlock
          opinion={activeOpinion}
          loading={opinionsQuery.isLoading || scoresLoading}
        />
      )}

      {chipsDetails}
    </TradingOperativaSection>
  );

  const resultadosBody = (
    <OperativaOutcomesBlock
      instrumentId={instrumentId}
      accountId={effectiveAccountId}
      symbol={symbol}
    />
  );

  const resultadosSection = (
    <TradingOperativaSection sectionId="resultados" title="Aprendizaje">
      {resultadosBody}
    </TradingOperativaSection>
  );

  const autoBody = <OperativaAutoPanel context={operationalContext} />;

  const autoSection = (
    <TradingOperativaSection sectionId="auto" title="AUTO">
      {autoBody}
    </TradingOperativaSection>
  );

  const contextoBlock = (
    <div
      className="min-w-0 space-y-2"
      data-testid="operativa-contexto-tecnico"
    >
      <div className="rounded-md border border-border/60 bg-muted/15 px-2 py-1.5">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Contexto técnico
        </p>
        <p className="text-[10px] leading-snug text-muted-foreground">
          Tendencia, fuerza y niveles calculados. Informan; no autorizan entradas
          ni sustituyen al dictamen.
        </p>
      </div>
      {analisisDiarioBlock()}
      {estructuraBlock()}
    </div>
  );

  const seguimientoBlock = (
    <div className="min-w-0 space-y-2" data-testid="operativa-seguimiento">
      {labSection}
      {mandatoSection}
    </div>
  );

  const evidenciaBlock = (
    <div className="min-w-0 space-y-2" data-testid="operativa-evidencia">
      {evidenciaSection}
      {resultadosSection}
      {autoSection}
    </div>
  );

  // ── S4 · Ventana maximizada de escritorio ────────────────────────────────
  // Orden de lectura: recomendación principal → actuación → estado de cartera
  // (hero) → ACCIÓN → contexto técnico → seguimiento → evidencia.
  if (surface === "maximized") {
    return (
      <div
        className={cn(
          "flex h-full min-h-0 flex-col gap-2 overflow-hidden p-2 text-[11px]",
          className,
        )}
        data-testid="trading-operativa-panel"
        data-maximized={maximized ? "true" : "false"}
        data-surface="maximized"
        aria-label={`DECISIÓN · ${symbol}`}
      >
        <div className="operativa-panel-scroll min-h-0 flex-1 overflow-y-auto">
          <OperativaRecomendacionPrincipal
            symbol={symbol}
            opinion={activeOpinion ?? null}
            opinionLoading={opinionsQuery.isLoading}
            carteraState={carteraState}
            actionHint={actionHint}
          />
          <div className="operativa-maximized-grid mt-2">
            <div
              className="operativa-max-col-accion min-w-0 space-y-2"
              data-testid="operativa-col-accion"
            >
              {unmeasuredBanner}
              {cockpitCard}
              {fueraEstudioBanner}
            </div>
            <div className="operativa-max-col-contexto min-w-0">
              {contextoBlock}
            </div>
            <div className="operativa-max-col-seguimiento min-w-0">
              {seguimientoBlock}
            </div>
            <div className="operativa-max-col-evidencia min-w-0">
              {evidenciaBlock}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Dock minimizado · cinco grupos plegables ─────────────────────────────
  // El rail derecho (260–420 px) deja de apilar bandas de alto fijo: cada asunto
  // es un grupo independiente, crece con su contenido y recuerda su estado en
  // `bolsa-trading-layout-v1`. Recomendación es el único abierto de entrada.
  if (surface === "dock") {
    const resumenRecomendacion = opinionsQuery.isLoading
      ? "Midiendo…"
      : carteraState.label;
    const resumenSeguimiento = slot1
      ? `#${slot1.rank} ${slot1.label}`
      : "Sin Finalista";
    const resumenMandato =
      churn.openCount === 0
        ? "Sin estrategia activa"
        : `${churn.openCount} activa${churn.openCount === 1 ? "" : "s"}`;

    return (
      <div
        className={cn(
          "flex h-full min-h-0 flex-col overflow-hidden p-2 text-xs",
          className,
        )}
        data-testid="trading-operativa-panel"
        data-maximized={maximized ? "true" : "false"}
        data-surface="dock"
        aria-label={`DECISIÓN · ${symbol}`}
      >
        <div className="operativa-panel-scroll min-h-0 flex-1 space-y-2 overflow-y-auto">
          <TradingOperativaSection
            sectionId="recomendacion"
            title="Recomendación"
            autoHeight
            size="md"
            summary={
              <span className="text-[11px] text-muted-foreground">
                {resumenRecomendacion}
              </span>
            }
          >
            <OperativaDictamenBlock
              opinion={activeOpinion}
              loading={opinionsQuery.isLoading}
              density="dock"
            />
            {unmeasuredBanner}
            {cockpitCard}
            {fueraEstudioBanner}
          </TradingOperativaSection>

          <TradingOperativaSection
            sectionId="fundamental"
            title="Fundamental"
            autoHeight
            size="md"
            summary={
              <span className="text-[11px] text-muted-foreground">
                {activeOpinion?.distress ? "Alerta" : "Sin alerta"}
              </span>
            }
          >
            <p className="leading-snug text-muted-foreground">
              Salud del negocio (FA). Informa; no autoriza entradas.
            </p>
            <OperativaPulseBlock
              io={rankResult?.io ?? null}
              ta={rankResult?.ta ?? null}
              fa={rankResult?.fa ?? null}
              rank={rankResult?.rank ?? null}
              total={rankResult?.total ?? studyIds.length}
              loading={scoresLoading}
              gauges={["fa"]}
              showHeader={false}
              showRank={false}
              showHelp={false}
              density="dock"
            />
            {activeOpinion?.distress ? (
              <p
                className="rounded-md border border-rose-600/40 bg-rose-500/10 px-2 py-1 font-semibold text-rose-900 dark:text-rose-100"
                data-testid="operativa-dock-fundamental-alerta"
              >
                Alerta fundamental: el IO queda frenado aunque el gráfico pinte
                bien.
              </p>
            ) : null}
          </TradingOperativaSection>

          <TradingOperativaSection
            sectionId="tecnico"
            title="Técnico"
            autoHeight
            size="md"
            summary={
              <span className="text-[11px] text-muted-foreground">
                {rankResult?.ta != null
                  ? `TA ${Math.round(rankResult.ta)}`
                  : "Sin TA"}
              </span>
            }
          >
            <p className="leading-snug text-muted-foreground">
              Tendencia, fuerza y niveles calculados. Informan; no autorizan
              entradas.
            </p>
            <OperativaPulseBlock
              io={rankResult?.io ?? null}
              ta={rankResult?.ta ?? null}
              fa={rankResult?.fa ?? null}
              rank={rankResult?.rank ?? null}
              total={rankResult?.total ?? studyIds.length}
              loading={scoresLoading}
              gauges={["ta"]}
              showHeader={false}
              showRank={false}
              showHelp={false}
              density="dock"
            />
            {analisisDiarioBlock("tecnico", "dock")}
            {estructuraBlock("dock", false)}
          </TradingOperativaSection>

          <TradingOperativaSection
            sectionId="seguimientoDia"
            title="Seguimiento del día"
            autoHeight
            size="md"
            summary={
              <span className="text-[11px] text-muted-foreground">
                {resumenSeguimiento}
              </span>
            }
          >
            {analisisDiarioBlock("seguimiento", "dock")}
            {labLinks}
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Mandato
                <span className="ml-1 font-normal normal-case">
                  · {resumenMandato}
                </span>
              </p>
              {mandatoBody}
            </div>
          </TradingOperativaSection>

          <TradingOperativaSection
            sectionId="evidencia"
            title="Evidencia"
            autoHeight
            size="md"
            summary={evidenciaSummary}
          >
            <OperativaPulseBlock
              io={rankResult?.io ?? null}
              ta={rankResult?.ta ?? null}
              fa={rankResult?.fa ?? null}
              rank={rankResult?.rank ?? null}
              total={rankResult?.total ?? studyIds.length}
              loading={scoresLoading}
              gauges={["io"]}
              showHeader={false}
              showHelp={false}
              density="dock"
            />
            {chipsDetails}
            {resultadosBody}
            {autoBody}
          </TradingOperativaSection>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex h-full min-h-0 flex-col gap-2 overflow-hidden p-2 text-[11px]",
        className,
      )}
      data-testid="trading-operativa-panel"
      data-maximized={maximized ? "true" : "false"}
      data-surface={surface}
      aria-label={`DECISIÓN · ${symbol}`}
    >
      <div
        className={cn(
          "operativa-panel-scroll min-h-0 overflow-y-auto",
          maximized ? "flex-1" : "shrink-0",
        )}
      >
        <div className="operativa-panel-grid">
          <div className="operativa-col-decision min-w-0 space-y-2">
            {unmeasuredBanner}
            {analisisDiarioBlock()}
            {estructuraBlock()}
            {cockpitCard}
            {fueraEstudioBanner}
          </div>

          <div className="operativa-col-detalle min-w-0 space-y-2">
            {labSection}
            {mandatoSection}
          </div>

          <div className="operativa-col-info min-w-0 space-y-2">
            {evidenciaSection}
            {resultadosSection}
            {autoSection}
          </div>
        </div>
      </div>
    </div>
  );
}
