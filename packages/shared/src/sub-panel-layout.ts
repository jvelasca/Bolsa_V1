import type { ChartIndicatorInstance } from './indicators-catalog.js';
import { findIndicatorDefinition } from './indicators-catalog.js';

/** Alto fijo de la barra de título cuando el panel está oculto. */
export const COLLAPSED_SUB_PANEL_HEADER_PX = 28;

/** Alto mínimo del área de traza (sin contar la barra de título). */
export const MIN_SUB_PANEL_CHART_PX = 72;

/** Alto de la asa entre dos paneles inferiores visibles. */
export const SUB_PANEL_HANDLE_PX = 8;

/** Peso mínimo (% del reparto entre paneles visibles). */
export const MIN_SUB_PANEL_WEIGHT = 8;

const MIN_VISIBLE_PANEL_PX = COLLAPSED_SUB_PANEL_HEADER_PX + MIN_SUB_PANEL_CHART_PX;

export function isSubPanelInstance(instance: ChartIndicatorInstance): boolean {
  return findIndicatorDefinition(instance.definitionId)?.panel === 'sub';
}

export function visibleSubPanelInstances(
  instances: ChartIndicatorInstance[],
): ChartIndicatorInstance[] {
  return instances.filter((instance) => instance.visible && isSubPanelInstance(instance));
}

export function equalSubPanelWeights(instanceIds: string[]): Map<string, number> {
  if (instanceIds.length === 0) return new Map();
  const weight = 100 / instanceIds.length;
  return new Map(instanceIds.map((id) => [id, weight]));
}

export function serializeSubPanelWeights(weights: Map<string, number>): string {
  return [...weights.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([id, weight]) => `${id}:${weight.toFixed(3)}`)
    .join('|');
}

/** Reparto normalizado (suma 100) entre paneles sub visibles. */
export function resolveSubPanelWeights(
  instances: ChartIndicatorInstance[],
): Map<string, number> {
  const visible = visibleSubPanelInstances(instances);
  if (visible.length === 0) return new Map();

  const hasStored = visible.some(
    (instance) => instance.subPanelWeight != null && instance.subPanelWeight > 0,
  );
  if (!hasStored) {
    return equalSubPanelWeights(visible.map((instance) => instance.instanceId));
  }

  const sum = visible.reduce((total, instance) => total + (instance.subPanelWeight ?? 0), 0);
  if (sum <= 0) {
    return equalSubPanelWeights(visible.map((instance) => instance.instanceId));
  }

  return new Map(
    visible.map((instance) => [
      instance.instanceId,
      ((instance.subPanelWeight ?? 0) / sum) * 100,
    ]),
  );
}

export function adjustAdjacentSubPanelWeights(
  weights: Map<string, number>,
  upperId: string,
  lowerId: string,
  deltaPct: number,
): Map<string, number> | null {
  const upper = weights.get(upperId) ?? 0;
  const lower = weights.get(lowerId) ?? 0;
  const nextUpper = upper + deltaPct;
  const nextLower = lower - deltaPct;
  if (nextUpper < MIN_SUB_PANEL_WEIGHT || nextLower < MIN_SUB_PANEL_WEIGHT) {
    return null;
  }
  const next = new Map(weights);
  next.set(upperId, nextUpper);
  next.set(lowerId, nextLower);
  return next;
}

/** Iguala pesos entre todos los sub-paneles visibles (p. ej. al aplicar plantilla). */
export function rebalanceSubPanelWeights(
  instances: ChartIndicatorInstance[],
): ChartIndicatorInstance[] {
  const weights = equalSubPanelWeights(
    visibleSubPanelInstances(instances).map((instance) => instance.instanceId),
  );
  return instances.map((instance) => {
    if (!instance.visible || !isSubPanelInstance(instance)) return instance;
    return { ...instance, subPanelWeight: weights.get(instance.instanceId) };
  });
}

