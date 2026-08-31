# Spec — V1.42 Operating Excellence (contrato)

> **AsOf:** 2026-08-31 · **Estado:** **CONTRATO** — sin código de producto.  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) · [ADR-032](../adr/032-operational-core-tradeplan-positionstate-execution.md) · [ADR-037](../adr/037-mesa-hoy-operational-ux.md) · [ADR-040](../adr/040-user-information-architecture.md) · [ADR-041](../adr/041-operational-coherence.md) · [ADR-042](../adr/042-operating-excellence.md).  
> **Tip certificado:** `v1.41.3-beta` → `a8101ab7` [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33382034705).  
> **Auditoría externa (2026-08-31):** PASS honesty; no más parches de UI; este documento es el salto estructural.

Este fichero es **una** especificación. No hay hojas rivales de «Mercado 2.0 vs Hoy 2.0 vs ExecutionState». El ADR acepta el contrato; la implementación (F1–F8 §D) queda **aparcada** hasta que el owner lo dé por aceptado.

```text
DOMAIN (intocado)
  → authorities existentes
  → proyecciones canónicas
  → UI
```

---

## 0. Propósito

Convertir la capacidad ya existente del backend (tesis ≠ plan ≠ permiso ≠ ejecución) en **una verdad operativa** que Mercado, Hoy, Journal y Operaciones lean igual, y que responda:

**¿Qué hago ahora con este activo?**

No añadir inteligencia. Cerrar el ciclo:

```text
ESTUDIO → ANÁLISIS → OPORTUNIDAD → PLAN → TRIGGER → PROPUESTA
  → CONFIRMACIÓN → ORDEN → FILL → POSICIÓN → PROTECCIÓN
  → T1 → T2 → TRAIL → SALIDA → FILL → CIERRE → JOURNAL
```

Ningún paso debe perder información del anterior.

### 0.1 Freeze (heredado, intacto)

Confirm = firma · Spine intacto · `PAPER_D_EXECUTE` off · AUTO execute off · Ranking ≠ BUY · LLM ≠ execution · `protect_hint` thin ≠ autoridad · sin drag entry/exit · sin motores nuevos · backend operativo (`packages/py` money path / Confirm / AUTO / `POST …/propose`) **intocado** en este slice y en F1–F6 hasta que un plan de código lo abra explícitamente.

### 0.2 Qué no es este documento

- No es un plan de implementación con tipos TypeScript.
- No crea tablas, endpoints, pantallas ni engines.
- No thaw, Lab P2, OCO, OpportunityScore, nav L1 nueva.

### 0.3 Germen en código (no reinventar)

| Pieza viva                                                                                 | Rol hoy                                          | Hueco V1.42                                                              |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------ | ------------------------------------------------------------------------ |
| `EntryOperatingTruth`                                                                      | Pre-posición: fase, plan, CTA, frase, gate       | Maduro                                                                   |
| `resolveMercadoCockpitPhase`                                                               | Allowlist; BLOCKED/EXPIRED/CANCELLED ≠ PREPARADA | Maduro en entrada                                                        |
| `OperationalTruth` + `PositionDecision`                                                    | Posición abierta: niveles, P&L, CTA, recon       | No cubre ciclo de orden ni historia                                      |
| `mapCandidateNextAction` / `mapMesaNextAction`                                             | CTA Mesa/Hoy                                     | `protectionDiscrepancy` gana a `full_exit` — **cambio de contrato** §A.8 |
| `ExitPlan` / `ProtectPlan` / `PositionRevision`                                            | Autoridad / evento post-fill                     | Falta proyección unificada                                               |
| PaperOrder / `DurableSubmitIntent` / OR-2 UNKNOWN                                          | Ejecución durable                                | Falta proyección de lectura `ExecutionState`                             |
| [`test_v127_golden_path.py`](../../packages/py/application/tests/test_v127_golden_path.py) | Confirm → protect → T1 → exit                    | Subconjunto; no los 10 GP de producto                                    |

