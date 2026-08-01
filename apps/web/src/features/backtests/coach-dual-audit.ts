/**
 * Doble auditoría del Coach ★ (Fase 1 + F2–F5).
 *
 * Motor A  — ranking local (shortlist).
 * Motor A2 — shadow score (excess+Sharpe+late); discrepancia fuerza atención.
 * Motor B  — auditor heurístico (siempre) + veto tipado LLM narrador (opcional).
 * Motor C  — adversario LLM tipado (allowlist; F2).
 * Gate     — publica TOP-3 sin #1 vetada; confianza Consenso/Discrepancia/Débil.
 * Red-team — challenge pack ampliado (F3): hard + soft checks.
 * Quorum   — chips A/A2/B/C + por qué #1 (F4).
 * Post-Lab — ACK soft: soft-fail no fuerza weak si #1 limpia (F5).
 *
 * @see canvases/coach-dual-ai-deep-dive.canvas.tsx
 * @see docs/engineering/research-lifecycle.md § P2
 */

import type { ExplorePresetRow } from '@/features/backtests/backtest-explore-value';
import {
  composeDeepTechnicalCoachNote,
  isStrictlyDominatedBy,
  rankTechnicalRecommendations,
  type DeepCoachContext,
  type DeepTechnicalCoachNote,
  type TechnicalRecommendation,
} from '@/features/backtests/backtest-deep-coach';

export type CoachAuditAction = 'confirm' | 'downgrade' | 'veto';

export type CoachAuditFinding = {
  strategyType: string;
  action: CoachAuditAction;
  /** Código estable para tests / UI. */
  code: string;
  reason: string;
  source: 'heuristic' | 'llm' | 'llm_c' | 'shadow' | 'red_team';
};

export type CoachConfidence = 'consensus' | 'discrepancy' | 'weak' | 'no_auditor';

export type CoachPassMode = 'initial' | 'post_lab';

export type CoachChallengeSeverity = 'hard' | 'soft';

export type CoachChallengeCheck = {
  code: string;
  passed: boolean;
  detail: string;
  severity: CoachChallengeSeverity;
};

export type CoachChallengeResult = {
  /** Sin fallos hard. */
  passed: boolean;
  /** Sin fallos soft. */
  softPassed: boolean;
  checks: CoachChallengeCheck[];
};

export type CoachQuorumChipId = 'A' | 'A2' | 'B' | 'C';

export type CoachQuorumChip = {
  id: CoachQuorumChipId;
  label: string;
  detail: string;
  tone: 'ok' | 'warn' | 'muted';
};

export type CoachQuorumSnapshot = {
  chips: CoachQuorumChip[];
  whyTop1: string;
  agree: boolean;
};

export type CoachAuditResultV1 = {
  schemaVersion: '1.1.0';
  findings: CoachAuditFinding[];
  /** Tipos vetados (unión heurística + LLM). */
  vetoedTypes: string[];
  /** Motor A vs A2 discrepan en #1. */
  shadowDisagreement: boolean;
  /** Auditor C vetó el #1 crowneado por A. */
  auditorCDisagreement: boolean;
  shadowTopType: string | null;
  primaryTopType: string | null;
  confidence: CoachConfidence;
  /** Red-team / challenge pack (F3). */
  challenge: CoachChallengeResult;
  /** Soft-fail solo aviso (post-Lab no bloquea). */
  softWeak: boolean;
  quorum: CoachQuorumSnapshot;
  whyTop1: string;
  auditorCActive: boolean;
  coachPass: CoachPassMode;
};

export type AuditedCoachBundle = {
  shortlist: TechnicalRecommendation[];
  recommendations: TechnicalRecommendation[];
  audit: CoachAuditResultV1;
};

const SHORTLIST_LIMIT = 7;
const TOP_LIMIT = 3;

function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.min(1, Math.max(0, n));
}

function isDeadCat(rec: TechnicalRecommendation): boolean {
  const early = rec.earlyReturnPct;
  const late = rec.lateReturnPct;
  const excess = rec.row.excessReturnPct;
  return (
    early != null &&
    late != null &&
    early < -20 &&
    late < 12 &&
    (excess == null || excess < 0)
  );
}

/**
 * Shadow score A2: excess + Sharpe + late (sin categoryFit / activity).
 * Si discrepa del #1 de A → shadowDisagreement.
 */
