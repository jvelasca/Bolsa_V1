# Roadmap — v1.12 Operational Reliability

> **Padre:** [`audit-ext-v111-operational-reliability-triage-2026-08-26.md`](./audit-ext-v111-operational-reliability-triage-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Estado:** **FASE CERRADA — D0 + OR-1…OR-6 CERRADOS · pack + tag `v1.12-beta`.** Partida **`v1.11-beta` → `76d0f951`**. Spine **433**. ≠ notas históricas CORE-R «v1.12».
> **Método:** **validar** el sistema bajo timeout, retry, crash y drift. No más arquitectura general. No thaw. No broker producción. No LLM.

---

## 0. Por qué esta fase

v1.11 dejó el post-fill **integrado** (OI-1…OE-1). El siguiente salto no es un indicador ni un adapter más: es demostrar que una operación **no se duplica ni se pierde** cuando falla la red, el proceso o la reconciliación.

```text
IDEMPOTENCIA E2E (retry Confirm = 1 fill)
    │
    ▼
CRASH / RESTART (UNKNOWN reconstruible)
    │
    ▼
ORDER STATE MACHINE (CREATED…FILLED + ramas)
    │
    ▼
RECON → OPENING VETO (drift bloquea entradas)
    │
    ▼
SCENARIO SUITE (A–L + retry + crash)
    │
    ▼
SEMI CERTIFICATION (4 estados; venue en CTA)
```

Autoridad normativa:

```text
CURRENT_SYSTEM → ADR-035 → código → tests → HELP
```

ADR-034 sigue siendo el contrato de **integridad** v1.11. No se reabre.

---

## 1. Secuencia (no se salta)

| Slice    | Nombre                          | Qué cierra                                                                                          | Qué no                              | Estado      |
| -------- | ------------------------------- | --------------------------------------------------------------------------------------------------- | ----------------------------------- | ----------- |
| **D0**   | Diseño / triage + ADR-035       | Congelar fiabilidad operativa · **no código**                                                       | Pack v112 (al tag)                  | **CERRADO** |
| **OR-1** | End-to-end idempotency          | Timeout + retry Confirm paper → 1 fill / 1 posición / misma identidad de intento                    | Tabla `execution_records` · XTB e2e | **CERRADO** |
| **OR-2** | Crash/restart recovery          | Submit intent durable; al reiniciar reconstruye `UNKNOWN` + recon                                   | Auto-heal                           | **CERRADO** |
| **OR-3** | Full order state machine        | Ampliar `CREATED→FILLED` hacia SUBMITTED / ACK / PARTIAL / REJECTED / CANCELLED / EXPIRED / UNKNOWN | Broker real · OCO                   | **CERRADO** |
| **OR-4** | Reconciliation → opening veto   | `drift` / live `unavailable` → DENY aperturas; exits protectivos ALLOW; sin heal                    | Resolución humana UI plena          | **CERRADO** |
| **OR-5** | Broker execution scenario suite | Batería A–L + retry + crash del auditor, anclada a `pnpm test:decision-spine`                       | 1.000–10.000 sesiones (post-v1.12)  | **CERRADO** |
| **OR-6** | SEMI operational certification  | Readiness `PAPER_READY` / `PAPER_DEGRADED` / `LIVE_EXPERIMENTAL` / `LIVE_BLOCKED`; venue en CTA     | Thaw estricto · AUTO on             | **CERRADO** |

Después: pack + tag **`v1.12-beta`** (**este release**). Thaw **estricto** Accept sigue deuda (DoD + palabra). UI preferencia cuenta = OR-6 (**cerrado**).

---

## 2. OR-1 (CERRADO)

Ver [`plan-or1-e2e-idempotency-2026-08-26.md`](./plan-or1-e2e-idempotency-2026-08-26.md) · relevo [`traspaso-relevo-or1-e2e-idempotency-2026-08-26.md`](./traspaso-relevo-or1-e2e-idempotency-2026-08-26.md).

Paper: Confirm → timeout → retry → **1 order identity + 1 execution**. Live: short-circuit solo con fill local; mapeo durable = OR-2 (**cerrado**).

## 2b. OR-2 (CERRADO)

Ver [`plan-or2-crash-restart-2026-08-26.md`](./plan-or2-crash-restart-2026-08-26.md) · relevo [`traspaso-relevo-or2-crash-restart-2026-08-26.md`](./traspaso-relevo-or2-crash-restart-2026-08-26.md).

Confirm persiste `DurableSubmitIntent` antes de `adapter.submit`. Crash/retry sin fill local → `UNKNOWN` reconstruido + mapeo `venue_order_id`; **no** re-POST. Store InMemory de proceso. Sin Alembic.

## 2c. OR-3 (CERRADO)

Ver [`plan-or3-order-state-machine-2026-08-26.md`](./plan-or3-order-state-machine-2026-08-26.md) · relevo [`traspaso-relevo-or3-order-state-machine-2026-08-26.md`](./traspaso-relevo-or3-order-state-machine-2026-08-26.md).

PaperOrder Literal + grafo `CREATED→SUBMITTED→ACK→PARTIAL→FILLED` + ramas. PaperBroker boom → `UNKNOWN`. Crash recovery `paperOrder.status=UNKNOWN`. OI-4 nacimiento CREATED intacto.

## 2d. OR-4 (CERRADO)

Ver [`plan-or4-recon-opening-veto-2026-08-26.md`](./plan-or4-recon-opening-veto-2026-08-26.md) · relevo [`traspaso-relevo-or4-recon-opening-veto-2026-08-26.md`](./traspaso-relevo-or4-recon-opening-veto-2026-08-26.md).

`check_opening`: OI-6 `drift` DENY aperturas; LR-1 `drift`/`unavailable` DENY solo venue live; exits ALLOW. OE-1 OI-6 honesto. Sin auto-heal · sin UI resolución.

## 2e. OR-5 (CERRADO)

Ver [`plan-or5-broker-execution-scenario-suite-2026-08-26.md`](./plan-or5-broker-execution-scenario-suite-2026-08-26.md) · relevo [`traspaso-relevo-or5-broker-execution-scenario-suite-2026-08-26.md`](./traspaso-relevo-or5-broker-execution-scenario-suite-2026-08-26.md).

Suite A–L + retry + crash en `test_or5_broker_execution_scenarios.py` anclada a spine (**418**). Sin OR-6 · sin mass sim.

## 3. OR-6 (CERRADO)

Ver [`plan-or6-semi-operational-certification-2026-08-26.md`](./plan-or6-semi-operational-certification-2026-08-26.md) · relevo [`traspaso-relevo-or6-semi-operational-certification-2026-08-26.md`](./traspaso-relevo-or6-semi-operational-certification-2026-08-26.md).

Cuatro estados discretos (sin %). CTA `Ejecutar en PAPER|LIVE`. UI preferencia cuenta (PA-1). OE-1 Autoeval intacto. LIVE nunca accepted.

## 4. Freeze (intactos en toda la fase)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · ExitPlan ≠ auto-exit · Confirm = firma · thin 5.x/8.x congelados · I1–I3 + RX1 · `PAPER_D_EXECUTE` **off** · mesa default **paper** · Accept estricto **parked** · LIVE **experimental** · **BETA / no producción**.

## 5. Parked (explícito)

- Live trading accepted · más brokers · AUTO on · thaw estricto
- Tabla `position_revisions` · JSONB PositionState → columnas como SoT
- Simulación 1.000–10.000 sesiones (después de v1.12)
- Auditoría 2 (owner no la entregó en este stamp)
