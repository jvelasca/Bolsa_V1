# Evidencia `v2.88.79-beta` — `AUTO · UI`: **«¿Qué está haciendo?» con telemetría real**

**Producto:** `V2.88.79-beta` · **Package:** `2.11.79-beta` · **AsOf:** 2026-10-06. **Con migración** `051_auto_engine_activity`. **Contrato HTTP con cambio** (`currentActivity` + `currentActivityMeasurement`). **Motor financiero sin cambio**; el worker se toca SOLO para emitir telemetría. **Sin tag.** El tag anotado `v2.88.76-beta` no se mueve.

**Padre de producto:** [`v2.88.78`](../v2.88.78/README.md).

## Qué cambia

Se cierra la deuda de UI «¿Qué está haciendo AUTO?» con un hecho durable, no con una inferencia.

- Nuevo campo durable `activity` en `auto_engine_runs` (y su traza append-only en `auto_engine_ticks`), emitido por el worker en cada tick vía el helper puro `derive_activity`.
- `derive_activity` mapea SOLO hechos que el motor ya calcula: kill activo → `BLOCKED`; fill/settlement → `APPLYING_RESULT`; orden emitida → `WAITING_EXECUTION`; propuesta que pasó el gate → `PREPARING_OPERATION`; el bucle evaluó símbolos → `ANALYZING`; tick vivo sin nada concreto → `NO_ACTIVITY`.
- El header del monitor expone `currentActivity` + `currentActivityMeasurement` (`COMPLETE`/`UNKNOWN`), con el mismo patrón que `lastDecisionAt`.
- La UI traduce por un conjunto cerrado (`ANALYZING`, `WAITING_SIGNAL`, `PREPARING_OPERATION`, `WAITING_EXECUTION`, `APPLYING_RESULT`, `NO_ACTIVITY`, `BLOCKED`). Fuera del conjunto o ausente → «Sin dato todavía». `NO_ACTIVITY` → «Sin actividad», distinto del hueco.

## Invariantes de honestidad (no negociables)

- Sin hecho durable → «Sin dato todavía»; NUNCA `RUNNING → Analizando`.
- `currentActivity` no contamina `lastActivityLabel`/`nextStepLabel` (la decisión sigue siendo solo `lastDecisionAt`/`nextDecisionAt`).
- Δ motor financiero = 0: no cambia `ExecuteTrade`, ledger, posiciones, ni settlement. Solo se añade telemetría.
- Filas preexistentes sin `activity` (nunca emitido) → «Sin dato todavía» hasta el primer tick tras el deploy.

## Qué no cambia

Núcleo financiero (`ExecuteTrade`, ledger, posiciones, `PortfolioDecision` durable, materialización). El criterio de operación en curso, las cabeceras «Orden pendiente», «Ejecución parcial» y «Precio aplicado», el banner `SIMULACIÓN — DINERO VIRTUAL`, y la separación latido/decisión de `v2.88.78`. El tag `v2.88.76-beta` permanece.

## Verificación

- Python: `derive_activity` (cada fase con su hecho real; sin hecho → `NO_ACTIVITY`), store hermético (read/write de `activity`, `_activity_of` fail-closed), `_header` del monitor (`currentActivity` + medición).
- TS: `activityLabel` (conjunto cerrado, ausente/token desconocido → «Sin dato todavía»), `buildAutoHomeSummary` (no contamina la decisión), `buildAutoBasicHome.doingLabel`, páginas HOME y Sistema.

## Cita POST-TAG

No hay tag de `v2.88.79-beta`. No se inventa un veredicto de `Release tag CI`.
