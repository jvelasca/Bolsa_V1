/**
 * R-2 — contrato de la traducción de códigos del parte a frases de nivel 1.
 *
 * Invariantes:
 * - todo código produce una frase (los desconocidos se declaran como hueco, no se silencian);
 * - el código crudo viaja en `technical` para el disclosure;
 * - los motivos con contador conservan el número (N valores sin medida);
 * - `describeEstudioDailyNotes` deduplica sin perder el orden.
 */

import { describe, expect, it } from "vitest";
import {
  describeEstudioDailyNote,
  describeEstudioDailyNotes,
  describePositionOpen,
} from "@/features/auto-monitor/estudio-daily-notes";

describe("describeEstudioDailyNote", () => {
  it("traduce la cartera no medida", () => {
    const note = describeEstudioDailyNote("positions_unavailable");
    expect(note.headline).toContain("No se pudo leer tu cartera");
    expect(note.technical).toBe("positions_unavailable");
  });

  it("conserva el número de valores sin chips", () => {
    const composite = describeEstudioDailyNote(
      "composite_chips_unavailable:12_ids",
    );
    expect(composite.headline).toContain("12 valores");
    expect(composite.technical).toBe("composite_chips_unavailable:12_ids");

    const fundamentals = describeEstudioDailyNote(
      "fundamentals_chips_unavailable:3_ids",
    );
    expect(fundamentals.headline).toContain("3 valores");
    expect(fundamentals.headline).toContain("fundamentales");
  });

  it("traduce los errores de opinión y la propuesta caída", () => {
    expect(
      describeEstudioDailyNote("opinion_errors:4_values").headline,
    ).toContain("4 valores");
    expect(describeEstudioDailyNote("propose_unavailable").headline).toContain(
      "propuesta de planes",
    );
    // El formato legacy del backend también se reconoce.
    expect(
      describeEstudioDailyNote("propose no disponible: timeout").headline,
    ).toContain("propuesta de planes");
  });

  it("declara el parte informativo sin afirmar que ejecuta", () => {
    const note = describeEstudioDailyNote(
      "allowTrading=true se declara como cálculo advisory; el veto de ejecución se aplica en el camino de ejecución (PAPER_D_EXECUTE).",
    );
    expect(note.headline).toContain("informativo");
    expect(note.technical).toContain("allowTrading=true");
  });

  it("declara el hueco de identidad del selector", () => {
    expect(
      describeEstudioDailyNote("selector_identity_unavailable").headline,
    ).toContain("selector");
    expect(describeEstudioDailyNote("no_snapshot_for_day").headline).toContain(
      "No hay foto del selector",
    );
  });

  it("declara el recorte del universo y los valores sin reportar (C-2)", () => {
    // El backend publica el código ESTABLE en `degradedReasons` (además de la nota).
    const truncated = describeEstudioDailyNote("universe_truncated:4");
    expect(truncated.headline).toContain("universo se recortó");
    expect(truncated.technical).toBe("universe_truncated:4");

    const notReported = describeEstudioDailyNote("values_not_reported:2");
    expect(notReported.headline).toContain("2 valores");
    expect(notReported.technical).toBe("values_not_reported:2");

    // La nota legacy sigue reconociéndose con la misma frase.
    expect(
      describeEstudioDailyNote(
        "Universo recortado a 100 valores (el ESTUDIO tiene más)",
      ).headline,
    ).toContain("universo se recortó");
  });

  it("un código desconocido no se oculta ni se disfraza", () => {
    const note = describeEstudioDailyNote("raro_del_backend:7");
    expect(note.headline).toContain("no se pudo medir");
    expect(note.technical).toBe("raro_del_backend:7");
  });

  it("una nota vacía no se inventa como «todo bien»", () => {
    expect(describeEstudioDailyNote("  ").headline).toContain(
      "no se pudo medir",
    );
  });
});

describe("describeEstudioDailyNotes", () => {
  it("deduplica conservando el orden y descarta vacíos", () => {
    const notes = describeEstudioDailyNotes([
      "positions_unavailable",
      "positions_unavailable",
      "",
      "composite_chips_unavailable:2_ids",
    ]);
    expect(notes.map((note) => note.code)).toEqual([
      "positions_unavailable",
      "composite_chips_unavailable:2_ids",
    ]);
  });

  it("tolera null/undefined sin romper", () => {
    expect(describeEstudioDailyNotes(null)).toEqual([]);
    expect(describeEstudioDailyNotes(undefined)).toEqual([]);
  });
});

describe("describePositionOpen", () => {
  it("distingue los tres estados (null NO es «sin posición»)", () => {
    expect(describePositionOpen(true)).toBe("Con posición abierta");
    expect(describePositionOpen(false)).toBe("Sin posición abierta");
    expect(describePositionOpen(null)).toBe("Cartera sin medida");
    expect(describePositionOpen(undefined)).toBe("Cartera sin medida");
  });
});
