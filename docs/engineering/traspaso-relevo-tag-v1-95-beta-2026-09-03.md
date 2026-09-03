# RELEVO — tag v1.95-beta → auditoría tip (2026-09-03)

> **Padre:** [`traspaso-relevo-v1-95-beta-certification-2026-09-03.md`](./traspaso-relevo-v1-95-beta-certification-2026-09-03.md).  
> **Estado:** **CI GREEN** — tip `v1.95-beta` → `6f262293` · Release-tag CI **GREEN** ([run 33804374800](https://github.com/jvelasca/Bolsa_V1/actions/runs/33804374800)).  
> **Partida:** V1.94 tip [`363984d2`](https://github.com/jvelasca/Bolsa_V1/commit/363984d2) · [`respuesta-auditor-v194`](./respuesta-auditor-v194-financial-integrity-2026-09-03.md) + AUDITORIA 2.

## Release

| Pieza        | Valor                                                                                        |
| ------------ | -------------------------------------------------------------------------------------------- |
| Tag tip      | `v1.95-beta` → `6f262293`                                                                    |
| CI           | **GREEN** · [run 33804374800](https://github.com/jvelasca/Bolsa_V1/actions/runs/33804374800) |
| Pre-release  | https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.95-beta                                 |
| lifecycle-pg | success (auth + golden V1.88–V1.91/V1.95 + worker V1.92/V1.93 + integrity V1.94 + V1.95)     |

## Hecho certificado (código)

- lag / dead\_\* / unavailable → opening DENY (ALLOW iff compose clean)
- `dead_non_head` nunca clean → ops DEGRADED; `dead_head` BLOCKED
- Fill chain OPEN+T1+T2+EXIT ↔ ledger `reference_id`
- OR-4 consume compose financial integrity
- GET integrity/reconciliation: `None` → JSON blocked (no assert/500)
- FIFO outbox sort UTC-aware
- Golden HTTP V1.95 OPEN→T1→EXIT→corrupt→DENY

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no `queue_sequence` · no unificar ledger · no auto-heal · integrated E2E opt-in

## Next

Arranque auditor externo tip V1.95 ([arranque](./arranque-auditor-v1-95-beta-certification-2026-09-03.md)). Criterio **beta PAPER explotable** / BETA estable. **Sin** LIVE aún.
