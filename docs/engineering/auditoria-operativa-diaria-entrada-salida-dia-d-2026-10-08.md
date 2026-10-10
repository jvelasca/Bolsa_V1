# Auditoría read-only — operativa diaria: entrada/salida · estrategia/indicadores · DÍA-D

> **AsOf:** 2026-10-08 · **Base:** `v2.88.94-beta` · **Naturaleza:** auditoría **read-only** (no toca motor, contrato HTTP ni Alembic; **no** re-mide DÍA-D).
> **Actualización (2026-10-09):** los slices `S1`–`S3` de §5 se **implementaron** en [`704c4547`](https://github.com/jvelasca/Bolsa_V1/commit/704c4547) (`apps/web/**` + `packages/shared/**`, `Δ motor = 0`); `S4` sigue **no lanzado**.
> **Actualización (2026-10-10):** **`S4` sí se entregó** después en [`d9df6de4`](https://github.com/jvelasca/Bolsa_V1/commit/d9df6de4) (`v2.88.97-beta`): el **agregador de evidencia** vive en `dia-d-evidence-aggregate-panel.tsx` (montado en `DiaDAutoPanel`) y mantiene el veredicto **`NO CONFIRMADO`** sin emitir jamás `CONFIRMED`. La afirmación «`S4` no lanzado» de la cabecera original **queda desactualizada**. Nuevo slice **`S5-puente-auto-dia-d`** (UI-only, `Δ motor = 0`) cierra el hueco restante: lleva desde la **operación de AUTO** a la **estrategia/indicadores ganadores que la sustentan** y a la **verificación DÍA-D bajo demanda** ya existente en Laboratorio.
> **Premisas auditadas:** [`PROJECT_PREMISES.md` §6](../PROJECT_PREMISES.md) — `P2` (claridad entrada/salida), `P3` (estrategia confirmada con los mejores indicadores), `P4` (evaluación DÍA-D).
> **Origen:** reorden de la FASE 3 — [auditoría FASE 2](./auditoria-operativa-auto-fase-2-2026-10-08.md) §8 y [plan de motor PARKED](./plan-cierre-operativa-auto-2026-10-08.md).
> **Punto de entrada para el auditor:** [`arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`](./arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md).

## 0. Alcance y método

- Se auditan **las superficies reales** de los tres pilares del propietario, citando `file:line`.
- Regla dura: lo **ausente** se declara «Sin dato todavía»; no se fabrica ni se rellena con `0` (§5.1.4).
- `P4` **evalúa si la medición es suficiente**; **no** la re-mide en este ciclo (fuera de alcance).
- Veredicto por pilar: **CUMPLE** / **CUMPLE PARCIAL** / **NO CUMPLE**, con hallazgos falsables `P#-n`.

---

## 1. `P2` · Claridad del punto de entrada y de salida

### 1.1 Superficies y evidencia

| Superficie | Evidencia | Qué muestra |
| --- | --- | --- |
| Cockpit `DECISIÓN` (entrada, densidad `full`) | `apps/web/src/features/trading/decision-surface-compact.tsx:311-378`, `:386-402` | Nivel 2: Entrada · Precio actual · Distancia · Stop · Tamaño · Riesgo. Nivel 3: T1 · T2 |
| Cockpit `HUD` (compacto) | `apps/web/src/features/trading/decision-surface-compact.tsx:296-308` | Una línea: `E {entrada} · S {stop} · T1 {objetivo}` |
| Ticket Confirm «riesgo primero» | `apps/web/src/features/trading/f3-trade-plan-risk-first-block.tsx:85-125` | Secciones **Entrada** / **Riesgo (primero)** con Stop y pérdida al stop / **Objetivo** T1 |
| Plan operativo (mesa) | `apps/web/src/features/mesa/operational-plan-view.tsx:113-148` | Entrada · Stop operativo · T1 · T2 · R/R · Riesgo |
| Líneas en el gráfico | `apps/web/src/features/charts/operational-plan-chart-levels.ts:159-201`, `:206-271` | `Entrada` (o `Trigger` en `prepared`) · `Stop vigente` · `T1` · `T2` |
| Cockpit posición (Journey HUD) | `apps/web/src/features/trading/decision-surface-compact.tsx:575-632`, `:636-671` | Nivel 2: Stop inicial · Stop vigente · Entrada. Nivel 3: escalera `OperatorPositionPlan` + T1/T2 `sr-only` |
| Drag del stop | `apps/web/src/features/charts/chart-operational-plan-levels-layer.tsx:5-7`, `:157-160` | Solo el **stop vigente** es arrastrable (Entrada/T1/T2 no) |

### 1.2 Hallazgos

- **`P2-1` (CUMPLE, entrada).** La **entrada** y el **stop** se muestran a primer nivel en cockpit, ticket Confirm y gráfico. Evidencia: `decision-surface-compact.tsx:311-352`, `f3-trade-plan-risk-first-block.tsx:85-104`, `operational-plan-chart-levels.ts:175-228`.
- **`P2-2` (GAP, salida sin precio).** El `ExitPlan` del ticket declara **intent, qty, estado, acción y motivo**, pero **no un precio/zona de salida** por peldaño (T1/T2). Evidencia: `apps/web/src/features/trading/f3-exit-plan-block.tsx:85-104`. *Falsable:* mostrar T1/T2 con precio en `F3ExitPlanBlock` y comparar.
- **`P2-3` (GAP, entrada literal en `prepared` + simple).** En `focus simple` y `phase === "prepared"`, la línea «Entrada» **no se dibuja** (se usa `Trigger`): si el trigger ≠ fill esperado, el punto de entrada no es literal. Evidencia: `apps/web/src/features/charts/operational-plan-chart-levels.ts:159-201`. *Falsable:* fijar `focusMode=simple`, `phase=prepared`, `entry≠trigger` y comprobar si aparece «Entrada».
- **`P2-4` (GAP, objetivos en Journey HUD).** Con Journey activo, los `dd` de T1/T2 quedan en `sr-only` (`decision-surface-compact.tsx:643-671`); el precio del objetivo solo aparece dentro del `detail` de la escalera (`operator-cabin-ui.tsx:600-618`), no como fila etiquetada «T1/T2». *Falsable:* inspeccionar el DOM visible de una posición con Journey.

**Veredicto `P2`: CUMPLE PARCIAL.** Entrada clara; la **salida** no declara precio en el ticket y los objetivos de una posición con Journey no son filas etiquetadas de primer nivel.

---

## 2. `P3` · Estrategia confirmada con los mejores indicadores detectados

### 2.1 Superficies y evidencia

| Superficie | Evidencia | Qué muestra |
| --- | --- | --- |
| Finalistas (TOP por valor) | `apps/web/src/features/backtests/instrument-strategy-top-panel.tsx:169-190` | `#rank label ★` · `source` · `return` · `DD` · `runId` — **sin indicadores** |
| Tipo ejecutable | `apps/web/src/features/backtests/instrument-top-strategy-type.ts:14-28`, `:30-41` | Sanea el `strategyType` al **preset de la definición** (evita el seed proxy de Lab) |
| Frescura del TOP | `apps/web/src/features/backtests/backtest-finalists-freshness.ts:1-18` | Mide **frescura** (huella), no confirmación de la estrategia |
| Coach técnico (razones) | `apps/web/src/features/backtests/backtest-deep-coach.ts:57-73`, `:434-481`, `:1046`, `:1112` | `TechnicalRecommendation.reasons: string[]` existe como razón local |
| Catálogo de indicadores | `apps/web/src/features/charts/indicators-catalog-dialog.tsx:279-299`, `:530-600` | Presets/templates **del gráfico** (sistema/personal/IA), no la razón de la estrategia |
| Evidencia LAB del TOP | `instrument-strategy-top-panel.tsx:560-570` | `status · v · TF` · badge de estabilidad · `lab OOS` / `in-sample` |

### 2.2 Hallazgos

- **`P3-1` (GAP, indicadores no visibles).** La superficie de primer nivel (Finalistas y cockpit) **no declara los indicadores detectados** que sustentan la estrategia; solo `label/source/ret/DD/estrellas`. Evidencia: `apps/web/src/features/backtests/instrument-strategy-top-panel.tsx:169-190`. *Falsable:* abrir un valor con Finalistas y buscar en el DOM visible algún nombre de indicador (RSI/SMA/SuperTrend…).
- **`P3-2` (CUMPLE, integridad del tipo).** El `strategyType` se alinea con el **preset de la definición guardada**, evitando que el seed proxy de Lab contamine la estrategia mostrada. Evidencia: `apps/web/src/features/backtests/instrument-top-strategy-type.ts:14-28`; consumo en `instrument-strategy-top-panel.tsx:353-397`.
- **`P3-3` (GAP, catálogo desacoplado).** El catálogo de indicadores pertenece al **gráfico** (presets y grupos por pestaña), no a la estrategia confirmada ni a la razón del ranking. Evidencia: `apps/web/src/features/charts/indicators-catalog-dialog.tsx:93-130`, `:530-600`.
- **`P3-4` (GAP, `reasons` no aterrizan).** El coach técnico **produce** `reasons` por recomendación (`backtest-deep-coach.ts:434-481`) y las persiste en `coachFacts.recommendations[].reasons` (`:1046`, `:1112`), pero la superficie de primer nivel **no las muestra** como razón de la estrategia. *Falsable:* leer `top.coachFacts` de un valor con TOP y comprobar si `reasons` aparece en UI.

**Veredicto `P3`: CUMPLE PARCIAL.** Existe el tipo ejecutable correcto y una razón (`reasons`) calculada y persistida, pero **ni los indicadores ni las razones** se declaran en la superficie de primer nivel.

---

## 3. `P4` · Evaluación DÍA-D (declarado vs ejecutado vs OOS real)

### 3.1 Superficies y evidencia

| Superficie | Evidencia | Qué mide |
| --- | --- | --- |
| DÍA-D AUTO · declarado vs ejecutado | `packages/py/application/src/bolsa_application/dia_d_auto.py:50-59`, `:138-199`; UI `apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx:24-31`, `:60-80` | Paso a paso: `MATCH` / `DIVERGENT` / `NOT_MEASURED` / `PARTIAL` |
| DÍA-D AUTO · feedback OOS por valor | `packages/py/application/src/bolsa_application/dia_d_auto_feedback.py:65-82`, `:374-407`; UI `apps/web/src/features/auto-monitor/dia-d-auto-feedback-panel.tsx:26-46` | Veredicto `OOS_SUPPORTED` / `MIXED` / `REFUTED` / `NOT_MEASURED` |
| Endpoint read-only | `apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py:248-291` | `GET /api/auto/dia-d-feedback[{window}]`, fail-closed por cuenta |
| Verificación D→hoy (Trading) | `apps/web/src/features/trading/trading-dia-d-replay-panel.tsx:283-290`, `:461-556`; `apps/web/src/features/trading/dia-d-verify-continuity.ts:33-40`, `:99-166` | Película D→hoy + reconciliación F-D#1 vs F-hoy#1 |
| Reconciliación de identidad/OOS | `apps/web/src/features/backtests/dia-d-reconciliation.ts:6-18`, `:149-165` | `SAME_CONFIRMED` / `SAME_FAILED` / `DRIFT_*` / `INCONCLUSIVE` |

### 3.2 Hallazgos

- **`P4-1` (CUMPLE, comparador declarado vs ejecutado).** Existe un comparador **paso a paso** declarado↔ejecutado con veredicto explícito y huecos declarados (`NOT_MEASURED`). Evidencia: `packages/py/application/src/bolsa_application/dia_d_auto.py:161-199`; UI `dia-d-auto-panel.tsx:60-80`.
- **`P4-2` (GAP CLAVE, sin `CONFIRMED`).** El techo actual del feedback es **`OOS_SUPPORTED`** (evidencia de REPLAY/OOS); `CONFIRMED` está **reservado para evidencia PAPER y NO se emite**. El **lado ejecutado** queda `NOT_MEASURED` en días históricos hasta que la ventana PAPER opere ese D. Evidencia: `packages/py/application/src/bolsa_application/dia_d_auto_feedback.py:65-82`, `:151-153`; UI `dia-d-auto-feedback-panel.tsx:34-40`. *Falsable:* buscar `CONFIRMED` emitido (`grep -r "CONFIRMED" packages/py/application/src`) → solo aparece como reservado.
  - **Incoherencia doc ↔ código:** [`PROJECT_PREMISES.md`](../PROJECT_PREMISES.md) §5 describe el `DÍA-D AUTO` como emisor de un veredicto `CONFIRMED`/…; el código **reserva** `CONFIRMED` y no lo emite, y el `window_gate` usa `READY`/`INCONCLUSIVE` (`packages/py/application/src/bolsa_application/operability_window.py:495-530`). La redacción de §5 es **aspiracional**; el contrato real es `OOS_SUPPORTED` + gate `READY`/`INCONCLUSIVE`.
- **`P4-3` (GAP, medición por artefacto CLI, no en vivo).** El feedback se calcula por **CLI** y la UI lo lee como artefacto read-only; no se recalcula en vivo. Evidencia: `auto_dia_d_feedback.py:35-59`, `:246-291`; aviso en `dia-d-auto-feedback-panel.tsx:153-179`.
- **`P4-4` (GAP, veredicto fragmentado en 3 superficies).** El «DÍA-D» existe como tres lentes separadas: (a) `SAME_CONFIRMED`/`DRIFT_*` en el panel Trading D→hoy, (b) `MATCH`/`DIVERGENT` en Auto‑monitor declarado↔ejecutado, (c) `OOS_SUPPORTED`/… en Auto‑monitor feedback. **No hay un único veredicto** que una declarado + ejecutado + OOS. Evidencia: `dia-d-reconciliation.ts:149-165` vs `dia_d_auto.py:184-199` vs `dia_d_auto_feedback.py:374-407`.

**Veredicto `P4`: CUMPLE PARCIAL.** La maquinaria de medición existe y es honesta (huecos declarados, `CONFIRMED` no falseado), pero **no produce confirmación de ejecución real** (`CONFIRMED`) y el veredicto está **fragmentado** en tres superficies sin unión declarado↔ejecutado↔OOS.

---

## 4. Resumen de hallazgos (falsables)

| ID | Pilar | Tipo | Resumen | Evidencia |
| --- | --- | --- | --- | --- |
| `P2-1` | P2 | CUMPLE | Entrada y stop a primer nivel en cockpit/ticket/gráfico | `decision-surface-compact.tsx:311-352`; `f3-trade-plan-risk-first-block.tsx:85-104` |
| `P2-2` | P2 | GAP | `ExitPlan` sin precio de salida por peldaño | `f3-exit-plan-block.tsx:85-104` |
| `P2-3` | P2 | GAP | Entrada no literal en `simple` + `prepared` (solo `Trigger`) | `operational-plan-chart-levels.ts:159-201` |
| `P2-4` | P2 | GAP | T1/T2 de posición con Journey no son filas etiquetadas | `decision-surface-compact.tsx:643-671`; `operator-cabin-ui.tsx:600-618` |
| `P3-1` | P3 | GAP | Indicadores de la estrategia no visibles en primer nivel | `instrument-strategy-top-panel.tsx:169-190` |
| `P3-2` | P3 | CUMPLE | Tipo ejecutable saneado al preset de la definición | `instrument-top-strategy-type.ts:14-28` |
| `P3-3` | P3 | GAP | Catálogo de indicadores es del gráfico, no de la estrategia | `indicators-catalog-dialog.tsx:93-130` |
| `P3-4` | P3 | GAP | `reasons` calculadas/persistidas pero no mostradas | `backtest-deep-coach.ts:434-481`, `:1112` |
| `P4-1` | P4 | CUMPLE | Comparador declarado↔ejecutado paso a paso | `dia_d_auto.py:161-199`; `dia-d-auto-panel.tsx:60-80` |
| `P4-2` | P4 | GAP CLAVE | Sin `CONFIRMED`; ejecutado PAPER queda `NOT_MEASURED` | `dia_d_auto_feedback.py:65-82`, `:151-153` |
| `P4-3` | P4 | GAP | Medición por artefacto CLI, no en vivo | `auto_dia_d_feedback.py:35-59` |
| `P4-4` | P4 | GAP | Veredicto DÍA-D fragmentado en 3 superficies | `dia-d-reconciliation.ts:149-165` vs `dia_d_auto.py:184-199` vs `dia_d_auto_feedback.py:374-407` |

---

## 5. Slices derivados (`S1`–`S5` **implementados** · `S4` **entregado**)

> `S1`–`S3` se **implementaron** tras la auditoría (commit [`704c4547`](https://github.com/jvelasca/Bolsa_V1/commit/704c4547), UI-only + `packages/shared`, **`Δ motor = 0`**); `S4` se **entregó** en [`d9df6de4`](https://github.com/jvelasca/Bolsa_V1/commit/d9df6de4) (`v2.88.97-beta`); `S5` (puente AUTO → DÍA-D) se **implementa** UI-only. Prioridad por relación coste/valor sobre `P1`–`P4`.

| Slice | Pilar | Objetivo | Alcance | Estado |
| --- | --- | --- | --- | --- |
| `S1-exit-precio` | P2 | Declarar T1/T2 con **precio** en el Plan de salida del ticket | UI (`f3-exit-plan-block.tsx`) + meta en `propose-position-exit.ts`; precio desde `position.operational.target*`; si falta → «Sin dato todavía» (**no** se fabrica) | **IMPLEMENTADO** `704c4547` |
| `S2-entrada-literal` | P2 | Resolver la **semántica** de niveles en `simple` + `prepared`: `Entrada` (fill) y `Trigger` (activación) coexisten **solo** si el precio difiere; **no** se duplica la línea | UI (`operational-plan-chart-levels.ts`) | **IMPLEMENTADO** `704c4547` |
| `S3-indicadores-razon` | P3 | Mostrar en primer nivel la cadena **Estrategia → indicadores que la sustentan → razón** | UI (`instrument-strategy-top-panel.tsx`) + helper en `strategy-top1-chart-indicators.ts`; indicadores de `definition.indicatorSpecs`→`presetIndicatorSpecs` (**nunca** el catálogo del gráfico); `reasons` persistidas en `coachFacts.recommendations[]`; hueco → «Sin dato todavía» | **IMPLEMENTADO** `704c4547` |
| `S4-agregador-evidencia` | P4 | **Agregador de evidencia** (no un veredicto nuevo): compone los veredictos existentes (declarado↔ejecutado · OOS · PAPER) y concluye `NO CONFIRMADO` mientras no haya evidencia PAPER | Implementado read-only en `dia-d-evidence-aggregate-panel.tsx` (+ `dia-d-evidence-aggregate.ts`), montado en `DiaDAutoPanel`. **Prohibido** `OOS_SUPPORTED + MATCH → CONFIRMED`; **no** emite `CONFIRMED`. Nació con el contrato semántico correcto (§5.2 de premises) | **IMPLEMENTADO** `d9df6de4` |
| `S5-puente-auto-dia-d` | P3 + P4 | **Puente operación → estrategia/indicadores → verificación DÍA-D**: desde la operación de AUTO, resolver el **UUID por ticker**, mostrar la **estrategia #1** del valor con los **indicadores que la sustentan** y la **razón**, y ofrecer el CTA **«Verificar D→hoy»** que entra la sesión DÍA-D LAB y navega al verificador | UI-only: helper puro `auto-operation-strategy.ts` + hook `use-auto-operation-strategy.ts` (`features/auto`) y bloque en `auto-operation-story-panel.tsx`. Reutiliza `strategySlotToIndicatorLabels` + `readRecommendationReasons`; **no** recalcula ranking ni score. Huecos → «Sin dato todavía» (nunca `0`); la coincidencia con el sello del ciclo es **heurística declarada**. Sin tocar motor/contrato/DB | **IMPLEMENTADO** (UI-only, `Δ motor = 0`) |

**Regla:** ningún slice toca motor, contrato HTTP ni Alembic. Si un slice **exige** motor (p. ej. emitir `CONFIRMED` con evidencia PAPER), se para y se reabre el [plan PARKED](./plan-cierre-operativa-auto-2026-10-08.md) con dueño y disparador. Se cumplió para `S1`–`S3` y `S5`: viven en `apps/web/**` (más `packages/shared/**` para `S3`); `git diff --name-only -- packages/py apps/api-python` **vacío**. `S4` es UI-only sobre el read-model existente.

**Nota del puente (2026-10-10).** `S4` **sí se entregó** en [`d9df6de4`](https://github.com/jvelasca/Bolsa_V1/commit/d9df6de4) (`v2.88.97-beta`): el agregador compone declarado↔ejecutado · OOS · PAPER y concluye `NO CONFIRMADO` sin emitir `CONFIRMED`, mitigando el hallazgo `P4-4` (veredicto fragmentado). El hueco que quedaba **no** era el veredicto, sino el **camino**: desde la operación de AUTO no había ninguna referencia a la estrategia/indicadores ganadores que sustentan ESA señal ni al verificador DÍA-D bajo demanda del Laboratorio. Ese es exactamente **`S5`**: UI-only, con **«Sin dato todavía»** en los huecos (`UNKNOWN ≠ 0`) y **sin** fingir coincidencia entre el sello de estrategia del ciclo y el TOP #1.

**Nota del auditor (2026-10-08).** `S1`–`S3` quedaron **aceptados** para diseño/implementación (con los límites de arriba) y **ya están implementados**; `S4` se **acepta como objetivo pero no como contrato actual**: queda reformulado a agregador de evidencia y **no se lanza**. Ver [respuesta del auditor](./respuesta-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md).

**Refinamiento `S5` (2026-10-10) — UI-only, `Delta motor = 0`:**

- **Refactor DRY:** nuevo hook `apps/web/src/features/trading/use-dia-d-verify-launch.ts` (`useDiaDVerifyLaunch`) unifica el lanzamiento «Verificar D-hoy» que estaba **DUPLICADO** en `auto-operation-story-panel.tsx` y `instrument-strategy-top-panel.tsx` (`enterSession` `mode:'auto'` + `setAdoption(candidata)` + `navigate(diaDVerifyHref)` + toast). Sin cambio de comportamiento.
- **Tarjeta extraída:** `apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx` (`AutoOperationStrategyCard`) conserva los mismos `data-testid`; el story panel la consume.
- **Heurística de coincidencia ENDURECIDA:** `resolveAutoOperationStrategyMatch` pasa de CONTENCIÓN sobre tokens normalizados (falso positivo: sello `ma` contenido en `smacrossover` se declaraba `same`) a IGUALDAD POR TOKEN COMPLETO; `same` solo con emparejamiento real, `unknown`/`differs` en el resto.
- **Pulido de honestidad UI:** `rank != 1` se declara explícitamente (no se etiqueta como '#1' lo que no lo es); las RAZONES se listan completas (hasta 5); y 'carga != hueco': nueva bandera `loading` en la vista; durante la carga NO se declara un falso «Sin dato todavía» (se muestra «Cargando...»). Los errores de lectura siguen declarando «No disponible».
- **Higiene E2E integrado:** `afterAll` en `gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts` limpia el `strategy-top` global sembrado (DELETE); sin cambiar aserciones.
- **Herramienta dev:** `scripts/dev/seed_auto_cycle_for_ui.py` siembra/limpia un ciclo AUTO durable + TOP en la BD dev (idempotente, `--cleanup`), FUERA de `apps/api-python` y `packages/py`.

Verificación (2026-10-10): detalle completo en [`PROJECT_STATE.md`](./PROJECT_STATE.md).

**Sello (2026-10-10).** El slice **`S5`** (puente AUTO → DÍA-D) se **sella** en **`v2.88.104-beta`** (UI-only, `Δ motor = 0` / `Δ contrato = 0`, sin migración); evidencia en [`evidence/v2.88.104/README.md`](./evidence/v2.88.104/README.md).

---

## 6. Falsabilidad del entregable

- Cada hallazgo cita `file:line` verificable en `v2.88.94-beta`.
- Lo ausente se declara («Sin dato todavía»), sin fabricar.
- Los veredictos `P2`/`P3`/`P4` son **CUMPLE PARCIAL**; ninguno se declara cerrado.
- `P4` **no** se re-mide: la auditoría solo juzga si la medición es suficiente.
- **Ningún slice se ejecutó antes** de fijar estos hallazgos; `S1`–`S3` se implementaron **después** (`704c4547`), con los límites aquí declarados. `P2`/`P3`/`P4` siguen en **CUMPLE PARCIAL** (los slices son mejoras de presentación; los hallazgos `P2-2`… se mitigan, no se re-auditan aquí).

## 7. Fuera de alcance

- No se toca motor, contrato HTTP ni Alembic.
- No se re-mide DÍA-D ni se emite `CONFIRMED`.
- `F2-1`/`F2-2`/`F2-3` (completitud contable) y `F2-4` (motivo de ranking por ciclo) siguen como **deuda declarada** de la FASE 2.
