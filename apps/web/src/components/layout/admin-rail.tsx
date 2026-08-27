/**
 * AdminRail — barra administrativa colapsable (V1.21).
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
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  Receipt,
  Wrench,
} from "lucide-react";
import {
  OPERATIONAL_CONSOLE_LABEL,
  OPERATIONAL_CONSOLE_PATH,
} from "@/features/confirm/daily-nav";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "bolsa-admin-rail-collapsed";

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

function loadCollapsed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return true;
  }
}

export function AdminRail() {
  const [collapsed, setCollapsed] = useState(loadCollapsed);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  return (
    <aside
      className={cn(
        "flex shrink-0 flex-col border-r border-border bg-card/80",
        collapsed ? "w-12" : "w-44",
      )}
      aria-label="Administración"
      data-testid="admin-rail"
      data-collapsed={collapsed ? "1" : "0"}
    >
      <div
        className={cn(
          "flex h-12 items-center border-b border-border px-2",
          collapsed ? "justify-center" : "gap-2",
        )}
      >
        <BarChart3 className="h-5 w-5 shrink-0 text-primary" aria-hidden />
        {!collapsed ? (
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
                collapsed && "justify-center px-1.5",
                isActive && "bg-accent text-primary",
              )
            }
            data-testid={`admin-rail-${item.href.replace(/^\//, "")}`}
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {!collapsed ? <span className="truncate">{item.label}</span> : null}
          </NavLink>
        ))}
      </nav>

      <button
        type="button"
        className="m-1.5 flex items-center justify-center gap-1 rounded-md border border-border/60 px-2 py-1.5 text-[10px] text-muted-foreground hover:bg-accent"
        onClick={() => setCollapsed((v) => !v)}
        aria-expanded={!collapsed}
        aria-label={
          collapsed ? "Expandir administración" : "Colapsar administración"
        }
        data-testid="admin-rail-toggle"
      >
        {collapsed ? (
          <ChevronRight className="h-3.5 w-3.5" />
        ) : (
          <>
            <ChevronLeft className="h-3.5 w-3.5" />
            <span>Admin</span>
          </>
        )}
      </button>
    </aside>
  );
}
