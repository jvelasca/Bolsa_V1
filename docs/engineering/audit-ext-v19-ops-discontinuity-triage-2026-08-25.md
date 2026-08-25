# Triage — Auditoría externa de discontinuidad operativa (post v1.9)

> **Padre:** [engineering-index](./engineering-index-2026-08-03.md) §5 · pack interno [`audit-pack-estado-global-2026-08-25-v19.md`](./audit-pack-estado-global-2026-08-25-v19.md).
> **Entrada:** informe externo sobre el hueco **decisión → posición viva** (no sobre tag v1.8.1). Contraste contra **`v1.9-beta` → `7d90d965`** (F1–F4 + ExitPermission + INFRA).
> **AsOf:** 2026-08-25. **Estado:** **RATIFICADO.** Operational Core v1.9 **CERRADO como modelo**. **No** Consola de Mesa. **No** Alembic. Siguiente = diseño Operational Authority v1.10 (ADR-033), no código.
> **Hijos:** [`adr-032-ops-authority-gap-2026-08-25.md`](./adr-032-ops-authority-gap-2026-08-25.md) · [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md) · ADR-033 · relevo [`traspaso-relevo-audit-ext-v19-ops-discontinuity-2026-08-25.md`](./traspaso-relevo-audit-ext-v19-ops-discontinuity-2026-08-25.md).

---

## 0. Veredicto producto (ratificado)

El auditor acierta el **problema de producto**. El núcleo de investigación, veto pretrade y paper está por delante de mucha app retail. La operativa diaria **se rompe al pasar de idea aprobada a posición que debe sobrevivir**.

Lo que **no** acierta del todo: habla de PositionState / ExitPlan / ExitPermission / ExecutionPlan como si fueran un diseño futuro. Ya existen (F1–F4 + ExitPermission, spine **217**). Son **factories + tests**, no autoridad persistente. Eso es el siguiente salto, no un rediseño desde cero.

```text
v1.8.1  consolidación honesty (C1–C6)
v1.9    operación MODELADA   ← ahora (ADR-032 cerrado)
v1.10   operación GOBERNADA  ← esta auditoría
```

| Área                         | Auditor | Arbitraje Bolsa                                                                                           |
| ---------------------------- | ------- | --------------------------------------------------------------------------------------------------------- |
| Diagnóstico (discontinuidad) | 🟢      | **Aceptado.** El hueco es fill → holding plano, no falta de tesis.                                        |
| Factories F1–F4              | 🟡      | Existen; el auditor las nombra como lógica pura. **Correcto como autoridad; incompleto como existencia.** |
| Stop/Limitada UI             | 🔴      | **CONFIRMED.** Etiqueta miente. Honesty H1.                                                               |
| Plan no sobrevive al fill    | 🔴      | **CONFIRMED.** Persistencia P1.                                                                           |
| Sizing ticket ≠ riesgo plan  | 🔴      | **CONFIRMED.** Firma P2.                                                                                  |
| Dos motores de salida        | 🟠      | **PARTIAL.** Lab sí; cognitiva unwired. No competirlas en runtime. P3.                                    |
| Invariantes factories        | 🔴      | **CONFIRMED** en código puro (aún no en producto). H2 **antes** de wire.                                  |
| Consola de Mesa              | 🟡      | Destino UX correcto. **Parked hasta P1–P3.** Ya parked en ADR-032 §5.                                     |
| OrderIntent-dios             | 🔴      | **RECHAZADO** como objeto único. ADR-029 ya tiene fill autorizado.                                        |
| Ranking canónico             | 🟡      | Ya parked. «Construir después».                                                                           |
| Auto-exit CTA cotidiano      | 🟢      | Ya **no** lo es (Señales / RX1 / `PAPER_D_EXECUTE` off). Conservar.                                       |
| Broker / producción          | 🔴      | **Correctamente NO.**                                                                                     |

---

## 1. Scorecard contrastado con código

