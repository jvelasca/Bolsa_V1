import { describe, expect, it, vi, beforeEach } from "vitest";

import { INSTRUMENT_QUOTES_BATCH_LIMIT } from "@bolsa/shared";

import { api } from "@/lib/api";
import { fetchInstrumentQuotesChunked } from "@/lib/chunked-quotes";

vi.mock("@/lib/api", () => ({
  api: {
    getInstrumentQuotes: vi.fn(),
  },
}));

function makeQuote(id: string) {
  return { id, symbol: id.toUpperCase(), name: id };
}

describe("fetchInstrumentQuotesChunked", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("trocea en lotes de 200 (límite de POST /api/instruments/quotes)", async () => {
    const ids = Array.from({ length: 213 }, (_, index) => `id-${index}`);
    vi.mocked(api.getInstrumentQuotes).mockImplementation(async (chunk) => ({
      data: chunk.map(makeQuote),
    }));

    const quotes = await fetchInstrumentQuotesChunked(ids);

    expect(api.getInstrumentQuotes).toHaveBeenCalledTimes(2);
    const sizes = vi
      .mocked(api.getInstrumentQuotes)
      .mock.calls.map(([chunk]) => chunk.length);
    expect(sizes).toEqual([INSTRUMENT_QUOTES_BATCH_LIMIT, 13]);
    expect(quotes).toHaveLength(213);
  });

  it("deduplica ids y evita llamadas vacías", async () => {
    vi.mocked(api.getInstrumentQuotes).mockImplementation(async (chunk) => ({
      data: chunk.map(makeQuote),
    }));

    await fetchInstrumentQuotesChunked([]);
    expect(api.getInstrumentQuotes).not.toHaveBeenCalled();

    await fetchInstrumentQuotesChunked(["a", "a", "b"]);
    expect(api.getInstrumentQuotes).toHaveBeenCalledTimes(1);
    expect(vi.mocked(api.getInstrumentQuotes).mock.calls[0]?.[0]).toEqual([
      "a",
      "b",
    ]);
  });

  it("la fusión no pierde instrumentos ni duplica cotizaciones (200 + 13)", async () => {
    const ids = Array.from({ length: 213 }, (_, index) => `id-${index}`);
    vi.mocked(api.getInstrumentQuotes).mockImplementation(async (chunk) => ({
      // El segundo lote repite un id del primero: la fusión debe colapsarlo.
      data: [...chunk, ...(chunk.length < 100 ? ["id-0"] : [])].map(makeQuote),
    }));

    const quotes = await fetchInstrumentQuotesChunked(ids);

    expect(quotes).toHaveLength(213);
    expect(new Set(quotes.map((quote) => quote.id)).size).toBe(213);
    expect(quotes.map((quote) => quote.id)).toEqual(ids);
  });

  it("mantiene el orden pedido aunque el servidor responda desordenado", async () => {
    vi.mocked(api.getInstrumentQuotes).mockImplementation(async (chunk) => ({
      data: [...chunk].reverse().map(makeQuote),
    }));

    const quotes = await fetchInstrumentQuotesChunked(["c", "a", "b"]);
    expect(quotes.map((quote) => quote.id)).toEqual(["c", "a", "b"]);
  });

  it("si un lote falla rechaza la consulta entera (aviso de precios)", async () => {
    const ids = Array.from({ length: 213 }, (_, index) => `id-${index}`);
    vi.mocked(api.getInstrumentQuotes).mockImplementation(async (chunk) => {
      if (chunk.includes("id-210")) throw new Error("lote caído");
      return { data: chunk.map(makeQuote) };
    });

    await expect(fetchInstrumentQuotesChunked(ids)).rejects.toThrow(
      "lote caído",
    );
  });

  it("descarta ids que el servidor no devuelve en vez de inventar filas", async () => {
    vi.mocked(api.getInstrumentQuotes).mockImplementation(async (chunk) => ({
      data: chunk.filter((id) => id !== "b").map(makeQuote),
    }));

    const quotes = await fetchInstrumentQuotesChunked(["a", "b", "c"]);
    expect(quotes.map((quote) => quote.id)).toEqual(["a", "c"]);
  });
});
