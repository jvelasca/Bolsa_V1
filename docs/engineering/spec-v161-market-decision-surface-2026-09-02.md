# Spec — V1.61 Market Decision Surface (posición)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (pre-flight local 2026-09-02).  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-042](../adr/042-operating-excellence.md) · [`spec-v160-ux-mercado-2026-09-02.md`](./spec-v160-ux-mercado-2026-09-02.md) · tip certificado previo **`v1.60-beta` → `7ac8ad9b`**. **No** LIVE.

Consolida el panel **DECISIÓN** de Mercado en una única **Position Decision Surface** (qué ocurre / qué hacer / por qué). Corrige recon desconocido→CLEAN y semántica visual verde fija. **No** motores nuevos · **no** EntryOperationalView · **no** E2E browser.

```text
P0  GP-V161-01 — recon fail-closed (unknown → unavailable, nunca CLEAN)
P0  GP-V161-02 — tono visual según operatingState
P0  GP-V161-03 — una superficie (sin StarCard + Summary apilados)
P1  GP-V161-04 — Primary Action Honesty (ninguna → COMPRAR)
P1  GP-V161-05 — DECISIÓN vs EJECUCIÓN copy
P1  GP-V161-06 — cross-surface POV facts (builders)
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin Alembic · sin bump package (`1.35.0-beta`) · sin scheduler · V1.54–V1.60 intactos salvo UI Mercado + tests shared/web.

Regla global: `Ranking ≠ Signal ≠ Proposal ≠ Authorization ≠ Order ≠ Fill`.

Regla de esta versión: **display-only en superficie** — no firma · no BUY. Una CTA primaria en ACCIÓN alineada a POV.

## 1. IN — P0

| ID         | Comportamiento                                                                                                                                         |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| GP-V161-01 | `mapPortfolioReconToPovRecon`: `clean`/`ok`→clean · `drift`→drift · `unavailable`/`not_wired`/`error`→unavailable · vacío/null→null · otro→unavailable |
| GP-V161-02 | `data-tone` + bordes según `operatingState` (esmeralda/ámbar/rosa/muted)                                                                               |
| GP-V161-03 | Fase `posicion`: Decision Surface única; sin `PositionOperatingSummary` ni `OperationalPlanView`; `ExitRouteView` conservado                           |

## 2. IN — P1

| ID         | Comportamiento                                                                                           |
| ---------- | -------------------------------------------------------------------------------------------------------- |
| GP-V161-04 | PROTECTED→MANTENER · T1_READY→REDUCIR · EXIT_REQUIRED→SALIR · DRIFT/ERROR→REVISAR · ninguna→COMPRAR      |
| GP-V161-05 | DECISIÓN + EJECUCIÓN (NO REQUERIDA / PENDIENTE / EJECUTADA)                                              |
| GP-V161-06 | Misma fixture → mismo `operatingState` / `primaryAction` / recon / `nextEvent` en builders cross-surface |

Hook `buildPositionOperationalViewFromDto` devuelve `{ view, source: "canonical" \| "fallback" }`. Aviso DEV si fallback.

## 3. OUT / parked

EntryOperationalView · gráfico-puente · DTO HTTP POV Python · Browser E2E→FastAPI→PG · Paper Autonomous Desk · LIVE · scheduler · bump package.

## 4. Pre-flight

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-operational-view.test.ts src/cognitive/operational-context.test.ts src/cognitive/same-position-operating-truth-across-surfaces.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/operativa-cockpit-phase.test.ts src/features/trading/operativa-cockpit-card.test.tsx src/features/trading/use-position-operational-view.test.ts
python -m pytest apps/api-python/tests/integration/test_v159_e2e_paper_desk.py apps/api-python/tests/integration/test_v159_e2e_operational_wire.py -m integration -q
python -m pytest packages/py/application/tests/test_paper_desk_golden_day_adversarial.py packages/py/application/tests/test_inv_operational_truth.py -q
pnpm --filter @bolsa/web exec tsc --noEmit
```
