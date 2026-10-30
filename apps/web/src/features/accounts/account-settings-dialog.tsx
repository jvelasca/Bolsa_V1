import { Dialog } from "@/components/ui/dialog";
import type { InvestmentAccountDto } from "@bolsa/shared";
import { AccountSettingsPanel } from "./account-settings-panel";

interface AccountSettingsDialogProps {
  account: InvestmentAccountDto | null;
  open: boolean;
  onClose: () => void;
}

export function AccountSettingsDialog({
  account,
  open,
  onClose,
}: AccountSettingsDialogProps) {
  if (!account) return null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Comisiones y fiscal de la cuenta"
      description={`Comisiones y fiscal de «${account.name}». El perfil inversor se asigna en la ficha de la cuenta.`}
      className="max-w-2xl"
    >
      <AccountSettingsPanel
        accountId={account.id}
        currency={account.currency}
        settings={account.settings}
        onSaved={onClose}
      />
    </Dialog>
  );
}
