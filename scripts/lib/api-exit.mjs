/**
 * Motivo y hechos de la salida de la API en `run-dev.mjs` (PURO).
 *
 * **Por qué existe.** El commit 3f7cd5e9 declaró `api-exit:<code>` sólo para
 * exit no-cero (`if (code && code !== 0)`). Eso dejaba mudos justo los casos
 * que hay que diagnosticar: un exit `0`, una muerte por señal (`code === null`
 * en Windows/Unix) y un fallo de `spawn`. Además el motivo no identificaba al
 * proceso (rol, pid, señal, uptime) ni conservaba el último stderr, que suele
 * ser la causa real del cierre de uvicorn.
 *
 * **Regla.** Cualquier salida de la API una vez supervisada es fatal y se
 * declara con el prefijo literal `api-exit:` para que el grep del criterio
 * (`api-exit:<code>`) siga funcionando. El prefijo nunca se traduce: es el
 * contrato de búsqueda en consola, `logs/agent/events.log` y `logs/agent/dev.json`.
 */

/**
 * Etiqueta estable del motivo de salida.
 * @param {{code?: number | null, signal?: string | null}} [exit]
 * @returns {string} `api-exit:<code>`, `api-exit:signal:<SIG>` o `api-exit:unknown`
 */
export function apiExitReason({ code, signal } = {}) {
  // `code === 0` también es una salida y debe declararse (antes era invisible).
  if (typeof code === 'number') return `api-exit:${code}`;
  if (signal) return `api-exit:signal:${signal}`;
  return 'api-exit:unknown';
}

/**
 * Hechos estructurados del proceso que salió (para events.log y dev.json).
 * @param {{code?: number | null, signal?: string | null, pid?: number | null,
 *   uptimeMs?: number | null, role?: string, lastLines?: string[]}} [facts]
 * @returns {{role: string, pid?: number, code: number | null, signal: string | null,
 *   uptimeMs?: number, lastLines?: string[]}}
 */
export function apiExitFacts({
  code = null,
  signal = null,
  pid = null,
  uptimeMs = null,
  role = 'api',
  lastLines: tail = null,
} = {}) {
  const facts = { role };
  if (typeof pid === 'number') facts.pid = pid;
  facts.code = typeof code === 'number' ? code : null;
  facts.signal = signal ?? null;
  if (typeof uptimeMs === 'number') facts.uptimeMs = uptimeMs;
  if (Array.isArray(tail) && tail.length > 0) facts.lastLines = tail.slice(-3);
  return facts;
}

/**
 * Línea única y autosuficiente para consola y `events.log`: identifica el
 * proceso que inició el shutdown y adjunta la última línea de salida (causa).
 * @param {{reason?: string, facts?: ReturnType<typeof apiExitFacts>}} [exit]
 * @returns {string}
 */
export function describeApiExit({ reason, facts = {} } = {}) {
  const role = facts.role ?? 'api';
  const pid = typeof facts.pid === 'number' ? facts.pid : '-';
  const code = typeof facts.code === 'number' ? facts.code : '-';
  const signal = facts.signal ?? '-';
  const label = reason ?? apiExitReason(facts);
  const last =
    Array.isArray(facts.lastLines) && facts.lastLines.length > 0
      ? ` | último stderr: ${facts.lastLines[facts.lastLines.length - 1]}`
      : '';
  return `API salió (rol=${role} pid=${pid} code=${code} signal=${signal}) — ${label}; se detiene el stack${last}`;
}

/**
 * Últimas `n` líneas no vacías de un volcado (stderr suele venir con CRLF).
 * @param {string} text
 * @param {number} [n]
 * @returns {string[]}
 */
export function lastLines(text, n = 3) {
  if (typeof text !== 'string' || text.length === 0) return [];
  return text
    .replace(/\r/g, '')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .slice(-Math.max(1, n));
}
