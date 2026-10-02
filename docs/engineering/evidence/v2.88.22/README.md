# Evidencia cruda — `v2.88.22-beta` (AUTO Operational Monitor · correcciones semánticas de `M1`)

> **Objeto:** tag anotado **`v2.88.22-beta`** · package **`2.11.22-beta`** · Alembic head **`046_fill_reference_mid`** (**SIN migración**) · fecha **2026-10-02**.
> **Clase:** sello de **producto** (`Δ src ≠ 0`) sobre el **read model + contrato + UI** del monitor. **`Δ motor = 0`**: no se toca `auto_simulation_worker.py`. Este incremento **no cambia ninguna decisión de inversión**; sólo corrige **semántica de presentación** para que el monitor no afirme lo que no puede demostrar.
> **Origen:** auditoría de `v2.88.20-beta`/`v2.88.21.1-beta`. El monitor tenía **dos defectos semánticos** y tres etiquetas ambiguas; esta versión los corrige y los fija con tests de contrato.
> **Padres:** [`evidence/v2.88.20/README.md`](../v2.88.20/README.md) (`M1`) · [`evidence/v2.88.21.1/README.md`](../v2.88.21.1/README.md) (`M2` + hotfix).

---

## 0. Qué corrige este sello

| # | Defecto en `M1`/`M2` | Corrección |
|---|---|---|
| **1 🔴** | `SETTLEMENT` se afirmaba `reached` cuando `cycles_from_fills()` calculaba un ciclo cerrado. Un `fill + PnL + ciclo cerrado` **no** demuestra una liquidación durable. | `_settlement_step` sólo alcanza con un **hecho durable explícito** de settlement (`settlements`). Sin él ⇒ `unknown` + `settlement_not_durable`, **sin** facts de PnL (el PnL vive en `CYCLE_CLOSED`). |
| **2 🔴** | `lastDecisionAt` usaba `engine.last_tick_at`: un **heartbeat** del motor presentado como "última decisión". | Se separa `lastHeartbeatAt` (latido) de `lastDecisionAt` (último `auto_entry_decision` durable). Sin decisión durable ⇒ `NO MEDIDO`; `nextDecisionAt` sólo se deriva de una decisión medida. |
| **3 🟠** | "Precio real: ON/OFF" inducía a leer "AUTO opera con precio real". | La etiqueta pasa a **"Precio real habilitado"** (SÍ/NO): configuración, **no** fuente usada por la operación. |
| **4 🟠** | "Ticks duros" (`count(AutoEngineTickRow)`) parecía un conteo de eventos operativos. | Se renombra a **"Heartbeats persistidos"** (`heartbeatsPersisted`). |
| **5 🟠** | `duplicateClaims = count(claimed == False)` y `reservationRaces = duplicateClaims`: la carrera se infería del claim perdido. `claimed=False` puede ser invalid/expired/already_released/wrong_state. | Se separan `claimAttempts`, `successfulClaims`, `lostClaims` y `raceConflicts`; **sólo** cuenta como carrera el claim con `payload.conflict is True` declarado por el productor. |

