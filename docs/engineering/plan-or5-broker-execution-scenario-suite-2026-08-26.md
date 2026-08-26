# Plan — OR-5 Broker execution scenario suite

> **Padre:** [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO** (código + tests + docs). Spine **418**.
> **Relevo:** [`traspaso-relevo-or5-broker-execution-scenario-suite-2026-08-26.md`](./traspaso-relevo-or5-broker-execution-scenario-suite-2026-08-26.md).

---

## Objetivo

Certificar en el Decision Spine la batería del auditor (**A–L** + **retry** OR-1 + **crash** OR-2):

```text
A entrada SEMI → B manual → C/D SELL parcial/total
→ E timeout paper → F persist fail post-fill
→ G/H protect OK/fail → I T1 → J T2 no-replay
→ K recon drift → L broker unavailable
→ retry (OR-1) · crash (OR-2)
```

**Validar, no expandir.** Paper/mock. Sin live e2e accepted. Sin simulación 1k–10k (post-v1.12). Sin OR-6 CTA.

## Decisiones

| ID  | Decisión                                                                                                                                      |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Un módulo spine `test_or5_broker_execution_scenarios.py` con tests `test_or5_a_…` … `test_or5_l_…` + `test_or5_retry_…` + `test_or5_crash_…`. |
| D2  | Escenarios = **certificación** de contratos ya cerrados (OI/OR-1…4 / PH-1 / ExitPlan). Sin código de producto nuevo salvo hueco real.         |
| D3  | Matriz A–L fija (abajo). **J** = T2 subsume T1 (no reduce a ciegas como T1). **E** = boom/timeout → `unknown` (OI-3). Retry = OR-1 aparte.    |
| D4  | Anclar el módulo en `pnpm test:decision-spine` (`verify_decision_spine_battery.mjs`).                                                         |
| D5  | Sin Alembic · sin `contract:gen` · sin UI · sin OR-6 · sin auto-heal · sin mass sim.                                                          |
| D6  | Docs: plan · CURRENT_SYSTEM · ADR-035 · CHANGELOG · roadmap · relevo OR-5.                                                                    |

## Matriz A–L

| ID  | Escenario              | Contrato / ancla                                          |
| --- | ---------------------- | --------------------------------------------------------- |
| A   | Entrada normal SEMI    | Confirm TRIGGERED → `executed`                            |
| B   | Manual                 | HTTP gated buy → `human_manual`                           |
| C   | SELL parcial           | PersistExit → `PARTIAL` + remaining                       |
| D   | SELL total             | PersistExit → `CLOSED`                                    |
| E   | Timeout paper          | Confirm boom → `unknown` (≠ error ≠ gate)                 |
| F   | Persist fail post-fill | Fill OK + persist boom → trade `executed` + persist error |
| G   | Protect OK             | Confirm protect → `protect_applied`                       |
| H   | Protect fail           | Persist None → `skipped` / `stop_not_applied` (PH-1)      |
| I   | T1                     | ExitPlan `TARGET_1` → `reduce`                            |
| J   | T2 no-replay           | `TARGET_2` subsume; sin `TARGET_1` en reasons             |
| K   | Recon drift            | OI-6 `drift` → `reconciliation:portfolio_drift`           |
| L   | Broker unavailable     | Live venue + `unavailable` → veto; mock LIVE `not_wired`  |

Plus: **retry** (OR-1 short-circuit) · **crash** (OR-2 recovery sin re-POST).

## Ficheros

- [`test_or5_broker_execution_scenarios.py`](../../packages/py/application/tests/test_or5_broker_execution_scenarios.py)
- [`verify_decision_spine_battery.mjs`](../../scripts/research/verify_decision_spine_battery.mjs)
- Docs: este plan · CURRENT_SYSTEM · ADR-035 · CHANGELOG · roadmap · relevo

## DoD

- [x] A–L + retry + crash verdes en el módulo OR-5 (15 tests).
- [x] Módulo en `pnpm test:decision-spine`; spine **418**.
- [x] Sin Alembic / `contract:gen` / OR-6 / mass sim.
- [x] Docs + relevo OR-5.

## Freeze (intactos)

ADR-034 · Confirm = única firma · `PAPER_D_EXECUTE` off · no broker producción · no auto-heal · thin 5.x/8.x congelados · Lab ≠ mesa · OR-1…OR-4 intactos.

## E1

Tras OR-5: **OR-6** SEMI certification (CTA venue) **o** operar SEMI. **No** pack auditor v112 (al tag) en el mismo chat.
