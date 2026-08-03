/**
 * Preferencias del Asistente (localStorage): qué auto-ejecutar en cada paso.
 *
 * Clave: {@link ASSISTANT_PREFS_KEY}.
 * Destacado: `fullCycleOnPlay` (default ON) — Play = embudo completo 1 valor;
 * con Universo en modo Lista → Lista AUTO (`backtest-list-auto.ts`).
 *
 * Diagrama de ramas: `assistant-funnel-flow-config.tsx`.
 *
 * @see docs/engineering/research-lifecycle.md § Embudo D
 */

import type { AssistantStepId } from '@/features/backtests/backtest-assistant-steps';

export const ASSISTANT_PREFS_KEY = 'bolsa-backtest-assistant-prefs-v1';

export type AssistantUniversePrefs = {
  selectAllGenerics: boolean;
  runCoachOnEnter: boolean;
  autoAdvanceWhenDone: boolean;
  /** Añadir Optimizadas (Lab/clones) al Universo / Probar + coach. */
  includeOptimizedStrategies: boolean;
  /** Añadir Mis estrategias (autoría) al Universo / Probar + coach. */
  includeMineStrategies: boolean;
  /**
   * En ciclo Play: genéricas ∪ Finalistas del valor actual (TOP slots).
   * Default ON — stress-test del status quo del instrumento.
   */
  includeFinalistsInBattery: boolean;
  /** Si el lote (valor/periodo/estrategias) no cambió, no re-simular. */
  reuseLoteIfUnchanged: boolean;
  /**
   * Lista AUTO / ciclo: si Finalistas active tienen stamp de frescura
   * igual a los datos actuales → omitir embudo (`skip_fresh`).
   */
  skipFreshIfUnchanged: boolean;
};

export type AssistantSemifinalPrefs = {
  optimizeTop3OnEnter: boolean;
  autoAdvanceWhenDone: boolean;
};

export type AssistantLabPrefs = {
  autoAdvanceWhenActiveTop: boolean;
};

export type AssistantFinalistsPrefs = {
  revalidateCoachOnEnter: boolean;
};

export type AssistantCoachPrefs = {
  /**
   * Peso del tramo reciente en el score ★ (default 0.42).
   * 0.30 = más equilibrado · 0.55 = prioriza régimen actual.
   */
  futureWeight: 0.3 | 0.42 | 0.55;
  /**
   * Si Coach¹ califica el TOP como débil: ¿pasar al Lab?
   * OFF (default) → skip Lab / no pisar Finalistas (Lista AUTO → next).
   * ON → Lab aunque sea débil.
   */
  labEvenIfWeak: boolean;
  /**
   * Narración / adversario LLM (CORE A).
   * ON (default): auto-pide narrate+adversary al cerrar el lote.
   * OFF: ranking ★ + dual-audit heurístico solo (sin llamadas LLM).
   */
  llmNarrate: boolean;
  /**
   * Ciclo: soft-ACK en ACK¹ / ACK final si dual-audit débil/discrepancia.
   * Default ON. `pauseIfAckNeeded` lo anula.
   */
  autoAckOnCycle: boolean;
  /**
   * Si hace falta ACK (Coach¹ o Revalidar): pausar hasta checkbox humano.
   * Default OFF.
   */
  pauseIfAckNeeded: boolean;
  /**
   * Coach¹ débil/discrepancia: exigir ACK¹ antes de Lab (o atajo semifinal).
   * Default ON.
   */
  requireAckBeforeLab: boolean;
  /**
   * Tras Coach¹ OK/ACK: guardar TOP semifinal y cerrar (sin Lab).
   * Default OFF — no predeterminado.
   */
  saveSemifinalSkipLab: boolean;
};

export type AssistantPrefs = {
  enabledSteps: Record<AssistantStepId, boolean>;
  universe: AssistantUniversePrefs;
  semifinal: AssistantSemifinalPrefs;
  lab: AssistantLabPrefs;
  finalists: AssistantFinalistsPrefs;
  coach: AssistantCoachPrefs;
  /**
   * Play lanza el ciclo completo (Probar → Coach → Lab → Revalidar → Finalistas)
   * en lugar de un solo paso. Default ON.
   */
  fullCycleOnPlay: boolean;
};

export function defaultEnabledSteps(): Record<AssistantStepId, boolean> {
  return {
    universe: true,
    semifinal: true,
    lab: true,
    finalists: true,
  };
}

export function defaultAssistantPrefs(): AssistantPrefs {
  return {
    enabledSteps: defaultEnabledSteps(),
    universe: {
      selectAllGenerics: true,
      runCoachOnEnter: true,
      autoAdvanceWhenDone: true,
      includeOptimizedStrategies: false,
      includeMineStrategies: false,
      includeFinalistsInBattery: true,
      reuseLoteIfUnchanged: true,
      skipFreshIfUnchanged: true,
    },
    semifinal: {
      optimizeTop3OnEnter: true,
      autoAdvanceWhenDone: true,
    },
    lab: {
      autoAdvanceWhenActiveTop: true,
    },
    finalists: {
      revalidateCoachOnEnter: false,
    },
    coach: {
      futureWeight: 0.42,
      labEvenIfWeak: false,
      llmNarrate: true,
      autoAckOnCycle: true,
      pauseIfAckNeeded: false,
      requireAckBeforeLab: true,
      saveSemifinalSkipLab: false,
    },
    fullCycleOnPlay: true,
  };
}

