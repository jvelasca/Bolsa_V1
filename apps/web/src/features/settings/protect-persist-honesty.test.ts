import { describe, expect, it } from "vitest";
import {
  protectPersistNote,
  protectStopNotApplied,
} from "@/features/settings/protect-persist-honesty";

describe("PH-1 protect persist honesty", () => {
  it("does not flag applied protect", () => {
    expect(
      protectStopNotApplied(
        { status: "protect_applied" },
        { status: "applied" },
      ),
    ).toBe(false);
  });

  it("flags persist None as not applied", () => {
    expect(
      protectStopNotApplied(
        { status: "skipped", reason: "stop_not_applied" },
        { status: "skipped", reason: "stop_not_applied" },
      ),
    ).toBe(true);
  });

  it("flags persist error as not applied", () => {
    expect(
      protectStopNotApplied(
        { status: "skipped", reason: "persist_error" },
        { status: "error", reason: "boom" },
      ),
    ).toBe(true);
  });

  it("copy for skipped persist", () => {
    expect(
      protectPersistNote({ status: "skipped", reason: "stop_not_applied" }),
    ).toMatch(/stop no aplicado/i);
    expect(protectPersistNote({ status: "error", reason: "boom" })).toMatch(
      /positionPersist=error/i,
    );
  });
});
