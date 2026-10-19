#!/usr/bin/env node
/**
 * Runner de la ventana PAPER forward (>=4 dias) sobre el arbol congelado
 * `v2.88.29-beta`. Encadena, por dia, el pipeline del runbook §3.1:
 *
 *   preflight (v2_76 --preflight-only)
 *     -> forward (v2_76)
 *       -> journal (v2_77)
 *         -> ventana (v2_80)
 *           -> auditoria (v2_83)
 *
 * Ops-only: NO toca motor, gobernador, `TOP_N`, umbrales, allocation, pesos A/B
 * ni migraciones. Un dia con veto de regimen (`BEAR_TREND`, LONG vetadas) se
 * DECLARA como `NO_MEDIDO_REGIMEN` (no es un fallo y no se fuerza el regimen).
 *
 * Uso (desde la raiz del repo):
 *   node scripts/window-forward-runner.mjs preflight
 *   node scripts/window-forward-runner.mjs run-day [--force] [--skip-api-check]
 *   node scripts/window-forward-runner.mjs status
 *   node scripts/window-forward-runner.mjs task:install [--at 18:00]
 *   node scripts/window-forward-runner.mjs task:remove
 *   node scripts/window-forward-runner.mjs --dry-run run-day
 *
 * Docs: docs/engineering/runbook-ventana-forward-v2.78-2026-09-27.md
 *       docs/engineering/arranque-ventana-paper-operativa-2026-09-27.md
 */
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  appendFileSync,
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { hostname } from "node:os";
import { dirname, join } from "node:path";
import { loadEnvFile } from "./lib/load-env.mjs";
import { ROOT, logError, logInfo, logWarn } from "./lib/logger.mjs";
import {
  AUDIT_JSON,
  FORWARD_GLOB,
  LEDGER_PATH,
  RUNS_DIR,
  WINDOW_HTML,
  WINDOW_JSON,
  WINDOW_MIN_CYCLES,
  WINDOW_MIN_DAYS,
  WINDOW_MIN_EPISODES,
  classifyExit,
  classifyPreflight,
  cmdWrapperContent,
  dayIso,
  dayStamp,
  forwardPath,
  freezeCheck,
  isMarketDay,
  isPreflightPayload,
  isTerminalStatus,
  lockDecision,
  NON_MARKET_DAY_STATUS,
  parseGate,
  parseJsonLoose,
  parsePreflight,
  parseRevParse,
  resolveDayStatus,
  runDir,
  runLockDir,
  START_WHEN_AVAILABLE_MARKER,
  summarizeLedger,
  taskXml,
  unlockDecision,
  verifyWindowProvenance,
  windowConfig,
} from "./lib/window-forward.mjs";

const SCRIPT_FORWARD =
  "apps/api-python/scripts/v2_76_forward_market_material.py";
const SCRIPT_JOURNAL = "apps/api-python/scripts/v2_77_market_operability.py";
const SCRIPT_WINDOW = "apps/api-python/scripts/v2_80_market_window.py";
const SCRIPT_AUDIT = "apps/api-python/scripts/v2_83_window_audit.py";
const SCRIPT_EVIDENCE =
  "apps/api-python/scripts/v2_100_operational_certification_evidence.py";

const TASK_NAME = "BolsaV1_WindowForward";
const DEFAULT_TASK_TIME = "18:00";
//: v2.88.142 — vigía diario: tarea INDEPENDIENTE del stack dev, después del run-day.
const WATCH_TASK_NAME = "BolsaV1_WindowWatch";
const DEFAULT_WATCH_TIME = "20:20";
const WATCH_MODULE = "bolsa_api.background.window_day_watch_worker";
/** Exit code del CLI del vigía cuando hay día perdido/HARD_ERROR (queda en `LastTaskResult`). */
const WATCH_ALERT_EXIT = 3;
const SCOPE = "window";

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const flags = {
    force: false,
    dryRun: false,
    skipApiCheck: false,
    unsafeOverride: false,
    json: false,
    noPersist: false,
    noWatch: false,
    at: null,
    watchAt: null,
    lookbackDays: null,
    help: false,
  };
  const positionals = [];
  const unknown = [];
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--force") flags.force = true;
    else if (arg === "--dry-run") flags.dryRun = true;
    else if (arg === "--skip-api-check") flags.skipApiCheck = true;
    else if (arg === "--unsafe-override-window-config")
      flags.unsafeOverride = true;
    else if (arg === "--json") flags.json = true;
    else if (arg === "--no-persist") flags.noPersist = true;
    else if (arg === "--no-watch") flags.noWatch = true;
    else if (arg === "--help" || arg === "-h") flags.help = true;
    else if (arg === "--at") {
      flags.at = argv[i + 1] ?? null;
      i += 1;
    } else if (arg.startsWith("--at=")) flags.at = arg.slice("--at=".length);
    else if (arg === "--watch-at") {
      flags.watchAt = argv[i + 1] ?? null;
      i += 1;
    } else if (arg.startsWith("--watch-at="))
      flags.watchAt = arg.slice("--watch-at=".length);
    else if (arg === "--lookback-days") {
      flags.lookbackDays = argv[i + 1] ?? null;
      i += 1;
    } else if (arg.startsWith("--lookback-days="))
      flags.lookbackDays = arg.slice("--lookback-days=".length);
    else if (arg.startsWith("--")) unknown.push(arg);
    else positionals.push(arg);
  }
  return { command: positionals[0] ?? "help", positionals, flags, unknown };
}

function printHelp() {
  console.log(`Runner de la ventana PAPER forward (v2.88.30-beta)

Comandos:
  preflight                 Solo v2_76 --preflight-only (read-only). Declara el regimen de hoy.
  run-day [--force]         Dia completo: preflight -> forward -> v2_77 -> v2_80 -> v2_83.
  status                    Dias del ledger + gate LIGADO al run (>=4 dias, >=2 episodios, >=32 ciclos).
  evidence                  Bundle diario P1-P4 (read-only): certificador v2_98 + cadena ESTUDIO v2_99
                            + enlace DIA-D + aislamiento. Escribe operability_runs/daily-evidence/<DIA>/.
  unlock [--force]          Reclama el lock diario de hoy SOLO si esta huerfano (misma logica de
                            ownership que run-day). Nunca borra un PID vivo de este host: si hay un
                            run en curso, deniega (exit 1). --force solo fuerza un lock ajeno con TTL
                            fresco o un lock ilegible; para un PID vivo, mata el proceso.
  watch [--lookback-days N] Vigia diario (v2.88.142): evalua el dia + arrastre de dias perdidos y
                            AVISA (log + email). NO toca la ventana; deja latido en
                            operability_runs/window-runs/day-watch.json. Exit 0 sin aviso, 3 con aviso.
                            Corre sin el stack dev (su tarea programada es independiente).
  task:install [--at HH:MM] [--watch-at HH:MM]
                            Registra las tareas diarias de Windows (schtasks): run-day (18:00) y
                            vigia (20:20). --no-watch registra solo el run-day. Opcional.
  task:remove               Elimina las tareas diarias de Windows.

Flags:
  --dry-run                 Valida config/freeze/cadena sin abrir el motor.
  --force                   Re-ejecuta un dia ya terminal; NO salta un lock vivo (solo un lock huerfano de otro host/TTL). En unlock, reclama un lock ajeno con TTL fresco o ilegible.
  --skip-api-check          No exige /api/health/ready (el scheduler de barras vive en el API).
  --json                    (watch) Imprime el latido por stdout.
  --no-persist              (watch) No escribe el latido (dry-run).
  --unsafe-override-window-config
                            Permite que WINDOW_APPS_HASH/WINDOW_PACKAGES_HASH/WINDOW_ACCOUNT/
                            WINDOW_VERSION_A/WINDOW_VERSION_B/WINDOW_WATCH_SIZE sustituyan la config
                            certificada. Sella configMode=UNSAFE y el gate deja de ser valido.
  -h, --help                Esta ayuda.`);
}

