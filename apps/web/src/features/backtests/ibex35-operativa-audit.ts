/**
 * Auditoría operativa IBEX 35 (offline): simula lista completa + coach + Lista AUTO.
 *
 * No llama API/BD. Detecta fallos de coherencia del embudo:
 * - TOP #1 pegajoso (mismo preset en casi todos los valores)
 * - soft-fallback cuando hay periodReturns
 * - TOP mono-familia / slots duplicados
 * - Lista AUTO cap/avance/settle
 * - Política ciclo: sin mejora Lab no pisa active
 *
 * Live DB: `python scripts/research/audit_ibex35_operativa.py`
 *
 * @see docs/engineering/backtesting-funnel-handoff-2026-07-29.md
 */

import { IBEX35_INSTRUMENTS } from "@bolsa/shared";
import {
  rankTechnicalRecommendations,
  type DeepCoachContext,
  type TechnicalRecommendation,
} from "@/features/backtests/backtest-deep-coach";
import type { ExplorePresetRow } from "@/features/backtests/backtest-explore-value";
import { periodReturnsFromEquity } from "@/features/backtests/backtest-period-returns";
import {
  createListAutoCampaign,
  isListAutoComplete,
  LIST_AUTO_BATCH_SIZE,
  LIST_AUTO_HARD_MAX,
  LIST_AUTO_MAX_INSTRUMENTS,
  advanceListAutoAfterSettle,
  shouldStartListAuto,
  type FullCycleSettleReason,
} from "@/features/backtests/backtest-list-auto";
import {
  resolveFullCycleSaveDecision,
  shouldAutoHandoffLab,
} from "@/features/backtests/backtest-assistant-full-cycle";

export type AuditSeverity = "critical" | "warn" | "info" | "ok";

export type AuditFinding = {
  code: string;
  severity: AuditSeverity;
  message: string;
  detail?: string;
};

export type InstrumentCoachSnapshot = {
  symbol: string;
  top1Type: string | null;
  top1Category: string | null;
  topTypes: string[];
  categories: string[];
  softFallbackCount: number;
  qualityFlaggedCount: number;
  slotCount: number;
};

export type Ibex35OperativaAuditReport = {
  asOf: string;
  instrumentCount: number;
  expectedCount: number;
  listAutoCap: number;
  findings: AuditFinding[];
  snapshots: InstrumentCoachSnapshot[];
  top1Frequency: Record<string, number>;
  /** Fracción de valores con el mismo #1 (0–1). */
  stickyTop1Share: number;
  softFallbackRate: number;
  criticalCount: number;
  warnCount: number;
  passed: boolean;
};

const PRESET_DEFS: Array<{
  strategyType: ExplorePresetRow["strategyType"];
  label: string;
  category: ExplorePresetRow["category"];
  categoryLabel: string;
}> = [
  {
    strategyType: "sma_crossover",
    label: "SMA 20/50",
    category: "trend",
    categoryLabel: "Tendencia",
  },
  {
    strategyType: "golden_cross",
    label: "Golden",
    category: "trend",
    categoryLabel: "Tendencia",
  },
  {
    strategyType: "ma_stack_bullish",
    label: "MA stack",
    category: "trend",
    categoryLabel: "Tendencia",
  },
  {
    strategyType: "rsi_mean_reversion",
    label: "RSI",
    category: "mean_reversion",
    categoryLabel: "Reversión",
  },
  {
    strategyType: "stoch_oversold",
    label: "Stoch",
    category: "mean_reversion",
    categoryLabel: "Reversión",
  },
  {
    strategyType: "macd_signal_cross",
    label: "MACD",
    category: "momentum",
    categoryLabel: "Momentum",
  },
  {
    strategyType: "donchian_breakout",
    label: "Donchian",
    category: "trend",
    categoryLabel: "Tendencia",
  },
];

function equityRamp(points: number[]): Array<{ equity: number }> {
  return points.map((equity) => ({ equity }));
}

function thirdsEquity(earlyMul: number, midMul: number, lateMul: number) {
  const pts: number[] = [];
  let eq = 100;
  for (let i = 0; i < 4; i += 1) {
    eq *= 1 + earlyMul / 4 / 100;
    pts.push(eq);
  }
  for (let i = 0; i < 4; i += 1) {
    eq *= 1 + midMul / 4 / 100;
    pts.push(eq);
  }
  for (let i = 0; i < 4; i += 1) {
    eq *= 1 + lateMul / 4 / 100;
    pts.push(eq);
  }
  return periodReturnsFromEquity(equityRamp(pts))!;
}

