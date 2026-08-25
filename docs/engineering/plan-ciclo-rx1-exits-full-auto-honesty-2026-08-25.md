# Plan — Ciclo RX1 exits `full_auto` honesty (residual integridad, **sin thaw**)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §6 · [ADR-023](../adr/023-camino-d-thaw.md) (**Proposed**) · cierre I1–I3 [`traspaso-relevo-cierre-integridad-i1-i3-2026-08-25.md`](./traspaso-relevo-cierre-integridad-i1-i3-2026-08-25.md) · I3 [`plan-ciclo-i3-shadow-honesty-2026-08-25.md`](./plan-ciclo-i3-shadow-honesty-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO** (feat SHA en relevo). **No thaw.** **No** I4.
> **Método:** integridad thin (mismo espíritu que I3); Ranking ≠ BUY; Shadow **off**; sin broker; I1/I2/I3 intactos.
> **Nombre:** **RX1** = residual exits honesty — **no** «thaw I4».

---

## 0. Objetivo

I3 cerró HTTP `/route` + scan-execute para `paper_auto`. Quedaba un bypass interno: `POST /position-policies/evaluate-exits?executeTrades=true` → `EvaluatePositionExits` → `ExecutionRouter.execute` cuando position policy `mode=full_auto` + execution policy `paper_auto`.

**RX1 = fail-closed** ese camino con el mismo env que Paper D / I3. Eval-only (`executeTrades=false`) intacto. **No** producto auto-exit.

---

## 1. Decisiones (D1–D8 OK)

| Id  | Decisión                                                                                                                                  |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | **No thaw.** No `PAPER_D_EXECUTE=1`. ADR-023 sigue Proposed.                                                                              |
| D2  | `executeTrades=true` + `full_auto` + linked policy `paper_auto` → `require_http_paper_auto_env` antes del Router; HTTP 403. Eval-only OK. |
| D3  | Gate **antes** del Router (use-case) + map HTTP; **no** fusionar Router con Confirm/`allow_opening_fill`.                                 |
| D4  | **No** wire Exit Radar / TradePlan advisory → auto-exit. **No** inventar producto EvaluatePositionExits → spine.                          |
| D5  | Sin Alembic / `contract:gen` / broker / LLM.                                                                                              |
| D6  | `check_opening` intacto; sells/exits siguen fuera de opening basket.                                                                      |
| D7  | Pytest gate (mirror I3) + no romper integration position-policies.                                                                        |
| D8  | Plan + relevo + stamp CURRENT_SYSTEM / index. **No** push salvo decisión explícita.                                                       |

---

## 2. Arranque (hecho)

```text
Implementar Ciclo RX1 exits full_auto honesty según este plan.
D1=no thaw · D2=gate env antes de Router · D3=no fusionar Router · D4=no auto-exit product.
No PAPER_D_EXECUTE on · no broker · I1/I2/I3 intactos · no LLM.
```

---

## 3. Commits

| SHA      | Mensaje                                                             |
| -------- | ------------------------------------------------------------------- |
| _(feat)_ | `feat(spine): ADR-031 Ciclo RX1 exits full_auto honesty (no thaw).` |
| _(docs)_ | `docs: stamp living SoT after Ciclo RX1 (…)` — tras feat            |

## 4. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · advisory 5.x ≠ permiso · `PAPER_D_EXECUTE` off · I1/I2/I3 intactos · RX1 ≠ thaw.
