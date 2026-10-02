# Evidencia cruda — `v2.88.23-beta` (AUTO Operational Monitor · cierre de nueve grietas del contrato `M2`)

> **Objeto:** package **`2.11.23-beta`** · Alembic head **`046_fill_reference_mid`** (**SIN migración**) · fecha **2026-10-02**.
> **Clase:** sello de **producto** sobre el **read model + la auditoría + el contrato** del monitor AUTO. **`Δ decisión motor = 0`**: ninguna decisión de inversión cambia. `auto_simulation_worker.py` SÍ aparece en el diff, pero **sólo** en el tramo de **trazado** `_v2_journal_entry_decisions` (sella `account_id` cuando el productor no lo trae); con `AUTO_OPERATIONAL_AUDIT` OFF (default) ese tramo es un no-op ⇒ `Δ = 0` por defecto.
> **Origen:** auditoría externa de `v2.88.22-beta` (hallazgos §5, §6 y §7 del informe MIA) + dos re-pasadas de auditoría sobre el propio sello. Nueve grietas del contrato `M2`:
> (a) el productor de claim volvía a convertir `claimed=False` en carrera; (b) los contadores de concurrencia podían declararse `COMPLETE` estando truncados por `limit`; (c) `lastDecisionAt` dependía de los ciclos/reservas visibles; (d) `forcedReleases` era el MISMO truncamiento que (b) pero en la ventana de reservas; (e) la UI no distinguía `PARTIAL` de `COMPLETE`; (f) un hecho sin valor se rotulaba `MEDIDO`; (g) el fallback de concurrencia no degradaba `raceConflicts`; (h) un `side` no clasificable se descartaba en silencio; (i) la ventana de fills podía truncar sin declararlo.
> **Padre:** [`evidence/v2.88.22/README.md`](../v2.88.22/README.md).

---

## 0. Qué corrige este sello