export function shadowScoreA2(
  row: ExplorePresetRow,
  lateReturnPct: number | null | undefined,
): number {
  const excess = row.excessReturnPct ?? 0;
  const sharpe = row.sharpeRatio;
  const late = lateReturnPct ?? 0;
  const excessScore = clamp01(0.5 + excess / 35);
  const sharpeScore =
    sharpe == null || !Number.isFinite(sharpe) ? 0.4 : clamp01(0.5 + sharpe / 2.5);
  const lateScore = clamp01(0.5 + late / 28);
  return Math.round((excessScore * 0.4 + lateScore * 0.4 + sharpeScore * 0.2) * 100);
}

export function pickShadowTop(
  shortlist: TechnicalRecommendation[],
): TechnicalRecommendation | null {
  if (shortlist.length === 0) return null;
  return [...shortlist].sort(
    (a, b) =>
      shadowScoreA2(b.row, b.lateReturnPct) - shadowScoreA2(a.row, a.lateReturnPct) ||
      (b.row.excessReturnPct ?? -999) - (a.row.excessReturnPct ?? -999) ||
      a.row.strategyType.localeCompare(b.row.strategyType),
  )[0]!;
}

/** Auditor heurístico B — hard gates sobre candidatas de la shortlist. */
export function auditHeuristicFindings(
  shortlist: TechnicalRecommendation[],
): CoachAuditFinding[] {
  const findings: CoachAuditFinding[] = [];
  const solid = shortlist.filter(
    (r) =>
      (r.row.excessReturnPct ?? -1) >= 0 &&
      (r.lateReturnPct == null || r.lateReturnPct >= 0) &&
      !r.usedSoftFallback,
  );

  for (const rec of shortlist) {
    const type = rec.row.strategyType;
    const late = rec.lateReturnPct;
    const excess = rec.row.excessReturnPct;
    const total = rec.row.totalReturnPct;

    if (rec.usedSoftFallback) {
      findings.push({
        strategyType: type,
        action: 'veto',
        code: 'no_period_returns',
        reason: 'Sin tercios de equity fijados: no puede ser #1 ni TOP fiable.',
        source: 'heuristic',
      });
      continue;
    }

    if (late != null && late < 0 && (excess == null || excess < 0)) {
      findings.push({
        strategyType: type,
        action: 'veto',
        code: 'late_and_excess_negative',
        reason: 'Tramo reciente negativo y no bate buy & hold.',
        source: 'heuristic',
      });
      continue;
    }

    if (isDeadCat(rec)) {
      findings.push({
        strategyType: type,
        action: 'veto',
        code: 'dead_cat_bounce',
        reason: 'Rebote tras desplome temprano sin edge vs B&H.',
        source: 'heuristic',
      });
      continue;
    }

    if (excess != null && excess < -8) {
      findings.push({
        strategyType: type,
        action: 'veto',
        code: 'loses_buy_hold',
        reason: `vs B&H ${excess.toFixed(1)}% — por debajo del suelo del auditor.`,
        source: 'heuristic',
      });
      continue;
    }

    if (total != null && total < 0 && (excess == null || excess < 0)) {
      findings.push({
        strategyType: type,
        action: 'veto',
        code: 'negative_total',
        reason: 'Retorno total negativo y sin exceso vs B&H.',
        source: 'heuristic',
      });
      continue;
    }

    if (solid.length > 0 && (excess == null || excess < 0 || (total ?? 0) < 0)) {
      const dominator = solid.find((other) => other !== rec && isStrictlyDominatedBy(rec, other));
      if (dominator) {
        findings.push({
          strategyType: type,
          action: 'veto',
          code: 'dominated',
          reason: `Dominada por «${dominator.row.label}» en reciente / vs B&H / total.`,
          source: 'heuristic',
        });
        continue;
      }
    }

    if (rec.qualityFlagged) {
      findings.push({
        strategyType: type,
        action: 'downgrade',
        code: 'quality_flagged',
        reason: 'Marcada por suelos de calidad del ranking A — no preferir como #1.',
        source: 'heuristic',
      });
      continue;
    }

    if (excess != null && excess >= 0 && (late == null || late >= 0)) {
      findings.push({
        strategyType: type,
        action: 'confirm',
        code: 'ok',
        reason: 'Pasa gates duros del auditor heurístico.',
        source: 'heuristic',
      });
    } else {
      findings.push({
        strategyType: type,
        action: 'downgrade',
        code: 'soft_edge',
        reason: 'Edge débil o reciente flojo — usable en TOP solo si no hay mejores.',
        source: 'heuristic',
      });
    }
  }

  return findings;
}

