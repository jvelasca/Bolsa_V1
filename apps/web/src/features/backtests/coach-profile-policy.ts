/**
 * CORE-P — política Coach/Lab desde el perfil de la cuenta activa.
 *
 * El Asistente expone el check `labEvenIfWeak` (control explícito).
 * El perfil aporta sugerencia (`policy.allowLabIfWeak`); el check del rail manda.
 *
 * v1: stamp Finalistas, techo DD Lab, fingerprint de frescura, label rail.
 *
 * @see docs/engineering/profile-coach-lab-binding.md
 * @see docs/engineering/assistant-play-funnel-design-2026-07-29.md §3
 */

import type {
  OptimizeStrategyFamily,
  ProfileHorizon,
  RiskTolerance,
  StrategyPresetCategory,
} from "@bolsa/shared";
import type { CoachConfidence } from "@/features/backtests/coach-dual-audit";

export const COACH_PROFILE_POLICY_VERSION = "coach-profile-v1" as const;

/** Categorías Coach ★ más naturales por horizonte (AT puro). */
export function preferredCategoriesForHorizon(
  horizon: ProfileHorizon | null | undefined,
): StrategyPresetCategory[] {
  switch (horizon) {
    case "intraday":
      return ["mean_reversion", "momentum", "volatility"];
    case "swing":
      return ["trend", "momentum", "mean_reversion", "composite"];
    case "position":
      return ["trend", "composite", "momentum"];
    case "long_term":
      return ["trend", "composite"];
    default:
      return ["trend", "mean_reversion", "momentum"];
  }
}

const CATEGORY_TO_LAB_FAMILY: Partial<
  Record<StrategyPresetCategory, OptimizeStrategyFamily>
> = {
  trend: "sma_crossover",
  composite: "sma_crossover",
  mean_reversion: "rsi_mean_reversion",
  momentum: "macd_signal_cross",
  volatility: "macd_signal_cross",
};

/**
 * Familias Lab (espacio optimizable) alineadas al horizonte del perfil.
 * Orden = preferencia; no bloquea otras familias si Coach/semilla mandan.
 */
export function preferredLabFamiliesForHorizon(
  horizon: ProfileHorizon | null | undefined,
): OptimizeStrategyFamily[] {
  const out: OptimizeStrategyFamily[] = [];
  for (const cat of preferredCategoriesForHorizon(horizon)) {
    const family = CATEGORY_TO_LAB_FAMILY[cat];
    if (family && !out.includes(family)) out.push(family);
  }
  return out.length > 0
    ? out
    : ["sma_crossover", "rsi_mean_reversion", "macd_signal_cross"];
}

/**
 * Familia Lab por defecto (CORE-B v0.2 ↔ CORE-P).
 * Prioridad: semilla Coach → última adopción → horizonte del perfil → SMA.
 * No bloquea elegir otra familia a mano.
 */
export function resolveDefaultLabFamily(opts: {
  seedFamily?: OptimizeStrategyFamily | null;
  adoptionFamily?: OptimizeStrategyFamily | null;
  horizon?: ProfileHorizon | null;
}): OptimizeStrategyFamily {
  if (opts.seedFamily) return opts.seedFamily;
  if (opts.adoptionFamily) return opts.adoptionFamily;
  return preferredLabFamiliesForHorizon(opts.horizon)[0] ?? "sma_crossover";
}

const LAB_FAMILY_LABEL: Record<OptimizeStrategyFamily, string> = {
  sma_crossover: "SMA/trend",
  rsi_mean_reversion: "RSI",
  macd_signal_cross: "MACD",
};

/**
 * Factor de anchura del espacio Lab según riesgo del perfil (CORE-P soft-bias).
 * low → más estrecho · high → más ancho · resto 1.
 * No cambia ranking del Mejor ni la familia.
 */
export function labSpaceWidthFactorForRisk(
  risk: RiskTolerance | null | undefined,
): number {
  if (risk === "low") return 0.75;
  if (risk === "high") return 1.35;
  return 1;
}