// ---------------------------------------------------------------------------
// Procesos
// ---------------------------------------------------------------------------

/** Flags de operacion SOLO en el `env` del hijo (no mutan el shell del operador). */
function childEnv(config) {
  return { ...process.env, ...config.operatorEnv };
}

function uvBin() {
  return process.env.WINDOW_UV || "uv";
}

let LAUNCHER = null;

/**
 * Resuelve como lanzar Python, una sola vez:
 *   1. `WINDOW_PY` (override explicito del interprete, p. ej. `python`).
 *   2. `uv run --no-sync python` (convencion del repo), si `uv` puede lanzarlo.
 *   3. `python` directo: algunos entornos bloquean el spawn interno de `uv`
 *      (Application Control) y el interprete activo ya tiene los paquetes.
 */
async function resolveLauncher() {
  if (LAUNCHER) return LAUNCHER;
  if (process.env.WINDOW_PY) {
    LAUNCHER = {
      bin: process.env.WINDOW_PY,
      prefix: [],
      label: process.env.WINDOW_PY,
    };
    return LAUNCHER;
  }
  const uv = uvBin();
  const probe = await runProcess(
    uv,
    ["run", "--no-sync", "python", "-c", "print(0)"],
    {
      echo: false,
    },
  );
  if (probe.code === 0) {
    LAUNCHER = {
      bin: uv,
      prefix: ["run", "--no-sync", "python"],
      label: `${uv} run --no-sync python`,
    };
    return LAUNCHER;
  }
  const detail = (probe.err || "").trim().split(/\r?\n/).pop() || "fallo";
  logWarn(
    SCOPE,
    `uv no puede lanzar python (${detail}); se usa 'python' directo (override con WINDOW_PY)`,
  );
  LAUNCHER = { bin: "python", prefix: [], label: "python" };
  return LAUNCHER;
}

/**
 * Ejecuta un proceso capturando stdout/stderr, con eco opcional a consola y
 * volcado incremental a `logBase.out.txt` / `logBase.err.txt`.
 */
function runProcess(bin, args, options = {}) {
  const {
    cwd = ROOT,
    env = process.env,
    logBase = null,
    echo = true,
  } = options;
  return new Promise((resolve) => {
    let child;
    try {
      child = spawn(bin, args, { cwd, env, shell: false, windowsHide: true });
    } catch (error) {
      resolve({ code: null, out: "", err: "", spawnError: error });
      return;
    }
    const outLog = logBase ? `${logBase}.out.txt` : null;
    const errLog = logBase ? `${logBase}.err.txt` : null;
    if (logBase) {
      mkdirSync(dirname(logBase), { recursive: true });
      writeFileSync(outLog, "", "utf8");
      writeFileSync(errLog, "", "utf8");
    }
    let out = "";
    let err = "";
    child.stdout.on("data", (chunk) => {
      const text = chunk.toString();
      out += text;
      if (echo) process.stdout.write(text);
      if (outLog) appendFileSync(outLog, text, "utf8");
    });
    child.stderr.on("data", (chunk) => {
      const text = chunk.toString();
      err += text;
      if (echo) process.stderr.write(text);
      if (errLog) appendFileSync(errLog, text, "utf8");
    });
    child.on("error", (error) =>
      resolve({ code: null, out, err, spawnError: error }),
    );
    child.on("close", (code) => resolve({ code, out, err }));
  });
}

async function runPython(script, args, options = {}) {
  const launcher = await resolveLauncher();
  return runProcess(
    launcher.bin,
    [...launcher.prefix, join(ROOT, script), ...args],
    options,
  );
}

/**
 * Ejecuta un **módulo** del paquete Python (p. ej. el CLI del vigía) desde `apps/api-python`
 * con su `src` en `PYTHONPATH`, igual que hace el stack dev con sus workers.
 */
async function runPythonModule(moduleName, args, options = {}) {
  const launcher = await resolveLauncher();
  const apiDir = join(ROOT, "apps", "api-python");
  return runProcess(
    launcher.bin,
    [...launcher.prefix, "-m", moduleName, ...args],
    {
      cwd: apiDir,
      env: { ...process.env, PYTHONPATH: join(apiDir, "src") },
      ...options,
    },
  );
}

/** `git rev-parse "HEAD:apps" "HEAD:packages"` + contraste con el sello. */
async function gitFreeze(config) {
  const res = await runProcess(
    "git",
    ["rev-parse", "HEAD:apps", "HEAD:packages"],
    {
      echo: false,
    },
  );
  const revisions = parseRevParse(res.out);
  if (res.code !== 0) {
    return {
      ok: false,
      apps: revisions.apps,
      packages: revisions.packages,
      expectedApps: config.appsHash,
      expectedPackages: config.packagesHash,
      appsOk: false,
      packagesOk: false,
      error: res.err.trim() || "git rev-parse fallo",
    };
  }
  return { ...freezeCheck(revisions, config), error: null };
}

/** Precondicion dura: PostgreSQL listo (`db-ensure --ping`, read-only). */
async function pgPing() {
  const res = await runProcess(
    process.execPath,
    [join(ROOT, "scripts", "db-ensure.mjs"), "--ping"],
    {
      echo: false,
    },
  );
  const lines = `${res.out}\n${res.err}`.trim().split(/\r?\n/);
  return {
    ok: res.code === 0,
    code: res.code,
    message: lines[lines.length - 1] ?? "",
  };
}

/**
 * Precondicion: la API responde `ready` (el scheduler de barras vive en su
 * proceso; sin barras frescas el preflight cae en UNKNOWN).
 */
