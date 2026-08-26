# Audit pack — estado global v1.13 (Durable Execution)

> **AsOf:** 2026-08-26 · **Tag:** **`v1.13-beta`** — stamp release (SHA pin tras Release CI GREEN). Partida **`v1.12-beta` → `369b5d1`**.
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · roadmap [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md) · ADR-035 §8 · triage [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md) · pack previo [`audit-pack-estado-global-2026-08-26-v112.md`](./audit-pack-estado-global-2026-08-26-v112.md).
> **Para:** auditoría externa / GitHub Actions Release tag CI · cierre de fase V1.13.

---

## 0. Veredicto interno

Durable Execution v1.13 **CERRADA (D0 + DEX-1…DEX-5)**: persistencia PG de `DurableSubmitIntent`, certificación crash/restart cross-PID (store/cliente fresco → `UNKNOWN` · 0 re-POST), workflow mínimo `OperationalIncident` (resolve/clear sin auto-heal), Confirm descompuesto en coordinators (orquestador), e invariantes operacionales formalizados como property suite anclada al Decision Spine. OR-2 (ADR-035) queda **cerrado vía DEX-1+DEX-2**. Producto sigue **BETA / no producción**. Confirm = **única** firma. Accept estricto **NO**. `PAPER_D_EXECUTE` repo **OFF**. LIVE **experimental**. AUTO **off**.

| Slice | Nombre                      | Estado  |
| ----- | --------------------------- | ------- |
| D0    | Triage + nota ADR-035 §8    | CERRADO |
| DEX-1 | PostgreSQL SubmitIntent     | CERRADO |
| DEX-2 | Crash/restart cross-PID     | CERRADO |
| DEX-3 | OperationalIncident resolve | CERRADO |
| DEX-4 | Confirm = orquestador       | CERRADO |
| DEX-5 | Operational invariants      | CERRADO |

**Mensaje clave:** v1.12 **validó** lógica OR; v1.13 **endurece** durabilidad física + recuperación + incidente + orquestación Confirm + invariantes. Tag `v1.12-beta` intacto. **No** Accept estricto. **No** default-on execute. **No** AUTO on. **No** broker producción. **No** UI Mesa resolución incidente (candidata post-tag).

---

## 1. Scorecard DEX-1…DEX-5

| Slice     | Cierra                                                                                       | Evidencia principal                                                 | Spine   |
| --------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------- |
| **DEX-1** | Tabla `submit_intents` · `PostgresSubmitIntentStore` · fases `send_attempted` · DI Confirm   | Alembic `013` · store PG · `test_submit_intent*`                    | —       |
| **DEX-2** | Persist → kill → store/cliente fresco → `UNKNOWN` · 0 re-POST                                | `test_dex2_crash_restart_cross_pid.py`                              | **440** |
| **DEX-3** | Drift → OPEN → review → resolve(nota) → clear(solo recon clean) · veto `incident:unresolved` | Alembic `014` · `test_dex3_operational_incident.py`                 | **463** |
| **DEX-4** | Confirm = orquestador · `bolsa_application/confirm/` coordinators                            | `test_dex4_confirm_orchestrator.py`                                 | **465** |
| **DEX-5** | 6 invariantes property/seeded · `paper_order` qty/filled endurecido                          | `operational_invariants.py` · `test_dex5_operational_invariants.py` | **483** |

Invariantes DEX-5 (formalizados):

```text
qty ≥ 0
filled ≤ ordered
terminal ≠ re-ejecuta (fill)
1 decision_id → ≤1 live order_id (estable)
drift / incident unresolved → blocks opening
protect sin override → no empeora stop (no ↑ exposición)
```

---

## 2. Batería (local, pre-tag / 2026-08-26)

| Gate                       | Resultado                                                        |
| -------------------------- | ---------------------------------------------------------------- |
| `pnpm test:decision-spine` | **483** passed                                                   |
| Alembic                    | `013_submit_intents` · `014_operational_incidents` en `bolsa_v1` |
| Release tag CI             | `release-tag-ci.yml` — al pushear tag `v1.13-beta`               |

```bash
pnpm test:decision-spine
# expect: 483 passed
```

Spine progression V1.13: **433** (v1.12) → **440** (DEX-2) → **463** (DEX-3) → **465** (DEX-4) → **483** (DEX-5).

---

## 3. Qué entra en el tag (cuando el owner lo pida)

- **DEX-1:** Alembic `013` · `PostgresSubmitIntentStore` · fases `recorded`/`send_attempted`/… · Confirm DI PG.
- **DEX-2:** Cert cross-PID store/cliente fresco → `UNKNOWN` · 0 re-POST.
- **DEX-3:** `OperationalIncident` + Alembic `014` · veto `incident:unresolved` · sin auto-heal · sin UI Mesa.
- **DEX-4:** `bolsa_application/confirm/` Identity·RiskGate·OpeningGate·ExitGate·Execution·SubmitIntent·PositionSync.
- **DEX-5:** `operational_invariants.py` · suite 6 invariantes · `paper_order` qty/filled fail-closed.
- ADR-035 §8 · roadmap v1.13 · pack v113 · `CURRENT_SYSTEM.md`. ADR-034 / OR-1/3/4/5/6 intactos.

