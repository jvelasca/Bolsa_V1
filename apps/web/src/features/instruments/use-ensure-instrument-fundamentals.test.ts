/**
 * Guarda de forma del wire FA — `FundamentalCardDto` declara `facts`/`derived`/`metadata`
 * REQUERIDOS. Una respuesta que no los traiga se declara **ausencia** (`null`), no una tarjeta a
 * medio formar.
 *
 * Regresión que fija: el fallback genérico `{ data: [] }` de los mocks E2E hacía *truthy* al
 * `card` (`![] === false`), así que pasaba el `if (!card)` del panel y reventaba en
 * `card.facts.forwardPe` → «Cannot read properties of undefined (reading 'forwardPe')», blanqueando
 * la página entera (y con ella el verificador DÍA-D).
 */

import { describe, expect, it } from "vitest";
import type { FundamentalCardDto } from "@bolsa/shared";
import {
  fundamentalsSnapshotMissing,
  isFundamentalCardDto,
} from "./use-ensure-instrument-fundamentals";

const VALID = {
  schemaVersion: "fundamental_card_v1",
  instrumentId: "inst-1",
  ticker: "AAPL",
  scoreDisplay100: 62,
  distress: false,
  facts: { forwardPe: 28.4, trailingPe: 30.1, sector: "Technology" },
  derived: { altmanZ: 5.2, piotroski: 7 },
  metadata: { fetchedAt: "2026-10-01T00:00:00.000Z", confidence: "HIGH" },
} as unknown as FundamentalCardDto;

describe("isFundamentalCardDto", () => {
  it("acepta una tarjeta que trae facts/derived/metadata", () => {
    expect(isFundamentalCardDto(VALID)).toBe(true);
  });

  it("rechaza las formas que rompían el render (lista, null, objeto suelto, parcial)", () => {
    const bad = [
      [],
      [{}],
      null,
      undefined,
      "inst-1",
      7,
      {},
      { facts: {} },
      { facts: {}, derived: {} },
      { facts: {}, metadata: {} },
      { derived: {}, metadata: {} },
      { facts: [], derived: {}, metadata: {} },
    ];
    for (const value of bad) {
      expect(isFundamentalCardDto(value)).toBe(false);
    }
  });
});

describe("fundamentalsSnapshotMissing", () => {
  it("declara hueco ante un payload malformado (nunca lo trata como medición)", () => {
    expect(
      fundamentalsSnapshotMissing([] as unknown as FundamentalCardDto),
    ).toBe(true);
    expect(
      fundamentalsSnapshotMissing({
        facts: {},
      } as unknown as FundamentalCardDto),
    ).toBe(true);
  });

  it("una tarjeta con fetchedAt y un fact core no declara hueco", () => {
    expect(fundamentalsSnapshotMissing(VALID)).toBe(false);
  });

  it("una tarjeta as-of bloqueada no se declara hueco (respuesta válida sin auto-refresh)", () => {
    const blocked = {
      ...VALID,
      metadata: { pointInTime: "blocked", fetchedAt: null },
    } as unknown as FundamentalCardDto;
    expect(fundamentalsSnapshotMissing(blocked)).toBe(false);
  });
});