async function apiReady() {
  const port = process.env.API_PYTHON_PORT || process.env.API_PORT || "8000";
  const url =
    process.env.WINDOW_API_READY_URL ||
    `http://127.0.0.1:${port}/api/health/ready`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(url, { signal: controller.signal });
    return { ok: response.ok, status: response.status, url };
  } catch (error) {
    return {
      ok: false,
      status: null,
      url,
      error: error instanceof Error ? error.message : String(error),
    };
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Artefactos
// ---------------------------------------------------------------------------

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

/** sha256 de un fichero (para sellar y re-verificar el `window.json` del run). */
function sha256File(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

/** ¿El PID existe en ESTE host? (`EPERM` = existe pero no es nuestro). */
function pidAlive(pid) {
  const value = Number(pid);
  if (!Number.isInteger(value) || value <= 0) return false;
  try {
    process.kill(value, 0);
    return true;
  } catch (error) {
    return error?.code === "EPERM";
  }
}

function readLock(day) {
  return readJson(join(ROOT, runLockDir(day), "lock.json"));
}

/**
 * Adquiere el lock diario con `mkdir` (indivisible). Devuelve una funcion de
 * liberacion, o `null` si ya hay un run en curso (`RUN_ALREADY_IN_PROGRESS`).
 * `--force` NO salta un lock vivo: solo permite reclamar uno huerfano de otro
 * host o superado el TTL.
 */
function acquireDayLock(day, iso, command, config, flags) {
  const lockPath = join(ROOT, runLockDir(day));
  mkdirSync(join(ROOT, runDir(day)), { recursive: true });
  const host = hostname();
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const existing = readLock(day);
    const decision = lockDecision({
      lock: existing,
      host,
      isProcessAlive: pidAlive,
      force: flags.force,
    });
    if (decision.action === "blocked") {
      logError(
        SCOPE,
        `RUN_ALREADY_IN_PROGRESS (${decision.reason}): el dia ${day} ya tiene un run en curso ` +
          `(pid ${existing?.pid ?? "n/d"} · host ${existing?.host ?? "n/d"} · ${existing?.startedAt ?? "n/d"})`,
      );
      return null;
    }
    if (decision.action === "reclaim") {
      logWarn(
        SCOPE,
        `lock huerfano (${decision.reason}); se reclama el lock del dia ${day}`,
      );
      rmSync(lockPath, { recursive: true, force: true });
    }
    try {
      mkdirSync(lockPath);
    } catch (error) {
      if (error?.code === "EEXIST") continue; // otra instancia gano la carrera: se reevalua.
      throw error;
    }
    writeFileSync(
      join(lockPath, "lock.json"),
      `${JSON.stringify(
        {
          day,
          dayIso: iso,
          pid: process.pid,
          host,
          startedAt: new Date().toISOString(),
          command,
          configMode: config.configMode,
        },
        null,
        2,
      )}\n`,
      "utf8",
    );
    return () => rmSync(lockPath, { recursive: true, force: true });
  }
  logError(
    SCOPE,
    `no se pudo adquirir el lock del dia ${day} (contencion tras 3 intentos)`,
  );
  return null;
}

/** Dias (bajo `window-runs/`) con un lock vivo en este host; solo para avisar en `status`. */
function activeLockDays() {
  const runsRoot = dirname(join(ROOT, runDir("x")));
  if (!existsSync(runsRoot)) return [];
  const host = hostname();
  const days = [];
  for (const entry of readdirSync(runsRoot, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const lock = readLock(entry.name);
    if (lock && String(lock.host ?? "") === host && pidAlive(lock.pid)) {
      days.push({ day: entry.name, ...lock });
    }
  }
  return days;
}

function readLedger() {
  const path = join(ROOT, LEDGER_PATH);
  if (!existsSync(path)) return [];
  const rows = [];
  for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      rows.push(JSON.parse(trimmed));
    } catch {
      // Fila corrupta: se ignora, nunca se inventa.
    }
  }
  return rows;
}

function appendLedger(entry) {
  const path = join(ROOT, LEDGER_PATH);
  mkdirSync(dirname(path), { recursive: true });
  appendFileSync(path, `${JSON.stringify(entry)}\n`, "utf8");
}

function ledgerEntry(manifest) {
  return {
    day: manifest.day,
    dayIso: manifest.dayIso,
    status: manifest.status,
    veto: manifest.veto,
    reason: manifest.reason,
    account: manifest.account,
    versionA: manifest.versionA,
    watchSize: manifest.watchSize,
    configMode: manifest.configMode ?? "FROZEN",
    configOverrides: manifest.configOverrides ?? [],
    regime: manifest.regime ?? null,
    gate: manifest.gate ?? null,
    freeze: manifest.freeze
      ? {
          ok: manifest.freeze.ok,
          apps: manifest.freeze.apps,
          packages: manifest.freeze.packages,
        }
      : null,
    steps: manifest.steps ?? {},
    startedAt: manifest.startedAt,
    finishedAt: manifest.finishedAt,
    durationMs: manifest.durationMs,
  };
}

/** Sella el dia: adjunta pasos, escribe `manifest.json` y anexa al ledger. */
function finishDay(manifest, steps, artifacts) {
  manifest.steps = steps;
  manifest.artifacts = artifacts;
  manifest.finishedAt = new Date().toISOString();
  manifest.durationMs =
    Date.parse(manifest.finishedAt) - Date.parse(manifest.startedAt);
  const dir = join(ROOT, runDir(manifest.day));
  mkdirSync(dir, { recursive: true });
  writeFileSync(
    join(dir, "manifest.json"),
    `${JSON.stringify(manifest, null, 2)}\n`,
    "utf8",
  );
  appendLedger(ledgerEntry(manifest));
  printDaySummary(manifest);
  return manifest.status;
}

function printDaySummary(manifest) {
  const gate = manifest.gate;
  logInfo(
    SCOPE,
    `dia ${manifest.day} · ${manifest.status}` +
      (manifest.reason ? ` (${manifest.reason})` : "") +
      (manifest.regime
        ? ` · regimen ${manifest.regime.operationalRegime}`
        : ""),
  );
  if (gate) {
    logInfo(
      SCOPE,
      `gate ${gate.verdict} · dias ${gate.days}/${gate.minDays} · ` +
        `episodios ${gate.episodes}/${gate.minEpisodes} · ciclos ${gate.cycles}/${gate.minCycles}`,
    );
  }
}

// ---------------------------------------------------------------------------
// Comandos del pipeline
// ---------------------------------------------------------------------------

function preflightArgs(config) {
  const args = [
    "--preflight-only",
    "--watch-size",
    String(config.watchSize),
    "--json",
  ];
  if (config.watchFromEstudio) args.push("--watch-from-estudio");
  return args;
}

function forwardArgs(config, day) {
  const args = [
    "--account-id",
    config.account,
    "--version-a",
    config.versionA,
    "--watch-size",
    String(config.watchSize),
    "--interval-seconds",
    "60",
    "--max-ticks",
    "400",
    "--stop-when-ready",
    "--level",
    "evidence",
    "--json",
    "--out",
    forwardPath(day),
  ];
  if (config.watchFromEstudio) args.push("--watch-from-estudio");
  return args;
}

async function cmdPreflight(config, flags) {
  const launcher = await resolveLauncher();
  if (flags.dryRun) {
    logInfo(
      SCOPE,
      `--dry-run · preflight: ${launcher.label} ${SCRIPT_FORWARD} ${preflightArgs(config).join(" ")}`,
    );
    return 0;
  }
  const res = await runPython(SCRIPT_FORWARD, preflightArgs(config), {
    env: childEnv(config),
  });
  const classification = classifyPreflight(res.code);
  const prePayload = parseJsonLoose(res.out);
  const payloadOk = isPreflightPayload(prePayload);
  const regime = parsePreflight(prePayload);
  if (regime) {
    logInfo(
      SCOPE,
      `preflight: eje ${regime.operationalRegime} · LONG ${regime.entriesAllowedLong ? "PERMITIDAS" : "VETADAS"} · símbolos operables ${regime.symbolsOperable ?? "n/d"} (exit ${res.code})`,
    );
  }
  // Un `exit 2` SIN payload de preflight es un fallo duro (p. ej. el interprete
  // no arranco), nunca un veto de regimen.
  if (classification.veto && !payloadOk) {
    logError(
      SCOPE,
      `preflight devolvio exit ${res.code} sin payload valido: se trata como FALLO DURO, no como veto`,
    );
    return 1;
  }
  if (classification.veto) {
    logWarn(
      SCOPE,
      "veto de regimen legitimo: se DECLARA NO_MEDIDO_REGIMEN; no se fuerza el gobernador",
    );
  } else if (classification.hard) {
    logError(SCOPE, `preflight fallo de forma dura (exit ${res.code})`);
  }
  return classification.hard ? 1 : 0;
}

