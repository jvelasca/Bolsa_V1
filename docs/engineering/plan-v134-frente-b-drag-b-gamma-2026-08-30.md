# Plan — V1.34 Frente B Drag B-γ

> **Padre:** [`diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md`](./diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md) · estudio §8 **ACUERDO**.  
> **AsOf:** 2026-08-30.  
> **Estado:** **CERRADO (código + tests + docs).**

## Objetivo

Stop vigente arrastrable en gráfico (G3 ghost) con commit fail-closed a Confirm (`signedStop`) — B-γ. El gráfico no autoriza ni muta Position.

## Decisiones

| ID  | Decisión                                                                       |
| --- | ------------------------------------------------------------------------------ |
| D1  | Solo stop; entrada/T1/T2/trail fuera.                                          |
| D2  | Fases: preparada · posicion; nunca disparada.                                  |
| D3  | Commit = Confirm drawer + `signedStop`; cero protect API desde chart.          |
| D4  | Geometría = `validateOperationalLevels` / mismos blockReason.                  |
| D5  | Fuera Estudio / sin levels = G0.                                               |
| D6  | ≠ B-δ · ≠ OCO · ≠ flip execute · ≠ thaw · ≠ Radar AUTO.                        |
| D7  | Posición: encola protect con `suggestedStopOverride` + `allowPendingOverride`. |

## Kernel

```text
hit stop handle → ghost price → validate → (ok) open Confirm(signedStop)
```

## Archivos

- `chart-stop-drag-policy.ts` (+ test)
- `chart-stop-drag-commit.ts` (+ test)
- `chart-signed-stop-prefill.ts`
- `chart-operational-plan-levels-layer.tsx`
- `confirm-drawer.ts` · `supervised-f3-panel.tsx` · `propose-position-exit.ts`

## Freeze

Confirm = firma · AUTO execute env off · nav L1 · LLM no ejecuta · H2 kill asimétrico · B-δ no.