/** Parse vetoes tipados del payload LLM (solo veto/downgrade). */
export function auditFindingsFromLlmPayload(
  payload: {
    audit?: {
      findings?: Array<{
        strategyType?: string;
        action?: string;
        code?: string;
        reason?: string;
      }>;
    };
  } | null | undefined,
  source: 'llm' | 'llm_c' = 'llm',
): CoachAuditFinding[] {
  const raw = payload?.audit?.findings;
  if (!Array.isArray(raw)) return [];
  const out: CoachAuditFinding[] = [];
  for (const f of raw) {
    if (!f?.strategyType || typeof f.strategyType !== 'string') continue;
    const action =
      f.action === 'veto' || f.action === 'downgrade' || f.action === 'confirm'
        ? f.action
        : null;
    if (!action || action === 'confirm') continue;
    out.push({
      strategyType: f.strategyType,
      action,
      code: typeof f.code === 'string' ? f.code : source === 'llm_c' ? 'llm_c_audit' : 'llm_audit',
      reason:
        typeof f.reason === 'string'
          ? f.reason
          : source === 'llm_c'
            ? 'Veto del adversario C.'
            : 'Veto del auditor IA.',
      source,
    });
  }
  return out;
}

/** Descarta findings LLM fuera del lote (anti-alucinación). */
export function filterLlmFindingsToAllowlist(
  findings: CoachAuditFinding[],
  allowedStrategyTypes: Iterable<string>,
): CoachAuditFinding[] {
  const allow = new Set(allowedStrategyTypes);
  return findings.filter((f) => allow.has(f.strategyType));
}

export function mergeAuditFindings(
  heuristic: CoachAuditFinding[],
  llm: CoachAuditFinding[],
): CoachAuditFinding[] {
  const byType = new Map<string, CoachAuditFinding>();
  for (const f of heuristic) {
    const prev = byType.get(f.strategyType);
    if (!prev || severity(f.action) > severity(prev.action)) {
      byType.set(f.strategyType, f);
    }
  }
  for (const f of llm) {
    const prev = byType.get(f.strategyType);
    if (!prev || severity(f.action) > severity(prev.action)) {
      byType.set(f.strategyType, f);
    }
  }
  return [...byType.values()];
}

function severity(action: CoachAuditAction): number {
  if (action === 'veto') return 2;
  if (action === 'downgrade') return 1;
  return 0;
}

/**
 * Red-team / challenge pack (F3).
 * Hard fail → TOP débil. Soft fail → aviso (post-Lab no fuerza ACK).
 */
