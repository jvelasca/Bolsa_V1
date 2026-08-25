# ADR-033: Operational Authority — Position persistida / una cadena / pending ≠ stop (contrato v1.10)

**Estado:** Accepted — **H1+H2+P1+P2+P3 CERRADOS**; P4 no implementado  
**Fecha:** 2026-08-25  
**Contexto:** Auditoría externa de discontinuidad operativa post-`v1.9-beta`. F1–F4 + ExitPermission **existen como factories**. El producto sigue rompiéndose al fill: holding plano, etiqueta «stop» sin stop, ticket que no firma el riesgo del plan.

**Depende de:** [ADR-031](./031-operational-model-tesis-plan-permiso.md) · [ADR-032](./032-operational-core-tradeplan-positionstate-execution.md) · [ADR-029](./029-order-proposal-decision-journal.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · triage [`audit-ext-v19-ops-discontinuity-triage-2026-08-25.md`](../engineering/audit-ext-v19-ops-discontinuity-triage-2026-08-25.md) · gap [`adr-032-ops-authority-gap-2026-08-25.md`](../engineering/adr-032-ops-authority-gap-2026-08-25.md).

---

## 1. Decisión

Un spine, dos tiempos (ADR-032) **y** una autoridad post-fill. **No** se crea un segundo motor. **No** se implementa en este ADR.

```text
Antes de entrar:  DecisionPackage → TradePlan → check_opening → OrderIntent (fill)
Después:          Position persistida → ExitPlan → ExitPermission → Execution
                  (holding ledger sigue siendo contabilidad, no el plan)
```

| Tiempo      | Objeto                  | Pregunta                                      | Hoy (v1.9)                                     |
| ----------- | ----------------------- | --------------------------------------------- | ---------------------------------------------- |
| **Antes**   | `DecisionPackage`       | ¿Qué creemos?                                 | Runtime / tesis (ADR-031)                      |
| **Antes**   | `TradePlan`             | ¿Qué haríamos **si** entramos?                | v1 **viva** (factory en propose/confirm)       |
| **Antes**   | `check_opening`         | ¿Podemos llenar ahora?                        | Único veto de apertura                         |
| **Antes**   | `OrderIntent`           | ¿Qué fill autorizó el humano/policy?          | Side/qty/price — **no** es stop ni bracket     |
| **Después** | **Position persistida** | ¿Qué ocurre **tras** el fill, mañana también? | Factory only; holding = qty/avg_cost           |
| **Después** | `ExitPlan`              | Si ocurre Y, ¿cómo salimos / protegemos?      | Factory; ≠ Lab `EvaluatePositionExits`         |
| **Después** | `ExitPermission`        | ¿Podemos salir / mutar stop ahora?            | Factory; kill switch **asimétrico** (H2)       |
| **Envío**   | `ExecutionPlan`         | ¿Cómo se envía al paper?                      | PAPER only; broker blocked                     |
| **Pending** | orden a precio          | ¿Hay un límite esperando?                     | UI dice «Stop/Limitada»; modelo = `limitPrice` |

Este documento **acepta el contrato de autoridad**. No genera tipos nuevos, tablas ni mappers.

---

## 2. Position persistida es el SoT post-fill

Tras un fill (SEMI confirm **o** pending), el producto debe poder responder:

- ¿qué plan aprobamos?
- ¿cuál es el stop vigente?
- ¿se modificó?
- ¿qué objetivo ya se cumplió?
- ¿qué debo hacer ahora?

El holding ledger (`quantity`, `avg_cost`, mark, P&L) **no desaparece**. Deja de ser la única cara. El agregado durable reutiliza PositionState v1.9 (no un objeto hermano):

```text
Position
 ├─ trade_plan_snapshot
 ├─ fills / comisiones / transactionId
 ├─ stop inicial y revisiones auditadas
 ├─ T1/T2 y reducciones (cuando P1+ las gobierne)
 ├─ tesis / mandato / datos as-of (snapshot)
 └─ estado: OPEN | PARTIAL | PROTECTED | CLOSED
     (+ discrepancia cuando exista reconciliación)
```

**Prohibido** construir la Consola de Mesa sobre holdings planos. Operaciones puede enseñar el snapshot en P1 sin ser god page.

Factory `from_fill` **no** se llama desde `apps/` hoy. P1 es el wire. H2 es el guard (TRIGGERED) **antes** de grabar.

---

## 3. Un fill, un pending, un stop — tres cosas

| Cosa                 | Qué es                                    | Qué no es                        |
| -------------------- | ----------------------------------------- | -------------------------------- |
| `OrderIntent`        | Voluntad autorizada de **fill** (ADR-029) | Stop, T1/T2, OCO, pérdida máxima |
| Pending `limitPrice` | Orden **a precio** (opcional `expiryAt`)  | Stop de posición · trigger · OCO |
| `currentStop`        | Protección de la **posición**             | Campo del diálogo de pending     |

**H1 (honesty — CERRADO 2026-08-25):** la UI no etiqueta «Stop/Limitada» ni «precio límite / stop» mientras el modelo solo persista `limitPrice`. Copy: orden pendiente a precio. Plan: [`plan-h1-honesty-pending-2026-08-25.md`](../engineering/plan-h1-honesty-pending-2026-08-25.md).

**Rechazado:** un OrderIntent-dios (entrada + protección + objetivos + grupo + riesgo). Misma lección que tesis ≠ plan ≠ permiso.

Bracket / OCO / `stopPrice` de orden = **parked** hasta que Position sea durable. Thin `bracketPlan` sigue display-only.

---

## 4. Una cadena de salida de producto

Lab `position_policies` / `EvaluatePositionExits` opera holdings históricos en `/screeners`. **Sigue Lab.** No es CTA de mesa. RX1 y `PAPER_D_EXECUTE` off se conservan.

Autoridad de mesa (P3):

```text
evento de mercado/dato
  → ExitPlan propone mantener | proteger | reducir | salir
  → ExitPermission valida riesgo y contexto
  → usuario confirma en SEMI  (o paper según política explícita)
  → fill actualiza Position persistida + ledger
  → Journal registra plan versus resultado
```

Thin `exitRadar` / «Salida» Hoy **≠** ExitPlan. **Prohibido** cablear los dos motores contra el mismo símbolo como producto.

Hasta P3, auto-exit **no** es un CTA cotidiano. **P3 CERRADO 2026-08-25:** Confirm `exit_hint`/`reduce` = puerto de producto (ExitPlan `manual` → ExitPermission → SEMI). Lab `EvaluatePositionExits` intacto. Operaciones muestra `suggestedAction` advisory. Persist reduce. Plan: [`plan-p3-cadena-salida-2026-08-25.md`](../engineering/plan-p3-cadena-salida-2026-08-25.md).

---

## 5. Invariantes (H2 — antes de persistir)

| #   | Invariante  | Contrato                                                                                                                                               |
| --- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Nacimiento  | `buildPositionStateFromFill` exige `TradePlan.status == TRIGGERED`, o override auditado. WATCH/ARMED no nacen posición.                                |
| 2   | Stop        | `applyCurrentStop` no empeora el stop sin override auditado.                                                                                           |
| 3   | Targets     | Tocar T2 no interpreta T1 a ciegas ni reduce media posición por el atajo T1.                                                                           |
| 4   | Dirección   | Cerrar / reducir un short no usa `side: "sell"` por defecto. Cerrar short = `buy`.                                                                     |
| 5   | Kill switch | Bloquea **aperturas** y **automatismos**. Permite desriesgo **humano** urgente (SEMI sell/protect). No DENY ciego de ExitPermission protectora humana. |

No grabar estas factories en Alembic **antes** de H2.

---

## 6. Firma de riesgo (P2)

TradePlan sizea por `riesgo_monetario / distancia_al_stop`. El ticket F3 sizea por % de caja y permite editar qty/precio **sin** stop. Eso **no** es autoridad.

Al firmar (P2): mostrar y bloquear tamaño sugerido y máximo; pérdida máxima en € y en R; stop técnico; coste total y efectivo posterior; exposición relevante; motivo obligatorio para override, con revalidación.

`check_opening` sigue siendo el veto de **apertura**. No se fusiona con sizing. El ticket no pisa `TradePlan.quantity` a ciegas **ni** usa % caja como SoT una vez P2 esté vivo.

---

## 7. Consola de Mesa (P4 — destino UX, no primer slice)

Claridad 10s, **no** god page, **no** sexta puerta. Confirmar sigue siendo la firma.

Orden de superficie:

1. Estado operativo global (mercado, caja, veto, excepciones).
2. **Posiciones** antes que candidatos (tesis, R, stop, T1/T2, CTA Mantener/Proteger/Reducir/Salir/Revisar).
3. Cola de entradas: Vigilar / Preparado / Propuesto / Bloqueado / Descartado.
4. «No operar» como veredicto de sesión → Journal (elevación de ADR-032 §7 / ADR-031).

Si hay veto global, la cola de **nuevas entradas** queda bloqueada y explica por qué. El desriesgo humano no se bloquea por ese veto (coherente con §5.5).

---

## 8. NO TRADE sigue de primera clase

**0 BUY + N WATCH / BLOCKED / ARMED puede ser un día excelente.** Cerrar una sesión sin operación alimenta el Journal como decisión correcta (P4), no como ausencia de actividad.

---

## 9. Tickets parked (no este ADR)

| Ticket                               | Qué                              | Qué no                |
| ------------------------------------ | -------------------------------- | --------------------- |
| Bracket / OCO / `stopPrice`          | Tras Position durable            | H1 etiqueta           |
| Ranking canónico versionado          | Snapshot fórmula + datos + as-of | Permiso / BUY         |
| Alertas servidoras                   | Después                          | CTA auto-exit         |
| Import bróker / reconciliación plena | Después                          | P1 mínimo (fill+plan) |
| Automatización paper por etapas      | Después de P3                    | `full_auto` cotidiano |
| ActionabilityScore v1                | **Prohibido**                    | Ordinal de status     |
| Broker live / thaw estricto          | Fuera                            | Este ADR              |

---

## 10. Freeze vigente (este ADR)

LAB ≠ TRADING · LLM **no** ejecuta · Ranking ≠ BUY · SETUP Wyckoff **cerrada** · 5.x + 8.0–8.2 thin **congelados** · I1–I3 + RX1 intactos · `PAPER_D_EXECUTE` **off** · **no** broker · **no** `contract:gen` · **no** mappers thin nuevos · **no** Consola de Mesa en D0/H1 · **no** OrderIntent-dios · **no** Alembic en este slice (D0).

F1–F4 de ADR-032 **no** se reabren para campos extra. H2 solo invariantes.

---

## 11. Consecuencias

- Un ADR más no compite con `CURRENT_SYSTEM`: este documento fija **contrato v1.10**; el estado vivo sigue en [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md). ADR-031 = tres capas de apertura. ADR-032 = objetos post-entrada. ADR-033 = **autoridad** de esos objetos.
- Implementar H1–P4 exige **fase propia** (plan D1–D8) que cite este ADR. Hasta entonces: cero runtime. Secuencia: H1 honesty → H2 invariantes → P1 Position → P2 firma → P3 salida → P4 consola. [`roadmap-v110-operational-authority-2026-08-25.md`](../engineering/roadmap-v110-operational-authority-2026-08-25.md).
- El siguiente chat no construye la consola **en el mismo chat que P3**. **P3 cadena de salida CERRADO**. Siguiente = **P4** Consola de Mesa (o operar SEMI).
- Conceptos críticos (pending ≠ stop, Position persistida, firma de riesgo, cadena de salida): consistencia **CODE + TEST + HELP + ADR**.
