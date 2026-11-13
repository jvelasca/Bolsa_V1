# Auditoría de integración — Fase 4 del bloque crítico de `/mercado/operativa`

**Fecha:** 2026-11-11 · **Árbol base:** `ae6410bf` (sin commitear; `main` +2 sobre `origin/main`)
**Alcance:** auditoría de integración, no reapertura de los ocho puntos ya cerrados.
**Estado de AUTO:** sin cambios — **PAPER**, AUTO desactivado, sin certificación de rentabilidad.

---

## 1. Qué se ha hecho en esta auditoría

1. **Prueba real de la migración `067_opinion_account_scope` con datos existentes** sobre una base
   scratch desechable (`test_067_opinion_account_scope_pg.py`). No existía: los «7 passed» de
   `test_unique_natural_keys_pg.py` son **6 guardias de claves naturales + el roundtrip de la `041`**.
2. **Cableado en CI**: el nuevo test entra en el job `lifecycle-pg` con
   `OPINION_ACCOUNT_SCOPE_PG_REQUIRED=1`; `contract:check` deja de ser decorativo en pushes normales
   (se añade `setup-uv` y el paso en `frontend-ci.yml`).
3. **Corrección del CHANGELOG**: se retira la atribución falsa del roundtrip y se sustituyen los
   recuentos por los medidos en esta sesión.
4. **Defecto de compilación corregido**: `packages/shared/src/instrument-daily-opinion.ts` tenía dos
   comentarios con sintaxis Python (`#`) dentro del array `as const`. Rompía `tsc`, el build de
   `@bolsa/shared` y, en cascada, las 379 suites de `@bolsa/web`. El «`tsc -b` limpio» del resumen no
   se sostenía sobre este árbol.
5. **Revisión de los puntos de unión** del diff (ruta → servicio → repositorio, historial, telemetría,
   contexto operativo, armado reactivo, confirmación y auditoría).

## 2. Qué queda demostrado (evidencia local)

| Área | Comando | Resultado |
| --- | --- | --- |
| Aplicación | `uv run python -m pytest packages/py/application/tests -q` | **3247 passed, 5 skipped** |
| Migración 067 (scratch) | `OPINION_ACCOUNT_SCOPE_PG_REQUIRED=1 pytest packages/py/infrastructure/tests/test_067_opinion_account_scope_pg.py` | **4 passed** |
| Roundtrip 041 (scratch) | `UNIQUE_NATURAL_KEYS_PG_REQUIRED=1 pytest packages/py/infrastructure/tests/test_041_unique_natural_keys_roundtrip_pg.py` | **1 passed** |
| Guardias de claves naturales | `UNIQUE_NATURAL_KEYS_PG_REQUIRED=1 pytest apps/api-python/tests/test_unique_natural_keys_pg.py` | **6 passed** |
| Guardias PG + 067 | `pytest test_account_evidence_policy_pg.py test_dia_d_cycle_verification_pg.py test_067_..._pg.py` | **19 passed** |
| Ciclo de vida del arnés scratch | `SCRATCH_DB_GUARD_PG_REQUIRED=1 pytest packages/py/infrastructure/tests/test_scratch_database_helper_pg.py` | **10 passed** |
| Guard de fugas de BD scratch | `uv run python packages/py/infrastructure/scripts/assert_no_scratch_databases.py` | **exit 0 · `scratch databases: none`** |
| Arnés endurecido sobre 041/061/062/067 | `pytest test_041_..._roundtrip_pg.py test_061_..._pg.py test_investor_profile_delete_race_pg.py test_062_..._pg.py test_067_..._pg.py` | **1 + 12 + 4 passed** |
| Web (vitest completo) | `pnpm --filter @bolsa/web test` | **379 ficheros / 2812 tests** |
| Shared (vitest) | `pnpm --filter @bolsa/shared test` | **104 ficheros / 914 passed, 1 todo** |
| Typecheck | `pnpm --filter @bolsa/shared typecheck` · `pnpm --filter @bolsa/web typecheck` | limpio |
| Ruff | `uv run ruff check packages/py apps/api-python --config pyproject.toml` (`0.16.2`) | **All checks passed** |
| Contrato | `pnpm --filter @bolsa/web contract:check` | **OK** |
| ESLint | `pnpm --filter @bolsa/web lint` | **0 errores / 23 warnings** |

Los 23 warnings son `react-hooks/exhaustive-deps` en 10 ficheros. En los dos que toca la fase
(`mesa-hoy-page.tsx` línea 237, `list-recommendation-scores-context.tsx` línea 67) el aviso cae sobre
lógica preexistente, no sobre las líneas modificadas. Se mantienen como deuda identificada.

