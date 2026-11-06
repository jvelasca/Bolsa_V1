/**
 * Journey LIVE de la operativa diaria AUTO — seed del mundo ESTUDIO (subproceso).
 *
 * El spec `gp-e2e-auto-daily-chain-live.spec.ts` ejercita la UI contra la API y el WORKER
 * **reales**: pulsa «Calcular operativa diaria» y espera el parte durable, y después pide el
 * DÍA-D del valor. Para que el parte PROPONGA (y no se quede en `no_plan`) el mundo debe
 * existir: instrumento con barras suficientes para SMA200, fundamentales en corte PIT,
 * estrategia ACTIVE, edge, TOP vigente y pertenencia a `estudio`.
 *
 * El mundo NO se reimplementa aquí: se lanza el CLI dev
 * `scripts/dev/seed_estudio_daily_for_ui.py`, que a su vez reutiliza el harness real de
 * siembra (`apps/api-python/tests/support/auto_chain_e2e.py`) — la misma fuente que el E2E de
 * Python. La limpieza es simétrica (`--cleanup`) y verifica sus propios ids deterministas.
 *
 * Opt-in: `E2E_INTEGRATION=1` + `E2E_ALLOW_DEV_DB=1` (el MISMO gate que el resto de journeys
 * integrados). Fail-closed: si `uv`/python o la raíz del repo no están disponibles devuelve un
 * motivo explícito en vez de lanzar; el spec lo convierte en FALLO con `E2E_LIVE_REQUIRED=1`.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

/** Ruta del CLI dev, relativa a la raíz del repo (una sola fuente de verdad). */
const SEED_SCRIPT_REL = path.join(
  "scripts",
  "dev",
  "seed_estudio_daily_for_ui.py",
);
const WORKSPACE_MARKER = "pnpm-workspace.yaml";
const DEFAULT_TIMEOUT_MS = 240_000;
const CLEANUP_TIMEOUT_MS = 180_000;

/** Identidad sembrada (la que el spec usa para localizar el valor y el día). */
export type EstudioDailySeedManifest = {
  accountId: string;
  symbol: string;
  instrumentId: string;
  asOf: string;
  bars: number;
  strategyVersionId: string;
  candidateId: string;
  previousMembership: string[];
};

export type EstudioDailySeedOutcome =
  | { ok: true; manifest: EstudioDailySeedManifest; stdout: string }
  | { ok: false; reason: string };

export const ESTUDIO_DAILY_SEED_DISABLED_REASON =
  "El seed del mundo ESTUDIO requiere el opt-in integrado (E2E_INTEGRATION=1 + E2E_ALLOW_DEV_DB=1).";

export const ESTUDIO_DAILY_SEED_UNAVAILABLE_PREFIX =
  "No se pudo ejecutar el seed del mundo ESTUDIO";

/** `true` con el MISMO opt-in que `gateIntegratedE2eEnvironment` exige para tocar la BD. */
export function estudioDailySeedEnabled(): boolean {
  return (
    process.env.E2E_INTEGRATION === "1" && process.env.E2E_ALLOW_DEV_DB === "1"
  );
}

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

function tail(text: string, max = 1600): string {
  const trimmed = text.trim();
  return trimmed.length <= max ? trimmed : `…${trimmed.slice(-max)}`;
}

/** La primera línea `MANIFEST {…}` del stdout (el resto es log humano). */
export function parseManifest(stdout: string): EstudioDailySeedManifest | null {
  for (const line of stdout.split(/\r?\n/)) {
    const text = line.trim();
    if (!text.startsWith("MANIFEST ")) continue;
    try {
      const parsed = JSON.parse(text.slice("MANIFEST ".length)) as Record<
        string,
        unknown
      >;
      const symbol = String(parsed.symbol ?? "").trim();
      const instrumentId = String(parsed.instrumentId ?? "").trim();
      const asOf = String(parsed.asOf ?? "").trim();
      if (!symbol || !instrumentId || !asOf) return null;
      return {
        accountId: String(parsed.accountId ?? "").trim(),
        symbol,
        instrumentId,
        asOf,
        bars: Number(parsed.bars ?? 0),
        strategyVersionId: String(parsed.strategyVersionId ?? "").trim(),
        candidateId: String(parsed.candidateId ?? "").trim(),
        previousMembership: Array.isArray(parsed.previousMembership)
          ? parsed.previousMembership.map((item) => String(item))
          : [],
      };
    } catch {
      return null;
    }
  }
  return null;
}

