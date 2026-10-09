# Contrato de evidencia PAPER para la confirmación — DÍA-D · paso 4 (MIA)

> **AsOf:** 2026-10-09 · **Base:** `v2.88.97-beta` · **Naturaleza:** contrato **read-only** — no toca motor, contrato HTTP ni Alembic (`Δ motor = 0`; `git diff --name-only -- packages/py` **vacío**).
> **Origen:** paso 4 de la orden recomendada por la auditoría externa MIA: *«Definir el contrato PAPER de confirmación. No emitir CONFIRMED todavía; acordar qué evidencia durable y qué criterios deben cumplirse para habilitarlo en el futuro.»*
> **Premisas:** [`PROJECT_PREMISES.md` §5.2](../PROJECT_PREMISES.md) — cuatro capas de veredicto que **no** son equivalentes y la regla de no promoción.
> **Precedentes obligatorios:** `S4` (agregado de evidencia DÍA-D) y `P4` («Por qué AUTO no operó»): read-models puros que declaran el hueco con el vocabulario único de `@/components/absent-data` (`UNKNOWN ≠ 0`).
> **Auditoría de referencia:** [`auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`](./auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md) §3 (`P4-2`: sin `CONFIRMED`; el lado ejecutado PAPER queda `NOT_MEASURED`).

---

## 0. Alcance y método

- Se **define** el contrato de la evidencia que habilitaría la confirmación de la ejecución real PAPER. **No se emite** la confirmación.
- Se enumera la **evidencia durable exigible** y su **origen** (artefacto/tabla/evento durable que la demuestra), marcando de forma explícita **lo que hoy NO se emite**.
- Se fijan **criterios de suficiencia falsables** (medibles y parametrizables), no aspiracionales.
- Regla dura: lo **ausente** se declara «Sin dato todavía»; **no** se fabrica ni se rellena con `0` (§5.1.4). Un criterio no puede darse por cumplido sin dato.
- El contrato es **definido y verificable**, pero queda **NO satisfecho** hoy: la capa PAPER es un **hueco estructural**.
- Este documento **no** re-mide DÍA-D ni cambia umbrales; sólo acuerda la vara futura.

---

## 1. Evidencia durable exigible

Toda la evidencia se lee del **registro durable** (no de memoria del proceso, no del replay, no de la proyección):

| # | Categoría | Hecho durable exigido | Origen durable (artefacto/tabla/evento) | ¿Se emite hoy? |
| --- | --- | --- | --- | --- |
| 1 | **Operaciones** | Round-trip (ida y vuelta) terminado: cantidades balanceadas (Σ buy = Σ sell) y sin posición abierta | Derivado del material durable de fills (`sim_fill_finance_context`, migraciones `028`/`029`; `cycle_id` en migración `044`) por el FIFO de `cycles_from_fills` (AUTO-17). Denominador de R en `portfolio_reservations` | **PARCIAL** — hay fills y ciclos, pero el material PAPER histórico nació sin `cycle_id` (`761` fills / `0` con ciclo en `v2.72`) |
| 2 | **Ejecuciones** | Fill durable con `execution_id` único, lado, cantidad, precio, atribución de cuenta y de operación | Tabla `sim_fill_finance_context` (PK `execution_id`; `side`/`quantity`/`price`; `account_id`; `cycle_id`; `strategy_version_id`; `created_at`) | **SÍ (con condiciones)** — la fila existe; la atribución de ciclo sólo desde la migración `044` |
| 3 | **Cierres** | Hecho de liquidación con identidad de ciclo, cantidad cerrada, motivo de salida y PnL con su medición | Evento append-only `auto_cycle_settlement` en `decision_journal_entries` (ADR-029 F1), construido por `build_cycle_settlement_entry` (`pnl`/`pnlMeasurement`); órdenes de salida en `auto_exit_orders` | **CONDICIONADO** — sólo se escribe con `AUTO_OPERATIONAL_AUDIT=1` (**default OFF**); un `CYCLE_CLOSED` reconstruido de fills **no** es un settlement |
| 4 | **Costes (fricción)** | Fricción **aplicada** por ciclo: `|price − reference_mid| × qty` por pata, agregada con `measurement = COMPLETE` | `reference_mid` durable en `sim_fill_finance_context` (migración `046`), agregado por `applied_cost.applied_cost_from_fills` (AUTO-16/17) sobre las patas de ENTRADA y SALIDA del ciclo | **SÍ, si `reference_mid` está medido** — una pata sin referencia deja el coste como **suelo** (`PARTIAL`), nunca `0` |
| 5 | **Resultados** | PnL realizado **durable** por operación cerrada, con medición `COMPLETE` | Payload del settlement `auto_cycle_settlement` (`pnl` + `pnlMeasurement`); PnL realizado en el dominio de ciclo de vida (`lifecycle`/`_sim_realized_pnl`) | **CONDICIONADO** — depende de (3); el PnL truncado viaja `None` + `PARTIAL`, jamás una cifra sobre un subconjunto |