/** Hint compacto para el panel Lab. */
export function formatPreferredLabFamiliesHint(
  horizon: ProfileHorizon | null | undefined,
): string {
  const families = preferredLabFamiliesForHorizon(horizon);
  const labels = families.map((f) => LAB_FAMILY_LABEL[f]).join(" · ");
  const h = horizon ?? "sin horizonte";
  return `Perfil ${h} → Lab prioriza ${labels}`;
}

/** Hint soft-bias riesgo (espacio). */
export function formatLabRiskSpaceHint(
  risk: RiskTolerance | null | undefined,
): string | null {
  const factor = labSpaceWidthFactorForRisk(risk);
  if (factor === 1) return null;
  if (factor < 1) {
    return `Riesgo ${risk}: espacio Lab más estrecho (×${factor})`;
  }
  return `Riesgo ${risk}: espacio Lab más amplio (×${factor})`;
}

/**
 * Finalistas guardados con otro perfil que el activo.
 * Aviso UI — no invalida el TOP ni pisa slots.
 */
export function activeTopProfileMismatch(opts: {
  topStatus?: string | null;
  stampedProfileId?: string | null;
  activeProfileId?: string | null;
}): { mismatch: boolean; message: string | null } {
  const status = opts.topStatus ?? null;
  if (status !== "active" && status !== "semifinal") {
    return { mismatch: false, message: null };
  }
  const stamped = opts.stampedProfileId?.trim() || null;
  const active = opts.activeProfileId?.trim() || null;
  if (!stamped || !active || stamped === active) {
    return { mismatch: false, message: null };
  }
  return {
    mismatch: true,
    message:
      "Finalistas guardados con otro perfil. Re-Play / Lab para alinear, o ignora si el cambio es deliberado.",
  };
}

export type CoachProfilePolicy = {
  /** Id del perfil declarado (auditabilidad / stamp Finalistas). */
  profileId?: string | null;
  /** Origen del perfil (UI / auditoría). */
  profileName?: string | null;
  horizon: ProfileHorizon | null;
  riskTolerance: RiskTolerance | null;
  /**
   * Si Coach¹ es débil: ¿seguir al Lab?
   * low → false · moderate → false (conservador) · high → true
   */
  allowLabIfWeak: boolean;
  /** Techo DD blando — Lab no adopta Mejor que lo rompa. */
  maxDrawdownSoftPct: number;
  /** futureWeight sugerido para el score ★. */
  suggestedFutureWeight: 0.3 | 0.42 | 0.55;
  policyVersion: typeof COACH_PROFILE_POLICY_VERSION;
};

const DEFAULT_POLICY: CoachProfilePolicy = {
  profileId: null,
  horizon: null,
  riskTolerance: null,
  allowLabIfWeak: false,
  maxDrawdownSoftPct: 25,
  suggestedFutureWeight: 0.3,
  policyVersion: COACH_PROFILE_POLICY_VERSION,
};

/**
 * Construye política desde el perfil declarado de la cuenta.
 * Sin perfil → conservador (no Lab si débil).
 */
export function resolveCoachProfilePolicy(opts: {
  profileId?: string | null;
  profileName?: string | null;
  horizon?: ProfileHorizon | null;
  riskTolerance?: RiskTolerance | null;
}): CoachProfilePolicy {
  const risk = opts.riskTolerance ?? null;
  const horizon = opts.horizon ?? null;
  const base = {
    profileId: opts.profileId ?? null,
    profileName: opts.profileName ?? null,
    horizon,
    riskTolerance: risk,
    policyVersion: COACH_PROFILE_POLICY_VERSION,
  } as const;

  if (risk === "high") {
    return {
      ...base,
      allowLabIfWeak: true,
      maxDrawdownSoftPct: 40,
      suggestedFutureWeight: horizon === "intraday" ? 0.55 : 0.42,
    };
  }

  if (risk === "moderate") {
    return {
      ...base,
      allowLabIfWeak: false,
      maxDrawdownSoftPct: 28,
      suggestedFutureWeight: 0.42,
    };
  }

  // low o ausente → conservador
  return {
    ...DEFAULT_POLICY,
    ...base,
    allowLabIfWeak: false,
    maxDrawdownSoftPct: risk === "low" ? 18 : 25,
    suggestedFutureWeight: 0.3,
  };
}

