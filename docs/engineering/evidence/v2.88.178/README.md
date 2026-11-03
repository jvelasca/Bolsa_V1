# Evidencia `v2.88.178-beta` — **SELLO CORRECTOR**: la persistencia del workspace se certifica también en el CI del tag

## 1. Qué corrige

El tag **`v2.88.177-beta`** quedó **ROJO** en
[`Release tag CI` 41592978552](https://github.com/jvelasca/Bolsa_V1/actions/runs/41592978552). Un solo job
falló; los otros **once** fueron `success`.

| Job del tag `.177` | Resultado |
| --- | --- |
| `python (ruff/imports/mypy/pytest offline)` | **failure** — step `Pytest offline`: **5 failed, 5887 passed**, todos `psycopg.OperationalError: connection refused` en `127.0.0.1:5432` |
| `frontend (typecheck/lint/test/build + contract:check)` | success |
| `shared (build/typecheck/test)` | success |
| `replay-repro` | success |
| `a7-gate` · `security` · `dr-verify` · `decision-spine` | success |
| `lifecycle-pg` · `playwright` ×4 | success / `playwright (integrated E2E, opt-in)` `skipped` |

### 1.1 Causa raíz

`d3236b5c` añadió `apps/api-python/tests/test_workspace_persistence.py` y el `--ignore` correspondiente **solo**
a `python-ci.yml`. `release-tag-ci.yml` mantiene su **propia** lista de `pytest` offline, así que el fichero
nuevo se recolectó allí **sin servicio PostgreSQL** y falló por conexión. Es exactamente el agujero que
`OBS-19` describe: la selección de tests está escrita a mano **por workflow**, y un fichero nuevo solo queda
cubierto donde alguien lo cablea.

No es un defecto de producto: `5887` tests pasaron en ese mismo job y el fichero de persistencia **pasa** en
`lifecycle-pg` de `python-ci.yml` (y pasó en su día sobre `d3236b5c`). Lo que faltaba era su certificación
**en el tag**.

## 2. Qué cambia (solo CI)

`.github/workflows/release-tag-ci.yml`:

1. `--ignore=apps/api-python/tests/test_workspace_persistence.py` en el bloque `Pytest offline`, con el motivo
   escrito **fuera** del `run: >`. Dentro del plegado, un `#` habría comentado el resto de la lista de
   `--ignore` (hazard documentado en `V2.40.2`); por eso el comentario va en el bloque de cabecera del step.
2. Paso **`Pytest persistencia del workspace PG`** en el job `lifecycle-pg` del tag, justo después de
   `Alembic upgrade head`. El fichero deja de estar solo «ignorado»: queda **ejecutado** en el tag.

Nada más cambia. El árbol de producto es idéntico al de `.177` salvo el bump.

## 3. Verificación medida

| Comprobación | Comando | Salida |
| --- | --- | --- |
| Censo de selección de tests | `pytest apps/api-python/tests/test_ci_test_selection_census.py` | **5 passed** (el fichero sigue contando como ejecutado, ahora también en el CI del tag) |
| YAML del workflow | `yaml.safe_load` + inspección del step | parsea; `run` offline **sin** `#`; `lifecycle-pg` tiene el paso nuevo con `uv run pytest apps/api-python/tests/test_workspace_persistence.py -q --tb=short` |
| Guardián del bump | `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **2 passed** |
| Pin PAPER | `node scripts/window-pin.mjs --check` · `pnpm window:test` | **`freeze OK`** · **50 / 50** |
| Persistencia (heredada de `.177`) | `pytest test_workspace_persistence.py test_batch_caps.py` | **14 passed** |
| Suites web / shared (heredadas) | `pnpm --filter @bolsa/web test` · `@bolsa/shared test` | **364 / 2728** · **101 / 883** |

Cadena del pin en este sello:

| Commit | `appsHash` | `packagesHash` | `window:freeze` |
| --- | --- | --- | --- |
| `5da78712` (fix de CI) | `246edde7…` | `0f8efb9b…` | `TREE_MOVED` (previsto: el pin apuntaba a `.177`) |
| `d33d08ef` (bump) | `6a4f3df0…` | `0f8efb9b…` | **`freeze OK`** tras el re-anclaje |
| `bf4f5087` (pin) | `6a4f3df0…` | `0f8efb9b…` | **`freeze OK`** |

`packages/py` no se mueve en todo el sello: solo `apps` (los `meta.bump`) y la raíz.

## 4. Qué NO cambia respecto de `.177`

- **Producto**: los seis defectos P0-1, P0-2, P1-3, P1-4, P1-7, P2-5 y P2-6 y la causa raíz de la membresía
  `newest-wins` son los de [`evidence/v2.88.177`](../v2.88.177/README.md), sin tocar.
- **Contrato HTTP**: sin cambios (`contract:check` **OK**).
- **Motor y decisión**: `Δ motor = 0`, `Δ decisión = 0`, sin migración (head
  `062_sync_settings_check_backfill`).
- **Revisión independiente**: la de `.177`
  ([`revision-independiente-workspace-2026-11-02.md`](../../revision-independiente-workspace-2026-11-02.md))
  sigue siendo válida: el diff de este sello **no** toca `packages/py/**` ni `apps/web/**`.
- **Límites**: `L-RIW-1`…`L-RIW-4` se heredan tal cual.

## 5. Publicación

| Paso | Estado |
| --- | --- |
| `v2.88.177-beta` | **publicado y ROJO** (run `41592978552`); se deja como registro, **sin** GitHub Release |
| `5da78712` fix del CI del tag | hecho |
| `d33d08ef` bump `2.11.178-beta` | hecho |
| `bf4f5087` re-anclaje del pin | hecho |
| Tag anotado `v2.88.178-beta` | sobre el commit de este documento |
| `Release tag CI` del tag | **§5.1** (POST-TAG) |
| GitHub Release | **§5.1** (POST-TAG) |
| Despliegue en `:8000` | **no realizado** y fuera de este sello |

### 5.1 POST-TAG

Pendiente de anotar tras el run del tag `v2.88.178-beta`.

## 6. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | El job offline del tag ya no recolecta el fichero de persistencia | `Pytest offline` con `--ignore` (inspeccionable en el YAML y en el `run`) |
| 2 | El fichero se certifica **en el tag** | step `Pytest persistencia del workspace PG` del job `lifecycle-pg` del run del tag |
| 3 | El censo no se rompe con el cambio | `test_ci_test_selection_census.py` (**5 passed**) |
| 4 | Nada de producto cambia | el diff del sello solo toca `.github/workflows`, `package.json`, `CHANGELOG.md`, `apps/api-python/scripts/*` y `scripts/lib/window-forward.mjs` |
| 5 | El pin casa con el árbol | `freeze OK`; rojo en el step `Window freeze gate` del tag si no |

## 7. Bitácora

| Paso | Hecho |
| --- | --- |
| 1 | Tag `.177` → run `41592978552` **ROJO** en `Pytest offline` (5 `Connection refused`). |
| 2 | Diagnóstico: el `--ignore` se añadió a `python-ci.yml` pero no al workflow del tag. |
| 3 | `5da78712`: `--ignore` + paso dedicado en `lifecycle-pg` del tag; censo **5 passed**. |
| 4 | `d33d08ef`: bump `2.11.178-beta`; bump guard `2 passed`; pin re-anclado. |
| 5 | `bf4f5087`: commit del pin; `freeze OK`, `window:test` 50/50. |
| 6 | Este documento, tag `v2.88.178-beta` y su `Release tag CI` (**§5.1**). |
