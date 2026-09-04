import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { F3ProtectStopBlock } from "@/features/trading/f3-protect-stop-block";

vi.mock("@/features/help/mesa-tip-button", () => ({
  MesaTipButton: () => null,
}));

afterEach(() => cleanup());

describe("F3ProtectStopBlock", () => {
  it("shows override textarea when stop worsens", () => {
    render(
      <F3ProtectStopBlock
        meta={{
          operativaIntent: "protect",
          suggestedStop: 95,
          currentStop: 100,
          direction: "long",
          stopOverrideRequired: true,
        }}
        currency="EUR"
        overrideReason=""
        onOverrideReasonChange={() => {}}
      />,
    );
    expect(screen.getByTestId("f3-protect-stop")).toBeTruthy();
    expect(screen.getByTestId("f3-protect-stop-override-reason")).toBeTruthy();
    expect(screen.getByText(/empeora el actual/i)).toBeTruthy();
  });

  it("calls onOverrideReasonChange", () => {
    const onChange = vi.fn();
    render(
      <F3ProtectStopBlock
        meta={{
          operativaIntent: "protect",
          suggestedStop: 95,
          currentStop: 100,
          direction: "long",
          stopOverrideRequired: true,
        }}
        currency="EUR"
        overrideReason=""
        onOverrideReasonChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("f3-protect-stop-override-reason"), {
      target: { value: "ajuste manual" },
    });
    expect(onChange).toHaveBeenCalledWith("ajuste manual");
  });

  it("V2.10 — bootstrap shows emergency copy, not technical stop", () => {
    render(
      <F3ProtectStopBlock
        meta={{
          operativaIntent: "protect",
          suggestedStop: 95,
          currentStop: null,
          direction: "long",
          stopOverrideRequired: false,
          protectKind: "bootstrap",
        }}
        currency="EUR"
        overrideReason=""
        onOverrideReasonChange={() => {}}
      />,
    );
    const block = screen.getByTestId("f3-protect-stop");
    expect(block.getAttribute("data-protect-kind")).toBe("bootstrap");
    expect(screen.getByTestId("f3-protect-bootstrap-banner")).toBeTruthy();
    expect(screen.getByText(/Posición sin protección/i)).toBeTruthy();
    expect(screen.getAllByText(/Stop de emergencia/i).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByText(/No sustituye al stop técnico/i)).toBeTruthy();
  });
});
