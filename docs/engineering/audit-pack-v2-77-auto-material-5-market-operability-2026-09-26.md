# Audit-pack — `v2.77-beta` (`AUTO-MATERIAL-5`: MARKET OPERABILITY)

> **AsOf:** 2026-09-26 · **Versión:** `2.02.0-beta` · **Base (diff):** `v2.76-beta`
> (`2.01.0-beta`) · **Alembic head:** `046_fill_reference_mid` (**SIN migración**)
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`).
> **Regla de lectura:** esta fase **no** decide nada. Acredita un **instrumento de medición** que
> convierte el JSON del forward PAPER en una **serie diaria** y reparte cada veto en su CAUSA, más
> la nomenclatura `pairCapable` vs `pairActive`. **No** acredita cierre estadístico: la ventana de
> ≥4 días es operación del propietario y sigue **pendiente**.

## 1. Alcance del diff

| Tipo | Fichero |
|---|---|
| **Puro nuevo** | `packages/py/application/src/bolsa_application/market_operability.py` |
| **Puros nuevos (tests)** | `packages/py/application/tests/test_market_operability.py` (**25**) |
| **I/O nuevo** | `apps/api-python/scripts/v2_77_market_operability.py` |
| **Aditivo** | `apps/api-python/scripts/v2_76_forward_market_material.py` (`pairCapable`/`pairActive`; `pairAvailable` como alias) |
| **Sonda** | `apps/api-python/scripts/v2_44_mutation_audit.py` (**M206**–**M210**, 205 → 210) |
| **CI** | `.github/workflows/python-ci.yml` (job `quality`), `.github/workflows/release-tag-ci.yml` (job `python`) |
| **Docs/versión** | `package.json` (`2.01.0-beta` → `2.02.0-beta`), `CHANGELOG.md`, `PROJECT_STATE.md`, `engineering-index`, `deuda-p3`, docs `*-v2-77-*`, evidencia cruda |
| **Ignorado** | `.gitignore` (`/operability_runs/`, artefacto generado) |

**No** se toca: `auto_simulation_worker.py`, `paper_material_readiness.py`, `auto_adaptive.py`,
`aggregate_trial_regime`, `TOP_N`, `DATA_GATE_POLICY_VERSION`, `AUTO_ENGINE_SIM_V2_*`,
`evidence_runs/`, `evidence_validations/`, `governor.json`, la UI.

### 1.b Rango del diff tag → tag (**declarado al auditor**)

El diff `v2.76-beta..v2.77-beta` tiene **4 commits**, y **dos NO son de esta fase**: son posteriores
al tag `v2.76-beta` y los introduce la cita de su CI.

| Commit | Fase | Qué es |
|---|---|---|
| `05b5fa85` | **`v2.76` (post-tag)** | `fix(v2.76)`: registra sus 2 puros en `release-tag-ci.yml` (hueco declarado en su §10) |
| `40d3d9dc` | **`v2.76` (post-tag)** | `docs(v2.76)`: cita su CI y declara el hueco de registro |
| `233ef8cc` | `v2.77` | `feat(v2.77)`: implementación |
| `ade1df58` | `v2.77` | `docs(v2.77)`: docs + evidencia + bump (**commit del tag**) |

Consecuencias que el auditor debe tener presentes:

- Las **dos entradas `M`** de docs de `v2.76` en el diff (`arranque-auditor-v2-76-…`,
  `audit-pack-v2-76-…`) vienen de `40d3d9dc`, **no** de esta fase.
- El cambio de `.github/workflows/release-tag-ci.yml` **combina** `05b5fa85` (v2.76) con
  `233ef8cc` (v2.77): el registro de los puros de `v2.77` se **añade encima** de aquel arreglo.
- El hueco de `v2.76` queda **ejercitado y cerrado** por el CI del tag de esta fase (§9).

## 2. El puro, pieza a pieza (qué se puede romper y qué lo muerde)

- **`classify_veto_reasons`** reparte por familia. Las siete familias **siempre** salen (aunque
  vacías) para que la tabla sea estable. Un código sin familia → `other`, **contado**, nunca
  descartado (`M207`).
- **`VETO_BUCKET_BY_REASON`** es la tabla declarada. `TOP_N_EXCLUDED` se **importa** de su dueño
  (`opportunity_ranker`) — el literal no se duplica; el test
  `test_the_top_n_literal_is_read_from_its_owner` lo fija.
- **Dueño único cubierto**: `test_every_decision_reason_code_has_a_declared_bucket` recorre
  `typing.get_args(DecisionReasonCode)` (los literales del dueño) y exige familia declarada para
  **todos** salvo `approved`. Si el motor añade un código y no se clasifica, el test cae.
- **`symbols_operable`** mide cuántos símbolos admiten LONG por sí mismos (`4/8` en el smoke real);
  sin `bySymbol` agrega `counts`; sin nada devuelve `None` (nunca `0` inventado).
- **`operability_state`** aísla la regla fail-closed: `no_signal` **solo** si
  `proposals == 0 and vetoes == 0` (`M209`). Un día con vetos **no** puede leerse «sin señal».
- **`pair_capable` / `pair_active`** son estados **distintos** (`M208`). El smoke real da
  `pairCapable=true`, `pairActive=false`: la arquitectura está lista, la segunda versión no opera.
- **`veto_counted`** suma **todas** las familias (`M210`), para que la contabilidad cuadre con los
  vetos del turno (en el smoke: `40 + 24 = 64`).

## 3. Nomenclatura (cambio aditivo, sin romper lo previo)

`apps/api-python/scripts/v2_76_forward_market_material.py` publica ahora:

- `pairCapable` = `len(watch) >= 2` (hay universo para repartir y enrutar A/B).
- `pairActive` = `secondary_loaded and version_b and watch_b` (las dos versiones **operan**).
- `pairAvailable` = **alias** de `pairActive` (compatibilidad con audit-packs previos).

`market_operability.pair_active` acepta `pairActive` y, si falta, el alias `pairAvailable`, y si
tampoco está, deriva de `secondaryActive` + `versionB` + `watchB`.

## 4. La sonda I/O

`v2_77_market_operability.py` **lee** JSON del runner (o el journal acumulado), **traduce** a filas
con el puro y **acumula** un JSONL no versionado. Propiedades:

- **Sin DB, sin material, sin gate**: no importa `asyncio`/SQLAlchemy ni toca `evidence_runs/`.
- **Día declarado con procedencia** (`evidence.day`/`asOf`/`date`, `filename`, `mtime`).
- **Idempotente por identidad** (`day`, `account`, `versionA`, `watchSize`): re-ejecutar el mismo
  forward no duplica filas.
- `exit 2` si no hay registros (se declara por stderr); `--no-write` para dry-run.

## 5. Mutaciones (medidas)

`M206`–`M210`, matriz **210/210**, restauración **byte a byte** y árbol **intacto** (evidencia
`evidencia-matriz-mutaciones-v2.77-210-2026-09-26.txt`):

| Mutación | Qué rompe | Qué test muerde |
|---|---|---|
| `M206` | todo el veto bajo `regime` | `test_classify_separates_…`, `test_record_from_the_real_forward_smoke`, `test_render_…` |
| `M207` | código desconocido descartado | `test_unknown_reason_is_counted_in_other_and_never_dropped`, `test_veto_counted_…` |
| `M208` | `pairCapable` como `pairActive` | `test_pair_capable_reads_the_explicit_flag_without_confusing_it_with_active` |
| `M209` | `no_signal` con vetos | `test_state_vetoed_when_there_were_vetoes_even_without_proposals`, `test_record_…` |
| `M210` | contabilidad que pierde `other` | `test_veto_counted_sums_all_families_including_other`, `test_unknown_reason_…` |

## 6. Compuertas (medidas en local)

- `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml` →
  **All checks passed!** (exit 0).
- `uv run --no-sync lint-imports --config packages/py/.importlinter` → **Contracts: 4 kept,
  0 broken** (636 ficheros, 3440 dependencias).
- `uv run --no-sync mypy packages/py/domain/src packages/py/market/src
  packages/py/infrastructure/src packages/py/application/src apps/api-python/src
  --follow-imports=silent` (la compuerta **exacta** del job `quality`) →
  **Success: no issues found in 505 source files**.
- `uv run --no-sync pytest packages/py/application/tests/test_market_operability.py -q` →
  **25 passed**.
- `uv run --no-sync pytest packages/py/analytics -q` → **1265 passed**;
  `packages/py/application` → **2010 passed / 5 errors**, donde los 5 errores son los mismos
  tests **DB-gated** preexistentes (`test_research_observatory.py`, `test_research_trials_db.py`)
  que fallan **solo** porque se forzó `DATABASE_URL=invalid://nope` para correr offline
  (`NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:invalid`), **no** por el diff; esos
  ficheros **no** están en la lista del job `quality`.
