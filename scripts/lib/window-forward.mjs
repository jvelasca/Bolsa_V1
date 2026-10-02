/**
 * Helpers del runner de la ventana PAPER forward (>=4 dias) sobre `v2.88.29-beta`.
 *
 * Modulo PURO (sin I/O de red, sin procesos, sin reloj de pared salvo el `Date`
 * inyectable): calculo de rutas por dia, clasificacion de codigos de salida,
 * parseo de freeze/gate e idempotencia. Se ejercita con `--dry-run`.
 *
 * Ops-only: no toca motor, gobernador, `TOP_N`, umbrales, allocation, pesos A/B
 * ni migraciones. Ver `docs/engineering/runbook-ventana-forward-v2.78-2026-09-27.md`.
 */
import { join } from 'node:path';

/** Directorio no versionado que acumula el material del forward (`.gitignore`). */
export const OPERABILITY_DIR = 'operability_runs';
/** Subdirectorio del runner: un folder por dia + ledger + manifests. */
export const RUNS_DIR = `${OPERABILITY_DIR}/window-runs`;
/** Ruta del ledger acumulado (una fila JSON por corrida). */
export const LEDGER_PATH = `${RUNS_DIR}/ledger.jsonl`;
/** Ruta canonica del forward del dia (el glob del runbook la reutiliza). */
export const FORWARD_GLOB = `${OPERABILITY_DIR}/forward-market-*.json`;
/** Serie/ventana que produce `v2_80` (material durable, read-only). */
export const WINDOW_JSON = `${OPERABILITY_DIR}/operability-window.json`;
export const WINDOW_HTML = `${OPERABILITY_DIR}/operability-window.html`;
/** Auditoria read-only que produce `v2_83`. */
export const AUDIT_JSON = `${OPERABILITY_DIR}/operability-audit.json`;
export const AUDIT_TXT = `${RUNS_DIR}/window-audit.txt`;
/** Journal JSONL que acumula `v2_77` / `v2_80` (no versionado). */
export const JOURNAL_JSONL = `${OPERABILITY_DIR}/journal.jsonl`;
export const WINDOW_JOURNAL_JSONL = `${OPERABILITY_DIR}/window.jsonl`;

/** Umbrales duros del gate (`window_gate`), no negociables durante la ventana. */
export const WINDOW_MIN_DAYS = 4;
export const WINDOW_MIN_EPISODES = 2;
export const WINDOW_MIN_CYCLES = 32;

/**
 * Configuracion pinneada de la ventana (arbol congelado `v2.88.30-beta`).
 * Los hashes son de `git rev-parse "HEAD:apps" "HEAD:packages"`; si el arbol de
 * codigo se mueve, el runner declara `TREE_MOVED` y aborta (fail-closed).
 * `commit` nombra el sello de ingenieria cuyo arbol queda pinneado.
 */
export const WINDOW_CONFIG = Object.freeze({
  commit: 'v2.88.30-beta',
  appsHash: '2237f0693f5102e74650ccad0309a9d7ae7bae35',
  packagesHash: 'ce0a38b7e6f5a9f102490e5774f859d7f83aac4a',
  account: '1484e253d2d54645945a6b1d7',
  versionA: 'v283-window-a',
  versionB: 'v283-window-b',
  watchSize: 20,
  days: WINDOW_MIN_DAYS,
  /** Flags de operacion: se inyectan SOLO en el `env` del proceso hijo. */
  operatorEnv: Object.freeze({
    AUTO_ENGINE_SIM_REAL_PRICE: '1',
    AUTO_OPERATIONAL_AUDIT: '1',
    BROKER_VENUE: 'paper',
  }),
});

/**
 * Config efectiva: los defaults pinneados, con override explicito por entorno
 * (util para sondas/dry-run en otro arbol sin tocar el codigo).
 * @param {NodeJS.ProcessEnv | Record<string,string|undefined>} [env]
 */
