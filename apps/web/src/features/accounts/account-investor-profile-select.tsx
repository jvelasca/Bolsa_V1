/**
 * Selector del perfil inversor activo de UNA cuenta.
 *
 * Es la ÚNICA superficie de asignación (Cuentas → ficha → Configuración). El catálogo se
 * gestiona en Configuración → Perfil inversor; aquí solo se elige y se aplica.
 * No crea perfiles al montarse: si el catálogo está vacío, se enlaza al catálogo.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type { SuggestablePolicyTemplateId } from "@bolsa/shared";
import { POLICY_TEMPLATE_LABELS } from "@bolsa/shared";
import {
  InvestorProfilePicker,
  profileUsageByAccount,
} from "@/features/accounts/investor-profile-picker";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";

interface AccountInvestorProfileSelectProps {
  accountId: string;
  activeProfileId?: string | null;
  disabled?: boolean;
  className?: string;
  /** Mostrar enlace al catálogo (Configuración → Perfil inversor). */
  showCatalogLink?: boolean;
}

function templateLabelOf(profile: {
  selectedPolicyTemplateId: string;
}): string {
  return (
    POLICY_TEMPLATE_LABELS[
      profile.selectedPolicyTemplateId as SuggestablePolicyTemplateId
    ] ?? profile.selectedPolicyTemplateId
  );
}

