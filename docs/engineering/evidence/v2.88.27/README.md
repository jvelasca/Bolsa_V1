# Evidencia cruda — `v2.88.27-beta` (AUTO · hechos M2 `exactly-once` + recuperación de `SETTLEMENT`)

> **Objeto:** package **`2.11.27-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**migración 048**) · fecha **2026-10-02**.
> **Clase:** sello de **producto** que cierra el **P1 de integridad de auditoría** abierto por la auditoría de `v2.88.25-beta`: (a) los hechos durables M2 se escribían con PK aleatoria `JNL-<uuid4>` **sin clave natural**, así que un reintento/rearranque del sumidero los **duplicaba**; (b) un crash entre `persist_position(CLOSED)` y `_v2_journal_cycle_settlement(...)` dejaba la posición cerrada con el `SETTLEMENT` **sin sellar** (el monitor volvía a `settlement_not_durable`). **`Δ decisión motor = 0`**: todo va tras `AUTO_OPERATIONAL_AUDIT` (default OFF ⇒ no-op) y la columna es aditiva.
> **Origen:** hallazgo P1 declarado en la auditoría de [`evidence/v2.88.25/README.md`](../v2.88.25/README.md) (crash entre cierre financiero y publicación del `SETTLEMENT`; ausencia de clave de idempotencia/deduplicación `(account, engine, event_type, cycle)`).
> **Padre:** [`evidence/v2.88.26/README.md`](../v2.88.26/README.md) (que cerró `PROTECTION`).
> **Nomenclatura:** `AUTO engineering release = v2.88.27-beta` · `application package = 2.11.27-beta` (el tag de ingeniería **no** es el semver del paquete).

---

## 0. Qué produce este sello

| # | Hueco (hasta `v2.88.26`) | Hecho durable que se produce ahora |
|---|---|---|
| **H1 🔴** | Los hechos M2 (`auto_entry_order`, `auto_cycle_settlement`, `auto_protection_event`) no tenían identidad natural: un reintento/rearranque los **duplicaba**. | `dedupe_key` determinista + índice único **parcial** + `append` idempotente (`ON CONFLICT DO NOTHING`). |
| **H2 🔴** | Un crash entre el cierre financiero y la publicación del `SETTLEMENT` dejaba el ciclo cerrado **sin hecho** (monitor en `settlement_not_durable`). | Recuperación de arranque `_v2_recover_durable_facts()`: reemite **sólo** el `SETTLEMENT` que los fills durables demuestran y que el spine no tiene, idempotente por `dedupe_key`. |
| **M1 🟠** | La autoridad de `price_source` (`fill` vs snapshot del evento) no estaba fijada por escrito. | `canonical_price_source` (gana el **fill**) + `price_source_snapshot_disagrees` (la discrepancia se declara, "no medido" ≠ "distinto"). |

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | La identidad de un hecho M2 es **determinista**: `auto_cycle_settlement:{account}:{engine}:{cycle}`, `auto_entry_order:{account}:{engine}:{cycle}:{order}` y `auto_protection_event:{account}:{engine}:{cycle}:{kind}:{revisionId}`. | Cambiar el formato ⇒ `test_auto_operational_audit.py` falla. | `packages/py/application/tests/test_auto_operational_audit.py` (**23 passed**; +4) |
| **C2** | La `kind` sola **no** basta para `PROTECTION`: sin `revisionId` la clave es `None` (dos transiciones legítimas del mismo tipo pueden convivir). | Clavear por `kind` ⇒ el test de revisión falla. | `test_auto_operational_audit.py` |
| **C3** | Sin componentes de identidad (cuenta/motor/ciclo) la clave es `None` (no se inventa una clave a medias) y un `event_type` ajeno es `None`. | Rellenar con un literal ⇒ el test falla. | `test_auto_operational_audit.py` |
| **C4** | El `append` es **idempotente** por `dedupe_key`: dos altas del MISMO hecho ⇒ **1 fila**. | Quitar el `ON CONFLICT` ⇒ el PG falla. | `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 … test_auto_v88_27_durable_facts_idempotent_pg.py` (**3 passed**) |
| **C5** | Sin `dedupe_key` (`NULL`) el comportamiento previo se conserva: dos altas ⇒ **2 filas** (índice **parcial**). | Índice no parcial ⇒ el PG falla. | `test_auto_v88_27_durable_facts_idempotent_pg.py` |
| **C6** | La migración `048` es **aditiva y reversible**: `downgrade` a `047` retira columna e índice; `upgrade head` los recrea. | Downgrade incompleto ⇒ el roundtrip del PG falla. | `test_auto_v88_27_durable_facts_idempotent_pg.py` (`test_migration_048_roundtrip_creates_and_drops_the_dedupe_key`) |
| **C7** | El productor sella `dedupe_key` para `ENTRY_ORDER`/`SETTLEMENT` en el turno real (misma clave en el reintento). | No sellarlo ⇒ `test_auto_v88_durable_facts.py` falla. | `apps/api-python/tests/test_auto_v88_durable_facts.py` (**4 passed**) |
| **C8** | La recuperación reemite el `SETTLEMENT` de un ciclo cerrado sin hecho, con el MISMO FIFO, `closedQty` del fill de cierre, `priceSource` del fill y `exitReason=None` **declarado**. | Inventar el motivo / no reemitir ⇒ el hermético falla. | `apps/api-python/tests/test_auto_v88_27_durable_facts_recovery.py` (**8 passed**) |
| **C9** | El reenvío es **idempotente entre procesos**: dos recuperaciones del mismo ciclo ⇒ **1 hecho**. | Clave no determinista ⇒ el doble sumidero daría 2. | `test_auto_v88_27_durable_facts_recovery.py` (`test_recovery_is_idempotent_across_processes`) |
| **C10** | Un ciclo ya sellado no se toca y un ciclo **abierto** no se declara settlement; sin lector no se recupera nada; la recuperación corre **una vez por proceso**. | Afirmar sin prueba / repetir ⇒ el hermético falla. | `test_auto_v88_27_durable_facts_recovery.py` |
| **C11** | **`Δ decisión motor = 0`**: sin sumidero no se construye sink ni lector, no corre la recuperación, `append` conserva el INSERT plano y la posición abierta es idéntica. | Cambiar la decisión ⇒ `test_auto_v2_worker_integration.py` falla. | `apps/api-python/tests/test_auto_v2_worker_integration.py` (**38 passed**) |
| **C12** | El monitor sigue **VERDE** con el head nuevo (13 facts PG). | No cablear el `journal` ⇒ el PG falla. | `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 … test_auto_operational_monitor_pg.py` (**13 passed**) |
| **C13** | **CON migración**: Alembic head pasa `047_fill_price_source` → `048_journal_entry_dedupe_key`. | Cadena rota/dos heads ⇒ los tests de head fallan. | `uv run alembic heads` → `048_journal_entry_dedupe_key (head)` |
| **C14** | La autoridad de `price_source` es el **fill**; el snapshot del evento no lo sobreescribe y la discrepancia sólo existe si ambas fuentes están **medidas**. | Hacer ganar al snapshot / tratar "no medido" como discrepancia ⇒ `test_price_source_kind.py` falla. | `packages/py/application/tests/test_price_source_kind.py` (**15 passed**; +2) |
| **C15** | El contrato no drifta: `openapi.json`/`schema.d.ts` sin cambios. | Tocar el DTO sin regenerar ⇒ `contract:check` rojo. | `pnpm --filter @bolsa/web contract:check` → `OK` |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | `Success: no issues found in 517 source files` (mismos ficheros que `v2.88.26`) |
| `uv run python -m pytest packages/py/application/tests -q` | **2299 passed** (`v2.88.26` tenía **2293**: **+6** de este sello) |
| `uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py packages/py/application/tests/test_price_source_kind.py -q` | **38 passed** (23 + 15) |
| `uv run python -m pytest apps/api-python/tests/test_auto_v88_durable_facts.py -q` | **4 passed** |
| `uv run python -m pytest apps/api-python/tests/test_auto_v88_27_durable_facts_recovery.py -q` | **8 passed** (nuevo, hermético) |
| `uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q` | **21 passed** |
| `uv run python -m pytest apps/api-python/tests/test_auto_v2_worker_integration.py -q` | **38 passed** |
| `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q` | **13 passed** (PG real; head `048`) |
| `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_auto_v88_27_durable_facts_idempotent_pg.py -q` | **3 passed** (PG real; `append` repetido ⇒ 1 fila · sin clave ⇒ 2 filas · roundtrip `047→048→head`) |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK — openapi.json y schema.d.ts coinciden con el commit.` |
| `uv run alembic heads` (en `packages/py/infrastructure`) | `048_journal_entry_dedupe_key (head)` |
| **CI de tag** — `Release tag CI` run [`37006426124`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37006426124) (`ref=refs/tags/v2.88.27-beta`, HEAD `5b650676`, `2026-10-02T12:23:50Z → 12:31:15Z`) | **`SUCCESS`**: 11 jobs `success` + `playwright (integrated E2E, opt-in)` `skipped` por diseño, `certify` `success`. Job `python`: `4302 passed, 42 skipped, 7 warnings in 136.40s` (`v2.88.26` = `4288 passed, 42 skipped` ⇒ **+14**, mismos `42` skips); `lifecycle-pg` **VERDE**; `replay-repro` → `VEREDICTO REPRODUCIDO`, `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` / `3340728 B`, **2ª corrida IDÉNTICA** ⇒ `Δ motor = 0` |

