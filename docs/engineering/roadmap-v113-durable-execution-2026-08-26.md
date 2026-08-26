# Roadmap — v1.13 Durable Execution & Recovery

> **Padre:** [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md) · ADR-035 (nota post-audit).
> **AsOf:** 2026-08-26.
> **Estado:** **FASE CERRADA (código + pack).** **D0 + DEX-1…DEX-5 CERRADOS.** Pack [`audit-pack-estado-global-2026-08-26-v113.md`](./audit-pack-estado-global-2026-08-26-v113.md). Tag `v1.13-beta` **pendiente owner**. Partida **`v1.12-beta` → `369b5d1`**. Spine **483**. ≠ notas históricas CORE-R «v1.13».
> **Método:** cerrar la **durabilidad física** de SubmitIntent y certificar recuperación cross-PID. No más arquitectura general. No thaw. No broker producción. No LLM.

---

## 0. Por qué esta fase

v1.12 validó timeout, retry, crash _lógico_, drift y readiness. El auditor demostró que `DurableSubmitIntent` vive en **InMemory de proceso**: no sobrevive al PID. V1.13 congela la arquitectura y cierra ese agujero antes de más trading features.

```text
DEX-1  PG submit_intents (persistencia real)
    │
    ▼
DEX-2  Crash/restart cross-proceso
    │
    ▼
DEX-3  Incident / resolución recon
    │
    ▼
DEX-4  Confirm = orquestador
    │
    ▼
DEX-5  Invariantes operacionales
```

Autoridad normativa:

```text
CURRENT_SYSTEM → ADR-035 → código → tests → HELP
```

ADR-034 (integridad) y OR-1/3/4/5/6 **no se reabren**. OR-2 lógico se **completa** con DEX-1+DEX-2.

---

## 1. Secuencia (no se salta)

| Slice     | Nombre                    | Qué cierra                                                                  | Qué no                          | Estado      |
| --------- | ------------------------- | --------------------------------------------------------------------------- | ------------------------------- | ----------- |
| **D0**    | Triage + nota ADR-035     | OR-2 PARTIAL documentado · roadmap · plan DEX-1                             | Código                          | **CERRADO** |
| **DEX-1** | PostgreSQL SubmitIntent   | Alembic `013` · store PG · fases `recorded`/`send_attempted`/… · DI Confirm | Incident UI · Confirm split     | **CERRADO** |
| **DEX-2** | Real crash/restart        | Persist → submit → cliente/store fresco → UNKNOWN · 0 re-POST               | 10k sesiones                    | **CERRADO** |
| **DEX-3** | Reconciliation resolution | `OperationalIncident` + resolve/clear (mínimo backend)                      | Mesa UI plena (slice posterior) | **CERRADO** |
| **DEX-4** | Confirm decomposition     | Coordinators; Confirm = orquestador                                         | Redesign producto               | **CERRADO** |
| **DEX-5** | Operational invariants    | Batería formal / property-based anclada a spine                             | LIVE real · AUTO                | **CERRADO** |

Después: **pack v113 stampado** · tag **`v1.13-beta`** si el dueño lo pide ([`traspaso-relevo-tag-v1-13-beta-2026-08-26.md`](./traspaso-relevo-tag-v1-13-beta-2026-08-26.md)). Thaw estricto Accept sigue deuda. LIVE experimental. AUTO off.

---

## 2. DEX-1 (CERRADO)

Ver [`plan-dex1-pg-submit-intents-2026-08-26.md`](./plan-dex1-pg-submit-intents-2026-08-26.md) · relevo [`traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md`](./traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md).

Tabla `submit_intents` · `PostgresSubmitIntentStore` · fases mínimas + `send_attempted_at` · Confirm DI: PG en runtime, InMemory en unit tests.

## 2b. DEX-2 (CERRADO)

Ver [`plan-dex2-crash-restart-cross-pid-2026-08-26.md`](./plan-dex2-crash-restart-cross-pid-2026-08-26.md) · relevo [`traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md`](./traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md).

Store/sesión A → kill → store B fresco (`PostgresSubmitIntentStore` + backing durable) → Confirm `UNKNOWN` · 0 re-POST. Spine **440**.

## 2c. DEX-3 (CERRADO)

Ver [`plan-dex3-operational-incident-2026-08-26.md`](./plan-dex3-operational-incident-2026-08-26.md) · relevo [`traspaso-relevo-dex3-operational-incident-2026-08-26.md`](./traspaso-relevo-dex3-operational-incident-2026-08-26.md).

`OperationalIncident` (Alembic `014` + store PG). Drift → OPEN → review → resolve (nota; no muta libros) → clear solo si recon `clean`. Veto `incident:unresolved`. Sin auto-heal. UI Mesa banner = candidata posterior. Spine **463**.

## 2d. DEX-4 (CERRADO)

Ver [`plan-dex4-confirm-orchestrator-2026-08-26.md`](./plan-dex4-confirm-orchestrator-2026-08-26.md) · relevo [`traspaso-relevo-dex4-confirm-orchestrator-2026-08-26.md`](./traspaso-relevo-dex4-confirm-orchestrator-2026-08-26.md).

`bolsa_application/confirm/`: Identity / RiskGate / OpeningGate / ExitGate / Execution / SubmitIntent / PositionSync. `ConfirmRecommendationIntent` = orquestador. Spine **465**.

## 2e. DEX-5 (CERRADO)

Ver [`plan-dex5-operational-invariants-2026-08-26.md`](./plan-dex5-operational-invariants-2026-08-26.md) · relevo [`traspaso-relevo-dex5-operational-invariants-2026-08-26.md`](./traspaso-relevo-dex5-operational-invariants-2026-08-26.md).

Invariantes: qty ≥ 0 · filled ≤ ordered · terminal no re-ejecuta · 1 decision → ≤1 live order · drift blocks opening · protect no aumenta exposición. Kernel `paper_order` endurecido · `operational_invariants.py`. Spine **483**.

---

## 3. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental**. AUTO **off**. Accept estricto **parked**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OR-1/3/4/5/6 **no se reabren** a ciegas.
- Auto-exit **no** es CTA cotidiano. **No** más brokers.
- JSONB PositionState SoT · `position_revisions` parked.

---

## 4. Docs clave

- Triage [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md)
- Plan DEX-1 · ADR-035 · `CURRENT_SYSTEM.md`
- Pack v113: [`audit-pack-estado-global-2026-08-26-v113.md`](./audit-pack-estado-global-2026-08-26-v113.md) · relevo tag [`traspaso-relevo-tag-v1-13-beta-2026-08-26.md`](./traspaso-relevo-tag-v1-13-beta-2026-08-26.md)
- Pack v112 (histórico): [`audit-pack-estado-global-2026-08-26-v112.md`](./audit-pack-estado-global-2026-08-26-v112.md)
- Roadmap v1.12 (cerrado, OR-2 PARTIAL anotado): [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md)
