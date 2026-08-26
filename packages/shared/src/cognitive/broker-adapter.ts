/**
 * BrokerAdapterReceipt — sello del puerto Paper | Live (ADR-034).
 * PaperBrokerAdapter = venue PAPER. Mock = LIVE not_wired.
 * XtbBrokerAdapter = LIVE vía bridge; submitted ≠ fill; filled→ledger (XL-2).
 * ≠ PaperBroker ≠ PaperOrder ≠ ExecutionRecord.
 */

export type BrokerAdapterVenueV1 = "PAPER" | "LIVE";

export type BrokerAdapterNameV1 = "paper_broker" | "mock" | "xtb";

export type BrokerAdapterFillStatusV1 =
  | "executed"
  | "unknown"
  | "not_wired"
  | "rejected"
  | "submitted";

export type BrokerAdapterReceiptV1 = {
  venue: BrokerAdapterVenueV1;
  adapter: BrokerAdapterNameV1;
  fillStatus: BrokerAdapterFillStatusV1;
};

export const BROKER_ADAPTER_KEY = "brokerAdapter";

export const BROKER_ADAPTER_PAPER = "paper_broker" as const;

export const BROKER_ADAPTER_MOCK = "mock" as const;

export const BROKER_ADAPTER_XTB = "xtb" as const;

export type BuildBrokerAdapterReceiptInputV1 = {
  venue: BrokerAdapterVenueV1;
  adapter: BrokerAdapterNameV1;
  fillStatus: BrokerAdapterFillStatusV1;
};

/** Receipt honesto tras submit por el puerto (paper / mock / xtb). */
export function buildBrokerAdapterReceipt(
  input: BuildBrokerAdapterReceiptInputV1,
): BrokerAdapterReceiptV1 {
  return {
    venue: input.venue,
    adapter: input.adapter,
    fillStatus: input.fillStatus,
  };
}

/** Copy de mesa: LIVE mock ≠ XTB; submitted ≠ fill; filled→ledger (XL-2). */
export function brokerAdapterVenueCopy(
  venue: BrokerAdapterVenueV1,
  adapter?: BrokerAdapterNameV1,
): string {
  if (venue === "LIVE" && adapter === "xtb") {
    return "XTB live — submitted ≠ fill; filled→ledger (≠ paper)";
  }
  if (venue === "LIVE") {
    return "Mock live — no envío (≠ broker live)";
  }
  return "Puerto paper (≠ broker live)";
}
