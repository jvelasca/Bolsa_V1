# ARRANQUE — post tip v2.8-beta (2026-09-05)

> **Leer primero:** [relevo tag v2.8-beta](./traspaso-relevo-tag-v2-8-beta-2026-09-05.md) · [relevo V2.8](./traspaso-relevo-v2-8-operator-certification-2026-09-05.md).  
> **Tip producto vigente:** [`v2.8-beta`](./traspaso-relevo-tag-v2-8-beta-2026-09-05.md) / package `1.38.0-beta`.  
> **Para quién:** agente post-tip · **NO MÁS PANELES** · no tip/bump salvo pedido · no reabrir motor FSM.

## Estado

| Corte                             | Estado                        |
| --------------------------------- | ----------------------------- |
| V2.8 Operator Cabin Certification | **cerrado** · tip `v2.8-beta` |
| V2.42–V2.45                       | **hecho**                     |
| Package `1.38.0-beta`             | **bump** tip                  |

## Qué no reabrir

- Motor FSM / `TRANSITIONS` / PAPER AUTO execute
- V2.33–V2.45 salvo regresión **display-only**
- Paneles nuevos de Mercado
- Tip/bump sin pedido explícito

## Freeze (copiar al chat)

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles de trading nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty intactos · escalera T1→T2→trail · package `1.38.0-beta` · **no afirmar CI GREEN sin status checks del SHA tip**.

## Next (fuera de tip)

- Confirmar Release-tag CI del tag `v2.8-beta` → stamp GREEN solo si success
- Seed ops: stop estructural / Journal MFE·MAE (paralelo)
- Auditoría walk live post-tip (opcional; e2e mock ya PASS)

## Prompt sugerido

> Lee `docs/engineering/arranque-agente-post-v2-44-2026-09-05.md` o el relevo tag v2.8-beta. Freeze intacto. NO MÁS PANELES. Solo regresión display-only o seed ops bajo pedido. No tip/bump.
