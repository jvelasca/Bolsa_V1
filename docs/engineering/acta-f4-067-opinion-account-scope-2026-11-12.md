# Acta de cierre — `F4-067-opinion-account-scope`

> **AsOf:** 2026-11-12
> **Padre:** [`engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md)
> **Veredicto:** **PASS funcional** · **PARTIAL PASS** en el CI global (el `Release tag CI` no queda GREEN).
> **Estado AUTO/PAPER:** sin cambios — **AUTO OFF**, PAPER **virtual e inconcluso**.
> **Naturaleza del acto:** documental, de solo lectura sobre el código. **No** introduce commit correctivo,
> **no** mueve `main` ni `origin/main`, **no** crea tags ni Releases y **no** re-ancla el pin PAPER.

---

## 1. Objeto y commit de referencia

| Dato | Valor |
| --- | --- |
| Commit de referencia | `bcdc45841b5bf12c0cabc282b3035ca310609b40` |
| Mensaje | `feat(fase4): migración 067 (dictamen por cuenta), arnés scratch y certificación PG en CI` |
| Autor / fecha del commit | `jvelasca` · 2026-11-12 07:30:40 +0100 |
| Rama | `feat/f4-067-opinion-account-scope` |
| `origin/feat/f4-067-opinion-account-scope` | `bcdc4584…` (idéntico: el slice está publicado en su rama) |
| Ancestro común con `main` | `1a091b36` (= `origin/main`) |
| Tags que apuntan al commit | **ninguno** |
| Run que lo mide | [`43169810570`](https://github.com/jvelasca/Bolsa_V1/actions/runs/43169810570) (`Release tag CI`, `workflow_dispatch`, intento 1) |

**Toda la evidencia de este acta se apoya en el objeto commit, no en el árbol de trabajo.** El checkout
local del 2026-11-12 contiene trabajo ajeno al slice (§8) que **no** forma parte de lo certificado aquí.

---

## 2. Integridad del cambio

`git show --numstat bcdc4584` devuelve **exactamente 18 rutas**, y `git diff --stat main...HEAD` devuelve
**solo esas 18** (+1291 / −201). No hay rutas incorporadas por arrastre.

| Área | Rutas |
| --- | --- |
| Workflows | `.github/workflows/python-ci.yml`, `.github/workflows/release-tag-ci.yml` |
| Migración | `packages/py/infrastructure/alembic/versions/067_opinion_account_scope.py` (nueva, 166 líneas) |
| Modelo | `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py` |
| Repositorio | `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/instrument_daily_opinion_repository.py` |
| Arnés scratch | `packages/py/infrastructure/tests/_profile_pg_helpers.py`, `packages/py/infrastructure/scripts/assert_no_scratch_databases.py` |
| Pruebas nuevas | `test_067_opinion_account_scope_pg.py` (425), `test_041_unique_natural_keys_roundtrip_pg.py` (189), `test_scratch_database_helper_pg.py` (157) |
| Guardias de head `066 → 067` | `apps/api-python/tests/test_account_evidence_policy_pg.py`, `test_auto_p7_lease_claim_pg.py`, `test_auto_v57_auto16_applied_cost_pg.py`, `test_auto_v88_27_durable_facts_idempotent_pg.py`, `test_dia_d_cycle_verification_pg.py`, `test_discovery_evidence_snapshot_pg.py`, `test_signal_alerts_v111_pg.py`, `test_unique_natural_keys_pg.py` |

Comprobaciones de no contaminación:

- `main` local = `ae6410bf`; `origin/main` = `1a091b36`; `main` está **+2 / −0** sobre `origin/main`
  (los dos commits documentales: `6032aa74`, `ae6410bf`). Ninguno entra en el diff del slice.
- **0 tags** apuntan a `bcdc4584` (total del repo, 361 tags: sin cambios por este acto).
- `CHANGELOG.md` **no** forma parte de las 18 rutas.

---

## 3. Qué queda certificado

### 3.1 Migración `067` hasta head

El log del job `lifecycle-pg` del run acredita el salto real de revisión sobre PostgreSQL:

```
INFO [alembic.runtime.migration] Running upgrade 066_account_evidence_policy -> 067_opinion_account_scope
```

### 3.2 Pruebas PostgreSQL

El paso `Pytest lifecycle PG + auth + golden … (fail if skipped)` de `lifecycle-pg` ejecuta —con
`UNIQUE_NATURAL_KEYS_PG_REQUIRED=1`, `OPINION_ACCOUNT_SCOPE_PG_REQUIRED=1` y
`SCRATCH_DB_GUARD_PG_REQUIRED=1`— también `test_041_unique_natural_keys_roundtrip_pg.py`,
`test_067_opinion_account_scope_pg.py` y `test_scratch_database_helper_pg.py`:

```
245 passed in 80.17s (0:01:20)
```

Resto de pasos del mismo job, todos `success`:

| Paso | Resultado publicado |
| --- | --- |
| W-G2/2 PostgreSQL batch (32 files) | `179 passed in 51.08s` |
| account-isolation gate V2.15.4 | `45 passed, 4 warnings` |
| Golden Day 2.0 | `3 passed` |
| AUTO ruta REAL del productor | `7 passed` |
| AUTO universe / DÍA-D / watch / PAPER / chain / identity / attempt cap | `23 passed` |
| DS-1 lease + C-1 readGaps + O-2 savepoint | `28 passed` |
| Crash/Recovery Day | `2 passed` |
| Concurrent AUTO (3 sesiones) | `3 passed` |
| HardKill recovery | `5 passed` |
| Crash injection matrix | `2 passed` |
| Multiprocess AUTO | `2 passed` |
| **Sin BD scratch huérfana (`if: always()`)** | `scratch databases: none` |

La sonda de bases huérfanas corre con `always()`: también se ejecuta si un test PG falló o el job se
cortó, de modo que una base huérfana no puede pasar desapercibida y envenenar la corrida siguiente.

### 3.3 Python y calidad estática sobre el mismo SHA

Job `python (ruff/imports/mypy/pytest offline)` ⇒ **`success`**:

| Gate | Salida |
| --- | --- |
| Ruff | `All checks passed!` |
| import-linter | `Contracts: 4 kept, 0 broken.` |
| mypy | `Success: no issues found in 599 source files` |
| pytest offline | `6515 passed, 111 skipped, 12 warnings in 169.26s` |

### 3.4 Frontend y contrato

Job `frontend (typecheck/lint/test/build + contract:check)` ⇒ **`success`** (vitest
`377` ficheros / `2801` pruebas `passed`). El slice **no** toca `openapi.json` ni `schema.d.ts`, y
`contract:check` corre dentro de ese job.

### 3.5 Integración en los workflows (lo que deja de depender de una corrida local)

El valor estructural del slice es este: los tests `041`/`067` y el arnés de bases temporales **ya no se
certifican por una ejecución local aislada**, sino en los workflows, con sus variables de obligatoriedad
activadas (`OPINION_ACCOUNT_SCOPE_PG_REQUIRED`, `SCRATCH_DB_GUARD_PG_REQUIRED`,
`UNIQUE_NATURAL_KEYS_PG_REQUIRED`). En el job offline se **ignoran explícitamente** las tres rutas
(`--ignore=…`) para que no skipeen en mudo dentro del pase de directorio; su certificación vive en
`lifecycle-pg`. Un `skip` ahí es un fallo duro, no un verde silencioso.

### 3.6 Trazabilidad de las cifras

| Cifra | Origen | Nivel de evidencia |
| --- | --- | --- |
| `245 passed` (incluye 041/067/arnés) | log de `lifecycle-pg` del run `43169810570` | **medida en CI** |
| `23/23` en la suite scratch | veredicto de la sesión que originó este acta | **reportada**, no re-derivada aquí |
| Composición local de referencia (4 + 1 + 6 + 10) | [`auditoria-integracion-fase4-2026-11-11.md`](./auditoria-integracion-fase4-2026-11-11.md) §2 | **medida en local** (2026-11-11) |
| `6515 passed, 111 skipped` · Ruff/imports/mypy | log del job `python` del mismo run | **medida en CI** |
| `2801 passed` (377 ficheros) | log del job `frontend` del mismo run | **medida en CI** |
| Limpieza de bases scratch | paso `Sin BD scratch huérfana` del mismo run | **medida en CI** |

Se deja constancia de la diferencia de granularidad: el CI no publica un total único de «suite scratch»;
la cifra que el run sí publica y sostiene la certificación es la de **245 pasadas**.

---

## 4. Qué no queda certificado

**PARTIAL PASS.** El run `43169810570` sobre `bcdc4584` termina en `failure`. Reparto de los 15 jobs:

| Resultado | Jobs |
| --- | --- |
| `success` (12) | `security`, `decision-spine`, `frontend`, `python`, `lifecycle-pg`, `replay-repro`, `dr-verify`, `a7-gate`, `playwright (mock E2E)`, `playwright (integrated AUTO S5)`, `playwright (integrated axe)`, `playwright (live AUTO daily chain)` |
| `failure` (2) | `shared (build/typecheck/test)`, `certify (aggregate + artifact)` |
| `skipped` (1) | `playwright (integrated E2E, opt-in)` — no certifica |

El fallo de `shared` **se limita al freeze de ventana**. Pasos del job:

| Paso | Resultado |
| --- | --- |
| Install / Build shared / Typecheck shared / Test shared | `success` (vitest: `104` ficheros) |
| Window runner guards (lock/config/provenance) | `success` (`# pass 86 · # fail 0`) |
| **Window freeze gate (pin == HEAD:apps/packages)** | **`failure`** |
| CI helper guards (playwright attempt timings) | `skipped` (no se alcanza) |

`certify` falla por **agregación** de `needs`, no por pruebas de migración ni de integridad: su único
paso ejecutado, `Fail if any required job failed`, sale 1 arrastrando el `shared` rojo.

**Lo que este acta no certifica en ningún caso:** rentabilidad, comportamiento longitudinal de PAPER ni
autorización para operar con dinero real. El alcance es la migración `067` y la integridad de
`instrument_daily_opinion`.

---

## 5. Bloqueo independiente: `window:freeze` / `TREE_MOVED`

### 5.1 El gate

En [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) (job `shared`):

```yaml
- name: Window freeze gate (pin == HEAD:apps/packages)
  run: pnpm window:freeze   # → node scripts/window-pin.mjs --check
```

El pin vive en `WINDOW_CONFIG` ([`scripts/lib/window-forward.mjs`](../../scripts/lib/window-forward.mjs)) y
se compara contra `git rev-parse HEAD:apps` y `HEAD:packages`. Si no casan, sale 1 con `TREE_MOVED`.

### 5.2 Causa medida

Reproducido en local sobre `bcdc4584` (`node scripts/window-pin.mjs --check`, exit 1):

| Campo | Pin (`90d07886`) | `HEAD` (`bcdc4584`) |
| --- | --- | --- |
| `commit` | `90d07886` | `bcdc4584` |
| `appsHash` | `5310f21dece29a4421acd16930856bec39e807ba` | `c552a16ec77bbf6a65700b171a08bbd7f3d7a6e5` |
| `packagesHash` | `7c31fca31e8825012d53bddc561ccde7501fd617` | `07647bd08598fd537e7a9bfc8ab57d2d9446f0d3` |

El pin coincide con el árbol del tag `v2.88.188-beta` (`53285f18`): `apps` `5310f21d…` y `packages`
`7c31fca3…`, los mismos que `WINDOW_CONFIG`. Su etiqueta `commit` (`90d07886`, el commit del bump) es
anterior al commit del tag y no participa del freeze real. La punta actual de `main` (`ae6410bf`) ya **no**
coincide: su `appsHash` es `53100a32…` (los goldens y un test movidos bajo `apps/` en los commits POST-TAG),
aunque `packages` sigue igual (`7c31fca3…`). El Release tag CI se disparó por
`workflow_dispatch` **sobre la rama del slice**, y el slice toca `apps/` (guardias de head) y `packages/`
(migración, modelo, repositorio, pruebas). **Cualquier rama que toque esos dos árboles falla este gate por
construcción**, con independencia de lo que la migración haga. No es *drift* del pin: es el gate midiendo
otra cosa.

### 5.3 Evidencia del log del run

El subtest que define la semántica del freeze **pasa**:

```
ok 68 - S1: TREE_MOVED es fallo duro e invalida la medicion
```

(`scripts/lib/window-measurement-check.test.mjs`). Acto seguido, el gate real sale 1:

```
> node scripts/window-pin.mjs --check
[window-pin] TREE_MOVED — el pin NO coincide con el arbol de HEAD
##[error]Process completed with exit code 1.
```

Es decir: el gate hace exactamente lo que su prueba dice que debe hacer. El rojo es **pretendido** y su
causa es de encuadre, no de calidad del slice.

### 5.4 Qué se excluye explícitamente

- **No** se re-ancla el pin (`window:pin --write`) dentro de este trabajo. Re-anclar el pin al árbol de una
  rama de slice movería la ventana de medición PAPER sin autorización.
- **No** se relaja el gate ni se le añade una excepción por rama.
- La deuda de `window:freeze` se resuelve por **revisión propia, con su propia autorización**, decidiendo
  qué árbol debe comparar el gate cuando el run no se dispara sobre un tag y qué significa ahí «congelado».

---

## 6. Decisiones conservadas

1. **Conservar `bcdc4584`** como commit de referencia del slice.
2. **No modificar** `main`, `origin/main` ni los dos commits documentales locales (`6032aa74`, `ae6410bf`).
3. **No crear** tags ni Releases.
4. **No re-anclar** el pin PAPER dentro de este trabajo.
5. **Registrar `TREE_MOVED`** como bloqueo independiente, con su propia revisión y autorización.

Corolario: el slice está suficientemente validado para considerarlo **cerrado en su alcance** y **no
necesita un commit correctivo** para compensar el fallo del freeze.

---

## 7. Estado AUTO/PAPER

Sin cambios: **AUTO OFF**, PAPER **virtual e inconcluso**. Este acta no aporta nada nuevo sobre
rentabilidad, comportamiento longitudinal de PAPER ni autorización para operar con dinero real, y no
altera el estado de ninguno de los dos modos.

---

## 8. Declaración del árbol de trabajo

Estado del checkout al redactar este acta (`git status --porcelain`, 59 entradas):

| Clase | Recuento |
| --- | --- |
| Modificados (rastreados) | 49 |
| Borrados (rastreados) | 1 (`apps/web/src/features/trading/use-instrument-daily-opinions.test.ts`) |
| Sin seguimiento | 9 |

**Ninguna de esas rutas pertenece a las 18 del slice.** El árbol contiene trabajo de otra fase —entre
otros `frontend-ci.yml`, `daily_opinion_service.py`, paneles de operativa y
`packages/shared/src/instrument-daily-opinion.ts`— y también el informe
`docs/engineering/auditoria-integracion-fase4-2026-11-11.md`, que pertenece a su propio flujo.

Por eso este acta **no** se commitea y se deja como fichero sin seguimiento: un `git add -A` arrastraría
ese trabajo ajeno. Este documento **no** lo incorpora, **no** lo evalúa y **no** lo da por bueno.

---

## Anexo — Cómo reproducir la lectura sin tocar nada

```bash
git show --numstat bcdc4584                     # 18 rutas, +1291/-201
git diff --stat main...HEAD                     # solo esas 18
git rev-list --left-right --count main...origin/main   # 2  0
git tag --points-at bcdc4584                    # (vacío)
node scripts/window-pin.mjs --check             # exit 1 · TREE_MOVED
gh run view 43169810570 --json jobs             # 12 success · 2 failure · 1 skipped
```

Ninguno de estos comandos escribe en el repositorio.
