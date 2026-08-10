/**
 * Tests — persistencia Lista AUTO (pausa + continuación tras Stop).
 */

import { describe, expect, it } from "vitest";
import {
  createListAutoCampaign,
  pauseListAutoCampaign,
} from "@/features/backtests/backtest-list-auto";
import {
  createListAutoBoard,
  markListAutoBoardPaused,
  markListAutoBoardRunning,
  markListAutoBoardSettled,
} from "@/features/backtests/backtest-list-auto-board";
import {
  boardFromContinueSnapshot,
  buildListAutoContinueSnapshot,
  buildListAutoPausedSnapshot,
  campaignFromPausedSnapshot,
  matchListAutoContinueSnapshot,
  parseListAutoPausedSnapshot,
  serializeListAutoPausedSnapshot,
} from "@/features/backtests/backtest-list-auto-persist";

describe("list auto pause persist", () => {
  it("builds snapshot only when paused between tickers", () => {
    const campaign = createListAutoCampaign({
      listId: "L1",
      instrumentIds: ["a", "b", "c"],
    });
    let board = createListAutoBoard({
      listId: "L1",
      instruments: [
        { instrumentId: "a", symbol: "SAN" },
        { instrumentId: "b", symbol: "GRF" },
        { instrumentId: "c", symbol: "ITX" },
      ],
    });
    board = markListAutoBoardRunning(board, 0);
    board = markListAutoBoardSettled(board, 0, "saved");
    pauseListAutoCampaign(campaign);
    campaign.index = 1;
    board = markListAutoBoardPaused(board, true);

    const snap = buildListAutoPausedSnapshot({
      campaign,
      board,
      freshnessMemory: new Map([["a", "fp-a"]]),
    });
    expect(snap).not.toBeNull();
    expect(snap!.campaign.index).toBe(1);
    expect(snap!.board.paused).toBe(true);
    expect(snap!.freshnessMemory?.a).toBe("fp-a");

    const roundtrip = parseListAutoPausedSnapshot(
      JSON.parse(serializeListAutoPausedSnapshot(snap!)),
    );
    expect(roundtrip?.campaign.listId).toBe("L1");
    const restored = campaignFromPausedSnapshot(roundtrip!);
    expect(restored.paused).toBe(true);
    expect(restored.index).toBe(1);
  });

  it("refuses snapshot while a row is still running", () => {
    const campaign = createListAutoCampaign({
      listId: "L1",
      instrumentIds: ["a", "b"],
    });
    pauseListAutoCampaign(campaign);
    let board = createListAutoBoard({
      listId: "L1",
      instruments: [
        { instrumentId: "a", symbol: "SAN" },
        { instrumentId: "b", symbol: "GRF" },
      ],
    });
    board = markListAutoBoardRunning(board, 0);
    board = markListAutoBoardPaused(board, true);
    expect(buildListAutoPausedSnapshot({ campaign, board })).toBeNull();
  });
});

describe("list auto continue after Stop", () => {
  it("matches same list and rebuilds board from nextIndex", () => {
    let board = createListAutoBoard({
      listId: "L1",
      instruments: [
        { instrumentId: "a", symbol: "SAN" },
        { instrumentId: "b", symbol: "GRF" },
        { instrumentId: "c", symbol: "ITX" },
      ],
    });
    board = markListAutoBoardRunning(board, 0);
    board = markListAutoBoardSettled(board, 0, "saved");
    board = markListAutoBoardRunning(board, 1);

    const snap = buildListAutoContinueSnapshot({
      listId: "L1",
      instrumentIds: ["a", "b", "c"],
      nextIndex: 1,
      board,
      freshnessMemory: { a: "fp-a" },
    });
    expect(snap).not.toBeNull();
    expect(
      matchListAutoContinueSnapshot(snap, {
        listId: "L1",
        instrumentIds: ["a", "b", "c"],
      })?.nextIndex,
    ).toBe(1);
    expect(
      matchListAutoContinueSnapshot(snap, {
        listId: "OTHER",
        instrumentIds: ["a", "b", "c"],
      }),
    ).toBeNull();

    const restored = boardFromContinueSnapshot(snap!);
    expect(restored.rows[0]!.phase).toBe("saved");
    expect(restored.rows[1]!.phase).toBe("queued");
    expect(restored.rows[2]!.phase).toBe("queued");
    expect(restored.aborted).toBe(false);
  });
});
