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

## Git

`.gitignore` ignora `logs/**` y conserva solo `logs/**/.gitkeep`.  
Rotación: cada `pnpm dev` conserva solo las `DEV_LOG_KEEP` sesiones `dev` más recientes
(`logs/dev/dev-*.log`; default 10, ajustable por entorno) y poda las más antiguas — las
demás carpetas de `logs/` sólo guardan los archivos `latest` + el sello de la última sesión.
Arranque del stack: [DEV_STARTUP.md](../DEV_STARTUP.md) · [docker.md](../docker.md).