---

## A. Operating Model

### A.1 Autoridades vs proyecciones

**Autoridad** = decide o persiste (gate, firma, estado durable).  
**Proyección** = lectura canónica para UI. No tabla. No segundo motor.

| Pregunta                        | Autoridad                                    | Proyección de lectura                                     |
| ------------------------------- | -------------------------------------------- | --------------------------------------------------------- |
| ¿Qué creemos?                   | `DecisionPackage`                            | Journal study view                                        |
| ¿Qué haríamos si entramos?      | `TradePlan`                                  | `EntryOperatingTruth`                                     |
| ¿Podemos abrir ahora?           | `check_opening`                              | `gateStatus` en truth (eco, no veto)                      |
| ¿El humano firmó?               | Confirm                                      | fase `propuesta` / `confirmada`                           |
| ¿Existe orden / fill / UNKNOWN? | PaperOrder · SubmitIntent · ledger           | **`ExecutionState`** (nuevo)                              |
| ¿Qué posición hay?              | `PositionState`                              | **`PositionOperatingTruth`** (compone `OperationalTruth`) |
| ¿Cómo salimos / protegemos?     | `ExitPlan` + `ExitPermission`                | misma POT + `ExitRouteView`                               |
| ¿Trail es stop?                 | `currentStop` (solo tras Confirm + revision) | trailing applied vs hint                                  |
| ¿Qué pasó en el tiempo?         | sesiones, fills, revisions, journal          | **`TradeStory`** (nuevo)                                  |
| ¿Qué hago ahora?                | composición de las anteriores                | `nextAction` (una CTA)                                    |

**Prohibido:** OpportunityEngine, ExecutionEngine2, DailyEngine, PositionEngine2, TradeStoryEngine.

### A.2 `entriesBlocked` vs `check_opening`

| Capa             | Rol                       | Qué hace                                                                                                        | Qué no hace                                  |
| ---------------- | ------------------------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| `entriesBlocked` | **UX fail-closed**        | Impide generar propuestas desde superficies (chart, quick trade, alarmas, OrderDialog, Operativa, lista, ficha) | No es veto de fill. No viaja al POST propose |
| `check_opening`  | **Autoridad de apertura** | ALLOW/VETO/DEFERRED de fill (Fit + DS-05 + DS-03 + recon/incidentes server)                                     | No es copy de UI                             |

`POST /ai/recommendations/propose` puede invocarse directo; execute sigue exigiendo Confirm + opening gate. **No modificar el endpoint ahora.** Documentar la distinción basta para mantener la arquitectura limpia.

VETO/DEFERRED de gate en UI → CTA `none` (`Gate en veto` / `Gate diferido`), nunca «Preparar operación».

### A.3 Cadena de proyecciones

```text
                 EXISTENTE
                     │
          ┌──────────┴──────────┐
          │                     │
   EntryOperatingTruth    PositionState
          │               ExitPlan / ProtectPlan
          │               PositionRevision / Recon
          │                     │
          └──────────┬──────────┘
                     ↓
              ExecutionState
                     ↓
         PositionOperatingTruth
           (compone OperationalTruth)
                     ↓
                 TradeStory
                     ↓
        ┌────────────┴────────────┐
        ↓                         ↓
      MERCADO                    HOY
     Terminal              Command Center
```

`PositionOperatingTruth` **no sustituye** `OperationalTruth`: la extiende (execution + secondaryConditions + nextAction unificado). `TradeStory` no sustituye Journal: Journal consume la historia.

### A.4 ExecutionState (proyección)

Responde: ¿existe orden? ¿pendiente? ¿aceptada? ¿parcial? ¿ejecutada? ¿UNKNOWN? ¿conciliada?

Campos mínimos (contrato, no tipos):

