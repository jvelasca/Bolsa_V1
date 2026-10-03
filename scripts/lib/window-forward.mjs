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

/** Nombre del directorio-lock atomico de un dia. */
export const LOCK_DIR_NAME = '.run.lock';
/** TTL de un lock de host desconocido antes de poder reclamarlo con `--force` (12 h). */
export const LOCK_TTL_MS = 12 * 60 * 60 * 1000;

/**
 * Configuracion pinneada de la ventana (arbol congelado).
 * Los hashes son de `git rev-parse "HEAD:apps" "HEAD:packages"`; si el arbol de
 * codigo se mueve, el runner declara `TREE_MOVED` y aborta (fail-closed).
 * `commit` nombra el commit cuyo arbol queda pinneado.
 *
 * RE-ANCLAJE 2026-10-03 (sello `v2.88.41-beta`): la atribucion MULTIRREGIMEN
 * DIA-D (`dia_d_multi.py` + tests + CLI `v2_93`) toco `src`/tests bajo
 * `packages/` y scripts bajo `apps/` (`Δ motor = 0`: CERO ficheros de motor).
 * El arbol pinneado es el del commit funcional `85b00235`. Editar el pin NO
 * mueve a su vez el arbol porque este modulo vive en `scripts/`. Pin anterior
 * (sello `v2.88.40-beta`, commit `bd3c9cd9`):
 * `apps` `22ca3e78…` / `packages` `f169415e…`.
 */
