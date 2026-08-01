/**
 * Seguimiento hub Instrumentos I3 — proyección de Trackers (Radar) por valor.
 * No edita schedules/políticas (dueño = Screeners).
 *
 * @see docs/engineering/instruments-hub-2026-07-31.md
 */

import type {
  ExecutionMode,
  TrackerDefinitionDetailDto,
} from '@bolsa/shared';
import type { HubListMembership } from '@/features/instruments/instruments-hub-enrichment';

export type HubTrackerCoverage = 'pin' | 'list';

export type HubTrackerChip = {
  trackerId: string;
  name: string;
  timeframe: string;
  enabled: boolean;
  /** Manual | Auto · cierre barra | Cron */
  scheduleLabel: string;
  /** aviso | alerta | auto | live | — */
  modeShort: string;
  mode: ExecutionMode | null;
  coverage: HubTrackerCoverage;
};

export function hubExecutionModeShort(mode: string | null | undefined): string {
  switch (mode) {
    case 'inform_only':
      return 'aviso';
    case 'alert':
      return 'alerta';
    case 'paper_auto':
      return 'auto';
    case 'live_auto':
      return 'live';
    default:
      return '—';
  }
}

export function hubTrackerScheduleLabel(
  detail: TrackerDefinitionDetailDto,
): string {
  const kind = detail.definition.schedule?.kind;
  if (!kind || kind === 'manual') return 'Manual';
  if (kind === 'on_bar_close') return 'Auto · cierre barra';
  if (kind === 'cron') return 'Cron';
  return kind;
}

/** listId → instrumentIds a partir del mapa I1 invertido. */
export function listMembersFromMemberships(
  membershipsByInstrument: Map<string, HubListMembership[]>,
): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const [instrumentId, refs] of membershipsByInstrument) {
    for (const ref of refs) {
      const prev = out.get(ref.listId);
      if (prev) prev.push(instrumentId);
      else out.set(ref.listId, [instrumentId]);
    }
  }
  return out;
}

function chipFromDetail(
  detail: TrackerDefinitionDetailDto,
  coverage: HubTrackerCoverage,
  policyModeById: Map<string, ExecutionMode>,
): HubTrackerChip {
  const policyId = detail.definition.defaultExecutionPolicyId ?? null;
  const mode = policyId ? (policyModeById.get(policyId) ?? null) : null;
  return {
    trackerId: detail.id,
    name: detail.name,
    timeframe: detail.timeframe,
    enabled: detail.enabled,
    scheduleLabel: hubTrackerScheduleLabel(detail),
    modeShort: hubExecutionModeShort(mode),
    mode,
    coverage,
  };
}

/**
 * Expande trackers → instrumentos (pin universe ∪ miembros de listId).
 */
export function invertTrackersByInstrument(
  details: TrackerDefinitionDetailDto[],
  membershipsByInstrument: Map<string, HubListMembership[]>,
  policyModeById: Map<string, ExecutionMode> = new Map(),
): Map<string, HubTrackerChip[]> {
  const listMembers = listMembersFromMemberships(membershipsByInstrument);
  const map = new Map<string, HubTrackerChip[]>();

  function push(instrumentId: string, chip: HubTrackerChip) {
    const prev = map.get(instrumentId);
    if (prev) {
      if (prev.some((c) => c.trackerId === chip.trackerId)) return;
      prev.push(chip);
    } else {
      map.set(instrumentId, [chip]);
    }
  }

  for (const detail of details) {
    const universe = detail.definition.universe;
    const pins = universe.instrumentIds ?? [];
    for (const instrumentId of pins) {
      push(instrumentId, chipFromDetail(detail, 'pin', policyModeById));
    }
    const listId = universe.listId?.trim();
    if (listId) {
      for (const instrumentId of listMembers.get(listId) ?? []) {
        push(instrumentId, chipFromDetail(detail, 'list', policyModeById));
      }
    }
  }

  for (const [, chips] of map) {
    chips.sort((a, b) => {
      if (a.enabled !== b.enabled) return a.enabled ? -1 : 1;
      if (a.coverage !== b.coverage) return a.coverage === 'pin' ? -1 : 1;
      return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
    });
  }

  return map;
}

/** Hasta maxVisible chips; overflow = resto. */
export function pickTrackerChips(
  chips: HubTrackerChip[],
  maxVisible = 3,
): { visible: HubTrackerChip[]; overflow: number } {
  if (chips.length <= maxVisible) return { visible: chips, overflow: 0 };
  return {
    visible: chips.slice(0, maxVisible),
    overflow: chips.length - maxVisible,
  };
}

export function hubTrackerChipTitle(chip: HubTrackerChip): string {
  const parts = [
    chip.name,
    chip.timeframe,
    chip.scheduleLabel,
    chip.modeShort !== '—' ? chip.modeShort : 'sin política',
    chip.coverage === 'pin' ? 'pin' : 'vía lista',
    chip.enabled ? null : 'pausado',
  ].filter(Boolean);
  return parts.join(' · ');
}

/** Nombre corto para chip denso. */
export function hubTrackerChipLabel(chip: HubTrackerChip): string {
  const raw = chip.name.replace(/^Radar\s*·\s*/i, '').trim() || chip.name;
  return raw.length > 14 ? `${raw.slice(0, 12)}…` : raw;
}
