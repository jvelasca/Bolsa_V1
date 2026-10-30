# Evidencia — Cuentas y Perfil inversor (2026-10-30)

Salida cruda de los gates del seguimiento [`seguimiento-ui-cuentas-perfil-inversor-2026-10-30.md`](../../seguimiento-ui-cuentas-perfil-inversor-2026-10-30.md), ejecutada en el worktree `cuentas-perfil-2026-10-30` (rama `feat/cuentas-perfil-2026-10-30`, base `a5f6f1c6`).

Esta carpeta es el **lote de gates**. El recorrido visual y la auditoría del diff viven aparte:

- [`diff-audit.md`](./diff-audit.md): auditoría archivo por archivo del diff contra `a5f6f1c6`, hallazgos AUD-01…AUD-09 y **§7 con las correcciones aplicadas en la segunda pasada** (AUD-01, AUD-03, AUD-07).
- [`e2e/README.md`](./e2e/README.md): CUE-E2E con navegador real sobre el stack aislado del worktree, con capturas, `console.txt`, `network.txt` y las fotos de BD antes/después.

## Reproducción: `regen-evidence.ps1`

Todo el lote se regenera con un solo comando (PowerShell 5.1 o 7, sin dependencias extra):

```powershell
powershell -ExecutionPolicy Bypass -File docs\engineering\evidence\cuentas-perfil-2026-10-30\regen-evidence.ps1
```

El script ejecuta los once gates y escribe cada salida con `[System.IO.File]::WriteAllText` y
`UTF8Encoding($false)`: **UTF-8 sin BOM**, con el código de salida y la duración anotados al final de cada
fichero. Sale con código 1 si algún gate falla. **AUD-07 cerrado**: ya no se usa el `Out-File` por defecto de
PowerShell 5.1 (que escribía UTF-16LE) y `contract-check.txt` contiene la salida real de `contract:gen` +
`contract:check`, sin bytes NUL.