| Campo                 | Valores canónicos                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `lifecycle`           | `none` \| `submit` \| `in_flight` \| `filled` \| `failed` \| `unknown` \| `reconciled`                            |
| `orderState`          | `none` \| `pending` \| `accepted` \| `partial` \| `filled` \| `rejected` \| `cancelled` \| `expired` \| `unknown` |
| `fillState`           | `none` \| `partial` \| `complete`                                                                                 |
| `protectionState`     | eco de protect (no autoridad)                                                                                     |
| `targetState`         | tocado vs gestionado (H2 intacto)                                                                                 |
| `trailingState`       | `inactive` \| `hint` \| `proposed` \| `applied`                                                                   |
| `reconciliationState` | `clean` \| `attention` \| `incident` \| `unknown`                                                                 |
| `nextAction`          | misma CTA que POT/entry truth                                                                                     |

Hoy `orderPending` / `executionHint` son el germen. ExecutionState es la foto completa. **No** duplica PaperOrder.

### A.5 PositionOperatingTruth (proyección)

Unifica para **un** instrumento con posición:

- `PositionState` + `ExitPlan` + `ProtectPlan` + `PositionRevision` + recon + `ExecutionState` + `OperationalTruth`

Debe decir: estado, P&L, R, stop operativo, T1, T2, trailing (applied vs hint), protección, reconciliación, **próxima acción**, `secondaryConditions[]`.

`PositionStatus` durable sigue `OPEN | PARTIAL | PROTECTED | CLOSED` (ADR-032). T1 / T2 / TRAIL / T1_REACHED son **vistas**, no columnas rivales.

### A.6 TradeStory (proyección)

Timeline reconstruible de **una** operación (idea → cierre). Cada evento tiene `asOf` y no borra el anterior.

Ejemplo canónico:

```text
02/09  Estudio
03/09  Preparada
05/09  Trigger
05/09  Propuesta
05/09  Confirmación
05/09  Fill
07/09  Stop actualizado
09/09  T1
12/09  T2
15/09  Cierre
```

Journal muestra tesis + esta historia. No es un segundo diario.

### A.7 Regla de oro — una CTA primaria

Para cada activo la UI muestra **como máximo una** acción primaria.

| Kind              | Copy de usuario                        | Nunca                          |
| ----------------- | -------------------------------------- | ------------------------------ |
| `maintain`        | Mantener                               | HOLD / T1_REACHED              |
| `protect`         | Proteger                               | protect_hint como orden        |
| `exit`            | Salir                                  | EXIT_TRIGGERED                 |
| `reduce`          | Reducir                                | TAKE_PROFIT crudo              |
| `review_proposal` | Revisar propuesta                      | BUY / COMPRAR                  |
| `watch`           | Vigilar                                | WATCH como botón de compra     |
| `none`            | — / Gate en veto / Entradas bloqueadas | «Preparar operación» bajo veto |

`allowsEntry: false` en la capa de CTA derivada de posición/candidato (invariante ADR-037). Ranking ≠ BUY.

Acciones secundarias (¿Por qué?, Ver análisis, Ver operaciones) **colapsadas**, no competidoras.

### A.8 Prioridad semántica — EXIT vs discrepancia de protección

**Contrato V1.42 (cambio respecto a `mapMesaNextAction` actual):**

Si existe una orden de salida válida y urgente (`exitSuggestedAction === "full_exit"`), la CTA primaria es **`exit`**.

La discrepancia de protección (`protectionDiscrepancy`) es **condición secundaria** (⚠️ Protección discrepante), no oculta «la tesis exige salir».

Prioridad de **atención** (no ranking):

```text
full_exit / stop hit     → exit
reduce (T1/T2 gestionable) → reduce
protect (hint o plan)    → protect   [si no hay full_exit]
review / recon crítico   → review
blocked (entradas)       → none (entradas); exits protectoras ALLOW
trigger / propuesta      → review_proposal
armed / preparada        → watch o ver tesis (no BUY)
watch                    → vigilar
discrepancia             → secondaryCondition (salvo que no haya exit/reduce)
```

