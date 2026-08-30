import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CommandPalette } from "@/features/command-palette/command-palette";
import {
  LABORATORIO_PATH,
  type CommandRunContext,
} from "@/features/command-palette/command-registry";
import {
  isCommandPaletteToggle,
  isEditableKeyboardTarget,
  resolveL1Hotkey,
} from "@/features/command-palette/keyboard";
import { applyUiDensityToDocument } from "@/features/command-palette/ui-density";
import {
  applyUiThemeToDocument,
  type UiTheme,
} from "@/features/command-palette/ui-theme";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import {
  ASESOR_PATH,
  CARTERA_POSICIONES_PATH,
  MERCADO_PATH,
  MESA_PATH,
} from "@/features/confirm/daily-nav";
import { useUiStore } from "@/stores/ui-store";
import { useTradingLayoutStore } from "@/stores/trading-layout-store";

export const BOLSA_COMMAND_PALETTE_EVENT = "bolsa:command-palette" as const;

const L1_PATH: Record<
  NonNullable<ReturnType<typeof resolveL1Hotkey>>,
  string
> = {
  hoy: MESA_PATH,
  mercado: MERCADO_PATH,
  cartera: CARTERA_POSICIONES_PATH,
  asesor: ASESOR_PATH,
  laboratorio: LABORATORIO_PATH,
  confirmar: CONFIRM_PATH,
};

/** Abre la palette desde UI (p. ej. botón en top bar). */
export function requestOpenCommandPalette(): void {
  window.dispatchEvent(new CustomEvent(BOLSA_COMMAND_PALETTE_EVENT));
}

export function CommandPaletteHost() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const openPlatformConfig = useUiStore((s) => s.openPlatformConfig);
  const uiDensity = useUiStore((s) => s.uiDensity);
  const setUiDensity = useUiStore((s) => s.setUiDensity);
  const uiTheme = useUiStore((s) => s.uiTheme);
  const setUiTheme = useUiStore((s) => s.setUiTheme);
  const applyNamedLayout = useTradingLayoutStore((s) => s.applyNamedLayout);

  useEffect(() => {
    applyUiDensityToDocument(uiDensity);
  }, [uiDensity]);

  useEffect(() => {
    applyUiThemeToDocument(uiTheme);
    if (uiTheme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyUiThemeToDocument("system" satisfies UiTheme);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [uiTheme]);

  const runContext = useMemo<CommandRunContext>(
    () => ({
      navigate,
      openPlatformConfig,
      uiDensity,
      setUiDensity,
      uiTheme,
      setUiTheme,
      applyNamedLayout,
    }),
    [
      navigate,
      openPlatformConfig,
      uiDensity,
      setUiDensity,
      uiTheme,
      setUiTheme,
      applyNamedLayout,
    ],
  );

  useEffect(() => {
    const onOpenRequest = () => setOpen(true);
    window.addEventListener(BOLSA_COMMAND_PALETTE_EVENT, onOpenRequest);
    return () =>
      window.removeEventListener(BOLSA_COMMAND_PALETTE_EVENT, onOpenRequest);
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isCommandPaletteToggle(event)) {
        // Con palette abierta, Ctrl+K cierra aunque el foco esté en el input.
        if (isEditableKeyboardTarget(event.target) && !open) return;
        event.preventDefault();
        setOpen((v) => !v);
        return;
      }

      if (open) return;
      if (isEditableKeyboardTarget(event.target)) return;

      const target = resolveL1Hotkey(event);
      if (!target) return;
      event.preventDefault();
      navigate(L1_PATH[target]);
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigate, open]);

  return (
    <CommandPalette
      open={open}
      onClose={() => setOpen(false)}
      runContext={runContext}
    />
  );
}
