import { describe, expect, it } from "vitest";
import { assertNever } from "./never.js";

describe("assertNever", () => {
  it("throws on unexpected value", () => {
    expect(() => assertNever("nope" as never)).toThrow(
      /unexpected value: nope/,
    );
  });
});
