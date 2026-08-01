import { Dialog } from '@/components/ui/dialog';
import type { InvestmentAccountDto } from '@bolsa/shared';
import { AccountSettingsPanel } from './account-settings-panel';

interface AccountSettingsDialogProps {
  account: InvestmentAccountDto | null;
  open: boolean;
  onClose: () => void;
}

export function AccountSettingsDialog({ account, open, onClose }: AccountSettingsDialogProps) {
  if (!account) return null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Configuración de cuenta"
      description={`Perfil inversor, comisiones y fiscal de «${account.name}»`}
      className="max-w-2xl"
    >
      <AccountSettingsPanel
        accountId={account.id}
        currency={account.currency}
        settings={account.settings}
        activeProfileId={account.activeProfileId}
        onSaved={onClose}
      />
    </Dialog>
  );
}
