/**
 * ExitRouteView — ruta visual canónica Entrada → Stop / T1 / T2 (V1.40).
 * Composición: OperationalTruth + buildPositionRouteLevels.
 * Mercado / Hoy / Journal / Operaciones leen los mismos nodos y roles.
 * Stop = proteger · T1 = beneficio parcial · T2 = trailing (thin).
 */

import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import {
  buildInvestmentPositionAggregate,
  buildPositionRouteLevels,
  type PositionRouteLevelV1,
} from "./investment-position-aggregate.js";
import {
  targetProgressHint,
  type OperationalPlanViewV1,
} from "./operational-plan-view.js";
import type { OperationalTruthV1 } from "./operational-truth.js";
import type { PositionDto } from "../types.js";

export type ExitRouteNodeKindV1 =
  | "entry"
  | "stop"
  | "target1"
  | "target2"
  | "price";

export type ExitRouteNodeV1 = {
  kind: ExitRouteNodeKindV1;
  /** Etiqueta técnica (Entrada, Stop, T1, T2, Precio). */
  label: string;
  /** Rol operativo humano (Proteger, T1, T2 · trailing). */
  roleLabel: string;
  value: number;
  distanceR: number | null;
  progressHint: string | null;
  reached: boolean;
};

export type ExitRouteViewV1 = {
  instrumentId: string;
  symbol: string;
  hasRoute: boolean;
  trailingActive: boolean;
  nodes: ExitRouteNodeV1[];
};

export type BuildExitRouteViewInputV1 = {
  truth: OperationalTruthV1;
  position: PositionDto;
  study?: DecisionJournalStudyViewV1 | null;
  originStudy?: DecisionJournalStudyViewV1 | null;
};

export type ExitRouteSurfaceSnapshotV1 = {
  labels: string[];
  roleLabels: string[];
  values: number[];
  trailingActive: boolean;
};

function mapRouteLevel(
  level: PositionRouteLevelV1,
  plan: OperationalPlanViewV1,
): ExitRouteNodeV1 | null {
  switch (level.label) {
    case "ENTRADA":
      return {
        kind: "entry",
        label: "Entrada",
        roleLabel: "Entrada",
        value: level.value,
        distanceR: level.distanceR,
        progressHint: level.reached ? "✓ fill" : null,
        reached: level.reached,
      };
    case "STOP":
      return {
        kind: "stop",
        label: "Stop",
        roleLabel: "Proteger",
        value: level.value,
        distanceR: level.distanceR,
        progressHint: null,
        reached: level.reached,
      };
    case "TP1":
      return {
        kind: "target1",
        label: "T1",
        roleLabel: "T1",
        value: level.value,
        distanceR: level.distanceR,
        progressHint: targetProgressHint(
          level.touched === true,
          level.managed === true,
        ),
        reached: level.reached,
      };
    case "TP2":
      return {
        kind: "target2",
        label: "T2",
        roleLabel: plan.trailingActive ? "T2 · trailing" : "T2",
        value: level.value,
        distanceR: level.distanceR,
        progressHint: targetProgressHint(
          level.touched === true,
          level.managed === true,
        ),
        reached: level.reached,
      };
    case "PRECIO":
      return {
        kind: "price",
        label: "Precio",
        roleLabel: "Actual",
        value: level.value,
        distanceR: level.distanceR,
        progressHint: null,
        reached: false,
      };
    default:
      return null;
  }
}

export function buildExitRouteView(
  input: BuildExitRouteViewInputV1,
): ExitRouteViewV1 | null {
  const { truth, position } = input;
  if (!truth.plan.hasPlan) {
    return {
      instrumentId: truth.instrumentId,
      symbol: truth.symbol,
      hasRoute: false,
      trailingActive: truth.plan.trailingActive,
      nodes: [],
    };
  }

  const aggregate = buildInvestmentPositionAggregate({
    position,
    study: input.study,
    originStudy: input.originStudy,
  });
  const levels = buildPositionRouteLevels(aggregate);
  const nodes = levels
    .map((level) => mapRouteLevel(level, truth.plan))
    .filter((node): node is ExitRouteNodeV1 => node != null);

  return {
    instrumentId: truth.instrumentId,
    symbol: truth.symbol,
    hasRoute: nodes.length > 0,
    trailingActive: truth.plan.trailingActive,
    nodes,
  };
}

export function exitRouteSurfaceSnapshot(
  route: ExitRouteViewV1,
): ExitRouteSurfaceSnapshotV1 {
  return {
    labels: route.nodes.map((n) => n.label),
    roleLabels: route.nodes.map((n) => n.roleLabel),
    values: route.nodes.map((n) => n.value),
    trailingActive: route.trailingActive,
  };
}
