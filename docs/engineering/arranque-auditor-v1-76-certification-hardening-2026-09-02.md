# Arranque auditor — V1.76 Certification Hardening (2026-09-02)

> **Padre:** [`spec-v176-certification-hardening-2026-09-02.md`](./spec-v176-certification-hardening-2026-09-02.md) · partida **V1.75** (`b5b114ff`)

## Punta de partida

- Producto: **V1.75** Chaos & stale → no-execute (E2E mock + pytest locales; sin CI GREEN)
- Brecha: GP-V175-01 OR AUTO feliz · GP-V175-04 UNKNOWN mezclado con stale · GP-V175-03 data-status AAPL vs NVDA
- **GitHub `main`:** [`b5b114ff`](https://github.com/jvelasca/Bolsa_V1/commit/b5b114ff)

## Qué auditar

| GP         | Evidencia                                                                                                                                |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| GP-V175-01 | `data-attention=BLOCKED` · `data-reason-code=ENTRY_STALE_DATA` · 0 COMPRAR · ítem sin AUTO armado · daily-report dryRun / !paperDExecute |
| GP-V175-02 | cubo `no_operar` count>0 (regresión)                                                                                                     |
| GP-V175-03 | `data-status.instrumentId=inst-nvda` · `freshnessStatus=stale` · cockpit NVDA · 0 COMPRAR                                                |
| GP-V175-04 | `ord-unknown-001` · lifecycle unknown · Orden desconocida / no reenviar · 0 COMPRAR · incidents vacíos                                   |
| GP-V176-01 | cadena freshness stale → reasonCode → BLOCKED → 0 COMPRAR                                                                                |

## Pre-flight (local 2026-09-02)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v175
# → 4 passed

E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v176
# → 1 passed

E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v174
# → 5 passed (regresión)

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0

pnpm --filter @bolsa/web test -- daily-desk-inbox
# → 6 passed

pnpm --filter @bolsa/shared test -- daily-desk-auto-projection
# → 13 passed
```

## No declarar

- CI GREEN · LIVE · bump `1.35.0-beta`
- `dryRun=false` browser · scheduler prod · V1.77 session reliability
