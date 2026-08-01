#!/usr/bin/env node
/**
 * Informe de arranque para agente/diagnóstico.
 * Lee logs/startup/latest.json y logs/agent/doctor.json
 */
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { readLatestStartupReport } from './lib/startup-timeline.mjs';
import { ROOT } from './lib/logger.mjs';

function readJson(path) {
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return null;
  }
}

const startup = readLatestStartupReport();
const doctor = readJson(join(ROOT, 'logs', 'agent', 'doctor.json'));
const dev = readJson(join(ROOT, 'logs', 'agent', 'dev.json'));

console.log('=== Bolsa V1 — informe arranque / rendimiento ===\n');

if (doctor) {
  console.log(`Doctor (${doctor.at}): ${doctor.status}`);
  for (const c of doctor.checks ?? []) {
    console.log(`  ${c.ok ? 'OK' : 'FAIL'} ${c.name}: ${c.detail}`);
  }
  console.log('');
}

if (startup) {
  console.log(`Último startup (${startup.startedAt}): ${startup.status} — ${startup.totalMs}ms total`);
  for (const step of startup.steps ?? []) {
    const delta = step.sincePreviousMs != null ? ` (+${step.sincePreviousMs}ms)` : '';
    console.log(`  ${step.elapsedMs}ms  ${step.step}${delta}`);
  }
  console.log('');
} else {
  console.log('Sin logs/startup/latest.json — ejecuta pnpm dev o F5 Dev primero.\n');
}

if (dev) {
  console.log(`Último dev session: ${dev.status} @ ${dev.at}`);
}

console.log('\nArchivos: logs/startup/latest.json · logs/agent/*.json · logs/dev/*.log');
