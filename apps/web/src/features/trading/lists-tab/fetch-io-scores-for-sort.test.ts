import { describe, expect, it, vi } from "vitest";
import {
  fetchIoByInstrumentIds,
  IO_SORT_COMPOSITE_CHUNK,
} from "@/features/trading/lists-tab/fetch-io-scores-for-sort";
import type { CompositeChipDto, FundamentalChipDto } from "@bolsa/shared";

function faChip(id: string, distress = false): FundamentalChipDto {
  return {
    instrumentId: id,
    scoreDisplay100: 50,
    isStale: false,
    distress,
  } as FundamentalChipDto;
}

function taChip(id: string, score: number): CompositeChipDto {
  return {
    instrumentId: id,
    scoreDisplay100: score,
    technicalDisplay100: score,
  } as CompositeChipDto;
}

describe("fetchIoByInstrumentIds", () => {
  it("uses seed cache and skips network for those ids", async () => {
    const queryFundamentals = vi.fn(async () => ({
      data: [] as FundamentalChipDto[],
    }));
    const queryComposite = vi.fn(async () => ({
      data: [] as CompositeChipDto[],
    }));

    const fa = new Map([
      ["a", { scoreDisplay100: 40, isStale: false, distress: false }],
      ["b", { scoreDisplay100: 40, isStale: false, distress: false }],
    ]);
    const ta = new Map([
      ["a", { technicalDisplay100: 80, compositeDisplay100: 80 }],
      ["b", { technicalDisplay100: 60, compositeDisplay100: 60 }],
    ]);

    const io = await fetchIoByInstrumentIds(
      ["a", "b"],
      {
        queryFundamentals,
        queryComposite,
        yieldBetweenChunks: async () => undefined,
      },
      { fa, ta },
    );

    expect(queryComposite).not.toHaveBeenCalled();
    expect(queryFundamentals).not.toHaveBeenCalled();
    expect(io.get("a")).toBe(80);
    expect(io.get("b")).toBe(60);
  });

  it("fetches composite in small sequential chunks", async () => {
    const calls: string[][] = [];
    const queryFa = vi.fn(async (instrumentIds: string[]) => ({
      data: instrumentIds.map((id) => faChip(id)),
    }));
    const queryComposite = vi.fn(async (instrumentIds: string[]) => {
      calls.push([...instrumentIds]);
      return { data: instrumentIds.map((id, i) => taChip(id, 90 - i)) };
    });

    const ids = Array.from(
      { length: IO_SORT_COMPOSITE_CHUNK * 2 + 1 },
      (_, i) => `id-${i}`,
    );
    const io = await fetchIoByInstrumentIds(ids, {
      queryFundamentals: queryFa,
      queryComposite,
      yieldBetweenChunks: async () => undefined,
    });

    expect(queryFa).toHaveBeenCalled();
    expect(calls.every((c) => c.length <= IO_SORT_COMPOSITE_CHUNK)).toBe(true);
    expect(calls.length).toBe(3);
    expect(io.get("id-0")).toBe(90);
  });

  it("falls back to 1×1 when a composite chunk throws", async () => {
    let compositeCalls = 0;
    const queryFa = vi.fn(async (instrumentIds: string[]) => ({
      data: instrumentIds.map((id) => faChip(id)),
    }));
    const queryComposite = vi.fn(async (instrumentIds: string[]) => {
      compositeCalls += 1;
      if (instrumentIds.length > 1) {
        throw new Error("Internal Server Error");
      }
      return { data: [taChip(instrumentIds[0]!, 70)] };
    });

    const io = await fetchIoByInstrumentIds(["x", "y"], {
      queryFundamentals: queryFa,
      queryComposite,
      yieldBetweenChunks: async () => undefined,
    });

    expect(compositeCalls).toBeGreaterThan(1);
    expect(io.get("x")).toBe(70);
    expect(io.get("y")).toBe(70);
  });

  it("applies FA distress floor to IO", async () => {
    const io = await fetchIoByInstrumentIds(
      ["z"],
      {
        queryFundamentals: async () => ({ data: [] }),
        queryComposite: async () => ({ data: [] }),
        yieldBetweenChunks: async () => undefined,
      },
      {
        fa: new Map([
          ["z", { scoreDisplay100: 20, isStale: false, distress: true }],
        ]),
        ta: new Map([
          ["z", { technicalDisplay100: 90, compositeDisplay100: 90 }],
        ]),
      },
    );
    expect(io.get("z")).toBe(40);
  });
});
