import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Dialog, DialogTabs, checkboxClassName } from "@/components/ui/dialog";
import { GeneralSettingsSection } from "@/features/settings/general-settings-section";
import { MarketProvidersStatusCard } from "@/features/settings/market-providers-status-card";
import { AccountSettingsPanel } from "@/features/accounts/account-settings-panel";
import { InvestorProfilePanel } from "@/features/accounts/investor-profile-panel";
import {
  useActivateAccount,
  useActiveAccount,
} from "@/features/accounts/use-active-account";
import { SyncSettingsPanel } from "@/features/sync/sync-settings-panel";
import { DatabaseConfigPanel } from "@/features/config/database-config-panel";
import { NotificationsSettingsPanel } from "@/features/config/notifications-settings-panel";
import { ShortcutsSettingsPanel } from "@/features/command-palette/shortcuts-settings-panel";
import { useTradePreferencesStore } from "@/stores/trade-preferences-store";
import { cn } from "@/lib/utils";
import { useUiStore, type PlatformConfigTab } from "@/stores/ui-store";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { POLICY_TEMPLATE_LABELS } from "@bolsa/shared";
import { api } from "@/lib/api";

/** Pestañas con UI real (notificaciones ya no es placeholder). */
const TABS: { id: PlatformConfigTab; label: string }[] = [
  { id: "general", label: "General" },
  { id: "investor-profile", label: "Perfil inversor" },
  { id: "commissions", label: "Comisiones y fiscal" },
  { id: "notifications", label: "Notificaciones" },
  { id: "confirmations", label: "Confirmaciones" },
  { id: "shortcuts", label: "Atajos" },
  { id: "bd", label: "BD" },
  { id: "other", label: "Sync / proveedores" },
];

function AccountSettingsCard() {
  const openWizard = useUiStore((s) => s.openCreateAccountWizard);
  const { account, effectiveAccountId, accounts } = useActiveAccount();
  const activate = useActivateAccount();
  const openAccounts = accounts.filter((a) => a.status === "active");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cuenta activa</CardTitle>
        <CardDescription>
          Es la que usa toda la app (Trading, barra inferior, operaciones). Se
          restaura al reabrir.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <label className="flex flex-col gap-1.5">
          <span className="font-medium">Cuenta activa</span>
          <select
            value={effectiveAccountId ?? ""}
            disabled={activate.isPending || openAccounts.length === 0}
            onChange={(e) => {
              const id = e.target.value;
              if (id) void activate.mutateAsync(id);
            }}
            className="rounded-md border border-border bg-background px-3 py-2"
          >
            {openAccounts.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} ({item.currency})
              </option>
            ))}
          </select>
        </label>

        {account && (
          <div className="rounded-md border border-border bg-muted/20 p-3 text-xs">
            <GeneralProfileSummary activeProfileId={account.activeProfileId} />
            <p className="mt-1">
              <span className="text-muted-foreground">Comisiones:</span>{" "}
              {account.settings?.commission.label ?? "—"}
            </p>
            <p className="mt-1">
              <span className="text-muted-foreground">Fiscal:</span>{" "}
              {account.settings?.tax.jurisdiction ?? "—"} ·{" "}
              {account.settings?.tax.costBasisMethod.toUpperCase() ?? "—"}
            </p>
            <div className="mt-2 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() =>
                  useUiStore.getState().setPlatformConfigTab("investor-profile")
                }
                className="text-primary hover:underline"
              >
                Gestionar catálogo de perfiles →
              </button>
              <button
                type="button"
                onClick={() =>
                  useUiStore.getState().setPlatformConfigTab("commissions")
                }
                className="text-primary hover:underline"
              >
                Comisiones y fiscal de la cuenta →
              </button>
            </div>
          </div>
        )}

        {!account && (
          <p className="text-xs text-muted-foreground">
            No hay cuentas disponibles.
          </p>
        )}

        <button
          type="button"
          onClick={openWizard}
          className="rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
        >
          Nueva demo…
        </button>
      </CardContent>
    </Card>
  );
}

function GeneralProfileSummary({
  activeProfileId,
}: {
  activeProfileId?: string | null;
}) {
  const { data } = useQuery({
    queryKey: ["investor-profiles"],
    queryFn: async () => (await api.listInvestorProfiles()).data,
    enabled: Boolean(activeProfileId),
  });
  const profile = data?.find((p) => p.profileId === activeProfileId);
  const label = profile
    ? `${profile.name} · ${POLICY_TEMPLATE_LABELS[profile.selectedPolicyTemplateId as keyof typeof POLICY_TEMPLATE_LABELS] ?? profile.selectedPolicyTemplateId}`
    : activeProfileId
      ? "Asignado (cargando…)"
      : "Sin perfil asignado";

  return (
    <p>
      <span className="text-muted-foreground">Perfil inversor:</span> {label}
    </p>
  );
}

function ActiveAccountSelect() {
  const { effectiveAccountId, accounts } = useActiveAccount();
  const activate = useActivateAccount();
  const openAccounts = accounts.filter((a) => a.status === "active");

  return (
    <label className="mb-4 flex flex-col gap-1.5 text-sm">
      <span className="font-medium">Cuenta activa</span>
      <select
        value={effectiveAccountId ?? ""}
        disabled={activate.isPending || openAccounts.length === 0}
        onChange={(e) => {
          const id = e.target.value;
          if (id) void activate.mutateAsync(id);
        }}
        className="max-w-md rounded-md border border-border bg-background px-3 py-2"
      >
        {openAccounts.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name} ({item.currency})
          </option>
        ))}
      </select>
    </label>
  );
}

