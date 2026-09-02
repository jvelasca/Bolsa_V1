# Arranque auditor — V1.78 Session Golden MERCADO→EXIT (2026-09-02)

> **Padre:** [`spec-v178-session-golden-mercado-exit-2026-09-02.md`](./spec-v178-session-golden-mercado-exit-2026-09-02.md) · partida **V1.77** [`1f25d351`](https://github.com/jvelasca/Bolsa_V1/commit/1f25d351)

## Punta de partida

- Producto: **V1.77** Session Reliability (E2E mock locales; sin CI GREEN)
- Brecha: arco golden MERCADO→EXIT aún no certificado en browser mock (pytest V1.53/55 ≠ UI journey)
- Regla: **NINGÚN estado ambiguo → COMPRAR** · dryRun honesto ≠ execute ledger

## Qué auditar

| GP         | Evidencia                                                    |
| ---------- | ------------------------------------------------------------ |
| GP-V178-01 | NVDA entry-only · entry surface · sin positionId · 0 COMPRAR |
| GP-V178-02 | Hoy AUTO armado · ejecución off · dryRun · 0 COMPRAR         |
| GP-V178-03 | ENTRY_STALE_DATA BLOCKED → recovery sin COMPRAR              |
| GP-V178-04 | POSITION AAPL · assertOperationalTruth                       |
| GP-V178-05 | data-pov-state=T1_READY · Reducir · 0 COMPRAR                |
| GP-V178-06 | data-pov-state=TRAILING · Proteger · ≠ COMPRAR               |
| GP-V178-07 | recon CRITICAL → clean · 0 COMPRAR                           |
| GP-V178-08 | data-pov-state=EXIT_REQUIRED · Salir · 0 COMPRAR             |

## Pre-flight (local 2026-09-02)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v178
# → 8 passed

E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-v173|gp-v174|gp-v175|gp-v176|gp-v177"
# → 20 passed (3 integrated skipped)

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

## No declarar

- CI GREEN · LIVE · bump `1.35.0-beta`
- `dryRun=false` browser · scheduler prod · fills ledger
