# RELEVO — Ciclo RX1 exits `full_auto` honesty (residual integridad, **sin thaw**)

> **Padre:** [`traspaso-relevo-cierre-integridad-i1-i3-2026-08-25.md`](./traspaso-relevo-cierre-integridad-i1-i3-2026-08-25.md).
> **Plan:** [`plan-ciclo-rx1-exits-full-auto-honesty-2026-08-25.md`](./plan-ciclo-rx1-exits-full-auto-honesty-2026-08-25.md) (D1–D8 OK).
> **AsOf:** 2026-08-25.
> **HEAD origin:** `05e354c`. Feat RX1 **`9289b53`** (local, no push).
> **Estado:** **CERRADO en `9289b53`.** Residual I3 D4 park → honesty. **No** thaw · **no** I4 · **no** auto-exit producto.
> **Fase:** **integridad residual**. **No** flip `PAPER_D_EXECUTE`.

---

## 0. Contexto

**I1–I3 CERRADOS.** I3 gated HTTP `paper_auto` en `/route` + scan-execute. `EvaluatePositionExits` con `executeTrades=true` + `full_auto` llamaba al Router **internamente** y podía saltarse ese gate.

## 1. Qué se cerró (RX1)

| Pieza     | Qué                                                                                                   |
| --------- | ----------------------------------------------------------------------------------------------------- |
| Use-case  | Antes de `ExecutionRouter.execute`: carga execution policy → `require_http_paper_auto_env` (reuso I3) |
| HTTP      | `POST /position-policies/evaluate-exits` → 403 `paper_auto_env_blocked` si el path execute lo dispara |
| Eval-only | `executeTrades=false` → signal status only; **sin** gate                                              |
| Skip      | Linked policy `inform_only` / `alert` / `live_auto` no pasan el env gate                              |

**Sin** thaw · **sin** fusionar Router · **sin** Exit Radar → auto-exit · **sin** Alembic / `contract:gen` · `check_opening` intacto.

## 2. Batería

- pytest `test_paper_auto_http_gate` + `test_position_exits_paper_auto_gate` + `test_paper_d_propose` + `test_position_policies` → **13 passed**
- integration `test_position_policies_flow` → **2 passed**
- `pnpm test:decision-spine` **no** tocada

## 3. Commits

| SHA       | Mensaje                                                           |
| --------- | ----------------------------------------------------------------- |
| `9289b53` | feat(spine): ADR-031 Ciclo RX1 exits full_auto honesty (no thaw). |
| _(docs)_  | stamp SoT                                                         |

**No push** salvo decisión explícita.

## 4. E1

1. ~~Feat RX1~~ · ~~stamp~~ · push (decisión explícita).
2. Thaw solo con «thaw» + ADR-023 / checklist.
3. Crecimiento 5.x (expectancy / trail / bracket) solo si se nombra.
4. **No** abrir auto-exit producto por inercia.

## 5. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · `PAPER_D_EXECUTE` off · I1/I2/I3 intactos · RX1 ≠ thaw · advisory 5.x ≠ permiso.
