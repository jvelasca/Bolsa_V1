/**
 * AUTO Monitor · Ownership de reservas — regresión de la MEDICIÓN declarada (§14).
 *
 * Invariante: un campo NO MEDIDO se rotula `NO MEDIDO`; jamás se degrada a `?` ni a un valor
 * fingido. Las 5 banderas (`reason`/`caller`/`aged`/`graceWindow`/`reconciliation`) viajan en el
 * DTO y la fila de reconciliación las usa para distinguir vacío de no medido.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AutoReservationPanel } from "@/features/auto-monitor/auto-reservation-panel";
import type { AutoMonitorReservationV1 } from "@bolsa/shared";

function reservation(
  overrides: Partial<AutoMonitorReservationV1> = {},
): AutoMonitorReservationV1 {
  return {
    reservationId: "res-1",
    instrumentId: "AAA",
    side: "buy",
    quantity: 10,
    remainingQty: 0,
    ownerSession: null,
    ownerMeasurement: "UNKNOWN",
    created: "2026-01-01T00:00:00Z",
    expires: null,
    expiresMeasurement: "UNKNOWN",
    state: "RELEASED_BY_FILL",
    releaseReason: "fill",
    releaseReasonMeasurement: "COMPLETE",
    fillProgress: { filled: 10, requested: 10, measurement: "COMPLETE" },
    reconciliations: [],
    ...overrides,
  };
}

afterEach(() => cleanup());

describe("AutoReservationPanel · reconciliaciones", () => {
  it("rotula NO MEDIDO en placeholders nulos (nunca '?')", () => {
    render(
      <AutoReservationPanel
        reservations={[
          reservation({
            reconciliations: [
              {
                decision: "KEEP",
                reason: null,
                reasonMeasurement: "UNKNOWN",
                caller: null,
                callerMeasurement: "UNKNOWN",
                aged: null,
                agedMeasurement: "UNKNOWN",
                graceWindowSeconds: null,
                graceWindowMeasurement: "UNKNOWN",
                reconciliationMeasurement: "COMPLETE",
              },
            ],
          }),
        ]}
      />,
    );

    const item = screen.getByTestId("auto-monitor-reservation");
    expect(item.textContent).toContain("NO MEDIDO");
    expect(item.textContent).not.toContain("?");
  });

  it("pinta aged/grace con su medición y no los finge MEDIDO si faltan", () => {
    render(
      <AutoReservationPanel
        reservations={[
          reservation({
            reconciliations: [
              {
                decision: "RELEASE",
                reason: "grace_window_expired",
                reasonMeasurement: "COMPLETE",
                caller: "sweep",
                callerMeasurement: "COMPLETE",
                aged: false,
                agedMeasurement: "COMPLETE",
                graceWindowSeconds: 30,
                graceWindowMeasurement: "COMPLETE",
                reconciliationMeasurement: "COMPLETE",
              },
            ],
          }),
        ]}
      />,
    );

    const item = screen.getByTestId("auto-monitor-reservation");
    expect(item.textContent).toContain("grace_window_expired");
    expect(item.textContent).toContain("caller sweep");
    expect(item.textContent).toContain("aged no");
    expect(item.textContent).toContain("gracia 30");
  });
});
