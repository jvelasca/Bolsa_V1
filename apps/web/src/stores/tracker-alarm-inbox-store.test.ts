import { describe, expect, it, beforeEach } from "vitest";
import type { ScanRunResultDto } from "@bolsa/shared";
import {
  itemsForAccount,
  unreadCountForAccount,
  useTrackerAlarmInboxStore,
} from "@/stores/tracker-alarm-inbox-store";

const sampleResult = (scanId: string): ScanRunResultDto =>
  ({
    scanId,
    scannedCount: 1,
    hitCount: 1,
    hits: [
      {
        instrumentId: "inst-1",
        symbol: "ACS",
        name: "ACS",
        signal: {
          id: "sig-1",
          instrumentId: "inst-1",
          timestamp: "2026-07-31T10:00:00Z",
          kind: "entry_long",
          strategyDefinitionId: "st",
          strategyVersion: 1,
          barIndex: 5,
          price: 41.2,
        },
      },
    ],
    skipped: [],
    timeframe: "1d",
    listId: "list-1",
    alarmRoute: {
      policyId: "pol-1",
      mode: "alert",
      actions: [
        {
          instrumentId: "inst-1",
          signalKind: "entry_long",
          status: "alert_dispatched",
        },
      ],
    },
  }) as ScanRunResultDto;

describe("tracker-alarm-inbox-store", () => {
  beforeEach(() => {
    useTrackerAlarmInboxStore.setState({ items: [], ingestedScanIds: [] });
  });

  it("ingests hits once per scanId for an account", () => {
    const store = useTrackerAlarmInboxStore.getState();
    expect(store.pushFromScan(sampleResult("scan-a"), "acc-demo")).toBe(1);
    expect(store.pushFromScan(sampleResult("scan-a"), "acc-demo")).toBe(0);
    const items = useTrackerAlarmInboxStore.getState().items;
    expect(itemsForAccount(items, "acc-demo")).toHaveLength(1);
    expect(unreadCountForAccount(items, "acc-demo")).toBe(1);
  });

  it("acks and scopes by account", () => {
    const store = useTrackerAlarmInboxStore.getState();
    store.pushFromScan(sampleResult("scan-b"), "acc-demo");
    const id = useTrackerAlarmInboxStore.getState().items[0]!.id;
    store.ack(id);
    expect(
      unreadCountForAccount(
        useTrackerAlarmInboxStore.getState().items,
        "acc-demo",
      ),
    ).toBe(0);
    expect(
      itemsForAccount(useTrackerAlarmInboxStore.getState().items, "acc-other"),
    ).toHaveLength(0);
  });

  it("stores strategyDefinitionId from hit signal", () => {
    useTrackerAlarmInboxStore
      .getState()
      .pushFromScan(sampleResult("scan-c"), "acc-demo");
    const item = useTrackerAlarmInboxStore.getState().items[0]!;
    expect(item.strategyDefinitionId).toBe("st");
  });

  it("rejects non-safe execution modes", () => {
    const unsafe = {
      ...sampleResult("scan-unsafe"),
      alarmRoute: {
        policyId: "pol-x",
        mode: "paper_auto",
        actions: [
          {
            instrumentId: "inst-1",
            signalKind: "entry_long",
            status: "alert_dispatched",
          },
        ],
      },
    } as ScanRunResultDto;
    expect(
      useTrackerAlarmInboxStore.getState().pushFromScan(unsafe, "acc-demo"),
    ).toBe(0);
    expect(useTrackerAlarmInboxStore.getState().items).toHaveLength(0);
  });
});
