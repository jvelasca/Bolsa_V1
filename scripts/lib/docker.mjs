import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import net from "node:net";
import { join } from "node:path";
import { logError, logInfo } from "./logger.mjs";

export const ROOT = new URL("../..", import.meta.url).pathname.replace(
  /^\/([A-Z]:)/,
  "$1",
);

const DOCKER_DESKTOP_PATHS = {
  win32: [
    join(
      process.env.ProgramFiles ?? "C:\\Program Files",
      "Docker",
      "Docker",
      "Docker Desktop.exe",
    ),
    join(
      process.env.ProgramFiles ?? "C:\\Program Files",
      "Docker",
      "Docker",
      "Docker Desktop.exe",
    ),
  ],
  darwin: ["/Applications/Docker.app"],
  linux: [],
};

const DOCKER_CLI_CANDIDATES = [
  process.env.DOCKER_EXE,
  "docker",
  join(
    process.env.ProgramFiles ?? "C:\\Program Files",
    "Docker",
    "Docker",
    "resources",
    "bin",
    "docker.exe",
  ),
].filter(Boolean);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function findDockerExe() {
  for (const cmd of DOCKER_CLI_CANDIDATES) {
    const result = spawnSync(cmd, ["--version"], {
      shell: true,
      encoding: "utf8",
    });
    if (result.status === 0) return cmd;
  }
  return null;
}

/*
 * Transporte de clientes PostgreSQL (V2.15 C2 / C2-13).
 *
 * Por defecto los scripts de backup/restore/DR hablan con la BD del proyecto a
 * través de `docker exec bolsa-postgres` (la máquina de dev normalmente no tiene
 * `psql`/`pg_dump` instalados como binarios de host). El auditor externo (C2-12 /
 * C2-13) exige ejercitar la batería DR en el CI release-tag, donde NO existe el
 * contenedor `bolsa-postgres` sino un servicio `postgres` alcanzable por TCP en
 * `127.0.0.1:5432`.
 *
 * Para no debilitar el DR local (Docker queda intacto por defecto), añadimos un
 * modo TCP opt-in por entorno: si `BOLSA_DR_TCP=1`, los mismos helpers usan
 * los binarios de host `psql`/`pg_dump` conectados por red a
 * `PGHOST/PGPORT/PGUSER/PGPASSWORD` (o `DB_*` como fallback) en vez de `docker
 * exec`. El CI instala `postgresql-client` (apt) y fija `BOLSA_DR_TCP=1`.
 */

const TCP_MODE_ENV = "BOLSA_DR_TCP";
const TRUTHY = new Set(["1", "true", "yes", "y", "on"]);

export function useTcpTransport() {
  const raw = (process.env[TCP_MODE_ENV] ?? "").toString().trim().toLowerCase();
  return TRUTHY.has(raw);
}

export function tcpPgConfig() {
  return {
    host: process.env.PGHOST ?? process.env.DB_HOST ?? "127.0.0.1",
    port: process.env.PGPORT ?? process.env.DB_PORT ?? "5432",
    user: process.env.PGUSER ?? process.env.DB_USER ?? "bolsa",
    password: process.env.PGPASSWORD ?? process.env.DB_PASSWORD ?? "",
  };
}

/**
 * Base de invocación de `psql` según el transporte activo.
 * Devuelve `{ bin, argv, env, tcp }`; el llamante añade el tail de flags/SQL.
 *   - docker (default dev): bin=docker · argv=[exec, (-i), container, psql, -U, user, -d, db]
 *   - tcp (BOLSA_DR_TCP=1): bin=psql · argv=[-h, host, -p, port, -U, user, -d, db] + PGPASSWORD
 * @param {{db:string, container?:string, user?:string, interactive?:boolean}} opts
 */
export function psqlBase(opts = {}) {
  const db = opts.db;
  const tcp = useTcpTransport();
  if (tcp) {
    const t = tcpPgConfig();
    return {
      bin: "psql",
      argv: ["-h", t.host, "-p", String(t.port), "-U", t.user, "-d", db],
      env: t.password ? { PGPASSWORD: t.password } : {},
      tcp: true,
    };
  }
  const docker = findDockerExe() ?? "docker";
  const interactiveFlag = opts.interactive ? ["-i"] : [];
  return {
    bin: docker,
    argv: [
      "exec",
      ...interactiveFlag,
      opts.container ?? "bolsa-postgres",
      "psql",
      "-U",
      opts.user ?? "bolsa",
      "-d",
      db,
    ],
    env: {},
    tcp: false,
  };
}

/**
 * Base de invocación de `pg_dump` (mismo transporte que psqlBase).
 * @param {{db:string, container?:string, user?:string}} opts
 */
export function pgDumpBase(opts = {}) {
  const db = opts.db;
  const tcp = useTcpTransport();
  if (tcp) {
    const t = tcpPgConfig();
    return {
      bin: "pg_dump",
      argv: ["-h", t.host, "-p", String(t.port), "-U", t.user, "-d", db],
      env: t.password ? { PGPASSWORD: t.password } : {},
      tcp: true,
    };
  }
  const docker = findDockerExe() ?? "docker";
  return {
    bin: docker,
    argv: [
      "exec",
      opts.container ?? "bolsa-postgres",
      "pg_dump",
      "-U",
      opts.user ?? "bolsa",
      "-d",
      db,
    ],
    env: {},
    tcp: false,
  };
}

/** Env fusionada lista para spawnSync (añade PGPASSWORD sólo si aplica). */
export function clientEnv(base) {
  return Object.keys(base.env).length
    ? { ...process.env, ...base.env }
    : process.env;
}