| Claim del auditor                                                       | Veredicto                       | Evidencia                                                                                                                                                                                                                                 |
| ----------------------------------------------------------------------- | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UI «Stop/Limitada» solo persiste `limitPrice`                           | **CONFIRMED**                   | `apps/web/src/features/trading/order-dialog.tsx` tab `"Orden Stop/Limitada"`. Modelo `PendingOrderRow`: `limit_price` + `expiry_at`. No `stopPrice`, trigger, OCO, grupo, `positionId`. `limitPrice` hace de trigger **y** de fill.       |
| El plan no sobrevive al fill                                            | **CONFIRMED**                   | Fill → `ExecuteTrade` + holding `qty/avg_cost`. Operaciones = qty / last / P&L. `buildPositionStateFromFill` **no** se llama desde `apps/`.                                                                                               |
| Ticket F3 sizea por % caja; TradePlan por riesgo €                      | **CONFIRMED**                   | `suggestQuantityFromCash` vs `compute_risk_size`. Ticket editable; stop no entra. `CURRENT_SYSTEM`: _«suggestedQuantity del ticket F3 no se pisa con TradePlan.quantity»_.                                                                |
| PositionState / ExitPlan no gobiernan                                   | **CONFIRMED**                   | Factories en shared + analytics. Sin Alembic, sin Confirm, sin fill path.                                                                                                                                                                 |
| Dos motores de salida incompatibles                                     | **PARTIAL**                     | Lab `position_exit_evaluator` opera holdings (Señales, no CTA de mesa). Cadena cognitiva existe y **no** está cableada. Hoy no compiten en runtime; **sí** competirían si se cablean las dos. Thin `exitRadar` es un **tercer** advisory. |
| `from_fill` desde WATCH/ARMED                                           | **CONFIRMED** (factory)         | `buildPositionStateFromFill` exige dirección + fill; **no** `status === "TRIGGERED"`.                                                                                                                                                     |
| Stop empeorable sin override                                            | **CONFIRMED** (factory)         | `applyCurrentStop` / `apply_position_current_stop` acepta cualquier stop > 0.                                                                                                                                                             |
| Tocar T2 interpreta T1 y puede reducir mitad                            | **CONFIRMED** (factory)         | ExitPlan: T1 y T2 pueden disparar; precedencia T1 > T2; T1 → `reduce` + `remaining/2`.                                                                                                                                                    |
| ExecutionPlan usa `sell` también para cerrar cortos                     | **CONFIRMED** (factory)         | `resolveActionable` hardcodea `side: "sell"` en long **y** short.                                                                                                                                                                         |
| Kill switch bloquea salida protectora                                   | **CONFIRMED** (diseño factory)  | `checkExitPermission`: `killSwitch` → DENY antes de actionability. `POST /portfolio/trade` **sells skip** opening gate — el producto aún puede desriesgar; el gate de salida, si se cablea tal cual, no.                                  |
| Ranking cliente sin snapshot canónico                                   | **CONFIRMED** (ya parked)       | Estudio `rankIndiceOperativo` cliente; IO fórmula server. ≠ permiso.                                                                                                                                                                      |
| Mesa abre por candidatos, no por posiciones                             | **CONFIRMED** (hueco UX)        | `HoyCommandStrip` primero (cola de **entrada**). Holdings abajo en Operaciones. Daily Operating Console **ya parked**.                                                                                                                    |
| Crear un OrderIntent rico (entrada+stop+T1/T2+OCO+riesgo)               | **RECHAZAR** como objeto único  | Ya existe `OrderIntent` = voluntad **autorizada de fill** (ADR-029). El auditor mezcla 5 conceptos. Misma lección que tesis ≠ plan ≠ permiso.                                                                                             |
| Reutilizar DecisionPackage, TradePlan, `check_opening`, ledger, Journal | **ACEPTADO**                    | No se tira el spine.                                                                                                                                                                                                                      |
| Degradar etiqueta Stop/Limitada, lote como CTA, `full_auto` como normal | **ACEPTADO** (honesty / freeze) | H1 + freeze AUTO. `full_auto` ya no es experiencia normal (`PAPER_D_EXECUTE` off).                                                                                                                                                        |

Nombres a no confundir:

| Nombre            | Qué es en Bolsa                                       | Qué cree el auditor a veces     |
| ----------------- | ----------------------------------------------------- | ------------------------------- |
| **Ticket F3**     | Confirm SEMI (`SupervisedF3Panel` / OrderIntent fill) | «F3»                            |
| **ExitPlan F3**   | Slice v1.9 del plan de salida (ADR-032)               | no lo nombra así                |
| **Pending**       | Orden a precio (`limitPrice`)                         | «stop»                          |
| **Holding**       | Fila ledger `qty/avg_cost`                            | posición operativa              |
| **PositionState** | Factory cognitiva post-fill                           | posición durable (aún no lo es) |

---

## 2. Cerrado de verdad (v1.9 — no reabrir)

Aceptado. El modelo post-entrada **existe**. No se reabre F1–F4 para «añadir campos del auditor» a ciegas.