function runSeedCli(
  args: string[],
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<
  { code: number; stdout: string; stderr: string } | { reason: string }
> {
  return new Promise((resolve) => {
    const root = findRepoRoot();
    if (!root) {
      resolve({
        reason:
          `${ESTUDIO_DAILY_SEED_UNAVAILABLE_PREFIX}: no localicé la raíz del repo ` +
          `(${WORKSPACE_MARKER} + ${SEED_SCRIPT_REL}). Define E2E_REPO_ROOT o ejecuta ` +
          "Playwright desde el monorepo.",
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

    const finish = (
      outcome:
        | { code: number; stdout: string; stderr: string }
        | { reason: string },
    ) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(outcome);
    };

    const timer = setTimeout(() => {
      try {
        child.kill("SIGKILL");
      } catch {
        // best-effort: el timeout reporta igualmente.
      }
      finish({
        reason:
          `${ESTUDIO_DAILY_SEED_UNAVAILABLE_PREFIX}: timeout tras ${timeoutMs} ms.\n` +
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
        reason: `${ESTUDIO_DAILY_SEED_UNAVAILABLE_PREFIX} (uv/python no disponibles): ${err.message}`,
      });
    });
    child.on("close", (code) => {
      finish({ code: code ?? -1, stdout, stderr });
    });
  });
}

/** Siembra el mundo ESTUDIO de `(accountId, symbol)` reutilizando el CLI dev. */
export async function seedEstudioDailyWorld(opts: {
  accountId: string;
  symbol: string;
  asOf?: string;
  apiBase: string;
}): Promise<EstudioDailySeedOutcome> {
  if (!estudioDailySeedEnabled()) {
    return { ok: false, reason: ESTUDIO_DAILY_SEED_DISABLED_REASON };
  }
  const args = [
    "--account-id",
    opts.accountId,
    "--symbol",
    opts.symbol,
    "--api-base",
    opts.apiBase,
  ];
  if (opts.asOf) args.push("--as-of", opts.asOf);
  const result = await runSeedCli(args);
  if ("reason" in result) return { ok: false, reason: result.reason };
  if (result.code !== 0) {
    return {
      ok: false,
      reason:
        `${ESTUDIO_DAILY_SEED_UNAVAILABLE_PREFIX}: exit ${result.code}.\n` +
        tail(result.stderr || result.stdout),
    };
  }
  const manifest = parseManifest(result.stdout);
  if (!manifest) {
    return {
      ok: false,
      reason:
        `${ESTUDIO_DAILY_SEED_UNAVAILABLE_PREFIX}: el seed no publicó MANIFEST.\n` +
        tail(result.stdout),
    };
  }
  return { ok: true, manifest, stdout: result.stdout };
}

/**
 * Limpia lo sembrado (ids deterministas + filas de la cuenta) y restaura la lista `estudio`
 * EXACTA. Simétrico del seed; el `afterAll` lo usa para no dejar residuo en la BD dev.
 */
export async function cleanupEstudioDailyWorld(opts: {
  accountId: string;
  symbol: string;
  apiBase: string;
  previousMembership?: readonly string[];
}): Promise<{ ok: true } | { ok: false; reason: string }> {
  if (!estudioDailySeedEnabled()) {
    return { ok: false, reason: ESTUDIO_DAILY_SEED_DISABLED_REASON };
  }
  const args = [
    "--cleanup",
    "--account-id",
    opts.accountId,
    "--symbol",
    opts.symbol,
    "--api-base",
    opts.apiBase,
  ];
  if (opts.previousMembership) {
    args.push("--previous-membership", opts.previousMembership.join(","));
  }
  const result = await runSeedCli(args, CLEANUP_TIMEOUT_MS);
  if ("reason" in result) return { ok: false, reason: result.reason };
  if (result.code !== 0) {
    return {
      ok: false,
      reason:
        `La limpieza del seed falló (exit ${result.code}):\n` +
        tail(result.stderr || result.stdout),
    };
  }
  return { ok: true };
}
