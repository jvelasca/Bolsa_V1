import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import net from 'node:net';
import { join } from 'node:path';
import { logError, logInfo } from './logger.mjs';

export const ROOT = new URL('../..', import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1');

const DOCKER_DESKTOP_PATHS = {
  win32: [
    join(process.env.ProgramFiles ?? 'C:\\Program Files', 'Docker', 'Docker', 'Docker Desktop.exe'),
    join(process.env.ProgramFiles ?? 'C:\\Program Files', 'Docker', 'Docker', 'Docker Desktop.exe'),
  ],
  darwin: ['/Applications/Docker.app'],
  linux: [],
};

const DOCKER_CLI_CANDIDATES = [
  process.env.DOCKER_EXE,
  'docker',
  join(process.env.ProgramFiles ?? 'C:\\Program Files', 'Docker', 'Docker', 'resources', 'bin', 'docker.exe'),
].filter(Boolean);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function findDockerExe() {
  for (const cmd of DOCKER_CLI_CANDIDATES) {
    const result = spawnSync(cmd, ['--version'], { shell: true, encoding: 'utf8' });
    if (result.status === 0) return cmd;
  }
  return null;
}

export function isDockerDaemonRunning(docker = findDockerExe()) {
  if (!docker) return false;
  const result = spawnSync(docker, ['info'], {
    shell: true,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  return result.status === 0;
}

function findDockerDesktopApp() {
  const platform = process.platform;
  const paths = DOCKER_DESKTOP_PATHS[platform] ?? [];
  return paths.find((p) => existsSync(p)) ?? null;
}

export async function startDockerDesktop() {
  const app = findDockerDesktopApp();
  if (!app) {
    return { started: false, reason: 'Docker Desktop no encontrado en el sistema' };
  }

  logInfo('docker', `Abriendo Docker Desktop: ${app}`);

  if (process.platform === 'win32') {
    spawn(`"${app}"`, [], { shell: true, detached: true, stdio: 'ignore' }).unref();
  } else if (process.platform === 'darwin') {
    spawn('open', ['-a', 'Docker'], { detached: true, stdio: 'ignore' }).unref();
  } else {
    return { started: false, reason: 'Arranque automático solo en Windows/macOS. Inicia Docker manualmente.' };
  }

  return { started: true };
}

export async function waitForDockerDaemon(docker, options = {}) {
  const maxAttempts = options.maxAttempts ?? 40;
  const intervalMs = options.intervalMs ?? 3000;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    if (isDockerDaemonRunning(docker)) {
      logInfo('docker', `Docker daemon listo (intento ${attempt})`);
      return true;
    }
    if (attempt === 1) {
      logInfo('docker', 'Esperando a que Docker Desktop arranque...');
    }
    await sleep(intervalMs);
  }

  return false;
}

export async function ensureDockerRunning(options = {}) {
  const docker = findDockerExe();

  if (!docker) {
    return {
      ok: false,
      docker: null,
      error: 'DOCKER_NOT_INSTALLED',
      message:
        'Docker no está instalado. Instala Docker Desktop: https://www.docker.com/products/docker-desktop/',
    };
  }

  if (isDockerDaemonRunning(docker)) {
    return { ok: true, docker, started: false, message: 'Docker ya estaba en marcha' };
  }

  const launch = await startDockerDesktop();
  if (!launch.started) {
    return {
      ok: false,
      docker,
      error: 'DOCKER_DESKTOP_NOT_FOUND',
      message: launch.reason ?? 'No se pudo abrir Docker Desktop',
    };
  }

  const ready = await waitForDockerDaemon(docker, options);
  if (!ready) {
    return {
      ok: false,
      docker,
      error: 'DOCKER_DAEMON_TIMEOUT',
      message: 'Docker Desktop no respondió a tiempo. Ábrelo manualmente y espera a que esté en verde.',
    };
  }

  return { ok: true, docker, started: true, message: 'Docker Desktop iniciado correctamente' };
}

export function checkPort(host, port, timeoutMs = 2000) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port });
    socket.setTimeout(timeoutMs);
    socket.on('connect', () => {
      socket.destroy();
      resolve(true);
    });
    socket.on('timeout', () => {
      socket.destroy();
      resolve(false);
    });
    socket.on('error', () => resolve(false));
  });
}

/**
 * ¿Postgres acepta queries? TCP abierto ≠ listo: tras cold start de Docker
 * el puerto 5432 responde mientras el motor aún dice «starting up» y el seed
 * Prisma falla (primer F5 aborta; el segundo pasa). Preferimos `pg_isready`.
 */
