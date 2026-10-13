# Deuda declarada — cierre del recorrido funcional de DÍA-D (`H3`·`H5`·`H6`)

> **Fecha:** 2026-10-13 · **Base:** `v2.11.124-beta` (árbol con trabajo no commiteado de `v2.88.123`/`v2.88.124`).
> **Naturaleza (1ª pasada, `v2.88.125`):** **SOLO DECLARACIÓN** (Δ motor = 0 · Δ decisión = 0 · sin migración).
> Estos tres huecos eran **contrato/UX con blast radius mayor** y NO se implementaron en ese incremento.
> **Contexto:** cierre del **paso 3** del veredicto de auditoría («recorrido funcional de DÍA-D:
> señales de entrada/salida, cierre, razones, P&L conciliado y acceso manual desde la app»).
> `H1` (motivo de cierre durable, ya corregido), `H2`/`H7` (verificación por valor y ciclo) y `H4`
> (la etapa `DECISION` consume `reasonCodes`) **sí** se implementaron; ver la entrega del sello.
> **Regla dura respetada:** no se toca umbral/`reparto`/`TOP_N`/`régimen`/selección/protección/ejecución.
>
> **2ª pasada (2026-10-13) — `H5` y `H6` RESUELTOS (sello `2.11.126-beta` / tag `v2.88.126-beta`).** Sobre la base anterior se implementaron los dos
> huecos de **contrato/UX**: **`H6`** (el CTA «Verificar D→hoy» verifica la estrategia **EJECUTADA**
> del ciclo, no el #1) y **`H5`** (el monitor admite consulta **por instrumento**). `H5` cambia el
> **contrato HTTP** de forma **aditiva** (`?instrumentId` + `filterInstrumentId`, `contract:gen`/
> `contract:check` ✅) y el read-model; `H6` es **UI/shared puro** (`Δ contrato = 0`). **`Δ decisión = 0`**,
> **sin migración** (head `053_dia_d_cycle_verifications`). **`H3`** (etapa `EXIT` propia) **sigue
> ABIERTO** (exige ratificar el modelo semántico; fuera del alcance de esta pasada). El detalle y el
> mapeo criterio→test están en cada sección.

---

## H3 — la «señal de SALIDA» no tiene etapa propia (está plegada en `SETTLEMENT`) · **ABIERTO**

**Dónde:** `packages/shared/src/cognitive/auto-operation-story.ts:279-287` (`id: "EXIT"`,
`kind: "DERIVED"`, `sourceStepId: "SETTLEMENT"`, `foldedInto: "SETTLEMENT"`).

**Qué falta:** la **intención/motivo** de salida (`time_exit`/`thesis_exit`/…) no se materializa
como fila independiente del modelo semántico; se pliega visualmente en la liquidación. El hecho
durable existe (`SETTLEMENT.facts.exitReason`), pero la historia de 14 conceptos no lo expone como
etapa propia.

**Por qué es deuda y no un cambio de este incremento:** desplegar `EXIT` como fila propia cambia la
forma de la historia (14 → 15 conceptos del modelo semántico, `auto-operation-story.ts:24-39`), el
contrato de la UI de tres bloques y sus tests de orden/plegado
(`auto-operation-story.test.ts`, `auto-operation-story-panel.test.tsx`). Requiere ratificar el
modelo semántico antes de tocar la superficie.

**Criterio de aceptación FALSABLE (cuando se aborde):**
1. Dado un ciclo cuyo `SETTLEMENT.facts.exitReason == "time_exit"`, la etapa `EXIT` existe como
   **fila propia** (`foldedInto === null`), `state === "REACHED"`, y su hecho `reason` publica
   `"time_exit"` con medición `COMPLETE`.
2. Dado un ciclo cuyo settlement **no** declara `exitReason`, `EXIT` declara el hueco
   (`reason` `null`/`UNKNOWN`), **nunca** un motivo de relleno ni `"flat"`.
3. `buildAutoOperationStory` mantiene `SELECTION (TOP-N) ≠ DECISION` y no duplica el hecho
   financiero de `SETTLEMENT` (una sola fila `REACHED` por hecho).

---

## H5 — el monitor no admite consulta POR INSTRUMENTO (solo `cycleId`/`limit`) · **RESUELTO**

**Estado: RESUELTO (2ª pasada, 2026-10-13).** El endpoint y el read-model admiten ahora el filtro
por instrumento, **aditivo** y sin migración.

**Cambios (implementación):**
- **Contrato HTTP (aditivo).** [`auto_operational_monitor.py`](../../apps/api-python/src/bolsa_api/api/v1/routes/auto_operational_monitor.py):
  nuevo query `instrumentId` (`alias="instrumentId"`, `max_length=128`) y campo aditivo
  `filterInstrumentId` en `AutoOperationalMonitorDto` (eco honesto del filtro aplicado). OpenAPI +
  `schema.d.ts` regenerados (`contract:gen`); `contract:check` ✅.
- **Read-model.** [`auto_operational_monitor.py`](../../packages/py/application/src/bolsa_application/auto_operational_monitor.py):
  `read_operational_monitor(..., instrument_id=…)` acota la ventana de reservas a ese valor
  (**`cycle_id` MANDA**: si ambos llegan, se ignora el filtro) y `build_operational_monitor`
  declara `filterInstrumentId` + nota `filter_instrument_empty` cuando el filtro deja `cycles == []`.
- **Store.** [`reservation_store.py`](../../packages/py/application/src/bolsa_application/reservation_store.py):
  `list_recent_with_cycle(..., instrument_id=None)` en Protocol + InMemory + Postgres; `None`
  conserva el comportamiento previo **byte a byte**. **Sin índice nuevo / sin migración.**

**Criterio de aceptación FALSABLE (cumplido):**
1. `GET /auto/operational-monitor?instrumentId=<id>` devuelve **solo** ciclos de ese instrumento;
   con un `instrumentId` sin ciclos devuelve `cycles == []` (lista vacía honesta, no global).
2. Coexiste con `cycleId` sin ambigüedad: si ambos se pasan, `cycleId` manda y el ciclo ajeno sigue
   sin heredar hechos (`SIGNAL`/`SETTLEMENT` no `reached`).
3. El contrato gana el parámetro de forma **aditiva** (`contract:check` ✅) y `readOnly` se
   conserva; un `instrumentId` desconocido NO cae a una lectura global.

**Mapeo criterio → test (evidencia):**
- **(1)** [`test_auto_operational_monitor_pg.py::test_monitor_filters_by_instrument_and_declares_the_filter`](../../apps/api-python/tests/test_auto_operational_monitor_pg.py)
  (PG real: `instrumentId="AAA"` ⇒ solo el ciclo AAA; `"ZZZ"` ⇒ `cycles == []` + `filter_instrument_empty`)
  y [`test_portfolio_reservation.py::test_store_recent_with_cycle_filters_by_instrument`](../../packages/py/application/tests/test_portfolio_reservation.py).
- **(2)** El mismo test PG: `cycleId` + `instrumentId` a la vez ⇒ se devuelve el ciclo del `cycleId`.
- **(3)** `contract:check` ✅ + [`test_auto_operational_monitor.py::test_filter_instrument_is_declared_and_empty_is_flagged`](../../packages/py/application/tests/test_auto_operational_monitor.py)
  (eco `filterInstrumentId`, sin filtro ⇒ `None`).

---

## H6 — el CTA manual verifica SIEMPRE el #1 de Finalistas, no la estrategia EJECUTADA del ciclo · **RESUELTO**

**Dónde:**
- `apps/web/src/features/auto/use-auto-operation-strategy.ts:75-79` — resuelve `strategyDefinitionId`
  del **slot #1** del TOP (`[...top.slots].sort((a, b) => a.rank - b.rank)[0]`).
- `apps/web/src/features/auto/auto-operation-strategy.ts:249-257` — `verifyHref` se construye desde
  ese `strategyDefinitionId` del #1.
- `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx:293-311` —
  `startDiaDVerification` lanza la verificación con el `strategyDefinitionId` del #1 y el `rank` del
  #1 (`rank: view.rank ?? 1`), aunque el ciclo declare **otra** estrategia ejecutada
  (`cycle.strategyPresetKey`).

**Estado: RESUELTO (2ª pasada, 2026-10-13).** Decisión de producto fijada: **CTA ÚNICO que verifica
la estrategia EJECUTADA**; si no se puede resolver, el CTA se **deshabilita** y declara el hueco
(no cae al #1 en silencio). `Δ contrato = 0` (solo UI/shared puro).

**Cambios (implementación):**
- [`auto-operation-strategy.ts`](../../apps/web/src/features/auto/auto-operation-strategy.ts):
  nuevo `resolveExecutedStrategySlot(presetKey, top, definition?)` (empareja por **igualdad EXACTA**
  de `presetKey` contra el `strategyType` de **cualquier** slot del TOP); la vista gana
  `executedStrategyDefinitionId/Label/Rank`, `verifyTarget`, `verifyGapReason`, y `verifyHref` pasa
  a exigir **la ejecutada** (fail-closed). El bloque del #1 se conserva como **referencia**.
- [`auto-operation-story-panel.tsx`](../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx)
  (`useDiaDVerifyLaunch`): `startDiaDVerification` precarga la **ejecutada** (`executedStrategyDefinitionId`
  + su `rank` real) con el `cycleId`/`strategyPresetKey`/`strategyVersion` del ciclo. El hook
  [`use-auto-operation-strategy.ts`](../../apps/web/src/features/auto/use-auto-operation-strategy.ts)
  **no** necesitó cambios: ya alimentaba la vista pura con el TOP, la definición del #1 y la
  `presetKey` del ciclo (la resolución de la ejecutada vive en la vista pura).
- [`auto-operation-strategy-card.tsx`](../../apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx):
  nueva línea «Estrategia ejecutada (lo que se verifica)» (`data-testid` + `data-verify-target`) y
  CTA deshabilitado + hueco declarado cuando no se resuelve.

**Criterio de aceptación FALSABLE (cumplido):**
1. Con un ciclo que declara `strategyPresetKey` y un TOP #1 con identidad distinta
   (`data-match="differs"`), el CTA verifica la **estrategia EJECUTADA** del ciclo y la sesión
   DÍA-D LAB queda precargada con esa estrategia.
2. Con `match === "same"` (identidades exactas) el comportamiento no cambia.
3. Con el ciclo **sin** `strategyPresetKey` (hueco), el CTA declara «Sin dato todavía» y no afirma
   ninguna identidad (no cae silenciosamente al #1 sin declararlo).

**Mapeo criterio → test (evidencia):**
- **(1)** [`auto-operation-strategy.test.ts`](../../apps/web/src/features/auto/auto-operation-strategy.test.ts)
  (`differs` ⇒ `executedStrategyDefinitionId` del slot #3, `verifyTarget === "executed"`) y
  [`auto-operation-story-panel.test.tsx`](../../apps/web/src/features/auto-monitor/auto-operation-story-panel.test.tsx)
  (la sesión LAB queda con `strategyDefinitionId` de la ejecutada, `rank` #3 y `cycleId`).
- **(2)** `auto-operation-strategy.test.ts` (ejecutada == #1 ⇒ misma identidad, `match === "same"`).
- **(3)** `auto-operation-strategy.test.ts` (sin `presetKey` ⇒ `verifyTarget === null`, `verifyHref === null`,
  `verifyGapReason` «no declara su estrategia ejecutada») y
  [`auto-operation-strategy-card.test.tsx`](../../apps/web/src/features/auto-monitor/auto-operation-strategy-card.test.tsx)
  (CTA deshabilitado + hueco declarado).

---

## Trazabilidad de los hallazgos resueltos (para no reabrirlos)

- **H1** — `packages/py/application/src/bolsa_application/auto_operational_monitor.py`:
  `_cycle_closed_step(..., exit_reason=...)` publica el `exitReason` durable del settlement (o el
  hueco `null`/`UNKNOWN`), nunca `"flat"`; tests en
  `packages/py/application/tests/test_auto_operational_monitor.py`.
- **H2/H7** — `apps/api-python/tests/test_auto_dia_d_trace_pg.py`: aserta `SETTLEMENT.facts.exitReason`
  (= `time_exit`), `decision.reasonCodes` no vacío y la conciliación **por valor y ciclo** con ≥2
  instrumentos (sin herencia entre valores).
- **H4** — `packages/shared/src/cognitive/auto-operation-story.ts`: la etapa `DECISION` consume
  `cycle.decision.reasonCodes` cuando el hecho durable existe (y declara el hueco cuando no);
  tests en `packages/shared/src/cognitive/auto-operation-story.test.ts`.
