import { describe, expect, it } from "vitest";
import {
  isCommandPaletteToggle,
  isEditableKeyboardTarget,
  resolveL1Hotkey,
} from "./keyboard";
import { nextUiDensity } from "./ui-density";
import { PLATFORM_SHORTCUTS } from "./platform-shortcuts";

function keyEvent(
  partial: Partial<KeyboardEvent> & { key: string },
): KeyboardEvent {
  return partial as KeyboardEvent;
}

describe("isEditableKeyboardTarget", () => {
  it("detects input/textarea/select and contentEditable", () => {
    const input = document.createElement("input");
    expect(isEditableKeyboardTarget(input)).toBe(true);

    const textarea = document.createElement("textarea");
    expect(isEditableKeyboardTarget(textarea)).toBe(true);

    const select = document.createElement("select");
    expect(isEditableKeyboardTarget(select)).toBe(true);

    const div = document.createElement("div");
    expect(isEditableKeyboardTarget(div)).toBe(false);

    div.setAttribute("contenteditable", "true");
    expect(isEditableKeyboardTarget(div)).toBe(true);
  });
});

describe("isCommandPaletteToggle", () => {
  it("matches Ctrl/Cmd+K without Alt/Shift", () => {
    expect(
      isCommandPaletteToggle(
        keyEvent({ key: "k", ctrlKey: true, metaKey: false }),
      ),
    ).toBe(true);
    expect(
      isCommandPaletteToggle(
        keyEvent({ key: "K", metaKey: true, ctrlKey: false }),
      ),
    ).toBe(true);
    expect(
      isCommandPaletteToggle(
        keyEvent({ key: "k", ctrlKey: true, altKey: true }),
      ),
    ).toBe(false);
  });
});

describe("resolveL1Hotkey", () => {
  it("maps Alt+1…5 and Alt+C", () => {
    expect(resolveL1Hotkey(keyEvent({ key: "1", altKey: true }))).toBe("hoy");
    expect(resolveL1Hotkey(keyEvent({ key: "2", altKey: true }))).toBe(
      "mercado",
    );
    expect(resolveL1Hotkey(keyEvent({ key: "3", altKey: true }))).toBe(
      "cartera",
    );
    expect(resolveL1Hotkey(keyEvent({ key: "4", altKey: true }))).toBe(
      "asesor",
    );
    expect(resolveL1Hotkey(keyEvent({ key: "5", altKey: true }))).toBe(
      "laboratorio",
    );
    expect(resolveL1Hotkey(keyEvent({ key: "c", altKey: true }))).toBe(
      "confirmar",
    );
  });

  it("ignores when Ctrl/Cmd held", () => {
    expect(
      resolveL1Hotkey(keyEvent({ key: "1", altKey: true, ctrlKey: true })),
    ).toBeNull();
  });
});

describe("nextUiDensity", () => {
  it("toggles comfortable ↔ compact", () => {
    expect(nextUiDensity("comfortable")).toBe("compact");
    expect(nextUiDensity("compact")).toBe("comfortable");
  });
});

describe("PLATFORM_SHORTCUTS", () => {
  it("lists palette + L1 + confirm", () => {
    expect(PLATFORM_SHORTCUTS.map((s) => s.id)).toEqual([
      "palette",
      "hoy",
      "mercado",
      "cartera",
      "asesor",
      "laboratorio",
      "confirmar",
    ]);
  });
});
