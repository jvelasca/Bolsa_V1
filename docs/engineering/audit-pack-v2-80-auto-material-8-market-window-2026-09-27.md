# Audit-pack — `v2.80-beta` / `AUTO-MATERIAL-8`: MARKET WINDOW

> **Objeto:** tag anotado `v2.80-beta` · **Versión:** `2.05.0-beta` (**bump** `2.04.0-beta → 2.05.0-beta`) ·
> **Base (diff):** `v2.79-beta` (`0314199c`, `2.04.0-beta`) · **Alembic head:** `046_fill_reference_mid`
> (**SIN migración**) · **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` /
> `auto15-v1` (`ALLOCATION = none`).
> **AsOf:** 2026-09-27.

## 1. Qué tiene que comprobar el auditor (por este orden)

1. **Identidad del objeto.** `package.json` = `2.05.0-beta`; tag `v2.80-beta` **anotado** apuntando al
   commit del sello; árbol **intacto** antes y después de la matriz (`git status --porcelain` vacío; tree
   id idéntico).
2. **Compuertas reproducidas** (medidas, no heredadas):
   - `ruff check packages/py apps/api-python --config pyproject.toml` → `All checks passed!`
   - `lint-imports --config packages/py/.importlinter` → `Contracts: 4 kept, 0 broken`
   - `mypy … --follow-imports=silent` → `Success: no issues found in 506 source files`
   - `alembic heads` → `046_fill_reference_mid (head)`
   - `pytest packages/py/application/tests/test_market_operability.py -q` → **58 passed** (`48 → 58`)
   - `pytest packages/py/application/tests/test_operability_window.py -q` → **13 passed** (nuevos)
   - `python apps/api-python/scripts/v2_44_mutation_audit.py` → **225/225**, restauración byte a byte.
3. **Auditoría 2 — `STATE_UNRESOLVED`.** `operability_state({"proposals":3,"vetoes":0,"fills":0,"closed":0})`
   → `unresolved`; con `vetoes>0` → `vetoed`; con fill/cierre → `operated`; ausencia sin cambios →
   `unknown`. El orden fail-closed (ausencia **primero**) se conserva.
4. **Auditoría 1 §20 — `other>0` es AVISO.** `build_operability_record` con un código desconocido ⇒
   `otherCount>0`, `contractViolation is True` (no excepción) y el render publica
   `ALERTA CONTRATO: other>0 …`; sin código desconocido ⇒ `contractViolation is False` y **no** hay línea.
5. **Auditoría 1 §21 — cobertura.** `DECLARED_REASON_CODES == frozenset(VETO_BUCKET_BY_REASON) |
   NON_VETO_REASON_CODES`; `reason_catalog_coverage` devuelve `declared`/`observed`/`unknown`; el día de
   reversión (`_AUDIT_REVERSAL_DAY`) tiene `observed == 4`, `unknown == 0`, `contractViolation is False`.
6. **Ventana — fila y linaje.** `build_window_row` publica `cycleIds`/`instruments`/`versions`/`account` y
   declara los huecos como `None` (`pairCapable`/`pairActive`/`priceSources`); `measured_r` es el **mismo**
   lector que el informe (sin regla paralela).
7. **Ventana — gate honesto.** `window_gate` cuenta **días distintos** (4 filas del mismo día **no**
   cumplen); `READY` sólo con ≥4 días **y** ≥2 episodios **y** ≥32 ciclos medibles; si no, `INCONCLUSIVE`.
8. **Capturador read-only.** `v2_80_market_window.py` **no** escribe en el journal durable ni en
   `evidence_runs/`/`evidence_validations/`; su único `open(…, "a")` es el journal propio de
   `operability_runs/` (gitignoreado); `exit 2` sin días legibles.
9. **Registro en CI.** `test_operability_window.py` aparece **explícito** en el job `quality` de
   `python-ci.yml` **y** en el job `python` de `release-tag-ci.yml`.
10. **Freeze / reparto / migración.** `git diff v2.79-beta..v2.80-beta` **no** toca
    `auto_simulation_worker.py`, `portfolio_decision_engine.py`, `opportunity_ranker.py`,
    `market_regime_gate.py`, `paper_material_readiness.py` ni `auto_reason_codes.py`; `TOP_N=5`; umbrales
    `32/3/8/4/2`; `auto15-v1`/`auto18-v1`; head `046_fill_reference_mid`.
11. **Mutaciones `M220`–`M225`** muerden (rojo en el test citado) y restauran **byte a byte**; matriz
    **225/225**.
12. **CI del tag** `v2.80-beta` verde en la primera pasada, con los jobs PG (`auto-v2-durable-pg`,
    `lifecycle-pg`, `paper-forward-pg`, `grammar-discovery-pg`) intactos.

## 2. Estado declarado de los hallazgos previos

- **`H-1`/`H-2`/`H-3`** (auditorías de `v2.78`): **CERRADOS** en `v2.79` (el auditor de `v2.79` los dio por
  sostenidos salvo el matiz de exhaustividad, `H-4`).
- **`H-4` (LOW)**: **ABIERTO**. El vocabulario de rechazo pre-ranqueo de `auto_v2_entry`
  (`signal_duplicate`, `signal_stale`, `signal_identity_missing`, `signal_superseded_by_candidate`,
  `signal_distinct_strategy_not_representable`) sigue sin familia declarada ⇒ cae en `other`. **No se
  cierra en esta fase** (fuera de alcance del plan): lo que sí cambia es que ahora es **visible** —
  `otherCount`/`contractViolation`/`reasonCatalogCoverage` lo **declaran** en vez de diluirlo.
- **`P3-2`/`P3-3`**: **ABIERTAS** (ventana ≥4 días = operación del propietario). Esta fase **prepara el
  instrumento**; **no** certifica.
- **`P3-5`** y **`OBS-5`**: siguen declaradas.

## 3. Límites de lo que el auditor podrá reproducir

- **Sin PostgreSQL**, los jobs PG se verifican **por su resultado en CI**, no en local.
- **Sin material PAPER real** (`operability_runs/` está gitignoreado), la tabla de la ventana se
  re-deriva con **fixtures**; **no puede afirmarse** que `P3-2`/`P3-3` estén cerradas ni que exista
  diversidad de mercado: **no hubo ventana**.
- El estado `unresolved` y el aviso `other>0` se prueban con fixtures deterministas; un journal real
  podría **no** exhibirlos si no ocurre el caso.

## 4. Evidencia cruda

- [`evidencia-matriz-mutaciones-v2.80-225-2026-09-27.txt`](./evidencia-matriz-mutaciones-v2.80-225-2026-09-27.txt)
  — matriz completa **225/225** con `M220`–`M225` mordiendo y restauración byte a byte.
- [`evidencia-ci-tag-v2.80-2026-09-27.txt`](./evidencia-ci-tag-v2.80-2026-09-27.txt) — CI del tag
  `v2.80-beta` (run, jobs, conteos) — **pendiente de la pasada de CI**.
