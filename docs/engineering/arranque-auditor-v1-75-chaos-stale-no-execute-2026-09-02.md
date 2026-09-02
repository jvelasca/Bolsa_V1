# Arranque auditor — V1.75 Chaos & stale → no-execute (2026-09-02)

> **Padre:** [`spec-v175-chaos-stale-no-execute-2026-09-02.md`](./spec-v175-chaos-stale-no-execute-2026-09-02.md) · partida **V1.74** (`67f922bf`) · tip certificado **[`b5b114ff`](https://github.com/jvelasca/Bolsa_V1/commit/b5b114ff)**

## Punta de partida

- Producto: **V1.74** Paper Autonomous Day · V1.73 Multi-instrument · V1.72 WHY rico
- Brecha: fail-closed stale/UNKNOWN/recovery sin E2E mock + pytest ancla
- **GitHub `main`:** [`b5b114ff`](https://github.com/jvelasca/Bolsa_V1/commit/b5b114ff) · árbol: https://github.com/jvelasca/Bolsa_V1/tree/main

## Qué auditar

| GP         | Evidencia                                          |
| ---------- | -------------------------------------------------- |
| GP-V175-01 | Hoy ENTRY_STALE_DATA · Datos obsoletos · 0 COMPRAR |
| GP-V175-02 | bucket `no_operar` count>0 · deny nombrado         |
| GP-V175-03 | Mercado entry surface · stale/bloquead · 0 COMPRAR |
| GP-V175-04 | Sin auto-heal · UNKNOWN copy · 0 COMPRAR           |
| GP-V175-05 | pytest dryRun STALE → held/data_stale · 0 sells    |
| GP-V175-06 | pytest ENTRY_STALE_DATA + humanMessage             |
| GP-V175-07 | pytest crash replay smoke · no 2º fill             |

## Pre-flight (local 2026-09-02)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v175
# → 4 passed

E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v174
# → 5 passed (regresión)

python -m pytest packages/py/application/tests/test_v175_chaos_stale_no_execute.py -q
# → 3 passed

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

## No declarar

- CI GREEN · LIVE · bump `1.35.0-beta`
- `dryRun=false` browser · scheduler prod