export function isDockerDaemonRunning(docker = findDockerExe()) {
  if (!docker) return false;
  const result = spawnSync(docker, ["info"], {
    shell: true,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
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
    return {
      started: false,
      reason: "Docker Desktop no encontrado en el sistema",
    };
  }

  logInfo("docker", `Abriendo Docker Desktop: ${app}`);

  if (process.platform === "win32") {
    spawn(`"${app}"`, [], {
      shell: true,
      detached: true,
      stdio: "ignore",
    }).unref();
  } else if (process.platform === "darwin") {
    spawn("open", ["-a", "Docker"], {
      detached: true,
      stdio: "ignore",
    }).unref();
  } else {
    return {
      started: false,
      reason:
        "Arranque automático solo en Windows/macOS. Inicia Docker manualmente.",
    };
  }

  return { started: true };
}

export async function waitForDockerDaemon(docker, options = {}) {
  const maxAttempts = options.maxAttempts ?? 40;
  const intervalMs = options.intervalMs ?? 3000;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    if (isDockerDaemonRunning(docker)) {
      logInfo("docker", `Docker daemon listo (intento ${attempt})`);
      return true;
    }
    if (attempt === 1) {
      logInfo("docker", "Esperando a que Docker Desktop arranque...");
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
      error: "DOCKER_NOT_INSTALLED",
      message:
        "Docker no está instalado. Instala Docker Desktop: https://www.docker.com/products/docker-desktop/",
    };
  }

  if (isDockerDaemonRunning(docker)) {
    return {
      ok: true,
      docker,
      started: false,
      message: "Docker ya estaba en marcha",
    };
  }

  const launch = await startDockerDesktop();
  if (!launch.started) {
    return {
      ok: false,
      docker,
      error: "DOCKER_DESKTOP_NOT_FOUND",
      message: launch.reason ?? "No se pudo abrir Docker Desktop",
    };
  }

  const ready = await waitForDockerDaemon(docker, options);
  if (!ready) {
    return {
      ok: false,
      docker,
      error: "DOCKER_DAEMON_TIMEOUT",
      message:
        "Docker Desktop no respondió a tiempo. Ábrelo manualmente y espera a que esté en verde.",
    };
  }

  return {
    ok: true,
    docker,
    started: true,
    message: "Docker Desktop iniciado correctamente",
  };
}

export function checkPort(host, port, timeoutMs = 2000) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port });
    socket.setTimeout(timeoutMs);
    socket.on("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.on("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.on("error", () => resolve(false));
  });
}

/**
 * ¿Postgres acepta queries? TCP abierto ≠ listo: tras cold start de Docker
 * el puerto 5432 responde mientras el motor aún dice «starting up» y el seed
 * Prisma falla (primer F5 aborta; el segundo pasa). Preferimos `pg_isready`.
 */
export function isPostgresReady(docker = findDockerExe(), options = {}) {
  const container = options.container ?? "bolsa-postgres";
  const user = options.user ?? "bolsa";
  const db = options.db ?? "bolsa_v1";
  if (!docker) return false;
  const result = spawnSync(
    docker,
    ["exec", container, "pg_isready", "-U", user, "-d", db],
    {
      shell: true,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  return result.status === 0;
}

export async function waitForPostgres(options = {}) {
  const host = options.host ?? "127.0.0.1";
  const port = options.port ?? 5432;
  const maxAttempts = options.maxAttempts ?? 40;
  const intervalMs = options.intervalMs ?? 1500;
  const docker = options.docker ?? findDockerExe();

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    if (docker && isPostgresReady(docker, options)) {
      logInfo(
        "docker",
        `PostgreSQL listo (pg_isready, intento ${attempt}) en ${host}:${port}`,
      );
      return true;
    }
    // Fallback sin CLI docker: TCP (más débil; no distingue «starting up»).
    if (!docker && (await checkPort(host, port))) {
      logInfo("docker", `PostgreSQL responde en ${host}:${port} (TCP)`);
      return true;
    }
    if (attempt === 1) {
      logInfo(
        "docker",
        "Esperando a que PostgreSQL acepte conexiones (pg_isready)...",
      );
    }
    await sleep(intervalMs);
  }

  return false;
}

export function startPostgresContainer(docker) {
  logInfo(
    "docker",
    "Levantando contenedor PostgreSQL (docker compose up -d)...",
  );
  const result = spawnSync(docker, ["compose", "up", "-d"], {
    cwd: ROOT,
    shell: true,
    encoding: "utf8",
    stdio: "inherit",
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
    return { ok: false, step: "docker", ...dockerResult };
  }

  const docker = dockerResult.docker;
  const alreadyAccepting = isPostgresReady(docker);

  if (!alreadyAccepting) {
    const tcpOpen = await checkPort("127.0.0.1", 5432);
    if (!tcpOpen) {
      const started = startPostgresContainer(docker);
      if (!started) {
        return {
          ok: false,
          step: "postgres",
          docker,
          error: "COMPOSE_FAILED",
          message: "No se pudo levantar el contenedor bolsa-postgres",
        };
      }
    } else {
      // Puerto abierto pero motor aún en recovery tras cold start de Docker.
      logInfo(
        "docker",
        "Puerto 5432 abierto — esperando pg_isready (evita fallo seed en 1.er F5)",
      );
    }

    const ready = await waitForPostgres({ ...options, docker });
    if (!ready) {
      return {
        ok: false,
        step: "postgres",
        docker,
        error: "POSTGRES_TIMEOUT",
        message:
          "PostgreSQL no aceptó conexiones a tiempo (pg_isready). Reintenta F5 o: docker compose up -d",
      };
    }
  } else {
    logInfo("docker", "PostgreSQL ya listo (pg_isready)");
  }

  return {
    ok: true,
    docker,
    dockerStarted: dockerResult.started,
    postgresStarted: !alreadyAccepting,
    message: "Docker y PostgreSQL listos",
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
