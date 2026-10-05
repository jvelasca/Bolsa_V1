/**
 * MeasurementValue / MeasurementBadge — representación única valor + medición.
 *
 * Invariante: un valor sin muestra nunca se pinta como medido; un valor con muestra no afirmable
 * se anota (`valor · PARCIAL`) o se retiene (`withhold`), y una cabecera sólo puede mostrar la
 * medición.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  MeasurementBadge,
  MeasurementValue,
} from "@/components/measurement-value";

afterEach(() => cleanup());

describe("MeasurementValue", () => {
  it("muestra el valor sólo cuando la medición es COMPLETE", () => {
    render(<MeasurementValue testId="v" value={7} measurement="COMPLETE" />);
    const node = screen.getByTestId("v");
    expect(node.textContent).toBe("7");
    expect(node.getAttribute("data-measurement")).toBe("COMPLETE");
    expect(node.getAttribute("data-measured")).toBe("true");
  });

  it("rotula la medición cuando no hay valor (nunca un número)", () => {
    render(<MeasurementValue testId="v" value={null} measurement="UNKNOWN" />);
    const node = screen.getByTestId("v");
    expect(node.textContent).toBe("NO MEDIDO");
    expect(node.getAttribute("data-measured")).toBe("false");
  });

  it("degrada COMPLETE sin valor a no medido (no afirma)", () => {
    render(<MeasurementValue testId="v" value={null} measurement="COMPLETE" />);
    expect(screen.getByTestId("v").textContent).toBe("NO MEDIDO");
  });

  it("anota un valor PARCIAL como suelo medido", () => {
    render(<MeasurementValue testId="v" value={3} measurement="PARTIAL" />);
    const node = screen.getByTestId("v");
    expect(node.textContent).toContain("3");
    expect(node.textContent).toContain("PARCIAL");
    expect(node.getAttribute("data-measurement")).toBe("PARTIAL");
  });

  it("retiene la cifra no afirmable con `withhold`", () => {
    render(
      <MeasurementValue
        testId="v"
        value={100}
        measurement="PARTIAL"
        incomplete="withhold"
      />,
    );
    const node = screen.getByTestId("v");
    expect(node.textContent).toBe("PARCIAL");
    expect(node.textContent).not.toContain("100");
  });

  it("admite un formateador propio cuando el valor sí se muestra", () => {
    render(
      <MeasurementValue
        testId="v"
        value="cyc-1"
        measurement="COMPLETE"
        formatValue={(value) => `#${String(value)}`}
      />,
    );
    expect(screen.getByTestId("v").textContent).toBe("#cyc-1");
  });
});

describe("MeasurementBadge", () => {
  it("traduce la medición a etiqueta", () => {
    render(<MeasurementBadge testId="b" measurement="COMPLETE" />);
    expect(screen.getByTestId("b").textContent).toBe("MEDIDO");
  });

  it("marca como no medida cualquier medición distinta de COMPLETE", () => {
    render(<MeasurementBadge testId="b" measurement="UNKNOWN" />);
    const node = screen.getByTestId("b");
    expect(node.textContent).toBe("NO MEDIDO");
    expect(node.getAttribute("data-measurement")).toBe("UNKNOWN");
  });
});