| # | Grieta en `M2` | Corrección |
|---|---|---|
| **1 🟠** | `build_reservation_claim_entry` hacía `resolved_conflict = (not claimed) if conflict is None else bool(conflict)` y fabricaba `conflictReason="duplicate_claim"`. Todo claim perdido se volvía a declarar como carrera. | `conflict` ausente viaja **NO DECLARADO**: `None` + `conflictMeasurement = UNKNOWN`, sin motivo inventado. Sólo quien **demostró** la carrera emite `conflict=True` (COMPLETE). |
| **2 🟠** | `read_operational_monitor` cargaba `max(limit*10, 100)` filas y **descartaba** el total de `list_entries`; contaba la página y la declaraba `COMPLETE`. | Nuevo agregado `SqlAlchemyJournalRepository.aggregate_auto_operational_audit` (`COUNT(*) FILTER`, JSONB `->>`). Los contadores salen del **universo completo**. `raceConflicts` se declara **PARTIAL** si hay claims perdidos sin `conflict` declarado. Sin agregado ⇒ fallback a filas usando el total, con desglose **PARTIAL** cuando `len(rows) < total`. |
| **3 🟠** | `lastDecisionAt` se derivaba del `journal` filtrado por los `decision_id` de las reservas visibles: sin reservas ⇒ `NO MEDIDO` aunque hubiera una decisión durable. | Consulta **global independiente** `account_id + event_type=auto_entry_decision + created_at DESC` (`limit=1`). El tramo de trazado sella `account_id` en las entradas `auto_entry_decision` (el productor no lo traía). `lastConflict` sólo desde `conflict is True`. |
| **4 🟠** | `forcedReleases` se contaba sobre la ventana de reservas (`limit`) y se declaraba `COMPLETE` fijo: mismo defecto que (2), en reservas. | Agregado `ReservationStore.count_forced_releases` (`COUNT(*)` sobre `release_reason IN (...)`, universo completo, sin filtrar por ciclo). Sin agregado ⇒ ventana + **PARTIAL** si `len == limit`. |
| **5 🟠** | La UI no distinguía `PARTIAL` de `COMPLETE`: coloreaba por "hay valor". | El panel de concurrencia rotula `N · PARCIAL` en ámbar cuando `measurement = PARTIAL` (también en `lastConflict`). |
| **6 🔴** | Un hecho SIN valor se rotulaba `MEDIDO`: `_fact(...)` nacía `COMPLETE` con `value=None` y la UI devolvía `MEDIDO` para `null`. | `_fact` deduce la medición del valor (sin valor ⇒ `UNKNOWN`); `formatMonitorFactValue` degrada `COMPLETE`+`null` a `NO MEDIDO`. |
| **7 🟠** | El fallback de concurrencia no degradaba `raceConflicts` a `PARTIAL` ante un claim perdido sin `conflict` (el agregado sí). | La ruta de filas calcula los conflictos no declarados y declara `PARTIAL`, igual que el agregado. |
| **8 🟠** | Un `side` no clasificable se descartaba en silencio (no entraba en el neto ni en los buckets) y `FILL` se declaraba `COMPLETE`. | Se cuenta aparte: `FILL` ⇒ `PARTIAL` + nota `fill_side_undeclared`, buckets `PARTIAL`, y **no** se afirma `closed` sobre un neto incompleto. |
| **9 🟠** | La ventana de fills (`max(limit*50, 200)`) podía truncar y `FILL` se declaraba `COMPLETE`. | Si `len(fills) == limit`, el paso `FILL` declara `PARTIAL` + nota `fill_window_truncated`. |

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | Un claim perdido **sin** `conflict` declarado NO es carrera: `conflict = None` + `conflictMeasurement = UNKNOWN`, sin `conflictReason`. | Volver a derivar `conflict = not claimed` ⇒ el test del productor falla. | `uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py -q` |
| **C2** | `conflict=True`/`False` explícitos ⇒ `conflictMeasurement = COMPLETE` y, con `True`, su motivo. | Degradar la medición ⇒ el test falla. | idem C1 |
| **C3** | Los contadores de concurrencia salen del **agregado** y NO dependen del `limit` (347 ≠ 100). | Volver a contar la página ⇒ el test puro y el PG fallan. | `test_concurrency_uses_aggregate_counts_independent_from_row_window` + PG `test_monitor_claim_counts_come_from_the_aggregate_not_the_page` |
| **C4** | `raceConflicts` es **PARTIAL** cuando hay claims perdidos sin `conflict` declarado. | Declararlo `COMPLETE` ⇒ el test falla. | idem C3 |
| **C5** | Sin agregado, `claimAttempts` usa el total de `list_entries` y el desglose es **PARTIAL** si `len(rows) < total`. | Declarar `COMPLETE` truncado ⇒ el test falla. | idem C3 |
| **C6** | `lastConflict` sólo se lee de `conflict is True`; PARTIAL si la ventana está truncada. | Volver a `claimed is False` ⇒ el test falla. | `uv run python -m pytest packages/py/application/tests/test_auto_operational_monitor.py -q` |
| **C7** | `lastDecisionAt` sale de la lectura GLOBAL, no de los ciclos visibles; sin lectura global cae al journal del ciclo. | Depender de las reservas ⇒ el test falla. | idem C6 |
| **C8** | El tramo de trazado **sella** `account_id` cuando falta y **no** reescribe el resto del hecho. | No sellar ⇒ la lectura global no encuentra nada; el test del seam falla. | `uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q` |
| **C9** | La cadena durable real en PG: `lastDecisionAt` global medido y conteos completos pese a página truncada. | Derivar de la página ⇒ el test PG falla. | `uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q` (PG real) |
| **C10** | El contrato OpenAPI/`schema.d.ts` no drift (el cambio es de VALOR, no de forma). | Tocar el DTO sin regenerar ⇒ `contract:check` rojo. | `pnpm --filter @bolsa/web contract:check` → `OK` |
| **C11** | `forcedReleases` sale del **agregado** (`count_forced_releases`) cuando está; sin agregado es **PARTIAL** si la ventana de reservas está llena. | Contar la ventana y declararla `COMPLETE` ⇒ el test puro y el PG fallan. | `test_concurrency_forced_releases_*` + PG `test_monitor_forced_releases_come_from_the_aggregate` |
| **C12** | La UI rotula `PARCIAL` (y no `COMPLETE`) cuando `measurement = PARTIAL`, conservando el valor como suelo. | Colorear por "hay valor" ⇒ el test de UI falla. | `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/auto-monitor.test.tsx` |
| **C13** | Un hecho SIN valor nunca es `COMPLETE`: `PROTECTION`/`RESERVATION` con `None` ⇒ `UNKNOWN`, y la UI lo rotula `NO MEDIDO`. | Volver a `_fact(..., COMPLETE)` fijo ⇒ el test puro y el de shared fallan. | `test_facts_without_value_are_never_declared_measured` + shared `formatMonitorFactValue(null, "COMPLETE")` |
| **C14** | El fallback de concurrencia declara `raceConflicts` `PARTIAL` ante un claim perdido sin `conflict` (paridad con el agregado). | Dejarlo `COMPLETE` ⇒ el test puro falla. | `test_fallback_marks_race_partial_on_undeclared_conflict` |
| **C15** | Un `side` no clasificable hace `FILL` `PARTIAL` (nota `fill_side_undeclared`), no se descarta en silencio. | Volver a filtrar sin declarar ⇒ el test puro falla. | `test_fill_with_unclassifiable_side_is_declared_partial_not_dropped` |
| **C16** | Con la ventana de fills llena el paso `FILL` se declara `PARTIAL` (nota `fill_window_truncated`). | Declararlo `COMPLETE` truncado ⇒ el test puro falla. | `test_fill_window_full_is_declared_partial` |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | `Success: no issues found in 515 source files` |
| `uv run python -m pytest packages/py/application/tests -q` | **2233 passed** (`v2.88.22` tenía **2217**: **+16** de este sello) |
| `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q` | **14 passed** (PG real; 4 del monitor + 10 del seam) |
| `pnpm --filter @bolsa/shared exec vitest run src/cognitive/auto-operational-monitor.test.ts` | **11 passed** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/auto-monitor.test.tsx` | **8 passed** |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK` |

