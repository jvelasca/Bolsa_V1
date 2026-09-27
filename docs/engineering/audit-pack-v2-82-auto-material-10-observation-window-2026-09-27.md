# Audit-pack — `v2.82-beta` / `AUTO-MATERIAL-10`: OBSERVATION WINDOW (fase operativa)

> **Objeto:** tag anotado `v2.82-beta` · **Versión:** `2.07.0-beta` (**bump** `2.06.0-beta → 2.07.0-beta`) ·
> **Base (diff):** `v2.81-beta` · **Alembic head:** `046_fill_reference_mid` (**SIN migración**) ·
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`). **AsOf:** 2026-09-27.

## 0. Naturaleza declarada del objeto: fase DOCS-ONLY

`v2.82` **no entrega código**. Es una fase **operativa**: formaliza con un marcador de fase
(`v2.82-beta`) el paso que la auditoría de `v2.81` dejó como operación del propietario (la **ventana ≥4
días**) y **no** toca el motor, el gobernador, `TOP_N`, los umbrales, la allocation, los pesos ni la
lógica A/B. **El único cambio no-doc es `package.json`.** Por eso este audit-pack es **declarativo**: el
auditor **no** encontrará un diff de comportamiento que reproducir; encontrará un diff de **documentos +
bump** y, sobre todo, la **evidencia operativa** que el propietario produzca.

## 1. Qué tiene que comprobar el auditor (por este orden)

1. **Identidad del objeto.** `package.json` = `2.07.0-beta`; tag `v2.82-beta` **anotado** apuntando al
   commit del sello; árbol **intacto** antes y después de cualquier sonda (`git status --porcelain` vacío).
2. **Diff docs-only.** `git diff v2.81-beta..v2.82-beta --stat` muestra **solo** `package.json` y
   `docs/engineering/*` (más `CHANGELOG.md`); **ningún** fichero de motor, instrumento, workflow o migración.
3. **Compuertas reproducidas** (medidas, no heredadas):
   - `ruff check packages/py apps/api-python --config pyproject.toml` → `All checks passed!`
   - `lint-imports --config packages/py/.importlinter` → `Contracts: 4 kept, 0 broken`
   - `mypy … --follow-imports=silent` → `Success: no issues found in 506 source files`
   - `alembic heads` → `046_fill_reference_mid (head)`
   - `pytest packages/py/application/tests/test_market_operability.py packages/py/application/tests/test_operability_window.py -q` → **81 passed** (58 + 23), **sin cambios** respecto a `v2.81`.
4. **Freeze / reparto / migración.** `git diff v2.81-beta..v2.82-beta` **no** toca
   `auto_simulation_worker.py`, `portfolio_decision_engine.py`, `opportunity_ranker.py`,
   `market_regime_gate.py`, `paper_material_readiness.py` ni `auto_reason_codes.py`; `TOP_N=5`; umbrales
   `32/3/8/4/2`; `auto15-v1`/`auto18-v1`; head `046_fill_reference_mid`.
5. **Sin mutaciones nuevas.** La matriz sigue en **230/230** (no hay código que mutar); `M226`–`M230`
   siguen mordiendo y restaurando **byte a byte** si se re-ejecutan.
6. **Instrumento intacto.** El funnel, el `unresolved_age` y el informe HTML de `v2.81` **no cambian**;
   el contrato `None ≠ 0` y el veredicto honesto `INCONCLUSIVE` siguen vigentes.
7. **Registro en CI.** Los workflows **no** se tocan; los ficheros puros ya registrados
   (`test_market_operability.py`, `test_operability_window.py`) mantienen su conteo.
8. **CI del tag** `v2.82-beta` verde en la primera pasada (docs-only, pero el workflow del tag corre igual).

## 2. Estado declarado de los hallazgos previos

- **`H-1`/`H-2`/`H-3`**: **CERRADOS** en `v2.79`.
- **`H-4` (LOW)**: **ABIERTO**; **no** se cierra en `v2.82` (decisión del auditor: cerrarlo **después** de
  la primera ventana real, y sólo si `otherCount > 0`).
- **`P3-2`/`P3-3`**: **ABIERTAS** (ventana ≥4 días = operación del propietario). `v2.82` **no** certifica.
- **`P3-5`** y **`OBS-5`**: siguen declaradas.

## 3. Límites de lo que el auditor podrá reproducir

- **Sin material PAPER real** (`operability_runs/` está gitignoreado), la tabla/funnel de la ventana se
  re-derivan con **fixtures**; **no** puede afirmarse que `P3-2`/`P3-3` estén cerradas: **no hubo ventana**.
- **Sin PostgreSQL**, los jobs PG se verifican **por su resultado en CI**, no en local.
- Sin `--forward`, los escalones superiores del funnel se leen `None`: es correcto (declarado), no un
  defecto.

## 4. Evidencia cruda

- `evidencia-ci-tag-v2.82-2026-09-27.txt` — CI del tag `v2.82-beta` (commit POST-TAG).
- Matriz adversarial vigente: [`evidencia-matriz-mutaciones-v2.81-230-2026-09-27.txt`](./evidencia-matriz-mutaciones-v2.81-230-2026-09-27.txt).
