import { describe, expect, it } from "vitest";
import {
  NO_MEASUREMENT_LABEL,
  type AutoMonitorCycleViewV1,
} from "@bolsa/shared";
import {
  buildOperationIdentity,
  formatEntryDay,
} from "./auto-operation-identity";

function makeCycle(input: {
  instrumentId?: string | null;
  directionLabel?: string;
  statusLabel?: string;
  signalAt?: string | null;
}): AutoMonitorCycleViewV1 {
  return {
    cycleId: "cyc-1",
    instrumentId: input.instrumentId ?? null,
    directionLabel: input.directionLabel ?? "Largo",
    statusLabel: input.statusLabel ?? "Abierto",
    steps: [
      {
        id: "SIGNAL",
        state: "reached",
        at: input.signalAt ?? null,
        measurement: "COMPLETE",
        facts: [],
        label: "Señal",
        stateLabel: "alcanzado",
        tone: "",
        dotTone: "",
        measurementLabel: "MEDIDO",
      },
    ],
    unmeasuredStepIds: [],
  } as unknown as AutoMonitorCycleViewV1;
}

describe("formatEntryDay", () => {
  it("copia el día de la señal en formato DD MMM determinista", () => {
    expect(formatEntryDay("2026-10-03T09:31:00Z")).toBe("03 oct");
    expect(formatEntryDay("2026-10-03")).toBe("03 oct");
  });

  it("un sello ausente o ilegible se declara NO MEDIDO", () => {
    expect(formatEntryDay(null)).toBe(NO_MEASUREMENT_LABEL);
    expect(formatEntryDay(undefined)).toBe(NO_MEASUREMENT_LABEL);
    expect(formatEntryDay("ayer por la mañana")).toBe(NO_MEASUREMENT_LABEL);
    expect(formatEntryDay("2026-99-03")).toBe(NO_MEASUREMENT_LABEL);
  });
});

describe("buildOperationIdentity", () => {
  it("compone símbolo · día · dirección · estado", () => {
    const identity = buildOperationIdentity(
      makeCycle({
        instrumentId: "AAPL",
        signalAt: "2026-10-03T09:31:00Z",
        directionLabel: "Largo",
        statusLabel: "Abierto",
      }),
    );
    expect(identity.entryDay).toBe("03 oct");
    expect(identity.label).toBe("AAPL · 03 oct · Largo · Abierto");
  });

  it("dos ciclos del mismo símbolo en días distintos son distinguibles", () => {
    const a = buildOperationIdentity(
      makeCycle({ instrumentId: "AAPL", signalAt: "2026-10-03T09:00:00Z" }),
    );
    const b = buildOperationIdentity(
      makeCycle({ instrumentId: "AAPL", signalAt: "2026-10-04T09:00:00Z" }),
    );
    expect(a.label).not.toBe(b.label);
  });

  it("un hueco (sin señal ni símbolo) se declara NO MEDIDO, no se inventa", () => {
    const identity = buildOperationIdentity(makeCycle({}));
    expect(identity.entryDay).toBe(NO_MEASUREMENT_LABEL);
    expect(identity.label).toBe(
      `${NO_MEASUREMENT_LABEL} · ${NO_MEASUREMENT_LABEL} · Largo · Abierto`,
    );
  });
});