async function cmdRunDay(config, flags) {
  const startedAt = new Date();
  const day = dayStamp(startedAt);
  const iso = dayIso(startedAt);

  if (flags.dryRun) {
    return dryRunDay(config, day);
  }

  // v2.88.143 — un dia SIN sesion no es un dia de ventana. La tarea corre `/sc daily`
  // tambien sabados y domingos: antes eso escribia una fila de VETO DE REGIMEN y un
  // sabado parecia «un dia intentado y vetado». Aqui se registra NON_MARKET_DAY y NO se
  // ejecuta preflight (no hay sesion que medir). `--force` NO convierte un sabado en
  // dia de mercado: la condicion es del calendario, no del operador.
  if (!isMarketDay(startedAt)) {
    return recordNonMarketDay(config, flags, { day, iso, startedAt });
  }

  // Lock diario atomico ANTES de la idempotencia y del freeze: dos `run-day`
  // simultaneos del mismo dia no pueden coexistir (un `--force` no salta el lock vivo).
  const release = acquireDayLock(day, iso, "run-day", config, flags);
  if (!release) return 1;
  try {
    return await runDayBody(config, flags, { day, iso, startedAt });
  } finally {
    release();
  }
}

/**
 * Registra un dia **sin sesion** (fin de semana) sin tocar el motor ni el preflight.
 *
 * Escribe `manifest.json` y anexa al ledger con `status: NON_MARKET_DAY`, `veto: false`
 * y `reason: non_market_day`; `regime`/`freeze` quedan en `null` porque **no se ejecuto
 * nada** (un freeze roto no puede declarar HARD_ERROR un dia en el que no hubo run).
 * Idempotente: si el dia ya esta en estado terminal y no hay `--force`, se omite.
 */
function recordNonMarketDay(config, flags, { day, iso, startedAt }) {
  const dir = join(ROOT, runDir(day));
  const manifestPath = join(dir, "manifest.json");
  if (existsSync(manifestPath) && !flags.force) {
    const previous = readJson(manifestPath);
    if (previous && isTerminalStatus(previous.status)) {
      logInfo(
        SCOPE,
        `dia ${day} ya registrado como ${previous.status} — se omite (usa --force para repetir)`,
      );
      return previous.status === "HARD_ERROR" ? 1 : 0;
    }
  }
  const manifest = {
    day,
    dayIso: iso,
    status: NON_MARKET_DAY_STATUS,
    veto: false,
    reason: "non_market_day",
    account: config.account,
    versionA: config.versionA,
    versionB: config.versionB,
    watchSize: config.watchSize,
    commit: config.commit,
    configMode: config.configMode,
    configOverrides: config.configOverrides,
    regime: null,
    freeze: null,
    startedAt: startedAt.toISOString(),
  };
  logInfo(
    SCOPE,
    `dia ${day} (${iso}) sin sesion de mercado: se registra ${NON_MARKET_DAY_STATUS} y NO se ejecuta preflight`,
  );
  finishDay(manifest, {}, {});
  return 0;
}

