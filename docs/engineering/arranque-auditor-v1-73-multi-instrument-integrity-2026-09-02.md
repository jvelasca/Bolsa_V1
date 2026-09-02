# Arranque auditor — V1.73 Multi-instrument integrity (2026-09-02)

> **Padre:** [`spec-v173-multi-instrument-integrity-2026-09-02.md`](./spec-v173-multi-instrument-integrity-2026-09-02.md) · partida **V1.72** (local post-`b70849bd`)

## Punta de partida

- Producto: **V1.72** Decision Explainability TOP (local) · **V1.71** Identity `b70849bd`
- Brecha: cambio de instrumento / refresh / Entry↔Position sin certificación E2E

## Qué auditar

| GP         | Evidencia                                                                                            |
| ---------- | ---------------------------------------------------------------------------------------------------- |
| GP-V173-01 | `gp-v173-*-mock/integrated` A→B→C→A · chart+cockpit `data-instrument-id` / `data-position-id`        |
| GP-V173-02 | refresh: foco B · reload + workspace B · sin residual A                                              |
| GP-V173-03 | dual chart Position→Entry (NVDA study ARMED)→Cartera Position · `entry-decision-surface` ↔ star card |
| GP-V173-04 | `ensureMultiInstrumentMercadoFixture` · `installMercadoMultiApiMocks` · quotes array fail-closed     |

## Pre-flight (local 2026-09-02)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v173-multi-instrument-mock
# → 3 passed

# Opt-in integrado:
# E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v173-multi-instrument-integrated

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

## No declarar

- CI GREEN · LIVE · bump `1.35.0-beta`
- Paper Autonomous Day (**V1.74**) · chaos / stale execute (**V1.75**)