### Casos cubiertos por la nueva prueba de la 067

- **Base nueva**: `position_open` nullable, `account_id NOT NULL`, índice único de cuatro columnas y
  ausencia del de tres; la 067 es idempotente sobre lo que ya creó el baseline.
- **Datos heredados en `066`**: filas con `account_id NULL` pasan a `__global__` sin perder ninguna; las
  cuentas reales no se reescriben; `position_open` queda `NULL` (no se inventa «sin posición») y un
  `INSERT` crudo con `NULL` falla con `NotNullViolation`.
- **`downgrade` con varias cuentas**: colapsa a la fila más reciente por `(instrumento, día, fuente)`,
  devuelve `__global__` a `NULL` **después** de relajar el `NOT NULL` (sin `NotNullViolation`), retira
  `position_open` y restaura la clave de tres columnas.
- **Reversibilidad**: un segundo `upgrade` repone la 067 y rellena los nulos sin violar la restricción.

## 3. Hallazgos de integración

### H-1 (alta) — RESUELTO — El roundtrip de la `041` se había vuelto destructivo

`test_unique_natural_keys_pg.py` bajaba a `040_auto_v2_durable_state` **contra `DATABASE_URL`**.
Desde que la head es `067`, ese `downgrade` ejecuta también el de la 067, que (a) retira
`position_open` de todas las filas y (b) **descarta filas** cuando más de una cuenta comparte
`(instrumento, día, fuente)`. Sobre la BD local (2322 filas, 0 claves multi-cuenta) la pérdida
habría sido solo de la columna de medición; con dos cuentas, de dictámenes.

**Aplicado:** el roundtrip vive ahora en
`packages/py/infrastructure/tests/test_041_unique_natural_keys_roundtrip_pg.py`, sobre base
**scratch** (`CREATE/DROP DATABASE`, nunca `DATABASE_URL`), usando `migrate_to`/`downgrade_to`
—el runner de producción— en vez de manipular `_alembic_config()` a mano. El fichero de la app
conserva **solo las 6 guardias** de claves naturales y su docstring declara el motivo del
traslado. CI: el nuevo fichero entra en `lifecycle-pg` con `UNIQUE_NATURAL_KEYS_PG_REQUIRED=1`.

**Endurecimiento del arnés (segunda pasada).** El aislamiento no estaba probado: se apoyaba en
`scratch_database` sin ninguna verificación propia. Ahora:

- `_scratch_name` sortea `<prefijo>_<uuid4().hex[:10]>` y **rechaza** `postgres` y el nombre de la BD
  de `DATABASE_URL`; agotados los 16 intentos falla en voz alta en vez de crear la base equivocada.
  El prefijo se valida con el criterio del DDL (`[a-z0-9_]`).
- `_create_scratch` reintenta con otro sufijo ante `DuplicateDatabase` (carrera con otra ejecución
  concurrente), así que dos jobs no pueden pisarse.
- El `DROP` sigue en `finally` (cubre excepción y `KeyboardInterrupt`); si el `DROP` falla, la
  excepción original se conserva encadenada (`raise ... from`) en vez de enmascararse.
- `test_scratch_database_helper_pg.py` (10 casos, gate `SCRATCH_DB_GUARD_PG_REQUIRED=1`) fija esos
  contratos: crea/borra, limpieza con `RuntimeError`, limpieza con `KeyboardInterrupt`, ausencia de
  enmascaramiento cuando el `DROP` falla (`__cause__` = excepción del cuerpo), dos contextos simultáneos
  con nombres distintos, 50 nombres sin repetición y anti-colisión con `uuid4` forzado.
- `scripts/assert_no_scratch_databases.py` cierra el único hueco que un `finally` no puede cubrir: un
  `SIGKILL` del runner (timeout o cancelación). Corre con `if: always()` al final de `lifecycle-pg` en
  ambos workflows y falla si sobrevive una BD con la firma del arnés. No usa un `bolsa%` genérico
  porque `bolsa_v1_iso` es una base dedicada legítima del propio job del tag.