| Fichero | Gate | Comando | Resultado |
|---------|------|---------|-----------|
| `pytest-area.txt` | Suites de perfiles + guard de borrado + contrato de esquema + guardas de la 061 | `uv run pytest packages/py/application/tests/test_investor_profiles.py packages/py/infrastructure/tests/test_investor_profile_delete_guard.py packages/py/infrastructure/tests/test_schema_contract.py packages/py/infrastructure/tests/test_061_profile_delete_restrict.py apps/api-python/tests/test_investor_profiles_assign.py -v` | **33 passed** (10 fake store + 3 repositorio/concurrencia PG + 5 contrato + 11 guardas de la 061 + 4 ASGI) |
| `pytest-integridad-061.txt` | Ciclo de vida de la 061 sobre BD scratch + carrera real asignación/borrado | `uv run pytest packages/py/infrastructure/tests/test_061_profile_delete_restrict_pg.py packages/py/infrastructure/tests/test_investor_profile_delete_race_pg.py -v` con `PROFILE_DELETE_MIGRATION_PG_REQUIRED=1` y `PROFILE_DELETE_RACE_PG_REQUIRED=1` | **8 passed** (4 de migración + 4 de carrera); el gate convierte un skip en fallo |
| `vitest-area.txt` | Suites nuevas/tocadas de Cuentas | `npx vitest run src/features/accounts/{investor-profile-panel,accounts-page,account-detail-panel,account-investor-profile-select,account-settings-panel}.test.tsx --reporter=verbose` | **5 files · 23 tests passed** |
| `vitest-web-full.txt` | Paquete web completo | `pnpm --filter @bolsa/web test` | **353 files · 2637 tests passed** |
| `vitest-web-full-run2.txt` | Segunda ejecución independiente de confirmación | `pnpm --filter @bolsa/web test` | **353 files · 2637 tests passed** |
| `tsc.txt` | Typecheck web | `pnpm --filter @bolsa/web typecheck` (`tsc -b --noEmit`) | sin errores |
| `eslint.txt` | ESLint de las áreas tocadas | `npx eslint src/features/accounts src/features/config src/features/help` | sin hallazgos (solo warnings de Node) |
| `contract-check.txt` | Contrato OpenAPI | `node scripts/sync-contract.mjs` + `node scripts/sync-contract.mjs --check` (en `apps/web`) | `contract:gen OK` · `contract:check OK` — 237 paths, 519 schemas |
| `ruff.txt` | Lint Python | `uv run ruff check packages/py apps/api-python --config pyproject.toml --output-format=concise` | `All checks passed!` |
| `mypy.txt` | Tipos Python | `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | 582 files, sin errores |
| `api-responses.txt` | Respuestas HTTP reales | `uv run python api-evidence.py` (ASGI + PostgreSQL local) | `200` propio · `409 profile_in_use` · `404` ajeno · `PUT null` → `active_profile_id NULL` |

`vitest-web-full-run2.txt` es una **ejecución independiente** del paquete completo, no una copia: sirve para
descartar que el primer recuento dependiera de caché u orden de ficheros. El recuento de referencia anterior
(353 · 2632) subió a **353 · 2637** por los cinco tests nuevos de «Quitar perfil».

## `pytest-integridad-061.txt` — qué demuestra

Cierra las dos comprobaciones de integración que el dictamen deja antes de integrar el bloque:

- **Ciclo de vida de la migración 061** (`test_061_profile_delete_restrict_pg.py`), sobre una BD **scratch
  efímera** creada y destruida por el test: base nueva que nace en `RESTRICT` y no recrea la FK al
  re-aplicar; base heredada en `060` con la FK forzada a `SET NULL` **y un perfil asignado**, que al subir a
  `head` conserva la asignación, los recuentos y bloquea el `DELETE` crudo; lector concurrente que nunca
  observa la FK ausente ni en `SET NULL` durante el `DROP + CREATE`; y `downgrade` que vuelve a `SET NULL`
  sin huérfanos, más re-`upgrade` que restaura el bloqueo.
- **Carrera real asignación/borrado** (`test_investor_profile_delete_race_pg.py`): el orden se impone desde
  fuera y se verifica con `pg_blocking_pids` (no con `sleep`). Cubre «gana el borrado» (la asignación recibe
  «Perfil no encontrado» sin escribir), «gana la asignación» (el borrado devuelve `in_use` con la cuenta) y
  el backstop de la FK con escritores que **ignoran** el protocolo de lock, en ambos órdenes.

El script fija `PROFILE_DELETE_MIGRATION_PG_REQUIRED=1` y `PROFILE_DELETE_RACE_PG_REQUIRED=1`: un skip
silencioso es un fallo del gate. Las dos variables quedan también en el paso propio del job `lifecycle-pg`
de `.github/workflows/python-ci.yml`.

## `api-responses.txt` — cómo se genera

[`api-evidence.py`](./api-evidence.py) levanta la app con su `lifespan` real vía `ASGITransport` y encadena,
sobre PostgreSQL local: alta de un perfil propio → asignación a la cuenta semilla → `DELETE` **en uso**
(`409 profile_in_use` con la lista de cuentas, asignación intacta) → `GET`/`PUT` de un perfil de otro tenant
insertado por SQL (`404`, sin filtrar su existencia) → `PUT {"profileId": null}` («Quitar perfil») → el
`GET active-profile` pasa a `404` porque `active_profile_id` es `NULL`, **sin** asignar el perfil por defecto
→ `DELETE` del perfil ya libre (`200`) → restauración del perfil anterior en la cuenta.

Al terminar verifica que no queda ninguna fila `PROF-EVIDENCIA*` ni `PROF-AJENO-*` y deja la cuenta semilla
con su `active_profile_id` original (`PROF-996fcd3d6ec6`).

## Lo que **no** incluye

- No es una certificación del sello ni una autorización operativa.
- No incluye el trabajo fiscal (47 ficheros) del árbol principal: este worktree no lo contiene.
- Los recuentos son de esta máquina y esta base; el script es la fuente de verdad si el entorno cambia.