function asBool(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

function normalizeEnabledSteps(raw: unknown): Record<AssistantStepId, boolean> {
  const d = defaultEnabledSteps();
  if (!raw || typeof raw !== 'object') return d;
  const o = raw as Partial<Record<AssistantStepId, boolean>>;
  return {
    universe: asBool(o.universe, d.universe),
    semifinal: asBool(o.semifinal, d.semifinal),
    lab: asBool(o.lab, d.lab),
    finalists: asBool(o.finalists, d.finalists),
  };
}

function asFutureWeight(
  value: unknown,
  fallback: AssistantCoachPrefs['futureWeight'],
): AssistantCoachPrefs['futureWeight'] {
  const n = typeof value === 'number' ? value : Number(value);
  if (n === 0.3) return 0.3;
  if (n === 0.55) return 0.55;
  if (n === 0.42) return 0.42;
  return fallback;
}

export function normalizeAssistantPrefs(raw: unknown): AssistantPrefs {
  const d = defaultAssistantPrefs();
  if (!raw || typeof raw !== 'object') return d;
  const o = raw as Partial<AssistantPrefs>;
  return {
    enabledSteps: normalizeEnabledSteps(o.enabledSteps),
    universe: {
      selectAllGenerics: asBool(o.universe?.selectAllGenerics, d.universe.selectAllGenerics),
      runCoachOnEnter: asBool(o.universe?.runCoachOnEnter, d.universe.runCoachOnEnter),
      autoAdvanceWhenDone: asBool(o.universe?.autoAdvanceWhenDone, d.universe.autoAdvanceWhenDone),
      // Legacy: un solo check «Optimizadas y Mis» → ambos ON si estaba activo.
      includeOptimizedStrategies: asBool(
        o.universe?.includeOptimizedStrategies ??
          (o.universe as { includeMineStrategies?: boolean } | undefined)
            ?.includeMineStrategies,
        d.universe.includeOptimizedStrategies,
      ),
      includeMineStrategies: asBool(
        o.universe?.includeMineStrategies,
        d.universe.includeMineStrategies,
      ),
      includeFinalistsInBattery: asBool(
        o.universe?.includeFinalistsInBattery,
        d.universe.includeFinalistsInBattery,
      ),
      reuseLoteIfUnchanged: asBool(
        o.universe?.reuseLoteIfUnchanged,
        d.universe.reuseLoteIfUnchanged,
      ),
      skipFreshIfUnchanged: asBool(
        o.universe?.skipFreshIfUnchanged,
        d.universe.skipFreshIfUnchanged,
      ),
    },
    semifinal: {
      optimizeTop3OnEnter: asBool(
        o.semifinal?.optimizeTop3OnEnter,
        d.semifinal.optimizeTop3OnEnter,
      ),
      autoAdvanceWhenDone: asBool(
        o.semifinal?.autoAdvanceWhenDone,
        d.semifinal.autoAdvanceWhenDone,
      ),
    },
    lab: {
      autoAdvanceWhenActiveTop: asBool(
        o.lab?.autoAdvanceWhenActiveTop,
        d.lab.autoAdvanceWhenActiveTop,
      ),
    },
    finalists: {
      revalidateCoachOnEnter: asBool(
        o.finalists?.revalidateCoachOnEnter,
        d.finalists.revalidateCoachOnEnter,
      ),
    },
    coach: {
      futureWeight: asFutureWeight(o.coach?.futureWeight, d.coach.futureWeight),
      labEvenIfWeak: asBool(o.coach?.labEvenIfWeak, d.coach.labEvenIfWeak),
      llmNarrate: asBool(o.coach?.llmNarrate, d.coach.llmNarrate),
      autoAckOnCycle: asBool(o.coach?.autoAckOnCycle, d.coach.autoAckOnCycle),
      pauseIfAckNeeded: asBool(o.coach?.pauseIfAckNeeded, d.coach.pauseIfAckNeeded),
      requireAckBeforeLab: asBool(
        o.coach?.requireAckBeforeLab,
        d.coach.requireAckBeforeLab,
      ),
      saveSemifinalSkipLab: asBool(
        o.coach?.saveSemifinalSkipLab,
        d.coach.saveSemifinalSkipLab,
      ),
    },
    fullCycleOnPlay: asBool(o.fullCycleOnPlay, d.fullCycleOnPlay),
  };
}

export function loadAssistantPrefs(): AssistantPrefs {
  try {
    const raw = localStorage.getItem(ASSISTANT_PREFS_KEY);
    if (!raw) return defaultAssistantPrefs();
    return normalizeAssistantPrefs(JSON.parse(raw));
  } catch {
    return defaultAssistantPrefs();
  }
}

export function saveAssistantPrefs(prefs: AssistantPrefs): void {
  try {
    localStorage.setItem(ASSISTANT_PREFS_KEY, JSON.stringify(prefs));
  } catch {
    // ignore quota
  }
}
