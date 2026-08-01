/**
 * Helpers Lab → Coach handoff (save-fail blocking).
 */

export type LabHandoffSaveOk = {
  ok: true;
  strategyId: string;
  name: string;
  presetKey?: string | null;
};

export type LabHandoffSaveFail = {
  ok: false;
  error: string;
};

export type LabHandoffSaveResult = LabHandoffSaveOk | LabHandoffSaveFail;

/**
 * If any improved zone failed to persist Mejor, block the whole Coach handoff.
 * Partial improved lists would leave Finalistas incompletos / inconsistentes.
 */
export function resolveLabReanalyzeGate(opts: {
  improvedSaved: number;
  saveFailures: Array<{ rank: number; error: string }>;
  carriedCount: number;
}): { allow: boolean; message: string | null } {
  if (opts.saveFailures.length > 0) {
    const detail = opts.saveFailures
      .map((f) => `#${f.rank}: ${f.error}`)
      .join(' · ');
    return {
      allow: false,
      message: `No se puede pasar al Coach: falló guardar el Mejor (${detail}). Reintenta Guardar o revisa la API.`,
    };
  }
  if (opts.improvedSaved === 0 && opts.carriedCount === 0) {
    return {
      allow: false,
      message:
        'Nada que llevar: espera a que terminen las zonas con mejora, o marca «Llevar» en las que no mejoraron.',
    };
  }
  return { allow: true, message: null };
}