El código actual (`protectionDiscrepancy` absoluto sobre `full_exit`) es **deuda de contrato**, no un parche a aplicar antes de F3.

### A.9 Trailing

Hoy: `trailingStopHint` ≠ stop operativo. Mostrar «No aplicado» / «Revisar». **No tocar esa distinción.**

Camino futuro (mismo modelo SEMI → AUTO):

```text
Trailing hint → propuesta → Policy → Confirm → PositionRevision → currentStop
```

AUTO no cambia objetos; solo omite la firma humana. Hint nunca se auto-promueve.

### A.10 Simetría ENTRY / EXIT (lenguaje de producto)

No son `PositionStatus` durables nuevos.

```text
ENTRY:  WATCH → READY → TRIGGER → PROPOSE → CONFIRM → OPEN
EXIT:   PROTECT → T1 → T2 → TRAIL → REDUCE → EXIT → CONFIRM → FILLED → CLOSED
ambos → Journal / TradeStory
```

Mapeo a fases cockpit actuales (`sin_contexto` … `posicion`): la entrada ya está; la posición debe ganar la misma calidad de frase/CTA (T1 alcanzado → «Mantener» si HOLD, no el enum interno).

### A.11 Dos capas de presentación — un motor

| Capa                     | Qué ve el inversor                                                     | Qué no                           |
| ------------------------ | ---------------------------------------------------------------------- | -------------------------------- |
| **Usuario**              | OPORTUNIDADES / REQUIERE ACCIÓN / VIGILAR / SIN ACCIÓN + frase + 1 CTA | Gate, DS-05, TTL, risk_signature |
| **Avanzado** (colapsado) | TradePlan, Gate, DS-05, DS-03, TTL, risk_signature, execution UNKNOWN  | Segunda CTA primaria             |

No dos motores. Hoy la cola de entradas se parece a una consola de diagnóstico; V1.42 la presenta primero en lenguaje usuario.

---

## B. UI State Machine

### B.1 Principio

**CONTEXTO (instrumento) → ESTADO (proyección) → ACCIÓN (una CTA).**

La UI no recalcula fase ni permiso. Consume `EntryOperatingTruth` **o** `PositionOperatingTruth` (+ `ExecutionState`).

### B.2 Superficies

| Superficie                | Pregunta                                           | No es                              |
| ------------------------- | -------------------------------------------------- | ---------------------------------- |
| **Mercado** `/trading`    | ¿Qué decisión operativa hay sobre **este** activo? | Command center del día             |
| **Hoy** `/mesa`           | ¿Qué debo hacer **hoy** (cola)?                    | Segundo terminal / segundo Mercado |
| **Journal**               | ¿Qué pensamos y qué pasó?                          | Cola de CTAs                       |
| **Cartera / Operaciones** | ¿Qué tengo / qué orden hay?                        | Discovery                          |

Hoy, Mesa, Asesor, Journal, Decision Spine **no** se meten en el cockpit. Cinco puertas L1 intactas (ADR-040).

Shell Mercado (layout congelado; solo cambia el **nombre** del panel derecho y el contenido por estado):

```text
┌───────────────┬──────────────────────┬────────────────────┐
│ LISTAS        │ GRÁFICO              │ DECISIÓN           │
│ Estudio       │                      │ Estado + niveles   │
│ Cartera       │                      │ Próxima acción     │
│ Watchlist     │                      │                    │
├───────────────┴──────────────────────┴────────────────────┤
│ RESUMEN / POSICIONES / ÓRDENES / EVENTOS                   │
└────────────────────────────────────────────────────────────┘
```

El panel derecho se llama **DECISIÓN**, no Operativa, ni Asesor, ni Trading. Contesta: ¿cuál es la decisión operativa sobre este activo?

### B.3 Máquina por instrumento

Prioridad de fase (ya en `resolveMercadoCockpitPhase`; extender, no reemplazar):

