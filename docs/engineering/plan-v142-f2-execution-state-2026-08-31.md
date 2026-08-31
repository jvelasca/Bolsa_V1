# Plan — V1.42 F2 ExecutionState

> **Padre:** [`spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md) §A.4 · [ADR-042](../adr/042-operating-excellence.md).  
> **AsOf:** 2026-08-31.  
> **Estado:** **CERRADO** (2026-08-31).

## Objetivo

Proyección canónica `ExecutionState` (no motor, no tabla) que responde: ¿hay orden? ¿pendiente? ¿parcial? ¿UNKNOWN? ¿conciliada? Mismo objeto en Mercado / Hoy / Journal / Operaciones.

## Entregables

| ID  | Entrega                                                                  | Estado          |
| --- | ------------------------------------------------------------------------ | --------------- |
| F2  | `execution-state.ts` — tipos §A.4 + `buildExecutionState` + precedencia  | CÓDIGO + vitest |
| F2  | `isOrderInFlight` · `formatExecutionStateCopy` · surface snapshot        | CÓDIGO          |
| F2  | GP-03 / GP-04 / GP-10 + same-across-surfaces + honesty 19a/19b           | CÓDIGO          |
| F2  | Thin wire: summaries + Mesa fila + Operaciones + Journal ficha + cockpit | CÓDIGO          |

## Precedencia (congelada en código)

1. Fill confirmado gana a intent stale
2. UNKNOWN (paper / record / send_attempted|venue_bound) gana a «parece pending»
3. PARTIAL · REJECTED/CANCELLED/EXPIRED · intent `recorded`→submit · Paper SUBMITTED/ACK · pending_orders · none
4. `orderReconciled` → lifecycle `reconciled`
5. Trailing hint ≠ applied (GP-A7)

## Freeze intacto

Confirm = firma · Spine · `PAPER_D_EXECUTE` off · AUTO execute off · sin `GET /submit-intents` · sin tocar Confirm / Router money path · sin PositionOperatingTruth / TradeStory / Mercado 2.0 / Hoy 2.0 · Ranking ≠ BUY · una CTA · hint trail ≠ `currentStop`.

## Explicitamente fuera (F2b / F3+)

| Tag   | Nombre                          | Notas                                               |
| ----- | ------------------------------- | --------------------------------------------------- |
| F2b   | List in-flight submit_intents   | Read-only; Mercado no descubre UNKNOWN huérfano hoy |
| F3    | PositionOperatingTruth + §A.8   | Compone OperationalTruth                            |
| F4–F8 | TradeStory → Mercado/Hoy → AUTO | Spec §D                                             |

## Criterios de cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/execution-state.test.ts src/cognitive/execution-state-golden-path.test.ts src/cognitive/same-execution-state-across-surfaces.test.ts src/cognitive/operational-honesty-scenarios.test.ts src/cognitive/same-operational-truth-across-surfaces.test.ts src/cognitive/same-entry-operating-truth-across-surfaces.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/position-operating-summary.test.tsx src/features/trading/entry-operating-summary.test.tsx src/features/trading/operativa-cockpit-card.test.tsx src/features/decision-journal/decision-ficha-panel.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```

Backend pytest **no** forma parte del DoD (money path intocado).
