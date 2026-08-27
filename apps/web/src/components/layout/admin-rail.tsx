/**
 * AdminRail — barra administrativa icon-first (V1.21+).
 * Por defecto solo iconos (mínimo ancho); al hover se descolapsa el texto.
 * No es navegación diaria de producto. Overview / Cuentas / Fiscal / Consola.
 *
 * @see docs/adr/040-user-information-architecture.md (enmienda V1.21)
 * @see docs/adr/041-operational-coherence.md
 */

import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Briefcase,
  LayoutDashboard,
  Pin,
  PinOff,
  Receipt,
  Wrench,
} from "lucide-react";
import {
  OPERATIONAL_CONSOLE_LABEL,
  OPERATIONAL_CONSOLE_PATH,
} from "@/features/confirm/daily-nav";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "bolsa-admin-rail-pinned";

const ADMIN_ITEMS = [
  {
    label: "Overview",
    href: "/overview",
    icon: LayoutDashboard,
    hint: "Resumen de cuenta y atajos",
  },
  {
    label: "Cuentas",
    href: "/accounts",
    icon: Briefcase,
    hint: "Hub de cuentas e operativa",
  },
  {
    label: "Fiscal",
    href: "/fiscal",
    icon: Receipt,
    hint: "Plusvalías y ejercicio",
  },
  {
    label: OPERATIONAL_CONSOLE_LABEL,
    href: OPERATIONAL_CONSOLE_PATH,
    icon: Wrench,
    hint: "Diagnóstico operativo",
  },
] as const;

function loadPinned(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function AdminRail() {
  const [pinned, setPinned] = useState(loadPinned);
  const [hovered, setHovered] = useState(false);
  const expanded = pinned || hovered;

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, pinned ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [pinned]);

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
      data-pinned={pinned ? "1" : "0"}
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
        {ADMIN_ITEMS.map((item) => (
          <NavLink
            key={item.href}
            to={item.href}
            title={item.hint}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 rounded-md px-2 py-2 text-xs font-medium text-muted-foreground hover:bg-accent hover:text-foreground",
                !expanded && "justify-center px-1.5",
                isActive && "bg-accent text-primary",
              )
            }
            data-testid={`admin-rail-${item.href.replace(/^\//, "")}`}
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {expanded ? <span className="truncate">{item.label}</span> : null}
          </NavLink>
        ))}
      </nav>

      <button
        type="button"
        className={cn(
          "m-1.5 flex items-center justify-center gap-1 rounded-md border border-border/60 px-2 py-1.5 text-[10px] text-muted-foreground hover:bg-accent",
          expanded && "justify-start",
        )}
        onClick={() => setPinned((v) => !v)}
        aria-pressed={pinned}
        aria-label={
          pinned
            ? "Desanclar administración (solo iconos)"
            : "Anclar administración expandida"
        }
        title={pinned ? "Desanclar" : "Anclar expandido"}
        data-testid="admin-rail-toggle"
      >
        {pinned ? (
          <PinOff className="h-3.5 w-3.5 shrink-0" />
        ) : (
          <Pin className="h-3.5 w-3.5 shrink-0" />
        )}
        {expanded ? (
          <span className="truncate">{pinned ? "Anclado" : "Anclar"}</span>
        ) : null}
      </button>
    </aside>
  );
}
