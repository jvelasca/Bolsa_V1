/**
 * Barra superior de la plataforma (nav + cluster derecha).
 *
 * Izquierda: historial ←→ · separador · nav L1 (Hoy · Mercado · Cartera · Asesor · Laboratorio)
 *   · paneles Mercado (cuando aplica).
 * Derecha (L→R): 🔔 · chip universo · cuenta activa · espacio · Ayuda · Config · menú sesión.
 * Logo / Overview / Cuentas / Fiscal / Consola → AdminRail (no ⚙).
 *
 * @see docs/adr/040-user-information-architecture.md
 * @see docs/adr/041-operational-coherence.md
 * @see docs/WORKSPACE_PERSISTENCE.md §0
 * @see docs/UI_PLATFORM.md — Barra superior / espacios
 */
import type { ComponentType } from "react";
import { useEffect, useRef, useState } from "react";
import {
  NavLink,
  NavigationType,
  useLocation,
  useNavigate,
  useNavigationType,
} from "react-router-dom";
import {
  Bell,
  Briefcase,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FlaskConical,
  LayoutGrid,
  LineChart,
  List,
  Microscope,
  PanelBottom,
  PanelRight,
  RotateCcw,
  Settings,
  SquareArrowOutUpRight,
  User,
} from "lucide-react";
import { AppHelpMenu } from "@/features/help/app-help-menu";
import { UniverseChip } from "@/features/platform/universe-chip";
import { AccountScopeSelector } from "@/features/accounts/account-scope-selector";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { useUiStore } from "@/stores/ui-store";
import { useTradingLayoutStore } from "@/stores/trading-layout-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useAsesorAlarmaBadge } from "@/features/research/use-asesor-alarma-badge";
import {
  confirmNavAriaLabel,
  formatConfirmNavBadge,
} from "@/features/confirm/confirm-nav";
import {
  ASESOR_LABEL,
  ASESOR_PATH,
  ASESOR_TESIS_HINT,
  CARTERA_LABEL,
  CARTERA_NAV,
  LABORATORIO_LABEL,
  MERCADO_LABEL,
  MERCADO_NAV,
  MESA_LABEL,
  MESA_PATH,
} from "@/features/confirm/daily-nav";
import { useListAutoActivityStore } from "@/stores/list-auto-activity-store";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";
import { isTradingRoute } from "@/lib/routes";

/** Historial SPA para habilitar ← / → en la barra (cualquier ruta / query). */
function useSpaHistoryNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const navType = useNavigationType();
  const stackRef = useRef<string[]>([]);
  const posRef = useRef(-1);
  const [canGoBack, setCanGoBack] = useState(false);
  const [canGoForward, setCanGoForward] = useState(false);

  const href = `${location.pathname}${location.search}`;

  useEffect(() => {
    const stack = stackRef.current;
    const entry = href;

    if (stack.length === 0) {
      stack.push(entry);
      posRef.current = 0;
    } else if (navType === NavigationType.Pop) {
      const found = stack.lastIndexOf(entry);
      if (found >= 0) {
        posRef.current = found;
      } else if (stack[posRef.current] !== entry) {
        stack.length = Math.max(0, posRef.current) + 1;
        stack.push(entry);
        posRef.current = stack.length - 1;
      }
    } else if (navType === NavigationType.Replace) {
      if (posRef.current >= 0) {
        stack[posRef.current] = entry;
        stack.length = posRef.current + 1;
      } else {
        stack.push(entry);
        posRef.current = 0;
      }
    } else if (stack[posRef.current] !== entry) {
      stack.length = posRef.current + 1;
      stack.push(entry);
      posRef.current = stack.length - 1;
    }

    setCanGoBack(posRef.current > 0);
    setCanGoForward(posRef.current < stack.length - 1);
  }, [href, navType]);

  return {
    canGoBack,
    canGoForward,
    goBack: () => {
      if (posRef.current > 0) navigate(-1);
    },
    goForward: () => {
      if (posRef.current < stackRef.current.length - 1) navigate(1);
    },
  };
}

interface MenuItem {
  label: string;
  action?: () => void;
  href?: string;
  separator?: boolean;
  checked?: boolean;
  disabled?: boolean;
  hint?: string;
}

/** Duplica la URL actual en otra pestaña (p. ej. segundo monitor). */
function OpenAppInNewTabButton({ className }: { className?: string }) {
  return (
    <button
      type="button"
      title="Abrir esta vista en otra pestaña (segundo monitor)"
      aria-label="Abrir en otra pestaña"
      onClick={() => {
        window.open(window.location.href, "_blank", "noopener,noreferrer");
      }}
      className={cn(
        "rounded p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground",
        className,
      )}
    >
      <SquareArrowOutUpRight className="h-3.5 w-3.5" />
    </button>
  );
}

