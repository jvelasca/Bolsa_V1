# Evidencia cruda — `v2.88.20-beta` (AUTO Operational Monitor · `M1`)

> **Objeto:** tag anotado **`v2.88.20-beta`** · package **`2.11.20-beta`** · Alembic head **`046_fill_reference_mid`** (**SIN migración**) · fecha **2026-10-01**.
> **Clase:** sello de **producto** (`Δ src ≠ 0`), pero **`Δ = 0` sobre la semántica del motor**: este incremento es un **read model + endpoint + UI** que **no** escribe nada en el dominio ni cambia ninguna decisión del motor. No se toca `auto_simulation_worker.py`.
> **Origen:** hallazgo del propietario sobre AUTO `v2.88.19-beta` — la UI sólo mostraba `AUTO = RUNNING`, sin poder reconstruir visualmente el ciclo `SIGNAL → TOP_N → RISK → RESERVATION → ORDER → FILL → PROTECTION → SETTLEMENT → CYCLE CLOSED`. `M1` proyecta **lo que ya era durable**; declara **`NO MEDIDO`** lo que aún no lo es.
> **Padres:** [`evidence/v2.88.19/README.md`](../v2.88.19/README.md) · el hermano **`M2`** es [`evidence/v2.88.21/README.md`](../v2.88.21/README.md).
> **CI del tag:** **[`36903850807`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36903850807)** — **VERDE** (POST-TAG, patrón `OBS-3`/`OBS-4`). Ver §5.

---

## 0. Qué hace `M1` (y qué **no**)

Camino obligatorio respetado: `DOMAIN EVENT → PERSISTED OPERATIONAL STATE → CANONICAL DTO → UI`. La UI **no** interpreta ni re-deriva: pinta el DTO.

| Paso de la timeline | Fuente durable en `M1` | Estado en `M1` |
|---|---|---|
| `SIGNAL` / `TOP_N` / `RISK` | journal de decisión (aún **en memoria**; no durable hasta `M2`) | **`unknown`** declarado |
| `RESERVATION` | `portfolio_reservations` | `reached` |
| `ORDER` | `auto_exit_orders` | `reached` |
| `FILL` | `sim_fill_finance_context` + `execution_events` | `reached` |
| `PROTECTION` | `sim_auto_positions` (`position_state` JSONB) | `reached` |
| `SETTLEMENT` | derivado de `APPLIED` | `UNKNOWN` sin productor |
| `CYCLE_CLOSED` | `cycles_from_fills` (PnL/fees) + `mfeMae` | `reached` |
| ownership de reservas | (no durable en `M1`) | **`NO MEDIDO`** |
| concurrencia (races/claims) | (no durable en `M1`) | **`NO MEDIDO`** |

> **Errata (corregida en [`v2.88.22-beta`](../v2.88.22/README.md)):** el **código** de `M1` afirmaba `SETTLEMENT = reached` en cuanto `cycles_from_fills()` calculaba un ciclo cerrado, contradiciendo esta misma fila (`UNKNOWN` sin productor). `v2.88.22` lo corrige: `SETTLEMENT` sólo alcanza con un hecho durable explícito; sin él viaja `unknown` + `settlement_not_durable`. `lastDecisionAt` dejó de ser `last_tick_at` (heartbeat) y las métricas de concurrencia se separaron. Este texto describe el estado de `M1`; la corrección posterior no reescribe su historia.

**Ficheros del sello:**

