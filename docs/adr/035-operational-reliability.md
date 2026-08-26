# ADR-035: Operational Reliability — validar el sistema (contrato v1.12)

**Estado:** Accepted — **D0 docs CERRADO.** **OR-1/3/4/5/6 CERRADOS** (código). **OR-2 cerrado vía DEX-1+DEX-2** (PG + cert cross-PID). Fase v1.12 **cerrada en pack + tag** (`v1.12-beta` → `369b5d1`). Post-audit: V1.13 Durable Execution (**DEX-1…DEX-5 CERRADOS**; pack v113; tag **`v1.13-beta` → `c8d5800`**).  
**Fecha:** 2026-08-26  
**Contexto:** Auditoría externa post-`v1.11-beta` (`76d0f951`). Operational Integrity (ADR-034) **cerrada**. El modelo sobrevive al fill; falta demostrar que sobrevive a timeout, retry, crash, drift y estado de broker desconocido. Auditoría post-`v1.12-beta` (`369b5d1`): concepto DurableSubmitIntent OK; durabilidad física = DEX-1; cert cross-PID = DEX-2.

**Depende de:** [ADR-034](./034-operational-integrity-continuity.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · triage [`audit-ext-v111-operational-reliability-triage-2026-08-26.md`](../engineering/audit-ext-v111-operational-reliability-triage-2026-08-26.md) · roadmap [`roadmap-v112-operational-reliability-2026-08-26.md`](../engineering/roadmap-v112-operational-reliability-2026-08-26.md) · triage post-v1.12 [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](../engineering/audit-ext-v112-durable-execution-triage-2026-08-26.md) · roadmap [`roadmap-v113-durable-execution-2026-08-26.md`](../engineering/roadmap-v113-durable-execution-2026-08-26.md).

---

## 1. Decisión

**Validar, no expandir.** v1.12 no añade indicadores, IA, páginas, rankings, modelos ML ni brokers. Convierte el Operational Integrity Layer en un sistema **operacionalmente determinista** bajo fallos.

```text
v1.11  MODELO  🟢 fuerte
v1.12  REALIDAD  🟠 validar  ← esta fase
```

Este documento **acepta el contrato de fiabilidad**. OR-1…OR-6 son los únicos objetivos. El código empieza en OR-1 (chat siguiente), no en este ADR.

Nombre de tag: **`v1.12-beta`**. No confundir con notas históricas CORE-R que decían «v1.12».

---

## 2. Dos gates de riesgo (no es omisión)

El camino HTTP manual **no** pasa por `risk_signature`. Eso es política, no un bug.

| Camino           | Origen                 | Gate                                                                 |
| ---------------- | ---------------------- | -------------------------------------------------------------------- |
| **AI_SEMI**      | TradePlan `TRIGGERED`  | `RiskSignature` (`require_triggered_plan` → `no_tradeplan`)          |
| **HUMAN_MANUAL** | `origin: HUMAN_MANUAL` | **ManualTradeRiskGate** = `check_opening` en buy; sell skip apertura |

Ambos terminan en `PositionState` (OI-1). `ManualTradeRiskGate` nombra la política I1 existente. **No** un segundo motor. **No** forzar TradePlan de IA a la operativa manual.

---

## 3. Seis objetivos (OR-1…OR-6)

| ID   | Contrato                                                                                            | Fuera de este ID                                           |
| ---- | --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| OR-1 | Retry Confirm paper = 1 fill / 1 posición / misma identidad · **CERRADO**                           | Alembic · live e2e                                         |
| OR-2 | Crash tras submit → `UNKNOWN` reconstruible; mapeo intent ↔ venue order · **CERRADO** (DEX-1+DEX-2) | Heal · Redis multi-worker                                  |
| OR-3 | State machine de orden más allá de `CREATED`/`FILLED` · **CERRADO**                                 | Broker producción · OCO                                    |
| OR-4 | Recon `drift` / live `unavailable` = veto **global de apertura** · **CERRADO**                      | Auto-heal · UI Mesa resolución (backend DEX-3 **CERRADO**) |
| OR-5 | Suite de escenarios A–L + retry + crash en el Decision Spine · **CERRADO**                          | Simulación masiva post-v1.12                               |
| OR-6 | Readiness 4 estados + CTA `EJECUTAR EN PAPER\|LIVE` · **CERRADO**                                   | Thaw estricto · AUTO on                                    |

**OR-4 (veto):** `DRIFT` → no new entries · Allow protective / manual de-risk · Require human resolution. Detect → Explain → Require resolution. **Nunca** auto-heal.

**OR-6 (readiness):** `PAPER_READY` · `PAPER_DEGRADED` · `LIVE_EXPERIMENTAL` · `LIVE_BLOCKED`. Un FAIL crítico (p.ej. recon = 0) **no** se promedia a «50 % listo». OE-1 sigue **measure ≠ Accept**.

---

## 4. LIVE experimental · AUTO no es modalidad

- `XtbBrokerAdapter` + `POST /orders` = **puerto de experimento**, no de capital.
- `submitted ≠ fill`. Producto **BETA / no producción**.
- Clasificación: LIVE ADAPTER WIRED · LIVE TRADING **NOT ACCEPTED**.
- AUTO **no** significa IA → BUY. Significa Opportunity → TradePlan → Risk → Portfolio permission → Execution policy → Order, y cada paso puede bloquear. Confirm sigue siendo la **única** firma transaccional. `PAPER_D_EXECUTE` default **OFF**.

---

## 5. Parked (deuda deliberada)

- Tabla `position_revisions` (hoy JSON en snapshot).
- JSONB `position_state` como SoT → columnas (JP-1 dual-write se conserva).
- ExecutionRecord como entidad fuerte (OR-1 no la crea; identidad durable PG = DEX-1).
- Tabla PG `submit_intents` / Redis multi-worker (OR-2 físico) → **DEX-1 + DEX-2 CERRADOS** (tabla + store PG + cert store fresco); Redis multi-worker sigue parked.
- Más brokers (IBKR, etc.).
- AUTO on · thaw estricto · Accept P1–P5.
- Simulación 1.000–10.000 sesiones (después de cerrar OR-1…OR-6 / DEX).

---

## 6. Freeze

ADR-034 intacto · Confirm = única firma · Lab ≠ mesa · thin 5.x/8.x congelados · I1–I3 + RX1 · `PAPER_D_EXECUTE` off · mesa default paper · no `contract:gen` en OR-1…OR-3 · no Alembic en OR-1…OR-3 (Alembic `submit_intents` = **DEX-1**).

---

## 7. Consecuencias

- Docs: triage v111 reliability · roadmap v1.12 · plan OR-1 · plan OR-2 · plan OR-3 · plan OR-4 · plan OR-5 · plan OR-6 · relevo OR-6 · pack + tag `v1.12-beta`.
- Código: **OR-1 CERRADO** — short-circuit Confirm · ids estables · fail-closed sin `decision_id`. **OR-2 CERRADO vía DEX-1+DEX-2** — `DurableSubmitIntent` pre-submit · recovery `UNKNOWN` sin re-POST · mapeo `venue_order_id` · PG `submit_intents` · cert store/cliente fresco cross-PID. **OR-3 CERRADO** — `PaperOrder` Literal + grafo · PaperBroker `SUBMITTED`→`FILLED`/`UNKNOWN` · crash recovery `paperOrder.status=UNKNOWN`. **OR-4 CERRADO** — recon → opening veto (`drift` / live `unavailable`); exits ALLOW; OE-1 OI-6 honesto; sin auto-heal. **OR-5 CERRADO** — suite A–L + retry + crash anclada a spine (15 tests certificación). **OR-6 CERRADO** — 4 estados de readiness (sin promedio) + CTA `Ejecutar en PAPER|LIVE` + UI preferencia cuenta.
- Spine: `pnpm test:decision-spine` **483** (partida v1.12 = 433 · post-DEX-2 = 440 · post-DEX-3 = 463 · post-DEX-4 = 465 · post-DEX-5 = 483).
- Pack [`audit-pack-estado-global-2026-08-26-v112.md`](../engineering/audit-pack-estado-global-2026-08-26-v112.md) · tag [`traspaso-relevo-tag-v1-12-beta-2026-08-26.md`](../engineering/traspaso-relevo-tag-v1-12-beta-2026-08-26.md).

---

## 8. Post-v1.12 audit (2026-08-26) — Durable Execution

Auditoría externa contra código `369b5d1`: OR-2 **PARTIAL / CONDITIONALLY CLOSED** en tag v1.12. Tag `v1.12-beta` **válido**. **DEX-1 + DEX-2 (2026-08-26)** cierran persistencia PG + cert store/cliente fresco → `UNKNOWN` · 0 re-POST.

| Cerrado (v1.12 lógico)                                                          | Cerrado (V1.13 físico)                                                                                                                                                                                                                 | Sigue parked                                    |
| ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| UNKNOWN · identity · venue map · no blind re-POST · reconstruction mismo worker | PG `submit_intents` · `PostgresSubmitIntentStore` · fases `send_attempted` · tests cross-PID (store fresco) · `OperationalIncident` resolve/clear (mínimo backend) · Confirm = orquestador (DEX-4) · invariantes operacionales (DEX-5) | Redis multi-worker · Incident UI Mesa · 10k sim |

**Siguiente fase:** pack auditor v113 (cierre) — [`roadmap-v113-durable-execution-2026-08-26.md`](../engineering/roadmap-v113-durable-execution-2026-08-26.md) · triage [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](../engineering/audit-ext-v112-durable-execution-triage-2026-08-26.md).

DEX-1…DEX-5: PG `submit_intents` (**DEX-1 CERRADO**) → crash tests cross-PID (**DEX-2 CERRADO**) → Incident resolution (**DEX-3 CERRADO**) → Confirm decomposition (**DEX-4 CERRADO**) → operational invariants (**DEX-5 CERRADO**). Pack auditor [`audit-pack-estado-global-2026-08-26-v113.md`](../engineering/audit-pack-estado-global-2026-08-26-v113.md). Tag **`v1.13-beta` → `c8d5800`**. **No** ADR-036 (esta sección extiende el contrato).

**DEX-1 (2026-08-26):** Alembic `013` · `PostgresSubmitIntentStore` · fases `send_attempted` + `send_attempted_at` · Confirm DI PG. Relevo [`traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md`](../engineering/traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md).

**DEX-2 (2026-08-26):** Cert store/sesión A → kill → store B fresco → Confirm `UNKNOWN` · 0 re-POST. Spine **440**. Plan [`plan-dex2-crash-restart-cross-pid-2026-08-26.md`](../engineering/plan-dex2-crash-restart-cross-pid-2026-08-26.md) · relevo [`traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md`](../engineering/traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md).

**DEX-3 (2026-08-26):** `OperationalIncident` + Alembic `014` + store PG · drift → OPEN → review → resolve (nota; sin auto-heal) → clear solo si recon `clean` · veto `incident:unresolved`. Spine **463**. Plan [`plan-dex3-operational-incident-2026-08-26.md`](../engineering/plan-dex3-operational-incident-2026-08-26.md) · relevo [`traspaso-relevo-dex3-operational-incident-2026-08-26.md`](../engineering/traspaso-relevo-dex3-operational-incident-2026-08-26.md).

**DEX-4 (2026-08-26):** Confirm = orquestador · `bolsa_application/confirm/` (Identity / RiskGate / OpeningGate / ExitGate / Execution / SubmitIntent / PositionSync). Semántica intacta. Spine **465**. Plan [`plan-dex4-confirm-orchestrator-2026-08-26.md`](../engineering/plan-dex4-confirm-orchestrator-2026-08-26.md) · relevo [`traspaso-relevo-dex4-confirm-orchestrator-2026-08-26.md`](../engineering/traspaso-relevo-dex4-confirm-orchestrator-2026-08-26.md).

**DEX-5 (2026-08-26):** Invariantes operacionales (property suite): qty ≥ 0 · filled ≤ ordered · terminal no re-ejecuta · 1 decision ≤1 order · drift blocks opening · protect no ↑ exposición. Spine **483**. Plan [`plan-dex5-operational-invariants-2026-08-26.md`](../engineering/plan-dex5-operational-invariants-2026-08-26.md) · relevo [`traspaso-relevo-dex5-operational-invariants-2026-08-26.md`](../engineering/traspaso-relevo-dex5-operational-invariants-2026-08-26.md).