export function runCoachChallengePack(
  recommendations: TechnicalRecommendation[],
): CoachChallengeResult {
  const checks: CoachChallengeCheck[] = [];
  if (recommendations.length === 0) {
    return {
      passed: false,
      softPassed: false,
      checks: [
        {
          code: 'empty_top',
          passed: false,
          detail: 'Sin candidatas en el lote (batería vacía).',
          severity: 'hard',
        },
      ],
    };
  }

  const top = recommendations[0]!;
  const second = recommendations[1];

  checks.push({
    code: 'top_beats_bh',
    passed: (top.row.excessReturnPct ?? -1) >= 0,
    detail:
      top.row.excessReturnPct == null
        ? 'Sin excess vs B&H en #1.'
        : `#1 vs B&H ${top.row.excessReturnPct.toFixed(1)}%.`,
    severity: 'hard',
  });

  checks.push({
    code: 'top_late_nonneg',
    passed: top.lateReturnPct == null || top.lateReturnPct >= 0,
    detail:
      top.lateReturnPct == null
        ? 'Sin tramo reciente en #1.'
        : `#1 reciente ${top.lateReturnPct.toFixed(1)}%.`,
    severity: 'hard',
  });

  checks.push({
    code: 'top_has_thirds',
    passed: !top.usedSoftFallback,
    detail: top.usedSoftFallback
      ? '#1 sin tercios fijados (fallback).'
      : '#1 con tercios de equity.',
    severity: 'hard',
  });

  checks.push({
    code: 'dead_cat_top',
    passed: !isDeadCat(top),
    detail: isDeadCat(top)
      ? '#1 parece dead-cat (desplome temprano + rebote flojo).'
      : '#1 sin patrón dead-cat.',
    severity: 'hard',
  });

  const dominatedBySecond =
    second != null &&
    (top.row.excessReturnPct ?? -1) >= 0 &&
    isStrictlyDominatedBy(top, second);
  checks.push({
    code: 'top_not_dominated',
    passed: !dominatedBySecond,
    detail: dominatedBySecond
      ? `#1 dominada por #2 «${second!.row.label}».`
      : '#1 no dominada por #2.',
    severity: 'hard',
  });

  const minOps = recommendations.every((r) => (r.row.tradeCount ?? 0) >= 3);
  checks.push({
    code: 'min_ops',
    passed: minOps,
    detail: minOps
      ? 'Todas las del TOP tienen ≥3 ops.'
      : 'Alguna del TOP tiene <3 ops (muestra débil).',
    severity: 'soft',
  });

  const fragile =
    (top.row.totalReturnPct ?? 0) > 20 &&
    top.lateReturnPct != null &&
    top.lateReturnPct < 2;
  checks.push({
    code: 'not_fragile_total',
    passed: !fragile,
    detail: fragile
      ? 'Total alto con reciente casi plano — frágil a régimen actual.'
      : 'Sin patrón frágil total≫reciente en #1.',
    severity: 'soft',
  });

  const categories = new Set(recommendations.map((r) => r.row.category));
  const cloneFamily = recommendations.length >= 3 && categories.size === 1;
  checks.push({
    code: 'family_diversity',
    passed: !cloneFamily,
    detail: cloneFamily
      ? `TOP-3 misma familia «${recommendations[0]!.row.categoryLabel}» — clones.`
      : 'Diversidad de familia OK (o TOP <3).',
    severity: 'soft',
  });

  const sharpe = top.row.sharpeRatio;
  const ops = top.row.tradeCount ?? 0;
  const sharpeOpsInsane =
    sharpe != null && Number.isFinite(sharpe) && sharpe > 2.5 && ops > 0 && ops < 5;
  checks.push({
    code: 'sharpe_ops_sane',
    passed: !sharpeOpsInsane,
    detail: sharpeOpsInsane
      ? `Sharpe ${sharpe!.toFixed(2)} con solo ${ops} ops — sospechoso.`
      : 'Sharpe/ops de #1 coherentes.',
    severity: 'soft',
  });

  const hardFail = checks.some((c) => !c.passed && c.severity === 'hard');
  const softFail = checks.some((c) => !c.passed && c.severity === 'soft');

  return { passed: !hardFail, softPassed: !softFail, checks };
}

/**
 * Gate TOP-N: prioriza no vetadas; si faltan, rellena con vetadas (último recurso).
 * Siempre intenta devolver hasta `limit` candidatas si hay shortlist.
 */
