# Evidencia — Integración Cuentas / Perfil inversor + fiscal (2026-10-30)

> Todo lo de esta carpeta se midió en el worktree
> `C:\Users\josea\.cursor\worktrees\integracion-cuentas-perfil-2026-10-30`
> (rama `integracion/cuentas-perfil-2026-10-30`), **nunca** en `Bolsa_V1`.
> La BD usada es la scratch propia `bolsa_v1_integracion` (061), no `bolsa_v1`.

## Qué hay aquí

| Fichero | Contenido |
|---|---|
| `certificacion-061.txt` | Ciclo completo de la 061 por la ruta real (`db-restore` → `ensure_migrated` → API): versión, `oid` de la FK, idempotencia, `downgrade`/`upgrade`, datos y arranque del API |
| `vitest-web-full-1.txt` / `-2.txt` | Dos pasadas completas de Vitest web (353 → **355 ficheros / 2.659 tests**) |
| `pytest-dirigido.txt` | Pytest dirigido del área (061, guard, carrera, contrato, perfiles, fiscal, enqueue race) con los gates `PROFILE_DELETE_*_PG_REQUIRED=1` |
| `mypy.txt` | `mypy` estricto sobre dominio, mercado, infraestructura, aplicación y API (**582 ficheros**) |
| `alembic-check-drift.txt` | Fallo **preexistente** del gate de drift (ver «Hallazgo 2») |
| `e2e-smoke.mjs` | Smoke Playwright del stack aislado (Vite 5318 → API 8318 → `bolsa_v1_integracion`) |
| `smoke-01-ficha.png`, `smoke-02-fiscal.png` | Capturas: ficha con perfil + resumen fiscal fusionado; diálogo abierto en Fiscal sin selector de perfil |
| `smoke-console.txt`, `smoke-result.json` | 12/12 comprobaciones OK y consola del navegador (0 `console.error`, 0 `pageerror`) |

## Gates medidos

| Gate | Comando | Resultado |
|---|---|---|
| TypeScript (raíz) | `pnpm typecheck` | 4/4 tareas OK |
| ESLint | `pnpm lint` | 4/4 tareas OK · **0 errores**, 23 warnings preexistentes |
| Contrato OpenAPI | `pnpm contract:check` | `OK — openapi.json y schema.d.ts coinciden` |
| Vitest web ×2 | `pnpm test` / `vitest run` | **355 ficheros / 2.659 tests** en ambas pasadas |
| Vitest shared | `pnpm --filter @bolsa/shared test` | 100 ficheros / 878 tests (+1 `todo`) |
| Pytest dirigido | ver `pytest-dirigido.txt` | **63 passed**, 0 skipped |
| Pytest integración | `tests/integration/test_accounts.py`, `test_tax_report.py` | 7 passed (tras `pnpm db:seed` en la scratch) |
| mypy | `mypy packages/py/{domain,market,infrastructure,application}/src apps/api-python/src` | **582 ficheros**, sin issues |
| YAML del CI | `yaml.safe_load` | válido; `Pytest integridad 061 PG` entre `Alembic upgrade head` y `Pytest A12 PG` |
| Smoke E2E | `node e2e-smoke.mjs` | **12/12** |

## Hallazgo 1 — el desfase que impedía arrancar la APP (reparado)

- `bolsa_v1.alembic_version` estaba en `061_profile_delete_restrict` (estampada por el stack
  del worktree candidato sobre la BD **compartida**) mientras `Bolsa_V1` solo conoce hasta
  `060_provider_check_policy` → `CommandError: Can't locate revision identified by
  '061_profile_delete_restrict'` en `ensure_migrated` y caída del lifespan.
- Reparado con `downgrade_to("060_provider_check_policy")` ejecutado **desde el worktree
  candidato** (el único que tiene el fichero de la 061 y el runner).
- Verificación posterior: versión `060`, FK `confdeltype='n'` (SET NULL, el comportamiento
  heredado), la única cuenta conserva su perfil (`PROF-996fcd3d6ec6`), 0 huérfanos.
- `ensure_migrated` desde `Bolsa_V1` → `True`, y `GET /api/health` del árbol fiscal → `200`
  con `schema_revision = 060_provider_check_policy`.
- Prevención aplicada: este worktree tiene su propio `.env` con
  `DATABASE_URL=…/bolsa_v1_integracion`; ningún stack de otro árbol se ejecuta contra `bolsa_v1`.

## Hallazgo 2 — el gate de drift NO está limpio, y no es por esta integración

Se midió antes de tocar nada del árbol fiscal y se reprodujo en sus dos linajes:

1. **Linaje restaurado/heredado** (copia del 29-oct, FK creada por el esquema Prisma):
   `alembic check` → `remove_fk(... onupdate='CASCADE', ondelete='RESTRICT')` +
   `add_fk(... ondelete='RESTRICT')`. La BD tiene `ON UPDATE CASCADE`; `tables.py` no declara
   `onupdate`. **La misma diferencia aparece en `Bolsa_V1` con la BD en 060** (con
   `ondelete='SET NULL'`), así que precede a la 061.
2. **Linaje nuevo** (BD creada solo con migraciones): falta el `CHECK`
   `sync_settings_provider_check_interval_check` que `Base.metadata` declara. Causa:
   `060_provider_check_policy.upgrade()` crea el constraint **solo dentro** de
   `if not _column_exists(_INTERVAL)`; la baseline ya incluye la columna, así que el
   constraint nunca se crea en una BD nueva.

Con `SCHEMA_DRIFT_PG_REQUIRED=1`, `test_schema_drift_gate_pg.py` falla en ambos linajes
(1 failed, 1 passed). **No se tocó**: es deuda del bloque fiscal (060) y cualquier cambio en
la 061 alteraría el candidato ya auditado. Se deja declarado para que el dueño del bloque
decida entre declarar `onupdate` en la metadata o corregir la guarda de la 060.

## Hallazgo 3 — `ruff` deriva por versión no fijada

`pyproject.toml` pide `ruff>=0.9` y **`uv.lock` no fija `ruff`**, así que `uv sync` instala
la última (0.16.2). Con esa versión, `ruff check packages/py apps/api-python` da **827 I001**
en este worktree y **824 I001** en `Bolsa_V1` (mismo repo, sin nuestros cambios): es deriva de
herramienta sobre ~800 ficheros, no de la integración. Los ficheros del diff dan 32 I001 + 1
B009 (este último en `docs/…/api-evidence.py`, fuera del gate). `ruff format --check` también
reformatearía 834 ficheros del repo. La evidencia de ambos bloques (`ruff.txt` = «All checks
passed!») se generó con una versión anterior de ruff.

## Reproducción

```powershell
# Stack aislado (puertos propios, BD scratch)
$env:DATABASE_URL='postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1_integracion?schema=public'
$env:API_PYTHON_PORT='8318'; $env:XTB_BRIDGE_AUTOSTART='0'
.venv/Scripts/bolsa-api.exe
$env:WEB_PORT='5318'; $env:API_PYTHON_PORT='8318'; pnpm --filter @bolsa/web dev

# Smoke
cd apps/web
$env:E2E_BASE_URL='http://localhost:5318'
node ..\..\docs\engineering\evidence\integracion-cuentas-perfil-fiscal-2026-10-30\e2e-smoke.mjs
```
