# RELEVO — V1.32 SEMI paper maduro (2026-08-30)

> **AsOf:** 2026-08-30 · **Estado:** **CÓDIGO** — producto V1.32-beta, **sin tag todavía**.  
> **Padre:** [`traspaso-relevo-v1-31-ux-10-2026-08-30.md`](./traspaso-relevo-v1-31-ux-10-2026-08-30.md) · [`roadmap-v127-path-to-10-2026-08-28.md`](./roadmap-v127-path-to-10-2026-08-28.md).  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`. Tip incluye V1.27–V1.32 (código; sin commit/tag aún).

---

## 0. Qué cierra V1.32

**SEMI paper maduro** — entrada/salida **simétricas supervisadas** en el shell Confirm: ExitPlan + fuente EVENTO|MANUAL visibles; firma de tamaño de salida (`exit_risk_signature`); fence HTTP sell si hay PositionState. **No** drag · **no** AUTO · H2 kill switch intacto (SEMI derisk ALLOW).

| Pieza                                                                                       | Estado         |
| ------------------------------------------------------------------------------------------- | -------------- |
| Enqueue reduce/exit: `OperativaExitMetaV1` (plannedQty + ExitPlan + exitSource)             | CÓDIGO + tests |
| Confirm: `F3ExitPlanBlock` + `F3ExitRiskSignatureBlock`                                     | CÓDIGO         |
| `evaluateExitRiskSignature` / `evaluate_exit_risk_signature` (TS + PY)                      | CÓDIGO + tests |
| Confirm server: reject `exit_risk_signature`                                                | CÓDIGO + tests |
| HTTP `POST /portfolio/trade` sell + Position abierta → 403 `position_exit_requires_confirm` | CÓDIGO + tests |

**Archivos clave:** `exit-risk-signature.ts` · `exit_risk_signature.py` · `propose-position-exit.ts` · `f3-exit-plan-block.tsx` · `f3-exit-risk-signature-block.tsx` · `supervised-f3-panel.tsx` · `confirm_recommendation.py` · `execute_gated_portfolio_trade.py` · `identity.py` (`extract_operativa_exit_meta`).

**No** se tocó: drag · AUTO · Confirm bypass · nav L1 · thaw · OCO · trail autoridad · H2 kill asymmetry.

## 1. Freeze intacto

Confirm = firma · gráfico G0 · sin drag · AUTO off · `PAPER_D_EXECUTE` off · nav L1 congelada · LLM no ejecuta.

## 2. Next (un epic)

| Epic           | Qué                               | Fuera               |
| -------------- | --------------------------------- | ------------------- |
| **V1.33**      | AUTO A-β + gobernanza             | thaw estricto · A-γ |
| V1.31 residual | Tema claro · layouts · flash tick | Drag                |
| Frente B       | Drag B-γ                          | N4 + §8 ACUERDO     |

## 3. Arranque siguiente chat

1. Este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) + roadmap.
2. `pnpm --filter @bolsa/shared test -- src/cognitive/exit-risk-signature` · web `propose-position-exit` · py `test_confirm_exit_chain` + `test_execute_gated_portfolio_trade` + `test_exit_risk_signature`.
3. Smoke: CTA reduce con ExitPlan → Confirm muestra EVENTO + qty plan; subir qty sin override bloquea; sell HTTP con Position → 403.
4. No abrir drag / AUTO.
5. Deuda tag: `v1.27`…`v1.32` aún no publicados.