export function applyAuditGate(
  shortlist: TechnicalRecommendation[],
  findings: CoachAuditFinding[],
  limit = TOP_LIMIT,
): TechnicalRecommendation[] {
  if (shortlist.length === 0) return [];

  const veto = new Set(
    findings.filter((f) => f.action === 'veto').map((f) => f.strategyType),
  );
  const downgrade = new Set(
    findings.filter((f) => f.action === 'downgrade').map((f) => f.strategyType),
  );

  const sortFn = (a: TechnicalRecommendation, b: TechnicalRecommendation) => {
    const aVeto = veto.has(a.row.strategyType);
    const bVeto = veto.has(b.row.strategyType);
    if (aVeto !== bVeto) return aVeto ? 1 : -1;
    const aDown = downgrade.has(a.row.strategyType);
    const bDown = downgrade.has(b.row.strategyType);
    if (aDown !== bDown) return aDown ? 1 : -1;
    return (
      b.score - a.score ||
      (b.lateReturnPct ?? -999) - (a.lateReturnPct ?? -999) ||
      (b.row.excessReturnPct ?? -999) - (a.row.excessReturnPct ?? -999)
    );
  };

  const preferred = [...shortlist.filter((r) => !veto.has(r.row.strategyType))].sort(sortFn);
  const fallback = [...shortlist.filter((r) => veto.has(r.row.strategyType))].sort(sortFn);
  const pool = [...preferred, ...fallback];

  const picked: TechnicalRecommendation[] = [];
  const usedCat = new Set<string>();
  const used = new Set<string>();

  const identityOf = (item: TechnicalRecommendation) =>
    item.row.strategyDefinitionId
      ? `id:${item.row.strategyDefinitionId}`
      : `type:${item.row.strategyType}`;

  for (const item of preferred) {
    if (picked.length >= limit) break;
    if (usedCat.has(item.row.category) && preferred.length > limit) continue;
    if (used.has(identityOf(item))) continue;
    picked.push(item);
    used.add(identityOf(item));
    usedCat.add(item.row.category);
  }
  for (const item of pool) {
    if (picked.length >= limit) break;
    if (used.has(identityOf(item))) continue;
    picked.push(item);
    used.add(identityOf(item));
  }

  return picked.map((item, i) => {
    const wasVetoed = veto.has(item.row.strategyType);
    return {
      ...item,
      rank: i + 1,
      qualityFlagged: Boolean(item.qualityFlagged || wasVetoed),
      stars: wasVetoed ? ((Math.min(item.stars, 2) as 1 | 2 | 3 | 4 | 5)) : item.stars,
      reasons: wasVetoed
        ? [
            ...item.reasons,
            'Incluida en TOP como último recurso (auditor B la había vetado) — ★ bajas / revisar.',
          ]
        : item.reasons,
    };
  });
}

export function buildWhyTop1(
  top: TechnicalRecommendation | undefined,
  opts?: { vetoFallback?: boolean },
): string {
  if (!top) return 'Sin #1 en el lote.';
  const bits = [
    top.row.label,
    top.lateReturnPct != null ? `reciente ${top.lateReturnPct.toFixed(1)}%` : null,
    top.row.excessReturnPct != null ? `vs B&H ${top.row.excessReturnPct >= 0 ? '+' : ''}${top.row.excessReturnPct.toFixed(1)}%` : null,
    `★${top.stars}`,
  ].filter(Boolean);
  if (opts?.vetoFallback) bits.push('último recurso (veto suavizado)');
  return bits.join(' · ');
}

export function buildCoachQuorum(opts: {
  primaryTopType: string | null;
  shadowTopType: string | null;
  shadowDisagreement: boolean;
  findings: CoachAuditFinding[];
  challenge: CoachChallengeResult;
  auditorCActive: boolean;
  auditorCDisagreement: boolean;
  whyTop1: string;
  recommendations: TechnicalRecommendation[];
}): CoachQuorumSnapshot {
  const topType = opts.recommendations[0]?.row.strategyType ?? opts.primaryTopType;
  const vetoes = opts.findings.filter((f) => f.action === 'veto');
  const bVetoes = vetoes.filter((f) => f.source === 'heuristic' || f.source === 'llm').length;
  const cVetoes = vetoes.filter((f) => f.source === 'llm_c').length;
  const hardOk = opts.challenge.passed;

  const chips: CoachQuorumChip[] = [
    {
      id: 'A',
      label: 'A',
      detail: opts.primaryTopType ? `#1 ${opts.primaryTopType}` : 'sin shortlist',
      tone: opts.primaryTopType ? 'ok' : 'muted',
    },
    {
      id: 'A2',
      label: 'A2',
      detail: opts.shadowTopType
        ? opts.shadowDisagreement
          ? `≠ A → ${opts.shadowTopType}`
          : `= A`
        : 'n/d',
      tone: opts.shadowDisagreement ? 'warn' : opts.shadowTopType ? 'ok' : 'muted',
    },
    {
      id: 'B',
      label: 'B',
      detail: hardOk
        ? bVetoes > 0
          ? `${bVetoes} veto(s) · gate OK`
          : 'gates OK'
        : 'challenge hard fail',
      tone: hardOk ? 'ok' : 'warn',
    },
    {
      id: 'C',
      label: 'C',
      detail: opts.auditorCActive
        ? opts.auditorCDisagreement
          ? `vetó crowning A`
          : cVetoes > 0
            ? `${cVetoes} veto(s)`
            : 'sin veto crowning'
        : 'sin LLM',
      tone: !opts.auditorCActive
        ? 'muted'
        : opts.auditorCDisagreement
          ? 'warn'
          : 'ok',
    },
  ];

  const agree =
    !opts.shadowDisagreement &&
    !opts.auditorCDisagreement &&
    hardOk &&
    Boolean(topType);

  return { chips, whyTop1: opts.whyTop1, agree };
}

