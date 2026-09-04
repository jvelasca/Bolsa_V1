# RELEVO — V2.x Product UX (cabina Mercado) (2026-09-04)

> **Padre:** tip [`v2.0-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.0-beta) → [`e05fc6b0`](https://github.com/jvelasca/Bolsa_V1/commit/e05fc6b0) · [relevo V2.0 PAPER AUTO](./traspaso-relevo-v2-0-cierre-paper-auto-2026-09-04.md).  
> **Estado:** código en working tree (sin tip / sin bump) · ENGINE FREEZE intacto.  
> **Para quién:** siguiente agente UX / ops smoke con posición PAPER abierta.

## Objetivo

Transición de «motor PAPER AUTO robusto» a **producto usable**: Mercado como cabina; NEXT ACTION como héroe; jerga de motor en avanzado.

## Hecho (V2.01–V2.07)

| ID        | Entrega                                            | Evidencia                                                                                  |
| --------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| **V2.01** | Cabina Mercado · 4 respuestas · NEXT ACTION        | `operator-cabin-view.ts` · `operativa-cockpit-card.tsx` · `operator-cabin-ui.tsx`          |
| **V2.02** | Opportunity Card (ESPERAR TRIGGER / ENTRADA LISTA) | `decision-surface-compact.tsx` entry · copy sin COMPRAR                                    |
| **V2.03** | Position Card misión + Risk Box                    | `JourneyHudBlock` · checklist · `primaryAction` · vitest journey                           |
| **V2.04** | AUTO Desk en DECISIÓN                              | `auto-desk-panel.tsx` · Manual/Asistido/Automático · checklist · perfil ExitPolicy         |
| **V2.05** | Hoy 4 cubos                                        | `daily-desk.ts` · Requiere atención (absorbe Proteger) · menú «Avanzado»                   |
| **V2.06** | Asesor = explicación                               | copy `/research` · no segunda mesa                                                         |
| **V2.07** | Journal = memoria + learning strip                 | `decision-journal-page` framing · Evolución lee `decision_sessions` learning (SoT intacto) |

## Freeze intacto

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042).

## Criterio 10 s

Al seleccionar un valor: NEXT ACTION visible (también en vigilar/descubierto). Con plan: tesis / trigger / stop+riesgo / plan. Con posición: misión Entrada→Stop→T1→T2→Trailing + Risk Box.

## OUT / next

- Smoke browser con **posición PAPER abierta** (mission HUD real)
- V2.08 polish tipografía/a11y · V2.09 user test · colapso nav L1 (ADR-040) solo tras cabina estable
- Tip producto UX (cuando el usuario lo pida) — no confundir con tip motor V2.0

## Pre-flight

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/operator-cabin-view.test.ts src/cognitive/daily-desk.test.ts
cd apps/web && npx vitest run src/features/trading/operativa-cockpit-card.test.tsx src/features/trading/decision-surface-journey.test.tsx src/features/mesa/mesa-hoy-view.test.ts
```
