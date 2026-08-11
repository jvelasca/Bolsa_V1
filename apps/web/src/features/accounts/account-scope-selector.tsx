import { cn } from "@/lib/utils";
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

  const openAccounts = accounts.filter((a) => a.status === "active");
  if (openAccounts.length === 0) return null;

  const selectClass = compact
    ? "max-w-[7.5rem] truncate rounded border border-border bg-background px-1 py-0 text-[10px] text-foreground"
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
        value={effectiveAccountId ?? ""}
        disabled={activate.isPending}
        onChange={(e) => {
          const id = e.target.value;
          if (id) void activate.mutateAsync(id);
        }}
        className={selectClass}
        aria-label="Cambiar cuenta activa"
        title={
          account
            ? `Cambiar cuenta (ahora: «${account.name}»)`
            : "Cambiar cuenta activa"
        }
      >
        {openAccounts.map((item) => (
          <option key={item.id} value={item.id}>
            {accountTypeShortLabel(item.type)} · {item.name}
          </option>
        ))}
      </select>
    </label>
  );
}
