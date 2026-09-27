# Audit-pack — `v2.81-beta` / `AUTO-MATERIAL-9`: REAL WINDOW EXECUTION (informe de ventana)

> **Objeto:** tag anotado `v2.81-beta` · **Versión:** `2.06.0-beta` (**bump** `2.05.0-beta → 2.06.0-beta`) ·
> **Base (diff):** `v2.80-beta` · **Alembic head:** `046_fill_reference_mid` (**SIN migración**) ·
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`). **AsOf:** 2026-09-27.

## 1. Qué tiene que comprobar el auditor (por este orden)

1. **Identidad del objeto.** `package.json` = `2.06.0-beta`; tag `v2.81-beta` **anotado** apuntando al
   commit del sello; árbol **intacto** antes y después de la matriz (`git status --porcelain` vacío).
2. **Compuertas reproducidas** (medidas, no heredadas):
   - `ruff check packages/py apps/api-python --config pyproject.toml` → `All checks passed!`
   - `lint-imports --config packages/py/.importlinter` → `Contracts: 4 kept, 0 broken`
   - `mypy … --follow-imports=silent` → `Success: no issues found in 506 source files`
   - `alembic heads` → `046_fill_reference_mid (head)`
   - `pytest packages/py/application/tests/test_operability_window.py -q` → **23 passed** (`13 → 23`)
   - `pytest packages/py/application/tests/test_market_operability.py -q` → **58 passed** (sin cambios)
   - `python apps/api-python/scripts/v2_44_mutation_audit.py` → **230/230**, restauración byte a byte.
3. **Funnel honesto.** `build_operability_funnel(row)` sin `--forward` ⇒ `universe`/`marketData`/
   `regimeAllowed`/`orders` con `count is None` y `measured is False`; `signals`→`reservation` son la
   aritmética declarada del censo; un día **no medido** deja **todos** los escalones durables en `None`
   (no en `0`). Con `--forward`, `universe=watchSize`, `marketData` = live+close, `regimeAllowed=
   symbols_operable`, `orders=turnTotals.orders`.
4. **`unresolved_age`.** Sólo las propuestas `approved` se cuentan; la referencia es el **último instante
   durable del día**; los cubos son `lt1m`/`1to5m`/`5to20m`/`gt20m`/`unknown`; sin timestamps ⇒
   `measured=false` y cubos `None`; `resolutionJoined=false` está declarado.
5. **Informe HTML.** `render_window_html` es determinista, **escapa** todo texto (`&lt;b&gt;…`), publica el
   veredicto del gate (`GATE: READY`/`INCONCLUSIVE`) y la `ALERTA CONTRATO: other>0` cuando procede; sin
   recursos externos.
6. **Capturador read-only.** `v2_80_market_window.py` ganó `--forward` y `--html`; su escritura sigue
   limitada a `operability_runs/` (journal propio + informe); **no** escribe en el journal durable ni en
   `evidence_runs/`/`evidence_validations/`; `exit 2` sin días legibles.
7. **Registro en CI.** `test_operability_window.py` sigue **explícito** en `python-ci.yml` (job `quality`)
   y en `release-tag-ci.yml` (job `python`).
8. **Freeze / reparto / migración.** `git diff v2.80-beta..v2.81-beta` **no** toca
   `auto_simulation_worker.py`, `portfolio_decision_engine.py`, `opportunity_ranker.py`,
   `market_regime_gate.py`, `paper_material_readiness.py` ni `auto_reason_codes.py`; `TOP_N=5`; umbrales
   `32/3/8/4/2`; `auto15-v1`/`auto18-v1`; head `046_fill_reference_mid`.
9. **Mutaciones `M226`–`M230`** muerden (rojo en el test citado) y restauran **byte a byte**; matriz
   **230/230**.
10. **CI del tag** `v2.81-beta` verde en la primera pasada, con los jobs PG intactos.

## 2. Estado declarado de los hallazgos previos

- **`H-1`/`H-2`/`H-3`**: **CERRADOS** en `v2.79`.
- **`H-4` (LOW)**: **ABIERTO**; `otherCount`/`contractViolation`/`reasonCatalogCoverage` (v2.80) y el funnel
  (v2.81) lo hacen **visible**; su cierre formal es posterior a la primera ventana real.
- **`P3-2`/`P3-3`**: **ABIERTAS** (ventana ≥4 días = operación del propietario). Esta fase **prepara el
  instrumento** (funnel + HTML); **no** certifica.
- **`P3-5`** y **`OBS-5`**: siguen declaradas.

## 3. Límites de lo que el auditor podrá reproducir

- **Sin PostgreSQL**, los jobs PG se verifican **por su resultado en CI**, no en local.
- **Sin material PAPER real** (`operability_runs/` está gitignoreado), el funnel y la tabla de la ventana
  se re-derivan con **fixtures**; **no puede afirmarse** que `P3-2`/`P3-3` estén cerradas ni que exista
  diversidad de mercado: **no hubo ventana**.
- Sin `--forward`, los escalones superiores del funnel se leen `None`: es correcto (declarado), no un
  defecto; el auditor debe aportar evidencia real para verlos medidos.

## 4. Evidencia cruda

- [`evidencia-matriz-mutaciones-v2.81-230-2026-09-27.txt`](./evidencia-matriz-mutaciones-v2.81-230-2026-09-27.txt)
  — matriz completa **230/230** con `M226`–`M230` mordiendo y restauración byte a byte.
- `evidencia-ci-tag-v2.81-2026-09-27.txt` — CI del tag `v2.81-beta` (commit POST-TAG).
