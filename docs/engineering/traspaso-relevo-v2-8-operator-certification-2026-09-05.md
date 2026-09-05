# RELEVO — V2.8 Operator Cabin Certification (2026-09-05)

> **Padre:** [relevo V2.7 Operator Hardening](./traspaso-relevo-v2-7-operator-hardening-2026-09-05.md) · tip [`v2.7-beta`](./traspaso-relevo-tag-v2-7-beta-2026-09-05.md) `8e7a5f95`.  
> **Estado:** **CERRADO** · tip [`v2.8-beta`](./traspaso-relevo-tag-v2-8-beta-2026-09-05.md) · package `1.38.0-beta`.  
> **Para quién:** certificación cabina (A3 · ARM semántico · touch · a11y · CI) · **NO MÁS PANELES** · no reabrir motor FSM.  
> **Arranque:** [arranque V2.8 / V2.42](./arranque-agente-v2-8-2026-09-05.md) · **post-código:** [arranque post-V2.44](./arranque-agente-post-v2-44-2026-09-05.md) · **post-tip:** [arranque post-tip v2.8](./arranque-agente-post-tip-v2-8-2026-09-05.md).  
> **Veredicto auditor V2.7:** PASS conceptual · 9,8/10 · 0 P0 · 0 P1 · 5 P2 de certificación (no features).

## Objetivo

V2.7 cerró Operator Hardening (arm honesty · touch · cert visual).  
V2.8 **no añade funcionalidad de trading** ni paneles. Cierra deuda P2 de la auditoría:

1. **V2.42** — A3 al estándar táctil/visual de cabina (`CABIN_TOUCH_TARGET`). ✅
2. **V2.43** — Chrome inequívoco AUTO DESARMADO / ARMADO + EJECUCIÓN PAPER; ARM ≠ autorización de operación. ✅
3. **V2.44** — Certificación real 1920 / 1366 / 1024 + teclado / ratón / touch / zoom / overflow / focus / dark-light. ✅
4. **V2.45** — CI GitHub verificable (dispatch V2.7 + honesty docs). ✅ (run registrado; **no** afirmar GREEN sin resultado)

Nombre distingue de [V2.2 Operator Certification](./traspaso-relevo-v2-2-operator-certification-2026-09-04.md) (Operating Truth / golden journeys). Aquí el objeto es la **cabina**.

## Freeze intacto

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · **AUTO sin controles de trading nuevos** · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty **intactos** · package `1.38.0-beta` · **no afirmar CI GREEN sin status checks del SHA**.

**Arm ≠ Execute · Arm ≠ autorización de operación · Confirm = firma · Ranking ≠ BUY.**

## Entrega

| ID        | P2 auditor | Entrega                                                               | Evidencia                                              |
| --------- | ---------- | --------------------------------------------------------------------- | ------------------------------------------------------ |
| **V2.42** | P2.1       | A3 cabin standard (`CABIN_TOUCH_TARGET` + `CABIN_TYPE` + focus)       | `demo-book-auto-arm-form` · vitest auto-desk · e2e v25 |
| **V2.43** | P2.2+P2.3  | AUTO ARM chrome (DESARMADO/ARMADO · EJECUCIÓN PAPER · permiso ≠ auth) | `paper-auto-posture` · `auto-desk-arm-state` · vitest  |
| **V2.44** | P2.5       | Cert 3 res + a11y                                                     | `gp-e2e-v28-cabin-cert-mock.spec.ts`                   |
| **V2.45** | P2.4       | CI verificable                                                        | runs abajo · filtro `gp-e2e` incluye v28               |

## V2.45 — CI honesty

| Pieza    | Valor                                                                                                     |
| -------- | --------------------------------------------------------------------------------------------------------- |
| Tip V2.7 | `v2.7-beta` → `8e7a5f95` · feat `5ec02e67`                                                                |
| Dispatch | [run 33929449228](https://github.com/jvelasca/Bolsa_V1/actions/runs/33929449228) · **failure** (no GREEN) |
| Push tag | [run 33928787528](https://github.com/jvelasca/Bolsa_V1/actions/runs/33928787528) · **cancelled**          |
| Stamp    | **V2.7 tag CI ≠ GREEN** — no mentir                                                                       |

### Fallos tip V2.7 (diagnóstico) + fixes en árbol V2.8

| Job                 | Causa                                                            | Fix V2.8 (código local)                            |
| ------------------- | ---------------------------------------------------------------- | -------------------------------------------------- |
| shared              | 3 tests: buckets 5→4 · protect kind Planificado · phrase honesty | tests alineados V2.05/V2.33                        |
| frontend            | `ChartPlanContextStrip` sin `instrumentId` · `view.t1`/`t2` null | typecheck OK                                       |
| playwright-mock     | `gp-e2e-v25` sin `installMercadoApiMocks` → cockpit ausente      | mercado mocks en v25/v26/v28                       |
| security (gitleaks) | false positives `generic-api-key` en storage keys                | [`.gitleaks.toml`](../../.gitleaks.toml) allowlist |

**Siguiente verificación CI:** push/commit de estos fixes + `gh workflow run "Release tag CI"` sobre el SHA / tip V2.8 — **no** re-dispatch solo sobre `v2.7-beta` (sigue fallando sin estos patches).

Filtro Playwright mock: `gp-e2e\|…` → incluye `gp-e2e-v25` / `v26` / **`v28`**.

## Pre-flight local

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/paper-auto-posture.test.ts src/cognitive/operator-cabin-view.test.ts
cd apps/web && npx vitest run src/features/trading/auto-desk-panel.test.tsx src/features/trading/demo-book-mode-panel.test.tsx src/features/trading/demo-book-auto-arm.test.ts src/features/trading/cabin-visual.test.ts
```

shared posture + cabin **PASS** · web A3/AUTO **18/18 PASS**.

## OUT / Next

- Tip [`v2.8-beta`](./traspaso-relevo-tag-v2-8-beta-2026-09-05.md) + bump `1.38.0-beta` — stamp en relevo tag.
- Release-tag CI sobre tip — GREEN solo con success.
- Ops walk browser opcional (e2e mock v25+v28 **22/22 PASS** local).
- No reabrir motor FSM / PAPER AUTO execute.
- Seed ops (stop estructural / Journal MFE·MAE) paralelo.