export const WINDOW_CONFIG = Object.freeze({
  commit: '85b00235',
  appsHash: 'b0cd017438c2a745cffa876f45211c021ba3309f',
  packagesHash: '35a37d565b6d211306f6cb1aef87d6c8e12536aa',
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
 * Variables de entorno que **solo** pueden tocar la identidad/el freeze en modo
 * explicitamente inseguro (`--unsafe-override-window-config`). `WINDOW_PY`,
 * `WINDOW_UV` y `WINDOW_API_READY_URL` NO son freeze y siguen siendo legitimas.
 */
export const FREEZE_ENV_KEYS = Object.freeze({
  appsHash: 'WINDOW_APPS_HASH',
  packagesHash: 'WINDOW_PACKAGES_HASH',
  account: 'WINDOW_ACCOUNT',
  versionA: 'WINDOW_VERSION_A',
  versionB: 'WINDOW_VERSION_B',
  watchSize: 'WINDOW_WATCH_SIZE',
});

/**
 * Config efectiva de la ventana. Por defecto es **inmutable**: el entorno NO
 * puede reescribir `appsHash`/`packagesHash`/`account`/`versionA`/`versionB`/`watchSize`
 * (si lo hiciera, el freeze `TREE_MOVED` dejaria de ser un freeze). El override
 * exige `unsafeOverride: true`; devuelve `configMode` y `configOverrides` para
 * sellarlos en el manifest.
 * @param {NodeJS.ProcessEnv | Record<string,string|undefined>} [env]
 * @param {{unsafeOverride?: boolean}} [options]
 */
export function windowConfig(env = {}, { unsafeOverride = false } = {}) {
  const base = { ...WINDOW_CONFIG };
  const configOverrides = [];
  if (unsafeOverride) {
    for (const [field, key] of Object.entries(FREEZE_ENV_KEYS)) {
      const raw = env[key];
      if (raw === undefined || raw === '') continue;
      if (field === 'watchSize') {
        const parsed = Number(raw);
        if (Number.isFinite(parsed) && parsed > 0) {
          base.watchSize = parsed;
          configOverrides.push(key);
        }
      } else if (String(raw) !== String(WINDOW_CONFIG[field])) {
        base[field] = raw;
        configOverrides.push(key);
      }
    }
  }
  return {
    ...base,
    configMode: unsafeOverride ? 'UNSAFE' : 'FROZEN',
    configOverrides,
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

/** Directorio-lock (creado con `mkdir`, atomico) que serializa el dia. */
export function runLockDir(day) {
  return `${runDir(day)}/${LOCK_DIR_NAME}`;
}

/**
 * Decide que hacer con un lock existente. Logica PURA (reloj y `isProcessAlive`
 * inyectables) para poder ejercitarla sin tocar el sistema de ficheros:
 *   - sin lock => `acquire`.
 *   - mismo host + PID vivo => `blocked` (un `--force` **no** salta un lock vivo).
 *   - mismo host + PID muerto => `reclaim` (stale inequivoco, sin `--force`).
 *   - otro host / TTL superado => `blocked` salvo `--force` => `reclaim`.
 * @param {{
 *   lock?: Record<string, unknown> | null,
 *   now?: number,
 *   host?: string,
 *   isProcessAlive?: (pid: unknown) => boolean,
 *   ttlMs?: number,
 *   force?: boolean,
 * }} [options]
 */
export function lockDecision({
  lock = null,
  now = Date.now(),
  host = '',
  isProcessAlive = () => false,
  ttlMs = LOCK_TTL_MS,
  force = false,
} = {}) {
  if (!lock || typeof lock !== 'object') {
    return { action: 'acquire', reason: 'sin_lock', stale: false };
  }
  const sameHost = String(lock.host ?? '') !== '' && String(lock.host) === String(host);
  if (sameHost && isProcessAlive(lock.pid)) {
    return { action: 'blocked', reason: 'pid_vivo', stale: false };
  }
  if (sameHost) {
    return { action: 'reclaim', reason: 'pid_muerto', stale: true };
  }
  const startedAt = Date.parse(String(lock.startedAt ?? ''));
  const expired = Number.isFinite(startedAt) && now - startedAt > ttlMs;
  if (force) {
    return { action: 'reclaim', reason: expired ? 'ttl_expirado_force' : 'host_distinto_force', stale: true };
  }
  return { action: 'blocked', reason: expired ? 'ttl_expirado' : 'host_distinto', stale: true };
}

/**
 * Decide que hacer con `window:unlock`. A diferencia de `acquireDayLock`, el
 * unlock es una accion MANUAL del operador: **nunca** debe borrar el lock de un
 * proceso vivo (romper el lock de exclusion mutua permitiria dos `run-day`
 * simultaneos del mismo dia). Logica PURA (reloj y `isProcessAlive` inyectables):
 *   - sin lock => `nothing`.
 *   - lock ilegible (`lock.json` ausente/corrupto: no se puede probar ownership)
 *     => `deny` salvo `--force` => `reclaim` (`lock_ilegible_force`).
 *   - mismo host + PID vivo => `deny` (un `--force` **no** salta un PID vivo: el
 *     operador mata el proceso y el PID pasa a muerto => `reclaim` automatico).
 *   - mismo host + PID muerto => `reclaim` (huerfano inequivoco, sin `--force`).
 *   - otro host + TTL superado (12 h) => `reclaim` (huerfano), sin `--force`.
 *   - otro host + TTL no expirado => `deny` salvo `--force` => `reclaim`.
 * @param {{
 *   lockExists?: boolean,
 *   lock?: Record<string, unknown> | null,
 *   now?: number,
 *   host?: string,
 *   isProcessAlive?: (pid: unknown) => boolean,
 *   ttlMs?: number,
 *   force?: boolean,
 * }} [options]
 */
export function unlockDecision({
  lockExists = false,
  lock = null,
  now = Date.now(),
  host = '',
  isProcessAlive = () => false,
  ttlMs = LOCK_TTL_MS,
  force = false,
} = {}) {
  if (!lockExists) {
    return { action: 'nothing', reason: 'sin_lock', stale: false };
  }
  if (!lock || typeof lock !== 'object') {
    return force
      ? { action: 'reclaim', reason: 'lock_ilegible_force', stale: true }
      : { action: 'deny', reason: 'lock_ilegible', stale: false };
  }
  const base = lockDecision({ lock, now, host, isProcessAlive, ttlMs, force });
  if (base.action === 'acquire') {
    return { action: 'nothing', reason: 'sin_lock', stale: false };
  }
  if (base.action === 'reclaim') {
    return { action: 'reclaim', reason: base.reason, stale: true };
  }
  if (base.reason === 'pid_vivo') {
    return { action: 'deny', reason: 'pid_vivo', stale: false };
  }
  if (base.reason === 'ttl_expirado') {
    return { action: 'reclaim', reason: 'ttl_expirado', stale: true };
  }
  return { action: 'deny', reason: base.reason, stale: false };
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

/**
 * Comprueba que el gate que se va a pintar procede de un run **ligado** al ledger
 * y al arbol congelado: mismo dia/cuenta/versionA, freeze certificado, sha256 del
 * `window.json` del run y cabecera (`meta.header`) coherente. Logica PURA.
 * Cualquier problema => `ok:false` (el runner NO debe mostrar el gate).
 * @param {{
 *   ledgerRow?: Record<string, unknown> | null,
 *   manifest?: Record<string, unknown> | null,
 *   windowGate?: ReturnType<typeof parseGate> | null,
 *   windowJsonSha256?: string | null,
 *   windowHeader?: Record<string, unknown> | null,
 *   frozen?: typeof WINDOW_CONFIG,
 * }} [options]
 */
export function verifyWindowProvenance({
  ledgerRow = null,
  manifest = null,
  windowGate = null,
  windowJsonSha256 = null,
  windowHeader = null,
  frozen = WINDOW_CONFIG,
} = {}) {
  const problems = [];
  if (!manifest || typeof manifest !== 'object') {
    return { ok: false, problems: ['sin_manifest'] };
  }
  const provenance = manifest.windowProvenance;
  if (!provenance || typeof provenance !== 'object') problems.push('sin_provenance');
  if (!windowGate) problems.push('sin_gate');
  if (!manifest.freeze || manifest.freeze.ok !== true) {
    problems.push('freeze_no_certificado');
  } else {
    if (manifest.freeze.apps !== frozen.appsHash) problems.push('apps_hash_no_congelado');
    if (manifest.freeze.packages !== frozen.packagesHash) problems.push('packages_hash_no_congelado');
  }
  if (manifest.configMode === 'UNSAFE') problems.push('config_override_unsafe');
  if (ledgerRow) {
    if (String(ledgerRow.day ?? '') !== String(manifest.day ?? '')) problems.push('dia_no_coincide');
    if (String(ledgerRow.account ?? '') !== String(manifest.account ?? '')) {
      problems.push('cuenta_no_coincide');
    }
    if (String(ledgerRow.versionA ?? '') !== String(manifest.versionA ?? '')) {
      problems.push('version_a_no_coincide');
    }
  }
  if (provenance && provenance.windowJsonSha256) {
    if (!windowJsonSha256 || windowJsonSha256 !== provenance.windowJsonSha256) {
      problems.push('sha256_no_coincide');
    }
  }
  if (windowHeader) {
    if (String(windowHeader.account ?? '') !== String(manifest.account ?? '')) {
      problems.push('window_cuenta_no_coincide');
    }
    const versions = Array.isArray(windowHeader.versions) ? windowHeader.versions.map(String) : [];
    if (versions.length > 0 && !versions.includes(String(manifest.versionA ?? ''))) {
      problems.push('window_version_no_coincide');
    }
  } else {
    problems.push('sin_window_header');
  }
  return { ok: problems.length === 0, problems };
}