/** Reparte espacio al añadir un sub-panel sin resetear proporciones existentes. */
export function assignSubPanelWeightOnAdd(
  instances: ChartIndicatorInstance[],
  newInstanceId: string,
): ChartIndicatorInstance[] {
  const existingVisible = visibleSubPanelInstances(instances).filter(
    (instance) => instance.instanceId !== newInstanceId,
  );
  if (existingVisible.length === 0) {
    return instances.map((instance) =>
      instance.instanceId === newInstanceId && instance.visible && isSubPanelInstance(instance)
        ? { ...instance, subPanelWeight: 100 }
        : instance,
    );
  }

  const newWeight = 100 / (existingVisible.length + 1);
  const scale = (100 - newWeight) / 100;

  return instances.map((instance) => {
    if (instance.instanceId === newInstanceId && instance.visible && isSubPanelInstance(instance)) {
      return { ...instance, subPanelWeight: newWeight };
    }
    if (
      instance.visible &&
      isSubPanelInstance(instance) &&
      instance.instanceId !== newInstanceId
    ) {
      const current =
        instance.subPanelWeight ?? 100 / Math.max(1, existingVisible.length);
      return { ...instance, subPanelWeight: current * scale };
    }
    return instance;
  });
}

/** Reparte el peso del panel eliminado entre los que quedan. */
export function redistributeSubPanelWeightAfterRemove(
  instances: ChartIndicatorInstance[],
  removedWeight: number,
): ChartIndicatorInstance[] {
  const remaining = visibleSubPanelInstances(instances);
  if (remaining.length === 0) return instances;
  if (removedWeight <= 0) return rebalanceSubPanelWeights(instances);

  const sum = remaining.reduce((total, instance) => total + (instance.subPanelWeight ?? 0), 0);
  const basis = sum > 0 ? sum : remaining.length;
  const targetSum = basis + removedWeight;

  return instances.map((instance) => {
    if (!instance.visible || !isSubPanelInstance(instance)) return instance;
    const share = (instance.subPanelWeight ?? basis / remaining.length) / basis;
    return { ...instance, subPanelWeight: share * targetSum };
  });
}

/** Ajusta pesos al mostrar u ocultar un sub-panel. */
export function adjustSubPanelWeightsAfterVisibilityChange(
  instances: ChartIndicatorInstance[],
  toggledId: string,
  nowVisible: boolean,
): ChartIndicatorInstance[] {
  const toggled = instances.find((instance) => instance.instanceId === toggledId);
  if (!toggled || !isSubPanelInstance(toggled)) return instances;

  if (nowVisible) {
    return assignSubPanelWeightOnAdd(instances, toggledId);
  }

  const visibleBefore = visibleSubPanelInstances(instances);
  const hiddenWeight =
    toggled.subPanelWeight ??
    (visibleBefore.length > 0 ? 100 / visibleBefore.length : 100);
  const others = visibleBefore.filter((instance) => instance.instanceId !== toggledId);
  if (others.length === 0) {
    return instances.map((instance) =>
      instance.instanceId === toggledId ? { ...instance, subPanelWeight: undefined } : instance,
    );
  }

  const sum = others.reduce((total, instance) => total + (instance.subPanelWeight ?? 0), 0);
  const basis = sum > 0 ? sum : others.length;
  const targetSum = basis + hiddenWeight;

  return instances.map((instance) => {
    if (instance.instanceId === toggledId) {
      return { ...instance, subPanelWeight: undefined };
    }
    if (!instance.visible || !isSubPanelInstance(instance)) return instance;
    const share = (instance.subPanelWeight ?? basis / others.length) / basis;
    return { ...instance, subPanelWeight: share * targetSum };
  });
}

export function applySubPanelWeightsToInstances(
  instances: ChartIndicatorInstance[],
  weights: Map<string, number>,
): ChartIndicatorInstance[] {
  return instances.map((instance) => {
    const weight = weights.get(instance.instanceId);
    if (weight == null) return instance;
    return { ...instance, subPanelWeight: weight };
  });
}

export function buildSubPanelGridTemplateRows(
  instances: ChartIndicatorInstance[],
  weights: Map<string, number>,
): string {
  const rows: string[] = [];

  for (let index = 0; index < instances.length; index++) {
    const instance = instances[index];
    if (!instance) continue;
    if (!instance.visible) {
      rows.push(`${COLLAPSED_SUB_PANEL_HEADER_PX}px`);
      continue;
    }
    const weight = weights.get(instance.instanceId) ?? 1;
    rows.push(`minmax(${MIN_VISIBLE_PANEL_PX}px, ${weight}fr)`);
    const next = instances[index + 1];
    if (next?.visible) {
      rows.push(`${SUB_PANEL_HANDLE_PX}px`);
    }
  }

  return rows.join(' ');
}