| Slice            | Qué modela                                     | Qué **no** es             |
| ---------------- | ---------------------------------------------- | ------------------------- |
| **F1** TradePlan | Tesis → plan (stop, T1/T2, riesgo €, qty, R/R) | Permiso · fill · posición |
| **F2+F2.1**      | PositionState from_fill + mark/reduce/BE       | Persistencia · wire fill  |
| **F3** ExitPlan  | Razones canónicas · suggestedAction advisory   | Auto-exit · mutar stop    |
| **F4** PAPER     | Journal → Replay → Validation                  | Broker · ExecuteTrade     |
| **EP**           | `checkExitPermission` ALLOW/DENY               | `check_opening` · wire    |
| **INFRA**        | CI-by-tag                                      | —                         |

Thin 5.x/8.x **congelados**. I1–I3 + RX1 **intactos**. `PAPER_D_EXECUTE` **off**.

---

## 3. No cerrado (correcto; no es bug de v1.9)

1. PositionState persistido y gobernando el fill.
2. Stop real / vínculo orden↔posición.
3. Ticket F3 firmando el riesgo del TradePlan.
4. Una sola cadena de salida de **producto** (Lab `position_policies` no es esa cadena).
5. Invariantes H2 (WATCH/ARMED, stop empeorado, T2→T1, sell-en-corto, kill switch asimétrico).
6. Consola de Mesa (posiciones antes que candidatos; «no operar» como veredicto).
7. Ranking canónico versionado.
8. Reconciliación operativa completa (orden, fill, posición, caja, comisión, dividendo, desviación vs plan).
9. Broker live · OCO · thaw estricto.

Nada de esto se «arregla» cableando las factories tal cual, ni con una god page.

---

## 4. Decisiones adoptadas (no código en este triage)

| #   | Decisión                                                                                                      | Cuándo        |
| --- | ------------------------------------------------------------------------------------------------------------- | ------------- |
| 1   | **No** Consola de Mesa en el primer slice. Persistencia y honesty **antes** de UX de mesa.                    | Ya            |
| 2   | **No** OrderIntent-dios. `OrderIntent` sigue = fill autorizado (ADR-029). Protección vive en PositionState.   | Ya            |
| 3   | Pending actual = **orden a precio**. No se presenta como stop de posición (H1).                               | Primer código |
| 4   | Invariantes de factories **antes** de persistir / wire (H2). No grabar bugs.                                  | Tras H1       |
| 5   | Position persistida = SoT post-fill (P1). Holding ledger no desaparece; deja de ser la única cara.            | Tras H2       |
| 6   | Al firmar, el ticket muestra y bloquea riesgo del plan; override con motivo + revalidación (P2).              | Tras P1       |
| 7   | Una cadena de salida de producto: ExitPlan → ExitPermission → SEMI/paper. Lab `EvaluatePositionExits` = Lab.  | P3            |
| 8   | Auto-exit **no** es CTA cotidiano. Conservar RX1 / env gate.                                                  | Ya            |
| 9   | Kill switch: bloquea aperturas y automatismos; **permite** desriesgo humano urgente.                          | H2            |
| 10  | Daily Operating Console / Portfolio Operating Layer = P4, no H1.                                              | Parked        |
| 11  | Ranking canónico, alertas servidoras, simulación impacto, import bróker, auto paper por etapas = **después**. | Parked        |
| 12  | Tag `v1.9-beta` **no** se reabre. v1.10 es fase nueva. Tests = invariantes, no conteo.                        | Disciplina    |

---

## 5. Qué reutilizar / retirar / no inventar

**Reutilizar:** DecisionPackage, TradePlan, `check_opening`, mandato, frescura, ledger, ticket F3, Journal, replay, PositionState/ExitPlan/ExitPermission/ExecutionPlan **como factories**.

**Retirar / degradar (honesty, no borrar camino):** etiqueta «Stop/Limitada»; presentar ejecución manual sin plan como camino **estándar**; «ejecutar lote» como CTA principal; `full_auto` como experiencia normal.

**No construir ahora (el auditor los pone juntos; nosotros los secuenciamos):** Consola de Mesa, bracket/OCO, ranking versionado, alertas servidoras, import bróker, auto paper por etapas.

**No fusionar** Lab `position_policies` con ExitPlan.

---

## 6. Qué no hacer

- No god page / Consola de Mesa en este stamp ni en H1–H2.
- No segundo OrderIntent que mezcle entrada + stop + T1/T2 + OCO + riesgo.
- No persistir PositionState **antes** de H2 (invariantes).
- No cablear `EvaluatePositionExits` como CTA de mesa.
- No promocionar thin 5.x/8.x a SoT.
- No ExecutionPlan → broker.
- No ActionabilityScore predictivo.
- No thaw estricto / producción.
- No optimizar el modelo con DEMO.
- No inflar la batería por conteo.
- No reabrir F1–F4 para campos «del auditor» a ciegas.
