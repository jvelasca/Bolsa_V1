# Evidencia cruda — `v2.88.24-beta` (AUTO Operational Monitor · cierre de A1–A4 de la auditoría de `v2.88.23`)

> **Objeto:** package **`2.11.24-beta`** · Alembic head **`046_fill_reference_mid`** (**SIN migración**) · fecha **2026-10-02**.
> **Clase:** sello de **producto** sobre el **read model + la auditoría + el contrato** del monitor AUTO. **`Δ decisión motor = 0`**: ninguna decisión de inversión cambia. `auto_simulation_worker.py` SÍ aparece en el diff, pero **sólo** en el tramo de **trazado** `_v2_journal_entry_decisions` (sella `payload.engineId` cuando el productor no lo trae); con `AUTO_OPERATIONAL_AUDIT` OFF (default) ese tramo es un no-op ⇒ `Δ = 0` por defecto.
> **Origen:** auditoría externa de `v2.88.23-beta` (hallazgos A1–A4). Cierra la incoherencia entre `fill_window_truncated` y la reconstrucción de `CYCLE_CLOSED`/`PnL`, y tres deudas semánticas del agregado/lectura.
> **Padre:** [`evidence/v2.88.23/README.md`](../v2.88.23/README.md).

---

## 0. Qué corrige este sello

| # | Grieta | Corrección |
|---|---|---|
| **A1 🟠 (P1)** | La ventana de fills se marcaba `PARTIAL`, pero `cycles_from_fills` ya se había calculado antes y **`CYCLE_CLOSED` podía afirmarse `reached`** con `result.pnl` sobre un subconjunto truncado. | Agregado `count_by_cycle_ids` (`GROUP BY cycle_id`). La completitud es **por ciclo**: truncado ⇒ `CYCLE_CLOSED` `unknown`/`PARTIAL` (nota `cycle_closed_window_truncated`), `closed = null` + `closedMeasurement = PARTIAL`, `result = null`. Sin agregado se cae al suelo global `fills_window_full`. |
| **A2 🟡 (P2)** | El agregado ejecutado con `COUNT(*)=0` se convertía en `None` + `UNKNOWN` (`raw_claim_attempts > 0`): "cero medido" ≠ "no medido". | Con el agregado disponible, `0` y `>0` son `COMPLETE`; `UNKNOWN` queda para la consulta no disponible. La ruta de filas también trata un total explícito (`0` incluido) como medido. |
| **A3 🟡 (P2)** | `list_entries` ordenaba sólo por `created_at DESC`: con timestamps empatados el `LIMIT 1` no era determinista. | `ORDER BY created_at DESC, id DESC` (también en `list_by_decision_ids`). |
| **A4 🟡 (P2)** | `lastDecisionAt` se leía por `account_id + event_type`: dos motores de la misma cuenta compartían "última decisión". | El trazado sella `payload.engineId`; `list_entries` filtra `payload->>'engineId'`; `read_operational_monitor` acota por `engine_id`. |

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | Con la ventana de fills de un ciclo truncada (`cargados < total`), `CYCLE_CLOSED` es `unknown`/`PARTIAL` y `result`/`closed` no se afirman. | Volver a derivar el cierre del `cycles_from_fills` de la ventana ⇒ el test puro y el PG fallan. | `test_cycle_window_truncated_degrades_cycle_closed_and_pnl` + PG `test_monitor_truncated_fill_window_does_not_affirm_cycle_closed` |
| **C2** | La completitud es **por ciclo**: un ciclo corto completo NO se degrada porque la ventana global esté llena. | Usar sólo `fills_window_full` ⇒ el test puro falla. | `test_cycle_window_complete_keeps_cycle_closed_even_with_global_window_full` |
| **C3** | Sin agregado por ciclo, el suelo global `fills_window_full` vuelve a degradar (fail-closed). | Ignorar el flag global ⇒ el test puro falla. | `test_cycle_window_full_without_aggregate_falls_back_to_global` |
| **C4** | Un `side` no clasificable deja `closed = null`/`PARTIAL` (el neto puede estar incompleto). | Volver a afirmar `closed=False` ⇒ el test puro falla. | `test_fill_with_unclassifiable_side_is_declared_partial_not_dropped` |
| **C5** | El agregado ejecutado con `COUNT=0` es `COMPLETE` (cero medido), no `UNKNOWN`. | Volver a `raw > 0` ⇒ el test puro y el PG fallan. | `test_concurrency_aggregate_zero_is_measured_not_unknown` + PG `test_monitor_aggregate_zero_is_measured_complete` |
| **C6** | Con `created_at` empatado el orden es determinista (`id DESC`). | Quitar el desempate ⇒ el test PG falla de forma intermitente/incierta. | PG `test_list_entries_tiebreaks_equal_timestamps_deterministically` |
| **C7** | `lastDecisionAt` es la decisión del `engine_id` leído, no la de otro motor más nuevo. | Volver a `account_id` solo ⇒ el test PG falla. | PG `test_monitor_last_decision_is_scoped_by_engine` |
| **C8** | El trazado sella `payload.engineId` sólo cuando falta (aditivo, sin reescribir identidad). | No sellar / pisar un `engineId` del productor ⇒ los tests del seam fallan. | `test_entry_decision_seals_the_engine_id_for_the_scoped_read`, `test_entry_decision_keeps_a_producer_engine_id_without_rewriting` |
| **C9** | El contrato no drifta: `closed` nullable + `closedMeasurement` regenerados. | Tocar el DTO sin regenerar ⇒ `contract:check` rojo. | `pnpm --filter @bolsa/web contract:check` → `OK` |
| **C10** | La UI no afirma "Abierto"/"Cerrado" cuando el cierre no está medido. | Colorear por "hay valor" ⇒ el test de UI/shared falla. | shared `buildAutoOperationalMonitorView` + web `auto-monitor.test.tsx` |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | `Success: no issues found in 515 source files` |
| `uv run python -m pytest packages/py/application/tests -q` | **2237 passed** (`v2.88.23` tenía **2233**: **+4** de este sello) |
| `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q` | **20 passed** (PG real; 8 del monitor + 12 del seam) |
| `pnpm --filter @bolsa/shared exec vitest run src/cognitive/auto-operational-monitor.test.ts` | **12 passed** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/auto-monitor.test.tsx` | **9 passed** |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK` |