/** Filas del grid en píxeles (reparto real según pesos persistidos). */
export function buildSubPanelGridTemplateRowsPx(
  instances: ChartIndicatorInstance[],
  weights: Map<string, number>,
  gridHeightPx: number,
): string {
  if (gridHeightPx <= 0) {
    return buildSubPanelGridTemplateRows(instances, weights);
  }

  const rows: string[] = [];
  const visible = instances.filter((instance) => instance?.visible);
  const hiddenCount = instances.filter((instance) => instance && !instance.visible).length;
  const handleCount = Math.max(0, visible.length - 1);
  const reserved =
    hiddenCount * COLLAPSED_SUB_PANEL_HEADER_PX + handleCount * SUB_PANEL_HANDLE_PX;
  const flexPool = Math.max(0, gridHeightPx - reserved);
  const totalWeight =
    visible.reduce((sum, instance) => sum + (weights.get(instance!.instanceId) ?? 0), 0) || 100;

  for (let index = 0; index < instances.length; index++) {
    const instance = instances[index];
    if (!instance) continue;
    if (!instance.visible) {
      rows.push(`${COLLAPSED_SUB_PANEL_HEADER_PX}px`);
      continue;
    }
    const weight = weights.get(instance.instanceId) ?? 100 / Math.max(1, visible.length);
    const rowPx = Math.max(
      MIN_VISIBLE_PANEL_PX,
      Math.round((flexPool * weight) / totalWeight),
    );
    rows.push(`${rowPx}px`);
    const next = instances[index + 1];
    if (next?.visible) {
      rows.push(`${SUB_PANEL_HANDLE_PX}px`);
    }
  }

  return rows.join(' ');
}

/** Altura mínima para mostrar todos los sub-paneles sin comprimir por debajo del mínimo. */
export function minRequiredSubPanelGridHeightPx(instances: ChartIndicatorInstance[]): number {
  let hiddenCount = 0;
  let visibleCount = 0;
  for (const instance of instances) {
    if (!instance) continue;
    if (instance.visible) visibleCount += 1;
    else hiddenCount += 1;
  }
  const handleCount = Math.max(0, visibleCount - 1);
  return (
    hiddenCount * COLLAPSED_SUB_PANEL_HEADER_PX +
    handleCount * SUB_PANEL_HANDLE_PX +
    visibleCount * MIN_VISIBLE_PANEL_PX
  );
}

export function resolveSubPanelGridLayout(
  instances: ChartIndicatorInstance[],
  weights: Map<string, number>,
  viewportHeightPx: number,
): {
  gridTemplateRows: string;
  contentHeightPx: number;
  scrollable: boolean;
} {
  if (viewportHeightPx <= 0) {
    return {
      gridTemplateRows: buildSubPanelGridTemplateRows(instances, weights),
      contentHeightPx: 0,
      scrollable: false,
    };
  }

  const minRequired = minRequiredSubPanelGridHeightPx(instances);
  const scrollable = minRequired > viewportHeightPx + 1;
  const contentHeightPx = scrollable ? minRequired : viewportHeightPx;

  return {
    gridTemplateRows: buildSubPanelGridTemplateRowsPx(instances, weights, contentHeightPx),
    contentHeightPx,
    scrollable,
  };
}

/** Altura asignable a paneles visibles (resta cabeceras ocultas y asas). */
export function subPanelFlexPoolHeightPx(
  gridHeightPx: number,
  instances: ChartIndicatorInstance[],
): number {
  if (gridHeightPx <= 0) return 0;
  const hiddenCount = instances.filter((instance) => !instance.visible).length;
  const visibleCount = instances.filter((instance) => instance.visible).length;
  const handleCount = Math.max(0, visibleCount - 1);
  const reserved =
    hiddenCount * COLLAPSED_SUB_PANEL_HEADER_PX + handleCount * SUB_PANEL_HANDLE_PX;
  return Math.max(0, gridHeightPx - reserved);
}
