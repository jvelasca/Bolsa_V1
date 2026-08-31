/**
 * AdminRail — barra administrativa icon-first (V1.21+).
 * Por defecto solo iconos (mínimo ancho); al hover se descolapsa el texto.
 * Chincheta cicla: Auto (hover) → Fijo colapsado → Fijo expandido.
 * No es navegación diaria de producto. Overview / Cuentas / Perfiles /
 * Estadísticas (preparado) / Fiscal / Consola.
 *
 * @see docs/adr/040-user-information-architecture.md (enmienda V1.21)
 * @see docs/adr/041-operational-coherence.md
 */

import { useEffect, useState, type ComponentType } from "react";
import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Briefcase,
  LayoutDashboard,
  PieChart,
  Pin,
  PinOff,
  Receipt,
  UserCircle,
  Wrench,
} from "lucide-react";
import {
  OPERATIONAL_CONSOLE_LABEL,
  OPERATIONAL_CONSOLE_PATH,
} from "@/features/confirm/daily-nav";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";

const STORAGE_KEY = "bolsa-admin-rail-mode";
/** Legacy boolean pin (expanded-only). */
const LEGACY_PIN_KEY = "bolsa-admin-rail-pinned";

export type AdminRailMode = "auto" | "pinned-collapsed" | "pinned-expanded";

const MODE_CYCLE: AdminRailMode[] = [
  "auto",
  "pinned-collapsed",
  "pinned-expanded",
];

type AdminNavItem = {
  kind: "nav";
  id: string;
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  hint: string;
};

type AdminActionItem = {
  kind: "action";
  id: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  hint: string;
  /** Si true, solo preparado (próximamente). */
  stub?: boolean;
  onClick: () => void;
};

type AdminItem = AdminNavItem | AdminActionItem;

const NAV_ITEMS: AdminNavItem[] = [
  {
    kind: "nav",
    id: "overview",
    label: "Overview",
    href: "/overview",
    icon: LayoutDashboard,
    hint: "Resumen de cuenta y atajos",
  },
  {
    kind: "nav",
    id: "accounts",
    label: "Cuentas",
    href: "/accounts",
    icon: Briefcase,
    hint: "Hub de cuentas e operativa",
  },
];

const TRAILING_NAV: AdminNavItem[] = [
  {
    kind: "nav",
    id: "fiscal",
    label: "Fiscal",
    href: "/fiscal",
    icon: Receipt,
    hint: "Plusvalías y ejercicio",
  },
  {
    kind: "nav",
    id: "operational-console",
    label: OPERATIONAL_CONSOLE_LABEL,
    href: OPERATIONAL_CONSOLE_PATH,
    icon: Wrench,
    hint: "Diagnóstico operativo",
  },
];

export function loadAdminRailMode(): AdminRailMode {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (
      raw === "auto" ||
      raw === "pinned-collapsed" ||
      raw === "pinned-expanded"
    ) {
      return raw;
    }
    // Migrate legacy pin: "1" = locked expanded, "0"/null = auto.
    const legacy = localStorage.getItem(LEGACY_PIN_KEY);
    if (legacy === "1") return "pinned-expanded";
    return "auto";
  } catch {
    return "auto";
  }
}

function nextMode(current: AdminRailMode): AdminRailMode {
  const idx = MODE_CYCLE.indexOf(current);
  return MODE_CYCLE[(idx + 1) % MODE_CYCLE.length]!;
}

const railButtonClass = (expanded: boolean, active?: boolean) =>
  cn(
    "flex w-full items-center gap-2 rounded-md px-2 py-2 text-xs font-medium text-muted-foreground hover:bg-accent hover:text-foreground",
    !expanded && "justify-center px-1.5",
    active && "bg-accent text-primary",
  );

function modeChrome(mode: AdminRailMode): {
  ariaLabel: string;
  title: string;
  label: string;
  pinned: boolean;
} {
  switch (mode) {
    case "pinned-collapsed":
      return {
        ariaLabel: "Anclado colapsado — clic para anclar expandido",
        title: "Anclado: solo iconos (sin hover). Clic → expandido fijo",
        label: "Iconos",
        pinned: true,
      };
    case "pinned-expanded":
      return {
        ariaLabel: "Anclado expandido — clic para modo auto (hover)",
        title: "Anclado: expandido. Clic → auto (hover)",
        label: "Expandido",
        pinned: true,
      };
    default:
      return {
        ariaLabel: "Modo auto (hover) — clic para anclar colapsado",
        title: "Auto: se abre al pasar el ratón. Clic → fijar solo iconos",
        label: "Auto",
        pinned: false,
      };
  }
}