- `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py` → **210/210**.

## 7. Evidencia cruda

- `evidencia-operabilidad-v2.77-2026-09-26.txt`: la tabla diaria calculada desde el JSON **real** del
  forward smoke de `v2.76`.

  | Día | Régimen | Long | SimbOper | Decid | Prop | Veto | Fills | Ciclos | Par |
  |---|---|---|---|---|---|---|---|---|---|
  | 2026-09-26 | `BEAR_TREND` | `NO` | `4/8` | 64 | 0 | 64 | 0 | 0 | `CAPAZ` |

  Vetos: `regime=40`, `top_n=24` (`regime_invalid=40`, `top_n_excluded=24`). `NO SIGNAL` **no
  aplicable** (hubo vetos).
- `evidencia-matriz-mutaciones-v2.77-210-2026-09-26.txt`: matriz completa **210/210**.
- `evidencia-ci-tag-v2.77-2026-09-26.txt`: CI del tag medido (`Release tag CI` `36279417767` GREEN a
  la primera; `python` del tag **`2948/37`**; 10/10 runs del commit `ade1df58`), el rango declarado y
  el cierre del hueco de registro de `v2.76`.

## 8. Declarado, NO hecho

- La **ventana de ≥4 días** de calendario **no se ejecutó**: los cubos salen de
  `created_at = datetime.now(UTC)` y es operación de tiempo real del propietario. `P3-2` y `P3-3`
  siguen **ABIERTAS**; `AUTO-22`/`AUTO-23` no se corren sin material (un bundle sobre vacío no
  acredita nada).
