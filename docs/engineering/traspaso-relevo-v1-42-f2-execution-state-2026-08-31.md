# RELEVO — V1.42 F2 ExecutionState (2026-08-31)

> **Padre:** [`plan-v142-f2-execution-state-2026-08-31.md`](./plan-v142-f2-execution-state-2026-08-31.md) · [`spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CERRADO** — proyección canónica de ciclo de orden; GP-03/04/10 en shared; thin wire UI.  
> **No tag** en este slice (código en tip; release-tag cuando el owner lo pida).

---

## 0. Qué cierra F2

No motor nuevo. No tabla. Compone hechos existentes → `ExecutionState`.

| Pieza                                                                              | Estado          |
| ---------------------------------------------------------------------------------- | --------------- |
| `packages/shared/src/cognitive/execution-state.ts`                                 | CÓDIGO + vitest |
| GP-03 pending · GP-04 partial · GP-10 UNKNOWN→reconcile (mismos ids, 0 re-POST UX) | CÓDIGO          |
| `same-execution-state-across-surfaces`                                             | CÓDIGO          |
| Honesty 19a/19b (parcial / REJECTED); 19c mercado cerrado parked                   | CÓDIGO / todo   |
| Thin wire: Position/Entry summary · Mesa fila · Operaciones · Journal · cockpit    | CÓDIGO          |

**Regla:** mismos hechos → mismo `lifecycle` / `orderState` / copy en Mercado / Hoy / Journal / Operaciones. UNKNOWN → «Ver operaciones» · **nunca reenviar**. Trailing hint ≠ applied.

## 1. Pre-flight cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/execution-state.test.ts src/cognitive/execution-state-golden-path.test.ts src/cognitive/same-execution-state-across-surfaces.test.ts src/cognitive/operational-honesty-scenarios.test.ts src/cognitive/same-operational-truth-across-surfaces.test.ts src/cognitive/same-entry-operating-truth-across-surfaces.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/position-operating-summary.test.tsx src/features/trading/entry-operating-summary.test.tsx src/features/trading/operativa-cockpit-card.test.tsx src/features/decision-journal/decision-ficha-panel.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```

Backend operativo **intocado** (Confirm · Router · `PAPER_D_EXECUTE`).

## 2. Freeze

Confirm = firma · Spine · `PAPER_D_EXECUTE` off · AUTO execute off · `protect_hint` thin ≠ autoridad · sin drag entry/exit · sin thaw LIVE.

## 3. Honestidad de alcance

| Capacidad                                             | Estado F2                                              |
| ----------------------------------------------------- | ------------------------------------------------------ |
| pending_orders → `in_flight`/`pending`                | CÓDIGO (germen UI)                                     |
| PaperOrder PARTIAL/REJECTED/UNKNOWN cuando hay hechos | CÓDIGO (Confirm/F3/tests)                              |
| Mercado descubre intents huérfanos post-crash         | **No** — falta F2b `GET` list submit_intents           |
| Paper D AUTO fill en proyección sin caller            | Hecho opcional `paper_auto_ledger`; no cableado Router |
| PositionOperatingTruth / TradeStory / Mercado 2.0     | Parked F3+                                             |

## 4. Next (hoja, no implementar aquí)

| Tag | Nombre                              | Notas                                               |
| --- | ----------------------------------- | --------------------------------------------------- |
| F2b | SubmitIntent read list              | Solo si owner quiere UNKNOWN en Mercado sin Confirm |
| F3  | PositionOperatingTruth              | + prioridad CTA §A.8                                |
| F4  | TradeStory                          | Journal consume                                     |
| F5+ | Mercado/Hoy 2.0 → SEMI → PAPER AUTO | Spec §D; sin thaw estricto                          |

Fuera: P2 Lab · móvil · push · thaw · OCO · OpportunityScore · segundo Mercado · motores nuevos.
