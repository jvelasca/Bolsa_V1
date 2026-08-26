/**
 * PaperBrokerReceipt — sello de venue paper (ADR-034 post-OI-6).
 * PaperBroker = capa paper antes de BrokerAdapter.
 * ≠ PaperOrder ≠ ExecutionRecord ≠ ExecutionPlan ≠ broker live.
 */

import type { PaperOrderV1 } from "./paper-order.js";

export type PaperBrokerVenueV1 = "PAPER";

export type PaperBrokerAdapterV1 = "paper_broker";

export type PaperBrokerFillStatusV1 = "executed" | "unknown";

export type PaperBrokerReceiptV1 = {
  venue: PaperBrokerVenueV1;
  adapter: PaperBrokerAdapterV1;
  paperOrder: PaperOrderV1;
  fillStatus: PaperBrokerFillStatusV1;
};

export const PAPER_BROKER_KEY = "paperBroker";

export const PAPER_BROKER_ADAPTER = "paper_broker" as const;

export type BuildPaperBrokerReceiptInputV1 = {
  paperOrder: PaperOrderV1;
  fillStatus: PaperBrokerFillStatusV1;
};

/** Receipt honesto tras un submit paper (CREATED o FILLED). */
export function buildPaperBrokerReceipt(
  input: BuildPaperBrokerReceiptInputV1,
): PaperBrokerReceiptV1 {
  return {
    venue: "PAPER",
    adapter: PAPER_BROKER_ADAPTER,
    paperOrder: input.paperOrder,
    fillStatus: input.fillStatus,
  };
}

/** Copy de mesa: PaperBroker ≠ broker live. */
export function paperBrokerVenueCopy(): string {
  return "Venue paper (≠ broker live)";
}
