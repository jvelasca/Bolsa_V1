/**
 * V1.42 F6 — Daily Desk four-bucket chrome.
 * V1.42 F7 — posición CTA encola → Confirm (no abre drawer vacío).
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DailyDeskInboxV1, PositionDto } from "@bolsa/shared";
import {
  DAILY_DESK_BUCKET_EMPTY,
  DAILY_DESK_BUCKET_LABEL,
  DAILY_DESK_BUCKET_ORDER,
  PAPER_AUTO_ARMED_EXEC_OFF,
  POSITION_BIRTH_FAILED_PHRASE,
} from "@bolsa/shared";
import { DailyDeskInbox } from "@/features/mesa/daily-desk-inbox";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";

const enqueue = vi.fn(() => "q1");
const setActive = vi.fn();

vi.mock("@/features/confirm/confirm-drawer", () => ({
  openConfirmDrawer: vi.fn(),
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1" },
    isLoading: false,
  }),
}));

vi.mock("@/stores/supervised-f3-queue-store", () => ({
  useSupervisedF3QueueStore: (
    sel: (s: { enqueue: () => string; setActive: () => void }) => unknown,
  ) => sel({ enqueue, setActive }),
}));

vi.mock("@/features/trading/demo-book-prefs", () => ({
  loadDemoBookPrefs: () => ({ mode: "semi" }),
  demoBookAllowsEnqueueConfirm: () => true,
}));

afterEach(() => {
  cleanup();
  enqueue.mockClear();
  setActive.mockClear();
  vi.mocked(openConfirmDrawer).mockClear();
});

function emptyBuckets(): DailyDeskInboxV1["buckets"] {
  return DAILY_DESK_BUCKET_ORDER.map((id) => ({
    id,
    label: DAILY_DESK_BUCKET_LABEL[id],
    items: [],
    count: 0,
    emptyLabel: DAILY_DESK_BUCKET_EMPTY[id],
  }));
}

function inbox(partial: Partial<DailyDeskInboxV1> = {}): DailyDeskInboxV1 {
  return {
    items: [],
    buckets: emptyBuckets(),
    count: 0,
    emptyLabel: "Nada requiere tu atención",
    ...partial,
  };
}

function aaplPosition(): PositionDto {
  return {
    id: "p1",
    instrumentId: "inst-aapl",
    symbol: "AAPL",
    name: "Apple",
    quantity: 10,
    avgCost: 100,
    lastPrice: 110,
    marketValue: 1100,
    unrealizedPnl: 100,
    unrealizedPnlPct: 10,
    operational: {
      status: "OPEN",
      direction: "long",
      tradePlanId: "tp-1",
      plannedEntry: 100,
      actualEntry: 100,
      initialStop: 95,
      currentStop: 95,
      target1: 110,
      target2: 120,
      exitPlan: {
        status: "TRIGGERED",
        suggestedAction: "reduce",
        suggestedQty: 5,
        primaryReason: "TARGET_1",
      },
    },
  };
}

describe("DailyDeskInbox V1.42 F6/F7", () => {
  it("renders four buckets with honest empty ⚪", () => {
    render(
      <MemoryRouter>
        <DailyDeskInbox inbox={inbox()} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("daily-desk-buckets")).toBeTruthy();
    for (const id of DAILY_DESK_BUCKET_ORDER) {
      expect(screen.getByTestId(`daily-desk-bucket-${id}`)).toBeTruthy();
      expect(screen.getByTestId(`daily-desk-empty-${id}`).textContent).toBe(
        DAILY_DESK_BUCKET_EMPTY[id],
      );
    }
    expect(
      screen.getByTestId("daily-desk-inbox").getAttribute("data-count"),
    ).toBe("0");
  });

  it("places items into the matching cube with phrase + CTA", () => {
    const items = [
      {
        id: "pending-confirm",
        kind: "pending_confirm" as const,
        bucket: "requiere_accion" as const,
        symbol: "Confirm",
        attention: "URGENT" as const,
        phrase: "1 propuesta pendiente de firma",
        reason: "1 pendiente de firma",
        ctaLabel: "Revisar y confirmar",
        ctaKind: "pending_confirm" as const,
        phaseLabel: "Propuesta",
      },
      {
        id: "entry-msft",
        kind: "entry" as const,
        bucket: "oportunidades" as const,
        symbol: "MSFT",
        attention: "ATTENTION" as const,
        phrase: "Plan armado. Disparador de entrada aún no cruzado",
        reason: "Preparada",
        ctaLabel: "Preparar operación",
        ctaKind: "view_thesis" as const,
        phaseLabel: "Preparada",
        instrumentId: "inst-msft",
      },
      {
        id: "position-p1",
        kind: "position" as const,
        bucket: "requiere_accion" as const,
        symbol: "AAPL",
        attention: "ATTENTION" as const,
        phrase: "T1 alcanzado",
        reason: "T1 alcanzado",
        ctaLabel: "Reducir",
        ctaKind: "reduce" as const,
        phaseLabel: "Posición",
        positionId: "p1",
      },
    ];
    const buckets = emptyBuckets().map((b) => {
      const bucketItems = items.filter((i) => i.bucket === b.id);
      return { ...b, items: bucketItems, count: bucketItems.length };
    });

    render(
      <MemoryRouter>
        <DailyDeskInbox
          inbox={inbox({
            count: items.length,
            items,
            buckets,
          })}
        />
      </MemoryRouter>,
    );

    expect(
      screen
        .getByTestId("daily-desk-bucket-requiere_accion")
        .getAttribute("data-count"),
    ).toBe("2");
    expect(
      screen
        .getByTestId("daily-desk-bucket-oportunidades")
        .getAttribute("data-count"),
    ).toBe("1");
    expect(screen.getByTestId("daily-desk-empty-no_operar")).toBeTruthy();
    expect(screen.getByTestId("daily-desk-cta-confirm").textContent).toBe(
      "Revisar y confirmar",
    );
    expect(screen.getByTestId("daily-desk-cta-AAPL").textContent).toBe(
      "Reducir",
    );
    expect(screen.getByTestId("daily-desk-cta-MSFT").textContent).toBe(
      "Preparar operación",
    );
    expect(screen.getByText("Preparada")).toBeTruthy();
    expect(screen.queryByText("ARMED")).toBeNull();
    expect(screen.queryByText("TRIGGERED")).toBeNull();
  });

  it("F7: Reducir encola payload y abre Confirm (no drawer vacío)", () => {
    const items = [
      {
        id: "position-p1",
        kind: "position" as const,
        bucket: "requiere_accion" as const,
        symbol: "AAPL",
        attention: "ATTENTION" as const,
        phrase: "T1 alcanzado · Mantener",
        reason: "T1",
        ctaLabel: "Reducir",
        ctaKind: "reduce" as const,
        phaseLabel: "Posición",
        positionId: "p1",
        instrumentId: "inst-aapl",
      },
    ];
    const buckets = emptyBuckets().map((b) => {
      const bucketItems = items.filter((i) => i.bucket === b.id);
      return { ...b, items: bucketItems, count: bucketItems.length };
    });

    render(
      <MemoryRouter>
        <DailyDeskInbox
          inbox={inbox({ count: 1, items, buckets })}
          positions={[aaplPosition()]}
        />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByTestId("daily-desk-cta-AAPL"));
    expect(enqueue).toHaveBeenCalledTimes(1);
    expect(setActive).toHaveBeenCalledWith("q1");
    expect(openConfirmDrawer).toHaveBeenCalledTimes(1);
  });

  it("V1.54: exception cubo rows link to operational console (Reconciliar)", () => {
    const items = [
      {
        id: "exception-birth-aapl",
        kind: "incident" as const,
        bucket: "requiere_accion" as const,
        symbol: "AAPL",
        attention: "URGENT" as const,
        phrase: POSITION_BIRTH_FAILED_PHRASE,
        reason: "position_birth_failed",
        ctaLabel: "Reconciliar",
        ctaKind: "review" as const,
        phaseLabel: null,
        instrumentId: "inst-aapl",
      },
    ];
    const buckets = emptyBuckets().map((b) => {
      const bucketItems = items.filter((i) => i.bucket === b.id);
      return { ...b, items: bucketItems, count: bucketItems.length };
    });

    render(
      <MemoryRouter>
        <DailyDeskInbox inbox={inbox({ count: 1, items, buckets })} />
      </MemoryRouter>,
    );

    const link = screen.getByTestId("daily-desk-cta-AAPL");
    expect(link.tagName).toBe("A");
    expect(link.getAttribute("href")).toBe("/operational-console");
    expect(link.textContent).toBe("Reconciliar");
  });

  it("V1.54: AUTO entry rows never show COMPRAR; paper auto is posture-only", () => {
    const items = [
      {
        id: "auto-entry-msft",
        kind: "entry" as const,
        bucket: "oportunidades" as const,
        symbol: "MSFT",
        attention: "URGENT" as const,
        phrase: "Disparo OK · AUTO armado · ejecución off",
        reason: "#1 · moderate",
        ctaLabel: PAPER_AUTO_ARMED_EXEC_OFF,
        ctaKind: "none" as const,
        phaseLabel: "Disparada",
        instrumentId: "inst-msft",
      },
    ];
    const buckets = emptyBuckets().map((b) => {
      const bucketItems = items.filter((i) => i.bucket === b.id);
      return { ...b, items: bucketItems, count: bucketItems.length };
    });

    render(
      <MemoryRouter>
        <DailyDeskInbox inbox={inbox({ count: 1, items, buckets })} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("daily-desk-cta-MSFT").textContent).toBe(
      PAPER_AUTO_ARMED_EXEC_OFF,
    );
    expect(screen.queryByText(/comprar/i)).toBeNull();
    expect(openConfirmDrawer).not.toHaveBeenCalled();
  });

  it("V1.76: denied stale item exposes data-reason-code and BLOCKED", () => {
    const items = [
      {
        id: "auto-deny-inst-msft",
        kind: "entry" as const,
        bucket: "no_operar" as const,
        symbol: "MSFT",
        attention: "BLOCKED" as const,
        phrase: "Datos obsoletos — no proponer.",
        reason: "#1 · moderate · ENTRY_STALE_DATA",
        ctaLabel: "Entradas bloqueadas",
        ctaKind: "none" as const,
        phaseLabel: null,
        instrumentId: "inst-msft",
        reasonCode: "ENTRY_STALE_DATA",
      },
    ];
    const buckets = emptyBuckets().map((b) => {
      const bucketItems = items.filter((i) => i.bucket === b.id);
      return { ...b, items: bucketItems, count: bucketItems.length };
    });

    render(
      <MemoryRouter>
        <DailyDeskInbox inbox={inbox({ count: 1, items, buckets })} />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByTestId("daily-desk-expand-no_operar"));
    const row = screen.getByTestId("daily-desk-item-auto-deny-inst-msft");
    expect(row.getAttribute("data-attention")).toBe("BLOCKED");
    expect(row.getAttribute("data-reason-code")).toBe("ENTRY_STALE_DATA");
    expect(screen.getByTestId("daily-desk-cta-MSFT").textContent).not.toMatch(
      /AUTO armado|COMPRAR/i,
    );
  });
});
