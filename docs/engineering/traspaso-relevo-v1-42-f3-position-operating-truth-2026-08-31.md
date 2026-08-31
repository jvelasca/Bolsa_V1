# RELEVO — V1.42 F3 PositionOperatingTruth (2026-08-31)

> **Padre:** [`plan-v142-f3-position-operating-truth-2026-08-31.md`](./plan-v142-f3-position-operating-truth-2026-08-31.md) · [`spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CERRADO** — POT + §A.8; thin wire UI.  
> **No tag** en este slice (código en tip; release-tag cuando el owner lo pida).

---

## 0. Qué cierra F3

| Pieza                                                                       | Estado          |
| --------------------------------------------------------------------------- | --------------- |
| `mapMesaNextAction` — `full_exit`/`reduce` antes de `protectionDiscrepancy` | CÓDIGO          |
| `packages/shared/src/cognitive/position-operating-truth.ts`                 | CÓDIGO + vitest |
| GP-05…09 golden · same-across-surfaces                                      | CÓDIGO          |
| Thin wire: Position summary · Mesa · Operaciones · cockpit · Journal        | CÓDIGO          |

**Regla:** wire `exitPlan` full_exit/reduce gana CTA (paridad Mesa); REVIEW recon gana; discrepancia secundaria bajo exit/reduce. Trail hint ≠ applied.

## 1. Freeze

Confirm = firma · Spine · `PAPER_D_EXECUTE` off · AUTO execute off · sin F4/F5+.

## 2. Next (hoja, no implementar aquí)

| Tag   | Nombre               | Notas             |
| ----- | -------------------- | ----------------- |
| F4    | TradeStory           | Journal consume   |
| F5    | Mercado 2.0 DECISIÓN | Spec §B           |
| F6    | Hoy 2.0 cubos        | Spec §B.7         |
| F7–F8 | SEMI → PAPER AUTO    | Sin thaw estricto |

## 3. Pre-flight

Ver plan F3 §criterios.