export function windowConfig(env = {}) {
  const number = (value, fallback) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
  };
  return {
    ...WINDOW_CONFIG,
    account: env.WINDOW_ACCOUNT || WINDOW_CONFIG.account,
    versionA: env.WINDOW_VERSION_A || WINDOW_CONFIG.versionA,
    versionB: env.WINDOW_VERSION_B || WINDOW_CONFIG.versionB,
    watchSize: number(env.WINDOW_WATCH_SIZE, WINDOW_CONFIG.watchSize),
    appsHash: env.WINDOW_APPS_HASH || WINDOW_CONFIG.appsHash,
    packagesHash: env.WINDOW_PACKAGES_HASH || WINDOW_CONFIG.packagesHash,
  };
}

const pad = (value) => String(value).padStart(2, '0');

/** Sello de dia `YYYYMMDD` (nombre de fichero del forward). */
export function dayStamp(date = new Date()) {
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}`;
}

/** Dia `YYYY-MM-DD` (cabecera del ledger). */
export function dayIso(date = new Date()) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Carpeta de artefactos de un dia. */
export function runDir(day) {
  return `${RUNS_DIR}/${day}`;
}

/** Fichero dentro de la carpeta de un dia. */
export function runFile(day, name) {
  return join(runDir(day), name);
}

/** Ruta canonica del forward del dia (`operability_runs/forward-market-<DIA>.json`). */
export function forwardPath(day) {
  return `${OPERABILITY_DIR}/forward-market-${day}.json`;
}

/**
 * Clasifica el codigo de salida de un script del pipeline.
 * `0` ok · `2` declarado (bloqueo/no material, NO es fallo duro) · `1` uso incorrecto
 * · `null`/otro error duro.
 * @param {number | null | undefined} exitCode
 */
export function classifyExit(exitCode) {
  if (exitCode === 0) return { exit: 0, ok: true, declared: false, hard: false, kind: 'ok' };
  if (exitCode === 2) {
    return { exit: 2, ok: false, declared: true, hard: false, kind: 'declared' };
  }
  if (exitCode === 1) {
    return { exit: 1, ok: false, declared: false, hard: true, kind: 'usage_error' };
  }
  return {
    exit: exitCode ?? null,
    ok: false,
    declared: false,
    hard: true,
    kind: 'error',
  };
}

/**
 * Preflight de `v2_76`: `0` = el universo admite LONG hoy; `2` = veto de regimen
 * legitimo (LONG vetadas; se DECLARA y no se fuerza) ; cualquier otro = error duro.
 * @param {number | null | undefined} exitCode
 */
export function classifyPreflight(exitCode) {
  const base = classifyExit(exitCode);
  if (exitCode === 0) return { ...base, veto: false, status: 'ALLOWED' };
  if (exitCode === 2) return { ...base, veto: true, status: 'NO_MEDIDO_REGIMEN' };
  return { ...base, veto: false, status: 'HARD_ERROR' };
}

/**
 * ¿El payload capturado es el de un preflight REAL? Sirve para no confundir un
 * fallo de arranque del interprete (que puede devolver codigo 2) con un veto de
 * regimen legitimo.
 * @param {unknown} payload
 */
export function isPreflightPayload(payload) {
  return Boolean(
    payload && typeof payload === 'object' && payload.mode === 'preflight' && payload.marketRegime,
  );
}

/**
 * Extrae `marketRegime` del payload de preflight (`v2_76 --preflight-only --json`).
 * @param {unknown} payload
 */
export function parsePreflight(payload) {
  if (!payload || typeof payload !== 'object') return null;
  const regime = payload.marketRegime;
  if (!regime || typeof regime !== 'object') return null;
  return {
    operationalRegime: String(regime.operationalRegime ?? 'UNKNOWN'),
    entriesAllowedLong: Boolean(regime.entriesAllowedLong),
    aggregate: String(regime.aggregateTrialRegime ?? regime.aggregate ?? ''),
    bySymbol: regime.bySymbol && typeof regime.bySymbol === 'object' ? regime.bySymbol : {},
  };
}

/**
 * Parseo defensivo de un JSON capturado en stdout (devuelve `null` si no lo es).
 * @param {string} text
 */
export function parseJsonLoose(text) {
  const raw = String(text ?? '').trim();
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/**
 * Extrae el gate de la ventana (`v2_80 --json` / `--out`). `null` si no lo trae:
 * nunca se fabrica un `0` ni un `READY`.
 * @param {unknown} payload
 */
export function parseGate(payload) {
  if (!payload || typeof payload !== 'object') return null;
  const gate = payload.meta?.gate;
  if (!gate || typeof gate !== 'object') return null;
  const number = (value, fallback) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };
  const list = (value) => (Array.isArray(value) ? value.map(String) : []);
  return {
    days: number(gate.days, 0),
    episodes: number(gate.episodes, 0),
    cycles: number(gate.cycles, 0),
    minDays: number(gate.minDays, WINDOW_MIN_DAYS),
    minEpisodes: number(gate.minEpisodes, WINDOW_MIN_EPISODES),
    minCycles: number(gate.minCycles, WINDOW_MIN_CYCLES),
    ready: Boolean(gate.ready),
    measured: Boolean(gate.measured),
    verdict: String(gate.verdict ?? 'INCONCLUSIVE'),
    dayList: list(gate.dayList),
    regimes: list(gate.regimes),
  };
}

/**
 * Parseo de `git rev-parse "HEAD:apps" "HEAD:packages"` (dos lineas, en orden).
 * @param {string} text
 */
export function parseRevParse(text) {
  const lines = String(text ?? '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return { apps: lines[0] ?? '', packages: lines[1] ?? '' };
}

/**
 * Contraste del arbol de codigo contra el sello congelado.
 * @param {{apps: string, packages: string}} revisions
 * @param {ReturnType<typeof windowConfig>} config
 */
export function freezeCheck(revisions, config) {
  const appsOk = revisions.apps === config.appsHash;
  const packagesOk = revisions.packages === config.packagesHash;
  return {
    ok: appsOk && packagesOk,
    apps: revisions.apps,
    packages: revisions.packages,
    expectedApps: config.appsHash,
    expectedPackages: config.packagesHash,
    appsOk,
    packagesOk,
  };
}

/** Estados terminales de un dia (idempotencia: no se re-ejecuta salvo `--force`). */
export const TERMINAL_STATUSES = Object.freeze([
  'NO_MEDIDO_REGIMEN',
  'MEDIDO',
  'DECLARADO',
  'HARD_ERROR',
]);

/** @param {unknown} status */
export function isTerminalStatus(status) {
  return TERMINAL_STATUSES.includes(String(status ?? ''));
}

/**
 * Decide el estado del dia a partir de las clasificaciones de cada paso.
 * Veto de regimen manda; un fallo duro manda sobre "declarado".
 * @param {{ preflight?: ReturnType<typeof classifyPreflight>, window?: ReturnType<typeof classifyExit>, hard?: boolean }} steps
 */
export function resolveDayStatus(steps) {
  if (steps.hard) return 'HARD_ERROR';
  if (steps.preflight?.veto) return 'NO_MEDIDO_REGIMEN';
  if (steps.preflight?.hard) return 'HARD_ERROR';
  if (steps.window?.ok) return 'MEDIDO';
  return 'DECLARADO';
}

/**
 * Ultima fila por dia (el ledger puede tener re-ejecuciones con `--force`).
 * @param {Array<Record<string, unknown>>} rows
 */
export function latestByDay(rows) {
  const map = new Map();
  for (const row of rows ?? []) {
    const day = String(row?.day ?? '').trim();
    if (!day) continue;
    map.set(day, row);
  }
  return [...map.values()].sort((a, b) => String(a.day).localeCompare(String(b.day)));
}

/**
 * Resumen honesto del ledger: cuenta dias por estado y adjunta el gate de la
 * ventana (o `null` si aun no se puede leer: nunca `0` fabricado).
 * @param {Array<Record<string, unknown>>} rows
 * @param {ReturnType<typeof parseGate>} [gate]
 */
export function summarizeLedger(rows, gate = null) {
  const days = latestByDay(rows);
  const count = (status) => days.filter((row) => row.status === status).length;
  return {
    days,
    total: days.length,
    measured: count('MEDIDO'),
    vetoed: count('NO_MEDIDO_REGIMEN'),
    declared: count('DECLARADO'),
    hardErrors: count('HARD_ERROR'),
    measuredDays: days.filter((row) => row.status === 'MEDIDO').map((row) => row.day),
    vetoedDays: days.filter((row) => row.status === 'NO_MEDIDO_REGIMEN').map((row) => row.day),
    gate,
    ready: Boolean(gate?.ready),
  };
}
