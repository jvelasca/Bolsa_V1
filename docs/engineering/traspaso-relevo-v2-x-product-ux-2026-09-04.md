# RELEVO — V2.x Product UX (cabina Mercado) (2026-09-04)

> **Padre:** tip [`v2.0-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.0-beta) → [`e05fc6b0`](https://github.com/jvelasca/Bolsa_V1/commit/e05fc6b0) · [relevo V2.0 PAPER AUTO](./traspaso-relevo-v2-0-cierre-paper-auto-2026-09-04.md).  
> **Estado:** código tip local [`a39595ce`](https://github.com/jvelasca/Bolsa_V1/commit/a39595ce) (sin tag / sin bump) · ENGINE FREEZE intacto.  
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

## Ops local (post-commit)

| Check                        | Resultado                                                                        |
| ---------------------------- | -------------------------------------------------------------------------------- |
| Commit                       | `a39595ce` · `feat(v2.x): Mercado operator cabin with NEXT ACTION and AUTO Desk` |
| Smoke `/trading` NEXT ACTION | **OK** — `CANDIDATO` / AUTO Desk en DECISIÓN                                     |
| Smoke Position Card (misión) | **PARTIAL** — cuenta PRINCIPAL sin posiciones PAPER abiertas (0)                 |

## OUT / next

- Smoke browser con **posición PAPER abierta** (mission HUD real)
- Push / tip producto UX (cuando el usuario lo pida) — no confundir con tip motor V2.0
- V2.08 polish tipografía/a11y · V2.09 user test · colapso nav L1 (ADR-040) solo tras cabina estable

## Pre-flight

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/operator-cabin-view.test.ts src/cognitive/daily-desk.test.ts
cd apps/web && npx vitest run src/features/trading/operativa-cockpit-card.test.tsx src/features/trading/decision-surface-journey.test.tsx src/features/mesa/mesa-hoy-view.test.ts
```
