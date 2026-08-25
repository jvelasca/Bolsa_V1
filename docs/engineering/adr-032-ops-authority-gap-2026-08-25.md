# Gap ADR-032 vs autoridad operativa (post-audit discontinuidad)

> **Padre:** [`audit-ext-v19-ops-discontinuity-triage-2026-08-25.md`](./audit-ext-v19-ops-discontinuity-triage-2026-08-25.md) · política v1.9 [`032-operational-core-tradeplan-positionstate-execution.md`](../adr/032-operational-core-tradeplan-positionstate-execution.md) · constitución v1.10 [`033-operational-authority-position-persistence.md`](../adr/033-operational-authority-position-persistence.md).
> **AsOf:** 2026-08-25. **Estado:** **CERRADO docs-only.** ADR-032 modeló objetos; esta auditoría pide que gobiernen. Congela **autoridad**, no una lista de campos nueva.
> **Regla:** cero runtime · cero `contract:gen` · cero Alembic · cero Consola de Mesa · cero mappers thin.

---

## 0. Veredicto del gap

ADR-032 acertó la frontera de **modelo**:

```text
Antes de entrar:  DecisionPackage → TradePlan → check_opening
Después:          PositionState → ExitPlan → ExitPermission → Execution
```

v1.9 **cerró** esas factories. El auditor de discontinuidad acierta la frontera de **autoridad**:

```text
MODELO (v1.9)                  AUTORIDAD (v1.10)
PositionState factory          Position persistida + fill wire
ExitPlan factory               única cadena de producto
OrderIntent fill               sigue fill; NO se convierte en dios
Pending «stop/limit»           honesty: orden a precio
Ticket % caja                  firma contra riesgo del TradePlan
Hoy = cola de entrada          mesa: posiciones primero (P4, no H1)
```

Hueco: el ADR nombra objetos y _intenciones_; el producto sigue mostrando un holding `qty/avg_cost` tras el fill. **No** se implementa aquí. **No** se reabre F1–F4 para campos extra.

---

## 1. Qué ADR-032 ya cubre (no reabrir)

| Objeto          | Estado v1.9                     | Lo que el auditor pide de más    | Arbitraje                                    |
| --------------- | ------------------------------- | -------------------------------- | -------------------------------------------- |
| TradePlan v1    | Campos gap §1 **en código**     | Snapshot canónico en la posición | P1 copia el plan al nacer; no otro TradePlan |
| PositionState   | Factory from_fill + F2.1        | Agregado durable versionado      | **P1** — persistir, no reinventar            |
| ExitPlan        | Razones canónicas, ≠ execution  | Motor de salida de producto      | **P3** — wire + autoridad única              |
| ExitPermission  | Gate puro ALLOW/DENY            | Kill switch asimétrico           | **H2** invariante; no fusionar con opening   |
| ExecutionPlan   | PAPER Journal/Replay/Validation | Bracket / OCO / broker           | Sigue parked. Side short = **H2**            |
| Daily Console   | Parked §5                       | Consola de Mesa ahora            | **P4**, después de P1–P3                     |
| Portfolio layer | Parked §5                       | Posiciones antes que TOP         | **P4**                                       |

Thin 5.x/8.x siguen stand-in. **No** copiar `exitRadar` / `bracketPlan` a PositionState.

---

## 2. Congelaciones de esta auditoría (v1.10)

### 2.1 Persistir Position **antes** de consola

El auditor describe una Consola de Mesa (estado global, posiciones, cola, «no operar»). Es el destino correcto (ADR-032 §5). **Prohibido** construirla sobre holdings planos. SoT post-fill = PositionState persistido (P1). Operaciones puede **enseñar** el snapshot sin ser god page.

### 2.2 No OrderIntent-dios

El auditor propone un `OrderIntent` con entrada + protección + objetivos + grupo OCO + riesgo. **Rechazado** como objeto único.

| Concepto         | Hogar vigente                           | v1.10                                     |
| ---------------- | --------------------------------------- | ----------------------------------------- |
| Fill autorizado  | `OrderIntent` (ADR-029)                 | Conservar. Side/qty/price/source          |
| Tesis / plan     | DecisionPackage / TradePlan             | Snapshot en Position (P1)                 |
| Stop de posición | `PositionState.initialStop/currentStop` | Autoridad post-fill; revisiones auditadas |
| Orden a precio   | `pending_orders.limit_price`            | Honesty H1: **no** se llama stop          |
| T1/T2 / reduce   | TradePlan + ExitPlan                    | Gobiernan vía Position, no vía pending    |
| Bracket / OCO    | Thin `bracketPlan` display-only         | **Parked** hasta Position durable         |

