# Deuda declarada — cierre del recorrido funcional de DÍA-D (`H3`·`H5`·`H6`)

> **Fecha:** 2026-10-13 · **Base:** `v2.11.124-beta` (árbol con trabajo no commiteado de `v2.88.123`/`v2.88.124`).
> **Naturaleza:** **SOLO DECLARACIÓN** (Δ motor = 0 · Δ decisión = 0 · sin migración). Estos tres
> huecos son **contrato/UX con blast radius mayor** y NO se implementan en este incremento.
> **Contexto:** cierre del **paso 3** del veredicto de auditoría («recorrido funcional de DÍA-D:
> señales de entrada/salida, cierre, razones, P&L conciliado y acceso manual desde la app»).
> `H1` (motivo de cierre durable, ya corregido), `H2`/`H7` (verificación por valor y ciclo) y `H4`
> (la etapa `DECISION` consume `reasonCodes`) **sí** se implementaron; ver la entrega del sello.
> **Regla dura respetada:** no se toca umbral/`reparto`/`TOP_N`/`régimen`/selección/protección/ejecución.

---

## H3 — la «señal de SALIDA» no tiene etapa propia (está plegada en `SETTLEMENT`)

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

## H5 — el monitor no admite consulta POR INSTRUMENTO (solo `cycleId`/`limit`)

**Dónde:** `apps/api-python/src/bolsa_api/api/v1/routes/auto_operational_monitor.py:246-264`
(`get_auto_operational_monitor(...)` solo declara `limit` y `cycle_id`); el read-model subyacente
`packages/py/application/src/bolsa_application/auto_operational_monitor.py`
(`read_operational_monitor`, `build_operational_monitor`) también filtra solo por `cycle_id`.

**Qué falta:** no hay forma de pedir «los ciclos DE ESTE valor». El usuario debe conocer el
`cycleId` (o recorrer la ventana) para acotar; el acceso manual «por valor» queda indirecto.

**Por qué es deuda y no un cambio de este incremento:** añadir un parámetro de endpoint es un
cambio de **contrato HTTP** (OpenAPI + `contract:gen`/`contract:check` + tipos shared) y de la
lectura de reservas (nuevo índice/consulta por instrumento). Blast radius de contrato + BD.

**Criterio de aceptación FALSABLE (cuando se aborde):**
1. `GET /auto/operational-monitor?instrumentId=<id>` devuelve **solo** ciclos de ese instrumento;
   con un `instrumentId` sin ciclos devuelve `cycles == []` (lista vacía honesta, no global).
2. Coexiste con `cycleId` sin ambigüedad: si ambos se pasan, `cycleId` manda y el ciclo ajeno sigue
   sin heredar hechos (`SIGNAL`/`SETTLEMENT` no `reached`).
3. El contrato gana el parámetro de forma **aditiva** (`contract:check` ✅) y `readOnly` se
   conserva; un `instrumentId` desconocido NO cae a una lectura global.

---

## H6 — el CTA manual verifica SIEMPRE el #1 de Finalistas, no la estrategia EJECUTADA del ciclo

**Dónde:**
- `apps/web/src/features/auto/use-auto-operation-strategy.ts:75-79` — resuelve `strategyDefinitionId`
  del **slot #1** del TOP (`[...top.slots].sort((a, b) => a.rank - b.rank)[0]`).
- `apps/web/src/features/auto/auto-operation-strategy.ts:249-257` — `verifyHref` se construye desde
  ese `strategyDefinitionId` del #1.
- `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx:293-311` —
  `startDiaDVerification` lanza la verificación con el `strategyDefinitionId` del #1 y el `rank` del
  #1 (`rank: view.rank ?? 1`), aunque el ciclo declare **otra** estrategia ejecutada
  (`cycle.strategyPresetKey`).

**Qué falta:** el CTA «Verificar D→hoy» precarga la **mejor estrategia del valor (Finalistas #1)**,
no la **estrategia EJECUTADA** que declara el ciclo. Cuando divergen (`data-match="differs"`), la
verificación DÍA-D no reproduce la operación real. Es una elección de UX/contrato con blast radius
(¿qué debe verificar el CTA: la ejecutada o la mejor disponible?), no un bug de dato.

**Por qué es deuda y no un cambio de este incremento:** cambiar el destino del CTA altera el
contrato de la sesión DÍA-D LAB (`strategyDefinitionId` precargado, `mode: "auto"`) y su UX; exige
decisión de producto sobre la semántica del botón.

**Criterio de aceptación FALSABLE (cuando se aborde):**
1. Con un ciclo que declara `strategyPresetKey` y un TOP #1 con identidad distinta
   (`data-match="differs"`), el CTA ofrece verificar la **estrategia EJECUTADA** del ciclo (o
   declara explícitamente cuál verifica), y la sesión DÍA-D LAB queda precargada con esa estrategia.
2. Con `match === "same"` (identidades exactas) el comportamiento no cambia.
3. Con el ciclo **sin** `strategyPresetKey` (hueco), el CTA declara «Sin dato todavía» y no afirma
   ninguna identidad (no cae silenciosamente al #1 sin declararlo).

---

## Trazabilidad de los hallazgos resueltos en este incremento (para no reabrirlos)

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
