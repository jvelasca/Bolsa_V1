/**
 * Puertos del stack de desarrollo y conflicto del supervisor (PURO).
 *
 * **Por que existe.** `window-stack-ready.mjs` comprobaba `WEB_PORT ?? 3002` como
 * "puerto web", pero 3002 es el puente XTB mock: la web vive en **5173**
 * (`scripts/run-dev.mjs` y `apps/web/vite.config.ts` usan `WEB_PORT ?? 5173`).
 * Medido el 2026-11-09: con el API caido y el puente XTB huerfano vivo, el
 * supervisor veia un listener en 3002, declaraba `port-busy` y **no arrancaba**
 * el stack — justo el escenario que existe para recuperar.
 *
 * **Regla de conflicto.**
 * - API ocupado ⇒ BLOQUEA: arrancar un segundo uvicorn pelea por el puerto y
 *   matar a un proceso ajeno no es tarea del supervisor.
 * - Web o puente ocupados ⇒ se AVISA y se arranca: `run-dev.mjs` libera los tres
 *   puertos en `ensureStackPortsFree()` antes de usarlos.
 */

/**
 * Puertos del stack, leyendo el entorno como lo hace `run-dev.mjs`.
 * @param {Record<string, string | undefined>} [env]
 * @returns {{api: number, web: number, bridge: number}}
 */
export function stackPorts(env = process.env) {
  return {
    api: Number(env.API_PYTHON_PORT || env.API_PORT || '8000'),
    web: Number(env.WEB_PORT || '5173'),
    bridge: Number(env.XTB_BRIDGE_PORT || '3002'),
  };
}

/**
 * Decide si un conflicto de puertos impide arrancar el stack.
 * @param {{api?: number[], web?: number[], bridge?: number[]}} listeners
 * @returns {{block: boolean, api: number[], stale: number[], byRole: {web: number[], bridge: number[]}}}
 */
export function decidePortConflict(listeners = {}) {
  const api = Array.isArray(listeners.api) ? listeners.api : [];
  const web = Array.isArray(listeners.web) ? listeners.web : [];
  const bridge = Array.isArray(listeners.bridge) ? listeners.bridge : [];
  return {
    block: api.length > 0,
    api,
    // Los puertos que `run-dev` libera por su cuenta: no bloquean, solo avisan.
    stale: [...web, ...bridge],
    byRole: { web, bridge },
  };
}

/**
 * Mensaje legible del conflicto (puro; se prueba sin puertos reales).
 * @param {{api: number, web: number, bridge: number}} ports
 * @param {{api: number[], byRole: {web: number[], bridge: number[]}}} decision
 * @returns {string}
 */
export function describePortConflict(ports, decision) {
  const parts = [];
  if (decision.api.length) {
    parts.push(`API :${ports.api} (PID ${decision.api.join(', ')})`);
  }
  if (decision.byRole.web.length) {
    parts.push(`web :${ports.web} (PID ${decision.byRole.web.join(', ')})`);
  }
  if (decision.byRole.bridge.length) {
    parts.push(`puente XTB :${ports.bridge} (PID ${decision.byRole.bridge.join(', ')})`);
  }
  return parts.join(' · ');
}
