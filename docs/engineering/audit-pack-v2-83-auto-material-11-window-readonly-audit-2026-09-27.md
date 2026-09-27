# Audit-pack — `v2.83-beta` / `AUTO-MATERIAL-11`: AUDITORÍA READ-ONLY de la ventana PAPER

> **Objeto:** tag anotado `v2.83-beta` · **Versión:** `2.08.0-beta` (**bump** `2.07.0-beta → 2.08.0-beta`) ·
> **Base (diff):** `v2.82-beta` · **Alembic head:** `046_fill_reference_mid` (**SIN migración**) ·
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`). **AsOf:** 2026-09-27.

## 0. Naturaleza declarada del objeto: fase de INSTRUMENTO READ-ONLY

`v2.83` **no** toca el motor, el gobernador (`aggregate_trial_regime`), `TOP_N`, los umbrales, la
allocation, los pesos A/B ni una migración. Entrega **código nuevo que sólo LEE**: un módulo **puro**
(`operability_audit.py`, sin I/O ni reloj) y un **CLI read-only** (`v2_83_window_audit.py`) que **agregan**
un `operability_runs/` ya producido y publican la fila **`TOTAL`** y las **tasas de operabilidad** que el
instrumento de `v2.81` no tenía. **El único cambio no-doc fuera del instrumento nuevo es `package.json`.**

**No fabrica evidencia:** no se inventa un escalón (`None`/`n/d` ≠ `0`), no se recalcula el gate, no se
baja ningún umbral y no se escribe en `evidence_runs/`/`evidence_validations/` ni en el journal durable.

## 1. Qué tiene que comprobar el auditor (por este orden)

1. **Identidad del objeto.** `package.json` = `2.08.0-beta`; tag `v2.83-beta` **anotado** apuntando al
   commit del sello; árbol **intacto** antes y después de cualquier sonda (`git status --porcelain` vacío).
2. **Diff acotado.** `git diff v2.82-beta..v2.83-beta --stat` muestra **sólo**:
   `packages/py/application/src/bolsa_application/operability_audit.py` (**nuevo**),
   `apps/api-python/scripts/v2_83_window_audit.py` (**nuevo**),
   `packages/py/application/tests/test_operability_audit.py` (**nuevo**), los dos workflows
   (`python-ci.yml`/`release-tag-ci.yml`, **una línea** de registro cada uno), `package.json`, `CHANGELOG.md`
   y `docs/engineering/*`. **Ningún** fichero de motor, gobernador, umbrales o migración.
3. **Compuertas reproducidas** (medidas, no heredadas):
   - `ruff check packages/py apps/api-python --config pyproject.toml` → `All checks passed!`
   - `lint-imports --config packages/py/.importlinter` → `Contracts: 4 kept, 0 broken`
   - `mypy … --follow-imports=silent` → `Success: no issues found in 507 source files` (**506 → 507**)
   - `alembic -c packages/py/infrastructure/alembic.ini heads` → `046_fill_reference_mid (head)`
   - `pytest packages/py/application/tests/test_operability_audit.py -q` → **16 passed**
   - `pytest packages/py/application/tests -q` → **2087 passed** (`2071 + 16`)
4. **Freeze / reparto / migración.** El diff **no** toca `auto_simulation_worker.py`,
   `portfolio_decision_engine.py`, `opportunity_ranker.py`, `market_regime_gate.py`,
   `paper_material_readiness.py` ni `auto_reason_codes.py`; `TOP_N=5`; umbrales `32/3/8/4/2`;
   `auto15-v1`/`auto18-v1`; head `046_fill_reference_mid`.
5. **Semántica dura del instrumento nuevo** (el núcleo que hay que intentar romper):
   - `window_totals` suma **sólo** días medidos y publica `coverage[field].partial`; un hueco **no** se
     suma como `0`. La clave `measured` ausente se lee como **medido** (misma convención que
     `operability_state`, sin abrir una segunda).
   - `window_rates` deriva **cada** tasa del funnel y devuelve `rate=None` cuando no hay días medidos o el
     denominador es `0` — **nunca** `0.0`; cada tasa viaja con `numerator`/`denominator`/`coveredDays`/`source`.
   - `render_window_audit` es **determinista** (sin reloj) y declara `n/d` en los huecos.
   - `enrich_rows_with_evidence` rellena **sólo** los huecos declarados y **no** sobrescribe lo medido.
6. **Mutaciones.** No hay mutaciones nuevas (no se toca lógica de motor); la matriz sigue en **230/230** y
   `M226`–`M230` muerden y restauran **byte a byte** si se re-ejecuta.
7. **Registro en CI.** `test_operability_audit.py` está **explícito** en el job `quality` de
   `python-ci.yml` **y** en el job `python` de `release-tag-ci.yml` (patrón que el hueco de `v2.76` obligó
   a formalizar; `v2.77`–`v2.82` lo siguen).
8. **CI del tag** `v2.83-beta` **acreditado**: `Release tag CI` `36329460515` **GREEN** en la primera
   pasada (`attempt 1`, 10 jobs + `certify`; `playwright (integrated)` skipped por diseño). La cita vive en
   el commit **POST-TAG** `80b18061` (ver §4 y `evidencia-ci-tag-v2.83-2026-09-27.txt`); la instancia
   **dentro** del tag es el **placeholder pre-tag** (patrón OBS-3/OBS-4), no un CI no acreditado.

## 2. Verificación pre-D1 declarada (no forzada)

| Brecha del runbook §2 | Resultado 2026-09-27 |
| --- | --- |
| Preflight de régimen | **exit 2** · `{range:8, trend_down:9, trend_up:3}` ⇒ `BEAR_TREND` ⇒ **LONG VETADAS** |
| Barras del loader | **20/20** servidas ⇒ el scheduler de barras responde hoy |
| `pairActive=true` (estrategia B **ACTIVE** + `EdgeReport`) | **NO VERIFICABLE**: `PAPER_D_ACCOUNT_ID` está **comentado** en `.env` ⇒ sin cuenta fija |
| Cuenta fija desde D2 | **NO VERIFICABLE** (misma causa) |
| Glob `operability_runs/forward-market-*.json` | aún **no** existe bundle real; el patrón del runbook excluye fixtures |

**Lectura honesta:** el preflight de hoy **veta** la entrada LONG por régimen (idéntico al hallazgo
operativo de `v2.76`), y las brechas 1 y 2 (par A/B y cuenta fija) siguen **ABIERTAS**: **no** se declaran
resueltas por documentación.

## 3. Estado declarado de los hallazgos previos

- **`H-1`/`H-2`/`H-3`**: **CERRADOS** en `v2.79`.
- **`H-4` (LOW)**: **ABIERTO**; `v2.83` lo **hace visible** en la auditoría (`warnings: reason_contract`)
  pero **no** lo cierra.
- **`P3-2`/`P3-3`**: **ABIERTAS** (ventana ≥4 días = operación del propietario). `v2.83` **no** certifica.
- **`P3-5`** y **`OBS-5`**: siguen declaradas.

## 4. Evidencia cruda

- `evidencia-ci-tag-v2.83-2026-09-27.txt` — CI del tag `v2.83-beta`, **acreditado** en el commit
  **POST-TAG** `80b18061` (`main`): tag anotado `8cfe7f6f` → `0ebf6630`; `Release tag CI`
  `36329460515` **SUCCESS** (`attempt 1`); job `python` `3020/37`; `quality` (Python CI `36329460471`)
  `3009/40`; cuatro jobs PG en `success`. La instancia **dentro** del tag es el **placeholder pre-tag**.
- Matriz adversarial vigente: [`evidencia-matriz-mutaciones-v2.81-230-2026-09-27.txt`](./evidencia-matriz-mutaciones-v2.81-230-2026-09-27.txt)
  (re-ejecutada en local en esta fase: **230/230**, restauración **byte a byte**, árbol limpio).
- Consolidada de la fase: [`evidencia-auditoria-v2.83-2026-09-27.txt`](./evidencia-auditoria-v2.83-2026-09-27.txt).

## 5. Límites de lo que el auditor podrá reproducir

- **Sin material PAPER real** (`operability_runs/` está gitignoreado), la tabla/`TOTAL`/tasas se re-derivan
  con **fixtures**; `v2.83` **no** puede acreditar diversidad de mercado: **no hubo ventana**.
- **Sin PostgreSQL**, los jobs PG se verifican **por su resultado en CI**, no en local.
- Sin `--forward`, `orders`/`pairActive` se leen `n/d`: es correcto (declarado), no un defecto.
- La `fillRate` sólo existe cuando la evidencia del runner está disponible: sin ella, `n/d`.
