# Arranque auditor — V1.71 Identity & Certification (2026-09-02)

> **Padre:** [`spec-v171-identity-certification-2026-09-02.md`](./spec-v171-identity-certification-2026-09-02.md) · partida **V1.70** (`960383d2`) · **Commit:** `b70849bd`

## Punta de partida

- Producto: **V1.70** LISTA→GRÁFICO→ACCIÓN, **aprobada con reservas de certificación**
- Brecha: POV wire sin recon; copy colapsaba unknown/failed/T2/DRIFT; E2E podía pintar verde por SKIP; focus duplicado; sin golden TS/Python

## Qué auditar

| GP         | Evidencia                                                                                                     |
| ---------- | ------------------------------------------------------------------------------------------------------------- |
| GP-V171-01 | `extra_mappers.attach_operational_positions` pasa `recon_status` · overlay en `use-position-operational-view` |
| GP-V171-02 | `entry-decision-surface.ts` / `position-decision-surface.ts` · tests REVISAR · headlines T2/DRIFT             |
| GP-V171-03 | `gateIntegratedE2eEnvironment` · buy throw · GP-V167-04 no SKIP si falta posición                             |
| GP-V171-04 | `data-instrument-id` lista/HUD/cockpit · `gp-v170-list-mercado-integrated.spec.ts` identidad + niveles        |
| GP-V171-05 | `open-hit-in-trading.ts` llama `focusInstrumentInMercado` · Asesor / Estilos / list-values-panel              |
| GP-V171-06 | `position-operational-view.test.ts` + `test_position_operational_view.py` goldens                             |

## Pre-flight (local 2026-09-02)

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-operational-view.test.ts src/cognitive/execution-state.test.ts
# → 21 + 16 passed

pnpm --filter @bolsa/web exec vitest run src/features/trading/entry-decision-surface.test.ts src/features/trading/position-decision-surface.test.ts src/features/trading/use-position-operational-view.test.ts src/features/trading/operativa-cockpit-card.test.tsx src/features/charts/chart-decision-surface-hud.test.tsx
# → 42 passed (5 files)

python -m pytest packages/py/analytics/tests/test_position_operational_view.py -q
# → 7 passed

pnpm --filter @bolsa/web exec tsc -b --noEmit
# → EXIT 0
```

E2E integrado **no** forma parte del stamp CI:

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v170-list
# mock: no requiere API

E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v170-list
# requiere API :8000 + PG; opt-in
```

## No declarar

- CI GREEN para V1.70 `960383d2` ni para V1.71 sin evidencia de `playwright-integrated` en tag
- LIVE · bump `1.35.0-beta`