---

## 4. Qué no entra / parked (candidatas post-v1.13)

| Excluido / parked                          | Notas                                    |
| ------------------------------------------ | ---------------------------------------- |
| Accept estricto P1–P5                      | Deuda; DoD runbook §4 + palabra **thaw** |
| `PAPER_D_EXECUTE` default on               | Opt-in local; repo **off**               |
| AUTO on / AUTO como modalidad              | Confirm = firma                          |
| UI Mesa banner / HTTP resolución incidente | Tras DEX-3 backend; slice UI posterior   |
| Redis multi-worker SubmitIntent            | Parked                                   |
| `position_revisions` tabla / SoT columnas  | JP-1 dual-write; JSONB PositionState SoT |
| ExecutionRecord entidad DB fuerte          | Parked                                   |
| OperationalPolicy (TEST/PAPER/SEMI/LIVE)   | Parked                                   |
| Simulación 1k–10k sesiones                 | Parked                                   |
| LIVE trading accepted / XTB capital        | LIVE experimental only                   |
| Thin 5.x/8.x / brokers nuevos              | Congelados                               |
| Reabrir OR-1/3/4/5/6 o DEX-1…5 a ciegas    | No                                       |

---

## 5. Cadena de autoridad

```text
CURRENT_SYSTEM → ADR-035 (§8 Durable Execution) → código → tests → HELP

Confirm SEMI = firma
OR-2 = cerrado vía DEX-1 + DEX-2 (PG + cert cross-PID)
Incident = detect → review → resolve(nota) → clear(recon clean) · sin auto-heal
DEX-5 invariants = property suite anclada a spine (≠ 10k sim)
Venue: memory ?? redis ?? account ?? env ?? paper
```

---

## 6. Freeze (v1.13)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · ExitPlan ≠ auto-exit · Confirm = firma · thin 5.x/8.x congelados · I1–I3 + RX1 · OI-1…OE-1 **no se reabren** · OR-1/3/4/5/6 **no se reabren** · DEX-1…DEX-5 **no se reabren** a ciegas · `PAPER_D_EXECUTE` **off** · mesa default **paper** · LIVE experimental · Accept estricto **parked** · AUTO **off** · **BETA / no producción**.

---

## 7. Docs clave (lectura auditor)

| Tipo       | Documento                                                                                                           |
| ---------- | ------------------------------------------------------------------------------------------------------------------- |
| SoT vivo   | [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)                                                                         |
| Contrato   | [`035-operational-reliability.md`](../adr/035-operational-reliability.md) (§8 Durable Execution)                    |
| Integridad | [`034-operational-integrity-continuity.md`](../adr/034-operational-integrity-continuity.md)                         |
| Roadmap    | [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md)                    |
| Triage     | [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md)  |
| Relevo tag | [`traspaso-relevo-tag-v1-13-beta-2026-08-26.md`](./traspaso-relevo-tag-v1-13-beta-2026-08-26.md)                    |
| DEX-5      | [`plan-dex5-operational-invariants-2026-08-26.md`](./plan-dex5-operational-invariants-2026-08-26.md) · relevo DEX-5 |
| Pack prev. | [`audit-pack-estado-global-2026-08-26-v112.md`](./audit-pack-estado-global-2026-08-26-v112.md)                      |
| Thaw deuda | [`deuda-thaw-estricto-runbook-2026-08-25.md`](./deuda-thaw-estricto-runbook-2026-08-25.md)                          |

---

## 8. Checklist auditor (E1)

1. Checkout tag **`v1.13-beta`** (SHA pin tras Release CI GREEN; owner publica).
2. Verificar GitHub Actions **`release-tag-ci.yml`** GREEN en el push del tag.
3. Ejecutar `pnpm test:decision-spine` → esperar **483** passed.
4. Contrastar ADR-035 §8 (DEX-1…DEX-5 CERRADOS) con código: PG intents, cert cross-PID, Incident resolve/clear, Confirm coordinators, property suite.
5. Confirmar freeze §6: sin Accept estricto, sin default-on, sin AUTO on, mesa paper, Confirm = firma, LIVE experimental, sin UI Mesa incidente.
6. Opcional SEMI UI: TRIGGERED → Confirm → CTA `Ejecutar en PAPER` · readiness en barra.
7. Emitir triage/findings si aplica (candidatas §4).

**Preguntas que este pack no resuelve:** Accept estricto · default-on · AUTO on · UI Mesa incidente · Redis multi-worker · mass sim · broker producción · thaw.
