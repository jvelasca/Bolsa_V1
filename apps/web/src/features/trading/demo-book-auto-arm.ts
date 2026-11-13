/**
 * A3 — armado local AUTO (doble confirmación) + preferencias.
 * Tras thaw BETA-D: UI on; execute sigue detrás de `PAPER_D_EXECUTE`.
 *
 * REACTIVIDAD: `loadAutoArm()` es una lectura imperativa de `localStorage`. Usarla en
 * render deja el armado congelado hasta el siguiente remount (armar en Ajustes no
 * actualizaba el cockpit). `useAutoArmArmed()` se suscribe al evento que emite
 * `saveAutoArm` y al evento `storage` (otra pestaña), con snapshot booleano estable.
 */

import { useSyncExternalStore } from "react";

export const DEMO_BOOK_AUTO_ARM_KEY = "bolsa-demo-book-auto-arm-v1";
/** Evento local emitido al guardar/desarmar (misma pestaña). */
export const DEMO_BOOK_AUTO_ARM_EVENT = "bolsa-demo-book-auto-arm";

export type DemoBookAutoArm = {
  /** Usuario completó doble confirmación (prep). */
  armed: boolean;
  armedAt: string | null;
  /** Texto que el usuario tecleó en el 2º paso (auditoría local). */
  confirmPhrase: string | null;
};

export const AUTO_ARM_CONFIRM_PHRASE = "ACTIVAR AUTO";

export function defaultAutoArm(): DemoBookAutoArm {
  return { armed: false, armedAt: null, confirmPhrase: null };
}

export function loadAutoArm(): DemoBookAutoArm {
  try {
    const raw = localStorage.getItem(DEMO_BOOK_AUTO_ARM_KEY);
    if (!raw) return defaultAutoArm();
    const o = JSON.parse(raw) as Partial<DemoBookAutoArm>;
    return {
      armed: Boolean(o.armed),
      armedAt: typeof o.armedAt === "string" ? o.armedAt : null,
      confirmPhrase:
        typeof o.confirmPhrase === "string" ? o.confirmPhrase : null,
    };
  } catch {
    return defaultAutoArm();
  }
}

export function saveAutoArm(arm: DemoBookAutoArm): void {
  localStorage.setItem(DEMO_BOOK_AUTO_ARM_KEY, JSON.stringify(arm));
  window.dispatchEvent(new Event(DEMO_BOOK_AUTO_ARM_EVENT));
}

function subscribeAutoArm(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = () => onStoreChange();
  window.addEventListener(DEMO_BOOK_AUTO_ARM_EVENT, handler);
  window.addEventListener("storage", handler);
  return () => {
    window.removeEventListener(DEMO_BOOK_AUTO_ARM_EVENT, handler);
    window.removeEventListener("storage", handler);
  };
}

function getAutoArmArmedSnapshot(): boolean {
  return loadAutoArm().armed;
}

/**
 * Armado AUTO reactivo (snapshot booleano, estable entre renders).
 *
 * Sustituye `loadAutoArm().armed` en render: armar/desarmar en otra vista actualiza
 * cockpit, AUTO y HUD sin remontar. En SSR/entorno sin `localStorage` → desarmado.
 */
export function useAutoArmArmed(): boolean {
  return useSyncExternalStore(
    subscribeAutoArm,
    getAutoArmArmedSnapshot,
    () => false,
  );
}

export function disarmAutoArm(): DemoBookAutoArm {
  const next = defaultAutoArm();
  saveAutoArm(next);
  return next;
}

/** Doble paso: step1 OK + phrase exacta → armed. */
export function tryArmAuto(
  phrase: string,
): { ok: true; arm: DemoBookAutoArm } | { ok: false; error: string } {
  if (phrase.trim() !== AUTO_ARM_CONFIRM_PHRASE) {
    return {
      ok: false,
      error: `Escribe exactamente «${AUTO_ARM_CONFIRM_PHRASE}» para confirmar.`,
    };
  }
  const arm: DemoBookAutoArm = {
    armed: true,
    armedAt: new Date().toISOString(),
    confirmPhrase: AUTO_ARM_CONFIRM_PHRASE,
  };
  saveAutoArm(arm);
  return { ok: true, arm };
}
