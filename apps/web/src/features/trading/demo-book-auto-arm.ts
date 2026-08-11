/**
 * A3 — armado local AUTO (doble confirmación) + preferencias.
 * No habilita execute; `DEMO_BOOK_AUTO_UI_ENABLED` sigue false hasta thaw.
 */

export const DEMO_BOOK_AUTO_ARM_KEY = "bolsa-demo-book-auto-arm-v1";

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
  window.dispatchEvent(new Event("bolsa-demo-book-auto-arm"));
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
