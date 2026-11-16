import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { autoTelemetryQueryKey } from "@/features/research/asesor-telemetry-strip";

describe("Asesor Opiniones · V1.22 explica", () => {
  it("does not propose F3 from Asesor (navigate only)", () => {
    const src = readFileSync(
      resolve(__dirname, "asesor-opiniones-panel.tsx"),
      "utf8",
    );
    expect(src).not.toMatch(/Proponer F3/);
    expect(src).not.toMatch(/proposeInstrumentSupervised/);
    expect(src).toMatch(/Actuar en Hoy/);
    expect(src).toMatch(/explica; no\s+encola firma/i);
  });

  it("declara los valores sin dictamen en vez de omitirlos", () => {
    const src = readFileSync(
      resolve(__dirname, "asesor-opiniones-panel.tsx"),
      "utf8",
    );
    expect(src).toContain("sinDictamenCount");
    expect(src).toContain("se declaran, no se ocultan");
    expect(src).toContain('data-testid="asesor-opinion-missing"');
  });

  it("muestra scores, veredicto y motor en el detalle técnico", () => {
    const src = readFileSync(
      resolve(__dirname, "asesor-opiniones-panel.tsx"),
      "utf8",
    );
    expect(src).toContain("faScore");
    expect(src).toContain("taScore");
    expect(src).toContain("gateStatus");
    expect(src).toContain("engineVersion");
    expect(src).toContain("TechnicalDetail");
  });
});

describe("telemetría A6 · la caché se separa por cuenta", () => {
  it("dos cuentas distintas producen dos entradas de caché distintas", () => {
    const client = new QueryClient();
    const keyA = autoTelemetryQueryKey(["inst-2", "inst-1"], "cuenta-A");
    const keyB = autoTelemetryQueryKey(["inst-2", "inst-1"], "cuenta-B");

    // La cuenta forma parte de la clave: no comparten entrada.
    expect(keyA).not.toEqual(keyB);
    expect(keyA).toContain("cuenta-A");
    expect(keyB).toContain("cuenta-B");

    client.setQueryData(keyA, { data: { account: "cuenta-A" } });
    expect(client.getQueryData(keyB)).toBeUndefined();
    expect(client.getQueryData(keyA)).toEqual({
      data: { account: "cuenta-A" },
    });
  });

  it("ordena los ids: el orden del Estudio no crea otra entrada", () => {
    const client = new QueryClient();
    const first = autoTelemetryQueryKey(["zeta", "alfa"], "cuenta-A");
    const second = autoTelemetryQueryKey(["alfa", "zeta"], "cuenta-A");

    expect(first).toEqual(second);
    client.setQueryData(first, { data: { days: 3 } });
    expect(client.getQueryData(second)).toEqual({ data: { days: 3 } });
  });
});
