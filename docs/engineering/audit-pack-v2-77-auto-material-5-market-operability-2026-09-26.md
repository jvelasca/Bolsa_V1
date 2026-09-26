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
- **CI del tag**: se citará en el commit de sello de `v2.77-beta` (el workflow de tag solo corre al
  empujar el tag).

## 10. Veredicto esperado

`APROBADO CON OBSERVACIONES` si el instrumento (clasificación por familia, `no_signal` fail-closed,
CAPABLE ≠ ACTIVE, mutaciones mordiendo y restaurando) se sostiene y las declaraciones de lo **no**
hecho se leen como tales. Lo que **no** puede afirmarse: que `P3-2`/`P3-3` estén cerradas, que el
gobernador conservador «sea el problema» (el instrumento **mide**, no concluye) ni que exista
material de mercado diverso — **no hubo ventana**.