### 1.1 Lo que HOY no se emite (declarado)

- **La confirmación (`CONFIRMED`).** Está **reservada** y **no se emite**: el feedback PAPER sólo publica `OOS_SUPPORTED`/`MIXED`/`REFUTED`/`NOT_MEASURED` y el gate de ventana usa `READY`/`INCONCLUSIVE`. El **lado ejecutado** de días históricos queda `NOT_MEASURED`.
- **Los hechos durables del journal**, por defecto. `auto_entry_order`, `auto_protection_event` y `auto_cycle_settlement` sólo se escriben tras el flag `AUTO_OPERATIONAL_AUDIT` (**OFF** por defecto). En la ventana PAPER se inyecta `AUTO_OPERATIONAL_AUDIT=1` **sólo** en el `env` del proceso hijo.
- **La decisión de cartera durable (`PortfolioDecision`) y la materialización de posición por operación.** Permanecen como deuda declarada del [plan PARKED](./plan-cierre-operativa-auto-2026-10-08.md) (`F2-1`/`F2-2`); **no** se infieren del ranking ni del fill.
- **El resultado realizado agregado a primer nivel.** Hoy el read-model de resumen sólo publica el no realizado (`S3` del plan PARKED).
- **La proyección `sim_auto_positions` como autoridad.** Es una **proyección de recuperación reconstruible** (AUTO-9.1 `P1-01`), **no** una autoridad financiera: por sí sola **no** puede acreditar una operación.

---

## 2. Criterios de suficiencia (falsables)

Cada criterio se evalúa a **cumplido / incumplido / sin dato todavía**. Sin dato medido, el criterio **no** se declara cumplido. Umbrales declarados y parametrizables (no se bajan para forzar una confirmación):

| ID | Criterio | Enunciado falsable | Umbral declarado | Fuente / referencia |
| --- | --- | --- | --- | --- |
| `window` | Ventana operativa suficiente | La ventana declara **y** alcanza un mínimo de días y episodios operados | `≥4 días` **y** `≥2 episodios` | `PROJECT_PREMISES` §5.1 · `operability_window` (`READY`/`INCONCLUSIVE`) |
| `operation_lineage` | Operaciones con linaje de ciclo | Hay operaciones cerradas suficientes **y todas** declaran su identidad de ciclo (`cycle_id`) | `≥32` operaciones cerradas (por estrategia) y `withCycleLineage == operations` | `DEFAULT_MIN_MEASURABLE_CYCLES_PER_STRATEGY` (`paper_material_readiness`) |
| `execution_attribution` | Ejecuciones atribuidas | Hay ejecuciones durables suficientes **y todas** están atribuidas a su operación | `≥64` fills (`2 × 32`) y `attributed == fills` | `sim_fill_finance_context` (atribución `cycle_id`, migración `044`) |
| `closure_reconciliation` | Cierres reconciliados | Hay cierres durables suficientes **y todos** reconcilian con la ida y vuelta del material | `≥32` settlements y `reconciled == settlements` | `auto_cycle_settlement` · comparador declarado↔ejecutado (`dia_d_auto`) |
| `cost_coverage` | Cobertura de costes | Todos los cierres que exigen coste aplicado lo tienen **medido por completo** (`COMPLETE`) | `≥32` cierres con coste exigido y `complete == expected` | `applied_cost` (AUTO-16) · `reference_mid` (migración `046`) |
| `durable_results` | Resultados durables | Hay resultados durables suficientes, medidos sobre el cierre real de cada operación | `≥32` cierres con resultado medido `COMPLETE` | `pnl`/`pnlMeasurement` del settlement |
| `non_contradiction` | Sin contradicciones | El material **no** declara ninguna contradicción entre sus cierres | `contradictions == 0` | contraste de cierres (`reconcile_*`, comparador declarado↔ejecutado) |

