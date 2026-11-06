import { describe, expect, it } from "vitest";
import type { PositionDto } from "@bolsa/shared";
import {
  portfolioMeasured,
  positionOpenHintFor,
  positionOpenHintKey,
} from "@/lib/position-open-hint";

function position(instrumentId: string, quantity: number): PositionDto {
  return {
    id: `pos-${instrumentId}`,
    instrumentId,
    symbol: instrumentId,
    name: instrumentId,
    quantity,
    avgCost: 10,
    lastPrice: 10,
    marketValue: quantity * 10,
    unrealizedPnl: 0,
    unrealizedPnlPct: 0,
  };
}

function query(
  positions: PositionDto[] | undefined,
  state: { isLoading?: boolean; isError?: boolean } = {},
) {
  return {
    data: positions === undefined ? undefined : { data: { positions } },
    isLoading: state.isLoading ?? false,
    isError: state.isError ?? false,
  };
}

/** El hint tal como lo construyen los paneles: posiciones + «medida» + id. */
function hintFor(
  q: ReturnType<typeof query>,
  instrumentId: string | null | undefined,
): boolean | null {
  return positionOpenHintFor(
    q.data?.data.positions,
    portfolioMeasured(q),
    instrumentId,
  );
}

describe("portfolioMeasured", () => {
  it("cargando, con error o sin dato ⇒ NO medido", () => {
    expect(portfolioMeasured(query(undefined, { isLoading: true }))).toBe(
      false,
    );
    expect(portfolioMeasured(query(undefined, { isError: true }))).toBe(false);
    expect(portfolioMeasured(query(undefined))).toBe(false);
    expect(portfolioMeasured(null)).toBe(false);
  });

  it("cartera leída (incluso vacía) ⇒ medido", () => {
    expect(portfolioMeasured(query([]))).toBe(true);
    expect(portfolioMeasured(query([position("AAA", 10)]))).toBe(true);
  });
});

describe("positionOpenHintFor", () => {
  it("cartera cargando ⇒ null (no medido), nunca false", () => {
    expect(hintFor(query(undefined, { isLoading: true }), "AAA")).toBeNull();
  });

  it("cartera con error ⇒ null (no medido)", () => {
    expect(hintFor(query(undefined, { isError: true }), "AAA")).toBeNull();
  });

  it("sin dato de cartera ⇒ null", () => {
    expect(hintFor(query(undefined), "AAA")).toBeNull();
  });

  it("sin id de instrumento ⇒ null", () => {
    expect(hintFor(query([position("AAA", 10)]), null)).toBeNull();
    expect(hintFor(query([position("AAA", 10)]), "  ")).toBeNull();
  });

  it("cartera leída con posición ⇒ true", () => {
    expect(hintFor(query([position("AAA", 10)]), "AAA")).toBe(true);
  });

  it("cartera leída sin la posición ⇒ false (ausencia medida)", () => {
    expect(hintFor(query([position("AAA", 10)]), "BBB")).toBe(false);
  });

  it("cantidad cero ⇒ false (no es posición abierta)", () => {
    expect(hintFor(query([position("AAA", 0)]), "AAA")).toBe(false);
  });

  it("cantidad negativa ⇒ true (corta abierta)", () => {
    expect(hintFor(query([position("AAA", -3)]), "AAA")).toBe(true);
  });

  it("posiciones sin el flag «medida» NO se leen como «sin posición»", () => {
    expect(positionOpenHintFor([position("AAA", 10)], false, "BBB")).toBeNull();
    expect(positionOpenHintFor(undefined, true, "AAA")).toBeNull();
  });
});

describe("positionOpenHintKey", () => {
  it("distingue los tres estados y la ausencia", () => {
    expect(positionOpenHintKey(true)).toBe("1");
    expect(positionOpenHintKey(false)).toBe("0");
    expect(positionOpenHintKey(null)).toBe("u");
    expect(positionOpenHintKey(undefined)).toBe("u");
  });

  it("null no colapsa con false (clave de caché del dictamen)", () => {
    expect(positionOpenHintKey(null)).not.toBe(positionOpenHintKey(false));
  });
});
