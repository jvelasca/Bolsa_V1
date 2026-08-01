import { ensureLogDirs, logInfo, logError, writeAgentLog } from './lib/logger.mjs';

const API_URL = process.env.VITE_API_URL ?? process.env.API_URL ?? 'http://localhost:8000';
const WEB_URL = process.env.WEB_URL ?? 'http://localhost:5173';

async function check(name, url) {
  const started = Date.now();
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
    const body = await response.text();
    return {
      name,
      url,
      ok: response.ok,
      status: response.status,
      latencyMs: Date.now() - started,
      bodyPreview: body.slice(0, 200),
    };
  } catch (error) {
    return {
      name,
      url,
      ok: false,
      status: 0,
      latencyMs: Date.now() - started,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

ensureLogDirs();

const checks = await Promise.all([
  check('api-health', `${API_URL}/api/health`),
  check('api-alerts', `${API_URL}/api/alerts`),
  check('web', WEB_URL),
]);

const report = {
  status: checks.every((c) => c.ok) ? 'healthy' : 'degraded',
  checks,
};

writeAgentLog('health', report);

for (const item of checks) {
  if (item.ok) {
    logInfo('health', `${item.name}: OK (${item.status}) ${item.latencyMs}ms`);
  } else {
    if (item.name === 'api-alerts' && item.status === 404) {
      logError(
        'health',
        `${item.name}: FAIL — la API en ${API_URL} no tiene rutas de alertas. Detén sesiones de depuración duplicadas y reinicia (Bolsa: API Python).`,
        item,
      );
    } else {
      logError('health', `${item.name}: FAIL`, item);
    }
  }
}

process.exit(report.status === 'healthy' ? 0 : 1);
