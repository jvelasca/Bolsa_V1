# Spec — V1.65 Operational Identity & Canonical DTO

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (pre-flight local 2026-09-02).  
> **Padre:** [`spec-v164-browser-e2e-integrated-2026-09-02.md`](./spec-v164-browser-e2e-integrated-2026-09-02.md) · tip certificado previo **V1.64** (`cbe89c8`). **No** LIVE.

Cierra la deuda **Decision ≠ TradePlan ≠ Position** y empieza a emitir `PositionOperationalView` desde el backend. **No** añade pantallas nuevas.

```text
P0  GP-V165-01 — PositionState.decisionId persistido (TS+Python)
P0  GP-V165-02 — POV sin alias silencioso tradePlanId→decisionId
P0  GP-V165-03 — tests lineage DEC≠TP
P0  GP-V165-04 — port Python buildPositionOperationalView
P0  GP-V165-05 — OperationalPositionDto.decisionId + operationalView HTTP
P0  GP-V165-06 — hook prefer-wire (canonical sin reconstruir)
P1  GP-V165-07 — entry-decision-surface GP-V162-04 real
P1  GP-V165-08 — CURRENT_SYSTEM → V1.64 cerrado · V1.65 en curso
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin Alembic · package `1.35.0-beta` · V1.58–V1.64 intactos salvo identidad + DTO + test + docs.

Regla: **nunca** reutilizar `tradePlanId` como fallback silencioso de `decisionId` cuando la identidad real exista.

## 1. IN — P0 identidad

| ID         | Comportamiento                                                                                                                                                                         |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GP-V165-01 | `PositionState.decisionId: string \| null`. Nacimiento: `decisionId = tradePlan.decisionId`, `tradePlanId = tradePlan.tradePlanId ?? tradePlan.decisionId`. JSONB extra (sin Alembic). |
| GP-V165-02 | `buildPositionOperationalView`: `view.decisionId` solo desde `position.decisionId`. Legacy sin campo → `decisionId: null` + `lineageCollapsed: true`.                                  |
| GP-V165-03 | Fixture `DEC-1` ≠ `TP-1` → POV, POT, revision y `originDecisionId` conservan ambos.                                                                                                    |

## 2. IN — P0 DTO canónico

| ID         | Comportamiento                                                                                             |
| ---------- | ---------------------------------------------------------------------------------------------------------- |
| GP-V165-04 | Port Python de `buildPositionOperationalView` en `bolsa_analytics`.                                        |
| GP-V165-05 | `OperationalPositionDto.decisionId` + `operationalView` (POV JSON). Mapper servidor en `extra_mappers.py`. |
| GP-V165-06 | Hook: si wire trae `operationalView` → `source: "canonical"` sin reconstruir negocio.                      |

## 3. IN — P1

| ID         | Comportamiento                                                                                                   |
| ---------- | ---------------------------------------------------------------------------------------------------------------- |
| GP-V165-07 | `entry-decision-surface.test.ts` GP-V162-04: `phase → entryOperatingCtaFromPhase → entryDecisionLabel → assert`. |
| GP-V165-08 | `CURRENT_SYSTEM.md` producto V1.64 · V1.65 en curso.                                                             |

## 4. OUT / parked

LISTA→GRÁFICO→ACCIÓN · Why (V1.66) · Browser E2E Mercado real (V1.67) · aislamiento E2E mutante · HUD T2 · perfil inversor · Paper Autonomous Desk · LIVE · bump package · partir `TradePlan.decisionId` · quitar fallback cliente POV.

## 5. Pre-flight

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-operational-view.test.ts src/cognitive/position-lineage.test.ts src/cognitive/position-state.test.ts src/cognitive/same-position-operating-truth-across-surfaces.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/use-position-operational-view.test.ts src/features/trading/entry-decision-surface.test.ts
python -m pytest packages/py/analytics/tests/test_position_state.py packages/py/application/tests/test_origin_decision_package.py packages/py/analytics/tests/test_position_operational_view.py -q
python -m pytest apps/api-python/tests/integration/test_v159_e2e_paper_desk.py apps/api-python/tests/integration/test_v159_e2e_operational_wire.py -m integration -q
pnpm --filter @bolsa/web exec tsc --noEmit
```
