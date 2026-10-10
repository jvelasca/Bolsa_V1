/**
 * Integrated E2E — durable AUTO cycle seed (subprocess wrapper).
 *
 * El journey integrado (`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`) necesita ≥1
 * ciclo AUTO **durable** en la cuenta efímera para dejar de declararse `skipped` por
 * `NO_CYCLE_REASON`. El motor AUTO (worker de simulación) **no** corre en el harness, así
 * que el propio harness siembra el ciclo **reutilizando** el CLI dev existente
 * `scripts/dev/seed_auto_cycle_for_ui.py` (NO reimplementa lógica de backend): lo lanza como
 * subproceso (`uv run --no-sync python …`) con la cuenta efímera y un símbolo real del
 * catálogo. La limpieza simétrica usa `--cleanup`.
 *
 * Opt-in: solo corre con `E2E_INTEGRATION=1` + `E2E_ALLOW_DEV_DB=1` (el MISMO gate que el
 * spec integrado). Fail-closed: si `uv`/python (o la raíz del repo) no están disponibles,
 * DEVUELVE un motivo explícito; NO lanza ni finge un fallo de producto — el spec lo DECLARA
 * como `skipped` con motivo.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

/** Ruta del CLI dev, relativa a la raíz del repo (una sola fuente de verdad). */
const SEED_SCRIPT_REL = path.join(
  "scripts",
  "dev",
  "seed_auto_cycle_for_ui.py",
);
/** Marca de la raíz del monorepo (para resolver el cwd del subproceso). */
const WORKSPACE_MARKER = "pnpm-workspace.yaml";
const DEFAULT_TIMEOUT_MS = 180_000;
const CLEANUP_TIMEOUT_MS = 120_000;

/** El seed no está habilitado: falta el opt-in integrado. */
export const AUTO_CYCLE_SEED_DISABLED_REASON =
  "El seed del ciclo AUTO requiere el opt-in integrado (E2E_INTEGRATION=1 + E2E_ALLOW_DEV_DB=1).";

/** Prefijo de los motivos en los que el subproceso del seed no pudo correr. */
export const AUTO_CYCLE_SEED_UNAVAILABLE_PREFIX =
  "No se pudo ejecutar el seed del ciclo AUTO";

export type AutoCycleSeedOutcome =
  | { ok: true; stdout: string }
  | { ok: false; reason: string };

/** `true` con el MISMO opt-in que `gateIntegratedE2eEnvironment` exige para tocar la BD dev. */
export function autoCycleSeedEnabled(): boolean {
  return (
    process.env.E2E_INTEGRATION === "1" && process.env.E2E_ALLOW_DEV_DB === "1"
  );
}

/**
 * Resuelve la raíz del monorepo desde el cwd de Playwright (p. ej. `apps/web`) buscando hacia
 * arriba el workspace marker + el CLI del seed. `E2E_REPO_ROOT` la fija explícitamente.
 */
function findRepoRoot(): string | null {
  const override = process.env.E2E_REPO_ROOT?.trim();
  const starts = override ? [override, process.cwd()] : [process.cwd()];
  for (const start of starts) {
    let dir = path.resolve(start);
    for (let i = 0; i < 10; i += 1) {
      if (
        existsSync(path.join(dir, WORKSPACE_MARKER)) &&
        existsSync(path.join(dir, SEED_SCRIPT_REL))
      ) {
        return dir;
      }
      const parent = path.dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }
  }
  return null;
}

function tail(text: string, max = 1200): string {
  const trimmed = text.trim();
  return trimmed.length <= max ? trimmed : `…${trimmed.slice(-max)}`;
}

/** Lanza `uv run --no-sync python <seed> …args` y normaliza el resultado (nunca lanza). */
function runSeedCli(
  args: string[],
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<AutoCycleSeedOutcome> {
  return new Promise((resolve) => {
    const root = findRepoRoot();
    if (!root) {
      resolve({
        ok: false,
        reason:
          `${AUTO_CYCLE_SEED_UNAVAILABLE_PREFIX}: no localicé la raíz del repo ` +
          `(${WORKSPACE_MARKER} + ${SEED_SCRIPT_REL}). Define E2E_REPO_ROOT o ejecuta ` +
          `Playwright desde el monorepo.`,
      });
      return;
    }
    const script = path.join(root, SEED_SCRIPT_REL);
    const child = spawn("uv", ["run", "--no-sync", "python", script, ...args], {
      cwd: root,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    let settled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const finish = (outcome: AutoCycleSeedOutcome) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      resolve(outcome);
    };

    timer = setTimeout(() => {
      try {
        child.kill("SIGKILL");
      } catch {
        // best-effort: el timeout reporta igualmente.
      }
      finish({
        ok: false,
        reason:
          `${AUTO_CYCLE_SEED_UNAVAILABLE_PREFIX}: timeout tras ${timeoutMs} ms.\n` +
          tail(stderr || stdout),
      });
    }, timeoutMs);

    child.stdout?.on("data", (chunk) => {
      stdout += String(chunk);
    });
    child.stderr?.on("data", (chunk) => {
      stderr += String(chunk);
    });
    child.on("error", (err) => {
      finish({
        ok: false,
        reason:
          `${AUTO_CYCLE_SEED_UNAVAILABLE_PREFIX} (uv/python no disponibles): ` +
          err.message,
      });
    });
    child.on("close", (code) => {
      if (code === 0) {
        finish({ ok: true, stdout });
        return;
      }
      finish({
        ok: false,
        reason:
          `${AUTO_CYCLE_SEED_UNAVAILABLE_PREFIX}: exit ${code}.\n` +
          tail(stderr || stdout),
      });
    });
  });
}

/** Siembra UN ciclo AUTO durable para `(accountId, symbol)` reutilizando el CLI dev. */
export async function seedAutoCycleForAccount(opts: {
  accountId: string;
  symbol: string;
  apiBase: string;
}): Promise<AutoCycleSeedOutcome> {
  if (!autoCycleSeedEnabled()) {
    return { ok: false, reason: AUTO_CYCLE_SEED_DISABLED_REASON };
  }
  return runSeedCli([
    "--account-id",
    opts.accountId,
    "--symbol",
    opts.symbol,
    "--api-base",
    opts.apiBase,
  ]);
}

/**
 * Limpia los ciclos `cyc-ui-*` sembrados de la cuenta (filas durables + `DELETE` del TOP).
 * Simétrico del seed; el `afterAll` lo usa para no dejar residuo en la BD dev.
 */
export async function cleanupAutoCycleForAccount(opts: {
  accountId: string;
  apiBase: string;
}): Promise<AutoCycleSeedOutcome> {
  if (!autoCycleSeedEnabled()) {
    return { ok: false, reason: AUTO_CYCLE_SEED_DISABLED_REASON };
  }
  return runSeedCli(
    ["--cleanup", "--account-id", opts.accountId, "--api-base", opts.apiBase],
    CLEANUP_TIMEOUT_MS,
  );
}