**Reparto en CI.** `python-ci.yml` ya ejecutaba 041/067 en scratch; ahora suma el arnés y la sonda de
fugas. `release-tag-ci.yml` **no** los ejecutaba: el `lifecycle-pg` del tag pasa a correr
`test_041_..._roundtrip_pg.py`, `test_067_..._pg.py` y `test_scratch_database_helper_pg.py`, con
`OPINION_ACCOUNT_SCOPE_PG_REQUIRED=1` y `SCRATCH_DB_GUARD_PG_REQUIRED=1` (el gate de la 041 ya estaba).
Los tres ficheros entran también en el `--ignore` del pase de directorio offline, donde skipearían en
mudo sin PostgreSQL. Queda fuera de esta corrección —y se anota como deuda— que el `lifecycle-pg` del
tag tampoco ejecuta `test_061_..._pg.py` ni `test_062_..._pg.py`.

### H-2 (media) — Los chips se calculan antes de validar la caché

`DailyOpinionService.query()` llama a `_resolve_hints()` antes de leer la caché, y la ruta ya no manda
`hints`. Resultado: cada consulta —incluidas las que sirven una fila cacheada— ejecuta los chips
composite/FA para todos los ids. Antes el cliente aportaba los hints y la caché se resolvía primero.
No es un fallo de corrección (la postura sigue siendo la medida), pero es una regresión de coste en la
ruta más caliente del panel.

**Recomendación:** medir primero la posición (barata), decidir con la caché y medir chips solo para los
ids que fallen la validación.

### H-3 (media) — Sin adaptador OHLCV no hay revalidación de precio

En `confirm_recommendation.py` el bloque de precio está bajo `self._ohlcv is not None`. Si el adaptador
no está inyectado, `last_close` nunca es `None` «conocido»: simplemente no se comprueba y la ejecución
sigue. En producción `get_ohlcv_repository` siempre se inyecta, así que hoy es una vía de tests; pero
contradice el «fail-closed» que declara el CHANGELOG (`price_unmeasured`).

**Recomendación:** tratar adaptador ausente igual que último cierre desconocido (`price_unmeasured`).

### H-4 (baja, informativa) — Deriva de linaje: a `066` conviven los dos índices únicos

El baseline `003` construye las tablas desde `Base.metadata`, es decir, desde el **modelo vivo**. Por eso
una base nueva ya nace con el índice de cuatro columnas y `account_id NOT NULL`; la `041` entonces
encuentra ausente el de tres columnas y **lo crea también**. Consecuencia: a `066` hay dos índices
únicos sobre la misma tabla en una base nueva, mientras que una base heredada real solo tiene el viejo.
La 067 lo resuelve (retira el viejo), pero conviene saberlo al leer `alembic check` y al interpretar
cualquier guardia de deriva.

### H-5 (informativa) — Sin cuenta activa, el CTA de entrada queda bloqueado

`studiesMeasured` exige `effectiveAccountId`; sin cuenta, la query de estudios no llega a `isSuccess` y
el cockpit muestra «No medido» con el CTA deshabilitado. Es coherente con fail-closed, pero conviene
confirmar que es el comportamiento de producto deseado (no un efecto colateral).

## 4. Qué NO queda demostrado

- **No hay commit.** Todo el bloque vive en el árbol de trabajo sobre `ae6410bf`; `main` está 2 commits
  por delante de `origin/main`.
- **No hay CI sobre este código.** La última ejecución verde es del tag `v2.88.188-beta`, anterior a la
  Fase 4. Existe además un `Frontend CI` en rojo sobre `main` (`run 42983533942`, 07:59) previo a la fase.
- **No se ha ejecutado el roundtrip de la `041`** contra la BD de desarrollo: ya no debe hacerse
  (H-1). Su cobertura es la base scratch, ejecutada y verde.
- **No hay prueba sobre un dump/restauración** de la BD de desarrollo: la evidencia de datos existentes
  es la base scratch sembrada, no una copia de producción.

## 5. Checklist para el sello

1. [ ] Commit del bloque (incluida la corrección de `instrument-daily-opinion.ts`).
2. [ ] Push y **CI verde sobre el SHA exacto** a certificar (Python, Frontend, lifecycle-pg, release-tag).
3. [ ] Árbol limpio (`git status` vacío) en ese SHA.
4. [ ] Decidir sobre H-2 y H-3 (coste de chips y `price_unmeasured` sin adaptador).
5. [ ] `CHANGELOG.md` con la sección `[Unreleased]` promovida solo cuando exista versión sellada.

## 6. Veredicto

**Funcionalidad e integridad: PASS** con la evidencia local de la tabla §2 y la cobertura nueva de la
067. **Sello: no procede todavía** — falta commit, CI sobre el SHA exacto y árbol limpio. H-1 queda
resuelto en esta auditoría; H-2 y H-3 siguen abiertos y no reabren los ocho puntos cerrados.

**AUTO sigue en PAPER, desactivado y sin certificación de rentabilidad.**