1. Sin instrumento → `sin_contexto`
2. Posición abierta → máquina de **posición** (§B.5)
3. Orden firmada / fill pendiente → `confirmada` + ExecutionState
4. Cola Confirm → `propuesta`
5. TRIGGERED → `disparada`
6. BLOCKED → `bloqueada` (CTA none)
7. EXPIRED / CANCELLED → `caducada` (nunca PREPARADA)
8. ARMED + plan → `preparada`
9. En Estudio → `vigilar` / `en_estudio`
10. Fuera → `descubierto` (nunca BUY)

### B.4 Tabla estado → CTA → copy (entrada)

| Fase                | Frase usuario                        | CTA primaria       | Secundaria          |
| ------------------- | ------------------------------------ | ------------------ | ------------------- |
| En estudio          | Esperando disparador                 | Ver análisis       | —                   |
| Preparada           | Plan armado. Disparador no cruzado   | Preparar operación | ¿Por qué?           |
| Disparada           | Disparo confirmado. Firma en Confirm | Revisar propuesta  | ¿Por qué?           |
| Propuesta           | Propuesta SEMI en cola               | Revisar propuesta  | Descartar si aplica |
| Confirmada          | Firma hecha — fill pendiente         | Ver operaciones    | —                   |
| Bloqueada / VETO    | Gate no autoriza entrada             | none               | Ver tesis           |
| Caducada            | Plan caducado                        | none               | —                   |
| Entradas bloqueadas | Incidente/recon — no proponer        | none               | Resolver incidente  |

### B.5 Tabla estado → CTA → copy (posición)

| Vista                            | Frase usuario                            | CTA primaria              | Secondary                                    |
| -------------------------------- | ---------------------------------------- | ------------------------- | -------------------------------------------- |
| Posición estable                 | Mantener                                 | Mantener                  | Ver ruta                                     |
| T1 alcanzado, HOLD               | T1 alcanzado · 50 % si aplica · Mantener | Mantener                  | Trail hint                                   |
| T2                               | T2 · reducción                           | Reducir                   | —                                            |
| Protección discrepante + no exit | Protección discrepante                   | Proteger                  | ⚠️                                           |
| `full_exit` / stop               | La tesis exige salir                     | **Salir**                 | ⚠️ discrepancia si hay                       |
| Trail hint                       | Trail no aplicado                        | Mantener o Revisar        | No aplicado                                  |
| Recon incidente                  | Broker ≠ ledger                          | Revisar                   | entradas bloqueadas; salida protectora ALLOW |
| UNKNOWN post-submit              | Orden desconocida — no duplicar          | Revisar / Ver operaciones | reconcile                                    |

T1 alcanzado **no** se etiqueta `T1_REACHED` en producto.

### B.6 Mockups canónicos (presentación)

**En estudio** — tendencia / momentum / régimen · entrada/stop/T1 · «Esperando disparador» · [VER ANÁLISIS].

**Disparada** — precio · entrada propuesta · stop · riesgo € · R/R · [REVISAR PROPUESTA].

**Posición** — qty · actual · % · R · STOP (protegida o no) · T1/T2 ○ · TRAIL inactivo · [MANTENER].

**T1 alcanzado** — % ejecutado · beneficio realizado · R restante · STOP · TRAIL activo · T2 · Próxima acción: Mantener.

### B.7 Hoy 2.0 (command center)

Hoy deja de intentar mostrarlo todo. Solo cuatro cubos:

| Cubo               | Semántica                                                                          |
| ------------------ | ---------------------------------------------------------------------------------- |
| 🔴 REQUIERE ACCIÓN | Firma, exit, protect, incidente, UNKNOWN                                           |
| 🟢 OPORTUNIDADES   | Preparadas / disparadas / propuestas (copy humano, no WATCH/ARMED/TRIGGERED crudo) |
| 🟡 VIGILAR         | En estudio, trigger no cruzado                                                     |
| ⚪ SIN ACCIÓN      | Nada que hacer                                                                     |

