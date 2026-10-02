# Evidencia cruda — `v2.88.26-beta` (AUTO · `PROTECTION` durable: `auto_protection_event`)

> **Objeto:** package **`2.11.26-beta`** · Alembic head **`047_fill_price_source`** (**SIN migración**) · fecha **2026-10-02**.
> **Clase:** sello de **producto** que cierra el **último hueco de la cadena operativa**: hasta ahora el paso `PROTECTION` se encendía con la **proyección** (`sim_auto_positions.position_state`) y no existía traza append-only de las transiciones de protección. El nuevo evento `auto_protection_event` sella *cuándo* y *por qué* cambió el stop, se alcanzó T1/T2, se armó el trailing o se pidió la salida. **`Δ decisión motor = 0`**: el evento va tras el sumidero de auditoría (`AUTO_OPERATIONAL_AUDIT`, default OFF ⇒ no-op) y **no** cambia ninguna decisión ni cálculo.
> **Origen:** hueco declarado en [`evidence/v2.88.25/README.md`](../v2.88.25/README.md) §3.2 (`PROTECTION` seguía siendo estado proyectado, no evento durable).
> **Padre:** [`evidence/v2.88.25/README.md`](../v2.88.25/README.md).

---

## 0. Qué produce este sello

| # | Hueco (hasta `v2.88.25`) | Hecho durable que se produce ahora |
|---|---|---|
| **H1 🔴** | El paso `PROTECTION` se encendía con la **proyección** `position_state`: no había traza append-only de las transiciones (nacimiento, ratchet, T1/T2, armado de trailing, salida pedida). | Evento `auto_protection_event` (builder puro `build_protection_entry`) sellado por `cycle_id`, con `kind` de vocabulario cerrado, `stopBefore`→`stopAfter`, `target`, `lifecycleFrom`→`lifecycleTo`, `revisionId` y `source`. |
| **H2 🔴** | Sin hecho durable, `PROTECTION` afirmaba `reached` sobre estado **no comprobado**. | `_protection_step` pasa a **durable-only**: sin evento ⇒ `unknown` con `protection_not_durable` y facts proyectados `UNKNOWN`; con evento ⇒ `reached` con la última transición + la proyección viva. |

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | El `kind` del hecho durable sólo admite el vocabulario canónico (eventos del FSM + `reason codes` de gestión + la extensión `T2_HIT`); cualquier otro literal se coacciona a `None` (no medido). | Aceptar un literal inventado ⇒ `test_protection_event_kind.py` falla. | `packages/py/application/tests/test_protection_event_kind.py` (**20 passed**) |
| **C2** | `T2_HIT` es una **extensión declarada**: NO se añade a `PositionLifecycleEvent` ni a la tabla de transiciones del FSM. El FSM es el mismo. | Añadirlo al FSM ⇒ el producto cartesiano de `test_position_lifecycle.py` cambia. | `packages/py/analytics/tests/test_position_lifecycle.py` (sin cambios) |
| **C3** | El builder es **fail-closed**: sin `cycle_id`/`instrument_id` ⇒ `None`; un `kind` ajeno ⇒ `None`; un stop ausente ⇒ `None` (jamás un `0`). | Rellenar con un literal/`0` ⇒ `test_auto_operational_audit.py` falla. | `packages/py/application/tests/test_auto_operational_audit.py` (**19 passed**) |
| **C4** | Sin hecho durable, `PROTECTION` se declara `unknown` con `protection_not_durable` y TODOS sus facts proyectados viajan `UNKNOWN`. | Encenderlo desde la proyección ⇒ `test_auto_operational_monitor.py` falla. | `packages/py/application/tests/test_auto_operational_monitor.py` (**49 passed**) |
| **C5** | Con el hecho durable, `PROTECTION` se enciende (`reached`) y expone `kind`, `stopBefore`/`stopAfter`, `target`, `lifecycleFrom`→`lifecycleTo`, `revisionId`, `source` + la proyección viva (`COMPLETE`). | No exponer la transición ⇒ el test puro falla. | `test_auto_operational_monitor.py` (`test_protection_reached_from_durable_event_and_exposes_the_transition`) |
| **C6** | Con varias transiciones en un ciclo, el paso expone la **más reciente por instante** (no por orden accidental de la lista). | Quedarse con la primera ⇒ el test falla. | `test_auto_operational_monitor.py` (`test_protection_keeps_the_latest_transition_of_the_cycle`) |
| **C7** | Si el último `kind` es una salida pedida (`EXIT_REQUESTED`/`PROTECT_REQUESTED`), se declara `protection_exit_requested_without_materialization`. | Ocultar la nota ⇒ el test falla. | `test_auto_operational_monitor.py` |
| **C8** | El productor sella `account_id`/`payload.engineId`; sin `cycle_id` es un no-op declarado; un sink roto **no** tumba el turno. | Emitir sin ciclo / dejar que el fallo propague ⇒ `test_auto_m2_operational_audit_seam.py` falla. | `apps/api-python/tests/test_auto_m2_operational_audit_seam.py` (**21 passed**) |
| **C9** | El nacimiento de la protección en el turno V2 sella `PROTECT_APPLIED` (`source=plan`) con el stop del plan y el `cycleId` de la posición. | No emitirlo ⇒ `test_auto_v2_worker_integration.py` falla. | `apps/api-python/tests/test_auto_v2_worker_integration.py` (**38 passed**) |
| **C10** | **`Δ decisión motor = 0`**: con y sin sumidero la posición abierta es idéntica; el flag ON sólo añade traza. | Cambiar la decisión ⇒ `test_v2_protection_sink_does_not_change_the_engine` falla. | `test_auto_v2_worker_integration.py` |
| **C11** | En PG real, con el evento `PROTECTION` alcanza; sin él degrada a `unknown` + `protection_not_durable`. | No cablear el `journal` ⇒ el PG falla. | `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 … test_auto_operational_monitor_pg.py` (**13 passed**) |
| **C12** | **SIN migración**: Alembic head sigue `047_fill_price_source`; el hecho vive en el JSONB `decision_journal_entries`. | Añadir una migración ⇒ el head cambia. | `uv run alembic heads` → `047_fill_price_source (head)` |
| **C13** | El contrato no drifta: los facts del monitor son genéricos `{key,value,measurement}`; `openapi.json`/`schema.d.ts` sin cambios. | Tocar el DTO sin regenerar ⇒ `contract:check` rojo. | `pnpm --filter @bolsa/web contract:check` → `OK` |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | `Success: no issues found in 517 source files` (`v2.88.25` = 516; **+1** = `protection_event_kind.py`) |
| `uv run python -m pytest packages/py/application/tests -q` | **2293 passed** (`v2.88.25` tenía **2265**: **+28** de este sello) |
| `uv run pytest packages/py/application/tests/test_protection_event_kind.py packages/py/application/tests/test_auto_operational_audit.py packages/py/application/tests/test_auto_operational_monitor.py -q` | **88 passed** (20 + 19 + 49) |
| `uv run pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q` | **21 passed** (`v2.88.25` = 17; **+4**) |
| `uv run pytest apps/api-python/tests/test_auto_v2_worker_integration.py -q` | **38 passed** (**+3**) |
| `uv run pytest apps/api-python/tests/test_auto_v88_durable_facts.py -q` | **4 passed** |
| `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q` | **13 passed** (PG real; `v2.88.25` = 11; **+2**) |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK — openapi.json y schema.d.ts coinciden con el commit.` |
| `uv run alembic heads` (en `packages/py/infrastructure`) | `047_fill_price_source (head)` |

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **Sin backfill.** Las posiciones abiertas **antes** de este sello no tienen eventos `auto_protection_event` retrospectivos: `PROTECTION` se declara `protection_not_durable` hasta la próxima transición con el sumidero activo.
2. **La adopción tras reinicio no fabrica una transición.** `_v2_adopt_position` rehidrata el estado durable; el hecho previo (si existía) sigue siendo la evidencia. No se emite un `PROTECT_APPLIED` por el mero reinicio.
3. **`PROTECTION_EXIT` en XTB/live fuera de alcance:** el vocabulario cubre las transiciones del motor SIM actual; no hay productor de venue vivo.
4. **`Δ decisión motor = 0`.** Los emisores van tras `AUTO_OPERATIONAL_AUDIT` (default OFF); no se toca ningún umbral, cálculo de stop ni reparto de fills.
5. **No cierra `P3-2`/`P3-3` ni `G1`–`G7`.** El crash/restart de la cadena completa es `P4`, no este sello.
6. **`PROJECT_STATE.md`/`engineering-index` no se tocan** (mismo criterio que `v2.88.25`: no trackean los sellos recientes).

---

## 4. Comandos (reproducir)

```bash
uv run python -m pytest packages/py/application/tests/test_protection_event_kind.py -q
uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py -q
uv run python -m pytest packages/py/application/tests/test_auto_operational_monitor.py -q
uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q
uv run python -m pytest apps/api-python/tests/test_auto_v2_worker_integration.py -q
uv run python -m pytest apps/api-python/tests/test_auto_v88_durable_facts.py -q
AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q   # exige PG real
pnpm --filter @bolsa/web contract:check
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
uv run alembic heads   # en packages/py/infrastructure
```

---

## 5. Sello

- **Versión:** `2.11.26-beta` (base `2.11.25-beta`); **SIN migración** — Alembic head `047_fill_price_source`.
- **Ficheros de producto:** `packages/py/analytics/src/bolsa_analytics/cognitive/position_lifecycle.py` (constante `T2_HIT`), `packages/py/application/src/bolsa_application/protection_event_kind.py` (**nuevo**), `.../auto_operational_audit.py` (`build_protection_entry`), `.../auto_operational_monitor.py` (`AUTO_PROTECTION_EVENT`, `_protection_step` durable-only, `protection_events`), `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (`_v2_journal_protection` + ganchos) + tests + docs.
- **Cita del CI:** `Release tag CI` run [`36998362582`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36998362582) (`ref=refs/tags/v2.88.26-beta`, HEAD `13e37412`, `2026-10-02T10:57:42Z → 11:05:56Z`) → **`SUCCESS`**: **11 jobs `success`** (`security`, `decision-spine`, `python`, `replay-repro`, `dr-verify`, `a7-gate`, `frontend`, `lifecycle-pg`, `shared`, `playwright (mock E2E)`, `certify`) + `playwright (integrated E2E, opt-in)` `skipped` por diseño, **`certify` `success`**. Job `python`: `All checks passed!` · `Contracts: 4 kept, 0 broken.` · `mypy no issues found in 517 source files` · **`4288 passed, 42 skipped, 7 warnings in 128.18s`** (`v2.88.25` = `4254 passed, 42 skipped` ⇒ **+34**, mismos `42` skips). `lifecycle-pg` **VERDE** con gates *fail-if-skipped*. `replay-repro` → `VEREDICTO REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)` con `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` (**idéntico a `v2.88.25`**), **2ª corrida IDÉNTICA** ⇒ **`Δ motor = 0` confirmado en el runner.**