Compilación del agregado contra el dialecto PostgreSQL (sin BD):

```sql
SELECT count(*) FILTER (WHERE event_type = 'auto_reservation_claim') AS "claimAttempts",
       count(*) FILTER (WHERE event_type = 'auto_reservation_claim'
                          AND (payload ->> 'claimed') = 'true') AS "successfulClaims",
       count(*) FILTER (WHERE event_type = 'auto_reservation_claim'
                          AND (payload ->> 'claimed') = 'false'
                          AND (payload ->> 'conflict') IS NULL) AS "lostClaimsUndeclaredConflict", ...
FROM decision_journal_entries
WHERE account_id = :account_id
```

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **Sin backfill.** Las filas `auto_entry_decision` escritas **antes** de este sello no tienen `account_id` (el productor no lo traía) y por tanto **no entran** en la lectura global: `lastDecisionAt` global se puebla a partir de la próxima decisión trazada. No hay migración ni reescritura de historia.
2. **`SETTLEMENT`/`ENTRY_ORDER` siguen `NO MEDIDO`.** Este sello no añade productores durables; sigue siendo deuda declarada (no se cierra aquí).
3. **`activeSessions` sigue siendo un SUELO** (sin productor de latido durable).
4. **Costura de settle/reconciliación intacta:** el agregado sólo **cuenta**; no introduce estado ni escribe.
5. **`Δ` del motor de decisión = 0.** El único cambio en `auto_simulation_worker.py` está en `_v2_journal_entry_decisions` (sello de `account_id`), inerte sin `AUTO_OPERATIONAL_AUDIT` encendido.
6. **No cierra `P3-2`/`P3-3` ni las compuertas `G1`–`G7`.** Sin migración: Alembic head sigue en `046_fill_reference_mid`.
7. **`heartbeatsPersisted` no está acotado por cuenta (límite declarado).** Se cuenta por `engine_id` y `AutoEngineTickRow` **no tiene `account_id`**: es telemetría del motor, no un censo de la cuenta. No es arreglable sin migración ⇒ se declara, no se finge por cuenta.

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

- **Versión:** `2.11.23-beta` (base `2.11.22-beta`); **SIN migración** (Alembic head `046_fill_reference_mid`).
- **Ficheros de producto:** `packages/py/application/src/bolsa_application/auto_operational_audit.py`, `.../auto_operational_monitor.py`, `.../reservation_store.py`, `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/journal_repository.py`, `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (tramo de trazado), `packages/shared/src/cognitive/auto-operational-monitor.ts`, `apps/web/src/features/auto-monitor/auto-concurrency-panel.tsx` + tests + docs.
- **Cita del CI:** `Release tag CI` run [`36978174405`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36978174405) (`ref=refs/tags/v2.88.23-beta`, HEAD `b92744f8`, `2026-10-02T07:22:01Z → 07:30:24Z`) → **`SUCCESS`**: **11 jobs `success`** + `playwright (integrated E2E, opt-in)` `skipped` por diseño, **`certify` `success`**. Job `python`: `All checks passed!` · `Contracts: 4 kept, 0 broken` · `mypy no issues found in 515 source files` · **`4211 passed, 42 skipped, 7 warnings in 102.49s`** (`v2.88.22` = `4193 passed, 42 skipped` ⇒ **+18**, mismos `42` skips). `lifecycle-pg` **VERDE** con gates *fail-if-skipped*. `replay-repro` → `VEREDICTO REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)` con `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` / **3340728 B** (LF; sello `3445622 B`) y **2ª corrida IDÉNTICA** ⇒ el artefacto OOS **no se mueve** (`Δ motor = 0` medido en el runner).
