/**
 * Tests — LedgerMovementRow muestra fecha/hora.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { LedgerEntryDto } from "@bolsa/shared";
import { LedgerMovementRow } from "@/features/accounts/account-detail-panel";
import { formatDateTimeCompact } from "@/lib/format";

function sample(partial?: Partial<LedgerEntryDto>): LedgerEntryDto {
  return {
    id: "led-1",
    accountId: "acc-1",
    portfolioId: null,
    type: "deposit",
    amount: 500,
    currency: "EUR",
    balanceAfter: 1500,
    instrumentId: null,
    symbol: null,
    quantity: null,
    price: null,
    referenceType: null,
    referenceId: null,
    description: null,
    executedAt: "2026-08-31T09:15:00.000Z",
    ...partial,
  };
}

describe("LedgerMovementRow", () => {
  afterEach(() => cleanup());

  it("renders compact date-time and amount", () => {
    const entry = sample();
    render(<LedgerMovementRow entry={entry} />);
    const dt = screen.getByTestId("ledger-movement-datetime").textContent ?? "";
    expect(dt).toContain(formatDateTimeCompact(entry.executedAt));
    expect(dt).toMatch(/saldo/i);
    expect(screen.getByTestId("ledger-movement-row").textContent).toMatch(
      /500|5\.?0{0,2}/,
    );
  });
});