async function runDayBody(config, flags, { day, iso, startedAt }) {
  const steps = {};
  const artifacts = {};

  const manifest = {
    day,
    dayIso: iso,
    status: null,
    veto: false,
    reason: null,
    account: config.account,
    versionA: config.versionA,
    versionB: config.versionB,
    watchSize: config.watchSize,
    commit: config.commit,
    configMode: config.configMode,
    configOverrides: config.configOverrides,
    startedAt: startedAt.toISOString(),
  };

  const dir = join(ROOT, runDir(day));
  mkdirSync(dir, { recursive: true });

  // Idempotencia: un dia terminal no se re-ejecuta salvo `--force`.
  const manifestPath = join(dir, "manifest.json");
  if (existsSync(manifestPath) && !flags.force) {
    const previous = readJson(manifestPath);
    if (previous && isTerminalStatus(previous.status)) {
      logInfo(
        SCOPE,
        `dia ${day} ya registrado como ${previous.status} — se omite (usa --force para repetir)`,
      );
      return previous.status === "HARD_ERROR" ? 1 : 0;
    }
  }

  // Freeze: si el arbol de codigo se movio, la ventana deja de ser de un solo arbol.
  manifest.freeze = await gitFreeze(config);
  if (!manifest.freeze.ok) {
    manifest.status = "HARD_ERROR";
    manifest.reason = "TREE_MOVED";
    logError(
      SCOPE,
      `arbol de codigo movido (apps=${manifest.freeze.apps} esperado ${manifest.freeze.expectedApps}; ` +
        `packages=${manifest.freeze.packages} esperado ${manifest.freeze.expectedPackages}) — aborta fail-closed`,
    );
    finishDay(manifest, steps, artifacts);
    return 1;
  }

  // Precondiciones duras: no son veto de mercado.
  const pg = await pgPing();
  if (!pg.ok) {
    manifest.status = "HARD_ERROR";
    manifest.reason = "POSTGRES_DOWN";
    logError(
      SCOPE,
      `PostgreSQL no responde (${pg.message}) — aborta; NO es veto`,
    );
    finishDay(manifest, steps, artifacts);
    return 1;
  }
  // 1) Preflight
  const pre = await runPython(SCRIPT_FORWARD, preflightArgs(config), {
    env: childEnv(config),
    logBase: join(dir, "preflight"),
  });
  steps.preflight = { exit: pre.code, ...classifyPreflight(pre.code) };
  const prePayload = parseJsonLoose(pre.out);
  const payloadOk = isPreflightPayload(prePayload);
  if (payloadOk) {
    writeFileSync(
      join(dir, "preflight.json"),
      `${JSON.stringify(prePayload, null, 2)}\n`,
      "utf8",
    );
    artifacts.preflight = "preflight.json";
  }
  // Un `exit 2` SIN payload de preflight es un fallo duro (interprete que no
  // arranca), NO un veto de regimen: no se declara NO_MEDIDO por un fallo.
  if (steps.preflight.veto && !payloadOk) {
    steps.preflight = {
      ...steps.preflight,
      veto: false,
      hard: true,
      kind: "error",
      reason: "preflight_sin_payload",
    };
    logError(
      SCOPE,
      `preflight exit ${pre.code} sin payload valido: FALLO DURO, no veto`,
    );
  }
  manifest.regime = payloadOk ? parsePreflight(prePayload) : null;
  if (manifest.regime) {
    logInfo(
      SCOPE,
      `preflight: eje ${manifest.regime.operationalRegime} · LONG ` +
        `${manifest.regime.entriesAllowedLong ? "PERMITIDAS" : "VETADAS"} · ` +
        `símbolos operables ${manifest.regime.symbolsOperable ?? "n/d"} (exit ${pre.code})`,
    );
  }
  if (steps.preflight.hard) {
    manifest.status = "HARD_ERROR";
    manifest.reason = "PREFLIGHT_ERROR";
    finishDay(manifest, steps, artifacts);
    return 1;
  }
  if (steps.preflight.veto) {
    manifest.status = "NO_MEDIDO_REGIMEN";
    manifest.veto = true;
    manifest.reason = "regime_invalid";
    logWarn(SCOPE, "veto de regimen: dia NO computable; no se lanza forward");
    finishDay(manifest, steps, artifacts);
    return 0;
  }

  // La API solo se exige para el FORWARD (su scheduler mantiene las barras
  // frescas); un dia con veto se registra sin depender de ella.
  if (!flags.skipApiCheck) {
    const api = await apiReady();
    manifest.api = { ok: api.ok, url: api.url, status: api.status };
    if (!api.ok) {
      manifest.status = "HARD_ERROR";
      manifest.reason = "API_NOT_READY";
      logError(
        SCOPE,
        `API no lista en ${api.url} (${api.error ?? `HTTP ${api.status}`}) — aborta; ` +
          "el scheduler de barras vive en el API (usa --skip-api-check para omitir la comprobacion)",
      );
      finishDay(manifest, steps, artifacts);
      return 1;
    }
  }

  // 2) Forward del dia (reloj REAL; los cubos salen de created_at = now).
  const fwd = await runPython(SCRIPT_FORWARD, forwardArgs(config, day), {
    env: childEnv(config),
    logBase: join(dir, "forward"),
  });
  steps.forward = { exit: fwd.code, ...classifyExit(fwd.code) };
  const canonicalForward = join(ROOT, forwardPath(day));
  if (existsSync(canonicalForward)) {
    copyFileSync(canonicalForward, join(dir, "forward.json"));
    artifacts.forward = "forward.json";
  }
  if (steps.forward.hard) {
    manifest.status = "HARD_ERROR";
    manifest.reason = "FORWARD_ERROR";
    logError(SCOPE, `forward fallo de forma dura (exit ${fwd.code})`);
    finishDay(manifest, steps, artifacts);
    return 1;
  }

  // 3) Journal de operabilidad (v2_77)
  if (existsSync(canonicalForward)) {
    const journal = await runPython(
      SCRIPT_JOURNAL,
      ["--forward", forwardPath(day), "--render"],
      { env: childEnv(config), logBase: join(dir, "journal") },
    );
    steps.journal = { exit: journal.code, ...classifyExit(journal.code) };
  } else {
    steps.journal = { exit: null, kind: "skipped", reason: "sin forward json" };
  }

  // 4) Ventana (v2_80): lee el journal DURABLE y enriquece con el forward.
  const win = await runPython(
    SCRIPT_WINDOW,
    [
      "--account-id",
      config.account,
      "--strategy-version",
      config.versionA,
      "--days",
      String(config.days),
      "--forward",
      FORWARD_GLOB,
      "--json",
      "--out",
      WINDOW_JSON,
      "--html",
      WINDOW_HTML,
    ],
    { env: childEnv(config), logBase: join(dir, "window") },
  );
  steps.window = { exit: win.code, ...classifyExit(win.code) };
  const windowJsonPath = join(ROOT, WINDOW_JSON);
  if (existsSync(windowJsonPath)) {
    copyFileSync(windowJsonPath, join(dir, "window.json"));
    artifacts.window = "window.json";
    if (existsSync(join(ROOT, WINDOW_HTML))) {
      copyFileSync(join(ROOT, WINDOW_HTML), join(dir, "window.html"));
      artifacts.windowHtml = "window.html";
    }
    manifest.gate = parseGate(
      parseJsonLoose(win.out) ?? readJson(windowJsonPath),
    );
  }
  if (steps.window.hard) {
    manifest.status = "HARD_ERROR";
    manifest.reason = "WINDOW_ERROR";
    finishDay(manifest, steps, artifacts);
    return 1;
  }

  // 5) Auditoria read-only (v2_83), solo si hay ventana que auditar.
  if (existsSync(windowJsonPath)) {
    const audit = await runPython(
      SCRIPT_AUDIT,
      [
        "--window",
        WINDOW_JSON,
        "--forward",
        FORWARD_GLOB,
        "--json",
        "--out",
        AUDIT_JSON,
      ],
      { env: childEnv(config), logBase: join(dir, "audit") },
    );
    steps.audit = { exit: audit.code, ...classifyExit(audit.code) };
    if (existsSync(join(ROOT, AUDIT_JSON))) {
      copyFileSync(join(ROOT, AUDIT_JSON), join(dir, "audit.json"));
      artifacts.audit = "audit.json";
    }
  } else {
    steps.audit = { exit: null, kind: "skipped", reason: "sin ventana json" };
  }

  const hard = Object.values(steps).some((step) => step.hard);
  manifest.status = resolveDayStatus({
    preflight: steps.preflight,
    window: steps.window,
    hard,
  });
  manifest.veto = Boolean(steps.preflight.veto);
  if (manifest.status === "NO_MEDIDO_REGIMEN")
    manifest.reason = "regime_invalid";

  // Provenance: liga el gate al run (dia/cuenta/version + freeze + sha256 del window.json).
  const runWindowPath = join(dir, "window.json");
  if (existsSync(runWindowPath)) {
    const windowPayload = parseJsonLoose(win.out) ?? readJson(windowJsonPath);
    manifest.windowProvenance = {
      windowRunId: `${day}-${manifest.startedAt}`,
      commit: manifest.commit,
      appsHash: manifest.freeze?.apps ?? null,
      packagesHash: manifest.freeze?.packages ?? null,
      account: manifest.account,
      versionA: manifest.versionA,
      versionB: manifest.versionB,
      watchSize: manifest.watchSize,
      capturedAt: windowPayload?.meta?.header?.capturedAt ?? null,
      windowJsonSha256: sha256File(runWindowPath),
      gate: manifest.gate ?? null,
    };
  }

  finishDay(manifest, steps, artifacts);
  return manifest.status === "HARD_ERROR" ? 1 : 0;
}

async function dryRunDay(config, day) {
  logInfo(
    SCOPE,
    `--dry-run · dia ${day} · cuenta ${config.account} · versionA ${config.versionA} · watch ${config.watchSize} · config ${config.configMode}`,
  );
  // v2.88.143: en un dia sin sesion el plan NO es la cadena de preflight: se registraria
  // NON_MARKET_DAY y no se abriria el motor. Decirlo es mas honesto que listar pasos.
  if (!isMarketDay(new Date())) {
    logWarn(
      SCOPE,
      `--dry-run · fin de semana: el run-day real solo registraria ${NON_MARKET_DAY_STATUS} (sin preflight, sin motor)`,
    );
    return 0;
  }
  if (config.configMode === "UNSAFE") {
    logWarn(
      SCOPE,
      `CONFIG_OVERRIDE = UNSAFE · overrides ${config.configOverrides.join(", ") || "ninguno"}`,
    );
  }
  const freeze = await gitFreeze(config);
  if (freeze.ok) {
    logInfo(
      SCOPE,
      `freeze OK · apps ${freeze.apps} · packages ${freeze.packages}`,
    );
  } else {
    logError(
      SCOPE,
      `freeze NO OK · apps ${freeze.apps} (esperado ${freeze.expectedApps}) · ` +
        `packages ${freeze.packages} (esperado ${freeze.expectedPackages})`,
    );
  }
  const scripts = [SCRIPT_FORWARD, SCRIPT_JOURNAL, SCRIPT_WINDOW, SCRIPT_AUDIT];
  const missing = scripts.filter((script) => !existsSync(join(ROOT, script)));
  if (missing.length > 0) {
    logError(SCOPE, `faltan scripts del pipeline: ${missing.join(", ")}`);
    return 1;
  }
  const launcher = await resolveLauncher();
  const py = launcher.label;
  console.log("Cadena que se ejecutaria:");
  console.log(
    `  1. ${py} ${SCRIPT_FORWARD} ${preflightArgs(config).join(" ")}`,
  );
  console.log(
    `  2. ${py} ${SCRIPT_FORWARD} ${forwardArgs(config, day).join(" ")}`,
  );
  console.log(
    `  3. ${py} ${SCRIPT_JOURNAL} --forward ${forwardPath(day)} --render`,
  );
  console.log(
    `  4. ${py} ${SCRIPT_WINDOW} --account-id ${config.account} --strategy-version ${config.versionA} --days ${config.days} --forward ${FORWARD_GLOB} --json --out ${WINDOW_JSON} --html ${WINDOW_HTML}`,
  );
  console.log(
    `  5. ${py} ${SCRIPT_AUDIT} --window ${WINDOW_JSON} --forward ${FORWARD_GLOB} --json --out ${AUDIT_JSON}`,
  );
  console.log(`Artefactos: ${runDir(day)}/`);
  console.log(
    `Flags de operacion (solo en el hijo): ${JSON.stringify(config.operatorEnv)}`,
  );
  return freeze.ok ? 0 : 1;
}