Cobertura Estudio es función distinta (KPI detrás de detalles), no un quinto cubo de chrome. Nivel avanzado colapsado.

---

## C. Golden Paths — DoD de V1.42

Estos diez escenarios **son** el criterio de salida de V1.42, no un anexo. Cada uno exige: misma CTA y frase en Mercado / Hoy / Journal; una sola acción primaria; Confirm = única firma de execute; Ranking ≠ BUY.

**Prohibido en todos:** botón COMPRAR; segunda CTA primaria; ejecutar sin Confirm (SEMI); promover trail hint a `currentStop`; fingir PREPARADA desde BLOCKED/EXPIRED/CANCELLED.

### GP-01 Entrada normal

Estudio → preparada → trigger → propuesta → confirm → fill → posición.

|             |                                                                                          |
| ----------- | ---------------------------------------------------------------------------------------- |
| Autoridades | TradePlan ARMED→TRIGGERED · `check_opening` ALLOW · Confirm · persist PositionState OPEN |
| Proyección  | EntryOperatingTruth → ExecutionState filled → PositionOperatingTruth OPEN                |
| CTA         | Revisar propuesta → (post-fill) Mantener                                                 |
| Superficies | Mercado DECISIÓN + Hoy 🟢/🔴 + Journal story                                             |
| Dominio hoy | Parcial (V1.38 + Confirm). Falta ExecutionState + Story                                  |

### GP-02 Entrada bloqueada

Estudio → veto → ninguna CTA de entrada.

|             |                                                                           |
| ----------- | ------------------------------------------------------------------------- |
| Autoridades | `check_opening` VETO/DEFERRED **o** `entriesBlocked`                      |
| CTA         | `none` (Gate en veto / Entradas bloqueadas)                               |
| Prohibido   | «Preparar operación»                                                      |
| Dominio hoy | CÓDIGO V1.41.3 (CTA + side-doors). Propose HTTP sigue abierto (aceptable) |

### GP-03 Orden pendiente

Confirmada → pending → fill.

|             |                                                                |
| ----------- | -------------------------------------------------------------- |
| Autoridades | Confirm · PaperOrder SUBMITTED/ACK                             |
| Proyección  | ExecutionState `pending`/`accepted` · fase `confirmada`        |
| CTA         | Ver operaciones                                                |
| Dominio hoy | `orderPendingFill` / executionHint. Falta ExecutionState pleno |

### GP-04 Fill parcial

OPEN → PARTIAL → OPEN (resto).

|             |                                                        |
| ----------- | ------------------------------------------------------ |
| Autoridades | PositionState PARTIAL · fillState partial              |
| CTA         | Mantener o Ver operaciones (una)                       |
| Dominio hoy | Status PARTIAL existe (F2.1). UI/proyección incompleta |

### GP-05 Stop

OPEN → stop hit → exit → fill → CLOSED.

|             |                                                                             |
| ----------- | --------------------------------------------------------------------------- |
| Autoridades | ExitPlan STRUCTURAL_STOP · `check_exit_permission` ALLOW · Confirm · CLOSED |
| CTA         | **Salir** (no Proteger si full_exit)                                        |
| Dominio hoy | POM + V1.27 GP. Prioridad CTA vs discrepancia = deuda §A.8                  |

### GP-06 T1

OPEN → T1 → reducción → stop actualizado.

|             |                                                                     |
| ----------- | ------------------------------------------------------------------- |
| Autoridades | target touched ≠ managed (H2) · reduce Confirm · `applyCurrentStop` |
| CTA         | Reducir **o** Mantener si ya gestionado/HOLD — nunca `T1_REACHED`   |
| Dominio hoy | V1.27 GP + ExitRouteView. Copy de producto incompleto               |

### GP-07 T2

T1 → T2 → reducción.

Simétrico a GP-06. T2 no inventa sello de gestionado (H2).

### GP-08 Trailing

