/**
 * Tests — Command palette: los grupos (nav/config/density/theme/layout) se
 * distinguen visualmente con una cabecera propia (`GROUP_LABEL[group]`), y cada
 * comando se pinta bajo la cabecera de su grupo, sin intercalarse con otro.
 *
 * Falsable del [Mapa de problemas UI 5.0 §2.4](../../../../../../docs/engineering/auditoria-ui-5-0-mapa-problemas-2026-10-08.md)
 * (regla `UI5-17`: Acción ≠ Navegación ≠ Información): si el render volviera a
 * ser un listado plano (sin cabeceras de grupo), estos tests fallarían.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CommandPalette } from "@/features/command-palette/command-palette";
import {
  PLATFORM_COMMANDS,
  type CommandGroup,
  type CommandRunContext,
} from "@/features/command-palette/command-registry";

const GROUP_ORDER: CommandGroup[] = [
  "nav",
  "config",
  "density",
  "theme",
  "layout",
];

const GROUP_HEADER: Record<CommandGroup, string> = {
  nav: "Navegación",
  config: "Configuración",
  density: "Densidad",
  theme: "Tema",
  layout: "Layout",
};

function mockCtx(): CommandRunContext {
  return {
    navigate: vi.fn(),
    openPlatformConfig: vi.fn(),
    uiDensity: "comfortable",
    setUiDensity: vi.fn(),
    uiTheme: "dark",
    setUiTheme: vi.fn(),
    applyNamedLayout: vi.fn(),
  };
}

afterEach(cleanup);

function renderPalette() {
  return render(
    <CommandPalette open onClose={vi.fn()} runContext={mockCtx()} />,
  );
}

function listbox() {
  return screen.getByRole("listbox");
}

/** La cabecera de grupo es el único `div` del listbox con ese texto exacto. */
function headerFor(group: CommandGroup): HTMLElement {
  return within(listbox()).getByText(GROUP_HEADER[group], { selector: "div" });
}

/** ¿`a` precede a `b` en el orden del DOM? */
function isBefore(a: Node, b: Node): boolean {
  return Boolean(
    a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING,
  );
}

describe("CommandPalette — grupos separados (UI5-17)", () => {
  it("pinta una cabecera única por grupo, en el orden del registry", () => {
    renderPalette();

    const headers = GROUP_ORDER.map((group) => headerFor(group));
    headers.forEach((header) => expect(header).toBeInTheDocument());

    for (let i = 1; i < headers.length; i += 1) {
      expect(isBefore(headers[i - 1], headers[i])).toBe(true);
    }

    // Ningún grupo repite cabecera (separación por bloques, no por comando).
    GROUP_ORDER.forEach((group) => {
      expect(
        within(listbox()).getAllByText(GROUP_HEADER[group], {
          selector: "div",
        }),
      ).toHaveLength(1);
    });
  });

  it("pinta un comando de config bajo 'Configuración', sin intercalarse con nav", () => {
    renderPalette();

    const configHeader = headerFor("config");
    const navHeader = headerFor("nav");

    expect(isBefore(navHeader, configHeader)).toBe(true);

    // Todo comando nav vive ANTES de la cabecera 'Configuración'.
    for (const cmd of PLATFORM_COMMANDS.filter((c) => c.group === "nav")) {
      const option = screen.getByRole("option", { name: cmd.label });
      expect(isBefore(option, configHeader)).toBe(true);
    }

    // Y todo comando config vive DESPUÉS de su cabecera.
    for (const cmd of PLATFORM_COMMANDS.filter((c) => c.group === "config")) {
      const option = screen.getByRole("option", { name: cmd.label });
      expect(isBefore(configHeader, option)).toBe(true);
    }

    expect(
      screen.getByRole("option", { name: "Abrir Configuración" }),
    ).toBeInTheDocument();
  });

  it("mantiene cada comando dentro del bloque de su grupo", () => {
    renderPalette();

    GROUP_ORDER.forEach((group, index) => {
      const header = headerFor(group);
      const nextGroup = GROUP_ORDER[index + 1];
      const nextHeader = nextGroup ? headerFor(nextGroup) : null;

      for (const cmd of PLATFORM_COMMANDS.filter((c) => c.group === group)) {
        const option = screen.getByRole("option", { name: cmd.label });
        expect(isBefore(header, option)).toBe(true);
        if (nextHeader) {
          expect(isBefore(option, nextHeader)).toBe(true);
        }
      }
    });
  });
});
