# Logs de desarrollo (`logs/`)

> **Fuente de verdad:** este doc en `docs/`. El directorio `logs/` **no** lleva README propio (solo `.gitkeep`); los ficheros de log no se versionan.

Directorio local para desarrollo y para que el agente/CI inspecten estado. Contenido regenerable; **no** es documentación de producto.

## Estructura

| Carpeta    | Contenido                                       |
| ---------- | ----------------------------------------------- |
| `api/`     | Logs del backend (si se activan)                |
| `web/`     | Logs del frontend (si se activan)               |
| `dev/`     | Salida combinada de `pnpm dev` / `pnpm dev:log` |
| `tests/`   | Resultados de `pnpm test:log` (`latest.log`)    |
| `agent/`   | Resúmenes JSON legibles por el agente           |
| `startup/` | Timeline de arranque (`latest.json`)            |

## Archivos útiles (agente / diagnóstico)

- `agent/health.json` — último health check (API + Web)
- `agent/tests.json` — último resultado de tests
- `agent/dev.json` — estado del servidor de desarrollo
- `agent/events.log` — eventos estructurados (JSON lines)
- `agent/startup.json` — copia del timeline de arranque
- `startup/latest.json` — fases DB / shared / API / Web (ms)
- `tests/latest.log` — salida completa del último test run

## Comandos

```bash
pnpm setup          # setup inicial + tests
pnpm dev            # stack; log en logs/dev/
pnpm dev:log        # alias / log explícito
pnpm test:log       # tests con log en logs/tests/
pnpm health         # comprobar API y Web → agent/health.json
pnpm startup:report # tiempos de arranque
pnpm doctor         # diagnóstico (puertos, Docker, PG)
```

## Caída de la API: motivo `api-exit:`

`scripts/run-dev.mjs` declara el motivo de toda parada del stack. Cuando la API sale
estando ya lista, el motivo lleva el prefijo literal **`api-exit:`** y se escribe en tres
sitios a la vez: consola, `logs/dev/dev-*.log` y `logs/agent/events.log` (nivel `error`),
más el resumen en `logs/agent/dev.json` (`status: "stopped"`).

| `reason`                      | Cuándo                                                        |
| ----------------------------- | ------------------------------------------------------------- |
| `api-exit:<code>`             | La API terminó con ese código (incluye `api-exit:0`)          |
| `api-exit:signal:<SIG>`       | Murió por señal (`code === null`, p. ej. `SIGKILL`)           |
| `api-exit:spawn-error`        | No se pudo lanzar el proceso (python ausente, `EACCES`)       |
| `api-exit:unknown`            | Salió sin código ni señal declarados                           |
| `console-close:SIGHUP`        | Se cerró la ventana/consola                                   |
| `console-close:SIGBREAK`      | `Ctrl+Break`                                                  |

La línea identifica el proceso que inició el shutdown y adjunta la última salida de
uvicorn (la causa suele estar ahí):

```text
[dev] API salió (rol=api pid=48232 code=1 signal=-) — api-exit:1; se detiene el stack | último stderr: psycopg.OperationalError: connection refused
```

`logs/agent/dev.json` añade `role`, `pid`, `code`, `signal`, `uptimeMs` y `lastLines`.
Cualquier salida de la API tras el health es fatal: el stack no se queda vivo sin API.
`taskkill /F` sobre el **padre** (o un `Stop-Process` del propio `run-dev`) no es
capturable; en ese caso no hay `reason` y el fichero de sesión se queda en `ready`.

## Git

`.gitignore` ignora `logs/**` y conserva solo `logs/**/.gitkeep`.  
Rotación: cada `pnpm dev` conserva solo las `DEV_LOG_KEEP` sesiones `dev` más recientes
(`logs/dev/dev-*.log`; default 10, ajustable por entorno) y poda las más antiguas — las
demás carpetas de `logs/` sólo guardan los archivos `latest` + el sello de la última sesión.
Arranque del stack: [DEV_STARTUP.md](../DEV_STARTUP.md) · [docker.md](../docker.md).
