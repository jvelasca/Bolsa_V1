/**
 * Informe Evidence sesión C (DÍA D) — solo interpreta métricas ya calculadas.
 * No recalcula FA ni Coach. Sandbox ≠ DEMO.
 *
 * Paridad con Python ``bolsa_analytics.knowledge.dia_d_session_evidence``.
 * UI: `trading-dia-d-replay-panel.tsx` · API narración: `explainDiaDSessionEvidence`.
 *
 * @see docs/engineering/backtesting-dia-d-premises-2026-07-31.md
 */

export type DiaDEvidenceBand = 'favorable' | 'mixed' | 'adverse' | 'incomplete';

export type DiaDSessionEvidenceInput = {
  mode: 'manual' | 'semi' | 'auto';
  symbol: string;
  strategyLabel: string;
  diaD: string;
  endDate: string;
  initialCash: number;
  auto: {
    totalReturnPct: number;
    maxDrawdownPct: number;
    tradeCount: number;
    finalEquity: number;
  };
  /** Trayectoria tras gate (en Auto = igual que auto). */
  gated: {
    totalReturnPct: number;
    maxDrawdownPct: number;
    tradeCount: number;
    finalEquity: number;
  };
  gate: {
    accepted: number;
    rejected: number;
  };
};

export type DiaDSessionEvidenceV1 = {
  schemaVersion: 'dia_d_session_evidence_v1';
  band: DiaDEvidenceBand;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  claims: string[];
  warnings: string[];
  metrics: {
    mode: string;
    returnPct: number;
    maxDrawdownPct: number;
    tradeCount: number;
    finalEquity: number;
    autoReturnPct: number;
    returnDeltaVsAutoPct: number;
    accepted: number;
    rejected: number;
  };
  paragraphs: [string, string, string];
  disclaimer: string;
};

