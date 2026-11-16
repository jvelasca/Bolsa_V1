import type { BacktestRunDetailDto } from "@bolsa/shared";
import type { OosEvidence } from "@/features/backtests/backtest-oos-evidence";
import {
  classifyWfe,
  formatWfe,
  walkForwardStabilityFlags,
  wfeBandLabel,
} from "@/features/backtests/backtest-walk-forward-metrics";
import {
  classifyPbo,
  formatPbo,
  pboBandLabel,
  PBO_WARN,
} from "@/features/backtests/backtest-pbo";

export type PaperCheckId =
  | "has_trades"
  | "net_profit"
  | "expectancy"
  | "beats_buy_hold"
  | "drawdown_ok"
  | "sample_size"
  | "saved_strategy"
  | "oos_validation"
  | "edge_report"
  | "pbo"
  | "ack_insample";

export type PaperCheckStatus = "pass" | "warn" | "fail" | "info";

export type PaperCheck = {
  id: PaperCheckId;
  status: PaperCheckStatus;
  label: string;
  detail: string;
  /** User must acknowledge warn/fail before deploy (ack_insample is always required). */
  requiresAck?: boolean;
};

export type PaperGateInput = {
  detail: BacktestRunDetailDto;
  excessReturnPct: number | null;
  buyHoldReturnPct: number | null;
  oosEvidence?: OosEvidence | null;
  /** Medición NETA declarada por el run (P1). Ausente = no medido, nunca 0. */
  netEvidence?: PaperNetEvidence | null;
};

/**
 * Evidencia de rentabilidad neta de un run (P1). Cada hueco es `null`, nunca 0:
 * `returnBasis: null` significa que el run no declaró cómo midió, no que midiera 0.
 */
export type PaperNetEvidence = {
  returnBasis: "net" | "gross" | null;
  netReturnPct: number | null;
  expectancyCurrency: number | null;
  roundTripCostBps: number | null;
  netTradeCount: number | null;
};

export const EMPTY_PAPER_NET_EVIDENCE: PaperNetEvidence = {
  returnBasis: null,
  netReturnPct: null,
  expectancyCurrency: null,
  roundTripCostBps: null,
  netTradeCount: null,
};

