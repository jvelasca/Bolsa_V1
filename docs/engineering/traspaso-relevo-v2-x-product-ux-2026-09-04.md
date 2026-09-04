# RELEVO — V2.x Product UX (cabina Mercado) (2026-09-04)

> **Padre:** tip [`v2.0-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.0-beta) → [`e05fc6b0`](https://github.com/jvelasca/Bolsa_V1/commit/e05fc6b0) · [relevo V2.0 PAPER AUTO](./traspaso-relevo-v2-0-cierre-paper-auto-2026-09-04.md).  
> **Estado:** código tip local [`a39595ce`](https://github.com/jvelasca/Bolsa_V1/commit/a39595ce) (sin tag / sin bump) · ENGINE FREEZE intacto.  
> **Smoke browser (2026-09-04):** Position Card + protect **OK** (ver Ops local).  
> **Para quién:** polish V2.08 / CTA Proteger `OPEN_UNPROTECTED` / tip producto cuando se pida.

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

| Check                        | Resultado                                                                                                                            |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Commit                       | `a39595ce` · `feat(v2.x): Mercado operator cabin with NEXT ACTION and AUTO Desk`                                                     |
| Docs stamp PARTIAL           | `3a71f47f` · smoke Position Card pendiente de posición                                                                               |
| Smoke `/trading` NEXT ACTION | **OK** — `CANDIDATO` / AUTO Desk en DECISIÓN                                                                                         |
| Smoke Position Card (misión) | **OK** — PRINCIPAL · BBVA 1× @ 25.40 · DECISIÓN `MANTENER` · misión Entrada✓ · Risk Box · AUTO Desk Asistido                         |
| Smoke protect (Confirm SEMI) | **OK** — stop operativo **24.00** · `trade=protect_applied` · API `PROTECTED` / `MONITOR` · Hoy PROTECCIÓN **1/1** · ruta Stop 24.00 |

### Hallazgo UX (no bloquea stamp)

Compra de mercado → plan `manual-*` + `OPEN_UNPROTECTED`, pero **sin CTA «Proteger»** en DECISIÓN hasta `protect_hint` / ExitPlan `protect`. Firma de stop vía cola Confirm (SEMI). Orden VENTA con posición abierta → `position_exit_requires_confirm` (esperado). Candidato V2.08: CTA Proteger secundaria cuando `operatingState=OPEN_UNPROTECTED` y hay `tradePlanId`.

## OUT / next

- ~~Smoke browser con posición PAPER abierta~~ **hecho 2026-09-04**
- V2.08: CTA Proteger para `OPEN_UNPROTECTED` (hallazgo arriba) · polish tipografía/a11y
- V2.09 user test · colapso nav L1 (ADR-040) solo tras cabina estable
- Push / tip producto UX (cuando el usuario lo pida) — no confundir con tip motor V2.0

## Pre-flight

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/operator-cabin-view.test.ts src/cognitive/daily-desk.test.ts
cd apps/web && npx vitest run src/features/trading/operativa-cockpit-card.test.tsx src/features/trading/decision-surface-journey.test.tsx src/features/mesa/mesa-hoy-view.test.ts
```
