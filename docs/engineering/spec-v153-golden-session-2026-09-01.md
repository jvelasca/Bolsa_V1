# Spec — V1.53 Golden Session (Estudio → Journal)

> **AsOf:** 2026-09-01 · **Estado:** **CÓDIGO**.  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v152-position-lifecycle-2026-09-01.md`](./spec-v152-position-lifecycle-2026-09-01.md) · tip certificado previo **`v1.52-beta` → `1da5eb3f`**. **No** LIVE.

Un pytest de sesión PAPER completa: **09:00 Estudio entry → birth → protect → T1 → TRAIL×2 → exit → CLOSED → PaperDailyReport (journal projection)**. Reutiliza V1.48 PositionTick + V1.51 birth + V1.52 TargetLeg/revisions. **No** UI Mesa · **no** segundo motor.

```text
09:00  EstudioPaperDeskEntry → fill → Position (identidades distintas)
10:00  protect + trail hint
11:00  T1 reduce → target1Leg.executed
12:00  TRAIL #1 (decisionId + policyId)
13:00  TRAIL #2
16:00  structural stop → CLOSED
       build_paper_daily_report → position_exited
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off (test env on) · no LIVE · sin Alembic · sin bump package · sin UI Mesa · sin scheduler · V1.48 CAOS intacto.

## 1. IN

| ID                   | Comportamiento                                                |
| -------------------- | ------------------------------------------------------------- |
| GP-SESSION-01        | Estudio 09:00 birth 1 Position; plan ≠ candidate ≠ fill       |
| GP-SESSION-02        | protect → T1 → TRAIL×2 → exit mismo día                       |
| GP-SESSION-03        | `target1Leg.executed` tras reduce; trail revisions enrich     |
| GP-SESSION-04        | `PaperDailyReport` final: `position_exited=1`, store `CLOSED` |
| V1.48 Golden Session | intacto (HonestStub pre-open)                                 |
| V1.52 lifecycle GPs  | intactos                                                      |

## 2. OUT / parked

UI Mesa (**V1.54**) · browser E2E Journal · scheduler · LIVE · package bump · rankingEngineId · perfil→política.

## 3. Pre-flight

Bloque V1.52 + `test_paper_desk_golden_session_estudio.py` + ruff + tsc.
