# Plan — V1.42 F8 PAPER AUTO

> **Padre:** [`spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md) §D F8 · [ADR-042](../adr/042-operating-excellence.md) · F7 [`plan-v142-f7-semi-2026-08-31.md`](./plan-v142-f7-semi-2026-08-31.md).  
> **AsOf:** 2026-08-31.  
> **Estado:** **CÓDIGO** (2026-08-31).

## Objetivo

Productizar PAPER AUTO: mismos objetos que SEMI (Entry/POT/ExecutionState, ExecutionRouter `paper_auto`, demo-book prefs / auto-arm); la ruta se distingue solo por **omitir firma humana**. Sin thaw estricto. LIVE broker frozen. `PAPER_D_EXECUTE` sigue **opt-in env** (default off); arm ≠ execute.

```text
SEMI:  IA → Risk → Policy → Humano confirma → Execution
AUTO:  IA → Risk → Policy → Execution   (same objects; omit human Confirm)
```

## Entregables

| ID  | Entrega                                                                   | Estado |
| --- | ------------------------------------------------------------------------- | ------ |
| F8  | Shared `buildPaperAutoPosture` (SEMI vs AUTO · arm ≠ execute)             | CÓDIGO |
| F8  | Mesa header modeLabel/modeDetail desde posture (no hardcode SEMI)         | CÓDIGO |
| F8  | Entry copy/CTA: AUTO omite «Revisar y confirmar»; env off → ejecución off | CÓDIGO |
| F8  | Demo-book: enqueue Confirm solo SEMI; badge «AUTO armado · ejecución off» | CÓDIGO |
| F8  | Cockpit DECISIÓN: sin Confirm CTA en AUTO; posture badge                  | CÓDIGO |
| F8  | vitest shared + web · `tsc` web                                           | CÓDIGO |
| F8  | Docs plan + relevo · stamp CURRENT_SYSTEM / spec §D / ADR-042             | CÓDIGO |

## Freeze intacto

Confirm semantics SEMI · Router money path · `PAPER_D_EXECUTE` default **off** · sin LIVE thaw · sin Accept 60d/50/70/55 · `protect_hint` ≠ autoridad · sin OCO · sin Lab P2 · sin trail auto-authority · sin bump `package.json` · Ranking ≠ BUY.

## Honestidad de alcance

| Capacidad                                         | Estado F8                               |
| ------------------------------------------------- | --------------------------------------- |
| UI posture AUTO vs SEMI (sin fingir LIVE)         | CÓDIGO                                  |
| Arm ≠ execute (`PAPER_D_EXECUTE=0` → clear badge) | CÓDIGO                                  |
| Spine AUTO = SEMI minus Confirm                   | CÓDIGO (copy + gates UI)                |
| Fill paper_auto vía Router cuando env on          | **Existente** (I3 gate); no nuevo motor |
| Trail hint → auto PositionRevision                | **Parked** (hint nunca auto-promueve)   |
| Thaw estricto / LIVE Camino D                     | **Parked / freeze**                     |

## Criterios de cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/paper-auto-posture.test.ts src/cognitive/entry-operating-copy.test.ts src/cognitive/mesa-next-action.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/demo-book-prefs.test.ts src/features/trading/demo-book-auto-copy.test.ts src/features/trading/demo-book-mode-panel.test.tsx src/features/trading/semi-demo-operativa.test.ts src/features/trading/operativa-cockpit-card.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
```
