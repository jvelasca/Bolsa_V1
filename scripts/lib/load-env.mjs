import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT } from './logger.mjs';

/**
 * Carga un `.env` (formato `KEY=VALUE`) en `process.env` sin pisar variables
 * ya presentes en el entorno real del shell.
 *
 * Devuelve el número de variables cargadas. No resuelve variables interpoladas
 * ni valores multi-línea complejos: para dev local basta con líneas planas.
 */
export function loadEnvFile(filePath = join(ROOT, '.env')) {
  if (!existsSync(filePath)) return 0;
  const raw = readFileSync(filePath, 'utf8');
  let loaded = 0;
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    if (!key) continue;
    // Quitar comillas envolventes simples/dobles.
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (process.env[key] === undefined) {
      process.env[key] = value;
      loaded += 1;
    }
  }
  return loaded;
}