export function isPostgresReady(docker = findDockerExe(), options = {}) {
  const container = options.container ?? 'bolsa-postgres';
  const user = options.user ?? 'bolsa';
  const db = options.db ?? 'bolsa_v1';
  if (!docker) return false;
  const result = spawnSync(
    docker,
    ['exec', container, 'pg_isready', '-U', user, '-d', db],
    {
      shell: true,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );
  return result.status === 0;
}

export async function waitForPostgres(options = {}) {
  const host = options.host ?? '127.0.0.1';
  const port = options.port ?? 5432;
  const maxAttempts = options.maxAttempts ?? 40;
  const intervalMs = options.intervalMs ?? 1500;
  const docker = options.docker ?? findDockerExe();

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    if (docker && isPostgresReady(docker, options)) {
      logInfo(
        'docker',
        `PostgreSQL listo (pg_isready, intento ${attempt}) en ${host}:${port}`,
      );
      return true;
    }
    // Fallback sin CLI docker: TCP (más débil; no distingue «starting up»).
    if (!docker && (await checkPort(host, port))) {
      logInfo('docker', `PostgreSQL responde en ${host}:${port} (TCP)`);
      return true;
    }
    if (attempt === 1) {
      logInfo(
        'docker',
        'Esperando a que PostgreSQL acepte conexiones (pg_isready)...',
      );
    }
    await sleep(intervalMs);
  }

  return false;
}

export function startPostgresContainer(docker) {
  logInfo('docker', 'Levantando contenedor PostgreSQL (docker compose up -d)...');
  const result = spawnSync(docker, ['compose', 'up', '-d'], {
    cwd: ROOT,
    shell: true,
    encoding: 'utf8',
    stdio: 'inherit',
  });

  return result.status === 0;
}

/**
 * Asegura Docker Desktop + contenedor PostgreSQL del proyecto.
 * Usado antes de `pnpm dev`, setup y arranque desde Cursor.
 */
export async function ensureProjectDatabase(options = {}) {
  const dockerResult = await ensureDockerRunning(options);
  if (!dockerResult.ok) {
    return { ok: false, step: 'docker', ...dockerResult };
  }

  const docker = dockerResult.docker;
  const alreadyAccepting = isPostgresReady(docker);

  if (!alreadyAccepting) {
    const tcpOpen = await checkPort('127.0.0.1', 5432);
    if (!tcpOpen) {
      const started = startPostgresContainer(docker);
      if (!started) {
        return {
          ok: false,
          step: 'postgres',
          docker,
          error: 'COMPOSE_FAILED',
          message: 'No se pudo levantar el contenedor bolsa-postgres',
        };
      }
    } else {
      // Puerto abierto pero motor aún en recovery tras cold start de Docker.
      logInfo(
        'docker',
        'Puerto 5432 abierto — esperando pg_isready (evita fallo seed en 1.er F5)',
      );
    }

    const ready = await waitForPostgres({ ...options, docker });
    if (!ready) {
      return {
        ok: false,
        step: 'postgres',
        docker,
        error: 'POSTGRES_TIMEOUT',
        message:
          'PostgreSQL no aceptó conexiones a tiempo (pg_isready). Reintenta F5 o: docker compose up -d',
      };
    }
  } else {
    logInfo('docker', 'PostgreSQL ya listo (pg_isready)');
  }

  return {
    ok: true,
    docker,
    dockerStarted: dockerResult.started,
    postgresStarted: !alreadyAccepting,
    message: 'Docker y PostgreSQL listos',
  };
}

export function printDockerInstallHelp() {
  console.log(`
Docker no está disponible.

Instalación (Windows):
  winget install Docker.DockerDesktop

Luego abre Docker Desktop y ejecuta:
  pnpm db:ensure
`);
}

export function printDockerRoleInProject() {
  console.log(`
¿Qué hace Docker en Bolsa V1?
────────────────────────────
Docker NO ejecuta la app (React ni la API). Solo levanta PostgreSQL,
la base de datos local donde se guardan:

  • Catálogo IBEX 35 (instrumentos)
  • Históricos OHLCV sincronizados desde Yahoo
  • Logs de sincronización

Contenedor: bolsa-postgres  →  PostgreSQL 16  →  localhost:5432
Configuración: docker-compose.yml
Datos persistentes: volumen Docker bolsa_pg_data (no se pierden al reiniciar)

Flujo:  Web/API (Node)  →  Prisma  →  PostgreSQL (Docker)
`);
}
