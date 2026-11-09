/**
 * `pnpm dev:lan` — arranque de desarrollo accesible desde la LAN, con autenticación OBLIGATORIA.
 *
 * Por qué existe: `vite.config.ts` tenía `host: true` fijo, así que CUALQUIER `pnpm dev`
 * exponía la web en la red local. Y con el proxy de Vite la API ve las peticiones como
 * loopback, de modo que los parches de «solo loopback» de la API no protegen nada: la
 * única protección real es la autenticación o no bindear la interfaz.
 *
 * Este perfil:
 *  - exige `APP_PASSWORD` y `APP_AUTH_SECRET` ANTES de arrancar (lee `.env` y el entorno);
 *  - pone `WEB_HOST=0.0.0.0` explícitamente (el default de `pnpm dev` es 127.0.0.1);
 *  - NO expone la API a la LAN: el proxy de Vite reenvía a 127.0.0.1.
 */

import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { loadEnvFile } from './lib/load-env.mjs';

const ROOT = fileURLToPath(new URL('..', import.meta.url));

loadEnvFile();

const missing = ['APP_PASSWORD', 'APP_AUTH_SECRET'].filter(
  (name) => !(process.env[name] ?? '').trim(),
);

if (missing.length > 0) {
  console.error(
    `[dev:lan] Faltan ${missing.join(', ')}. La LAN no se abre sin autenticación: ` +
      'define ambas en .env (APP_PASSWORD activo exige APP_AUTH_SECRET) o usa `pnpm dev` ' +
      '(loopback, sin exposición).',
  );
  process.exit(1);
}

console.warn(
  '[dev:lan] Vite escuchará en 0.0.0.0. La API queda en loopback y el proxy reenvía: ' +
    'la protección frente a la LAN es la autenticación, no un bind local de la API.',
);

const child = spawn(
  process.execPath,
  [join(ROOT, 'scripts', 'run-dev.mjs'), ...process.argv.slice(2)],
  {
    cwd: ROOT,
    stdio: 'inherit',
    env: {
      ...process.env,
      WEB_HOST: (process.env.WEB_HOST ?? '').trim() || '0.0.0.0',
    },
  },
);

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    if (!child.killed) child.kill(signal);
  });
}

child.on('exit', (code) => {
  process.exit(code ?? 0);
});