function resolveConfidence(opts: {
  coachPass: CoachPassMode;
  shadowDisagreement: boolean;
  auditorCDisagreement: boolean;
  recommendations: TechnicalRecommendation[];
  challenge: CoachChallengeResult;
  /** #1 del TOP gateado está vetada (relleno). */
  top1Vetoed: boolean;
  /** Algún slot del TOP es vetado relleno. */
  usedVetoFallback: boolean;
}): { confidence: CoachConfidence; softWeak: boolean } {
  if (opts.recommendations.length === 0) {
    return { confidence: 'no_auditor', softWeak: false };
  }

  const softWeak = !opts.challenge.softPassed;
  const hardWeak =
    !opts.challenge.passed ||
    opts.top1Vetoed ||
    (opts.coachPass === 'initial' && opts.usedVetoFallback);

  // F5: post-Lab — soft-fail y slots #2/#3 vetados no fuerzan weak si #1 limpia.
  if (opts.coachPass === 'post_lab') {
    if (hardWeak) return { confidence: 'weak', softWeak };
    if (opts.shadowDisagreement || opts.auditorCDisagreement) {
      return { confidence: 'discrepancy', softWeak };
    }
    return { confidence: 'consensus', softWeak };
  }

  if (hardWeak) return { confidence: 'weak', softWeak };
  if (opts.shadowDisagreement || opts.auditorCDisagreement) {
    return { confidence: 'discrepancy', softWeak };
  }
  // Semifinal: soft-fail también pide atención vía weak si no hay hard.
  if (softWeak) return { confidence: 'weak', softWeak };
  return { confidence: 'consensus', softWeak: false };
}

/**
 * Pipeline completo: shortlist A → audit B(+C) → gate TOP-3 → red-team → quorum.
 */
