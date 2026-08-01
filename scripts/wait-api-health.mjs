#!/usr/bin/env node
/** Wrapper CLI — espera API (preLaunchTask Web legacy). */
import { waitForApi } from './lib/wait-api.mjs';

const result = await waitForApi({
  log: (msg) => console.log(`[wait-api] ${msg}`),
});

if (!result.ok) {
  console.error('');
  console.error('  Usa F5 → «Bolsa: F5 Dev (recomendado)» (arranca API + Web juntos).');
  console.error('  O arranca la API: node scripts/dev-api-python.mjs');
  console.error('');
  process.exit(1);
}
