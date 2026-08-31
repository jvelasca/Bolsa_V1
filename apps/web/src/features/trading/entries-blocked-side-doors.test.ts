import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("entriesBlocked propose/buy side-doors (honesty residual)", () => {
  it("chart IA and operativa wire entriesBlocked into propose helper", () => {
    const chart = readFileSync(
      resolve(__dirname, "../charts/chart-instrument-ai-button.tsx"),
      "utf8",
    );
    expect(chart).toMatch(/useMesaEntriesBlocked/);
    expect(chart).toMatch(/entriesBlocked,/);

    const operativa = readFileSync(
      resolve(__dirname, "trading-operativa-panel.tsx"),
      "utf8",
    );
    expect(operativa).toMatch(/useMesaEntriesBlocked/);
    expect(operativa).toMatch(/entriesBlocked,/);
    expect(operativa).toMatch(/!entriesBlocked/);
    expect(operativa).toMatch(/ENTRIES_BLOCKED_CTA_LABEL/);
  });

  it("alarm inbox gates F3 on entriesBlocked", () => {
    const src = readFileSync(
      resolve(__dirname, "trading-alarm-inbox-button.tsx"),
      "utf8",
    );
    expect(src).toMatch(/useMesaEntriesBlocked/);
    expect(src).toMatch(/if \(entriesBlocked\) throw/);
    expect(src).toMatch(/disabled=\{proposePending \|\| entriesBlocked\}/);
  });

  it("order dialog and quick trade disable buy only", () => {
    const order = readFileSync(resolve(__dirname, "order-dialog.tsx"), "utf8");
    expect(order).toMatch(/useMesaEntriesBlocked/);
    expect(order).toMatch(/side === "buy" && entriesBlocked/);
    expect(order).toMatch(/disabled=\{busy \|\| entriesBlocked\}/);
    expect(order).toMatch(/ENTRIES_BLOCKED_CTA_LABEL/);

    const quick = readFileSync(
      resolve(__dirname, "../charts/chart-quick-trade-buttons.tsx"),
      "utf8",
    );
    expect(quick).toMatch(/useMesaEntriesBlocked/);
    expect(quick).toMatch(/disabled=\{entriesBlocked\}/);
    expect(quick).toMatch(/title="Venta rápida"/);
  });

  it("instrument detail gates buy on entriesBlocked", () => {
    const src = readFileSync(
      resolve(__dirname, "../instruments/instrument-detail-page.tsx"),
      "utf8",
    );
    expect(src).toMatch(/useMesaEntriesBlocked/);
    expect(src).toMatch(/side === "buy" && entriesBlocked/);
    expect(src).toMatch(/ENTRIES_BLOCKED_PROPOSE_MSG/);
  });

  it("list accordion Operar opener respects entriesBlocked", () => {
    const src = readFileSync(
      resolve(__dirname, "lists-tab/list-item-accordion.tsx"),
      "utf8",
    );
    expect(src).toMatch(/useMesaEntriesBlocked/);
    expect(src).toMatch(/disabled=\{entriesBlocked\}/);
    expect(src).toMatch(/ENTRIES_BLOCKED_PROPOSE_MSG/);
  });
});