T1 → trailing proposal → confirm → stop revision.

|             |                                                       |
| ----------- | ----------------------------------------------------- |
| Autoridades | hint → Confirm → PositionRevision → `currentStop`     |
| CTA         | Revisar (propuesta) luego Mantener                    |
| Prohibido   | hint = stop operativo                                 |
| Dominio hoy | Hint only (ciclo 8.1). Camino Confirm **no** producto |

### GP-09 Discrepancia

Position → broker ≠ ledger → INCIDENT → entradas bloqueadas → salida protectora permitida.

|              |                                                                                                           |
| ------------ | --------------------------------------------------------------------------------------------------------- |
| Autoridades  | OI-6 / DEX-3 · opening veto · ExitPermission H2 (SEMI desriesgo ALLOW)                                    |
| CTA primaria | Revisar (incidente) **o** Salir/Proteger si hay tesis de salida — discrepancia = secondary si `full_exit` |
| Dominio hoy  | Incidente + entriesBlocked. POT unificada falta                                                           |

### GP-10 Crash

submit → crash → UNKNOWN → reconcile → no duplicate order.

|             |                                             |
| ----------- | ------------------------------------------- |
| Autoridades | DurableSubmitIntent · OR-2 · 0 re-POST      |
| Proyección  | ExecutionState `unknown` → `reconciled`     |
| CTA         | Revisar / Ver operaciones — **no** reenviar |
| Dominio hoy | Spine OR-2/DEX. UI/proyección incompleta    |

### C.11 Cobertura tests actuales vs gap

| GP    | Dominio / spine      | Proyección shared        | UI Mercado/Hoy                      |
| ----- | -------------------- | ------------------------ | ----------------------------------- |
| 01    | Parcial V1.27        | Entry truth sí; Story no | Parcial                             |
| 02    | Gate + FE V1.41.3    | Sí                       | Sí                                  |
| 03–04 | PaperOrder / PARTIAL | Hint only                | Parcial                             |
| 05–07 | V1.27 + ExitRoute    | Parcial; §A.8 no         | Parcial                             |
| 08    | Hint only            | —                        | —                                   |
| 09–10 | OR/DEX               | —                        | Banner incidente; no ExecutionState |

---

## D. Next — implementación aparcada (no este slice)

Orden exacto **después** de spec aceptada:

| Fase | Qué                                                                                 | No                                       |
| ---- | ----------------------------------------------------------------------------------- | ---------------------------------------- |
| F1   | Tests Golden Path (contrato §C) sobre proyecciones existentes + huecos documentados | UI nueva                                 |
| F2   | `ExecutionState` proyección shared                                                  | Motor / tabla                            |
| F3   | `PositionOperatingTruth` + prioridad §A.8                                           | Sustituir OperationalTruth               |
| F4   | `TradeStory`                                                                        | Segundo Journal                          |
| F5   | Mercado 2.0 panel **DECISIÓN** (este contrato §B)                                   | Nav L1 / segundo Mercado                 |
| F6   | Hoy 2.0 cubos §B.7                                                                  | Dump diagnóstico                         |
| F7   | SEMI completo (entrada/salida simétricas ya modeladas)                              | AUTO execute                             |
| F8   | PAPER AUTO                                                                          | Thaw estricto · broker live como default |

SEMI vs AUTO:

```text
SEMI:  IA propone → Risk → Policy → Humano confirma → Execution
AUTO:  IA propone → Risk → Policy → Execution
```

El usuario no debe notar otra aplicación. AUTO no exige objetos nuevos.

---

## E. Fuera de alcance (sigue parked)

P2 Lab · móvil · push · thaw estricto · OCO · trail autoridad automática · drag entry/T1/T2 · OpportunityScore · `secondaryReasons[]` como motor · confirms individualizados · bump `package.json` (ver [`versioning.md`](./versioning.md)) · `POST /ai/recommendations/propose` + `entriesBlocked`.