- `packages/py/application/src/bolsa_application/auto_operational_monitor.py` (nuevo; `build_operational_monitor` puro + `read_operational_monitor` con I/O).
- `packages/py/application/src/bolsa_application/exit_order_store.py` (`list_by_cycle_ids` en el Protocol, in-memory y PG).
- `apps/api-python/src/bolsa_api/api/v1/routes/auto_operational_monitor.py` (nuevo) + registro en `router.py`.
- `apps/web/api/openapi.json` + `apps/web/src/api/schema.d.ts` (contrato regenerado).
- `apps/web/src/features/auto-monitor/` (página `/auto-monitor`, header, timeline, paneles) + `app.tsx` + `admin-rail.tsx` + `lib/api.ts`.
- `packages/shared/src/cognitive/auto-operational-monitor.ts` (+ test) e `index.ts`.
- `.github/workflows/python-ci.yml` / `release-tag-ci.yml`: el puro del monitor entra por el pase de directorio (ancla explícita en `M2`).

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **A1** | Un paso **sin traza durable** se declara `unknown`/`absent`, **nunca** se rellena con `0`. | Materializar `0`/`100.0` cuando `measurement == UNKNOWN` en un `facts` o en un paso ⇒ el test muere. | `uv run python -m pytest packages/py/application/tests/test_auto_operational_monitor.py -q` → **16 passed** |
| **A2** | El DTO declara en `notes[]` cada hueco (`signal_not_durable`, `owner_session_not_durable`…). | Quitar la nota del ensamblador ⇒ el assert de `notes` falla. | idem A1 |
| **A3** | `SIGNAL`/`TOP_N`/`RISK` en `M1` son `unknown` (no hay productor durable todavía). | Re-derivarlos de los fills (lo que la regla de la casa prohíbe) ⇒ el test de estado falla. | idem A1 |
| **A4** | La UI **no** reordena ni completa pasos: pinta el DTO. | Cambiar el orden de los pasos en el componente ⇒ el test por `data-testid` falla. | `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/auto-monitor.test.tsx` → **7 passed** |
| **A5** | El contrato OpenAPI y `schema.d.ts` coinciden con el commit. | Tocar el DTO sin regenerar ⇒ `contract:check` rojo. | `pnpm --filter @bolsa/web contract:check` → `OK` |
| **A6** | El formateador del view model declara `NO MEDIDO` en vez de un valor por defecto. | Devolver `0`/`—` silencioso ⇒ el test de `format` falla. | `pnpm --filter @bolsa/shared exec vitest run src/cognitive/auto-operational-monitor.test.ts` → **8 passed** |
| **A7** | `M1` **no** toca la semántica del motor (Δ = 0 en `auto_simulation_worker.py`). | Incluir cambios del worker en el commit de `M1` ⇒ la afirmación es falsa y el diff lo muestra. | `git show --stat v2.88.20-beta` (el commit de `M1` **no** lista `auto_simulation_worker.py`) |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | `Success: no issues found in 515 source files` (árbol combinado `M1`+`M2`; el commit de `M1` no añade fuentes a `apps/api-python/src` más allá del endpoint) |
| `uv run python -m pytest packages/py/application/tests/test_auto_operational_monitor.py -q` | **16 passed** |
| `pnpm --filter @bolsa/shared exec vitest run src/cognitive/auto-operational-monitor.test.ts` | **8 passed** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/auto-monitor.test.tsx` | **7 passed** |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK` |

---

## 3. Límites declarados (lo que `M1` **NO** hace)

1. **No cierra el ciclo completo.** `SIGNAL`/`TOP_N`/`RISK` siguen `unknown` porque el journal de decisión AUTO no es durable: eso lo cierra `M2` (`v2.88.21-beta`). Re-derivarlos de los fills aquí violaría la regla de la casa.
2. **Ownership y concurrencia salen `NO MEDIDO`.** No hay productor durable de claims ni de decisiones de reconciliación en `M1`; los paneles existen y lo **declaran**, no lo simulan. Lo cierra `M2`.
3. **Heartbeat durable ausente.** No hay productor de latido de sesión; el header lo declara.
4. **La certificación PG del read model llega con `M2`.** El test `apps/api-python/tests/test_auto_operational_monitor_pg.py` siembra claims/reconciliaciones con los builders de `M2`, así que viaja en el sello hermano. En `M1` el read model se certifica en puro.
5. **No mueve `P3-2`/`P3-3` ni las compuertas `G1`–`G7`.** La app resultante es el **instrumento** que `G4`/`W5` podrán usar.
6. **Sin migración**: Alembic head sigue en `046_fill_reference_mid`.
7. **No habilita `NEXT_BAR_OPEN`** ni certifica precio real / protección OHLC (`W5`).

---

## 4. Comandos (reproducir)

```bash
uv run python -m pytest packages/py/application/tests/test_auto_operational_monitor.py -q
pnpm --filter @bolsa/shared exec vitest run src/cognitive/auto-operational-monitor.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/auto-monitor.test.tsx
pnpm --filter @bolsa/web contract:check
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
```

---

## 5. Sello y CI

- **Sello**: commit `M1` + tag anotado `v2.88.20-beta` (sobre `main`); el hermano `M2` es `v2.88.21-beta` → hotfix `v2.88.21.1-beta`.
- **CI del tag: VERDE (POST-TAG, patrón `OBS-3`/`OBS-4`).** `Release tag CI` run **[`36903850807`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36903850807)** (`ref=refs/tags/v2.88.20-beta`, HEAD `4a3e78f6`) → **`SUCCESS`**. También verdes en la misma ref: `Python CI` `36903851185`, `Frontend CI` `36903850858`, `Optimize lab` `36903850761`, `Fase 2 scientific` `36903850709`. Es decir: **`M1` está verde en su propio tag**, y el rojo de su hermano `M2` (run `36903850433`) es **ajeno** a este incremento — ver [`evidence/v2.88.21.1/README.md`](../v2.88.21.1/README.md).
- **`replay-repro`**: `M1` es read-only sobre el estado durable (no añade ninguna escritura al camino del motor), así que **no puede** mover el artefacto OOS. Medido en el tag del hermano donde el artefacto sí se regenera: `VEREDICTO REPRODUCIDO` (run `36928967231`).