export function AdminRail() {
  const [mode, setMode] = useState<AdminRailMode>(loadAdminRailMode);
  const [hovered, setHovered] = useState(false);
  const expanded = mode === "pinned-expanded" || (mode === "auto" && hovered);
  const openPlatformConfig = useUiStore((s) => s.openPlatformConfig);
  const chrome = modeChrome(mode);

  const actionItems: AdminActionItem[] = [
    {
      kind: "action",
      id: "investor-profiles",
      label: "Perfiles",
      icon: UserCircle,
      hint: "Catálogo de perfiles de inversor",
      onClick: () => openPlatformConfig("investor-profile"),
    },
    {
      kind: "action",
      id: "portfolio-stats",
      label: "Estadísticas",
      icon: PieChart,
      hint: "Estadísticas de la cartera en curso (próximamente)",
      stub: true,
      onClick: () => {
        window.alert(
          "Estadísticas de la cartera: próximamente. El acceso queda preparado en esta barra.",
        );
      },
    },
  ];

  const items: AdminItem[] = [...NAV_ITEMS, ...actionItems, ...TRAILING_NAV];

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
      // Keep legacy key in sync for older readers / diagnostics.
      localStorage.setItem(
        LEGACY_PIN_KEY,
        mode === "pinned-expanded" ? "1" : "0",
      );
    } catch {
      /* ignore */
    }
  }, [mode]);

  // Migrate legacy collapsed key once (default was collapsed=true → unpinned).
  useEffect(() => {
    try {
      if (localStorage.getItem("bolsa-admin-rail-collapsed") != null) {
        localStorage.removeItem("bolsa-admin-rail-collapsed");
      }
    } catch {
      /* ignore */
    }
  }, []);

  return (
    <aside
      className={cn(
        "group relative z-30 flex shrink-0 flex-col border-r border-border bg-card/95 transition-[width] duration-150 ease-out",
        expanded ? "w-44" : "w-12",
      )}
      aria-label="Administración"
      data-testid="admin-rail"
      data-collapsed={expanded ? "0" : "1"}
      data-pinned={chrome.pinned ? "1" : "0"}
      data-mode={mode}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocusCapture={() => setHovered(true)}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
          setHovered(false);
        }
      }}
    >
      <div
        className={cn(
          "flex h-12 items-center border-b border-border px-2",
          expanded ? "gap-2" : "justify-center",
        )}
      >
        <BarChart3 className="h-5 w-5 shrink-0 text-primary" aria-hidden />
        {expanded ? (
          <span className="truncate text-sm font-semibold tracking-tight">
            Bolsa
          </span>
        ) : null}
      </div>

      <nav
        className="flex flex-1 flex-col gap-0.5 p-1.5"
        aria-label="Administración"
      >
        {items.map((item) => {
          if (item.kind === "nav") {
            return (
              <NavLink
                key={item.id}
                to={item.href}
                title={item.hint}
                className={({ isActive }) =>
                  railButtonClass(expanded, isActive)
                }
                data-testid={`admin-rail-${item.id}`}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {expanded ? (
                  <span className="truncate">{item.label}</span>
                ) : null}
              </NavLink>
            );
          }

          return (
            <button
              key={item.id}
              type="button"
              title={item.hint}
              onClick={item.onClick}
              className={cn(
                railButtonClass(expanded),
                item.stub && "opacity-80",
              )}
              data-testid={`admin-rail-${item.id}`}
              aria-disabled={item.stub ? true : undefined}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {expanded ? (
                <span className="truncate">
                  {item.label}
                  {item.stub ? (
                    <span className="ml-1 text-[10px] text-muted-foreground">
                      · pronto
                    </span>
                  ) : null}
                </span>
              ) : null}
            </button>
          );
        })}
      </nav>

      <button
        type="button"
        className={cn(
          "m-1.5 flex items-center justify-center gap-1 rounded-md border border-border/60 px-2 py-1.5 text-[10px] text-muted-foreground hover:bg-accent",
          expanded && "justify-start",
        )}
        onClick={() => setMode((m) => nextMode(m))}
        aria-pressed={chrome.pinned}
        aria-label={chrome.ariaLabel}
        title={chrome.title}
        data-testid="admin-rail-toggle"
        data-mode={mode}
      >
        {mode === "auto" ? (
          <Pin className="h-3.5 w-3.5 shrink-0" />
        ) : mode === "pinned-collapsed" ? (
          <Pin className="h-3.5 w-3.5 shrink-0 fill-current" />
        ) : (
          <PinOff className="h-3.5 w-3.5 shrink-0" />
        )}
        {expanded ? <span className="truncate">{chrome.label}</span> : null}
      </button>
    </aside>
  );
}
