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
});