> Nota de honestidad: la corrida local de `apps/api-python/tests` completa (contra PG real) reportó **5 fallos** que **no** son de este sello — 4 desaparecen al re-ejecutarlos en aislamiento (tests de caos/concurrencia: `chaos/live_a7`, `test_lifecycle_outbox_worker_pg`, `test_migration_039_roundtrip` por *deadlock* de procesos residuales, `test_workspaces_crud`) y el quinto (`test_tax_report.py::test_tax_report_after_round_trip_trade`, `403`) **falla idénticamente en el árbol PRE-cambio** (`git stash` + re-run). El job `python`/`lifecycle-pg` del CI es quien certifica.

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **Sin backfill.** Los hechos previos quedan con `dedupe_key = NULL` (índice parcial ⇒ no colisionan) y **no** se reescriben.
2. **`ENTRY_ORDER` sin recuperación de AUSENCIA** (sí exactly-once). El *intent* de orden (`order_id`, `requestedQty`, `partial`) no es durable hoy: un crash entre la materialización y la emisión deja un hueco de **observabilidad**, no financiero (los fills y la posición ya son durables). Cerrar la ausencia exige persistir el intent en un sello posterior.
3. **`PROTECTION` sin recuperación de transiciones** (sólo exactly-once): no hay histórico de transiciones que re-derivar; sólo la proyección viva es reconstruible.
4. **La ventana de recuperación acota el trabajo de arranque** (`_DURABLE_FACTS_RECOVERY_CYCLES`): el ciclo que quede fuera no se pierde — se sella al reabrirse o en el siguiente arranque, y mientras tanto el monitor lo declara `settlement_not_durable`.
5. **`Δ decisión motor = 0`.** Sin `AUTO_OPERATIONAL_AUDIT` (default OFF) no se construye sink ni lector, no corre la recuperación, `append` usa el INSERT plano y la columna es `NULL`; no se toca ningún umbral ni la lógica de entrada/salida.
6. **`PROJECT_STATE.md`/`engineering-index` no se tocan** (mismo criterio que `v2.88.25`/`v2.88.26`).