`ENTRY_ORDER`/`ORDER` **sigue** `unknown` (`entry_order_not_durable`): sin fuente durable de la orden de entrada no se falsea. Se refuerza con contrato.

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | Un ciclo cerrado **jamás** produce `SETTLEMENT = reached`; sólo un hecho durable lo alcanza. | Volver a derivar de `closed`/`cycles_from_fills` ⇒ el test muere. | `uv run python -m pytest packages/py/application/tests/test_auto_operational_monitor.py -q` → **20 passed** |
| **C2** | `lastDecisionAt` **no** es `last_tick_at`; `lastHeartbeatAt` sí lo es. Sin decisión durable, `lastDecisionAt = NO MEDIDO` y `nextDecisionAt = null`. | Volver a `last_tick_at` ⇒ el test falla. | idem C1 |
| **C3** | `raceConflicts` sólo cuenta conflictos **declarados** (`payload.conflict`), no `claimed=False`. | Contar todo claim perdido como carrera ⇒ el test falla. | idem C1 |
| **C4** | `ENTRY_ORDER`/`ORDER` sigue `unknown` + `entry_order_not_durable` sin fuente durable. | Materializar una orden de entrada ⇒ el test falla. | idem C1 |
| **C5** | El productor de claim declara `conflict`/`conflictReason`; un claim perdido no implica carrera. | Omitir la marca ⇒ el test de contrato del productor falla. | `uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py -q` → **7 passed** |
| **C6** | La cadena durable real en PG proyecta `SETTLEMENT = unknown` **pese a ciclo cerrado**, y las métricas de concurrencia separadas. | Persistir/derivar settlement sin hecho ⇒ el test PG falla. | `uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q` → **2 passed** |
| **C7** | La UI pinta `NO MEDIDO` en cada hueco y la etiqueta "Precio real habilitado" = `SÍ (habilitado)`/`NO` (nunca `ON`/`OFF`). | Simplificar la etiqueta ⇒ el test de UI falla. | `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/auto-monitor.test.tsx` → **7 passed** |
| **C8** | El view model puro conserva la honestidad de medición (`NO MEDIDO` ≠ `0`). | Devolver `0`/`—` silencioso ⇒ el test de shared falla. | `pnpm --filter @bolsa/shared exec vitest run src/cognitive/auto-operational-monitor.test.ts` → **10 passed** |
| **C9** | El contrato OpenAPI/`schema.d.ts` coincide con el commit. | Tocar el DTO sin regenerar ⇒ `contract:check` rojo. | `pnpm --filter @bolsa/web contract:check` → `OK` |
| **C10** | `Δ motor = 0`: este sello no toca `auto_simulation_worker.py` ni ninguna decisión. | Incluir cambios del worker ⇒ el diff lo muestra. | `git show --stat` (no lista `auto_simulation_worker.py`) |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | `Success: no issues found in 515 source files` |
| `uv run python -m pytest packages/py/application/tests -q` | **2217 passed** |
| `uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q` | **2 passed** (PG real, **8/8** corridas deterministas) |
| `pnpm --filter @bolsa/shared exec vitest run src/cognitive/auto-operational-monitor.test.ts` | **10 passed** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/auto-monitor.test.tsx` | **7 passed** |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK` |
| `pnpm --filter @bolsa/web typecheck` / `pnpm --filter @bolsa/shared typecheck` | sin errores |

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **No añade productores durables.** `SETTLEMENT`, `ENTRY_ORDER` y (si el flag `AUTO_OPERATIONAL_AUDIT` está OFF) `lastDecisionAt` siguen **`NO MEDIDO`**: es exactamente lo que la auditoría pedía mostrar. Persistir `SETTLEMENT_EVENT` y `ENTRY_ORDER` es trabajo de una fase posterior.
2. **Costura, no implementación, de settlement.** `build_operational_monitor(..., settlements=...)` y `_settlement_step` ya consumen un hecho durable, pero `read_operational_monitor` **no** lee todavía ninguna fuente (no existe). El paso se declara.
3. **Fuente de precio por operación ausente.** "Precio real habilitado" corrige la etiqueta, pero **no** hay aún un campo por ciclo/fill que diga `XTB`/`MARKET_CLOSE`/`REPLAY`/`SYNTHETIC`. Se declara pendiente; no se inventa.
4. **`activeSessions` sigue siendo un SUELO**, no un censo vivo (sin productor de latido durable).
5. **No cierra `P3-2`/`P3-3` ni las compuertas `G1`–`G7`.** Sin migración: Alembic head sigue en `046_fill_reference_mid`.
6. **Test PG estabilizado (test-only):** `_seed_fill` usa ahora `execution_id` determinista (`...-buy`/`...-sell`) porque el store sella `created_at` con `_now()` y `cycles_from_fills` empareja por `(created_at, execution_id)`: con ids aleatorios, una venta podía leerse antes de su compra y descartar el ciclo (**flaky pre-existente**, ~50 %). Se mide **8/8** verde tras el arreglo. No cambia producto.

---

## 4. Comandos (reproducir)

```bash
uv run python -m pytest packages/py/application/tests/test_auto_operational_monitor.py -q
uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py -q
uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q
uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q   # exige PG real
pnpm --filter @bolsa/shared exec vitest run src/cognitive/auto-operational-monitor.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/auto-monitor.test.tsx
pnpm --filter @bolsa/web contract:check
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
```

---

## 5. Sello

- **Sello**: commit [`e904ad3f`](https://github.com/jvelasca/Bolsa_V1/commit/e904ad3f39466eac9011a667b7e7518bd5a60201) + tag anotado `v2.88.22-beta` (tag object `0ca503c0`, sobre `v2.88.21.1-beta`); package `2.11.22-beta`.
- **CI del tag**: **TODO VERDE** — [`Release tag CI` run `36972156676`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36972156676) (`2026-10-02T06:08:44Z`): **11 jobs `success`** + `playwright` integrado `skipped` por diseño (opt-in); `certify` `success`; `python` **`4193 passed, 42 skipped`** (`ruff` `All checks passed!`; `mypy` `no issues found in 515 source files`); **`lifecycle-pg` VERDE** con `AUTO_CONCURRENT_PG_REQUIRED=1` (**176** + **45** + 1 + 1 + 3 + 2 + 2 + **1** `passed`, sin skips silenciosos).
- **`replay-repro`**: `REPRODUCIDO` — SHA-256 **`1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7`** (`3340728` bytes de contenido; sello en CRLF `3445622` · mismo contenido en LF) ⇒ con `Δ motor = 0` el artefacto OOS **no se mueve**, tal como se declaró.
