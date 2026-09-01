# Spec — V1.60 UX Mercado (tarjeta estrella DECISIÓN)

> **AsOf:** 2026-09-02 · **Estado:** **SPEC** (sin código).  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-042](../adr/042-operating-excellence.md) · [`spec-v157-operational-truth-2026-09-01.md`](./spec-v157-operational-truth-2026-09-01.md) · [`spec-v159-e2e-integrated-2026-09-02.md`](./spec-v159-e2e-integrated-2026-09-02.md) · tip certificado previo **`v1.59-beta` → `b5c5c6ab`**. **No** LIVE.

Cierra la brecha UI post-V1.57: el panel **DECISIÓN** (`operativa-cockpit-card`) consume **`PositionOperationalView`** (proyección canónica V1.55/V1.57) en lugar de depender solo de `PositionOperatingTruth` / copy legacy. **Tarjeta estrella** = una sola tarjeta contextual con estado operativo, stop history y recon honestos. **No** motores nuevos · **no** segundo Mercado.

```text
P0  GP-V160-01 — POV en tarjeta estrella (posición abierta)
P0  GP-V160-02 — T2_EXECUTED ≠ T2_READY · RECONCILIATION_DRIFT en copy/fase
P1  GP-V160-03 — stopHistory 5 orígenes visible (colapsable)
P1  GP-V160-04 — vitest componente + data-testid auditor
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin Alembic · sin bump package (`1.35.0-beta`) · sin scheduler · V1.54–V1.59 intactos salvo UI Mercado + tests.

Regla global: `Ranking ≠ Signal ≠ Proposal ≠ Authorization ≠ Order ≠ Fill`.

Regla de esta versión: **mismos hechos → misma proyección** en Mercado / Hoy / Journal (`PositionOperationalView` + `mapOperatingStateToDeskStatus`). Confirm = única firma. Una CTA primaria.

## 1. IN — P0 GP-V160-01..02

Archivos objetivo: `apps/web/src/features/trading/operativa-cockpit-card.tsx` · `position-operating-summary.tsx` (o subcomponente nuevo `position-operational-star-card.tsx` si reduce diff).

| ID         | Comportamiento                                                                                                                                                                                                                                                                 |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| GP-V160-01 | Con posición abierta + `position.operational` / blob PositionState: construir `PositionOperationalView` vía `positionOperationalViewFromBlob` o `buildPositionOperationalView`; tarjeta estrella muestra `operatingState`, `primaryAction`, `events` mínimos (no inventar BUY) |
| GP-V160-02 | Estados V1.57 visibles en chrome: `T2_READY` vs `T2_EXECUTED`; `RECONCILIATION_DRIFT` → copy/fase coherente con Hoy (`requiere_accion` / recon chip) — **≠** `RECONCILIATION_ERROR` de `unavailable`                                                                           |

Pre-open: reutilizar `portfolioReconStatus` ya cableado en cockpit; POV `operatingState` gana sobre heurística legacy cuando hay blob.

## 2. IN — P1 GP-V160-03..04

| ID         | Comportamiento                                                                                                                                                                                  |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GP-V160-03 | Bloque **Historial de stop** desde `view.stopHistory` — 5 orígenes (`protect` \| `trail` \| `reduce` \| `override` \| `stop`); deltas vs stop anterior; colapsable por defecto                  |
| GP-V160-04 | Vitest: `operativa-cockpit-card.test.tsx` (o extensión existente) con fixtures GP-V157-01 T2 + GP-V157-03 drift; `data-testid="operativa-cockpit-pov-state"` · `operativa-cockpit-stop-history` |

## 3. Relación con stacks previos

| Capa                           | Autoridad                        | V1.60                                  |
| ------------------------------ | -------------------------------- | -------------------------------------- |
| `buildPositionOperationalView` | `@bolsa/shared` tests GP-V157-\* | **Fuente UI** tarjeta estrella         |
| Golden Session / GP-V159 HTTP  | application + integration        | **Intacto** — pre-flight obligatorio   |
| Panel DECISIÓN F5              | spec-v142 §B                     | **Extiende** contenido, no layout dock |

## 4. OUT / parked

Segundo Mercado · drag entry/T1/T2 en gráfico · OpportunityScore · LIVE · scheduler · bump package · Playwright CI obligatorio · motores ranking/decision nuevos · encolar STRUCTURAL_STOP a apertura · redesign Hoy cubos · thaw Accept.

## 5. Pre-flight (post-implementación)

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-operational-view.test.ts src/cognitive/operational-context.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/operativa-cockpit-phase.test.ts src/features/trading/operativa-cockpit-card.test.tsx
python -m pytest apps/api-python/tests/integration/test_v159_e2e_paper_desk.py apps/api-python/tests/integration/test_v159_e2e_operational_wire.py -m integration -q
python -m pytest packages/py/application/tests/test_paper_desk_golden_day_adversarial.py packages/py/application/tests/test_inv_operational_truth.py -q
pnpm --filter @bolsa/web exec tsc --noEmit
```