function DropdownMenu({
  label,
  icon: Icon,
  items,
  align = "right",
  navStyle = false,
  active = false,
  iconOnly = false,
}: {
  label: string;
  icon?: ComponentType<{ className?: string }>;
  items: MenuItem[];
  align?: "left" | "right";
  navStyle?: boolean;
  active?: boolean;
  iconOnly?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center gap-1 rounded-md px-2 py-1.5 text-sm hover:bg-accent",
          navStyle && "gap-1.5 px-2.5 py-1.5 font-medium",
          navStyle && active && "bg-accent text-primary",
          iconOnly && "px-1.5",
        )}
        title={label}
        aria-label={label}
      >
        {Icon ? <Icon className="h-4 w-4 shrink-0" /> : null}
        {navStyle ? (
          <span className="hidden md:inline">{label}</span>
        ) : iconOnly ? null : (
          !Icon && label
        )}
        {!iconOnly && <ChevronDown className="h-3.5 w-3.5 opacity-60" />}
      </button>
      {open && (
        <div
          className={cn(
            "absolute top-full z-50 min-w-[200px] rounded-md border border-border bg-card py-1 shadow-xl",
            align === "left" ? "left-0" : "right-0",
          )}
        >
          {items.map((item, index) =>
            item.separator ? (
              <div
                key={`sep-${index}`}
                className="my-1 border-t border-border"
              />
            ) : (
              <button
                key={item.label}
                type="button"
                disabled={item.disabled}
                className="flex w-full flex-col px-3 py-1.5 text-left text-sm hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => {
                  if (item.disabled) return;
                  setOpen(false);
                  if (item.href) navigate(item.href);
                  item.action?.();
                }}
              >
                <span className="flex w-full items-center justify-between">
                  <span>{item.label}</span>
                  {item.checked != null && (
                    <span className="text-xs text-muted-foreground">
                      {item.checked ? "✓" : ""}
                    </span>
                  )}
                </span>
                {item.hint && (
                  <span className="text-xs text-muted-foreground">
                    {item.hint}
                  </span>
                )}
              </button>
            ),
          )}
        </div>
      )}
    </div>
  );
}

/** L1 — cinco conceptos de usuario (ADR-040). */
const HOY_NAV = {
  to: MESA_PATH,
  label: MESA_LABEL,
  icon: LayoutGrid,
} as const;

const MERCADO_MENU: MenuItem[] = MERCADO_NAV.items.map((item) => ({
  label: item.label,
  href: item.href,
  hint: item.hint,
}));

const CARTERA_MENU: MenuItem[] = CARTERA_NAV.items.map((item) => ({
  label: item.label,
  href: item.href,
  hint: item.hint,
}));

const BACKTESTING_MENU: MenuItem[] = [
  {
    label: "Probar estrategia",
    href: "/backtests?tab=run",
    hint: "Simulación sobre un valor y un periodo",
  },
  {
    label: "Biblioteca",
    href: "/backtests?tab=strategies",
    hint: "Genéricas, mías y finalistas",
  },
  {
    label: "Lab · Optimizar",
    href: "/backtests?tab=jobs",
    hint: "Mismo Lab del embudo Coach",
  },
  {
    label: "Pruebas anteriores",
    href: "/backtests?tab=history",
    hint: "Runs guardados · tope ⚙",
  },
];

const RESEARCH_MENU: MenuItem[] = [
  {
    label: "Resumen",
    href: `${ASESOR_PATH}?tab=dashboard`,
    hint: ASESOR_TESIS_HINT,
  },
  { label: "Diario", href: `${ASESOR_PATH}?tab=diario` },
  { label: "Historial", href: `${ASESOR_PATH}?tab=history` },
  { label: "Opiniones", href: `${ASESOR_PATH}?tab=opiniones` },
];

