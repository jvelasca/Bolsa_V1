/**
 * Regresiones del modulo PURO del runner de la ventana PAPER.
 *
 * Cubre las tres guardias del sello `2.11.31` (Muerden de verdad: revertir la
 * proteccion en `window-forward.mjs` pone el test en rojo):
 *   - config de freeze inmutable salvo `unsafeOverride`;
 *   - lock diario (`--force` no salta un lock vivo);
 *   - provenance del gate (status no pinta material stale).
 *
 * Ejecutar: `pnpm window:test` (o `node --test scripts/lib/window-forward.test.mjs`).
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  LOCK_TTL_MS,
  WINDOW_CONFIG,
  classifyPreflight,
  isPreflightPayload,
  lockDecision,
  parseGate,
  parseRevParse,
  resolveDayStatus,
  verifyWindowProvenance,
  windowConfig,
} from './window-forward.mjs';

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
