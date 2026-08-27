import { describe, expect, it } from "vitest";
import {
  ACCOUNT_ORIGIN_LABEL,
  DEFAULT_ACCOUNT_SEED_ID,
  accountOriginKind,
  isCloseableDevExtraAccount,
  isDailyTradingAccount,
  listCloseableDevExtraAccounts,
  type InvestmentAccountDto,
} from "./accounts.js";

function account(
  partial: Partial<InvestmentAccountDto> &
    Pick<InvestmentAccountDto, "id" | "type">,
): InvestmentAccountDto {
  return {
    userId: null,
    name: "X",
    description: null,
    status: "active",
    currency: "EUR",
    baseCurrency: "EUR",
    initialDeposit: 100000,
    leverage: 1,
    marginCallLevelPct: null,
    isDefault: false,
    settings: null,
    createdAt: "2026-08-27T00:00:00Z",
    updatedAt: "2026-08-27T00:00:00Z",
    lastActivityAt: null,
    ...partial,
  };
}

describe("account origin / OP-08", () => {
  it("classifies seed vs user demo vs lab paper", () => {
    expect(
      accountOriginKind(
        account({ id: DEFAULT_ACCOUNT_SEED_ID, type: "simulated" }),
      ),
    ).toBe("seed");
    expect(
      accountOriginKind(
        account({ id: "abc", type: "simulated", name: "Mi demo" }),
      ),
    ).toBe("user_demo");
    expect(
      accountOriginKind(
        account({
          id: "p1",
          type: "paper",
          name: "Paper · SMA",
          strategyDefinitionId: "s1",
        }),
      ),
    ).toBe("lab_paper");
    expect(ACCOUNT_ORIGIN_LABEL.seed).toMatch(/canónica/i);
  });

  it("daily trading selector excludes lab paper", () => {
    expect(
      isDailyTradingAccount(
        account({ id: DEFAULT_ACCOUNT_SEED_ID, type: "simulated" }),
      ),
    ).toBe(true);
    expect(
      isDailyTradingAccount(
        account({ id: "u1", type: "simulated", name: "Demo 2" }),
      ),
    ).toBe(true);
    expect(
      isDailyTradingAccount(
        account({ id: "p1", type: "paper", name: "Paper · X" }),
      ),
    ).toBe(false);
  });

  it("OP-08 closeable extras: seed never; open positions excluded; paper no bulk", () => {
    const seed = account({ id: DEFAULT_ACCOUNT_SEED_ID, type: "simulated" });
    const emptyDemo = account({ id: "demo-extra-1", type: "simulated" });
    const openDemo = account({ id: "demo-open", type: "simulated" });
    const paper = account({
      id: "paper-1",
      type: "paper",
      name: "Paper · Lab",
    });
    const closed = account({
      id: "demo-closed",
      type: "simulated",
      status: "closed",
    });

    expect(isCloseableDevExtraAccount(seed, 0)).toBe(false);
    expect(isCloseableDevExtraAccount(emptyDemo, 0)).toBe(true);
    expect(isCloseableDevExtraAccount(openDemo, 2)).toBe(false);
    expect(isCloseableDevExtraAccount(paper, 0)).toBe(false);
    expect(isCloseableDevExtraAccount(closed, 0)).toBe(false);

    const listed = listCloseableDevExtraAccounts(
      [seed, emptyDemo, openDemo, paper, closed],
      { [seed.id]: 0, [emptyDemo.id]: 0, [openDemo.id]: 2, [paper.id]: 0 },
    );
    expect(listed.map((a) => a.id)).toEqual(["demo-extra-1"]);
    expect(listed.some((a) => a.id === DEFAULT_ACCOUNT_SEED_ID)).toBe(false);
  });
});
