/**
 * Tests — tablero progreso Lista AUTO (fase / Δ Finalistas / omitido).
 */

import { describe, expect, it } from "vitest";
import {
  captureListAutoBeforeTop,
  createListAutoBoard,
  enrichListAutoBoardLabels,
  listAutoBoardProgress,
  listAutoTopFingerprint,
  markListAutoBoardAborted,
  markListAutoBoardDone,
  markListAutoBoardPaused,
  markListAutoBoardRunning,
  markListAutoBoardSettled,
  resolveListAutoChange,
} from "@/features/backtests/backtest-list-auto-board";

describe("listAutoTopFingerprint / resolveListAutoChange", () => {
  it("builds stable fingerprint from slots", () => {
    expect(
      listAutoTopFingerprint({
        status: "active",
        slots: [
          { strategyDefinitionId: "a", stars: 4 },
          { strategyDefinitionId: "b", stars: 3 },
        ],
      }),
    ).toBe("active|a:4,b:3");
    expect(listAutoTopFingerprint(null)).toBeNull();
  });

  it("saved / skip_fresh / skip_lab map change correctly", () => {
    expect(
      resolveListAutoChange({
        reason: "saved",
        beforeTopKey: null,
        afterTopKey: "x",
      }),
    ).toBe("new");
    expect(
      resolveListAutoChange({
        reason: "saved",
        beforeTopKey: "a",
        afterTopKey: "a",
      }),
    ).toBe("changed");
    expect(resolveListAutoChange({ reason: "skip_fresh" })).toBe("same");
    expect(resolveListAutoChange({ reason: "skip_lab" })).toBe("same");
  });
});

describe("enrichListAutoBoardLabels", () => {
  it("replaces truncated id placeholders with real tickers", () => {
    const board = createListAutoBoard({
      listId: "L1",
      instruments: [
        { instrumentId: "cuidabcdefghijk", symbol: "cuidabcd" },
        { instrumentId: "2", symbol: "GRF", name: "Grifols" },
      ],
    });
    const next = enrichListAutoBoardLabels(board, {
      cuidabcdefghijk: { symbol: "AAPL", name: "Apple" },
      "2": { symbol: "GRF", name: "Grifols" },
    });
    expect(next.rows[0]!.symbol).toBe("AAPL");
    expect(next.rows[0]!.name).toBe("Apple");
    expect(next.rows[1]!.symbol).toBe("GRF");
  });
});

describe("list auto board lifecycle", () => {
  it("tracks queue → running → settle including omitido fresco", () => {
    let board = createListAutoBoard({
      listId: "L1",
      instruments: [
        { instrumentId: "1", symbol: "SAN" },
        { instrumentId: "2", symbol: "GRF" },
        { instrumentId: "3", symbol: "ITX" },
      ],
    });
    expect(board.rows).toHaveLength(3);
    expect(listAutoBoardProgress(board).pct).toBe(0);

    board = markListAutoBoardRunning(board, 0);
    board = captureListAutoBeforeTop(board, 0, null);
    board = markListAutoBoardSettled(board, 0, "saved", {
      detail: "Finalistas lab_validated",
      afterTopKey: "active|x:5",
      lastSearchAt: "2026-07-29T10:00:00.000Z",
    });
    expect(board.rows[0]!.change).toBe("new");
    expect(board.rows[0]!.phase).toBe("saved");

    board = markListAutoBoardRunning(board, 1);
    board = markListAutoBoardSettled(board, 1, "skip_fresh", {
      detail: "datos igual",
      lastSearchAt: "2026-07-28T10:00:00.000Z",
    });
    expect(board.rows[1]!.phase).toBe("omitted");
    expect(board.rows[1]!.change).toBe("same");

    board = markListAutoBoardRunning(board, 2);
    board = markListAutoBoardPaused(board, true);
    expect(board.paused).toBe(true);
    board = markListAutoBoardSettled(board, 2, "skip_lab", { detail: "débil" });
    board = markListAutoBoardDone(board);
    const p = listAutoBoardProgress(board);
    expect(p.doneCount).toBe(3);
    expect(p.pct).toBe(100);
    expect(p.omittedCount).toBe(1);
    expect(p.skippedCount).toBe(1);
    expect(board.done).toBe(true);
  });

  it("abort marks remaining queued/running", () => {
    let board = createListAutoBoard({
      listId: "L1",
      instruments: [
        { instrumentId: "1", symbol: "SAN" },
        { instrumentId: "2", symbol: "GRF" },
      ],
    });
    board = markListAutoBoardRunning(board, 0);
    board = markListAutoBoardAborted(board);
    expect(board.aborted).toBe(true);
    expect(board.rows[0]!.phase).toBe("aborted");
    expect(board.rows[1]!.phase).toBe("aborted");
  });
});
