/**
 * Regresiones del modulo PURO del runner de la ventana PAPER.
 *
 * Cubre las cuatro guardias del sello `2.11.32` (Muerden de verdad: revertir la
 * proteccion en `window-forward.mjs` pone el test en rojo):
 *   - config de freeze inmutable salvo `unsafeOverride`;
 *   - lock diario (`--force` no salta un lock vivo);
 *   - `unlock` respeta el ownership (nunca borra un PID vivo) y la staleness;
 *   - provenance del gate (status no pinta material stale).
 *
 * Ejecutar: `pnpm window:test` (o `node --test scripts/lib/window-forward.test.mjs`).
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  LOCK_TTL_MS,
  NON_MARKET_DAY_STATUS,
  WINDOW_CONFIG,
  classifyPreflight,
  cmdWrapperContent,
  isMarketDay,
  isPreflightPayload,
  isTerminalStatus,
  lockDecision,
  parseGate,
  parseRevParse,
  resolveDayStatus,
  summarizeLedger,
  unlockDecision,
  verifyWindowProvenance,
  windowConfig,
} from './window-forward.mjs';
import { applyPin, freezeStatus, parsePinFields } from '../window-pin.mjs';

// ---------------------------------------------------------------------------
// Config inmutable (P1)
// ---------------------------------------------------------------------------

test('windowConfig ignora los overrides de freeze por defecto', () => {
  const config = windowConfig({
    WINDOW_APPS_HASH: 'deadbeef',
    WINDOW_PACKAGES_HASH: 'cafebabe',
    WINDOW_ACCOUNT: 'otra-cuenta',
    WINDOW_VERSION_A: 'otra-version',
    WINDOW_VERSION_B: 'otra-b',
    WINDOW_WATCH_SIZE: '3',
  });
  assert.equal(config.configMode, 'FROZEN');
  assert.deepEqual(config.configOverrides, []);
  assert.equal(config.appsHash, WINDOW_CONFIG.appsHash);
  assert.equal(config.packagesHash, WINDOW_CONFIG.packagesHash);
  assert.equal(config.account, WINDOW_CONFIG.account);
  assert.equal(config.versionA, WINDOW_CONFIG.versionA);
  assert.equal(config.versionB, WINDOW_CONFIG.versionB);
  assert.equal(config.watchSize, WINDOW_CONFIG.watchSize);
});

test('windowConfig sólo aplica overrides con unsafeOverride y lo sella', () => {
  const config = windowConfig(
    { WINDOW_APPS_HASH: 'deadbeef', WINDOW_ACCOUNT: 'otra-cuenta', WINDOW_WATCH_SIZE: '3' },
    { unsafeOverride: true },
  );
  assert.equal(config.configMode, 'UNSAFE');
  assert.equal(config.appsHash, 'deadbeef');
  assert.equal(config.account, 'otra-cuenta');
  assert.equal(config.watchSize, 3);
  assert.deepEqual(
    [...config.configOverrides].sort(),
    ['WINDOW_ACCOUNT', 'WINDOW_APPS_HASH', 'WINDOW_WATCH_SIZE'],
  );
});

test('windowConfig con unsafeOverride pero sin env no lista overrides', () => {
  const config = windowConfig({}, { unsafeOverride: true });
  assert.equal(config.configMode, 'UNSAFE');
  assert.deepEqual(config.configOverrides, []);
  assert.equal(config.appsHash, WINDOW_CONFIG.appsHash);
});

// ---------------------------------------------------------------------------
// Lock diario (P0)
// ---------------------------------------------------------------------------

const alive = () => true;
const dead = () => false;

test('lockDecision adquiere cuando no hay lock', () => {
  assert.equal(lockDecision({ lock: null, host: 'h' }).action, 'acquire');
});

test('lockDecision bloquea un lock con PID vivo en el mismo host (ni con --force)', () => {
  const lock = { host: 'h', pid: 42, startedAt: new Date().toISOString() };
  assert.equal(lockDecision({ lock, host: 'h', isProcessAlive: alive }).action, 'blocked');
  assert.equal(
    lockDecision({ lock, host: 'h', isProcessAlive: alive, force: true }).action,
    'blocked',
  );
});

test('lockDecision reclama un lock con PID muerto en el mismo host', () => {
  const lock = { host: 'h', pid: 42, startedAt: new Date().toISOString() };
  const decision = lockDecision({ lock, host: 'h', isProcessAlive: dead });
  assert.equal(decision.action, 'reclaim');
  assert.equal(decision.reason, 'pid_muerto');
});

test('lockDecision bloquea un lock de otro host sin --force', () => {
  const lock = { host: 'otro', pid: 42, startedAt: new Date().toISOString() };
  assert.equal(lockDecision({ lock, host: 'h', isProcessAlive: dead }).action, 'blocked');
});

test('lockDecision reclama un lock de otro host/TTL sólo con --force', () => {
  const lock = {
    host: 'otro',
    pid: 42,
    startedAt: new Date(Date.now() - LOCK_TTL_MS - 1000).toISOString(),
  };
  const decision = lockDecision({
    lock,
    host: 'h',
    isProcessAlive: dead,
    force: true,
  });
  assert.equal(decision.action, 'reclaim');
  assert.equal(decision.reason, 'ttl_expirado_force');
});

// ---------------------------------------------------------------------------
// unlock: ownership / staleness (P1)
// ---------------------------------------------------------------------------

const NOW = Date.parse('2026-10-02T20:00:00.000Z');
const freshLock = { host: 'h', pid: 42, startedAt: new Date(NOW).toISOString() };

test('unlockDecision no hace nada si no hay lock', () => {
  const decision = unlockDecision({ lockExists: false, host: 'h' });
  assert.equal(decision.action, 'nothing');
  assert.equal(decision.reason, 'sin_lock');
});

test('unlockDecision deniega un lock con PID vivo en el mismo host (ni con --force)', () => {
  const decision = unlockDecision({
    lockExists: true,
    lock: freshLock,
    now: NOW,
    host: 'h',
    isProcessAlive: alive,
  });
  assert.equal(decision.action, 'deny');
  assert.equal(decision.reason, 'pid_vivo');
  const forced = unlockDecision({
    lockExists: true,
    lock: freshLock,
    now: NOW,
    host: 'h',
    isProcessAlive: alive,
    force: true,
  });
  assert.equal(forced.action, 'deny');
  assert.equal(forced.reason, 'pid_vivo');
});

test('unlockDecision reclama un lock con PID muerto en el mismo host', () => {
  const decision = unlockDecision({
    lockExists: true,
    lock: freshLock,
    now: NOW,
    host: 'h',
    isProcessAlive: dead,
  });
  assert.equal(decision.action, 'reclaim');
  assert.equal(decision.reason, 'pid_muerto');
});

test('unlockDecision deniega un lock de otro host con TTL fresco (y --force lo reclama)', () => {
  const lock = { host: 'otro', pid: 42, startedAt: new Date(NOW).toISOString() };
  const decision = unlockDecision({
    lockExists: true,
    lock,
    now: NOW,
    host: 'h',
    isProcessAlive: dead,
  });
  assert.equal(decision.action, 'deny');
  assert.equal(decision.reason, 'host_distinto');
  const forced = unlockDecision({
    lockExists: true,
    lock,
    now: NOW,
    host: 'h',
    isProcessAlive: dead,
    force: true,
  });
  assert.equal(forced.action, 'reclaim');
  assert.equal(forced.reason, 'host_distinto_force');
});

test('unlockDecision reclama un lock de otro host con TTL expirado sin --force', () => {
  const lock = {
    host: 'otro',
    pid: 42,
    startedAt: new Date(NOW - LOCK_TTL_MS - 1000).toISOString(),
  };
  const decision = unlockDecision({
    lockExists: true,
    lock,
    now: NOW,
    host: 'h',
    isProcessAlive: dead,
  });
  assert.equal(decision.action, 'reclaim');
  assert.equal(decision.reason, 'ttl_expirado');
});

test('unlockDecision deniega un lock ilegible (sin lock.json) y --force lo reclama', () => {
  const decision = unlockDecision({
    lockExists: true,
    lock: null,
    now: NOW,
    host: 'h',
    isProcessAlive: dead,
  });
  assert.equal(decision.action, 'deny');
  assert.equal(decision.reason, 'lock_ilegible');
  const forced = unlockDecision({
    lockExists: true,
    lock: null,
    now: NOW,
    host: 'h',
    isProcessAlive: dead,
    force: true,
  });
  assert.equal(forced.action, 'reclaim');
  assert.equal(forced.reason, 'lock_ilegible_force');
});

// ---------------------------------------------------------------------------
// Provenance del gate (P2)
// ---------------------------------------------------------------------------

function frozenManifest(overrides = {}) {
  return {
    day: '20261002',
    account: WINDOW_CONFIG.account,
    versionA: WINDOW_CONFIG.versionA,
    configMode: 'FROZEN',
    freeze: {
      ok: true,
      apps: WINDOW_CONFIG.appsHash,
      packages: WINDOW_CONFIG.packagesHash,
    },
    windowProvenance: { windowJsonSha256: 'abc123' },
    ...overrides,
  };
}

const ledgerRow = {
  day: '20261002',
  account: WINDOW_CONFIG.account,
  versionA: WINDOW_CONFIG.versionA,
};
const windowGate = { days: 4, episodes: 2, cycles: 32, minDays: 4, minEpisodes: 2, minCycles: 32 };
const windowHeader = { account: WINDOW_CONFIG.account, versions: [WINDOW_CONFIG.versionA] };

test('verifyWindowProvenance acepta un run ligado al ledger y al arbol', () => {
  const verdict = verifyWindowProvenance({
    ledgerRow,
    manifest: frozenManifest(),
    windowGate,
    windowJsonSha256: 'abc123',
    windowHeader,
  });
  assert.equal(verdict.ok, true, verdict.problems.join(', '));
});

test('verifyWindowProvenance rechaza un sha256 que no cuadra', () => {
  const verdict = verifyWindowProvenance({
    ledgerRow,
    manifest: frozenManifest(),
    windowGate,
    windowJsonSha256: 'otro',
    windowHeader,
  });
  assert.equal(verdict.ok, false);
  assert.ok(verdict.problems.includes('sha256_no_coincide'));
});

test('verifyWindowProvenance rechaza una cuenta/version que no cuadra', () => {
  const verdict = verifyWindowProvenance({
    ledgerRow: { ...ledgerRow, account: 'ajena', versionA: 'ajena' },
    manifest: frozenManifest(),
    windowGate,
    windowJsonSha256: 'abc123',
    windowHeader,
  });
  assert.equal(verdict.ok, false);
  assert.ok(verdict.problems.includes('cuenta_no_coincide'));
  assert.ok(verdict.problems.includes('version_a_no_coincide'));
});

test('verifyWindowProvenance rechaza un freeze no certificado', () => {
  const verdict = verifyWindowProvenance({
    ledgerRow,
    manifest: frozenManifest({
      freeze: { ok: false, apps: 'movido', packages: 'movido' },
    }),
    windowGate,
    windowJsonSha256: 'abc123',
    windowHeader,
  });
  assert.equal(verdict.ok, false);
  assert.ok(verdict.problems.includes('freeze_no_certificado'));
});

test('verifyWindowProvenance rechaza un window.json de otro dia (cabecera ajena)', () => {
  const verdict = verifyWindowProvenance({
    ledgerRow,
    manifest: frozenManifest(),
    windowGate,
    windowJsonSha256: 'abc123',
    windowHeader: { account: 'ajena', versions: ['v-otra'] },
  });
  assert.equal(verdict.ok, false);
  assert.ok(verdict.problems.includes('window_cuenta_no_coincide'));
  assert.ok(verdict.problems.includes('window_version_no_coincide'));
});

test('verifyWindowProvenance rechaza un run marcado UNSAFE', () => {
  const verdict = verifyWindowProvenance({
    ledgerRow,
    manifest: frozenManifest({ configMode: 'UNSAFE' }),
    windowGate,
    windowJsonSha256: 'abc123',
    windowHeader,
  });
  assert.equal(verdict.ok, false);
  assert.ok(verdict.problems.includes('config_override_unsafe'));
});

test('verifyWindowProvenance rechaza si falta el manifest', () => {
  const verdict = verifyWindowProvenance({ ledgerRow, manifest: null });
  assert.equal(verdict.ok, false);
  assert.deepEqual(verdict.problems, ['sin_manifest']);
});

// ---------------------------------------------------------------------------
// No regresion: veto/exit 2 y estado del dia
// ---------------------------------------------------------------------------

test('isPreflightPayload exige mode=preflight y marketRegime', () => {
  assert.equal(isPreflightPayload({ mode: 'preflight', marketRegime: {} }), true);
  assert.equal(isPreflightPayload({ mode: 'preflight' }), false);
  assert.equal(isPreflightPayload(null), false);
});

test('classifyPreflight: exit 2 es veto declarado, exit 1/otro es duro', () => {
  assert.equal(classifyPreflight(0).veto, false);
  assert.equal(classifyPreflight(0).hard, false);
  assert.equal(classifyPreflight(2).veto, true);
  assert.equal(classifyPreflight(2).hard, false);
  assert.equal(classifyPreflight(1).hard, true);
  assert.equal(classifyPreflight(1).veto, false);
});

test('resolveDayStatus: veto manda; duro manda sobre declarado', () => {
  assert.equal(
    resolveDayStatus({ preflight: classifyPreflight(2), window: { ok: false }, hard: false }),
    'NO_MEDIDO_REGIMEN',
  );
  assert.equal(
    resolveDayStatus({ preflight: classifyPreflight(0), window: { ok: true }, hard: false }),
    'MEDIDO',
  );
  assert.equal(
    resolveDayStatus({ preflight: classifyPreflight(0), window: { ok: false }, hard: false }),
    'DECLARADO',
  );
  assert.equal(
    resolveDayStatus({ preflight: classifyPreflight(0), window: { ok: true }, hard: true }),
    'HARD_ERROR',
  );
});

test('parseRevParse y parseGate no inventan valores', () => {
  assert.deepEqual(parseRevParse('aaa\nbbb\n'), { apps: 'aaa', packages: 'bbb' });
  assert.equal(parseGate({ meta: {} }), null);
  assert.equal(parseGate(null), null);
  const gate = parseGate({ meta: { gate: { days: 4, episodes: 2, cycles: 32, verdict: 'READY' } } });
  assert.equal(gate.days, 4);
  assert.equal(gate.minDays, 4);
  assert.equal(gate.ready, false);
});

// ---------------------------------------------------------------------------
// Pin de la ventana: parseo, freeze y re-anclaje (puro, sin git)
// ---------------------------------------------------------------------------

test('parsePinFields extrae los tres campos y no inventa si faltan', () => {
  const text = [
    'export const WINDOW_CONFIG = Object.freeze({',
    "  commit: 'abc12345',",
    `  appsHash: '${'a'.repeat(40)}',`,
    `  packagesHash: '${'b'.repeat(40)}',`,
    '});',
  ].join('\n');
  const pin = parsePinFields(text);
  assert.equal(pin.commit, 'abc12345');
  assert.equal(pin.appsHash, 'a'.repeat(40));
  assert.equal(pin.packagesHash, 'b'.repeat(40));
  assert.deepEqual(parsePinFields('sin campos'), {
    commit: null,
    appsHash: null,
    packagesHash: null,
  });
});

test('freezeStatus: el freeze real son los dos tree hashes; el commit es etiqueta', () => {
  const pin = { commit: 'old', appsHash: 'A', packagesHash: 'P' };
  assert.equal(
    freezeStatus(pin, { commit: 'new', appsHash: 'A', packagesHash: 'P' }).ok,
    true,
  );
  assert.equal(
    freezeStatus(pin, { commit: 'new', appsHash: 'A', packagesHash: 'P' }).commitLabelStale,
    true,
  );
  const moved = freezeStatus(pin, { commit: 'new', appsHash: 'A2', packagesHash: 'P' });
  assert.equal(moved.ok, false);
  assert.deepEqual(moved.mismatches, ['appsHash']);
});

test('applyPin reescribe los tres campos y es idempotente', () => {
  const text = [
    'export const WINDOW_CONFIG = Object.freeze({',
    "  commit: 'old00000',",
    `  appsHash: '${'x'.repeat(40)}',`,
    `  packagesHash: '${'y'.repeat(40)}',`,
    "  account: 'cuenta-fija',",
    '});',
  ].join('\n');
  const next = applyPin(text, {
    commit: 'new11111',
    appsHash: 'a'.repeat(40),
    packagesHash: 'b'.repeat(40),
    note: 'prueba',
    day: '2026-10-15',
  });
  assert.equal(next.changed, true);
  const parsed = parsePinFields(next.text);
  assert.equal(parsed.commit, 'new11111');
  assert.equal(parsed.appsHash, 'a'.repeat(40));
  assert.equal(parsed.packagesHash, 'b'.repeat(40));
  // La identidad NO se toca.
  assert.match(next.text, /account: 'cuenta-fija'/);
  assert.match(next.text, /RE-ANCLAJE 2026-10-15/);
  // Idempotente: aplicar el mismo pin no cambia nada.
  const again = applyPin(next.text, {
    commit: 'new11111',
    appsHash: 'a'.repeat(40),
    packagesHash: 'b'.repeat(40),
    note: 'prueba',
    day: '2026-10-15',
  });
  assert.equal(again.changed, false);
  assert.equal(again.text, next.text);
});

// ---------------------------------------------------------------------------
// Wrapper `.cmd` de la tarea programada (v2.88.142)
//
// Falsacion del defecto medido: el wrapper del `.140` invocaba
// `<root>\node_modules\.bin\pnpm.cmd`, que NO existe en este repo => las dos tareas
// quedaban «Estado: Listo» y no ejecutaban nada.
// ---------------------------------------------------------------------------

const wrapperParts = {
  root: 'C:/repo/Bolsa_V1',
  node: 'C:\\Program Files\\nodejs\\node.exe',
  runner: 'C:/repo/Bolsa_V1/scripts/window-forward-runner.mjs',
  command: 'watch',
};

test('cmdWrapperContent invoca node ABSOLUTO + runner (no pnpm ni PATH)', () => {
  const content = cmdWrapperContent(wrapperParts);
  assert.match(content, /"C:\\Program Files\\nodejs\\node\.exe"/);
  assert.match(content, /"C:\\repo\\Bolsa_V1\\scripts\\window-forward-runner\.mjs" watch/);
  assert.doesNotMatch(content, /pnpm/);
  assert.doesNotMatch(content, /node_modules/);
});

test('cmdWrapperContent fija el cwd al repo y es idempotente para el mismo comando', () => {
  const content = cmdWrapperContent(wrapperParts);
  assert.match(content, /cd \/d "C:\\repo\\Bolsa_V1"/);
  assert.equal(content, cmdWrapperContent({ ...wrapperParts }));
});

test('cmdWrapperContent NO mete comillas anidadas (fix .140 de schtasks)', () => {
  const content = cmdWrapperContent(wrapperParts);
  assert.doesNotMatch(content, /""/);
  // Cada linea tiene un numero PAR de comillas (apertura y cierre).
  const quotesPerLine = content.split(/\r?\n/).map((line) => (line.match(/"/g) ?? []).length);
  for (const count of quotesPerLine) assert.equal(count % 2, 0);
});

test('cmdWrapperContent propaga el codigo de salida (LastTaskResult: 3 = hubo aviso)', () => {
  const content = cmdWrapperContent(wrapperParts);
  assert.match(content, /exit \/b %ERRORLEVEL%/);
  assert.match(content, /if errorlevel 1 exit \/b 1/);
});

test('cmdWrapperContent distingue run-day de watch', () => {
  assert.match(cmdWrapperContent({ ...wrapperParts, command: 'run-day' }), /run-day/);
  assert.match(cmdWrapperContent({ ...wrapperParts, command: 'watch' }), /watch/);
});

test('cmdWrapperContent rechaza piezas ausentes y un node no absoluto', () => {
  assert.throws(() => cmdWrapperContent({ ...wrapperParts, node: '' }), /faltan/);
  assert.throws(() => cmdWrapperContent({ ...wrapperParts, command: '  ' }), /faltan/);
  assert.throws(() => cmdWrapperContent({ ...wrapperParts, root: '' }), /faltan/);
  assert.throws(() => cmdWrapperContent({ ...wrapperParts, node: 'node.exe' }), /absoluta/);
});

// ---------------------------------------------------------------------------
// Dia sin sesion (v2.88.143)
//
// Falsacion del defecto medido el 17/10 (sabado): la tarea `/sc daily` corrio y
// escribio una fila de VETO DE REGIMEN, de modo que un sabado parecia «un dia de
// ventana intentado y vetado». Un dia sin sesion no es ninguna de las dos cosas.
// ---------------------------------------------------------------------------

test('isMarketDay descarta sabado y domingo', () => {
  // 17/10/2026 fue sabado y 18/10/2026 domingo (los dos dias reales del defecto).
  assert.equal(isMarketDay(new Date('2026-10-17T18:00:00')), false);
  assert.equal(isMarketDay(new Date('2026-10-18T18:00:00')), false);
});

test('isMarketDay acepta los laborables de la ventana (14/15/16 y lunes 19)', () => {
  assert.equal(isMarketDay(new Date('2026-10-14T18:00:00')), true);
  assert.equal(isMarketDay(new Date('2026-10-15T18:00:00')), true);
  assert.equal(isMarketDay(new Date('2026-10-16T18:00:00')), true);
  assert.equal(isMarketDay(new Date('2026-10-19T18:00:00')), true);
});

test('NON_MARKET_DAY es terminal: una re-ejecucion del dia se omite', () => {
  assert.equal(isTerminalStatus(NON_MARKET_DAY_STATUS), true);
  assert.equal(NON_MARKET_DAY_STATUS, 'NON_MARKET_DAY');
});

test('summarizeLedger NO cuenta los dias sin sesion como dias de ventana', () => {
  const rows = [
    { day: '20261014', status: 'NO_MEDIDO_REGIMEN' },
    { day: '20261015', status: 'NO_MEDIDO_REGIMEN' },
    { day: '20261016', status: 'NO_MEDIDO_REGIMEN' },
    { day: '20261017', status: 'NON_MARKET_DAY' },
  ];
  const summary = summarizeLedger(rows, null);
  assert.equal(summary.rows, 4); // filas del ledger
  assert.equal(summary.total, 3); // dias DE VENTANA (14/15/16)
  assert.equal(summary.nonMarket, 1);
  assert.deepEqual(summary.nonMarketDays, ['20261017']);
  assert.equal(summary.vetoed, 3); // el sabado NO se cuenta como veto
  assert.equal(summary.measured, 0);
});

test('summarizeLedger con el dia corregido por --force usa la ULTIMA fila del dia', () => {
  const rows = [
    { day: '20261017', status: 'NO_MEDIDO_REGIMEN' }, // fila vieja (antes del fix)
    { day: '20261017', status: 'NON_MARKET_DAY' }, // fila nueva
  ];
  const summary = summarizeLedger(rows, null);
  assert.equal(summary.rows, 1);
  assert.equal(summary.total, 0);
  assert.equal(summary.nonMarket, 1);
  assert.equal(summary.vetoed, 0);
});

test('summarizeLedger sin filas no fabrica ceros: total 0 y nonMarket 0', () => {
  const summary = summarizeLedger([], null);
  assert.equal(summary.rows, 0);
  assert.equal(summary.total, 0);
  assert.equal(summary.nonMarket, 0);
  assert.equal(summary.gate, null);
});

