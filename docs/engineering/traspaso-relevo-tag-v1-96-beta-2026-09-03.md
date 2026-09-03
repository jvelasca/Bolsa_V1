# RELEVO — tag v1.96-beta → auditoría tip (2026-09-03)

> **Padre:** [`traspaso-relevo-v1-96-final-beta-certification-2026-09-03.md`](./traspaso-relevo-v1-96-final-beta-certification-2026-09-03.md).  
> **Estado:** **CI GREEN** — tip `v1.96-beta` → `30479e97` · Release-tag CI **GREEN** ([run 33808076820](https://github.com/jvelasca/Bolsa_V1/actions/runs/33808076820)).  
> **Partida:** V1.95 tip [`6f262293`](https://github.com/jvelasca/Bolsa_V1/commit/6f262293) · [`respuesta-auditor-v195`](./respuesta-auditor-v195-beta-certification-2026-09-03.md).

## Release

| Pieza        | Valor                                                                                        |
| ------------ | -------------------------------------------------------------------------------------------- |
| Tag tip      | `v1.96-beta` → `30479e97`                                                                    |
| CI           | **GREEN** · [run 33808076820](https://github.com/jvelasca/Bolsa_V1/actions/runs/33808076820) |
| Pre-release  | https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.96-beta                                 |
| lifecycle-pg | success · **25 passed** (V1.88–V1.91/V1.95/V1.96 + worker + integrity)                       |

## Hecho certificado (código)

- Confirm SEMI `reduce`+`TARGET_2` → `T2_TRIGGERED` + `T2_EXECUTED` (puente compartido con AUTO)
- `reason_code` en payload outbox (drain remapea)
- Idempotencia T2 ≠ T1 (mismo `decisionId`)
- Golden HTTP V1.96 OPEN→T1→T2→EXIT→corrupt T2 ledger→OPEN DENY
- Golden V1.95 OPEN→T1→EXIT intacto

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no `queue_sequence` · no unificar ledger · no auto-heal · integrated E2E opt-in

## Next

Arranque auditor externo tip V1.96 ([arranque](./arranque-auditor-v1-96-final-beta-certification-2026-09-03.md)). Criterio **beta PAPER explotable** / BETA estable. **Sin** LIVE aún.