function metricNum(
  metrics: Record<string, number | string | null> | null | undefined,
  key: string,
): number | null {
  if (!metrics) return null;
  const value = metrics[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * Resuelve la evidencia neta desde `metrics` del run y/o `isMetrics` del trial,
 * en orden de preferencia. La base (`returnBasis`) y el retorno neto deben venir
 * del MISMO registro: mezclar payloads inventaría una medición.
 */
export function resolvePaperNetEvidence(
  ...sources: (Record<string, number | string | null> | null | undefined)[]
): PaperNetEvidence {
  for (const metrics of sources) {
    if (!metrics) continue;
    const rawBasis = metrics.returnBasis;
    const returnBasis =
      rawBasis === "net" || rawBasis === "gross" ? rawBasis : null;
    const netReturnPct = metricNum(metrics, "netReturnPct");
    if (returnBasis == null && netReturnPct == null) continue;
    return {
      returnBasis,
      netReturnPct,
      expectancyCurrency: metricNum(metrics, "expectancyCurrency"),
      roundTripCostBps: metricNum(metrics, "roundTripCostBps"),
      netTradeCount: metricNum(metrics, "netTradeCount"),
    };
  }
  return { ...EMPTY_PAPER_NET_EVIDENCE };
}

export type PaperGateResult = {
  checks: PaperCheck[];
  hardBlockers: PaperCheckId[];
  canDeploy: boolean;
};

const MAX_DD_WARN = 35;
const MIN_BARS = 200;
const MIN_TRADES = 4;
/**
 * Suelo de fricción ida y vuelta (P1). Espeja `BASELINE_THRESHOLDS`
 * (`minRoundTripCostBps = 22`) del backend; el test anti-drift vive ahí.
 */
const MIN_ROUND_TRIP_COST_BPS = 22;

/** P1 — el run debe declarar medición NETA con fricción real y en positivo. */
function buildNetProfitCheck(net: PaperNetEvidence): PaperCheck | null {
  if (net.returnBasis === "gross") {
    return {
      id: "net_profit",
      status: "fail",
      label: "Beneficio neto",
      detail:
        "Este run se midió SIN fricción (returnBasis = gross). Relánzalo con costes de referencia: una simulación bruta no se despliega a paper.",
    };
  }

  if (net.returnBasis !== "net") {
    return {
      id: "net_profit",
      status: "warn",
      label: "Beneficio neto",
      detail:
        "Sin medición neta declarada (run anterior al gate P1). Relánzalo con costes para ver el resultado real antes de paper.",
      requiresAck: true,
    };
  }

  const costBps = net.roundTripCostBps;
  if (costBps == null) {
    return {
      id: "net_profit",
      status: "warn",
      label: "Beneficio neto",
      detail:
        "El run dice medir neto pero no declara la fricción aplicada (bps ida y vuelta). Sin coste declarado el neto no es auditable.",
      requiresAck: true,
    };
  }
  if (costBps < MIN_ROUND_TRIP_COST_BPS) {
    return {
      id: "net_profit",
      status: "fail",
      label: "Beneficio neto",
      detail: `Fricción declarada de ${costBps} bps, por debajo del suelo de ${MIN_ROUND_TRIP_COST_BPS} bps. El neto está inflado: revisa el modelo de costes.`,
    };
  }

  const netPct = net.netReturnPct;
  if (netPct == null) {
    return {
      id: "net_profit",
      status: "warn",
      label: "Beneficio neto",
      detail:
        "El run dice medir neto pero no trae el retorno neto. Sin ese dato no hay gate: vuelve a lanzarlo.",
      requiresAck: true,
    };
  }

  if (netPct <= 0) {
    return {
      id: "net_profit",
      status: "fail",
      label: "Beneficio neto",
      detail: `Retorno neto ${netPct.toFixed(1)}% tras ${costBps} bps ida y vuelta. Paper no arregla una pérdida por fricción.`,
    };
  }

  return {
    id: "net_profit",
    status: "pass",
    label: "Beneficio neto",
    detail: `Neto +${netPct.toFixed(1)}% tras ${costBps} bps ida y vuelta · ${net.netTradeCount ?? "—"} operaciones cerradas.`,
  };
}

/** Esperanza por operación en moneda. `null` no es 0: se declara el hueco. */
function buildExpectancyCheck(net: PaperNetEvidence): PaperCheck | null {
  if (net.returnBasis !== "net") return null;

  const expectancy = net.expectancyCurrency;
  if (expectancy == null) {
    return {
      id: "expectancy",
      status: "warn",
      label: "Esperanza por operación",
      detail:
        "Sin esperanza medida en moneda. Necesita operaciones cerradas y unidad de riesgo declarada.",
      requiresAck: true,
    };
  }

  if (expectancy <= 0) {
    return {
      id: "expectancy",
      status: "warn",
      label: "Esperanza por operación",
      detail: `Esperanza ${expectancy.toFixed(2)} por operación cerrada: el sistema no gana de media. Paper solo como experimento.`,
      requiresAck: true,
    };
  }

  return {
    id: "expectancy",
    status: "pass",
    label: "Esperanza por operación",
    detail: `+${expectancy.toFixed(2)} por operación cerrada (moneda de la cuenta).`,
  };
}

function buildOosValidationCheck(
  evidence: OosEvidence | null | undefined,
): PaperCheck {
  const kind = evidence?.kind ?? "none";

  if (kind === "none") {
    return {
      id: "oos_validation",
      status: "warn",
      label: "Validación fuera de muestra",
      detail:
        "Este run no trae hold-out, walk-forward ni CPCV. En Optimizar, reserva OOS o activa WF/CPCV antes de paper.",
      requiresAck: true,
    };
  }

  if (kind === "walkforward" || kind === "cpcv") {
    const rawMean = evidence!.meanOosScore ?? evidence!.oosScore;
    if (rawMean == null || !Number.isFinite(rawMean)) {
      return {
        id: "oos_validation",
        status: "warn",
        label: kind === "cpcv" ? "CPCV ligero OOS" : "Walk-forward OOS",
        detail:
          "La evidencia no trae score OOS medio. Sin ese dato no se puede decir que el tramo reservado confirme el in-sample.",
        requiresAck: true,
      };
    }
    const mean = rawMean;
    const std = evidence!.stdOosScore ?? 0;
    const folds =
      kind === "cpcv"
        ? (evidence!.pathCount ?? evidence!.nFolds)
        : evidence!.nFolds;
    const foldLabel =
      kind === "cpcv"
        ? folds != null
          ? `${folds} paths`
          : "paths CPCV"
        : folds != null
          ? `${folds} pliegues`
          : "pliegues";
    const label = kind === "cpcv" ? "CPCV ligero OOS" : "Walk-forward OOS";
    const wfe = evidence!.walkForwardEfficiency;
    const band = classifyWfe(wfe);
    const flags = walkForwardStabilityFlags({
      walkForwardEfficiency: wfe,
      oosCv: evidence!.oosCv,
      positiveOosFoldShare: evidence!.positiveOosFoldShare,
    });
    const wfePart =
      wfe != null
        ? ` · WFE ${formatWfe(wfe)} (${wfeBandLabel(band)}, lab score)`
        : "";
    const cvPart =
      evidence!.oosCv != null && Number.isFinite(evidence!.oosCv)
        ? ` · CV ${evidence!.oosCv.toFixed(2)}`
        : "";
    const meanLine = `Media OOS ${mean.toFixed(2)}${std > 0 ? ` ± ${std.toFixed(2)}` : ""}${wfePart}${cvPart}`;

    if (
      mean < 0 ||
      flags.weakWfe ||
      flags.fewPositiveFolds ||
      flags.unstableCv
    ) {
      const reasons: string[] = [];
      if (mean < 0) reasons.push("media OOS negativa");
      if (flags.weakWfe) reasons.push("WFE < 0.5");
      if (flags.fewPositiveFolds)
        reasons.push(
          kind === "cpcv" ? "pocos paths OOS≥0" : "pocos pliegues OOS≥0",
        );
      if (flags.unstableCv) reasons.push("OOS inestable (CV alto)");
      return {
        id: "oos_validation",
        status: "warn",
        label,
        detail: `${meanLine} (${foldLabel}). Aviso: ${reasons.join("; ")}. Paper solo como experimento.`,
        requiresAck: true,
      };
    }
    return {
      id: "oos_validation",
      status: "pass",
      label,
      detail:
        kind === "cpcv"
          ? `${meanLine} en ${foldLabel}. CPCV ligero (purge/embargo en barras) — no es PBO ni garantía de edge.`
          : `${meanLine} en ${foldLabel}. No es garantía de edge.`,
    };
  }

  // holdout
  const score = evidence!.oosScore;
  const ret =
    evidence!.oosReturnPct != null
      ? ` · retorno OOS ${evidence!.oosReturnPct.toFixed(1)}%`
      : "";
  if (score == null || !Number.isFinite(score)) {
    return {
      id: "oos_validation",
      status: "warn",
      label: "Hold-out OOS",
      detail:
        "La evidencia no trae score del tramo reservado. Un hueco no es un cero: vuelve a correr el hold-out.",
      requiresAck: true,
    };
  }
  if (score < 0) {
    return {
      id: "oos_validation",
      status: "warn",
      label: "Hold-out OOS",
      detail: `Score OOS ${score.toFixed(2)}${ret} en negativo. El tramo reservado no confirma el IS.`,
      requiresAck: true,
    };
  }
  return {
    id: "oos_validation",
    status: "pass",
    label: "Hold-out OOS",
    detail: `Score OOS ${score.toFixed(2)}${ret}. Un solo corte — no es walk-forward.`,
  };
}

/** Heuristic pre-service checklist (P4 / P4.B). Does not invent edge — only gates paper deploy UX. */
export function buildPaperGate(input: PaperGateInput): PaperGateResult {
  const { detail, excessReturnPct, oosEvidence } = input;
  const net = input.netEvidence ?? EMPTY_PAPER_NET_EVIDENCE;
  const checks: PaperCheck[] = [];

  if (detail.tradeCount <= 0) {
    checks.push({
      id: "has_trades",
      status: "fail",
      label: "Hay operaciones",
      detail: "Sin compras/ventas no hay nada que desplegar en paper.",
    });
  } else if (detail.tradeCount < MIN_TRADES) {
    checks.push({
      id: "has_trades",
      status: "warn",
      label: "Muestra de operaciones",
      detail: `Solo ${detail.tradeCount} ops (recomendado ≥ ${MIN_TRADES}). El paper será ruidoso.`,
      requiresAck: true,
    });
  } else {
    checks.push({
      id: "has_trades",
      status: "pass",
      label: "Hay operaciones",
      detail: `${detail.tradeCount} operaciones · ${detail.winCount} a favor.`,
    });
  }

  const netCheck = buildNetProfitCheck(net);
  if (netCheck) checks.push(netCheck);
  const expectancyCheck = buildExpectancyCheck(net);
  if (expectancyCheck) checks.push(expectancyCheck);

  if (excessReturnPct == null) {
    checks.push({
      id: "beats_buy_hold",
      status: "warn",
      label: "Vs buy & hold",
      detail: "Sin baseline claro. Revisa el periodo y vuelve a probar.",
      requiresAck: true,
    });
  } else if (excessReturnPct <= 0) {
    checks.push({
      id: "beats_buy_hold",
      status: "warn",
      label: "Vs buy & hold",
      detail: `No bate comprar y mantener (${excessReturnPct.toFixed(1)} pp). Paper solo como experimento.`,
      requiresAck: true,
    });
  } else {
    checks.push({
      id: "beats_buy_hold",
      status: "pass",
      label: "Vs buy & hold",
      detail: `Exceso +${excessReturnPct.toFixed(1)} pp in-sample (no garantiza fuera de muestra).`,
    });
  }

  if (detail.maxDrawdownPct >= MAX_DD_WARN) {
    checks.push({
      id: "drawdown_ok",
      status: "warn",
      label: "Drawdown",
      detail: `Peor caída ${detail.maxDrawdownPct.toFixed(1)}% (≥ ${MAX_DD_WARN}%). Revisa si toleras ese riesgo en paper.`,
      requiresAck: true,
    });
  } else {
    checks.push({
      id: "drawdown_ok",
      status: "pass",
      label: "Drawdown",
      detail: `Peor caída ${detail.maxDrawdownPct.toFixed(1)}% dentro del umbral suave.`,
    });
  }

  if (detail.barCount < MIN_BARS) {
    checks.push({
      id: "sample_size",
      status: "warn",
      label: "Tamaño de muestra",
      detail: `${detail.barCount} barras (< ${MIN_BARS}). Preferible historial largo antes de paper.`,
      requiresAck: true,
    });
  } else {
    checks.push({
      id: "sample_size",
      status: "pass",
      label: "Tamaño de muestra",
      detail: `${detail.barCount} barras · ${detail.firstDate} → ${detail.lastDate}.`,
    });
  }

  if (!detail.strategyDefinitionId) {
    checks.push({
      id: "saved_strategy",
      status: "fail",
      label: "Estrategia guardada",
      detail:
        "Sin StrategyDefinition vinculada el API no puede crear paper. Guarda/adopta la estrategia desde Optimizar o Mis estrategias y vuelve a probar.",
    });
  } else {
    checks.push({
      id: "saved_strategy",
      status: "pass",
      label: "Estrategia guardada",
      detail: "Hay definición persistida vinculada al run.",
    });
  }

  const oosCheck = buildOosValidationCheck(oosEvidence);
  checks.push(oosCheck);

  const edge = oosEvidence;
  if (edge?.credibility != null || edge?.edgeBand != null) {
    const band = edge.edgeBand ?? "n/d";
    const cred = edge.credibility != null ? edge.credibility.toFixed(1) : "n/d";
    const mc =
      edge.monteCarloPValue != null
        ? ` · MC p=${edge.monteCarloPValue.toFixed(3)}`
        : "";
    const dsr = edge.dsr != null ? ` · DSR ${edge.dsr.toFixed(2)}` : "";
    const weak =
      band === "luck" ||
      (edge.monteCarloPValue != null && edge.monteCarloPValue > 0.05) ||
      (edge.dsr != null && edge.dsr < 0.5);
    checks.push({
      id: "edge_report",
      status: weak ? "warn" : "pass",
      label: "EdgeReport lab (lite)",
      detail: weak
        ? `Credibility ${cred} · banda ${band}${mc}${dsr}. Señal débil / no skill — paper solo como experimento.`
        : `Credibility ${cred} · banda ${band}${mc}${dsr}. Suite lab (no auto-live; edge_reports lite si Optimizar persistió).`,
      requiresAck: weak || undefined,
    });
  } else {
    checks.push({
      id: "edge_report",
      status: "info",
      label: "EdgeReport lab (lite)",
      detail:
        "Sin suite MC/DSR del laboratorio. Tras Optimizar con OOS/WF/CPCV y ≥3 ops del campeón se genera automáticamente.",
    });
  }

  if (edge?.pbo != null && Number.isFinite(edge.pbo)) {
    const band = classifyPbo(edge.pbo);
    const weak = edge.pbo >= PBO_WARN;
    checks.push({
      id: "pbo",
      status: weak ? "warn" : "pass",
      label: "PBO (CSCV lab)",
      detail: weak
        ? `PBO ${formatPbo(edge.pbo)} (${pboBandLabel(band)}). El proceso IS≈azar OOS — paper solo como experimento.`
        : `PBO ${formatPbo(edge.pbo)} (${pboBandLabel(band)}). CSCV lab sobre scores; no es PBO de eventos completo.`,
      requiresAck: weak || undefined,
    });
  } else if (oosEvidence?.kind === "cpcv") {
    checks.push({
      id: "pbo",
      status: "info",
      label: "PBO (CSCV lab)",
      detail: "CPCV sin PBO calculado (hace falta S par ≥4 y ≥2 candidatos).",
    });
  }

  const hasOosPass = oosCheck.status === "pass";
  if (hasOosPass) {
    checks.push({
      id: "ack_insample",
      status: "info",
      label: "Paper sigue siendo simulación",
      detail:
        "Hay señal OOS/WF del laboratorio, pero el paper no es dinero real ni gate de producción.",
      requiresAck: true,
    });
  } else {
    checks.push({
      id: "ack_insample",
      status: "info",
      label: "Solo evidencia in-sample (o OOS débil)",
      detail:
        "Este resultado de prueba no sustituye una validación OOS/WF sólida. No es luz verde para dinero real.",
      requiresAck: true,
    });
  }

  const hardBlockers = checks
    .filter((c) => c.status === "fail")
    .map((c) => c.id);

  return {
    checks,
    hardBlockers,
    canDeploy: hardBlockers.length === 0,
  };
}

export function requiredAckIds(checks: PaperCheck[]): PaperCheckId[] {
  return checks.filter((c) => c.requiresAck).map((c) => c.id);
}
