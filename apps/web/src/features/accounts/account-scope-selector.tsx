import { cn } from "@/lib/utils";
import {
  ACCOUNT_ORIGIN_LABEL,
  accountOriginKind,
  isDailyTradingAccount,
} from "@bolsa/shared";
import {
  accountTypeShortLabel,
  useActivateAccount,
  useActiveAccount,
} from "@/features/accounts/use-active-account";

type AccountScopeSelectorProps = {
  compact?: boolean;
  /** Oculta la etiqueta «Activa» (p. ej. cuando la barra ya la muestra). */
  hideLabel?: boolean;
  className?: string;
};

/** Selector de la cuenta Activa (persiste al cerrar/reabrir la app). */
export function AccountScopeSelector({
  compact = false,
  hideLabel = false,
  className,
}: AccountScopeSelectorProps) {
  const { account, effectiveAccountId, accounts } = useActiveAccount();
  const activate = useActivateAccount();

  // V1.21 — selector diario = demos operativas; Lab paper vive en Admin → Cuentas.
  const openAccounts = accounts.filter(isDailyTradingAccount);
  if (openAccounts.length === 0) return null;

  const selectClass = compact
    ? "max-w-[9rem] truncate rounded border border-border bg-background px-1 py-0 text-[10px] text-foreground"
    : "rounded-md border border-border bg-background px-2 py-1.5 text-sm";

  return (
    <label className={cn("flex items-center gap-1", className)}>
      {!hideLabel && (
        <span
          className={cn(
            "shrink-0 text-muted-foreground/80",
            compact ? "text-[10px]" : "text-xs text-muted-foreground",
          )}
          title="Cuenta con la que opera la app. Se restaura al volver a abrirla."
        >
          {compact ? "Activa:" : "Cuenta activa"}
        </span>
      )}
      <select
        value={
          effectiveAccountId &&
          openAccounts.some((a) => a.id === effectiveAccountId)
            ? effectiveAccountId
            : (openAccounts[0]?.id ?? "")
        }
        disabled={activate.isPending}
        onChange={(e) => {
          const id = e.target.value;
          if (id) void activate.mutateAsync(id);
        }}
        className={selectClass}
        aria-label="Cambiar cuenta activa"
        data-testid="account-scope-selector"
        title={
          account
            ? `Cambiar cuenta (ahora: «${account.name}»)`
            : "Cambiar cuenta activa"
        }
      >
        {openAccounts.map((item) => {
          const origin = accountOriginKind(item);
          const originTag =
            origin === "seed" ? ` · ${ACCOUNT_ORIGIN_LABEL.seed}` : "";
          return (
            <option key={item.id} value={item.id}>
              {accountTypeShortLabel(item.type)} · {item.name}
              {originTag}
            </option>
          );
        })}
      </select>
    </label>
  );
}