/**
 * Deriva el gate SOLO de un run ligado al ledger y al arbol congelado: recorre
 * los dias MEDIDOS (del mas nuevo al mas viejo), lee el `manifest.json` y el
 * `window.json` del run, y exige que `verifyWindowProvenance` cuadre. Nunca se
 * pinta el `operability_runs/operability-window.json` canonico a pelo (podria
 * ser material stale de otra ejecucion).
 */
function resolveVerifiedGate(days) {
  let lastProblems = null;
  let sawMeasured = false;
  for (const row of [...days].reverse()) {
    if (row.status !== "MEDIDO") continue;
    sawMeasured = true;
    const runWindowPath = join(ROOT, runDir(row.day), "window.json");
    const manifest = readJson(join(ROOT, runDir(row.day), "manifest.json"));
    const windowPayload = existsSync(runWindowPath)
      ? readJson(runWindowPath)
      : null;
    const windowGate = parseGate(windowPayload);
    const windowJsonSha256 = existsSync(runWindowPath)
      ? sha256File(runWindowPath)
      : null;
    const verdict = verifyWindowProvenance({
      ledgerRow: row,
      manifest,
      windowGate,
      windowJsonSha256,
      windowHeader: windowPayload?.meta?.header ?? null,
    });
    if (verdict.ok)
      return { gate: windowGate, day: row.day, problems: [], sawMeasured };
    if (!lastProblems)
      lastProblems = { day: row.day, problems: verdict.problems };
  }
  return {
    gate: null,
    day: null,
    problems: lastProblems?.problems ?? [],
    sawMeasured,
  };
}

function cmdStatus() {
  const rows = readLedger();
  const summary = summarizeLedger(rows, null);
  const verified = resolveVerifiedGate(summary.days);
  const gate = verified.gate;
  logInfo(
    SCOPE,
    `estado de la ventana · ${WINDOW_MIN_DAYS} dias / ${WINDOW_MIN_EPISODES} episodios / ${WINDOW_MIN_CYCLES} ciclos`,
  );
  const locks = activeLockDays();
  for (const lock of locks) {
    logWarn(
      SCOPE,
      `RUN EN CURSO: dia ${lock.day} (pid ${lock.pid} · ${lock.startedAt}) — no lances otro run-day`,
    );
  }
  if (summary.rows === 0) {
    logWarn(
      SCOPE,
      "ledger vacio: aun no hay ningun dia registrado (NO MEDIDO, nunca 0)",
    );
  } else {
    for (const row of summary.days) {
      const regime = row.regime?.operationalRegime ?? "n/d";
      console.log(
        `  ${row.day}  ${String(row.status).padEnd(18)} regimen=${regime}`,
      );
    }
  }
  console.log(
    `  resumen: dias_de_ventana=${summary.total} medidos=${summary.measured} veto=${summary.vetoed} declarados=${summary.declared} duros=${summary.hardErrors} no_mercado=${summary.nonMarket}`,
  );
  if (gate) {
    console.log(
      `  gate ${gate.verdict} (run ${verified.day}): dias ${gate.days}/${gate.minDays} · ` +
        `episodios ${gate.episodes}/${gate.minEpisodes} · ciclos ${gate.cycles}/${gate.minCycles}`,
    );
  } else if (verified.sawMeasured) {
    console.log(
      `  gate: STALE (ningun run MEDIDO con provenance valida${verified.problems.length ? `: ${verified.problems.join(", ")}` : ""})`,
    );
  } else {
    console.log("  gate: NO_MEDIDO (sin dias medidos)");
  }
  console.log(`  ledger: ${LEDGER_PATH}`);
  return 0;
}

/**
 * `evidence` — bundle diario P1-P4 (read-only) sobre la config pinneada.
 *
 * Encadena el certificador de la ventana (`v2_98`) y la cadena durable del ESTUDIO
 * (`v2_99`) en un paquete por dia, ligado a la MISMA cuenta/versiones del pin. NO
 * sustituye la operacion real: solo ORDENA y PERSISTE la evidencia medida.
 */
function evidenceArgs(config) {
  const args = [
    "--account-id",
    config.account,
    "--strategy-version",
    config.versionA,
    "--strategy-version",
    config.versionB,
    "--engine-id",
    "auto-sim",
  ];
  return args;
}

async function cmdEvidence(config, flags) {
  const launcher = await resolveLauncher();
  if (flags.dryRun) {
    logInfo(
      SCOPE,
      `--dry-run · evidence: ${launcher.label} ${SCRIPT_EVIDENCE} ${evidenceArgs(config).join(" ")}`,
    );
    return 0;
  }
  const res = await runPython(SCRIPT_EVIDENCE, evidenceArgs(config), {
    env: childEnv(config),
  });
  if (res.code !== 0) {
    logError(
      SCOPE,
      `evidencia: v2_100 salio con codigo ${res.code} (material no leido)`,
    );
  } else {
    logInfo(
      SCOPE,
      "evidencia: bundle P1-P4 escrito en operability_runs/daily-evidence/<DIA>/",
    );
  }
  return res.code ?? 1;
}

/**
 * `unlock` (escape hatch administrativo) reclama el lock del dia SOLO si esta
 * huerfano: aplica exactamente la misma logica de ownership que `run-day`
 * (`unlockDecision`). Nunca borra el lock de un proceso vivo: para un PID vivo
 * del mismo host ni `--force` lo salta (mata el proceso y el PID pasa a muerto
 * => se reclama solo). Un lock de otro host con TTL fresco o un lock ilegible
 * exigen `--force`, que reclamara incluso un lock vivo de otro host.
 */
function cmdUnlock(flags) {
  const day = flags.at || dayStamp(new Date());
  const lockPath = join(ROOT, runLockDir(day));
  const lockExists = existsSync(lockPath);
  const existing = lockExists ? readLock(day) : null;
  const decision = unlockDecision({
    lockExists,
    lock: existing,
    host: hostname(),
    isProcessAlive: pidAlive,
    force: flags.force,
  });
  if (decision.action === "nothing") {
    logInfo(SCOPE, `no hay lock para el dia ${day}`);
    return 0;
  }
  if (decision.action === "deny") {
    const owner =
      existing && typeof existing === "object"
        ? `(pid ${existing.pid ?? "n/d"} · host ${existing.host ?? "n/d"} · ${existing.startedAt ?? "n/d"})`
        : "(lock ilegible: sin lock.json)";
    logError(
      SCOPE,
      `unlock DENEGADO (${decision.reason}): el lock del dia ${day} ${owner} no es reclamable por defecto` +
        (decision.reason === "pid_vivo"
          ? "; hay un run en curso: no lances otro run-day"
          : "; si estas seguro de que es un resto administrativo, usa --force"),
    );
    return 1;
  }
  if (flags.dryRun) {
    console.log(`rm -rf ${lockPath} (${decision.reason})`);
    return 0;
  }
  rmSync(lockPath, { recursive: true, force: true });
  logInfo(SCOPE, `lock del dia ${day} eliminado (${decision.reason})`);
  return 0;
}