- **Prerrequisito de `pairActive`**: sin una estrategia **ACTIVE** + `EdgeReport` promovida, el par
  queda `CAPABLE` pero no `ACTIVE`. El instrumento lo declara, no lo simula.
- **Deuda PG**: `test_auto_v70_auto23_evidence_validation.py` (`assert 17 == 26`) es **pre-existente**
  y ajena al diff; se salta en CI sin Postgres. Se anota como pendiente **antes** de declarar AUTO
  estadísticamente certificado.
- **Vivo `market_live`**: depende del bridge XTB (servicio externo); el instrumento solo declara la
  procedencia (`live`/`close`/`missing`).

## 9. CI

- `test_market_operability.py` entra **explícito** en el job `quality` de `python-ci.yml` **y** en el
  job `python` de `release-tag-ci.yml` (corrige de raíz la clase de hueco que `v2.76` declaró en su
  §10: un puro nuevo registrado solo en un workflow).
- La sonda `v2_77_market_operability.py` **no** se invoca desde ningún workflow (es I/O de
  `scripts/`): su camino real queda **declarado como operación**, no como test de CI.

### 9.a CI del tag `v2.77-beta` (medido)

**Objeto sellado:** tag **anotado** `v2.77-beta` → objeto `22da1bb0` → commit **`ade1df58`**
(versión `2.02.0-beta`). Evidencia cruda: `evidencia-ci-tag-v2.77-2026-09-26.txt`.

`Release tag CI` run **`36279417767`** → **GREEN en la primera pasada** (`attempt: 1`, **9m6s**),
**10 jobs en `success` + `certify` en `success`**; `playwright (integrated E2E, opt-in)`
**skipped por diseño**.

| Job del tag | Medición |
|---|---|
| `python` (ruff/imports/mypy/pytest offline) | **`2948 passed / 37 skipped`**; `ruff` `All checks passed!`; `Contracts: 4 kept, 0 broken`; `mypy` `0 issues (505 files)` |
| `lifecycle-pg` | `165 passed` + gates fail-if-skipped |
| `decision-spine` | `604 passed` |
| `a7-gate` (chaos live_a7, real-PG) | `7 passed` |
| `shared` | `786 passed` (95 ficheros) |
| `frontend` | `1339 passed` (232 ficheros) |
| `playwright (mock E2E)` | `76 passed` |
| `security (gitleaks)`, `dr-verify`, `certify` | `success` |

Sobre el mismo commit y tag: `Python CI` `36279417814`, `Frontend CI` `36279417738`,
`Optimize lab` `36279417797` y `Fase 2 scientific` `36279417742` en **success**. En `main`:
`Python CI` `36279416502` (job `quality` **`2937 passed / 40 skipped`** = `2912 + 25`),
`Frontend CI` `36279416554`, `Optimize lab` `36279416392`, `Fase 2 scientific` `36279416393` y
`Gitleaks` `36279416453`, en **success** (**10/10** runs del commit sellado).

### 9.b Hueco de `v2.76` ejercitado y cerrado

El job `python` del **tag** pasa de **`2898 passed / 37 skipped`** (valor de `v2.76`) a
**`2948 passed / 37 skipped`** = `2898` + **25** (los puros de `v2.76`, cuyo registro en
`release-tag-ci.yml` se corrigió en `05b5fa85` **después** de sellar) + **25** (los puros nuevos de
`v2.77`). Es decir: la corrección de `v2.76` **queda probada por el CI** sin haber movido el tag
`v2.76-beta`, y el registro de `v2.77` **no repite** el hueco. Los `37 skipped` del tag son los
**mismos** que en `v2.75`/`v2.76` (ningún skip nuevo de esta fase).

### 9.c Sello y cita del CI

El tag apunta a `ade1df58`; esta sección y la evidencia del CI se añaden **después**, en un commit
de docs **posterior al tag** (mismo patrón que `v2.74`/`v2.75`/`v2.76`): el **código** auditado es
el del tag y el diff tag→HEAD es **solo docs**.

## 10. Veredicto esperado

`APROBADO CON OBSERVACIONES` si el instrumento (clasificación por familia, `no_signal` fail-closed,
CAPABLE ≠ ACTIVE, mutaciones mordiendo y restaurando) se sostiene y las declaraciones de lo **no**
hecho se leen como tales. Lo que **no** puede afirmarse: que `P3-2`/`P3-3` estén cerradas, que el
gobernador conservador «sea el problema» (el instrumento **mide**, no concluye) ni que exista
material de mercado diverso — **no hubo ventana**.
