/**
 * Registry de comandos V1.31 — puro, sin React.
 * SoT de rutas L1: daily-nav + confirm-nav.
 */
import {
  ASESOR_LABEL,
  ASESOR_PATH,
  CARTERA_LABEL,
  CARTERA_POSICIONES_PATH,
  CONFIRMAR_LABEL,
  LABORATORIO_LABEL,
  MERCADO_LABEL,
  MERCADO_PATH,
  MESA_LABEL,
  MESA_PATH,
} from "@/features/confirm/daily-nav";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import type { PlatformConfigTab } from "@/stores/ui-store";
import {
  nextUiDensity,
  type UiDensity,
} from "@/features/command-palette/ui-density";
import { nextUiTheme, type UiTheme } from "@/features/command-palette/ui-theme";
import type { NamedLayoutId } from "@/features/command-palette/named-layout";

export type CommandGroup = "nav" | "config" | "density" | "theme" | "layout";

export type CommandRunContext = {
  navigate: (to: string) => void;
  openPlatformConfig: (tab?: PlatformConfigTab) => void;
  uiDensity: UiDensity;
  setUiDensity: (density: UiDensity) => void;
  uiTheme: UiTheme;
  setUiTheme: (theme: UiTheme) => void;
  applyNamedLayout: (id: NamedLayoutId) => void;
};

export type PlatformCommand = {
  id: string;
  label: string;
  keywords: string[];
  group: CommandGroup;
  run: (ctx: CommandRunContext) => void;
};

export const LABORATORIO_PATH = "/backtests" as const;

export const PLATFORM_COMMANDS: PlatformCommand[] = [
  {
    id: "nav-hoy",
    label: `Ir a ${MESA_LABEL}`,
    keywords: ["hoy", "mesa", "inbox", "briefing"],
    group: "nav",
    run: (ctx) => ctx.navigate(MESA_PATH),
  },
  {
    id: "nav-mercado",
    label: `Ir a ${MERCADO_LABEL}`,
    keywords: ["mercado", "trading", "terminal", "grafico"],
    group: "nav",
    run: (ctx) => ctx.navigate(MERCADO_PATH),
  },
  {
    id: "nav-cartera",
    label: `Ir a ${CARTERA_LABEL}`,
    keywords: ["cartera", "posiciones", "libro", "portfolio"],
    group: "nav",
    run: (ctx) => ctx.navigate(CARTERA_POSICIONES_PATH),
  },
  {
    id: "nav-asesor",
    label: `Ir a ${ASESOR_LABEL}`,
    keywords: ["asesor", "research", "dictamen", "ledger"],
    group: "nav",
    run: (ctx) => ctx.navigate(ASESOR_PATH),
  },
  {
    id: "nav-laboratorio",
    label: `Ir a ${LABORATORIO_LABEL}`,
    keywords: ["laboratorio", "backtests", "lab", "estrategia"],
    group: "nav",
    run: (ctx) => ctx.navigate(LABORATORIO_PATH),
  },
  {
    id: "nav-confirmar",
    label: `Ir a ${CONFIRMAR_LABEL}`,
    keywords: ["confirmar", "firma", "confirm", "f3"],
    group: "nav",
    run: (ctx) => ctx.navigate(CONFIRM_PATH),
  },
  {
    id: "config-general",
    label: "Abrir Configuración",
    keywords: ["config", "ajustes", "preferencias", "settings"],
    group: "config",
    run: (ctx) => ctx.openPlatformConfig("general"),
  },
  {
    id: "config-notifications",
    label: "Abrir Notificaciones",
    keywords: ["notificaciones", "alertas", "toasts"],
    group: "config",
    run: (ctx) => ctx.openPlatformConfig("notifications"),
  },
  {
    id: "config-investor-profile",
    label: "Abrir Perfil inversor",
    keywords: ["perfil", "inversor", "encaja", "suitability"],
    group: "config",
    run: (ctx) => ctx.openPlatformConfig("investor-profile"),
  },
  {
    id: "density-comfortable",
    label: "Densidad: Comfortable",
    keywords: ["densidad", "comfortable", "espaciado", "ui"],
    group: "density",
    run: (ctx) => ctx.setUiDensity("comfortable"),
  },
  {
    id: "density-compact",
    label: "Densidad: Compact",
    keywords: ["densidad", "compact", "compacta", "ui"],
    group: "density",
    run: (ctx) => ctx.setUiDensity("compact"),
  },
  {
    id: "density-toggle",
    label: "Alternar densidad",
    keywords: ["densidad", "toggle", "alternar", "ui"],
    group: "density",
    run: (ctx) => ctx.setUiDensity(nextUiDensity(ctx.uiDensity)),
  },
  {
    id: "theme-dark",
    label: "Tema: Oscuro",
    keywords: ["tema", "oscuro", "dark", "theme"],
    group: "theme",
    run: (ctx) => ctx.setUiTheme("dark"),
  },
  {
    id: "theme-light",
    label: "Tema: Claro",
    keywords: ["tema", "claro", "light", "theme"],
    group: "theme",
    run: (ctx) => ctx.setUiTheme("light"),
  },
  {
    id: "theme-system",
    label: "Tema: Sistema",
    keywords: ["tema", "sistema", "system", "theme", "os"],
    group: "theme",
    run: (ctx) => ctx.setUiTheme("system"),
  },
  {
    id: "theme-toggle",
    label: "Alternar tema",
    keywords: ["tema", "toggle", "alternar", "theme"],
    group: "theme",
    run: (ctx) => ctx.setUiTheme(nextUiTheme(ctx.uiTheme)),
  },
  {
    id: "layout-simple",
    label: "Layout: Simple",
    keywords: ["layout", "simple", "paneles", "dock", "mercado"],
    group: "layout",
    run: (ctx) => ctx.applyNamedLayout("simple"),
  },
  {
    id: "layout-trader",
    label: "Layout: Trader",
    keywords: ["layout", "trader", "paneles", "dock", "mercado", "terminal"],
    group: "layout",
    run: (ctx) => ctx.applyNamedLayout("trader"),
  },
  {
    id: "layout-analista",
    label: "Layout: Analista",
    keywords: ["layout", "analista", "paneles", "dock", "mercado", "listas"],
    group: "layout",
    run: (ctx) => ctx.applyNamedLayout("analista"),
  },
];

function normalizeQuery(query: string): string {
  return query.trim().toLowerCase().normalize("NFD").replace(/\p{M}/gu, "");
}

/**
 * Filtra comandos por label + keywords (acentos ignorados).
 * Query vacía → todos, en orden del registry.
 */
export function filterCommands(
  query: string,
  commands: PlatformCommand[] = PLATFORM_COMMANDS,
): PlatformCommand[] {
  const q = normalizeQuery(query);
  if (!q) return [...commands];
  return commands.filter((cmd) => {
    const haystack = normalizeQuery(
      [cmd.label, ...cmd.keywords, cmd.id].join(" "),
    );
    return haystack.includes(q);
  });
}
