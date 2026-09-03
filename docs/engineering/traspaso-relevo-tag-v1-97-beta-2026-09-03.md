# RELEVO — tag v1.97-beta → auditoría tip (2026-09-03)

> **Padre:** [`traspaso-relevo-v1-97-t2-transactional-atomicity-2026-09-03.md`](./traspaso-relevo-v1-97-t2-transactional-atomicity-2026-09-03.md).  
> **Estado:** tip `v1.97-beta` → `363dfcea` · Python CI **GREEN** ([run 33811212221](https://github.com/jvelasca/Bolsa_V1/actions/runs/33811212221)) · Release-tag CI al push del tip.  
> **Partida:** V1.96 tip [`30479e97`](https://github.com/jvelasca/Bolsa_V1/commit/30479e97) · [`respuesta-auditor-v196`](./respuesta-auditor-v196-final-beta-certification-2026-09-03.md).

## Release

| Pieza        | Valor                                                                                        |
| ------------ | -------------------------------------------------------------------------------------------- |
| Tag tip      | `v1.97-beta` → `363dfcea`                                                                    |
| Python CI    | **GREEN** · [run 33811212221](https://github.com/jvelasca/Bolsa_V1/actions/runs/33811212221) |
| Pre-release  | https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.97-beta                                 |
| lifecycle-pg | unit + PG store + worker T2 mid-pair (local PASS; Release-tag certifica)                     |

## Hecho certificado (código)

- `append_many` + un savepoint: `T2_TRIGGERED`+`T2_EXECUTED` atómicos
- `AppendLifecycleEvent` aplica el par desde `t1_executed` (SEMI/AUTO/outbox)
- Crash mid-pair → 0 orphan trigger → retry → 1+1
- Recovery `t2_ready` → solo `T2_EXECUTED`
- Sin Alembic nuevo (`019`)

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no `queue_sequence` · no unificar ledger · no auto-heal · integrated E2E opt-in

## Next

Arranque auditor externo tip V1.97 ([arranque](./arranque-auditor-v1-97-t2-transactional-atomicity-2026-09-03.md)). **Sin** LIVE. Después: Beta Stabilization.
