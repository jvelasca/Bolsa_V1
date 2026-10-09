# Evidencia `v2.88.99-beta` — `PAPER-2`: **adaptador de evidencia durable + conciliación verificable (`Δ motor ≠ 0` estricto · `Δ decisión = 0`)**

**Producto:** `V2.88.99-beta` · **Package:** `2.11.99-beta` · **AsOf:** 2026-10-09. **Sin migración nueva** (head `052_top3_opportunities`). Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.99-beta` junto al `package.json` (guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py)).

> **Nota de árbol (honesta).** Este sello **`Δ motor ≠ 0` en sentido ESTRICTO**: `git diff --name-only -- packages/py` **NO** está vacío. Añade **código Python read-only** (`paper_evidence_reconciliation.py`, `paper_evidence_adapter.py`, `paper_evidence_reader.py`) y **un endpoint HTTP read-only** (`GET /api/auto/paper-evidence`). Lo que **sí** es cero es la **decisión** (`Δ decisión = 0`): sin motor, sin worker, sin umbrales, sin Alembic, sin scheduler, sin cambios de comportamiento en endpoints existentes. `replay-repro` lo confirma por CI: **`REPRODUCIDO`** `24066225…6D9F54F0` (render) / `1E3ADAC2…929A37E7` (mismo contenido en LF).

**Origen.** Ejecuta el plan `PAPER-2` (adaptador de evidencia durable) sobre el contrato puro de `PAPER-1` ([`paper-confirmation-contract.ts`](../../../../apps/web/src/features/auto-monitor/paper-confirmation-contract.ts)): conectar los siete criterios a las **fuentes durables reales** y **conciliar** sus registros entre sí, sin emitir `CONFIRMED`.

## 1. Cambios (por tarea del plan)

| # | Tarea | Qué hace | Implementación |
| --- | --- | --- | --- |
| 1 | **Conciliación pura** | Funciones puras que cruzan operaciones ↔ ejecuciones ↔ cierres ↔ resultados: ejecución duplicada, fill huérfano (sin `cycle_id`), cantidad desequilibrada, settlement sin cierre probado, PnL/cantidad discrepantes. Reutiliza `cycles_from_fills` (AUTO-7) como ÚNICA autoridad de cierre y `applied_cost_from_fills` (AUTO-16) para el coste; **sin** un segundo FIFO. Cada cruce devuelve medición declarada y **contradicción nombrada**. | [`paper_evidence_reconciliation.py`](../../../../packages/py/application/src/bolsa_application/paper_evidence_reconciliation.py), [`test_paper_evidence_reconciliation.py`](../../../../packages/py/application/tests/test_paper_evidence_reconciliation.py) |
| 2 | **Compositor del adaptador** | Compone los **siete criterios** del contrato (`window`, `operation_lineage`, `execution_attribution`, `closure_reconciliation`, `cost_coverage`, `durable_results`, `non_contradiction`) con `status` (`met`/`unmet`/`unknown`), **procedencia**, medición y contadores nullable. `null` viaja `null` + `UNKNOWN`, nunca `0`; ningún criterio se mide sin fuente cargada; detalle **por `strategyVersion`**. `verdict` literal `NO_CONFIRMED`. | [`paper_evidence_adapter.py`](../../../../packages/py/application/src/bolsa_application/paper_evidence_adapter.py), [`test_paper_evidence_adapter.py`](../../../../packages/py/application/tests/test_paper_evidence_adapter.py) |
| 3 | **Lector + endpoint read-only** | `read_paper_evidence` lee, **solo con `SELECT`**, `sim_fill_finance_context` (fills por ciclo + `count_by_strategy_version`), el spine `decision_journal_entries` (`auto_cycle_settlement` por `decision_id` derivado) y compone el DTO. La ruta `GET /api/auto/paper-evidence` es **account-scoped** (fail-closed `no_account_scope`, nunca global), `readOnly = true`, con DTO **sin campo de confirmación**. | [`paper_evidence_reader.py`](../../../../packages/py/application/src/bolsa_application/paper_evidence_reader.py), [`auto_paper_evidence.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_paper_evidence.py), [`router.py`](../../../../apps/api-python/src/bolsa_api/api/v1/router.py) |
| 4 | **Contrato FE/BE** | `contract:gen` regenera [`openapi.json`](../../../../apps/web/api/openapi.json) (+529 líneas) y [`schema.d.ts`](../../../../apps/web/src/api/schema.d.ts) (+201 líneas); `contract:check` verde. | [`auto_paper_evidence.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_paper_evidence.py) |
| 5 | **Cableado web (mapeo, sin rediseño)** | `getAutoPaperEvidence` + hook `use-auto-paper-evidence` + mapeo **puro** DTO→`PaperConfirmationContractInput`. `buildPaperConfirmationVerdict` sigue siendo la ÚNICA autoridad del veredicto y la copy. | [`api.ts`](../../../../apps/web/src/lib/api.ts), [`use-auto-paper-evidence.ts`](../../../../apps/web/src/features/auto-monitor/use-auto-paper-evidence.ts), [`paper-evidence-from-dto.ts`](../../../../apps/web/src/features/auto-monitor/paper-evidence-from-dto.ts), [`paper-evidence-from-dto.test.ts`](../../../../apps/web/src/features/auto-monitor/paper-evidence-from-dto.test.ts) |
| Bump | — | `package.json` (`2.11.99-beta`) + `meta.bump` de `v2_89`…`v2_97`. | [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) |

## 2. Reglas que NO cambian

- **`UNKNOWN ≠ 0`.** Fuente no leída ⇒ criterio `unknown` y contadores `null`. Fuente leída y vacía ⇒ cero **medido** (no un hueco). Jamás se colapsa la ausencia a un `0` ni a «Cumplido».
- **Confirmación reservada.** `verdict` es el literal `NO_CONFIRMED`; el token suelto `CONFIRMED` **no** aparece en el payload (probado con `/\bCONFIRMED\b/` en Python, PG y web). Aunque los siete criterios se cumplan, el veredicto **sigue** siendo `NO_CONFIRMED`.
- **Un dato parcial no satisface un criterio completo.** Ejecución duplicada, fill huérfano, cantidad desequilibrada, cierre contradictorio o PnL discrepante ⇒ **contradicción declarada** y criterio degradado.
- **Una sola noción de cierre.** La conciliación no reimplementa FIFO: cuelga de `cycles_from_fills` (la misma autoridad que el informe AUTO-7, la confianza y el readiness).
- **Motor intacto.** Sin motor de decisión, sin worker, sin umbrales, sin Alembic, sin scheduler, sin re-habilitar `CONFIRMED`.

## 3. Verificación (local)

- `pnpm --filter @bolsa/web run typecheck` (`tsc -b --noEmit`) → **OK** (exit 0).
- `pnpm --filter @bolsa/web run lint` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes, ajenos a este sello).
- `pnpm --filter @bolsa/web run test` → **289 ficheros / 2011 tests verdes** (+1 fichero / +4 tests sobre `v2.88.98`).
- `uv run pytest packages/py/application/tests -q` → **2549 passed** (+16 tests nuevos sobre `v2.88.98`).
- `uv run pytest apps/api-python/tests/test_auto_paper_evidence_pg.py -q` → **3 passed** contra **PostgreSQL real** (cadena durable, ausencia medida y cierre contradictorio).
- `uv run pytest apps/api-python/tests/test_auto_paper_evidence_route.py -q` → **2 passed** (DTO válido; `no_account_scope` ⇒ todo `unknown`).
- `uv run mypy packages/py/application/src/bolsa_application/paper_evidence_{reconciliation,adapter,reader}.py` → **Success**.
- `uv run ruff check` (módulos y tests nuevos) → **All checks passed**.
- `pnpm --filter @bolsa/web run contract:check` → **OK**.
- `uv run pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` → **1 passed** (`2.11.99-beta`).
- **`Δ decisión = 0`**: `replay-repro` **`REPRODUCIDO`** — `assert-artifact` byte a byte contra `24066225…6D9F54F0` / 3 445 622 B y mismo contenido `1E3ADAC2…929A37E7` en LF (medido sobre una BD **limpia** sembrada con el fixture congelado, como en CI).

## 4. Qué no cambia / deuda declarada

- **Motor de decisión/ejecución**, worker, umbrales, Alembic (head `052_top3_opportunities`) y scheduler: **intactos**.
- **`Δ motor ≠ 0` estricto:** se añade código Python **read-only** y un endpoint **read-only**; ningún camino que decida o ejecute cambia. La evidencia lo declara en vez de esconderlo tras un `git diff` vacío que sería falso.
- **La superficie web es mapeo + test, sin pantalla nueva.** `buildPaperConfirmationVerdict` es la única autoridad del veredicto; el panel visible queda para el `P2` posterior.
- **`E2E integrado`** del sello se declara `skipped` (opt-in), **no** como prueba superada.
- **La ventana (`window`)** se mide sobre el material durable (`sim_fill_finance_context.created_at` + ciclos observados), no sobre el artefacto de operabilidad del replay; la procedencia lo declara. La confirmación de la ejecución real PAPER sigue **reservada**: ningún criterio aislado confirma la operativa.
