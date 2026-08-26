# Plan — OE-1 Ops Autoeval (SEMI + AUTO)

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034.  
> **AsOf:** 2026-08-26.  
> **Estado:** **CERRADO (código + tests + docs).**  
> **Relevo:** [`traspaso-relevo-oe1-ops-autoeval-2026-08-26.md`](./traspaso-relevo-oe1-ops-autoeval-2026-08-26.md).

---

## Objetivo

Scorecard read-only unificado SEMI/MANUAL vs AUTO (P1–P5). Measure ≠ Accept · ≠ flip env.

## Decisiones

| ID  | Decisión                                                                           |
| --- | ---------------------------------------------------------------------------------- |
| D1  | Script `scripts/ops_operativa_self_eval.mjs` → GET `/api/risk/ops-self-eval`.      |
| D2  | Builder `ops_self_eval.py` + counts SQL account; recon OI-6 = `not_wired` honesto. |
| D3  | Thin UI: chip Autoeval en `mesa-operational-bar` + HELP Hoy.                       |
| D4  | ≠ Accept estricto · ≠ default-on · ≠ Redis per-account · ≠ UI account venue.       |
| D5  | Tests unit builder (mocks); vitest barra + HELP.                                   |

## Kernel

```text
GET /risk/ops-self-eval
→ kill + venue + telemetry A0 + confirm/journal/buys/MaxDD
→ lanes.semi + lanes.auto (PASS|FAIL|WARN|UNAVAILABLE)
→ mesa chip + script --json
```

## Freeze

Confirm firma · `PAPER_D_EXECUTE` off · Accept parked · LAB≠TRADING.