---

## 4. Comandos (reproducir)

```bash
uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py -q
uv run python -m pytest packages/py/application/tests/test_price_source_kind.py -q
uv run python -m pytest apps/api-python/tests/test_auto_v88_durable_facts.py -q
uv run python -m pytest apps/api-python/tests/test_auto_v88_27_durable_facts_recovery.py -q
uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q
uv run python -m pytest apps/api-python/tests/test_auto_v2_worker_integration.py -q
AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q   # exige PG real
AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_auto_v88_27_durable_facts_idempotent_pg.py -q   # exige PG real
pnpm --filter @bolsa/web contract:check
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
uv run alembic heads   # en packages/py/infrastructure
```

---

## 5. Sello

- **Versión:** `2.11.27-beta` (base `2.11.26-beta`); **CON migración** — Alembic head `047_fill_price_source` → `048_journal_entry_dedupe_key`.
- **Ficheros de producto:** `packages/py/domain/src/bolsa_domain/entities/cognitive_artifacts.py` (`dedupe_key`), `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py` (columna), `packages/py/infrastructure/alembic/versions/048_journal_entry_dedupe_key.py` (**nueva**), `.../database/repositories/journal_repository.py` (`append` idempotente), `packages/py/application/src/bolsa_application/auto_operational_audit.py` (`durable_fact_dedupe_key`), `.../price_source_kind.py` (`canonical_price_source`, `price_source_snapshot_disagrees`), `.../sim_durable_store.py` (`list_recent_cycle_ids`), `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (sellado de `dedupe_key`, `build_durable_fact_cycle_reader`, `_v2_recover_durable_facts`, `settlement_snapshot_from_fills`) + tests + docs + CI.
- **Cita del CI:** `Release tag CI` run [`37006426124`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37006426124) (`ref=refs/tags/v2.88.27-beta`, HEAD `5b650676`, `2026-10-02T12:23:50Z → 12:31:15Z`) → **`SUCCESS`**: **11 jobs `success`** (`security`, `decision-spine`, `python`, `replay-repro`, `dr-verify`, `a7-gate`, `frontend`, `lifecycle-pg`, `shared`, `playwright (mock E2E)`, `certify`) + `playwright (integrated E2E, opt-in)` `skipped` por diseño, **`certify` `success`**. Job `python`: `All checks passed!` · `Contracts: 4 kept, 0 broken.` · `mypy no issues found in 517 source files` · **`4302 passed, 42 skipped, 7 warnings in 136.40s`** (`v2.88.26` = `4288 passed, 42 skipped` ⇒ **+14**, mismos `42` skips). `lifecycle-pg` **VERDE** con gates *fail-if-skipped* (incluido el nuevo PG de idempotencia). `replay-repro` → `VEREDICTO REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)` con `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` / `3340728 B` (**idéntico a `v2.88.25`/`v2.88.26`**), **2ª corrida IDÉNTICA** ⇒ **`Δ motor = 0` confirmado en el runner.**
