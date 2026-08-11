import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { InvestmentAccountDto } from "@bolsa/shared";
import { defaultAccountSettings } from "@bolsa/shared";
import { api } from "@/lib/api";
import { useActiveAccountStore } from "@/stores/active-account-store";

function asAccountList(value: unknown): InvestmentAccountDto[] {
  if (Array.isArray(value)) return value as InvestmentAccountDto[];
  // Cache legado: algún queryFn guardó `{ data: Account[] }` bajo la misma key.
  if (
    value &&
    typeof value === "object" &&
    Array.isArray((value as { data?: unknown }).data)
  ) {
    return (value as { data: InvestmentAccountDto[] }).data;
  }
  return [];
}

function pickFallbackAccountId(
  accounts: InvestmentAccountDto[],
): string | null {
  const open = accounts.filter((a) => a.status === "active");
  if (open.length === 0) return null;
  // Prefer last-used mirrored on server (isDefault), else first open account.
  return open.find((a) => a.isDefault)?.id ?? open[0]?.id ?? null;
}

/**
 * Cuenta **Activa**: la única que gobierna la app (Trading, patrimonio, órdenes, Coach…).
 * Premisa 2026-07-31: hoy solo cuentas **DEMO** (`simulated`). Tipo Paper = broker real futuro.
 * @see docs/engineering/account-premises-demo-vs-paper-2026-07-31.md
 *
 * Se guarda en el navegador y se restaura al reabrir. Puedes tener varias demos
 * (p. ej. otro mercado) y cambiar cuál es la Activa.
 *
 * `isDefault` en servidor es solo espejo silencioso de la última Activa
 * (fallback si no hay persistencia local); no es un concepto de UI.
 */
export function useActiveAccount(): {
  account: InvestmentAccountDto | null;
  effectiveAccountId: string | null;
  isLoading: boolean;
  accounts: InvestmentAccountDto[];
} {
  const activeAccountId = useActiveAccountStore((s) => s.activeAccountId);
  const setActiveAccountId = useActiveAccountStore((s) => s.setActiveAccountId);

  const accountsQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.getAccounts()).data,
  });

  const accounts = asAccountList(accountsQuery.data);
  const openAccounts = accounts.filter((a) => a.status === "active");

  const storedStillValid = Boolean(
    activeAccountId && openAccounts.some((a) => a.id === activeAccountId),
  );
  const effectiveAccountId = storedStillValid
    ? activeAccountId
    : pickFallbackAccountId(openAccounts);
  const account = accounts.find((a) => a.id === effectiveAccountId) ?? null;

  useEffect(() => {
    if (accountsQuery.isLoading || accountsQuery.isError) return;
    if (openAccounts.length === 0) {
      if (activeAccountId) setActiveAccountId(null);
      return;
    }
    if (!storedStillValid && effectiveAccountId) {
      setActiveAccountId(effectiveAccountId);
    }
  }, [
    accountsQuery.isLoading,
    accountsQuery.isError,
    openAccounts.length,
    activeAccountId,
    storedStillValid,
    effectiveAccountId,
    setActiveAccountId,
  ]);

  return {
    account,
    effectiveAccountId,
    isLoading: accountsQuery.isLoading,
    accounts,
  };
}

/** Cambia la Activa (persiste local) y refleja en servidor la última usada. */
export function useActivateAccount() {
  const queryClient = useQueryClient();
  const setActiveAccountId = useActiveAccountStore((s) => s.setActiveAccountId);

  return useMutation({
    mutationFn: async (accountId: string) => {
      setActiveAccountId(accountId);
      await api.setDefaultAccount(accountId);
      return accountId;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
  });
}

export function useActiveAccountSettings() {
  const { account, effectiveAccountId, isLoading } = useActiveAccount();
  return {
    settings: account?.settings ?? defaultAccountSettings(),
    currency: account?.currency ?? "EUR",
    accountName: account?.name ?? null,
    effectiveAccountId,
    isLoading,
  };
}

export function accountTypeShortLabel(
  type: InvestmentAccountDto["type"],
): string {
  if (type === "simulated") return "Demo";
  if (type === "paper") return "Paper (futuro · broker)";
  return "Live (reservado)";
}
