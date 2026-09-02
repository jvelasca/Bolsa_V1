# Arranque auditor — V1.65 Operational Identity & Canonical DTO (2026-09-02)

> **Padre:** [`spec-v165-operational-identity-dto-2026-09-02.md`](./spec-v165-operational-identity-dto-2026-09-02.md) · [`traspaso-relevo-v1-65-operational-identity-dto-2026-09-02.md`](./traspaso-relevo-v1-65-operational-identity-dto-2026-09-02.md).

## Qué auditar

1. **Identidad** — `decisionId` y `tradePlanId` separados en nacimiento, POV y revisiones. Legacy sin `decisionId` → `lineageCollapsed: true`, no inferencia silenciosa.
2. **DTO HTTP** — `OperationalPositionDto` expone `decisionId` + `operationalView`; hook cliente prefiere wire canónico.
3. **Tests** — GP-V165-03 lineage · GP-V162-04 CTA real · GP-V165-06 prefer-wire.
4. **Gobierno** — `CURRENT_SYSTEM.md` producto V1.64 cerrado; V1.65 documentada.

## Pre-flight

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-operational-view.test.ts src/cognitive/position-lineage.test.ts src/cognitive/position-state.test.ts src/cognitive/same-position-operating-truth-across-surfaces.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/use-position-operational-view.test.ts src/features/trading/entry-decision-surface.test.ts
python -m pytest packages/py/analytics/tests/test_position_state.py packages/py/analytics/tests/test_position_operational_view.py packages/py/application/tests/test_origin_decision_package.py -q
python -m pytest apps/api-python/tests/integration/test_v159_e2e_paper_desk.py apps/api-python/tests/integration/test_v159_e2e_operational_wire.py -m integration -q
pnpm --filter @bolsa/web exec tsc --noEmit
```

## Deuda aparcada

Why (V1.66) · E2E Mercado real (V1.67) · aislamiento E2E mutante · LISTA→GRÁFICO→ACCIÓN · quitar fallback cliente POV · LIVE.
