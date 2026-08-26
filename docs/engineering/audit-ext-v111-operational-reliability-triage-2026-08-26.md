# Triage — Auditoría externa Operational Reliability (post v1.11)

> **Padre:** [engineering-index](./engineering-index-2026-08-03.md) §5 · pack interno [`audit-pack-estado-global-2026-08-26-v111.md`](./audit-pack-estado-global-2026-08-26-v111.md).
> **Entrada:** informe externo post-tag **`v1.11-beta` → `76d0f951`** (no el commit documental `8780c732`). Contraste contra ADR-034 OI-1…OE-1 **CERRADOS**.
> **AsOf:** 2026-08-26. **Estado:** **RATIFICADO.** Operational Integrity v1.11 **CERRADA**. **OR-1…OR-6 CERRADOS** (spine 433). Siguiente = pack + tag **`v1.12-beta`** (chat aparte). Auditoría 2 **aparcada** (owner).
> **Hijos:** [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md) · ADR-035 · plan [`plan-or1-e2e-idempotency-2026-08-26.md`](./plan-or1-e2e-idempotency-2026-08-26.md) · plan [`plan-or2-crash-restart-2026-08-26.md`](./plan-or2-crash-restart-2026-08-26.md) · plan [`plan-or3-order-state-machine-2026-08-26.md`](./plan-or3-order-state-machine-2026-08-26.md) · relevo OR-3 [`traspaso-relevo-or3-order-state-machine-2026-08-26.md`](./traspaso-relevo-or3-order-state-machine-2026-08-26.md).

---

## 0. Veredicto producto (ratificado)

El auditor acierta el **cambio de frontera**. v1.10 preguntaba si una operación puede sobrevivir al fill. v1.11 responde **sí** (OI-1…OE-1). La pregunta de v1.12 es:

> ¿Puede la operación sobrevivir a timeout, retry, crash, discrepancia, partial fill o broker desconocido **sin perder el control del estado**?

Nuestra respuesta actual: **casi**. Eso es exactamente donde concentrar la siguiente fase. **No** más indicadores, IA, páginas, rankings, modelos ML ni brokers.

```text
v1.10   operación GOBERNADA     (ADR-033 H1→P4)
v1.11   operación INTEGRADA     ← ahora (ADR-034 OI-1…OE-1)
v1.12   operación VALIDADA      ← esta auditoría
```

| Área                              | Auditor | Arbitraje Bolsa                                                                                |
| --------------------------------- | ------- | ---------------------------------------------------------------------------------------------- |
| Salto arquitectónico v1.11        | 🟢      | **Aceptado.** Operational Integrity Layer existe en código, no solo en docs.                   |
| OI-1 continuidad / `human_manual` | 🟢      | **CERRADO.** Manual y AI terminan en PositionState.                                            |
| OI-2 risk signature SEMI          | 🟢      | **CERRADO.** Distinción `AI_SEMI` vs `HUMAN_MANUAL` debe quedar **cristalina** (docs, no bug). |
| OI-3 UNKNOWN ≠ ERROR              | 🟢      | **CERRADO.**                                                                                   |
| OI-4 PaperOrder CREATED→FILLED    | 🟠      | **CERRADO como v1.11.** Lifecycle corto; ampliar = **OR-3**, no reabrir OI-4.                  |
| OI-5 PositionRevision JSON        | 🟠      | **CERRADO.** Tabla `position_revisions` = deuda deliberada. **No** en v1.12.                   |
| OI-6 / LR-1 detect-report         | 🟠      | **CERRADO como detect.** Falta veto de apertura = **OR-4**.                                    |
| PaperBroker / IBrokerAdapter      | 🟢      | **Aceptado.** Puerto correcto.                                                                 |
| LIVE XTB wired ≠ trading accepted | 🔴      | **Aceptado.** Adapter experimental. **No** capital.                                            |
| Venue selector / UX CTA           | 🟢      | CTA Mesa dice PAPER\|LIVE. UX = **OR-6 CERRADO**.                                              |
| OE-1 % vs readiness states        | 🟢      | 4 estados OR-6 (sin %). OE-1 sigue PASS/FAIL/WARN · measure ≠ Accept.                          |
| AUTO como modalidad               | 🔴      | **Correctamente NO.** Confirm = firma · `PAPER_D_EXECUTE` off.                                 |
| Prioridad = validar, no expandir  | 🟢      | **Aceptado.** Seis objetivos OR-1…OR-6.                                                        |
| CI tag GREEN no verificable aquí  | 🟡      | Precisión aceptada. El repo declara Actions GREEN; el auditor no vio combined status del SHA.  |

---

## 1. Dos políticas de riesgo (formalizar; no es omisión)

El auditor pide que dentro de seis meses nadie lea el HTTP manual como un agujero accidental de `risk_signature`. **Correcto.** Queda contrato de dominio:

| Camino           | Origen snapshot                                  | Gate de riesgo                                                                            | Qué no es                  |
| ---------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------- | -------------------------- |
| **AI_SEMI**      | TradePlan TRIGGERED                              | `RiskSignature` (`require_triggered_plan` → `no_tradeplan` fail-closed)                   | Manual HTTP                |
| **HUMAN_MANUAL** | `origin: HUMAN_MANUAL` · override `human_manual` | **ManualTradeRiskGate** = `check_opening` en buy (I1 Fit+DS-05+DS-03); sell skip apertura | Una firma de IA disfrazada |

`ManualTradeRiskGate` es **nombre de política**, no un motor segundo. El código ya es I1 + OI-1. No se inventa un objeto-dios. ADR-035 lo estampa.

---

## 2. Scorecard P0 / P1 / P2 contrastado con código

### P0 — esta fase (v1.12)

| #   | Claim del auditor                                                                       | Veredicto                 | Evidencia                                                                                                                                                                                                                                                                                                            |
| --- | --------------------------------------------------------------------------------------- | ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | End-to-end idempotency (timeout + retry Confirm → 1 order / 1 fill / 1 position)        | **PARTIAL**               | Ledger UNIQUE `decision_id` en `ExecuteTrade` + `test_confirm_double_execute_concurrent_single_logical_fill`. Confirm **siempre** reentra `adapter.submit`. `intent_id` = `INT-{uuid4}` por llamada. Fallback `confirm-{uuid4}` si falta `decision_id`. PaperOrder `ORD-…` nuevo. ExecutionRecord efímero. **OR-1.** |
| 2   | Crash/restart recovery (submit → crash → reconstruye UNKNOWN)                           | **CERRADO (OR-2)**        | `DurableSubmitIntent` pre-submit + recovery sin re-POST. Store InMemory de proceso. Tabla PG / Redis multi-worker parked.                                                                                                                                                                                            |
| 3   | Reconciliation → global opening veto (`DRIFT` → no new entries; protective exits ALLOW) | **CERRADO (OR-4)**        | `check_opening` + Confirm/Fill/HTTP/Router. OI-6 drift DENY; LR-1 drift/unavailable DENY venue live. Exits ALLOW. Sin auto-heal.                                                                                                                                                                                     |
| 4   | Live execution real end-to-end                                                          | **CONFIRMED** no-aceptado | XL-1 `submitted ≠ fill`. LIVE **EXPERIMENTAL**. **No** entra en v1.12 como “closed”. Escenarios paper/mock en **OR-5**.                                                                                                                                                                                              |

### P1 — después de OR-1 o parked dentro de v1.12

| #   | Claim                                                                                           | Veredicto                                             | Dónde                                                                       |
| --- | ----------------------------------------------------------------------------------------------- | ----------------------------------------------------- | --------------------------------------------------------------------------- |
| 5   | Order lifecycle completo (SUBMITTED → ACK → PARTIAL → FILLED + REJECTED/CANCEL/EXPIRED/UNKNOWN) | **CERRADO (OR-3)**                                    | Grafo + PaperBroker + crash recovery. No reabrir OI-4.                      |
| 6   | Position revisions como tabla append-only                                                       | **PARKED**                                            | Auditor: «no lo tocaría ahora». JSONB `PositionState.revisions` válido.     |
| 7   | ExecutionRecord persistente como entidad fuerte                                                 | **PARKED OR-1; OR-2 si hace falta identidad durable** | Hoy DTO. OR-1 cierra retry paper **sin** Alembic.                           |
| 8   | Broker order ID ↔ internal order ID                                                             | **CERRADO en OR-2**                                   | `venueOrderId` durable en `DurableSubmitIntent`. Recovery adjunta el mapeo. |

### P2 — no ahora

| #   | Claim                                                     | Veredicto          | Dónde                                                                                                                                     |
| --- | --------------------------------------------------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| 9   | JSONB PositionState → hot columns como SoT                | **PARKED**         | JP-1 dual-write; JSONB SoT. Dual-write → backfill → métricas **antes** de cambiar SoT.                                                    |
| 10  | UI cuenta/venue unificada + CTA `EJECUTAR EN PAPER\|LIVE` | **CERRADO (OR-6)** | CTA `Ejecutar en PAPER                                                                                                                    | LIVE`. Preferencia cuenta en settings. |
| 11  | AUTO gobernado por policy engine                          | **PARKED**         | AUTO ≠ IA→BUY. Cadena Opportunity→TradePlan→Risk→Permission→Execution policy→Order. Confirm sigue siendo la firma. `PAPER_D_EXECUTE` off. |

---

## 3. Cerrado de verdad (v1.11 — no reabrir)

Aceptado. No se reabre OI-1…OE-1 para «añadir campos del auditor» a ciegas.

