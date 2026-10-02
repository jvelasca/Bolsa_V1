# Evidencia cruda — `v2.88.28-beta` (AUTO · `PROTECTION` `exactly-once` en TODOS sus caminos)

> **Objeto:** package **`2.11.28-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-02**.
> **Clase:** sello **quirúrgico de producto** que cierra el **hallazgo principal de la auditoría de `v2.88.27-beta`**: el hecho durable de protección (`auto_protection_event`) exigía `revisionId`, pero varios productores lo emitían **sin** revisión ⇒ `durable_fact_dedupe_key` devolvía `None` ⇒ el `append` caía al INSERT plano y un reintento/crash **duplicaba** la transición. Ahora **toda** transición de protección lleva una revisión durable **determinista** y su `dedupe_key`. **`Δ decisión motor = 0`**: los productores van tras `AUTO_OPERATIONAL_AUDIT` (default OFF ⇒ no-op) y las revisiones son audit-only.
> **Origen:** hallazgo `🔴 PROTECTION exactly-once — PENDIENTE` de la auditoría externa de `v2.88.27-beta`.
> **Padre:** [`evidence/v2.88.27/README.md`](../v2.88.27/README.md) (que introdujo `dedupe_key` + recuperación de `SETTLEMENT`).
> **Nomenclatura:** `AUTO engineering release = v2.88.28-beta` · `application package = 2.11.28-beta` (el tag de ingeniería **no** es el semver del paquete).

---

## 0. Qué produce este sello

| # | Hueco (hasta `v2.88.27`) | Hecho durable que se produce ahora |
|---|---|---|
| **H1 🔴** | Sólo el ratchet que **mueve el stop** pasaba `revision_id`; nacimiento, `T1_HIT`/`T2_HIT`/`TRAIL_ARMED`, `PROTECT_REQUESTED` y las salidas pedidas viajaban **sin** revisión ⇒ `dedupe_key = NULL` ⇒ duplicables. | `seal_protection_transition(...)` en los **6** puntos de emisión: reutiliza la revisión del paso o **añade** una determinista; el hecho declara `dedupe_key`. |
| **H2 🔴** | La revisión de un cambio real se generaba con `REV-<uuid4>` **por intento**: un crash antes de persistir y su recomputación darían dos identidades. | `deterministic_revision_id(...)` deriva `REV-<sha256(estado durable)[:16]>` (sin `at`): el mismo cambio recomputado ⇒ la **misma** clave ⇒ **una** fila. |

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | La identidad de una revisión es **determinista** y **content-addressed**: el mismo cambio desde el mismo estado durable ⇒ la misma `REV-…`; otro ordinal/discriminador ⇒ otra. | Volver a `uuid4`/incluir `at` ⇒ el test de determinismo falla. | `packages/py/analytics/tests/test_position_revision.py` (**19 passed**; +7) |
| **C2** | `apply_position_current_stop`/`apply_position_reduce` sellan la revisión con la identidad determinista (no `uuid4`). | Revertir a `uuid4` ⇒ los tests de determinismo fallan. | `test_position_revision.py::test_apply_stop_revision_id_is_deterministic` / `…reduce…` |
| **C3** | `seal_protection_transition` **reutiliza** la revisión si el paso ya la añadió, la **añade** si el cambio es sólo de lifecycle, y **no** inventa revisión si no hubo cambio durable (id por contenido). | Duplicar la revisión / no añadirla ⇒ el test del helper falla. | `test_position_revision.py` (`test_seal_protection_transition_*`, 3 tests) |
| **C4** | Cada `kind` del vocabulario cerrado, con su `revision_id`, deriva una clave determinista y el alta es **idempotente** (mismo hecho ⇒ **1** fila). | Quitar el `revision_id`/`ON CONFLICT` ⇒ el hermético falla. | `apps/api-python/tests/test_auto_v88_28_protection_exactly_once.py` (**12 passed**, parametrizado por `kind`) |
| **C5** | Una **revisión nueva** (transición legítima distinta) es un **hecho nuevo** ⇒ otra fila. | Clavear sólo por `kind` ⇒ el test falla. | `test_auto_v88_28_protection_exactly_once.py::test_a_distinct_revision_is_a_distinct_fact` |
| **C6** | Sin `revision_id` **no** se finge identidad: `dedupe_key = None` y el INSERT plano del histórico se conserva. | Inventar una clave ⇒ el test falla. | `test_auto_v88_28_protection_exactly_once.py::test_without_a_revision_the_fact_declares_no_identity` |
| **C7** | **PG real**: cada `kind` con su revisión es idempotente bajo reintento ⇒ **1** fila. | Quitar el índice/`ON CONFLICT` ⇒ el PG falla. | `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 … test_auto_v88_28_protection_exactly_once_pg.py` (**3 passed**) |
| **C8** | **PG real**: dos procesos (sesiones/conexiones) que publican la MISMA transición ⇒ **1** fila. | Clave no determinista ⇒ 2 filas. | `test_auto_v88_28_protection_exactly_once_pg.py::test_two_sessions_recovering_the_same_transition_write_one_row` |
| **C9** | **PG real**: sin revisión (`NULL`) el comportamiento previo se conserva ⇒ **2** filas (índice **parcial**). | Índice no parcial ⇒ el PG falla. | `test_auto_v88_28_protection_exactly_once_pg.py::test_without_a_revision_the_plain_insert_is_kept` |
| **C10** | El **productor** sella el nacimiento (`PROTECT_APPLIED`) con `revision_id` durable y `dedupe_key`, y añade su revisión al `PositionState` persistido. | No sellarlo ⇒ el test de integración falla. | `apps/api-python/tests/test_auto_v2_worker_integration.py` (**39 passed**; +1) |
| **C11** | **`Δ decisión motor = 0`**: sin sumidero no se emite nada y la posición abierta es idéntica; `revisions` es audit-only. | Cambiar la decisión ⇒ `test_auto_v2_worker_integration.py` falla; alterar el artefacto OOS ⇒ el run PRE-cambio y el de este sello dejarían de ser byte-idénticos. | `test_auto_v2_worker_integration.py`; regeneración local del artefacto OOS **pre-cambio vs sello** = `IDENTICAL` (`sha256 LF CD877EDB…`), sin `revision`/`positionState` en el artefacto |
| **C12** | El contrato no drifta: `openapi.json`/`schema.d.ts`/shared sin cambios; **sin migración** (Alembic head sigue `048`). | Tocar el DTO / la cadena ⇒ `contract:check`/`alembic heads` rojo. | `uv run alembic heads` → `048_journal_entry_dedupe_key (head)` |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | `Success: no issues found in 517 source files` (mismos ficheros que `v2.88.27`) |
| `uv run python -m pytest packages/py/analytics/tests -q` | **1277 passed** |
| `uv run python -m pytest packages/py/analytics/tests/test_position_revision.py -q` | **19 passed** (`v2.88.27` = 12; **+7** de este sello) |
| `uv run python -m pytest packages/py/application/tests -q` | **2299 passed** (sin cambios: este sello no añade tests de `application`) |
| `uv run python -m pytest apps/api-python/tests/test_auto_v88_28_protection_exactly_once.py -q` | **12 passed** (nuevo, hermético) |
| `uv run python -m pytest apps/api-python/tests/test_auto_v2_worker_integration.py -q` | **39 passed** (`v2.88.27` = 38; **+1**) |
| `uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q` | **21 passed** |
| `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_auto_v88_28_protection_exactly_once_pg.py -q` | **3 passed** (PG real) |
| `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_auto_v88_27_durable_facts_idempotent_pg.py apps/api-python/tests/test_auto_v88_27_durable_facts_recovery.py apps/api-python/tests/test_auto_v88_28_protection_exactly_once_pg.py apps/api-python/tests/test_auto_v88_durable_facts.py -q` | **18 passed** |
| `uv run lint-imports --config packages/py/.importlinter` | `Contracts: 4 kept, 0 broken.` |
| `uv run alembic heads` (en `packages/py/infrastructure`) | `048_journal_entry_dedupe_key (head)` (**sin migración**) |
| `replay-repro` (regeneración local del artefacto OOS desde el fixture congelado, Windows) | `NO reproducido` **por *drift de plataforma* documentado** (render CRLF local `30DC1412…` / `sha256 LF` `CD877EDB…` vs sello Linux `1E3ADAC2…` / `3340728 B`); **pero** el artefacto de este sello y el del árbol **PRE-cambio** (los 3 ficheros de producto en `git stash`) son **byte-idénticos** (`Compare-Object` = `IDENTICAL`) y el artefacto **no contiene** `revision`/`positionState` ⇒ **`Δ motor = 0`**. La reproducción del sello byte a byte la certifica el runner Linux del job `replay-repro` del tag. |
| **CI de tag** | **Pendiente de publicar el tag** `v2.88.28-beta`; se citará con su `run` real (mismo criterio que `v2.88.27`). |

> Nota de honestidad: la corrida local completa de `apps/api-python/tests` (contra PG real) reportó fallos de **caos/concurrencia** (`test_auto_v46_multiprocess_pg`, `test_auto_v56_auto15_data_gate_pg`, `test_strategy_lifecycle_pg`, `integration/test_trade_idempotency`, `integration/test_idempotency_reused_409`, `test_workspaces_crud`) que **desaparecen al re-ejecutarlos en aislamiento** (30 passed / 1 failed), más `integration/test_tax_report.py::test_tax_report_after_round_trip_trade` (`403`), **preexistente** ya documentado en la evidencia de `v2.88.27` (falla idénticamente en el árbol pre-cambio). El job `python`/`lifecycle-pg` del CI es quien certifica.

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **`PROTECTION` sin recuperación de AUSENCIA** de transiciones (sólo exactly-once): no hay histórico que re-derivar; sólo la proyección viva es reconstruible.
2. **Sin migración.** Reutiliza la columna `dedupe_key` y el índice único parcial de la `048`; no hay `upgrade`.
3. **Sin backfill.** Los hechos previos quedan con `dedupe_key = NULL` (índice parcial ⇒ no colisionan) y **no** se reescriben.
4. **`ENTRY_ORDER` sin recuperación de AUSENCIA** (ya declarado en `v2.88.27`).
5. **`Δ decisión motor = 0`.** Sin `AUTO_OPERATIONAL_AUDIT` (default OFF) no hay sink y los productores son no-op; `revisions` no entra en signal/ranking/risk sizing/allocation/execution.
6. **Golden Day 2.0, crash/recovery longitudinal y PAPER ≥4 días** siguen fuera de alcance (siguiente salto de calidad, ya no más observabilidad).
7. **`PROJECT_STATE.md`/`engineering-index` no se tocan** (mismo criterio que `v2.88.25`–`v2.88.27`).

---

## 4. Comandos (reproducir)

```bash
uv run python -m pytest packages/py/analytics/tests/test_position_revision.py -q
uv run python -m pytest packages/py/analytics/tests -q
uv run python -m pytest packages/py/application/tests -q
uv run python -m pytest apps/api-python/tests/test_auto_v88_28_protection_exactly_once.py -q
uv run python -m pytest apps/api-python/tests/test_auto_v2_worker_integration.py -q
uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q
AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_auto_v88_28_protection_exactly_once_pg.py -q   # exige PG real
uv run lint-imports --config packages/py/.importlinter
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
uv run alembic heads   # en packages/py/infrastructure
```

---

## 5. Sello

- **Versión:** `2.11.28-beta` (base `2.11.27-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros de producto:** `packages/py/analytics/src/bolsa_analytics/cognitive/position_revision.py` (`deterministic_revision_id`), `packages/py/analytics/src/bolsa_analytics/cognitive/position_state.py` (`seal_protection_transition`, `_with_revision_if_changed` determinista), `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (los 6 puntos de emisión pasan `revision_id`) + tests + docs.
- **CI:** pendiente de tag; se actualizará esta evidencia con el `run` real de `Release tag CI` al publicar `v2.88.28-beta`.
