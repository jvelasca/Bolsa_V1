# Arranque auditor — V1.74 Paper Autonomous Day (2026-09-02)

> **Padre:** [`spec-v174-paper-autonomous-day-2026-09-02.md`](./spec-v174-paper-autonomous-day-2026-09-02.md) · partida **V1.73** (`4b0e80f5`)

## Punta de partida

- Producto: **V1.73** Multi-instrument · **V1.72** WHY rico
- Brecha: cadena día autónomo Paper sin certificación E2E mock + pytest multi-tick

## Qué auditar

| GP             | Evidencia                                                         |
| -------------- | ----------------------------------------------------------------- |
| GP-V174-01     | `gp-v174-*-mock` T1 Reducir + MSFT oportunidad + buckets          |
| GP-V174-02     | AUTO armado · ejecución off · 0 COMPRAR                           |
| GP-V174-03     | `?view=journal` → `hoy-view-journal`                              |
| GP-V174-04     | Hoy→`/trading` identity `data-position-id` / `data-instrument-id` |
| GP-V174-05     | recon ok mock · sin drift inbox                                   |
| GP-V174-06..08 | `test_v174_paper_autonomous_day.py` multi-tick + journal + recon  |

## Pre-flight (local 2026-09-02)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v174-paper-autonomous-day-mock
# → 5 passed

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

## No declarar

- CI GREEN · LIVE · bump `1.35.0-beta`
- `dryRun=false` browser · chaos/stale execute (**V1.75**)