export function AccountInvestorProfileSelect({
  accountId,
  activeProfileId,
  disabled = false,
  className,
  showCatalogLink = true,
}: AccountInvestorProfileSelectProps) {
  const queryClient = useQueryClient();
  const [pendingId, setPendingId] = useState("");
  const [confirmingClear, setConfirmingClear] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const listQuery = useQuery({
    queryKey: ["investor-profiles"],
    queryFn: async () => (await api.listInvestorProfiles()).data,
  });

  const accountsQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.getAccounts()).data,
  });

  useEffect(() => {
    // Al cambiar de cuenta, se descarta cualquier selección pendiente y la confirmación.
    setPendingId("");
    setConfirmingClear(false);
    setError(null);
  }, [accountId, activeProfileId]);

  const assignMutation = useMutation({
    mutationFn: (profileId: string | null) =>
      api.assignAccountProfile(accountId, profileId),
    onSuccess: () => {
      setError(null);
      setPendingId("");
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      void queryClient.invalidateQueries({
        queryKey: ["account-summary", accountId],
      });
    },
    onError: (err: Error) => setError(err.message),
  });

  /**
   * Desasignación explícita (AUD-01). Es una operación DISTINTA de «cambiar perfil»:
   * envía ``{"profileId": null}`` y NO bootstrap-ea ni asigna el perfil por defecto,
   * así que el resultado real en servidor es ``active_profile_id = NULL``.
   */
  const clearMutation = useMutation({
    mutationFn: () => api.assignAccountProfile(accountId, null),
    onSuccess: () => {
      setError(null);
      setPendingId("");
      setConfirmingClear(false);
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      void queryClient.invalidateQueries({
        queryKey: ["account-summary", accountId],
      });
    },
    onError: (err: Error) => setError(err.message),
  });

  const profiles = listQuery.data ?? [];
  const active = profiles.find((p) => p.profileId === activeProfileId) ?? null;
  const selectedId = pendingId || (activeProfileId ?? "");
  const pending = profiles.find((p) => p.profileId === pendingId) ?? null;
  const usage = useMemo(
    () => profileUsageByAccount(accountsQuery.data ?? []),
    [accountsQuery.data],
  );
  const pendingUsedBy = pendingId ? (usage[pendingId] ?? []) : [];
  const dirty = pendingId !== "" && pendingId !== (activeProfileId ?? "");

  return (
    <div
      className={cn("space-y-2 rounded-md border border-border p-3", className)}
      data-testid="account-investor-profile-select"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-foreground">Perfil inversor</p>
          <p className="text-xs text-muted-foreground">
            Un perfil activo por cuenta. Define la Trading Policy del Policy
            Gate.
          </p>
        </div>
        {showCatalogLink ? (
          <button
            type="button"
            className="shrink-0 text-xs text-primary hover:underline"
            onClick={() =>
              useUiStore.getState().openPlatformConfig("investor-profile")
            }
          >
            Gestionar catálogo →
          </button>
        ) : null}
      </div>

      {active ? (
        <p
          className="text-xs text-muted-foreground"
          data-testid="account-profile-active"
        >
          Activo:{" "}
          <span className="font-medium text-foreground">{active.name}</span>
          {" · "}
          {templateLabelOf(active)}
        </p>
      ) : null}

      {/* CTA-D2: sin catálogo no hay evidencia para decir «legacy» ni «sin perfil». */}
      {!listQuery.isPending && !listQuery.isError && !active ? (
        <p
          className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-amber-800 dark:text-amber-300"
          data-testid="account-profile-missing"
        >
          {activeProfileId
            ? "Esta cuenta apunta a un perfil que no está en tu catálogo (perfil legacy). Elige uno del catálogo y aplícalo para fijarlo."
            : "Esta cuenta no tiene perfil asignado: el Policy Gate aplica moderate por defecto. Elige un perfil del catálogo y aplícalo para fijarlo."}
        </p>
      ) : null}

      <InvestorProfilePicker
        value={selectedId}
        onChange={(next) => setPendingId(next)}
        disabled={
          disabled ||
          listQuery.isLoading ||
          assignMutation.isPending ||
          profiles.length === 0
        }
        usedByAccounts={usage}
        maxHeightClassName="max-h-48"
      />

      {pendingUsedBy.length > 0 ? (
        <p
          className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-800 dark:text-amber-300"
          data-testid="account-profile-shared-warning"
        >
          «{pending?.name}» ya lo usan {pendingUsedBy.length}{" "}
          {pendingUsedBy.length === 1 ? "cuenta" : "cuentas"} (
          {pendingUsedBy.join(", ")}). Compartirán la misma Trading Policy.
        </p>
      ) : null}

      <p className="text-[11px] text-muted-foreground">
        Editar un perfil en Configuración → Perfil inversor cambia la política
        de todas las cuentas que lo usan.
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          data-testid="account-profile-apply"
          disabled={
            !dirty || assignMutation.isPending || clearMutation.isPending
          }
          onClick={() => assignMutation.mutate(pendingId)}
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
        >
          {assignMutation.isPending ? "Guardando…" : "Aplicar a esta cuenta"}
        </button>
        {dirty ? (
          <button
            type="button"
            className="text-xs text-muted-foreground hover:underline"
            onClick={() => setPendingId("")}
            disabled={assignMutation.isPending}
          >
            Cancelar
          </button>
        ) : (
          <span className="text-[11px] text-muted-foreground">
            Elige otro perfil para cambiarlo.
          </span>
        )}
      </div>

      {activeProfileId ? (
        <div className="border-t border-border pt-2">
          {confirmingClear ? (
            <div
              role="alertdialog"
              aria-label="Confirmar quitar el perfil de la cuenta"
              data-testid="account-profile-clear-confirm-block"
              className="space-y-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2"
            >
              <p className="text-xs text-foreground">
                La cuenta quedará{" "}
                <span className="font-medium">sin perfil asignado</span>. El
                Policy Gate seguirá aplicando moderate por defecto; no se
                asignará ningún perfil automáticamente.
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  data-testid="account-profile-clear-confirm"
                  disabled={clearMutation.isPending || disabled}
                  onClick={() => clearMutation.mutate()}
                  className="rounded-md bg-destructive px-3 py-1.5 text-xs font-medium text-destructive-foreground disabled:opacity-50"
                >
                  {clearMutation.isPending ? "Quitando…" : "Sí, quitar perfil"}
                </button>
                <button
                  type="button"
                  data-testid="account-profile-clear-cancel"
                  disabled={clearMutation.isPending}
                  onClick={() => setConfirmingClear(false)}
                  className="text-xs text-muted-foreground hover:underline"
                >
                  Cancelar
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                data-testid="account-profile-clear"
                disabled={
                  disabled ||
                  assignMutation.isPending ||
                  clearMutation.isPending
                }
                onClick={() => setConfirmingClear(true)}
                className="text-xs text-destructive hover:underline disabled:opacity-50"
              >
                Quitar perfil
              </button>
              <span className="text-[11px] text-muted-foreground">
                Deja la cuenta sin perfil (no asigna el perfil por defecto).
              </span>
            </div>
          )}
        </div>
      ) : null}

      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
