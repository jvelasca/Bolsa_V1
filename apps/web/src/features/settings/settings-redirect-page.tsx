import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useUiStore, type PlatformConfigTab } from '@/stores/ui-store';

const HASH_TO_TAB: Record<string, PlatformConfigTab> = {
  general: 'general',
  'investor-profile': 'investor-profile',
  profile: 'investor-profile',
  commissions: 'commissions',
  notifications: 'notifications',
  'data-capture': 'other',
  'auto-sync': 'other',
  'chart-platform': 'other',
};

/** Redirige a Overview y abre el modal de configuración (reemplaza la página /settings). */
export function SettingsRedirectPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const openPlatformConfig = useUiStore((s) => s.openPlatformConfig);

  useEffect(() => {
    const hash = location.hash.replace('#', '');
    const tab = HASH_TO_TAB[hash] ?? 'general';
    openPlatformConfig(tab);
    navigate('/overview', { replace: true });
  }, [location.hash, navigate, openPlatformConfig]);

  return null;
}
