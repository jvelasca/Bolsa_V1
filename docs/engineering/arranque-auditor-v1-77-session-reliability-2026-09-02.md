# Arranque auditor — V1.77 Session Reliability (2026-09-02)

> **Padre:** [`spec-v177-session-reliability-2026-09-02.md`](./spec-v177-session-reliability-2026-09-02.md) · partida **V1.76** [`bf6ba462`](https://github.com/jvelasca/Bolsa_V1/commit/bf6ba462)

## Punta de partida

- Producto: **V1.76** Certification Hardening (E2E mock locales; sin CI GREEN)
- Brecha: journey identidad + fail-closed + recon en una certificación mock
- Regla: **NINGÚN estado ambiguo → COMPRAR**

## Qué auditar

| GP         | Evidencia                                                                |
| ---------- | ------------------------------------------------------------------------ |
| GP-V177-01 | A→B→C→A · IDs · phase · levels · primaryAction · recon CLEAN · 0 COMPRAR |
| GP-V177-02 | Refresh foco B · sin residual A                                          |
| GP-V177-03 | data-status stale · badge · 0 COMPRAR · IDs                              |
| GP-V177-04 | Recovery current · sin inventar COMPRAR                                  |
| GP-V177-05 | ord-unknown-001 · lifecycle unknown · no reenviar · 0 COMPRAR            |
| GP-V177-06 | recon drift CRITICAL · REVISAR · 0 COMPRAR                               |
| GP-V177-07 | Back to CLEAN · freshness current · 0 COMPRAR                            |

## Pre-flight (local 2026-09-02)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v177
# → 7 passed

E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-v173|gp-v174|gp-v175|gp-v176"
# → 13 passed (3 integrated skipped)

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

## No declarar

- CI GREEN · LIVE · bump `1.35.0-beta`
- Golden MERCADO→EXIT (V1.78+) · scheduler · dryRun=false browser