Misma lección que ADR-031: tesis ≠ plan ≠ permiso. Aquí: **intent de fill ≠ stop de posición ≠ pending a precio**.

### 2.3 Lab exits ≠ producto

`EvaluatePositionExits` / `position_policies` opera holdings en `/screeners`. **Sigue Lab.** Cadena de mesa cuando se cablee:

```text
evento → ExitPlan propone → ExitPermission valida
  → SEMI confirma (o paper según política)
  → fill actualiza Position persistida + ledger
  → Journal plan vs resultado
```

Hasta P3: auto-exit **no** es CTA cotidiano (ya es así: RX1, `PAPER_D_EXECUTE` off).

### 2.4 Invariantes **antes** de grabar (H2)

No persistir ni cablear las factories con estos huecos:

| Invariante   | Hoy (factory)                       | Contrato v1.10                                               |
| ------------ | ----------------------------------- | ------------------------------------------------------------ |
| Nacimiento   | `from_fill` acepta WATCH/ARMED      | Exige `TRIGGERED` o override auditado                        |
| Stop         | Cualquier `currentStop` > 0         | No empeorar sin override auditado                            |
| T1 vs T2     | T2 puede disparar T1 → reduce mitad | T2 no interpreta T1 a ciegas                                 |
| Cerrar corto | ExecutionPlan `side: "sell"`        | Cerrar short = `buy`                                         |
| Kill switch  | DENY salida si `killSwitch`         | Bloquea aperturas/automatismos; **permite** desriesgo humano |

---

## 3. Mapa auditor → slice (no se salta)

| Pedido del auditor                         | Slice  | Notas                                    |
| ------------------------------------------ | ------ | ---------------------------------------- |
| Renombrar Stop/Limitada                    | **H1** | Solo etiqueta + HELP. No `stopPrice`.    |
| Factories no gobiernan / invariantes       | **H2** | Código puro + tests. Sin Alembic.        |
| Posición durable + snapshot + fills        | **P1** | Alembic + wire fill SEMI y pending.      |
| Sizing ticket vs riesgo; override          | **P2** | Firma. No % caja como autoridad.         |
| Una cadena de salida                       | **P3** | Lab intacto. Sin auto-exit CTA.          |
| Consola de Mesa / «no operar» / barra      | **P4** | Después. No sustituye las 5 puertas.     |
| Bracket / OCO / grupo de órdenes           | parked | Tras Position durable.                   |
| Ranking canónico versionado                | parked | Estudio cliente sigue ≠ BUY.             |
| Alertas servidoras, import bróker, auto    | parked | El auditor los pone «después». Aceptado. |
| Reconciliación plena (div, comisión, plan) | parked | Ledger ya cubre fees; el resto no es H1. |

---

## 4. Acompañantes parked (siguen)

| Concepto                                 | Decisión                                                                                        |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `ActionIdentity`                         | instrument + positionId + actionType. Dedup Hoy por `symbol` **intacta** hasta que P1 lo exija. |
| ActionabilityScore v1                    | **Prohibido.** Hoy = ordinal.                                                                   |
| Contrato formal OpenAPI / `contract:gen` | Después de shape P1 estable.                                                                    |
| Broker live · OCO · thaw estricto        | Fuera de v1.10 primer arco.                                                                     |

---

## 5. Batería v1.10 (invariantes, no conteo)

Cuando haya runtime, cubrir **estas** familias — no «pasar de 217»:

| Familia          | Ejemplos                                                              |
| ---------------- | --------------------------------------------------------------------- |
| **H** Honesty    | pending ≠ stop · etiqueta UI · HELP                                   |
| **B** Risk       | from_fill TRIGGERED · stop no empeora · qty firma ≤ plan · override   |
| **C** Lifecycle  | fill → Position persistida · mark/reduce/BE · CLOSED                  |
| **D** Exit       | una cadena · Lab no dispara mesa · kill switch asimétrico · short=buy |
| **E** Accounting | transactionId · fees · qty ledger ↔ remaining Position                |

Negativos, transiciones e idempotencia > snapshots felices.

---

## 6. Consistencia de 4 puntos

Conceptos críticos de v1.10 (pending ≠ stop, Position persistida, firma de riesgo, cadena de salida): **CODE + TEST + HELP + ADR**. Ya empezó en C1. Mantener. H1 es el primer slice de honesty de usuario.
