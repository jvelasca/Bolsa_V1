# Arranque en desarrollo (F5)

Guía única para Cursor/VS Code y terminal. **Un solo flujo recomendado.**

## F5 — forma correcta

1. **Tras reiniciar el PC** (una vez): Docker Desktop en verde + `pnpm db:ensure`
2. **F5** con launch config: **`Bolsa: F5 Dev (recomendado)`**

Eso arranca en **un solo proceso** (Node `run-dev.mjs`):

| Paso | Qué hace |
|------|----------|
| 1 | Ping PostgreSQL; si no hay BD → setup completo |
| 2 | Migraciones Prisma (rápido, no interactivo) |
| 3 | Libera puertos 8000 / 5173 / 3002 si quedaron colgados |
| 4 | Compila `@bolsa/shared` (skip si `dist` ≥ `src`) |
| 5 | Arranca **API** Python (:8000) y **espera** `/api/health` |
| 6 | Arranca **Web** Vite (:5173) — sin `ECONNREFUSED` |
| 7 | Opcional: bridge XTB mock (:3002) |

**API reload:** por defecto **sin** `--reload` (arranque ~2× más rápido). Para autoreload al editar Python:

```powershell
$env:BOLSA_API_RELOAD=1; pnpm dev
```

En Windows, sin reload uvicorn usaría `ProactorEventLoop` (incompatible con psycopg). `run_dev.py` fuerza `SelectorEventLoop` vía `bolsa_api.win_loop`.

**URLs:** Web http://localhost:5173 · API http://localhost:8000/api/health

Cursor abre el navegador al ver `Web lista -> http://localhost:5173` (`serverReadyAction` en `.vscode/launch.json`). Si aparece *Failed to open… (0x2)*, es un fallo al lanzar el navegador por defecto (no de la app); el stack sigue OK. Revisa el navegador predeterminado de Windows o abre la URL a mano.

### Arranque rápido (warm F5)

| Fase | Antes (típ.) | Ahora |
|------|--------------|-------|
| PostgreSQL ping+migrate | ~0.1–0.2 s | igual (cache fingerprint) |
| Liberar puertos Windows | ~3 s (PowerShell) | ~0.1–0.3 s (`netstat`) |
| Import API + health | ~3 s | igual (sin `--reload`) |
| UI listas tras paint | N× `GET /lists/{id}` + N× strategy-top | `GET /lists/memberships` + batch tops |
| CORE-R shell al abrir | tick inmediato | diferido idle / ~4 s (cadencia sigue en minutos) |

Informe: `pnpm startup:report` · `logs/agent/startup.json`.

## No uses (obsoleto / confuso)

| Antes | Problema |
|-------|----------|
| Compound «API Python + Web» | 2 debuggers Node, race conditions, tasks colgadas |
| Solo «Bolsa: Web» | API no arranca → proxy ECONNREFUSED |
| Task «Docker + PostgreSQL» en cada F5 | Lento (1-2 min Docker); solo tras reinicio PC |
| `db push` interactivo | Prompt Prisma colgaba la task |

## Comandos útiles

```powershell
pnpm doctor          # diagnóstico (puertos, Docker, PG, runtime)
pnpm doctor:fix      # libera puertos 8000/5173/3002
pnpm dev:verify      # doctor + smoke tests Python
pnpm startup:report  # tiempos de arranque (agente / diagnóstico)
pnpm db:ensure       # Docker + PG + migrate + seed (setup)
pnpm health          # HTTP check API + Web (con servicios en marcha)
pnpm dev             # mismo que F5 Dev (terminal)
```

## Si algo falla

1. **Ctrl+C** en terminales de debug anteriores
2. `pnpm doctor:fix`
3. Si PostgreSQL down: `pnpm db:ensure`
4. F5 de nuevo con **«Bolsa: F5 Dev (recomendado)»**

Logs: ver [engineering/dev-logs.md](./engineering/dev-logs.md) (`logs/dev/`, `logs/agent/`, `logs/startup/`). No hay README dentro de `logs/` — la doc vive en `docs/`.

## Informe de arranque (agente)

Tras cada F5 / `pnpm dev`, se escribe una línea de tiempo en:

- `logs/startup/latest.json` — fases (DB, shared, API, Web) con ms por paso
- `logs/agent/startup.json` — copia para el agente

Consulta rápida:

```powershell
pnpm startup:report
```

El agente puede leer esos JSON para comparar arranques tras reinicios o cambios en el stack.

## Launch configs (avanzado)

| Config | Cuándo |
|--------|--------|
| **F5 Dev (recomendado)** | Uso diario |
| Solo API | Depurar backend sin Vite |
| Solo Web | Solo si API ya corre en :8000 |

## Puertos

| Puerto | Servicio |
|--------|----------|
| 5432 | PostgreSQL (Docker `bolsa-postgres`) |
| 8000 | API FastAPI |
| 5173 | Vite dev server |
| 3002 | XTB bridge mock |
