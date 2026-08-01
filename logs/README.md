# Logs — Bolsa V1

Directorio de logs para desarrollo y para que el agente de Cursor pueda inspeccionar el estado del proyecto.

## Estructura

| Carpeta | Contenido |
|---------|-----------|
| `api/` | Logs del backend Fastify (`api.log`) |
| `web/` | Logs del frontend (si se activan) |
| `dev/` | Salida combinada de `pnpm dev:log` |
| `tests/` | Resultados de `pnpm test:log` (`latest.log`) |
| `agent/` | Resúmenes JSON legibles por el agente |

## Archivos clave para el agente

- `agent/health.json` — último health check (API + Web)
- `agent/tests.json` — último resultado de tests
- `agent/dev.json` — estado del servidor de desarrollo
- `agent/events.log` — eventos estructurados (JSON lines)
- `tests/latest.log` — salida completa del último test run

## Comandos

```bash
pnpm setup        # setup inicial + tests
pnpm dev:log      # desarrollo con log en logs/dev/
pnpm test:log     # tests con log en logs/tests/
pnpm health       # comprobar API y Web
```

Los archivos de log **no se suben a git** (excepto este README y `.gitkeep`).