function InvestorProfileTabPanel() {
  const { account, accounts } = useActiveAccount();
  const invalidateAccounts = useQueryClient();

  if (!account) {
    return (
      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground">
          Crea una cuenta de inversión para asignar un perfil del catálogo
          (RFC-008 ART-PROFILE).
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Catálogo de perfiles</CardTitle>
        <CardDescription>
          Catálogo reutilizable: crea/edita perfiles y asígnalos a cada cuenta
          (una cuenta = un perfil activo). También se elige al crear una demo en
          el asistente.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <InvestorProfilePanel
          accountId={account.id}
          activeProfileId={account.activeProfileId}
          accounts={accounts}
          catalogOnly
          onSaved={() => {
            void invalidateAccounts.invalidateQueries({
              queryKey: ["accounts"],
            });
          }}
        />
      </CardContent>
    </Card>
  );
}

function CommissionsTabPanel() {
  const { account } = useActiveAccount();

  if (!account) {
    return (
      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground">
          Crea una cuenta de inversión para configurar comisiones y fiscal
          simulados.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Cuenta: perfil, comisiones y fiscal</CardTitle>
          <CardDescription>
            Elige el perfil inversor de esta cuenta y los parámetros de
            comisiones/fiscal. El Policy Gate usa el perfil seleccionado.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ActiveAccountSelect />
          <AccountSettingsPanel
            accountId={account.id}
            currency={account.currency}
            settings={account.settings}
            activeProfileId={account.activeProfileId}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function ConfirmationsTabPanel() {
  const confirmBeforeTrade = useTradePreferencesStore(
    (s) => s.confirmBeforeTrade,
  );
  const setConfirmBeforeTrade = useTradePreferencesStore(
    (s) => s.setConfirmBeforeTrade,
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Confirmaciones de trading</CardTitle>
        <CardDescription>
          Controla si se muestra un resumen con comisiones antes de ejecutar
          operaciones.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            className={cn(checkboxClassName, "mt-0.5")}
            checked={confirmBeforeTrade}
            onChange={(e) => setConfirmBeforeTrade(e.target.checked)}
          />
          <span>
            <span className="font-medium">Confirmar antes de operar</span>
            <p className="mt-1 text-xs text-muted-foreground">
              Muestra importe, comisiones estimadas (comisión, IVA,
              transmisiones) y total a debitar antes de comprar o vender. Aplica
              en Trading, ficha de instrumento y órdenes limitadas.
            </p>
          </span>
        </label>
        <p className="text-xs text-muted-foreground">
          Próximamente: confirmación al cerrar posiciones, cancelar órdenes y
          borrar dibujos del gráfico.
        </p>
      </CardContent>
    </Card>
  );
}

function ConfigTabPanel({ tab }: { tab: PlatformConfigTab }) {
  switch (tab) {
    case "general":
      return (
        <div className="space-y-4">
          <AccountSettingsCard />
          <GeneralSettingsSection compact />
        </div>
      );
    case "investor-profile":
      return <InvestorProfileTabPanel />;
    case "commissions":
      return <CommissionsTabPanel />;
    case "confirmations":
      return <ConfirmationsTabPanel />;
    case "notifications":
      return <NotificationsSettingsPanel />;
    case "shortcuts":
      return <ShortcutsSettingsPanel />;
    case "bd":
      return <DatabaseConfigPanel />;
    case "other":
      return (
        <div className="space-y-6">
          <p className="text-sm text-muted-foreground">
            Ajustes de sincronización y estado de proveedores. El flujo de datos
            y la plataforma IA están en{" "}
            <span className="text-foreground">Ayuda</span>. Mantenimiento
            PostgreSQL: <span className="text-foreground">BD</span>.
          </p>
          <MarketProvidersStatusCard />
          <Card>
            <CardHeader>
              <CardTitle>Sincronización automática</CardTitle>
              <CardDescription>
                Cola con rate limiting para Yahoo — el worker respeta estos
                valores
              </CardDescription>
            </CardHeader>
            <CardContent>
              <SyncSettingsPanel embedded />
            </CardContent>
          </Card>
        </div>
      );
    case "sounds":
      // Tab reservado (aún sin UI)
      return (
        <div className="space-y-4">
          <AccountSettingsCard />
          <GeneralSettingsSection compact />
        </div>
      );
    default:
      return null;
  }
}

export function PlatformConfigDialog() {
  const open = useUiStore((s) => s.platformConfigOpen);
  const tab = useUiStore((s) => s.platformConfigTab);
  const close = useUiStore((s) => s.closePlatformConfig);
  const setTab = useUiStore((s) => s.setPlatformConfigTab);

  const knownTabs = new Set(TABS.map((t) => t.id));
  const safeTab: PlatformConfigTab = knownTabs.has(tab) ? tab : "general";

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Configuración"
      description="Preferencias editables. Guías y estado de plataforma → Ayuda."
      className="max-w-4xl"
    >
      <DialogTabs
        tabs={TABS}
        active={safeTab}
        onChange={(id) => setTab(id as PlatformConfigTab)}
      />
      <ConfigTabPanel tab={safeTab} />
    </Dialog>
  );
}
