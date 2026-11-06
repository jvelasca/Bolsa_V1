import { describe, expect, it } from "vitest";
import type { ScanSkippedInstrumentDto } from "@bolsa/shared";
import { isWarmupInsufficientReason } from "@bolsa/shared";
import {
  notEvaluableSkipped,
  scanSilenceBreakdown,
  scanSilenceSummary,
  skippedCause,
} from "@/lib/scan-silence";

const WARMUP_REASON =
  "warmup_insufficient: sma(period=200) requiere 201 barras y la ventana tiene 120";

function skipped(reason: string, i = 0): ScanSkippedInstrumentDto {
  return { instrumentId: `inst-${i}`, reason };
}

const NO_BARS = "Menos de 50 barras — sincroniza el instrumento";

describe("skippedCause", () => {
  it("clasifica el warmup por su prefijo estable, no por el texto", () => {
    expect(skippedCause(WARMUP_REASON)).toBe("not_evaluable");
    // El resto del motivo es prosa libre: puede cambiar sin romper la clasificación.
    expect(skippedCause("warmup_insufficient: otra redacción")).toBe(
      "not_evaluable",
    );
    expect(skippedCause("  warmup_insufficient: con espacios")).toBe(
      "not_evaluable",
    );
  });

  it("no confunde el warmup con otros motivos que contienen la palabra", () => {
    expect(skippedCause("El warmup_insufficient no aplica")).toBe("other");
    expect(skippedCause("requiere más barras")).toBe("other");
  });

  it("separa la falta de barras del warmup del preset", () => {
    expect(skippedCause(NO_BARS)).toBe("insufficient_data");
    expect(skippedCause("Instrumento no encontrado")).toBe("other");
  });
});

describe("scanSilenceBreakdown", () => {
  it("cuenta solo como evaluados los que no se omitieron", () => {
    const breakdown = scanSilenceBreakdown({
      scannedCount: 5,
      skipped: [
        skipped(WARMUP_REASON, 0),
        skipped(WARMUP_REASON, 1),
        skipped(NO_BARS, 2),
      ],
    });
    expect(breakdown).toEqual({
      evaluated: 2,
      notEvaluable: 2,
      insufficientData: 1,
      other: 0,
    });
  });

  it("no produce evaluados negativos si el recuento viene inconsistente", () => {
    const breakdown = scanSilenceBreakdown({
      scannedCount: 1,
      skipped: [skipped(WARMUP_REASON, 0), skipped(WARMUP_REASON, 1)],
    });
    expect(breakdown.evaluated).toBe(0);
  });
});

describe("scanSilenceSummary", () => {
  it("no dice «sin señal» cuando el preset no era evaluable", () => {
    const summary = scanSilenceSummary({
      scannedCount: 1,
      skipped: [skipped(WARMUP_REASON)],
    });
    expect(summary.headline).toBe("Ningún instrumento pudo evaluarse");
    expect(summary.headline).not.toContain("Sin señal");
    expect(summary.detail).toContain("warmup");
    expect(summary.detail).toContain("más barras que la ventana");
  });

  it("separa lo evaluado de lo no evaluable en el titular", () => {
    const summary = scanSilenceSummary({
      scannedCount: 4,
      skipped: [
        skipped(WARMUP_REASON, 0),
        skipped(WARMUP_REASON, 1),
        skipped(WARMUP_REASON, 2),
      ],
    });
    expect(summary.headline).toBe("1 sin señal · 3 instrumentos no evaluables");
    expect(summary.breakdown.evaluated).toBe(1);
  });

  it("usa el singular cuando solo hay uno", () => {
    const summary = scanSilenceSummary({
      scannedCount: 2,
      skipped: [skipped(WARMUP_REASON)],
    });
    expect(summary.headline).toBe("1 sin señal · 1 instrumento no evaluable");
  });

  it("conserva el titular de siempre cuando todo se evaluó", () => {
    const summary = scanSilenceSummary({ scannedCount: 3, skipped: [] });
    expect(summary.headline).toBe(
      "Sin señales en la última barra de la lista.",
    );
    expect(summary.detail).toBeNull();
  });

  it("declara la falta de barras como causa propia", () => {
    const summary = scanSilenceSummary({
      scannedCount: 1,
      skipped: [skipped(NO_BARS)],
    });
    expect(summary.headline).toBe("Ningún instrumento pudo evaluarse");
    expect(summary.detail).toContain("sincroniza el instrumento");
    expect(summary.detail).not.toContain("warmup");
  });

  it("no cuenta como no evaluable un skip por fundamentales", () => {
    const summary = scanSilenceSummary({
      scannedCount: 2,
      skipped: [skipped("No cumple filtro fundamental", 0)],
    });
    expect(summary.headline).toBe("1 sin señal · 1 instrumento no evaluable");
    expect(summary.detail).toContain("otro motivo");
  });

  it("no promete detalle si no hay nada que detallar", () => {
    const summary = scanSilenceSummary({ scannedCount: 0, skipped: [] });
    expect(summary.headline).toBe(
      "Sin señales en la última barra de la lista.",
    );
    expect(summary.detail).toBeNull();
  });
});

describe("notEvaluableSkipped", () => {
  it("devuelve solo los de warmup, conservando su motivo", () => {
    const items = notEvaluableSkipped([
      skipped(NO_BARS, 0),
      skipped(WARMUP_REASON, 1),
      skipped("Instrumento no encontrado", 2),
    ]);
    expect(items).toHaveLength(1);
    expect(items[0]?.instrumentId).toBe("inst-1");
    expect(items[0]?.reason).toContain("warmup_insufficient");
  });
});

describe("isWarmupInsufficientReason", () => {
  it("acepta el prefijo con espacio inicial pero no a mitad de frase", () => {
    expect(isWarmupInsufficientReason("warmup_insufficient: x")).toBe(true);
    expect(isWarmupInsufficientReason("  warmup_insufficient")).toBe(true);
    expect(isWarmupInsufficientReason("motivo: warmup_insufficient")).toBe(
      false,
    );
  });
});
