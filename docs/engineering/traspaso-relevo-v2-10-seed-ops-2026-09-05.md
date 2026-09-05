# RELEVO — V2.10 Seed Ops (birth estructural + Journal MFE·MAE) (2026-09-05)

> **Padre:** [relevo V2.9 Visual and Operational Certification](./traspaso-relevo-v2-9-visual-operational-certification-2026-09-05.md) · tip [`v2.10-beta`](./traspaso-relevo-tag-v2-10-beta-2026-09-05.md).  
> **Estado:** **CÓDIGO + OPS CERRADO** · tip [`v2.10-beta`](./traspaso-relevo-tag-v2-10-beta-2026-09-05.md) · package `1.39.0-beta`.  
> **Para quién:** seed ops cabina · **NO MÁS PANELES** · no reabrir motor FSM.  
> **Arranque:** [arranque V2.10](./arranque-agente-v2-10-2026-09-05.md) · **Runbook:** [seed cabin smoke](./runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md).

## Objetivo

Cerrar el hueco ops bloqueado desde v2.6 (birth protegido live **BLOCKED** · Journal ficha **N/A**) **sin** features de trading ni tip:

1. **V2.52** — Seed birth Confirm + `signedStop` estructural → `PROTECTED` / Planificado (≠ bootstrap −5 %).
2. **V2.53** — Seed/assert Journal study con `runtime.mfeMae` finito → ficha `journal-mfe-mae`.

## Freeze intacto

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · **AUTO sin controles de trading nuevos** · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty **intactos** · package `1.39.0-beta` · **no afirmar CI GREEN sin `conclusion=success`**.

**Arm ≠ Execute · Arm ≠ autorización de operación · Confirm = firma · Ranking ≠ BUY.**

## Entrega

| ID        | Entrega                                                                                  | Evidencia                                                                                        |
| --------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **V2.52** | `scripts/ops_seed_cabin_smoke.py` + wrapper `.mjs` · fixture flat + Confirm `signedStop` | smoke local **PASS** (cuenta `ops-v210-seed` / `c0f692cf…`) · `PROTECTED` · stop 9.7 ≠ floor 9.5 |
| **V2.53** | mismo script `journal-mfe-mae` · seed `mfeMae` en propose session                        | smoke local **PASS** · study AAF `mfeR=0.42` `maeR=-0.18`                                        |
| **Docs**  | este relevo · arranque · runbook · OUT V2.9                                              | index + CURRENT_SYSTEM                                                                           |

## Matriz de certificación (honestidad)

| Cubierto                                                       | Aproximación — no afirmar                                                   |
| -------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Birth vía Confirm + stop estructural (fixture OHLCV flat @ 10) | Que propose live `action=wait` abra sin seed BD                             |
| Journal MFE/MAE como foto de sesión en Tesis                   | Final R / life-peak PositionState · status siempre `closed`                 |
| Smoke local con wrapper Node + DATABASE_URL                    | CI GREEN / tip `v2.10-beta` (CI NO CERTIFICABLE · run `conclusion=failure`) |

## Smoke stamp (2026-09-05 local)

| Check                                                                                                   | Resultado                                                                                                                                                              |
| ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `node scripts/ops_seed_cabin_smoke.mjs birth-structural --apply --account-id c0f692cf67f941ae8529f145c` | **PASS** · Confirm executed · `operatingState=PROTECTED` · `currentStop=9.7`                                                                                           |
| `node scripts/ops_seed_cabin_smoke.mjs journal-mfe-mae --apply --account-id 516fc66a90ae40a0bdb83eecd`  | **PASS** · study con mfeR/maeR                                                                                                                                         |
| Tip / bump / Release-tag CI                                                                             | tip `v2.10-beta` + bump `1.39.0-beta` · CI [run 33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `conclusion=failure` · **NO CERTIFICABLE** |

Nota: cuenta `debug-opening` puede `risk_veto` por estado de recon/cesta; usar cuenta limpia (`ops-v210-seed`) para birth.

## Pre-flight

```bash
node scripts/ops_seed_cabin_smoke.mjs birth-structural --account-id <id>
node scripts/ops_seed_cabin_smoke.mjs birth-structural --apply --account-id <id>
node scripts/ops_seed_cabin_smoke.mjs journal-mfe-mae --apply --account-id <id>
```

## OUT / Next

- Tip [`v2.10-beta`](./traspaso-relevo-tag-v2-10-beta-2026-09-05.md) + bump `1.39.0-beta` — **autorizado**.
- Auditoría externa del conjunto tip `v2.10-beta` (V2.8 + V2.9 + V2.10).
- Release-tag CI **stampado** [run 33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `conclusion=failure` — **no GREEN**.
- No reabrir motor FSM / PAPER AUTO execute / paneles.