export function AppTopBar() {
  const location = useLocation();
  const isBacktestsRoute = location.pathname.startsWith("/backtests");
  const isResearchRoute = location.pathname.startsWith("/research");
  const isHoyRoute = location.pathname.startsWith("/mesa");
  const searchParams = new URLSearchParams(location.search);
  const isCarteraRoute =
    location.pathname.startsWith("/history") ||
    (isHoyRoute &&
      (searchParams.get("view") === "posiciones" ||
        searchParams.get("focus") === "libro"));
  const isMercadoRoute =
    isTradingRoute(location.pathname) ||
    location.pathname.startsWith("/screeners") ||
    location.pathname.startsWith("/instruments") ||
    location.pathname.startsWith("/alerts");
  const trading = isTradingRoute(location.pathname);
  const historyNav = useSpaHistoryNav();

  const clearSession = useAuthStore((s) => s.clearSession);
  const openWorkspacePicker = useUiStore((s) => s.openWorkspacePicker);
  const openPlatformConfig = useUiStore((s) => s.openPlatformConfig);
  const workspace = useWorkspaceStore((s) => s.workspace);
  const isDirty = useWorkspaceStore((s) => s.isDirty);
  const isSaving = useWorkspaceStore((s) => s.isSaving);

  const layout = useTradingLayoutStore();
  const asesorAlarmaBadge = useAsesorAlarmaBadge();
  const confirmQueueCount = useSupervisedF3QueueStore((s) => s.items.length);
  const confirmBadge = formatConfirmNavBadge(confirmQueueCount);
  const listAutoActive = useListAutoActivityStore((s) => s.active);
  const listAutoSummary = useListAutoActivityStore((s) => s.summary);

  const sessionMenu: MenuItem[] = [
    {
      label: "Notificaciones…",
      action: () => openPlatformConfig("notifications"),
    },
    {
      label: "Configuración…",
      action: () => openPlatformConfig("general"),
    },
    { label: "Cerrar sesión", action: clearSession },
  ];

  const configMenu: MenuItem[] = [
    {
      label: "Preferencias…",
      action: () => openPlatformConfig("general"),
      hint: "Interfaz, notificaciones, datos, trading",
    },
    {
      label: "Perfil inversor…",
      action: () => openPlatformConfig("investor-profile"),
    },
    {
      label: "Notificaciones…",
      action: () => openPlatformConfig("notifications"),
    },
    {
      label: "Confirmaciones…",
      action: () => openPlatformConfig("confirmations"),
    },
    { separator: true, label: "sep-cfg-adv" },
    {
      label: "Datos / BD…",
      action: () => openPlatformConfig("bd"),
    },
    {
      label: "Sync / proveedores…",
      action: () => openPlatformConfig("other"),
    },
  ];

  return (
    <header className="flex h-12 shrink-0 items-center gap-1 border-b border-border bg-card/90 px-2">
      <div
        className="flex items-center gap-0.5 rounded-md border border-border/70 bg-background/40 p-0.5"
        role="group"
        aria-label="Historial de navegación"
      >
        <button
          type="button"
          title="Atrás (historial)"
          aria-label="Atrás"
          disabled={!historyNav.canGoBack}
          onClick={historyNav.goBack}
          className={cn(
            "rounded-md p-1.5 transition-colors",
            historyNav.canGoBack
              ? "border border-border/80 bg-background text-foreground shadow-sm hover:bg-accent"
              : "text-muted-foreground/50 opacity-50",
            "disabled:pointer-events-none",
          )}
        >
          <ChevronLeft className="h-4 w-4" strokeWidth={2.25} />
        </button>
        <button
          type="button"
          title="Adelante (historial)"
          aria-label="Adelante"
          disabled={!historyNav.canGoForward}
          onClick={historyNav.goForward}
          className={cn(
            "rounded-md p-1.5 transition-colors",
            historyNav.canGoForward
              ? "border border-border/80 bg-background text-foreground shadow-sm hover:bg-accent"
              : "text-muted-foreground/50 opacity-50",
            "disabled:pointer-events-none",
          )}
        >
          <ChevronRight className="h-4 w-4" strokeWidth={2.25} />
        </button>
      </div>

      <div className="mx-1.5 h-5 w-px shrink-0 bg-border sm:mx-2" aria-hidden />

      <nav className="flex items-center gap-0.5" aria-label="Principal">
        <NavLink
          to={HOY_NAV.to}
          end
          className={({ isActive }) =>
            cn(
              "relative flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium hover:bg-accent",
              (isActive || isHoyRoute) && "bg-accent text-primary",
            )
          }
          title={
            confirmQueueCount > 0
              ? `${confirmQueueCount} pendientes de firma`
              : "¿Qué debo hacer hoy?"
          }
        >
          <HOY_NAV.icon className="h-4 w-4 shrink-0" />
          <span className="hidden lg:inline">{HOY_NAV.label}</span>
          {confirmBadge ? (
            <span
              className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold leading-none text-primary-foreground"
              aria-label={confirmNavAriaLabel(confirmQueueCount)}
            >
              {confirmBadge}
            </span>
          ) : null}
        </NavLink>

        <DropdownMenu
          label={MERCADO_LABEL}
          icon={LineChart}
          items={MERCADO_MENU}
          align="left"
          navStyle
          active={isMercadoRoute && !isHoyRoute}
        />

        <DropdownMenu
          label={CARTERA_LABEL}
          icon={Briefcase}
          items={CARTERA_MENU}
          align="left"
          navStyle
          active={isCarteraRoute}
        />

        <div className="relative">
          <DropdownMenu
            label={ASESOR_LABEL}
            icon={Microscope}
            items={RESEARCH_MENU}
            align="left"
            navStyle
            active={isResearchRoute}
          />
          {asesorAlarmaBadge > 0 ? (
            <span
              className="pointer-events-none absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-semibold leading-none text-white"
              title={`${asesorAlarmaBadge} alarma${asesorAlarmaBadge === 1 ? "" : "s"} de dictamen`}
              aria-label={`${asesorAlarmaBadge} alarmas de dictamen`}
            >
              {asesorAlarmaBadge > 9 ? "9+" : asesorAlarmaBadge}
            </span>
          ) : null}
        </div>

        <div className="relative">
          <DropdownMenu
            label={LABORATORIO_LABEL}
            icon={FlaskConical}
            items={BACKTESTING_MENU}
            align="left"
            navStyle
            active={isBacktestsRoute}
          />
          {listAutoActive ? (
            <span
              className="pointer-events-none absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-600 px-1 text-[10px] font-semibold leading-none text-white"
              title={listAutoSummary ?? "Lista AUTO en curso"}
              aria-label={listAutoSummary ?? "Lista AUTO en curso"}
            >
              …
            </span>
          ) : null}
        </div>
      </nav>

      {trading ? (
        <>
          <div
            className="mx-2 hidden h-5 w-px bg-border sm:block"
            aria-hidden
          />
          <div
            className="flex items-center gap-0.5 rounded-md border border-border/70 bg-background/40 p-0.5"
            role="group"
            aria-label="Paneles Mercado"
          >
            <button
              type="button"
              title={
                layout.listsOpen ? "Ocultar watchlist" : "Mostrar watchlist"
              }
              onClick={layout.toggleLists}
              className={cn(
                "rounded p-1.5 hover:bg-accent",
                layout.listsOpen && "bg-accent text-primary",
              )}
            >
              <List className="h-4 w-4" />
            </button>
            <button
              type="button"
              title={
                layout.operationsOpen
                  ? "Ocultar operaciones"
                  : "Mostrar operaciones"
              }
              onClick={layout.toggleOperations}
              className={cn(
                "rounded p-1.5 hover:bg-accent",
                layout.operationsOpen && "bg-accent text-primary",
              )}
            >
              <PanelBottom className="h-4 w-4" />
            </button>
            <button
              type="button"
              title={
                layout.operativaOpen ? "Ocultar operativa" : "Mostrar operativa"
              }
              onClick={layout.toggleOperativa}
              className={cn(
                "rounded p-1.5 hover:bg-accent",
                layout.operativaOpen && "bg-accent text-primary",
              )}
            >
              <PanelRight className="h-4 w-4" />
            </button>
            <div className="mx-0.5 h-4 w-px bg-border/80" aria-hidden />
            <button
              type="button"
              title="Restablecer paneles (watchlist / operaciones / operativa)"
              onClick={layout.resetLayout}
              className="rounded p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
            <span className="w-1.5 shrink-0" aria-hidden />
            <div className="h-4 w-px bg-border/80" aria-hidden />
            <OpenAppInNewTabButton />
          </div>
        </>
      ) : (
        <>
          <div
            className="mx-2 hidden h-5 w-px bg-border sm:block"
            aria-hidden
          />
          <OpenAppInNewTabButton className="border border-border/70 bg-background/40" />
        </>
      )}

      <div className="ml-auto flex items-center gap-1">
        <NavLink
          to="/alerts"
          className={({ isActive }) =>
            cn(
              "rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground",
              isActive && "bg-accent text-primary",
            )
          }
          title="Alertas"
          aria-label="Alertas"
        >
          <Bell className="h-4 w-4" />
        </NavLink>
        <UniverseChip density="icon" />
        <AccountScopeSelector compact hideLabel className="hidden sm:flex" />
        <button
          type="button"
          onClick={openWorkspacePicker}
          title="Espacio de trabajo — gestionar, guardar y exportar"
          className={cn(
            "flex max-w-[200px] items-center gap-1.5 rounded-md border px-2 py-1 text-left text-xs transition-colors hover:bg-accent",
            isDirty && !isSaving
              ? "border-amber-500/40 bg-amber-500/5"
              : "border-border bg-background/60",
          )}
        >
          <span className="hidden truncate font-medium text-foreground sm:inline">
            {workspace.name}
          </span>
          <span className="truncate text-muted-foreground sm:hidden">
            Espacio
          </span>
          {isSaving ? (
            <span className="shrink-0 text-[10px] text-sky-400">
              Guardando…
            </span>
          ) : isDirty ? (
            <span className="shrink-0 text-[10px] text-amber-500">•</span>
          ) : null}
          <ChevronDown className="h-3 w-3 shrink-0 opacity-50" />
        </button>
        <AppHelpMenu />
        <DropdownMenu
          label="Configuración"
          icon={Settings}
          items={configMenu}
          iconOnly
        />
        <DropdownMenu label="Sesión" icon={User} items={sessionMenu} iconOnly />
      </div>
    </header>
  );
}
