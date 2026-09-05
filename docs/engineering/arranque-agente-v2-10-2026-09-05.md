# ARRANQUE — V2.10 Seed Ops (2026-09-05)

> **Relevo:** [V2.10 Seed Ops](./traspaso-relevo-v2-10-seed-ops-2026-09-05.md) · [runbook](./runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md).  
> **Tip producto vigente:** [`v2.8-beta`](./traspaso-relevo-tag-v2-8-beta-2026-09-05.md) `a9ec6424` / package `1.38.0-beta`.  
> **Para quién:** agente · **NO MÁS PANELES** · no tip/bump salvo pedido · no reabrir motor FSM.

## Estado

| Corte                             | Estado                                                 |
| --------------------------------- | ------------------------------------------------------ |
| V2.8 Operator Cabin Certification | **cerrado** · tip `v2.8-beta`                          |
| V2.9 Visual/Operational (código)  | **hecho** · **sin tip**                                |
| V2.52–V2.53 Seed Ops              | **hecho** · smoke local PASS                           |
| Tip `v2.9` / `v2.10`              | **pendiente** autorización                             |
| CI GREEN V2.9+                    | **NO CERTIFICABLE** hasta run con `conclusion=success` |

## Qué no reabrir

- Motor FSM / `TRANSITIONS` / PAPER AUTO execute / `RecoverOrphanOpeningFills.recover()` algorithm
- Paneles nuevos de Mercado
- Tip/bump sin pedido explícito
- Ampliar `.gitleaks.toml`

## Freeze (copiar al chat)

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles de trading nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty intactos · escalera T1→T2→trail · package `1.38.0-beta` · **no afirmar CI GREEN sin status checks del SHA**.

## Next

- Auditoría externa (usuario) del conjunto tip V2.8 + código V2.9 + seeds V2.10
- Tip/bump solo bajo pedido
- Dispatch Release-tag CI → stamp URL + conclusion (o NO CERTIFICABLE)