function fmtPct(n: number): string {
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function resolveBand(input: DiaDSessionEvidenceInput): DiaDEvidenceBand {
  const { mode, auto, gated, gate } = input;
  if (mode !== 'auto' && gate.accepted + gate.rejected === 0 && auto.tradeCount > 0) {
    return 'incomplete';
  }
  const delta = gated.totalReturnPct - auto.totalReturnPct;
  if (gated.totalReturnPct <= -8 || delta <= -6) return 'adverse';
  if (
    gated.totalReturnPct >= 0 &&
    (delta >= -1 || gate.rejected === 0) &&
    gated.maxDrawdownPct <= Math.max(auto.maxDrawdownPct, 15) + 2
  ) {
    return 'favorable';
  }
  if (gated.totalReturnPct >= 2 && delta >= 0) return 'favorable';
  return 'mixed';
}

function buildClaims(input: DiaDSessionEvidenceInput, band: DiaDEvidenceBand): string[] {
  const delta = input.gated.totalReturnPct - input.auto.totalReturnPct;
  const claims: string[] = [
    `Modo ${input.mode} · ${input.symbol} · #1 ${input.strategyLabel}`,
    `Ventana ${input.diaD} → ${input.endDate}`,
    `Retorno sesión ${fmtPct(input.gated.totalReturnPct)} · DD ${fmtPct(input.gated.maxDrawdownPct)} · ${input.gated.tradeCount} ops`,
  ];
  if (input.mode !== 'auto') {
    claims.push(
      `Vs Auto: retorno ${fmtPct(delta)} · ops ${input.gated.tradeCount}/${input.auto.tradeCount} · gate OK/KO ${input.gate.accepted}/${input.gate.rejected}`,
    );
  } else {
    claims.push(`Trayectoria Auto (#1 congelada) · capital fin ${input.gated.finalEquity.toFixed(2)}`);
  }
  if (band === 'incomplete') {
    claims.push('Aún no hay decisiones de gate: el informe es provisional.');
  }
  return claims;
}

function buildParagraphs(
  input: DiaDSessionEvidenceInput,
  band: DiaDEvidenceBand,
): [string, string, string] {
  const delta = input.gated.totalReturnPct - input.auto.totalReturnPct;
  const p1 =
    band === 'incomplete'
      ? `Sesión DÍA D de ${input.symbol} en modo ${input.mode}: hay ${input.auto.tradeCount} señales Auto pendientes de Aceptar/Rechazar. Hasta decidir, el equity gated no refleja tu criterio.`
      : band === 'favorable'
        ? `En ${input.diaD}→${input.endDate}, la sesión ${input.mode} de ${input.symbol} cierra con retorno ${fmtPct(input.gated.totalReturnPct)} (DD ${fmtPct(input.gated.maxDrawdownPct)}). El resultado es coherente o mejor que el Auto de referencia.`
        : band === 'adverse'
          ? `La sesión ${input.mode} de ${input.symbol} termina con retorno ${fmtPct(input.gated.totalReturnPct)} y DD ${fmtPct(input.gated.maxDrawdownPct)}. Respecto al Auto (${fmtPct(input.auto.totalReturnPct)}) el delta es ${fmtPct(delta)}.`
          : `Resultado mixto en ${input.symbol}: retorno ${fmtPct(input.gated.totalReturnPct)} vs Auto ${fmtPct(input.auto.totalReturnPct)} (delta ${fmtPct(delta)}), con ${input.gated.tradeCount} ops ejecutadas.`;

  const p2 =
    input.mode === 'auto'
      ? `Modo Auto ejecuta todas las señales de #1 sin filtro humano. Úsalo como referencia; Semi/Manual miden el valor de tus vetos.`
      : input.gate.rejected > 0
        ? `Gate: ${input.gate.accepted} aceptadas y ${input.gate.rejected} rechazadas. Un buy rechazado anula su sell; el equity se reescribe solo con accepts.`
        : `Gate: ${input.gate.accepted} aceptadas y ninguna rechazo. La trayectoria se acerca al Auto; conviene contrastar DD y nº de ops.`;

  const p3 =
    band === 'incomplete'
      ? `Siguiente: recorre la película, decide cada señal y vuelve a este informe. No es consejo de inversión ni despliegue DEMO.`
      : band === 'adverse'
        ? `Revisa si los rechazos evitaron pérdidas o cortaron winners. Contrasta con el embudo ≤ D (no es el mismo informe). Sandbox ≠ DEMO live.`
        : `Guarda el aprendizaje: qué señales vetaste y por qué. El embudo ≤ D es otro informe; este solo cubre D→hoy. Sandbox ≠ DEMO live.`;

  return [p1, p2, p3];
}

export function buildDiaDSessionEvidence(
  input: DiaDSessionEvidenceInput,
): DiaDSessionEvidenceV1 {
  const band = resolveBand(input);
  const delta = input.gated.totalReturnPct - input.auto.totalReturnPct;
  const warnings: string[] = [];
  if (band === 'incomplete') {
    warnings.push('Informe incompleto: sin decisiones Semi/Manual aún.');
  }
  if (input.gated.tradeCount === 0 && input.mode === 'auto' && input.auto.tradeCount === 0) {
    warnings.push('El run Auto no generó operaciones en D→hoy.');
  }
  if (input.gated.maxDrawdownPct >= 20) {
    warnings.push('Max DD ≥ 20%: revisar tamaño y filtros.');
  }

  const confidence: DiaDSessionEvidenceV1['confidence'] =
    band === 'incomplete'
      ? 'LOW'
      : input.mode === 'auto' || input.gate.accepted + input.gate.rejected >= 3
        ? 'HIGH'
        : 'MEDIUM';

  return {
    schemaVersion: 'dia_d_session_evidence_v1',
    band,
    confidence,
    claims: buildClaims(input, band),
    warnings,
    metrics: {
      mode: input.mode,
      returnPct: input.gated.totalReturnPct,
      maxDrawdownPct: input.gated.maxDrawdownPct,
      tradeCount: input.gated.tradeCount,
      finalEquity: input.gated.finalEquity,
      autoReturnPct: input.auto.totalReturnPct,
      returnDeltaVsAutoPct: delta,
      accepted: input.gate.accepted,
      rejected: input.gate.rejected,
    },
    paragraphs: buildParagraphs(input, band),
    disclaimer:
      'Interpretación Evidence de la sesión sandbox DÍA D. No recalcula FA ni Coach. No es consejo de inversión ni escribe la DEMO live.',
  };
}

export const DIA_D_EVIDENCE_BAND_LABELS: Record<DiaDEvidenceBand, string> = {
  favorable: 'Favorable',
  mixed: 'Mixto',
  adverse: 'Adverso',
  incomplete: 'Incompleto',
};