> Nota de método: cada criterio se mide de forma **independiente**; ninguno rellena el hueco de otro. Un contador ausente (`null`) produce «Sin dato todavía», **no** un `0` incumplido.

---

## 3. Regla de no promoción

- **Ningún criterio aislado confirma la operativa.** Cumplir la ventana no confirma las operaciones; tener operaciones no confirma los cierres; tener cierres no confirma los costes; y **ninguno** de ellos confirma la ejecución real.
- **La confirmación permanece RESERVADA y no se emite en esta ronda.** El read-model devuelve siempre el literal `NO_CONFIRMED`, **incluso si los siete criterios se cumplen**: la promoción exige una decisión de contrato/humana posterior, no una condición de datos.
- **`READY ≠ CONFIRMED` · `MATCH ≠ CONFIRMED` · `OOS_SUPPORTED ≠ CONFIRMED`** (§5.2). La evidencia OOS del REPLAY **no** acredita la ejecución PAPER.
- **Frontera de capas.** La capa PAPER sigue siendo un **hueco estructural**: este contrato la **describe**, no la mide.

---

## 4. Qué evidencia NO vale

| Evidencia | Por qué NO vale |
| --- | --- |
| **Dato ausente** | Ausencia **no** es `0`. Un hueco se rotula «Sin dato todavía»; jamás se colapsa a un cero ni a un criterio cumplido (`UNKNOWN ≠ 0`). |
| **`ranking` (SELECTION / TOP_N)** | Es ordenación, no decisión: `ranking ≠ decisión` (`UI5-12`). No materializa una operación. |
| **`propuesta` (propuesta/plan declarado)** | Una propuesta **no** es una posición materializada; sin traza durable de materialización sigue siendo «Sin dato todavía». |
| **Inferencia del replay / de la proyección** | El replay y la proyección reconstruible (`sim_auto_positions`) **no** son ejecución real: un `CycleClosed` reconstruido de fills no es un settlement. |
| **OOS del REPLAY (`OOS_SUPPORTED`)** | Acredita el replay fuera de muestra, **no** la ejecución PAPER (`OOS_SUPPORTED ≠ CONFIRMED`). |
| **Precio sin referencia de fricción** | El precio SIM lleva la fricción dentro; sin `reference_mid` la fricción aplicada **no** se puede afirmar (sería «fricción gratis»). |
| **Un agregado sin declarar su medición** | Sumar sólo lo medible produce un **suelo**: un `PARTIAL` no es total y no puede entrar al R neto como si lo fuera. |

---

## 5. Estado actual declarado

**El contrato queda DEFINIDO pero NO satisfecho.** Hoy:

- La **capa PAPER es un hueco estructural**: no recibe hechos y no tiene rama que la mida (igual que en `S4`).
- El read-model devuelve `verdict = "NO_CONFIRMED"` con la lista de criterios **sin dato todavía** (material histórico) o **incumplidos** (material insuficiente), y jamás cumple un criterio sin dato.
- El material PAPER medido hasta ahora (`paper_material_readiness`) declaró el material **BLOQUEADO** por estructura (fills sin linaje de ciclo, sin reservas, sin cierres): es exactamente `PRODUCER_READY` pendiente, no confirmación.
- Emitir la confirmación exigiría, además, habilitar escrituras durables hoy **default OFF** (`AUTO_OPERATIONAL_AUDIT`) y cerrar la deuda de decisión/posición durable (`F2-1`/`F2-2`): **fuera de alcance** de esta ronda.

---

## 6. Read-model puro y regresión (entregable B)

Superficie read-only, determinista y sin `Date`/I-O, bajo `apps/web/src/features/auto-monitor/`:

| Fichero | Rol |
| --- | --- |
| `paper-confirmation-contract.ts` | Read-model puro: tipos de entrada nullable (ventana, operaciones, ejecuciones, cierres, costes, resultados), evaluación de los siete criterios y veredicto literal `NO_CONFIRMED`. |
| `paper-confirmation-contract-labels.ts` | Única casa de la copy de primer nivel (títulos, enunciados, orígenes y motivos); reutiliza `absentDataLabel()` para el hueco. |
| `paper-confirmation-contract.test.ts` | Regresión falsable de las invariantes. |

### 6.1 Verificación (resultado real)

```
# 1. Suites de auto-monitor
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor
#    → Test Files 10 passed (10) · Tests 74 passed (74)

# 2. Type-check del paquete web
pnpm --filter @bolsa/web exec tsc --noEmit
#    → exit 0 (sin errores)

# 3. Lint de los tres ficheros nuevos
pnpm --filter @bolsa/web exec eslint \
  src/features/auto-monitor/paper-confirmation-contract.ts \
  src/features/auto-monitor/paper-confirmation-contract-labels.ts \
  src/features/auto-monitor/paper-confirmation-contract.test.ts
#    → exit 0 (sin avisos)

# 4. Contrato HTTP en sincronía
pnpm --filter @bolsa/web run contract:check
#    → contract:check OK — openapi.json y schema.d.ts coinciden con el commit.

# 5. Δ motor = 0
git diff --name-only -- packages/py
#    → (vacío)
```

Invariantes cubiertas por la regresión: sin entradas todo es «Sin dato todavía» y `verdict === "NO_CONFIRMED"`; el token reservado no aparece en `JSON.stringify(resultado)` comprobado con word-boundary (`/\bCONFIRMED\b/`); un criterio con dato ausente **no** se marca cumplido; con los siete criterios cumplidos el veredicto **sigue** siendo `NO_CONFIRMED`; y el módulo no conoce identidad ajena (`SAME_CONFIRMED`).

---

## 7. Falsabilidad del entregable

- Los siete criterios y sus umbrales están **declarados** y son medibles por separado.
- El veredicto es un **tipo literal** `NO_CONFIRMED`; no existe rama que emita la confirmación.
- La evidencia exigible cita su **origen durable** con nombre de tabla/evento, y se marca lo que **no** se emite hoy.
- La regresión muerde: quitar un dato pone el criterio en «Sin dato todavía»; intentar colapsarlo a `0` o a cumplido rompe un test.

## 8. Fuera de alcance

- **No** se emite `CONFIRMED` ni se habilita la promoción.
- **No** se cablea la superficie en paneles, rutas ni componentes existentes.
- **No** se toca motor, contrato HTTP, migraciones Alembic ni `contract:gen`.
- **No** se re-mide DÍA-D ni se corrigen los huecos del material histórico (`AUTO-10` no reescribe el pasado).
- La reactivación del [plan de cierre](./plan-cierre-operativa-auto-2026-10-08.md) (decisión de cartera durable, materialización de posición) queda **PARKED** con dueño y disparador.
