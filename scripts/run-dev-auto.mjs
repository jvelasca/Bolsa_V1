/**
 * `pnpm dev:auto` — arranque de DESARROLLO con el perfil AUTO completo encendido.
 *
 * Por qué existe: `pnpm dev` deja AUTO apagado a propósito (el repo no opera solo). Pero
 * probar AUTO exigía recordar seis variables y sus defaults; la auditoría externa de
 * 2026-11-08 encontró que el gobernador y el veto por ATR nacían OFF y que el «precio
 * real» OFF fabricaba 100.0 en el camino hermético. Este script enciende el perfil
 * COMPLETO y lo declara, sin tocar `pnpm dev`.
 *
 * Reglas:
 *  - Las variables ya presentes en el entorno (o en `.env`) tienen prioridad: esto solo
 *    rellena lo que falta. Un `AUTO_ENGINE_SIM_V2=0` explícito se respeta.
 *  - Identidad de motor ESTABLE de desarrollo (`auto-dev-local`) para no mezclar filas.
 *  - No es producción: el worker sigue siendo SIM y la cuenta es la DEMO canónica.
 */

import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));

/** Perfil dev: todo lo que la auditoría pedía declarado y encendido EN ESTE PERFIL. */
const AUTO_DEV_PROFILE = {
  AUTO_SIMULATION_WORKER_ENABLED: '1',
  AUTO_ENGINE_SIM_V2: '1',
  AUTO_ENGINE_SIM_REAL_PRICE: '1',
  AUTO_ENGINE_SIM_V2_GOVERNOR: '1',
  AUTO_ENGINE_SIM_V2_ATR_REQUIRED: '1',
  AUTO_ENGINE_SIM_V2_ACCOUNT_MAX_DD_PCT: '15',
  AUTO_ENGINE_SIM_V2_COST_MODEL: '1',
  AUTO_ENGINE_SIM_V2_COMMISSION_BPS: '10',
  AUTO_ENGINE_SIM_V2_SPREAD_BPS: '2',
  AUTO_ENGINE_SIM_V2_SLIPPAGE_BPS: '5',
  AUTO_ENGINE_SIM_V2_EQUITY: '100000',
  AUTO_ENGINE_SIM_ENGINE_ID: 'auto-dev-local',
  AUTO_ENGINE_SIM_ACCOUNT_ID: 'default-account-seed',
};

const missing = Object.entries(AUTO_DEV_PROFILE).filter(
  ([name]) => !(process.env[name] ?? '').trim(),
);

if (missing.length === 0) {
  console.log('[dev:auto] el entorno ya declara el perfil completo; no se cambia nada.');
} else {
  console.log(
    `[dev:auto] perfil AUTO dev: ${missing.map(([name]) => name).join(', ')} ` +
      '(los valores ya declarados se respetan).',
  );
}

const child = spawn(process.execPath, [join(ROOT, 'scripts', 'run-dev.mjs'), ...process.argv.slice(2)], {
  cwd: ROOT,
  stdio: 'inherit',
  env: {
    ...AUTO_DEV_PROFILE,
    // Una variable heredada vacía NO debe borrar el perfil: solo cuenta si trae valor.
    ...Object.fromEntries(
      Object.entries(process.env).filter(([, value]) => (value ?? '').trim() !== ''),
    ),
  },
});

const forward = (signal) => {
  if (!child.killed) child.kill(signal);
};

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => forward(signal));
}

child.on('exit', (code) => {
  process.exit(code ?? 0);
});