Compilación del agregado por ciclo contra el dialecto PostgreSQL (sin BD):

```sql
SELECT cycle_id, count(*)
FROM sim_fill_finance_context
WHERE cycle_id IN (:cycle_ids) AND account_id = :account_id
GROUP BY cycle_id
```

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **Sin backfill de `engineId`.** Las filas `auto_entry_decision` escritas **antes** de este sello no llevan `payload.engineId` y **no entran** en la lectura scoped por motor: `lastDecisionAt` scoped se puebla a partir de la próxima decisión trazada. Mismo patrón que el backfill de `account_id` de `v2.88.23`.
2. **`SETTLEMENT`/`ENTRY_ORDER` siguen `NO MEDIDO`.** Este sello no añade productores durables; sigue siendo deuda declarada.
3. **`activeSessions` sigue siendo un SUELO** (sin productor de latido durable).
4. **`price_source` durable sigue pendiente.** `realPriceEnabled` sigue significando configuración, no fuente usada por operación.
5. **`Δ` del motor de decisión = 0.** El único cambio en `auto_simulation_worker.py` está en `_v2_journal_entry_decisions` (sello de `payload.engineId`), inerte sin `AUTO_OPERATIONAL_AUDIT` encendido.
6. **No cierra `P3-2`/`P3-3` ni las compuertas `G1`–`G7`.** Sin migración: Alembic head sigue en `046_fill_reference_mid`.

---

## 4. Comandos (reproducir)

```bash
uv run python -m pytest packages/py/application/tests/test_auto_operational_monitor.py -q
uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py -q
uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q
AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q   # exige PG real
pnpm --filter @bolsa/shared exec vitest run src/cognitive/auto-operational-monitor.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/auto-monitor.test.tsx
pnpm --filter @bolsa/web contract:check
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
```

---

## 5. Sello

- **Versión:** `2.11.24-beta` (base `2.11.23-beta`); **SIN migración** (Alembic head `046_fill_reference_mid`).
- **Ficheros de producto:** `packages/py/application/src/bolsa_application/auto_operational_monitor.py`, `.../sim_durable_store.py`, `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/journal_repository.py`, `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (tramo de trazado), `apps/api-python/src/bolsa_api/api/v1/routes/auto_operational_monitor.py`, `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`, `packages/shared/src/cognitive/auto-operational-monitor.ts`, `apps/web/src/features/auto-monitor/auto-cycle-timeline.tsx` + tests + docs.
- **Cita del CI:** `Release tag CI` run [`36985958957`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36985958957) (`ref=refs/tags/v2.88.24-beta`, HEAD `695c9800`, `2026-10-02T08:46:29Z → 08:54:34Z`) → **`SUCCESS`**: **11 jobs `success`** + `playwright (integrated E2E, opt-in)` `skipped` por diseño, **`certify` `success`**. Job `python`: `All checks passed!` · `Contracts: 4 kept, 0 broken` · `mypy no issues found in 515 source files` · **`4217 passed, 42 skipped, 7 warnings in 91.03s`** (`v2.88.23` = `4211 passed, 42 skipped` ⇒ **+6**, mismos `42` skips). `lifecycle-pg` **VERDE** con gates *fail-if-skipped*. `replay-repro` → `VEREDICTO REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)` con `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` / **3340728 B** (LF; sello `3445622 B`) y **2ª corrida IDÉNTICA** ⇒ el artefacto OOS **no se mueve** (`Δ motor = 0` medido en el runner).
