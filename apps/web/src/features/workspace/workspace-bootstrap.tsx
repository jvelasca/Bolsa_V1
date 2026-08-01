import { useEffect, useRef } from 'react';
import { useWorkspaceStore } from '@/stores/workspace-store';

/** Carga espacios de trabajo desde la API al arrancar la sesión. */
export function WorkspaceBootstrap() {
  const bootstrap = useWorkspaceStore((s) => s.bootstrapWorkspaces);
  const hydrated = useWorkspaceStore((s) => s.hydrated);
  const started = useRef(false);

  useEffect(() => {
    if (hydrated || started.current) return;
    started.current = true;
    void bootstrap();
  }, [bootstrap, hydrated]);

  return null;
}
