/** Guards y helpers de teclado para palette / hotkeys V1.31. */

export function isEditableKeyboardTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  if (target.getAttribute("contenteditable") === "true") return true;
  return target.closest('[contenteditable="true"]') != null;
}

export function isModKey(event: KeyboardEvent): boolean {
  return event.metaKey || event.ctrlKey;
}

/** Ctrl/Cmd+K — abrir/cerrar command palette. */
export function isCommandPaletteToggle(event: KeyboardEvent): boolean {
  return (
    isModKey(event) &&
    !event.altKey &&
    !event.shiftKey &&
    event.key.toLowerCase() === "k"
  );
}

export type L1HotkeyTarget =
  | "hoy"
  | "mercado"
  | "cartera"
  | "asesor"
  | "laboratorio"
  | "confirmar";

/**
 * Alt+1…5 → L1; Alt+C → Confirmar.
 * Ignora si hay Mod (Ctrl/Cmd) para no pelear con atajos del SO.
 */
export function resolveL1Hotkey(event: KeyboardEvent): L1HotkeyTarget | null {
  if (!event.altKey || event.metaKey || event.ctrlKey) return null;
  const key = event.key.toLowerCase();
  switch (key) {
    case "1":
      return "hoy";
    case "2":
      return "mercado";
    case "3":
      return "cartera";
    case "4":
      return "asesor";
    case "5":
      return "laboratorio";
    case "c":
      return "confirmar";
    default:
      return null;
  }
}
