# Plan de remediación del universo LABORATORIO (LAB) · 2026-11-16

> **Padre:** [índice de ingeniería](./engineering-index-2026-08-03.md)
> **Auditoría que lo origina:** [auditoria-laboratorio-2026-11-16.md](./auditoria-laboratorio-2026-11-16.md).
> **Estado:** aprobada e **implementada** el 2026-11-16: **R1, R3, R2, R5, R4, R7, R6 y R8
> cerradas por código, tests y documentación**. R6 se cerró en dos tandas: *append-only* con
> guardián y Cartera LAB declarada efímera primero, y **`F-D` durable en servidor** después (§9).
> Cada cierre se anota en
> [`engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md) (entradas 223 y 224).
> **Alcance:** cerrar la distancia entre «verificar robustez» y «demostrar beneficio neto», y
> hacer alcanzable y confiable el embudo que hoy existe pero no se puede disparar.

---

## 1 · Decisiones del propietario que fijan el alcance

Registradas el 2026-11-16. No son propuestas: son restricciones.

| Decisión | Elección |
| --- | --- |
| **P1 / beneficio** | **Gate duro con hueco declarado.** Sin beneficio neto de costes, expectancy positiva y exceso vs benchmark no hay FINALISTA ni ACTIVE. Si falta la medición: «Sin dato todavía» y **no** se promociona. |
| **Función objetivo** | **Reordenar la selección por beneficio neto.** El campeón se elige por retorno neto de costes; el score bruto queda como columna secundaria. |
| **Histórico** | **Solo runs nuevos.** El gate rige desde su entrada en vigor; lo anterior se marca «Sin dato todavía», sigue visible y no es promocionable. Sin migración de datos. |
| **Embudo E4–E6** | **Disparador HTTP gobernado**, manual, auditado, fail-closed. |
| **Dos «Laboratorio»** | El Asesor mantiene un **resumen corto** y delega con deep-link a `/backtests`. |
| **«Desplegar en demo»** | Corregir copy: crea una **cuenta paper de procedencia**; **no** escribe trades ni el ledger DEMO. |
| **Ejecución** | Auditoría primero (hecha). Implementación **solo tras aprobar este plan**. |
| **Monotonía de gates** | **Añadir `risk` a FINALISTA.** El conjunto crece con el estado; se acaba el gate que aparece y desaparece. El TOP3 pasará a exigir también drawdown medido y 30 round trips OOS. |
| **`expectancyR`** | **No fabricar R.** `expectancyPct` siempre; `expectancyR` solo con unidad de riesgo declarada. Sin stop ni ATR: «Sin dato todavía». |

## 2 · Orden, y por qué

```
R1 (medir y elegir por neto)  →  R3 (confiar en el dato)  →  R2 (disparar el embudo)
        ↓                              ↓
R4 (P2/P3 en primer nivel)      R5 (una sola puerta)
        ↓
R7 (cobertura)  →  R6 (durabilidad)  →  R8 (documentación)
```

**R1 antes que R2 a propósito.** Un disparador para un embudo que no mide beneficio solo
automatiza la selección de perdedores. Y **R3 antes que R2** porque un endpoint que ejecuta el
embudo sobre un TOP que el cliente puede inventar convierte un problema de confianza en un
problema de integridad de datos.

**R8 va al final** pero es obligatoria: el estado que deje R1 (gate nuevo, octava puerta, runs
antiguos no promocionables) es exactamente el que hoy no está documentado en ningún sitio.

## 3 · R1 · P1 como gate real y selección por beneficio neto

**Impacto en beneficio: máximo.** Es la única línea que puede cambiar qué estrategia gana.

### 3.1 Paso 1 — aplicar costes en la rejilla

Hoy `finalize_grid_is_metrics` no pasa `costs=`, así que se aplica `BacktestCostModel()`
**0/0/0** ([backtest.py:50-55](../../packages/py/analytics/src/bolsa_analytics/backtest.py)), y los
cuatro simuladores operan a precio puro.

- Añadir `costs: BacktestCostModel` a `finalize_grid_is_metrics` y a los cuatro simuladores.
- Aplicar la convención que el repo ya declaró: ida y vuelta =
  `2 × (comisión + deslizamiento) + horquilla` ([baseline_arms.py:63-76](../../packages/py/application/src/bolsa_application/baseline_arms.py)).
  En entrada y en salida, cargar sobre el precio de ejecución.
- Alimentar los bps desde `BaselineCosts` (10/5/2 ⇒ **32 bps** por ida y vuelta) como default de
  producto, no como constante escondida.
- **No** cambiar el default de `BacktestCostModel`: un default global silencioso reescribiría
  resultados de llamadores que no piden costes.

**Archivos:** [optimize/metrics.py](../../packages/py/analytics/src/bolsa_analytics/optimize/metrics.py),
[optimize/grid_is_metrics.py](../../packages/py/analytics/src/bolsa_analytics/optimize/grid_is_metrics.py),
[optimize/sma_grid.py](../../packages/py/analytics/src/bolsa_analytics/optimize/sma_grid.py),
[optimize/rsi_grid.py](../../packages/py/analytics/src/bolsa_analytics/optimize/rsi_grid.py),
[optimize/macd_grid.py](../../packages/py/analytics/src/bolsa_analytics/optimize/macd_grid.py),
[optimize/rules_grid.py](../../packages/py/analytics/src/bolsa_analytics/optimize/rules_grid.py).

### 3.2 Paso 2 — claves nuevas, con una ausencia declarada

Añadir al payload de cada trial:

| Clave | Qué es | Cuándo falta |
| --- | --- | --- |
| `netReturnPct` | retorno de la curva con costes aplicados | nunca, si hay costes configurados |
| `buyHoldReturnPct` | benchmark de la **misma ventana**, con el **mismo** modelo de costes | si no hay serie de cierre |
| `excessReturnPct` | `netReturnPct − buyHoldReturnPct` | si falta el benchmark |
| `expectancyPct` | media de PnL por round trip, neta | si no hay round trips cerrados |
| `expectancyR` | media de PnL / unidad de riesgo declarada | **casi siempre** (§3.3) |
| `netTradeCount` | round trips cerrados con coste | si no hay operaciones |
| `roundTripCostBps` | coste efectivo aplicado | nunca |

`compute_is_metrics` debe producir las mismas claves para la ruta humana y la de rejilla: hoy
`excessReturnPct` solo existe en `run_backtest`. Una sola vocabulario, un solo productor.

**Corrección obligatoria del benchmark:** `compute_buy_hold_return_pct` es explícitamente «no
costs» ([backtest.py:164-168](../../packages/py/analytics/src/bolsa_analytics/backtest.py)).
Un exceso que resta un benchmark sin fricción a un retorno con fricción **sobreestima el mérito**
de la estrategia. Las dos magnitudes tienen que ser comparables antes de que el exceso sea un gate.

### 3.3 Paso 3 — la parte incómoda: R no se puede inventar

`expectancyR` exige una **unidad de riesgo por operación**. La rejilla no tiene stop: compra con
toda la caja y vende a señal
([sma_grid.py:74-90](../../packages/py/analytics/src/bolsa_analytics/optimize/sma_grid.py)). Sin
stop no hay denominador, y **`R = pnl / |pnl|` no es R**, es el signo.

Decisión de diseño **ratificada** por el propietario el 2026-11-16:

- `expectancyPct` se mide **siempre** que haya round trips.
- `expectancyR` se emite **solo** cuando la estrategia declara unidad de riesgo (stop, ATR o
  presupuesto de riesgo). En cualquier otro caso: `None` y **«Sin dato todavía»**.
- El gate P1 **no** exige R cuando no hay unidad de riesgo: exige `expectancyPct` positiva con
  intervalo. Exigir R sería fabricar el número, que es lo que esta auditoría denuncia.

### 3.4 Paso 4 — el score pasa a ser neto

`score` se calcula hoy bruto. Pasa a:

```
grossScore = totalReturnPct − 0,25 × maxDrawdownPct        (se conserva, columna secundaria)
score      = netReturnPct − 0,25 × maxDrawdownPct          (ranking y bestScore)
```

El peso `0,25` se mantiene **deliberadamente**: es una preferencia de riesgo, no una medida de
beneficio, y cambiarla junto con la introducción del neto impediría atribuir el cambio de
resultados a una sola causa. Se revisa en un trabajo posterior, con datos.

**Consecuencias que hay que aceptar por escrito:**

- `robust_score == oos_score` deja de ser el contrato vigente
  ([test_strategy_lab_phase.py:138-159](../../packages/py/application/tests/test_strategy_lab_phase.py)).
- El histórico no es comparable con el nuevo ranking. La UI debe rotular «neto de costes» y
  marcar los runs anteriores como «sin coste medido».
- Los PnL de trade deben ser netos **antes** de calcular DSR/PSR/PBO, o la deflación medirá un
  universo distinto del que decide
  ([optimize/lab_edge_report.py](../../packages/py/analytics/src/bolsa_analytics/optimize/lab_edge_report.py)).

### 3.5 Paso 5 — declarar el gate `p1`

Con `_gate`, y por tanto fail-closed por construcción: sin medición ⇒ `NOT_EVALUATED` ⇒ bloquea
([strategy_lab_phase.py:246-452](../../packages/py/application/src/bolsa_application/strategy_lab_phase.py)).

Componentes, con umbrales tomados de la política ya fijada en `BASELINE_THRESHOLDS`:

| Componente | Umbral inicial | Fuente |
| --- | --- | --- |
| Beneficio neto | `> minNetReturnPct` (0,0) | [baseline_arms.py:53](../../packages/py/application/src/bolsa_application/baseline_arms.py) |
| Exceso vs benchmark | `> minExcessVsBuyHoldPct` (0,0) | [baseline_arms.py:56](../../packages/py/application/src/bolsa_application/baseline_arms.py) |
| Expectancy | `> 0` con intervalo que no cruce cero | `auto_adaptive.expectancy_interval` |
| Muestra | `netTradeCount >= min_trades` (30) | `LabThresholds.min_trades` |
| Coste declarado | `roundTripCostBps >= minRoundTripCostBps` (22) | [baseline_arms.py:57](../../packages/py/application/src/bolsa_application/baseline_arms.py) |

La última fila es la que impide el escenario del §4.3 de la auditoría: un run con coste 0 no
puede pasar P1, porque el coste no medido es un hueco, no un mérito.

### 3.6 Paso 6 — aplicarlo en los cuatro sitios, a la vez

| Sitio | Cambio |
| --- | --- |
| `PROMOTION_GATES` | añadir `p1` (octava puerta) — [strategy_lifecycle.py:100-108](../../packages/py/domain/src/bolsa_domain/entities/strategy_lifecycle.py) |
| `REQUIRED_GATES_BY_STATE` | añadir `p1` a **FINALISTA** y **VALIDACION**; **añadir también `risk` a FINALISTA**, que hoy no lo exige |
| Barrera del TOP3 | se propaga sola por `LAB_VALIDATED_GATES = required_gates_for(FINALISTA)`; **revisar** que ningún llamador pase `min_gates` relajado |
| Gate de paper (cliente) | añadir beneficio neto, expectancy y coste declarado; **eliminar los `?? 0`** de [backtest-paper-gate.ts:73,137,215](../../apps/web/src/features/backtests/backtest-paper-gate.ts) |

Añadir `risk` a FINALISTA es una decisión de producto que este plan **propone** porque hoy el
conjunto no es monótono: un gate que aparece en VALIDACION y no en FINALISTA permite que el
campeón empeore al avanzar de fase.

### 3.7 Tests

- `test_promotion_gate_names_are_the_seven` → pasa a ocho y cambia de nombre
  ([test_auto_orchestrator.py:374-384](../../packages/py/application/tests/test_auto_orchestrator.py)).
- Los cinco positivos del orquestador (`:115,396,432,526,565`) bloquean por `p1`
  `NOT_EVALUATED`: hay que darles evidencia **con coste y beneficio**, no relajar el gate.
- `test_strategy_top3_coach_phase.py:97` fija la barrera de cuatro: sube a cinco.
- `test_strategy_lab_phase.py:138` fija `robust_score == OOS`: se reescribe al contrato nuevo.
- Nuevos: coste aplicado por los cuatro simuladores, `netReturnPct`/`excessReturnPct` presentes,
  `expectancyR` `None` sin unidad de riesgo, gate `p1` `NOT_EVALUATED` sin muestra, y un test que
  **muerda**: el campeón bruto-ganador/neto-perdedor del §4.3 debe quedar bloqueado.

**Criterio de hecho:** con costes 32 bps, una estrategia con retorno bruto +1,10 % y 10 round
trips **no** obtiene `lab_validated` ni entra en FINALISTA, y el intento declara «Sin dato
todavía» o FAIL con el componente que falló. **Esfuerzo: L. Riesgo: alto** (cambia qué gana).

## 4 · R3 · Confianza en el dato y honestidad del copy

**Impacto en beneficio: indirecto pero decisivo.** Un TOP que el cliente puede inventar hace
irrelevante cualquier gate posterior.

### 4.1 El slot deja de ser autorado por el cliente

Validar en servidor, en el caso de uso y no en el DTO:

- el `runId` **existe** en `backtest_runs`;
- pertenece al instrumento del path;
- ese run tiene evaluación LAB con `p1` medido;
- `evidenceLevel` **se deriva** de los gates; no se acepta del cliente;
- si el slot declara `lab_validated` sin `p1` en PASS ⇒ `422` con el motivo, no un `200` con el
  dato guardado.

**Archivos:** [instrument_strategy_tops.py (ruta)](../../apps/api-python/src/bolsa_api/api/v1/routes/instrument_strategy_tops.py),
[instrument_strategy_tops.py (caso de uso)](../../packages/py/application/src/bolsa_application/instrument_strategy_tops.py),
[shared/instrument-strategy-top.ts](../../packages/shared/src/instrument-strategy-top.ts).

**Compatibilidad:** los TOP ya guardados con `runId` inválido no se borran: se marcan
«procedencia no verificada» y **no** son promocionables. Coherente con «solo runs nuevos».

### 4.2 Eliminar la auto-escritura del panel

Sustituir el `useEffect` de reparación
([instrument-strategy-top-panel.tsx:493-535](../../apps/web/src/features/backtests/instrument-strategy-top-panel.tsx))
por un **aviso de solo lectura** que declare la desalineación y ofrezca un botón explícito. Abrir
una pantalla no puede subir la `version` de un registro de evidencia.

### 4.3 Corregir el copy del despliegue

Texto canónico a imponer en los tres sitios y en el tooltip del chip:

> «Desplegar en demo» crea una **cuenta paper de procedencia** vinculada a la estrategia y
> guarda la evidencia del LAB en esa cuenta. **No** escribe trades ni asientos en el ledger de la
> cuenta DEMO.

| Archivo | Qué cambia |
| --- | --- |
| [paper-paths-copy.ts:5-28](../../apps/web/src/features/settings/paper-paths-copy.ts) | cabecera y `PAPER_PATH_LAB`: invertir «cuenta activa DEMO» y «no tipo Paper» |
| [domain-language.md:125-126](./../domain-language.md) | invertir las dos filas `Paper` y `Desplegar en demo` |
| [research-lifecycle.md:19,281](./research-lifecycle.md) | «deploy en cuenta activa DEMO» → cuenta paper de procedencia |
| [universe-chip.tsx](../../apps/web/src/features/platform/universe-chip.tsx) | tooltip coherente con lo anterior |

**Criterio de hecho:** un test de copy afirma la frase canónica en los tres sitios, y ningún
documento ni tooltip afirma que el despliegue escribe el ledger DEMO. **Esfuerzo: M. Riesgo: bajo.**

## 5 · R2 · Disparador gobernado del embudo (E4–E6)

**Impacto: hace alcanzable lo que hoy solo existe de noche y con un flag OFF.**

### 5.1 Contrato

```
POST /api/auto/orchestrator/run
body: { instrumentId, accountId?, dryRun?: true, toPhase?: "finalista" }
```

Reglas, todas obligatorias:

- **`dryRun` por defecto `true`.** Un `POST` sin cuerpo no escribe nada.
- **Nunca escribe ACTIVE.** El alcance máximo es FINALISTA; el salto a ACTIVE sigue pasando por
  `decide_promotion` y por P1.
- **Idempotencia** por `(instrumentId, accountId, snapshot, cycle)`: repetir no duplica.
- **Ámbito**: el `instrumentId` debe estar en ESTUDIO; una cuenta cerrada es `409`.
- **Auditoría**: un evento por ejecución con actor, `dryRun`, fase alcanzada, gates evaluados y
  resultado. Sin eso, el disparador es una puerta trasera.
- **Fail-closed**: si el orquestador no puede construir la evaluación, el resultado es
  `INCOMPLETE` con motivo; nunca un `200` optimista.
- **Prohibido**: aceptar evidencia del cliente en el cuerpo; saltar gates; sustituir el universo
  ESTUDIO; escribir el TOP directamente.

### 5.2 Implementación

- Extraer el cuerpo del ciclo del worker a un servicio reutilizable (`run_cycle_once`), para que
  worker y ruta compartan una sola implementación.
- La ruta valida y delega; no reimplementa el embudo.
- UI: botón «Ejecutar embudo» en Finalistas con `dryRun` visible y el recibo del resultado.

**Archivos:** ruta nueva en `apps/api-python/src/bolsa_api/api/v1/routes/`,
[auto_orchestrator_worker.py](../../apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py),
[evaluaciones/lectura] (hoy `strategy_evaluations` no tiene lectura HTTP),
[instrument-strategy-top-panel.tsx](../../apps/web/src/features/backtests/instrument-strategy-top-panel.tsx).

**Nota de contrato:** esta ruta **sí** es aditiva en `openapi.json`; exige `contract:gen` y por
tanto queda fuera del invariante `Δ contrato = 0` de la auditoría. Es una decisión explícita, no
un efecto colateral.

**Criterio de hecho:** un `POST` con `dryRun` produce un recibo con gates y fase, sin escrituras
verificables; el mismo `POST` repetido devuelve el mismo `runId` de job; un instrumento fuera de
ESTUDIO devuelve `409`. **Esfuerzo: M. Riesgo: medio** (superficie nueva de escritura).

## 6 · R5 · Una sola puerta LAB

- **Asesor · Laboratorio** pasa a: resumen de estado + último experimento + CTA «Abrir el
  Laboratorio» con deep-link a `/backtests`. Nada de historial ni detalle completo.
- **Mover a `/backtests`** las dos cosas que hoy solo existen en el Asesor y que no se pueden
  perder: la **salud/cobertura de métricas** (`lab-health-card`) y el **historial de
  experimentos con su detalle** (`lab-trial-history-panel`).
- **Chip de universo** en el Asesor mientras el resumen siga existiendo.

**Archivos:** [asesor-hub-tabs.tsx](../../apps/web/src/features/research/asesor-hub-tabs.tsx),
[lab-summary-panel.tsx](../../apps/web/src/features/research/lab-summary-panel.tsx),
[lab-health-card.tsx](../../apps/web/src/features/research/lab-health-card.tsx),
[lab-trial-history-panel.tsx](../../apps/web/src/features/research/lab-trial-history-panel.tsx),
[research-page.tsx](../../apps/web/src/features/research/research-page.tsx).

**Criterio de hecho:** ningún dato del LAB es alcanzable solo por el Asesor; el deep-link
conserva la posición y el instrumento; el chip se renderiza en el resumen. **Esfuerzo: M. Riesgo: bajo.**

## 7 · R4 · P2 y P3 en el primer nivel del LAB

- El resultado de un run declara **estrategia #1 + `indicatorSpecs`** sin abrir el detalle (P3).
- Cuando exista plan, declara **entrada, stop y objetivos**, distinguiendo `WATCH` / `BLOCKED` /
  `EXPIRED` de «sin plan» (P2).
- Reutilizar la proyección existente `buildInstrumentDailyAnalysis` en vez de calcular en el
  componente: `UNKNOWN ≠ 0` y huecos declarados ya están resueltos allí.

**Criterio de hecho:** un run sin plan muestra «sin plan declarado», no un hueco vacío; un run
con plan muestra niveles en la tarjeta de resultado. **Esfuerzo: M. Riesgo: bajo.**

## 8 · R7 · Cobertura y CI

- Incorporar los tests de gates del LAB a la batería que ya corre en CI (`test:optimize` no los
  ejecuta hoy).
- `test_strategy_lifecycle_pg.py`: añadirlo al `--ignore` del job offline **y** darle guarda
  anti-skip en el job con PostgreSQL.
- Tests DOM de `lab-*` y de `backtest-paper-gate` con los casos de ausencia (`Sin dato todavía`).
- Un test que fije el append-only de Evidence.
- Un e2e mínimo de `/research` (deep-link) y de `/backtests` (resultado con P1).

**Criterio de hecho:** quitar el gate `p1` rompe al menos tres tests; volver a poner los `?? 0`
rompe al menos dos. **Esfuerzo: M. Riesgo: bajo.**

**Cierre (2026-11-16).** Los gates del LAB entran en la batería que ya corre en CI:
`verify_optimize_battery.mjs` suma los tests Python de procedencia, gate P1, fase LAB, coach
FINALISTA y ruta del orquestador, y los tests web de checklist, tarjeta de resultado, sección
LAB, disparador gobernado, TOP por instrumento, historial/detalle de trials, deep-link y
navegación. `verify_fase2_battery.mjs` registra `test_research_evidence_append_only.py`.
`test_strategy_lifecycle_pg.py` sale de los jobs offline con `--ignore` **y** corre en
`lifecycle-pg` con `STRATEGY_LIFECYCLE_PG_REQUIRED=1`, donde un skip es rojo. Los casos de
ausencia se fijan en DOM: un dato que falta dice «Sin dato todavía», nunca `0` ni `—`, y el
checklist de papel exige reconocer el hueco de beneficio neto antes de habilitar el despliegue.
`optimize-lab.yml` vigila además `features/research/**` y `features/confirm/**`.

## 9 · R6 · Durabilidad y trazabilidad

Cuatro puntos que la auditoría dejó abiertos y que **no** bloquean R1, pero que impiden operar
con confianza:

- **`F-D` server-side**: el TOP experimento as-of D no puede vivir solo en el cliente.
- **Cartera LAB**: o se persiste con identidad propia, o se declara efímera en la UI. Hoy no se
  sabe cuál de las dos es.
- **CORE-R**: la cola deja de depender del dispositivo.
- **Append-only**: guarda en base de datos, no solo convención.

**Esfuerzo: L. Riesgo: medio.** Puede ir después de R2.

**Cierre (2026-11-16).** *Append-only* deja de ser convención:
`ResearchEvidence` es un `@dataclass(frozen=True)` y `SqlAlchemyResearchEvidenceRepository`
solo expone `insert_evidence`, `get_by_id` y `list_evidence`; el guardián
`test_research_evidence_append_only.py` falla si aparece `update`, `delete`, `upsert`,
`merge` o cualquier parámetro de sobreescritura por conflicto, y si el módulo importa
sentencias de mutación. **CORE-R** ya tiene su fuente de verdad en base de datos
(`GET|PUT /api/accounts/{id}/core-r`): el `localStorage` es caché, no el registro, así que la
cola no depende del dispositivo. **Cartera LAB** se declara **efímera** en el producto y no se
finge persistente: el banner lo dice con esas palabras («Cartera LAB efímera · no escribe DEMO ·
guarda Evidence para conservar») y la evidencia se guarda explícitamente («Guardar Evidence»).

**`F-D` deja el navegador (segunda tanda, 2026-11-16).** El experimento TOP as-of D se
persiste con la misma infraestructura auditable que el resto de Evidence: **append-only** en
`research_evidence` con `source='dia_d_experiment_top'`,
`math_version='dia_d_experiment_top_v0'` y `schemaVersion='dia_d_experiment_top_v1'`. El
experimento vigente es la fila **más reciente** para `(instrumento, timeframe, D)`; guardar otra
vez no sobreescribe historia, añade un intento nuevo. Contrato HTTP:
`POST /api/research/dia-d-experiment-top` (201) y `GET
/api/research/dia-d-experiment-top?instrumentId=…&timeframe=…&asOfDiaD=…`, donde `data: null`
es una respuesta **legítima** y significa «no hay experimento guardado» — el hueco se declara.

Lo que el servidor **no** acepta del cliente:

- **Procedencia**: cada slot con `runId` se verifica en servidor
  (`verify_top_provenance`, R3). Un `runId` inexistente o de otro instrumento devuelve **422**;
  nunca se guarda una cita que el servidor no puede verificar.
- **Nivel**: `C` si **todos** los slots citan un run verificado, `D` si alguno es narrativa. El
  cliente no puede inyectar `level` ni `evidenceLevel`.
- **Sello temporal**: lo pone el servidor al insertar; el cliente no envía `savedAt` ni
  `evidenceId`.
- **Futuro**: `asOfDiaD` tiene que ser una fecha ya cerrada (400 si es futura) y los `rank` de los
  slots tienen que ser `1..N` consecutivos (400). El payload es `extra="forbid"`.

En el cliente, `useDiaDExperimentTop` lee el servidor y **hidrata** la caché local solo con
evidencia verificada, sin pisar un registro local más reciente; `DiaDVerifyHost`,
`TradingOperativaPanel` e `InstrumentStrategyTopPanel` consumen ese hook, y el panel muestra el
estado del servidor y el `evidenceId` como prueba de que lo guardado es auditable. Guardar un
experimento **no** toca F-hoy, ni Finalistas, ni el ledger DEMO.

Tests: `test_dia_d_experiment_top.py` (16 casos: fecha ISO y no futura, append-only con `source`
propio, derivación `C`/`D`, rechazo de `runId` ajeno o inexistente, ranks consecutivos, lectura
con filtro por `source`), `test_dia_d_experiment_top_route.py` (8 casos HTTP: 201, 400 por fecha
futura y ranks rotos, 422 por campo extra y por run no verificable, 200 con `data: null`),
`dia-d-experiment-top.test.ts` (6 casos de espejo del sello del servidor e hidratación) y
`use-dia-d-experiment-top.test.tsx` (3 casos DOM de hidratación, hueco declarado y fecha nula).
Las cuatro entran en las baterías (`test:optimize`, `test:fase2`) y el smoke de Fase 2 sondea la
ruta cuando el build desplegado ya la trae (404 = build anterior, se avisa y no falla).

**Smoke en vivo (2026-11-16).** Instancia efímera en `:8010` contra la PostgreSQL real (la de
`:8000` corría un build anterior y devolvía 404): hueco ⇒ `200 {"data":null}`; `POST` con `runId`
real ⇒ **201** con `level='C'` y `evidenceId`; `GET` posterior devuelve el mismo `id`; `runId`
inexistente ⇒ **422**; fecha futura ⇒ **400**; campo extra `level` ⇒ **422**; `rank=2` sin `rank=1`
⇒ **400**; `POST` repetido ⇒ **201** con `evidenceId` nuevo y el `GET` devuelve el vigente
(append-only, 2 filas). La evidencia guardada declara `p1Status='not_evaluated'` y
`reason='neto_no_medido'` junto a `level='C'`: el experimento **no** afirma P1 medido, solo que
los slots citan runs reales.

## 10 · R8 · Documentación y vocabulario

- **ADR-052** · gate P1: componentes, umbrales, `NOT_EVALUATED ⇒ «Sin dato todavía»`, vigencia
  para runs nuevos y el hecho de que el embudo se congela hasta que haya un run con coste medido.
- **ADR-053** · disparador gobernado: contrato, `dryRun`, idempotencia, ámbito, auditoría, límite
  en FINALISTA.
- **Correcciones**: cabeceras de ADR-019 y del diseño dual; premisas DÍA-D `:68`; `HELP.md`
  (ocho puertas, `CONFIRMED` reservado y no emitido, `NOT_EVALUATED` → «Sin dato todavía»);
  `domain-language.md`; `research-lifecycle.md`; `README.md` (falta ADR-045…051);
  `engineering-index`; y cierre de `H-8` en la certificación del Asesor.
- **`P1` se califica siempre**: `P1-gate` para el nuevo; el resto de sentidos, con su apellido.

**Criterio de hecho:** un lector que solo lea los documentos puede predecir qué hace el código
con un run sin coste. **Esfuerzo: M. Riesgo: bajo.**

**Cierre (2026-11-16).** ADR-052 y ADR-053 escritos y registrados en el índice (`README.md`,
ADR-040…053). Cabeceras de ADR-019, del diseño dual y de las premisas DÍA-D actualizadas al
estado `U1`–`U5` implementado. `HELP.md` documenta las ocho puertas, el fail-closed
`NOT_EVALUATED → «Sin dato todavía»`, el congelado de runs históricos sin coste medido y que
`CONFIRMED` está reservado y no se emite. `domain-language.md` y `research-lifecycle.md`
distinguen **`P1-gate`** (la puerta) de **`P1`** a secas (la baseline) y fijan el contrato del
disparador gobernado. `H-8` se cierra en la certificación del Asesor: la pestaña por defecto es
**Cartera**, no la más vacía.

## 11 · Lo que este plan no hace

- **No** cambia umbrales de PBO, WFE, DSR ni drawdown.
- **No** cambia el peso `0,25` del score (deliberadamente, para aislar la causa del cambio).
- **No** migra datos históricos ni re-ejecuta la rejilla.
- **No** toca AUTO, la ejecución real ni el ledger.
- **No** implementa R6 ni R2 en la misma tanda que R1: se aprueban y se ejecutan por separado.

## 12 · Batería de verificación

Por fase, y con la regla de que **un verde no certifica nada que no se haya medido**:

- **R1:** tests nuevos de coste y de gate; la batería de gates del LAB en CI; comprobación de que
  el caso bruto-ganador/neto-perdedor queda bloqueado; `replay-repro` sin cambio (R1 no toca el
  motor de decisión de TRADING).
- **R3:** test de servidor que rechaza `runId` inexistente y `evidenceLevel` inyectado; test DOM
  del aviso de solo lectura; test de copy canónico.
- **R2:** test de idempotencia, de `dryRun` sin escrituras, de `409` fuera de ESTUDIO, y de que
  ACTIVE no se alcanza.
- **R5/R4:** e2e de deep-link y de tarjeta de resultado.
- **R6:** `test_dia_d_experiment_top.py` (append-only, nivel derivado, run ajeno ⇒ 422),
  `test_dia_d_experiment_top_route.py` (201/400/422 y `data: null` en el hueco), tests de espejo
  e hidratación en el cliente, y guardián de `research_evidence` sin mutaciones.
- **Transversal:** `pnpm typecheck`, `lint`, `contract:check`, `ruff`, `mypy`, `lint-imports`.

## 13 · Riesgo abierto que sigue siendo decisión del propietario

1. **Congelación del histórico** (§1): entre R1 y el primer run nuevo con coste medido, el embudo
   no puede promocionar nada. Hay que decidir si eso se comunica en la UI como estado esperado o
   si se permite una excepción auditada para los TOP vigentes.

**Cerrados el 2026-11-16:** añadir `risk` a FINALISTA (decidido: sí, §1 y §3.6) y no fabricar
`expectancyR` sin unidad de riesgo (decidido: no se emite, §1 y §3.3).
