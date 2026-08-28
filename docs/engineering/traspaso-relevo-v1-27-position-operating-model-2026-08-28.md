# RELEVO — V1.27 Position Operating Model (2026-08-28)

> **AsOf:** 2026-08-28 · **Estado:** **CÓDIGO** — producto V1.27-beta, **sin tag todavía**.  
> **Padre:** [`traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md`](./traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md) · [`roadmap-v127-path-to-10-2026-08-28.md`](./roadmap-v127-path-to-10-2026-08-28.md).  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`.

---

## 0. Qué cierra V1.27

| Pieza                                                             | Estado                  |
| ----------------------------------------------------------------- | ----------------------- |
| `ExitPolicy` en plantillas conservative/moderate/aggressive_swing | CÓDIGO + tests paridad  |
| `PositionDecision` proyección (no tabla)                          | CÓDIGO + tests TS/PY    |
| Evento ≠ decisión (T1 + aggressive = HOLD)                        | CÓDIGO + tests          |
| `target2AchievedAt` (H2 T2 tocado ≠ gestionado)                   | CÓDIGO                  |
| GOLDEN-PATH-01 entrada→protect→T1→exit→recon                      | CÓDIGO                  |
| GOLDEN-PATH-FAIL geometría / drift / tesis                        | CÓDIGO                  |
| Recon CLEAN/ATTENTION/CRITICAL → chip Operativa                   | CÓDIGO                  |
| Lab `risk_policy` desde TradingPolicy Moderado                    | CÓDIGO (`backtests.py`) |

**No** se duplica ExitPlan / ExitPermission / PositionStatus durable.

## 1. Freeze intacto

Confirm = firma · gráfico G0 · sin drag · AUTO off · `PAPER_D_EXECUTE` off · nav L1 congelada · LLM no ejecuta.

Estudio AUTO+gráfico §8 **Aplazado** (N4 pendiente). **No** `diseno-operativa-auto-grafico-ACORDADO-*`.

## 2. Next (un epic)

| Epic      | Qué                                                              | Fuera                 |
| --------- | ---------------------------------------------------------------- | --------------------- |
| **V1.28** | Daily cockpit + toasts DISPARADA/T1 (B-α, G2) en shell existente | Drag · nav nueva      |
| Frente B  | Drag B-γ                                                         | Hasta N4 + §8 ACUERDO |
| Frente A  | AUTO A-β                                                         | V1.33; A-γ rechazada  |

## 3. Arranque siguiente chat

1. Este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) + roadmap path-to-10.
2. `pnpm --filter @bolsa/shared test` (**430**) · `pnpm test:decision-spine` (**530**, incluye `test_v127_golden_path.py` + FAIL).
3. No abrir drag / AUTO.
