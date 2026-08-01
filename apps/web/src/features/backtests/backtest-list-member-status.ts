/**
 * Resumen compacto del estado de backtesting por valor (Lista → Universo).
 *
 * Una mirada: Finalistas / estrellas / Lab / pendiente / fase Lista AUTO.
 * Alimenta `BacktestUniversePicker` (modo Lista) sin abrir cada ticker.
 *
 * Datos: batch `POST /api/instrument-strategy-tops/query` + fases del tablero AUTO.
 *
 * @see docs/engineering/lists-universes-design-2026-07-30.md
 * @see docs/engineering/list-auto-ops-2026-07-29.md
 */

import type { InstrumentStrategyTopV1 } from '@bolsa/shared';
import type { ListAutoRowPhase } from '@/features/backtests/backtest-list-auto-board';
import { formatFreshnessAge } from '@/features/backtests/backtest-finalists-freshness';

export type ListMemberStatusTone = 'muted' | 'amber' | 'sky' | 'emerald' | 'violet';

export type ListMemberBacktestStatus = {
  primary: string;
  secondary?: string;
  tone: ListMemberStatusTone;
  /** Para ordenar: 0 sin TOP … 3 activo lab */
  rankScore: number;
};

function formatStars(n: number): string {
  const rounded = Math.round(n * 10) / 10;
  if (Number.isInteger(rounded)) return `${rounded}★`;
  return `${rounded}★`;
}

function formatExcess(pct: number | null | undefined): string | null {
  if (typeof pct !== 'number' || !Number.isFinite(pct)) return null;
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(1)}% vs B&H`;
}

function bestSlot(top: InstrumentStrategyTopV1) {
  if (!top.slots.length) return null;
  return [...top.slots].sort((a, b) => b.stars - a.stars || b.score - a.score)[0] ?? null;
}

function autoPhaseStatus(phase: ListAutoRowPhase): ListMemberBacktestStatus | null {
  switch (phase) {
    case 'running':
      return { primary: 'AUTO · en curso', tone: 'sky', rankScore: 5 };
    case 'saved':
      return { primary: 'AUTO · guardado', tone: 'emerald', rankScore: 4 };
    case 'omitted':
      return { primary: 'AUTO · omitido (fresco)', tone: 'violet', rankScore: 3 };
    case 'same':
      return { primary: 'AUTO · sin cambio', tone: 'muted', rankScore: 2 };
    case 'skipped':
      return { primary: 'AUTO · skip Lab', tone: 'amber', rankScore: 2 };
    case 'aborted':
      return { primary: 'AUTO · detenido', tone: 'muted', rankScore: 1 };
    case 'queued':
      return { primary: 'AUTO · en cola', tone: 'muted', rankScore: 1 };
    default:
      return null;
  }
}

/**
 * Resume el estado backtesting de un miembro de lista.
 * Si hay fase Lista AUTO, la antepone al TOP (contexto de campaña).
 */
export function summarizeListMemberBacktest(opts: {
  top?: InstrumentStrategyTopV1 | null;
  autoPhase?: ListAutoRowPhase | null;
}): ListMemberBacktestStatus {
  const auto = opts.autoPhase ? autoPhaseStatus(opts.autoPhase) : null;
  const top = opts.top ?? null;
  const slot = top ? bestSlot(top) : null;

  let topStatus: ListMemberBacktestStatus;
  if (!top || !slot || top.slots.length === 0) {
    topStatus = {
      primary: 'Sin Finalistas',
      secondary: 'pendiente de embudo',
      tone: 'muted',
      rankScore: 0,
    };
  } else {
    const evidence =
      top.evidenceLevel === 'lab_validated' ? 'Lab' : 'IS';
    const statusLabel =
      top.status === 'active' ? 'Activo' : top.status === 'semifinal' ? 'Semifinal' : 'Borrador';
    const excess = formatExcess(slot.excessReturnPct);
    const age = formatFreshnessAge(top.updatedAt);
    topStatus = {
      primary: `${formatStars(slot.stars)} ${statusLabel} · ${evidence}`,
      secondary: [excess, age !== '—' ? age : null, `${top.slots.length} slot(s)`]
        .filter(Boolean)
        .join(' · '),
      tone:
        top.status === 'active'
          ? 'emerald'
          : top.status === 'semifinal'
            ? 'sky'
            : 'amber',
      rankScore:
        top.status === 'active'
          ? top.evidenceLevel === 'lab_validated'
            ? 4
            : 3
          : top.status === 'semifinal'
            ? 2
            : 1,
    };
  }

  if (!auto || auto.primary.startsWith('AUTO · en cola')) {
    // En cola no aporta mucho si ya hay TOP; si no hay TOP, sí.
    if (auto?.primary.startsWith('AUTO · en cola') && topStatus.rankScore > 0) {
      return topStatus;
    }
    if (auto?.primary.startsWith('AUTO · en cola')) {
      return { ...auto, secondary: topStatus.primary };
    }
    return topStatus;
  }

  // Campaña viva / settle: mostrar AUTO + TOP debajo
  return {
    primary: auto.primary,
    secondary: topStatus.primary + (topStatus.secondary ? ` · ${topStatus.secondary}` : ''),
    tone: auto.tone,
    rankScore: Math.max(auto.rankScore, topStatus.rankScore),
  };
}

export function listMemberStatusClass(tone: ListMemberStatusTone): string {
  switch (tone) {
    case 'emerald':
      return 'text-emerald-700 dark:text-emerald-300';
    case 'sky':
      return 'text-sky-700 dark:text-sky-300';
    case 'amber':
      return 'text-amber-700 dark:text-amber-300';
    case 'violet':
      return 'text-violet-700 dark:text-violet-300';
    default:
      return 'text-muted-foreground';
  }
}