export function runCoachDualAudit(opts: {
  rows: ExplorePresetRow[];
  ctx: DeepCoachContext;
  llmFindings?: CoachAuditFinding[];
  adversaryFindings?: CoachAuditFinding[];
  shortlistLimit?: number;
  topLimit?: number;
  coachPass?: CoachPassMode;
}): AuditedCoachBundle {
  const shortlistLimit = opts.shortlistLimit ?? SHORTLIST_LIMIT;
  const topLimit = opts.topLimit ?? TOP_LIMIT;
  const coachPass: CoachPassMode =
    opts.coachPass ??
    (opts.ctx.evidenceLevel === 'lab_validated' ? 'post_lab' : 'initial');

  const shortlist = rankTechnicalRecommendations(opts.rows, opts.ctx, {
    limit: shortlistLimit,
    diversifyCategories: true,
  });

  const allowTypes = new Set(opts.rows.map((r) => r.strategyType));
  for (const r of shortlist) allowTypes.add(r.row.strategyType);

  const shadowTop = pickShadowTop(shortlist);
  const primaryTop = shortlist[0] ?? null;
  const shadowDisagreement = Boolean(
    primaryTop &&
      shadowTop &&
      primaryTop.row.strategyType !== shadowTop.row.strategyType,
  );

  const heuristic = auditHeuristicFindings(shortlist);
  if (shadowDisagreement && shadowTop && primaryTop) {
    heuristic.push({
      strategyType: primaryTop.row.strategyType,
      action: 'downgrade',
      code: 'shadow_disagreement',
      reason: `Shadow A2 preferiría «${shadowTop.row.label}» — no crowning ciego de A.`,
      source: 'shadow',
    });
  }

  const llmNarrate = filterLlmFindingsToAllowlist(opts.llmFindings ?? [], allowTypes);
  const llmC = filterLlmFindingsToAllowlist(opts.adversaryFindings ?? [], allowTypes);
  const auditorCActive = llmC.length > 0 || (opts.adversaryFindings?.length ?? 0) > 0;
  // Si el adversario respondió vacío tras filtro pero hubo llamada, marcar active vía flag externo:
  // preferimos auditorCActive si se pasaron findings (aunque vacíos tras filter) — ver opts flag below.
  const auditorCCalled = opts.adversaryFindings !== undefined;

  const auditorCDisagreement = Boolean(
    primaryTop &&
      llmC.some((f) => f.action === 'veto' && f.strategyType === primaryTop.row.strategyType),
  );

  const findings = mergeAuditFindings(heuristic, [...llmNarrate, ...llmC]);
  const recommendations = applyAuditGate(shortlist, findings, topLimit);
  const challenge = runCoachChallengePack(recommendations);
  const vetoedTypes = [
    ...new Set(findings.filter((f) => f.action === 'veto').map((f) => f.strategyType)),
  ];
  const usedVetoFallback = recommendations.some((r) =>
    vetoedTypes.includes(r.row.strategyType),
  );
  const top1Vetoed = Boolean(
    recommendations[0] && vetoedTypes.includes(recommendations[0].row.strategyType),
  );

  const whyTop1 = buildWhyTop1(recommendations[0], { vetoFallback: top1Vetoed });
  const { confidence, softWeak } = resolveConfidence({
    coachPass,
    shadowDisagreement,
    auditorCDisagreement,
    recommendations,
    challenge,
    top1Vetoed,
    usedVetoFallback,
  });

  const cActive = auditorCCalled || auditorCActive;
  const quorum = buildCoachQuorum({
    primaryTopType: primaryTop?.row.strategyType ?? null,
    shadowTopType: shadowTop?.row.strategyType ?? null,
    shadowDisagreement,
    findings,
    challenge,
    auditorCActive: cActive,
    auditorCDisagreement,
    whyTop1,
    recommendations,
  });

  return {
    shortlist,
    recommendations,
    audit: {
      schemaVersion: '1.1.0',
      findings,
      vetoedTypes,
      shadowDisagreement,
      auditorCDisagreement,
      shadowTopType: shadowTop?.row.strategyType ?? null,
      primaryTopType: primaryTop?.row.strategyType ?? null,
      confidence,
      challenge,
      softWeak,
      quorum,
      whyTop1,
      auditorCActive: cActive,
      coachPass,
    },
  };
}

export function confidenceLabel(c: CoachConfidence): string {
  switch (c) {
    case 'consensus':
      return 'Consenso';
    case 'discrepancy':
      return 'Discrepancia';
    case 'weak':
      return 'Débil';
    case 'no_auditor':
      return 'Sin lote';
    default:
      return c;
  }
}

/** Lectura ligera del dualAudit persistido en Finalistas (CORE A readback). */
export type PriorCoachAuditHint = {
  confidence: CoachConfidence;
  softWeak: boolean;
  coachPass?: string | null;
};

export function readPriorCoachAuditHint(
  coachFacts: Record<string, unknown> | null | undefined,
): PriorCoachAuditHint | null {
  if (!coachFacts || typeof coachFacts !== 'object') return null;
  const dual = coachFacts.dualAudit;
  if (!dual || typeof dual !== 'object') return null;
  const conf = (dual as { confidence?: unknown }).confidence;
  if (
    conf !== 'consensus' &&
    conf !== 'discrepancy' &&
    conf !== 'weak' &&
    conf !== 'no_auditor'
  ) {
    return null;
  }
  return {
    confidence: conf,
    softWeak: Boolean((dual as { softWeak?: unknown }).softWeak),
    coachPass:
      typeof coachFacts.coachPass === 'string' ? coachFacts.coachPass : null,
  };
}

/** Nota coach con doble auditoría (entry point UI). */
export function buildAuditedDeepTechnicalCoachNote(
  rows: ExplorePresetRow[],
  ctx: DeepCoachContext,
  llmFindings?: CoachAuditFinding[],
  opts?: {
    adversaryFindings?: CoachAuditFinding[];
    coachPass?: CoachPassMode;
  },
): DeepTechnicalCoachNote {
  const audited = runCoachDualAudit({
    rows,
    ctx,
    llmFindings,
    adversaryFindings: opts?.adversaryFindings,
    coachPass: opts?.coachPass,
  });
  return composeDeepTechnicalCoachNote({
    rows,
    ctx,
    recommendations: audited.recommendations,
    audit: audited.audit,
  });
}
