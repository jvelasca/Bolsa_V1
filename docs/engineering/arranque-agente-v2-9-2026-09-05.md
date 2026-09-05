# ARRANQUE — V2.9 Visual and Operational Certification (2026-09-05)

> **Relevo:** [V2.9 Visual and Operational Certification](./traspaso-relevo-v2-9-visual-operational-certification-2026-09-05.md).  
> **Tip producto vigente:** [`v2.10-beta`](./traspaso-relevo-tag-v2-10-beta-2026-09-05.md) / package `1.39.0-beta`.  
> **Para quién:** agente · **NO MÁS PANELES** · no tip/bump salvo pedido · no reabrir motor FSM.

## Estado

| Corte                             | Estado                                                                                                                      |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| V2.8 Operator Cabin Certification | **cerrado** · tip `v2.8-beta`                                                                                               |
| V2.46–V2.51                       | **hecho** (código)                                                                                                          |
| Tip `v2.9-beta`                   | **no** (incluido en `v2.10-beta`)                                                                                           |
| CI GREEN V2.10                    | **NO CERTIFICABLE** · [run 33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `conclusion=failure` |

## Qué no reabrir

- Motor FSM / `TRANSITIONS` / PAPER AUTO execute / `RecoverOrphanOpeningFills.recover()` algorithm
- Paneles nuevos de Mercado
- Tip/bump sin pedido explícito
- Ampliar `.gitleaks.toml`

## Freeze (copiar al chat)

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles de trading nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty intactos · escalera T1→T2→trail · package `1.39.0-beta` · **no afirmar CI GREEN sin status checks del SHA**.

## Next

- Seed ops: stop estructural / Journal MFE·MAE → **cerrado en V2.10** ([relevo](./traspaso-relevo-v2-10-seed-ops-2026-09-05.md))
- Tip [`v2.10-beta`](./traspaso-relevo-tag-v2-10-beta-2026-09-05.md) · [arranque post-tip](./arranque-agente-post-tip-v2-10-2026-09-05.md)
- Release-tag CI **stampado** [run 33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `conclusion=failure` — **no GREEN**