| Slice              | Qué es                                                                            | Qué no es                                        |
| ------------------ | --------------------------------------------------------------------------------- | ------------------------------------------------ |
| OI-1…OI-6          | Continuidad, firma SEMI, UNKNOWN, PaperOrder corto, revisiones JSON, recon detect | Idempotencia de intento · veto recon · OMS pleno |
| PB-1 / BA-1        | PaperBroker + puerto Paper\|Live                                                  | Broker producción                                |
| PH-1               | Protect persist honesto; cero ledger                                              | Orden de broker                                  |
| XL-1 / XL-2 / LR-1 | Adapter XTB + fill opt-in + live recon detect                                     | LIVE accepted                                    |
| VS-1 / RV-1 / PA-1 | Venue coalesce                                                                    | CTA unificado en todas las pantallas             |
| JP-1               | Dual-write columnas                                                               | Cambio de SoT                                    |
| OE-1               | Scorecard PASS/FAIL/WARN                                                          | Ready for live · 4 estados OR-6                  |
| Thaw stamp         | DEMO opt-in autorizado                                                            | Default-on · thaw estricto                       |

Thin 5.x/8.x **congelados**. I1–I3 + RX1 **intactos**. Confirm = **única** firma. `PAPER_D_EXECUTE` **off**. BETA / no producción.

---

## 4. Lo que el auditor pide para v1.12 (adoptado)

Seis objetivos. **Ninguno** es un indicador nuevo.

| Slice    | Nombre                          | Cierra                                                                          |
| -------- | ------------------------------- | ------------------------------------------------------------------------------- |
| **OR-1** | End-to-end idempotency          | Retry Confirm paper → 1 fill / 1 posición / misma identidad de intento          |
| **OR-2** | Crash/restart recovery          | Submit intent durable; UNKNOWN reconstruible                                    |
| **OR-3** | Full order state machine        | Ampliar CREATED→FILLED (paper/adapter), no broker real                          |
| **OR-4** | Reconciliation → opening veto   | `drift` / live `unavailable` → DENY aperturas; exits protectivos ALLOW; no heal |
| **OR-5** | Broker execution scenario suite | Escenarios A–L + retry + crash anclados a spine                                 |
| **OR-6** | SEMI operational certification  | Readiness 4 estados (un FAIL crítico no se promedia) + venue en CTA             |

Escenarios A–L del auditor (entrada normal, manual, SELL parcial/total, timeout paper, persist fail post-fill, protect OK/fail, T1, T2 no-replay, recon drift, broker unavailable) se **certifican en OR-5**; OR-1 cierra el de **reintento**. Simulación 1.000–10.000 sesiones = **post-v1.12**.

---

## 5. Decisiones adoptadas (docs en este stamp; código OR-1 en chat siguiente)

| #   | Decisión                                                                                           | Cuándo         |
| --- | -------------------------------------------------------------------------------------------------- | -------------- |
| 1   | **No** más arquitectura general. Validar el sistema.                                               | Ya             |
| 2   | **No** más brokers. Paper + XTB adapter + live recon + venue = suficiente.                         | Ya             |
| 3   | LIVE = **EXPERIMENTAL**. No capital. `submitted ≠ fill` se conserva.                               | Ya             |
| 4   | AUTO **no** se activa. Definición futura = policy chain, no IA→BUY.                                | Ya             |
| 5   | `PAPER_D_EXECUTE` default **OFF**. Thaw estricto = deuda aparte.                                   | Ya             |
| 6   | Dos gates de riesgo: `AI_SEMI` / `HUMAN_MANUAL`. Documentar, no fusionar.                          | Este stamp     |
| 7   | Tabla `position_revisions` y SoT columnas = **parked**.                                            | v1.12          |
| 8   | Primer código = **OR-1** (paper retry). Sin Alembic. Sin OR-3 machine.                             | Chat siguiente |
| 9   | UX venue CTA = **OR-6**, no OR-1.                                                                  | Después        |
| 10  | Tag `v1.11-beta` **no** se reabre. `v1.12-beta` es fase nueva (≠ notas históricas CORE-R «v1.12»). | Disciplina     |
| 11  | Pack auditor v112 = al **tag**, no ahora.                                                          | Cierre de fase |
| 12  | Auditoría 2 aparcada hasta que el owner la entregue.                                               | Owner          |

---

## 6. Qué reutilizar / no inventar

**Reutilizar:** Confirm SEMI, `decision_id` como `idempotency_key` de `ExecuteTrade`, `find_transaction_by_idempotency`, `PersistPositionFromFill` (open por `open_transaction_id`), ExecutionRecord outcomes, PaperOrder, IBrokerAdapter, `check_opening`, OI-6/LR-1 informes, OE-1 lanes.

**No construir ahora:** segundo motor de riesgo, OrderIntent-dios, auto-heal de recon, tabla `execution_records` en OR-1, OMS broker, AUTO on, más adapters, thin nuevos, Consola plena, simulación masiva.

**No fusionar** Lab `position_policies` con ExitPlan (freeze v1.10+).

---

## 7. Qué no hacer

- No indicadores / IA / páginas / rankings / ML en v1.12.
- No conectar IBKR u otro broker.
- No declarar LIVE trading accepted.
- No default-on `PAPER_D_EXECUTE`.
- No Accept estricto sin DoD thaw + palabra **thaw**.
- No auto-heal en reconciliación.
- No promediar un FAIL crítico de recon en un «92 % listo».
- No reabrir OI-1…OE-1 ni F1–F4 a ciegas.
- No Alembic en OR-1.
- No `contract:gen` en OR-1.