// ---------------------------------------------------------------------------
// Vigia diario (v2.88.142) — vigilancia verificable e independiente del stack
// ---------------------------------------------------------------------------

const WATCH_STATUS_PATH = "operability_runs/window-runs/day-watch.json";

/**
 * `watch`: evalua el dia de hoy + el arrastre de dias perdidos y AVISA (log + email).
 *
 * Read-only sobre la ventana (solo lee el ledger y el lock) y escribe su **latido** en
 * `day-watch.json`, que es el instrumento que permite comprobar desde fuera que el vigia
 * corrio. Corre SIN el stack dev: por eso tiene su propia tarea programada (`20:20`).
 *
 * Exit: `0` sin aviso · `3` con dia perdido/HARD_ERROR (queda en `LastTaskResult`) · `1` error.
 */
async function cmdWatch(flags) {
  const args = ["--once"];
  if (flags.lookbackDays) args.push("--lookback-days", String(flags.lookbackDays));
  if (flags.json) args.push("--json");
  if (flags.noPersist) args.push("--no-persist");

  logInfo(SCOPE, "vigia diario: evaluando el ledger de la ventana (read-only)...");
  const result = await runPythonModule(WATCH_MODULE, args);
  if (result.spawnError) {
    logError(
      SCOPE,
      `no se pudo lanzar el vigia: ${result.spawnError.message ?? String(result.spawnError)}`,
    );
    return 1;
  }
  if (result.code === WATCH_ALERT_EXIT) {
    logWarn(
      SCOPE,
      `vigia: HAY aviso${flags.noPersist ? " (sin latido: --no-persist)" : ` (latido en ${WATCH_STATUS_PATH})`}; revisa el log/email y, si procede, ` +
        "`pnpm window:status` + `pnpm window:run-day`",
    );
    return WATCH_ALERT_EXIT;
  }
  if (result.code !== 0) {
    logError(SCOPE, `el vigia termino con codigo ${result.code ?? "n/d"}`);
    return result.code ?? 1;
  }
  logInfo(
    SCOPE,
    flags.noPersist
      ? "vigia: sin aviso (sin latido: --no-persist)"
      : `vigia: sin aviso (latido en ${WATCH_STATUS_PATH})`,
  );
  return 0;
}

// ---------------------------------------------------------------------------
// Tareas programadas (Windows)
// ---------------------------------------------------------------------------

/** Ruta del wrapper `.cmd` que ejecuta la tarea programada (generado, no versionado). */
function taskWrapperPath() {
  return join(ROOT, RUNS_DIR, "window-forward-task.cmd");
}

/** Ruta del wrapper `.cmd` del vigía diario (generado, no versionado). */
function watchWrapperPath() {
  return join(ROOT, RUNS_DIR, "window-watch-task.cmd");
}

/**
 * Escribe (o reescribe) el wrapper `.cmd` que la tarea de Windows ejecuta.
 *
 * Motivo (fix 2.11.140): registrar `schtasks /tr "cmd /c \"cd ... && ...\""` con comillas
 * ANIDADAS rompe el parseo de `schtasks` en Windows («Falta la opcion obligatoria "sc"»):
 * las comillas internas se consumen y `/sc` deja de ser un flag. Un wrapper con una ruta
 * SIN comillas anidadas elimina el problema: `/tr "<ruta-wrapper.cmd>"` es un unico token.
 *
 * Motivo (fix 2.11.142): el wrapper llamaba a `<root>\node_modules\.bin\pnpm.cmd`, que en
 * este repo **no existe** (pnpm es una instalacion GLOBAL, no una dependencia del arbol) y
 * que ademas no esta en el PATH con el que arranca el Programador de tareas. Medido: el
 * wrapper fallaba con «no se reconoce como un comando interno o externo» => las DOS tareas
 * quedaban registradas y **no ejecutaban nada**. Ahora se invoca **node por ruta absoluta**
 * (`process.execPath`, el mismo interprete con el que se instala) sobre el runner: cero
 * dependencia de pnpm/PATH. `exit /b %ERRORLEVEL%` propaga el codigo (3 = hubo aviso).
 */
function writeCmdWrapper(wrapper, runnerCommand) {
  const content = cmdWrapperContent({
    root: ROOT,
    node: process.execPath,
    runner: join(ROOT, "scripts", "window-forward-runner.mjs"),
    command: runnerCommand,
  });
  mkdirSync(dirname(wrapper), { recursive: true });
  writeFileSync(wrapper, content, "utf8");
  return wrapper;
}

function writeTaskWrapper() {
  return writeCmdWrapper(taskWrapperPath(), "run-day");
}

/** v2.88.142: wrapper de la tarea del vigía (independiente del stack dev). */
function writeWatchWrapper() {
  return writeCmdWrapper(watchWrapperPath(), "watch");
}

/**
 * v2.88.142 — verificacion END-TO-END del wrapper ANTES de registrar la tarea.
 *
 * El `.140` registraba la tarea y daba por buena la cadencia mirando solo
 * `schtasks /query` (Estado: Listo): «Listo» dice que el Programador la acepto, NO que
 * el comando exista. Aqui se escribe un wrapper **temporal** con la MISMA forma
 * (`node` absoluto + runner + `status`, que es read-only y barato), se ejecuta con
 * `cmd /c` y se exige exit 0; si falla, NO se registra ninguna tarea (fail-closed).
 */
function verifyWrapperShape() {
  const probe = join(ROOT, RUNS_DIR, "window-task-probe.cmd");
  writeCmdWrapper(probe, "status");
  try {
    const res = spawnSync("cmd", ["/c", probe], {
      cwd: ROOT,
      encoding: "utf8",
      timeout: 120_000,
    });
    if (res.error) {
      logError(SCOPE, `no se pudo ejecutar el wrapper de prueba: ${res.error.message}`);
      return false;
    }
    if (res.status !== 0) {
      const detail = (res.stderr || res.stdout || "")
        .trim()
        .split(/\r?\n/)
        .slice(-4)
        .join(" | ");
      logError(
        SCOPE,
        `el wrapper de la tarea NO se ejecuta (exit ${res.status})${detail ? `: ${detail}` : ""}`,
      );
      return false;
    }
    logInfo(SCOPE, "wrapper verificado end-to-end (node absoluto + runner, exit 0)");
    return true;
  } finally {
    try {
      rmSync(probe, { force: true });
    } catch {
      /* la sonda es efimera: si no se puede borrar, no invalida la verificacion */
    }
  }
}

/**
 * `2.11.144` — registro por **XML** (no `/tr`): `schtasks /create` no expone
 * `StartWhenAvailable`; solo el XML lo lleva. Ver `taskXml` en el lib para las
 * decisiones declaradas (bateria y `WakeToRun` NO se tocan).
 */
function schtasksCreateCommand(name, xmlPath) {
  return `schtasks /create /tn "${name}" /xml "${xmlPath}" /f`;
}

