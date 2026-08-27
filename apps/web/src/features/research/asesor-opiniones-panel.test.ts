import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

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
});
