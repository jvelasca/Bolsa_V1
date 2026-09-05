# ARRANQUE — post V2.44 / V2.8 código (2026-09-05)

> **Leer primero:** [relevo V2.8](./traspaso-relevo-v2-8-operator-certification-2026-09-05.md) · tip vigente [`v2.7-beta`](./traspaso-relevo-tag-v2-7-beta-2026-09-05.md) `8e7a5f95`.  
> **Para quién:** agente post-código V2.8 · **NO MÁS PANELES** · no tip/bump salvo pedido · no reabrir motor FSM.

## Estado

| Corte                             | Estado                                                      |
| --------------------------------- | ----------------------------------------------------------- |
| V2.7 Operator Hardening           | **cerrado** · tip `v2.7-beta`                               |
| V2.8 Operator Cabin Certification | **cerrado en código** · tip pendiente                       |
| V2.42 A3 cabin standard           | **hecho**                                                   |
| V2.43 AUTO ARM chrome             | **hecho**                                                   |
| V2.44 Cert 3 res + a11y           | **hecho** · `gp-e2e-v28`                                    |
| V2.45 CI verificable              | **hecho** · V2.7 = **FAILURE** documentado · fixes en árbol |
| Package `1.37.0-beta`             | vigente hasta tip `v2.8-beta`                               |

## Qué no reabrir

- Motor FSM / `TRANSITIONS` / PAPER AUTO execute
- V2.33–V2.44 salvo regresión **display-only**
- Paneles nuevos de Mercado
- Tip/bump sin pedido explícito

## Freeze (copiar al chat)

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles de trading nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty intactos · escalera T1→T2→trail · package `1.37.0-beta` · **no afirmar CI GREEN sin status checks del SHA**.

## Next (fuera de tip)

- **V2.7 tag CI = FAILURE** ([33929449228](https://github.com/jvelasca/Bolsa_V1/actions/runs/33929449228)) — no stamp GREEN
- Fixes CI en árbol V2.8 (shared tests · typecheck · mercado mocks e2e · `.gitleaks.toml`) — pendientes de commit/push
- Tras commit: `frontend-ci` en push + tip `v2.8-beta` / bump `1.38.0-beta` solo con pedido
- Ops walk browser (3 res · A3 · ARM · zoom · dark/light) — e2e mock v25/v28 **22/22 PASS** local
- Seed ops: stop estructural / Journal MFE·MAE (paralelo)

## Prompt sugerido

> Lee `docs/engineering/arranque-agente-post-v2-44-2026-09-05.md` y el relevo V2.8. Freeze intacto. NO MÁS PANELES. Solo regresión display-only, stamp CI GREEN si run success, o tip bajo pedido.