/**
 * `2.11.144` — verifica DESPUES de registrar que la tarea quedo **de verdad** con
 * `StartWhenAvailable = true`, leyendo el XML que devuelve el Programador.
 *
 * Mismo criterio que la sonda del wrapper en el `.142`: no basta con que `schtasks`
 * diga «Listo»; hay que leer lo registrado. Si no casa, se **desregistra** la tarea
 * (fail-closed: mejor ninguna tarea que una que se declara y no lo es).
 */
function verifyTaskXml(name) {
  const result = spawnSync(`schtasks /query /tn "${name}" /xml ONE`, [], {
    shell: true,
    encoding: "utf8",
  });
  const xml = String(result.stdout ?? "");
  if (result.status === 0 && xml.includes(START_WHEN_AVAILABLE_MARKER)) {
    logInfo(
      SCOPE,
      `tarea "${name}" verificada: StartWhenAvailable = true (leido del registro)`,
    );
    return true;
  }
  logError(
    SCOPE,
    `la tarea "${name}" NO quedo con StartWhenAvailable = true — se desregistra (fail-closed)`,
  );
  spawnSync(`schtasks /delete /tn "${name}" /f`, [], { shell: true, encoding: "utf8" });
  return false;
}

/** Registra una tarea diaria y devuelve `true` si `schtasks` salio bien Y se verifico. */
function registerTask(name, time, wrapper) {
  const xmlPath = wrapper.replace(/\.cmd$/i, ".xml");
  let xml;
  try {
    xml = taskXml({
      name,
      time,
      wrapper,
      description:
        "Bolsa V1 · cadencia de la ventana PAPER (freeze + preflight + run-day). " +
        "StartWhenAvailable=true: si el equipo estaba dormido, la corrida se recupera al despertar.",
    });
  } catch (error) {
    logError(
      SCOPE,
      `no se pudo construir el XML de la tarea "${name}": ${error.message}`,
    );
    return false;
  }
  // El Programador exige XML en UTF-16 con BOM; se conserva en el directorio de
  // corridas para que el registro sea AUDITABLE (no un flag opaco en el registro).
  writeFileSync(xmlPath, `\ufeff${xml}`, "utf16le");
  logInfo(SCOPE, `XML de la tarea "${name}" escrito en ${xmlPath}`);
  const command = schtasksCreateCommand(name, xmlPath);
  logInfo(SCOPE, `registrando tarea diaria "${name}" a las ${time}...`);
  const result = spawnSync(command, [], {
    shell: true,
    encoding: "utf8",
    stdio: "inherit",
  });
  if (result.status !== 0) {
    logError(
      SCOPE,
      "schtasks devolvio error; revisa permisos (terminal como administrador).",
    );
    return false;
  }
  if (!verifyTaskXml(name)) return false;
  logInfo(SCOPE, `tarea "${name}" registrada.`);
  logInfo(
    SCOPE,
    `consulta/elimina: schtasks /query /tn "${name}" · schtasks /delete /tn "${name}" /f`,
  );
  return true;
}

function cmdTaskInstall(flags) {
  if (process.platform !== "win32") {
    logInfo(
      SCOPE,
      "task:install solo aplica a Windows (schtasks). En otro SO usa cron/systemd-timer.",
    );
    return 0;
  }
  const time = flags.at || DEFAULT_TASK_TIME;
  const watchTime = flags.watchAt || DEFAULT_WATCH_TIME;
  const installWatch = !flags.noWatch;
  if (flags.dryRun) {
    const plans = [[TASK_NAME, time, taskWrapperPath()]];
    if (installWatch) plans.push([WATCH_TASK_NAME, watchTime, watchWrapperPath()]);
    for (const [name, at, wrapper] of plans) {
      const xmlPath = wrapper.replace(/\.cmd$/i, ".xml");
      logInfo(
        SCOPE,
        `--dry-run · ${name} ${at} · schtasks /create /tn "${name}" /xml "${xmlPath}" /f`,
      );
      logInfo(
        SCOPE,
        `--dry-run · ${name} · StartWhenAvailable=true · DisallowStartIfOnBatteries=true · WakeToRun=false`,
      );
    }
    return 0;
  }
  const wrapper = writeTaskWrapper();
  logInfo(SCOPE, `wrapper de la tarea escrito en ${wrapper}`);
  // v2.88.142 — fail-closed: si el wrapper NO se ejecuta, no se registra nada.
  if (!verifyWrapperShape()) return 1;
  if (!registerTask(TASK_NAME, time, wrapper)) return 1;
  if (!installWatch) return 0;

  // v2.88.142: el vigía tiene su PROPIA tarea diaria (20:20), de modo que avisa aunque el
  // equipo/stack no esté levantado a la hora del run-day.
  const watchWrapper = writeWatchWrapper();
  logInfo(SCOPE, `wrapper del vigia escrito en ${watchWrapper}`);
  return registerTask(WATCH_TASK_NAME, watchTime, watchWrapper) ? 0 : 1;
}

function cmdTaskRemove(flags) {
  if (process.platform !== "win32") {
    logInfo(SCOPE, "task:remove solo aplica a Windows (schtasks).");
    return 0;
  }
  let ok = true;
  for (const name of [TASK_NAME, WATCH_TASK_NAME]) {
    const command = `schtasks /delete /tn "${name}" /f`;
    if (flags.dryRun) {
      console.log(command);
      continue;
    }
    const result = spawnSync(command, [], {
      shell: true,
      encoding: "utf8",
      stdio: "inherit",
    });
    if (result.status !== 0) {
      logError(SCOPE, `no se pudo eliminar la tarea "${name}".`);
      ok = false;
      continue;
    }
    logInfo(SCOPE, `tarea "${name}" eliminada.`);
  }
  return ok ? 0 : 1;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  loadEnvFile();
  const { command, flags, unknown } = parseArgs(process.argv.slice(2));
  const unsafeOverride =
    flags.unsafeOverride || process.env.WINDOW_UNSAFE_CONFIG_OVERRIDE === "1";
  const config = windowConfig(process.env, { unsafeOverride });

  if (flags.help || command === "help") {
    printHelp();
    return 0;
  }
  if (unknown.length > 0) {
    logWarn(SCOPE, `flags desconocidos ignorados: ${unknown.join(", ")}`);
  }
  if (config.configMode === "UNSAFE") {
    logWarn(
      SCOPE,
      `CONFIG_OVERRIDE = UNSAFE: la config certificada NO aplica ` +
        `(overrides: ${config.configOverrides.join(", ") || "ninguno"}); el gate de estos dias no es valido`,
    );
  }

  switch (command) {
    case "preflight":
      return cmdPreflight(config, flags);
    case "run-day":
      return cmdRunDay(config, flags);
    case "status":
      return cmdStatus();
    case "evidence":
      return cmdEvidence(config, flags);
    case "unlock":
      return cmdUnlock(flags);
    case "watch":
      return cmdWatch(flags);
    case "task:install":
      return cmdTaskInstall(flags);
    case "task:remove":
      return cmdTaskRemove(flags);
    default:
      logError(SCOPE, `comando desconocido: ${command}`);
      printHelp();
      return 1;
  }
}

main()
  .then((code) => {
    process.exit(code ?? 0);
  })
  .catch((error) => {
    logError(
      SCOPE,
      error instanceof Error ? (error.stack ?? error.message) : String(error),
    );
    process.exit(1);
  });