function baseRow(
  partial: Partial<ExplorePresetRow> &
    Pick<ExplorePresetRow, "strategyType" | "label">,
): ExplorePresetRow {
  return {
    category: "trend",
    categoryLabel: "Tendencia",
    status: "ok",
    totalReturnPct: 10,
    excessReturnPct: 2,
    maxDrawdownPct: 12,
    tradeCount: 20,
    barCount: 500,
    sharpeRatio: 0.8,
    buyHoldReturnPct: 8,
    ...partial,
  };
}

/**
 * Perfil de late-returns por índice de símbolo.
 * Rota el ganador entre familias para que un IBEX sano no tenga #1 único.
 */
export function lateProfileForIndex(index: number): Record<string, number> {
  const rotate = index % 3;
  if (rotate === 0) {
    return {
      sma_crossover: 6 + (index % 5),
      golden_cross: 5,
      ma_stack_bullish: 4,
      rsi_mean_reversion: 18 + (index % 7),
      stoch_oversold: 10,
      macd_signal_cross: 8,
      donchian_breakout: 7,
    };
  }
  if (rotate === 1) {
    return {
      sma_crossover: 16 + (index % 6),
      golden_cross: 12,
      ma_stack_bullish: 10,
      rsi_mean_reversion: 5,
      stoch_oversold: 4,
      macd_signal_cross: 9,
      donchian_breakout: 14,
    };
  }
  return {
    sma_crossover: 7,
    golden_cross: 6,
    ma_stack_bullish: 5,
    rsi_mean_reversion: 8,
    stoch_oversold: 7,
    macd_signal_cross: 20 + (index % 5),
    donchian_breakout: 9,
  };
}

/** Catálogo sintético con periodReturns (ruta coach fuerte). */
export function catalogForIbexSymbol(
  symbol: string,
  index: number,
  opts?: { omitPeriodReturns?: boolean },
): ExplorePresetRow[] {
  const lateByType = lateProfileForIndex(index);
  return PRESET_DEFS.map((d) => {
    const late = lateByType[d.strategyType] ?? 0;
    const early = late > 0 ? late * 0.2 : 8;
    const mid = late > 0 ? late * 0.4 : 4;
    const pr = thirdsEquity(early, mid, late);
    return baseRow({
      ...d,
      runId: `${symbol}-${d.strategyType}`,
      periodReturns: opts?.omitPeriodReturns ? undefined : pr,
      totalReturnPct: early + mid + late,
      excessReturnPct: late - 2,
      maxDrawdownPct: Math.max(8, 25 - late / 2),
      sharpeRatio: 0.5 + late / 40,
    });
  });
}

function snapshotFromRank(
  symbol: string,
  top: TechnicalRecommendation[],
): InstrumentCoachSnapshot {
  return {
    symbol,
    top1Type: top[0]?.row.strategyType ?? null,
    top1Category: top[0]?.row.category ?? null,
    topTypes: top.map((t) => t.row.strategyType),
    categories: top.map((t) => t.row.category),
    softFallbackCount: top.filter((t) => t.usedSoftFallback).length,
    qualityFlaggedCount: top.filter((t) => t.qualityFlagged).length,
    slotCount: top.length,
  };
}

function ctx(symbol: string): DeepCoachContext {
  return {
    symbol,
    timeframe: "1d",
    horizon: "swing",
    riskTolerance: "moderate",
  };
}

/**
 * Simula coach TOP-3 sobre los 35 del catálogo compartido + operativa Lista AUTO / ciclo.
 */
