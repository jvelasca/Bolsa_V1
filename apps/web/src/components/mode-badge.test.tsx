/**
 * UI Contract 5.0 (`UI5-10`/`UI5-17`) — la insignia de modo es información, no acción.
 *
 * Una operación sin evidencia de modo se pinta «Sin dato todavía», nunca un verde.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ModeBadge } from "@/components/mode-badge";
import {
  AUTO_OPERATION_MODE,
  OPERATION_MODE_NO_DATA_LABEL,
} from "@/features/operations/operation-mode";

afterEach(cleanup);

describe("ModeBadge", () => {
  it("declara el modo y el canal con evidencia", () => {
    render(<ModeBadge badge={AUTO_OPERATION_MODE} testId="badge" />);
    const badge = screen.getByTestId("badge");
    expect(badge.textContent).toBe("AUTO · SIMULADO");
    expect(badge.dataset.mode).toBe("AUTO");
    expect(badge.dataset.channel).toBe("SIMULADO");
  });

  it("sin evidencia de modo, declara «Sin dato todavía»", () => {
    render(
      <ModeBadge badge={{ mode: null, channel: "SIMULADO" }} testId="badge" />,
    );
    const badge = screen.getByTestId("badge");
    expect(badge.textContent).toBe(OPERATION_MODE_NO_DATA_LABEL);
    expect(badge.dataset.mode).toBe("unknown");
  });

  it("no es interactivo (información, no botón)", () => {
    render(<ModeBadge badge={AUTO_OPERATION_MODE} testId="badge" />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
