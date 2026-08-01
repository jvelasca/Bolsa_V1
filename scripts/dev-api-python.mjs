#!/usr/bin/env node

/**

 * Arranca la API Python (FastAPI) con python -m uvicorn.

 * Uso: node scripts/dev-api-python.mjs

 *

 * Solo comprueba que PostgreSQL responda (~100 ms). No arranca Docker.

 * Setup completo: node scripts/db-ensure.mjs

 */

import { spawn } from 'node:child_process';

import { join, dirname } from 'node:path';

import { fileURLToPath } from 'node:url';

import { checkPort } from './lib/docker.mjs';

import { resolvePython } from './lib/python.mjs';

import { ensurePortFree, freePort } from './lib/ports.mjs';



const root = join(dirname(fileURLToPath(import.meta.url)), '..');

const apiDir = join(root, 'apps', 'api-python');

const port = Number(process.env.API_PYTHON_PORT ?? '8000');

const python = resolvePython();



const postgresUp = await checkPort('127.0.0.1', 5432);

if (!postgresUp) {

  console.error('[dev-api-python] PostgreSQL no responde en localhost:5432');

  console.error('');

  console.error('  1. Abre Docker Desktop y espera a que esté en verde');

  console.error('  2. Ejecuta una vez: node scripts/db-ensure.mjs');

  console.error('  3. Vuelve a lanzar el debug');

  console.error('');

  console.error('  Tip: deja Docker + bolsa-postgres corriendo; el debug arranca al instante.');

  process.exit(1);

}



if (freePort(port)) {

  console.log(`[dev-api-python] Puerto ${port} liberado (procesos uvicorn anteriores)`);

}



ensurePortFree(port, { label: 'dev-api-python' });



console.log(`[dev-api-python] PostgreSQL OK - Python: ${python} - http://0.0.0.0:${port}`);



const child = spawn(

  python,

  [join(apiDir, 'run_dev.py')],

  {

    cwd: apiDir,

    stdio: 'inherit',

    shell: false,

    env: {

      ...process.env,

      PYTHONPATH: join(apiDir, 'src'),

      API_PYTHON_PORT: String(port),

    },

  },

);



child.on('exit', (code) => process.exit(code ?? 0));

