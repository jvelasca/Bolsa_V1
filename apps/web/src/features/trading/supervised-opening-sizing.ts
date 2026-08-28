/**
 * V1.25 — alinear qty de propose con TradePlan TRIGGERED (sin % caja como SoT).
 */

import type { SupervisedProposePayload } from "@/stores/supervised-f3-queue-store";
import { applySupervisedOpeningQuantity } from "@bolsa/shared";

export function finalizeSupervisedProposePayload(
  payload: SupervisedProposePayload,
): SupervisedProposePayload {
  return applySupervisedOpeningQuantity(payload);
}