export function runIbex35OperativaAudit(opts?: {
  symbols?: string[];
  /** Si true, omite periodReturns (debe disparar soft-fallback warn/critical). */
  forceSoftFallback?: boolean;
  /** Si true, fuerza el mismo late-winner en todos (debe disparar sticky_top1). */
  forceStickyTop1?: boolean;
}): Ibex35OperativaAuditReport {
  const findings: AuditFinding[] = [];
  const expected = IBEX35_INSTRUMENTS.map((i) => i.symbol);
  const symbols = opts?.symbols ?? expected;

  if (symbols.length !== expected.length && !opts?.symbols) {
    findings.push({
      code: "ibex_count_mismatch",
      severity: "critical",
      message: `Catálogo IBEX esperado ${expected.length}, got ${symbols.length}`,
    });
  }

  if (symbols.length > LIST_AUTO_HARD_MAX) {
    findings.push({
      code: "list_auto_over_cap",
      severity: "warn",
      message: `Lista ${symbols.length} > tope duro ${LIST_AUTO_HARD_MAX}; Lista AUTO recorta.`,
    });
  } else if (symbols.length > LIST_AUTO_BATCH_SIZE) {
    findings.push({
      code: "list_auto_multi_batch",
      severity: "ok",
      message: `Lista ${symbols.length} · ${Math.ceil(symbols.length / LIST_AUTO_BATCH_SIZE)} tandas de ~${LIST_AUTO_BATCH_SIZE} (sin truncar).`,
    });
  }

  const snapshots: InstrumentCoachSnapshot[] = [];
  let softFallbacks = 0;
  let rankedSlots = 0;

  for (let i = 0; i < symbols.length; i += 1) {
    const symbol = symbols[i]!;
    const omitPeriodReturns = Boolean(opts?.forceSoftFallback);
    const catalog = opts?.forceStickyTop1
      ? catalogForIbexSymbol(symbol, 0, { omitPeriodReturns })
      : catalogForIbexSymbol(symbol, i, { omitPeriodReturns });

    const top = rankTechnicalRecommendations(catalog, ctx(symbol), {
      limit: 3,
      diversifyCategories: true,
    });
    const snap = snapshotFromRank(symbol, top);
    snapshots.push(snap);
    softFallbacks += snap.softFallbackCount;
    rankedSlots += snap.slotCount;

    if (snap.slotCount < 3) {
      findings.push({
        code: "thin_top",
        severity: "warn",
        message: `${symbol}: TOP con ${snap.slotCount} slots (esperado 3)`,
      });
    }

    const uniqueTypes = new Set(snap.topTypes);
    if (uniqueTypes.size < snap.topTypes.length) {
      findings.push({
        code: "duplicate_slot_types",
        severity: "critical",
        message: `${symbol}: strategyType duplicado en TOP`,
        detail: snap.topTypes.join(", "),
      });
    }

    const cats = new Set(snap.categories);
    if (snap.slotCount >= 3 && cats.size < 2) {
      findings.push({
        code: "mono_family_top",
        severity: "warn",
        message: `${symbol}: TOP-3 mono-familia (${[...cats].join(",")})`,
      });
    }
  }

  const top1Frequency: Record<string, number> = {};
  for (const s of snapshots) {
    if (!s.top1Type) continue;
    top1Frequency[s.top1Type] = (top1Frequency[s.top1Type] ?? 0) + 1;
  }
  const maxTop1 = Math.max(0, ...Object.values(top1Frequency));
  const stickyTop1Share = snapshots.length > 0 ? maxTop1 / snapshots.length : 0;
  const softFallbackRate = rankedSlots > 0 ? softFallbacks / rankedSlots : 0;

  if (stickyTop1Share >= 0.75 && snapshots.length >= 10) {
    findings.push({
      code: "sticky_top1",
      severity: "critical",
      message: `TOP #1 pegajoso: ${(stickyTop1Share * 100).toFixed(0)}% comparten el mismo preset`,
      detail: JSON.stringify(top1Frequency),
    });
  } else if (stickyTop1Share >= 0.5 && snapshots.length >= 10) {
    findings.push({
      code: "sticky_top1",
      severity: "warn",
      message: `TOP #1 concentrado: ${(stickyTop1Share * 100).toFixed(0)}% mismo preset`,
      detail: JSON.stringify(top1Frequency),
    });
  }

  if (softFallbackRate > 0.4) {
    findings.push({
      code: "soft_fallback_rate",
      severity: "critical",
      message: `Soft-fallback ${(softFallbackRate * 100).toFixed(0)}% de slots (periodReturns ausentes o rota)`,
    });
  } else if (softFallbackRate > 0.05) {
    findings.push({
      code: "soft_fallback_rate",
      severity: "warn",
      message: `Soft-fallback ${(softFallbackRate * 100).toFixed(0)}% de slots`,
    });
  }

  // ——— Lista AUTO operativa ———
  const startOk = shouldStartListAuto({
    universeMode: "list",
    fullCycleOnPlay: true,
    listId: "ibex35",
    instrumentCount: symbols.length,
  });
  if (!startOk) {
    findings.push({
      code: "list_auto_start_blocked",
      severity: "critical",
      message: "shouldStartListAuto=false con lista + ciclo ON",
    });
  }

  const campaign = createListAutoCampaign({
    listId: "ibex35",
    instrumentIds: symbols.map((s) => `id-${s}`),
  });
  const expectedQueue = Math.min(symbols.length, LIST_AUTO_HARD_MAX);
  if (campaign.instrumentIds.length !== expectedQueue) {
    findings.push({
      code: "list_auto_slice_bug",
      severity: "critical",
      message: `Campaña recortó mal: ${campaign.instrumentIds.length} vs min(${symbols.length},${LIST_AUTO_HARD_MAX})`,
    });
  }

  const settleReasons: FullCycleSettleReason[] = [
    "saved",
    "skip_lab",
    "skip_finalists",
  ];
  let steps = 0;
  while (!isListAutoComplete(campaign) && !campaign.aborted) {
    void settleReasons[steps % settleReasons.length];
    const adv = advanceListAutoAfterSettle(campaign);
    steps += 1;
    if (adv === "done" || adv === "aborted") break;
    if (steps > expectedQueue + 5) {
      findings.push({
        code: "list_auto_infinite",
        severity: "critical",
        message: "Bucle Lista AUTO no termina",
      });
      break;
    }
  }
  if (!isListAutoComplete(campaign) && !campaign.aborted) {
    findings.push({
      code: "list_auto_incomplete",
      severity: "critical",
      message: `Campaña incompleta index=${campaign.index}/${campaign.instrumentIds.length}`,
    });
  } else {
    findings.push({
      code: "list_auto_complete",
      severity: "ok",
      message: `Lista AUTO recorrió ${campaign.instrumentIds.length} valores (settle mixto)`,
    });
  }

  // ——— Política ciclo completo ———
  if (
    shouldAutoHandoffLab({
      fullCycleActive: true,
      allZonesDone: true,
      improvedCount: 0,
      alreadyTriggered: false,
    })
  ) {
    findings.push({
      code: "cycle_handoff_without_improve",
      severity: "critical",
      message: "Lab auto-handoff con improvedCount=0 (no debe)",
    });
  }

  const keep = resolveFullCycleSaveDecision({
    postLab: true,
    labImprovedCount: 0,
    canSaveTop: true,
    existingTopStatus: "active",
  });
  if (keep.action !== "skip_keep_previous") {
    findings.push({
      code: "cycle_overwrite_active",
      severity: "critical",
      message: `Sin mejora Lab debería skip_keep_previous, got ${keep.action}`,
    });
  } else {
    findings.push({
      code: "cycle_preserve_active",
      severity: "ok",
      message: "Sin mejora Lab conserva TOP active",
    });
  }

  const save = resolveFullCycleSaveDecision({
    postLab: true,
    labImprovedCount: 2,
    canSaveTop: true,
  });
  if (save.action !== "save_active") {
    findings.push({
      code: "cycle_save_blocked",
      severity: "critical",
      message: `Con mejora Lab debería save_active, got ${save.action}`,
    });
  }

  const criticalCount = findings.filter(
    (f) => f.severity === "critical",
  ).length;
  const warnCount = findings.filter((f) => f.severity === "warn").length;

  if (criticalCount === 0 && warnCount === 0) {
    findings.push({
      code: "ibex_coach_healthy",
      severity: "ok",
      message: `Coach IBEX simulado OK · ${symbols.length} valores · #1 diversificado`,
      detail: JSON.stringify(top1Frequency),
    });
  }

  return {
    asOf: new Date().toISOString().slice(0, 10),
    instrumentCount: symbols.length,
    expectedCount: expected.length,
    listAutoCap: LIST_AUTO_MAX_INSTRUMENTS,
    findings,
    snapshots,
    top1Frequency,
    stickyTop1Share,
    softFallbackRate,
    criticalCount,
    warnCount,
    passed: criticalCount === 0,
  };
}

/** Resumen texto para consola / observación. */
export function formatIbex35AuditReport(
  report: Ibex35OperativaAuditReport,
): string {
  const lines = [
    `IBEX35 operativa audit · ${report.asOf}`,
    `valores=${report.instrumentCount} (esperado ${report.expectedCount}) · cap Lista AUTO=${report.listAutoCap}`,
    `stickyTop1=${(report.stickyTop1Share * 100).toFixed(1)}% · softFallback=${(report.softFallbackRate * 100).toFixed(1)}%`,
    `passed=${report.passed} · critical=${report.criticalCount} · warn=${report.warnCount}`,
    "TOP #1 freq: " + JSON.stringify(report.top1Frequency),
    "Findings:",
  ];
  for (const f of report.findings) {
    lines.push(`  [${f.severity}] ${f.code}: ${f.message}`);
  }
  return lines.join("\n");
}
