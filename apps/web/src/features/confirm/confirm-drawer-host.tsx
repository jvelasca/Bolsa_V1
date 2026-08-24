/**
 * Host del slide-over Confirmar (U3). Escucha `bolsa:confirm-drawer`.
 * Embebe el mismo flujo SEMI que `/confirm` (preview → firma humana).
 */

import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { SlideOver } from "@/components/ui/slide-over";
import { ConfirmContent } from "@/features/confirm/confirm-content";
import {
  BOLSA_CONFIRM_DRAWER_EVENT,
  closeConfirmDrawer,
  isConfirmDrawerCloseDetail,
  isConfirmDrawerOpenDetail,
} from "@/features/confirm/confirm-drawer";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";

export function ConfirmDrawerHost() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();

  const onClose = useCallback(() => {
    setOpen(false);
    closeConfirmDrawer();
  }, []);

  useEffect(() => {
    const onEvent = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (isConfirmDrawerOpenDetail(detail)) {
        setOpen(true);
        return;
      }
      if (isConfirmDrawerCloseDetail(detail)) {
        setOpen(false);
      }
    };
    window.addEventListener(BOLSA_CONFIRM_DRAWER_EVENT, onEvent);
    return () =>
      window.removeEventListener(BOLSA_CONFIRM_DRAWER_EVENT, onEvent);
  }, []);

  // En la página completa el drawer sobra.
  useEffect(() => {
    if (pathname === CONFIRM_PATH && open) {
      setOpen(false);
    }
  }, [pathname, open]);

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title="Confirmar"
      description="Firma aquí sin salir de la mesa. Mismo flujo SEMI que la página Confirmar."
      widthClassName="max-w-xl sm:max-w-2xl"
      testId="confirm-drawer"
    >
      <ConfirmContent compact showFullPageLink onFullPageNavigate={onClose} />
    </SlideOver>
  );
}
