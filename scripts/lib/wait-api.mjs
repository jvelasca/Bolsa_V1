import http from 'node:http';

/**
 * Espera a que /api/health responda 200.
 * @param {{ port?: number, maxWaitMs?: number, intervalMs?: number, log?: (msg: string) => void }} [options]
 */
export async function waitForApi(options = {}) {
  const port = options.port ?? Number(process.env.API_PYTHON_PORT ?? 8000);
  const maxWaitMs = options.maxWaitMs ?? 90_000;
  const intervalMs = options.intervalMs ?? 400;
  const log = options.log ?? (() => {});
  const healthUrl = `http://127.0.0.1:${port}/api/health`;

  function pingHealth() {
    return new Promise((resolve) => {
      const req = http.get(healthUrl, (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      });
      req.on('error', () => resolve(false));
      req.setTimeout(1500, () => {
        req.destroy();
        resolve(false);
      });
    });
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  const started = Date.now();
  log(`Esperando API en ${healthUrl} (max ${Math.round(maxWaitMs / 1000)}s)...`);

  while (Date.now() - started < maxWaitMs) {
    if (await pingHealth()) {
      const elapsed = Date.now() - started;
      log(`API lista en ${elapsed}ms`);
      return { ok: true, elapsedMs: elapsed, url: healthUrl };
    }
    await sleep(intervalMs);
  }

  return {
    ok: false,
    elapsedMs: Date.now() - started,
    url: healthUrl,
    error: 'API timeout',
  };
}