/** Segmento de fingerprint de frescura (cambio de perfil invalida skip). */
export function buildProfilePolicyFingerprintSegment(
  policy: Pick<CoachProfilePolicy, "policyVersion" | "profileId">,
): string {
  return `${policy.policyVersion}|pid:${policy.profileId ?? "none"}`;
}

/** Label compacto para el rail del Asistente. */
export function formatCoachProfileRailLabel(
  policy: CoachProfilePolicy,
): string {
  const name = policy.profileName?.trim() || "sin perfil";
  const horizon = policy.horizon ?? "—";
  const risk = policy.riskTolerance ?? "—";
  return `Perfil: ${name} · ${horizon} · riesgo ${risk}`;
}

/** |DD| ≤ techo blando del perfil (ausente techo → ok). */
export function isDrawdownWithinSoftCap(
  maxDrawdownPct: number | null | undefined,
  softCapPct: number | null | undefined,
): boolean {
  if (softCapPct == null || !Number.isFinite(softCapPct)) return true;
  if (maxDrawdownPct == null || !Number.isFinite(maxDrawdownPct)) return true;
  return Math.abs(maxDrawdownPct) <= softCapPct;
}

/**
 * ¿El Lab puede marcar Mejor como mejora adoptável?
 * Score/OOS mejor + DD dentro del techo del perfil.
 */
export function labImprovedRespectingProfileDd(opts: {
  scoreImproved: boolean;
  maxDrawdownPct: number | null | undefined;
  maxDrawdownSoftPct: number | null | undefined;
}): { improved: boolean; profileDdBlocked: boolean } {
  const profileDdBlocked =
    opts.scoreImproved &&
    !isDrawdownWithinSoftCap(opts.maxDrawdownPct, opts.maxDrawdownSoftPct);
  return {
    improved: opts.scoreImproved && !profileDdBlocked,
    profileDdBlocked,
  };
}

/** Stamp en coachFacts al guardar Finalistas / semifinal. */
export function buildCoachProfileBindingFacts(
  policy: CoachProfilePolicy,
): Record<string, unknown> {
  return {
    profileId: policy.profileId ?? null,
    policyVersion: policy.policyVersion,
    profileName: policy.profileName ?? null,
    maxDrawdownSoftPct: policy.maxDrawdownSoftPct,
    profileHorizon: policy.horizon,
    profileRiskTolerance: policy.riskTolerance,
  };
}

export type CoachLabAdvanceDecision =
  | { advance: true; reason: string }
  | { advance: false; reason: string };

/**
 * ¿El embudo debe pasar de Coach¹ a Lab?
 * Si `confidence === 'weak'`: usa `labEvenIfWeak` del Asistente si viene definido;
 * si no, `policy.allowLabIfWeak` (perfil).
 */
export function shouldAdvanceToLab(opts: {
  confidence: CoachConfidence | null | undefined;
  policy: CoachProfilePolicy;
  /** Check del Asistente — control explícito (manda sobre el perfil). */
  labEvenIfWeak?: boolean;
  recommendationCount: number;
}): CoachLabAdvanceDecision {
  if (opts.recommendationCount <= 0) {
    return {
      advance: false,
      reason: "Coach¹ sin TOP útil · no Lab · no se tocan Finalistas",
    };
  }
  const conf = opts.confidence ?? "no_auditor";
  const allowWeak =
    typeof opts.labEvenIfWeak === "boolean"
      ? opts.labEvenIfWeak
      : opts.policy.allowLabIfWeak;
  if (conf === "weak" && !allowWeak) {
    return {
      advance: false,
      reason: `Coach¹ débil · check «pasar si débil» OFF · Finalistas intactos`,
    };
  }
  return {
    advance: true,
    reason:
      conf === "weak"
        ? "Coach¹ débil · check Asistente permite Lab"
        : `Coach¹ ${conf} · avance a Lab`,
  };
}
