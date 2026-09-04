# RELEVO — V2.x Product UX (cabina Mercado) (2026-09-04)

> **Padre:** tip motor [`v2.0-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.0-beta) → [`e05fc6b0`](https://github.com/jvelasca/Bolsa_V1/commit/e05fc6b0) · [relevo V2.0 PAPER AUTO](./traspaso-relevo-v2-0-cierre-paper-auto-2026-09-04.md).  
> **Estado:** **CERRADO para auditoría externa** · tip cadena UX [`b8192d3a`](https://github.com/jvelasca/Bolsa_V1/commit/b8192d3a) (V2.09) · base [`a39595ce`](https://github.com/jvelasca/Bolsa_V1/commit/a39595ce) · **sin tip GitHub** `v2.x-*` (≠ tip motor V2.0).  
> **Arranque auditor:** [`arranque-auditor-v2-x-product-ux-2026-09-04.md`](./arranque-auditor-v2-x-product-ux-2026-09-04.md).  
> **Smoke browser (2026-09-04):** Position Card + protect **OK** (ver Ops).  
> **Para quién:** auditor externo · ops (user test) · no reabrir motor FSM.

## Objetivo

Transición de «motor PAPER AUTO robusto» a **producto usable**: Mercado como cabina; NEXT ACTION como héroe; jerga de motor en avanzado.

## Commits (cadena tip UX → `origin/main`)

| SHA        | Mensaje                                                           |
| ---------- | ----------------------------------------------------------------- |
| `a39595ce` | feat(v2.x): Mercado operator cabin with NEXT ACTION and AUTO Desk |
| `3a71f47f` | docs: stamp V2.x smoke PARTIAL (Position Card pendiente)          |
| `e17c51c1` | docs: stamp V2.x Position+protect smoke OK                        |
| `fd16181e` | feat(v2.08): Proteger CTA for OPEN_UNPROTECTED                    |
| `b8192d3a` | feat(v2.09): cabin typography and a11y polish                     |
| `67d30188` | docs: arranque auditor V2.x + cierre relevo auditoría             |

## Hecho (V2.01–V2.09)

| ID        | Entrega                                            | Evidencia                                                                                   |
| --------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| **V2.01** | Cabina Mercado · 4 respuestas · NEXT ACTION        | `operator-cabin-view.ts` · `operativa-cockpit-card.tsx` · `operator-cabin-ui.tsx`           |
| **V2.02** | Opportunity Card (ESPERAR TRIGGER / ENTRADA LISTA) | `decision-surface-compact.tsx` entry · copy sin COMPRAR                                     |
| **V2.03** | Position Card misión + Risk Box                    | `JourneyHudBlock` · checklist · `primaryAction` · vitest journey                            |
| **V2.04** | AUTO Desk en DECISIÓN                              | `auto-desk-panel.tsx` · Manual/Asistido/Automático · checklist · perfil ExitPolicy          |
| **V2.05** | Hoy 4 cubos                                        | `daily-desk.ts` · Requiere atención (absorbe Proteger) · menú «Avanzado»                    |
| **V2.06** | Asesor = explicación                               | copy `/research` · no segunda mesa                                                          |
| **V2.07** | Journal = memoria + learning strip                 | `decision-journal-page` framing · Evolución lee `decision_sessions` learning (SoT intacto)  |
| **V2.08** | CTA Proteger en `OPEN_UNPROTECTED`                 | `positionShowsProtectCta` · bootstrap stop 5% · DECISIÓN + Hoy · Confirm sigue firmando     |
| **V2.09** | Polish tipografía / a11y cabina                    | NEXT ACTION `text-base` + `role=status` · Risk/Resumen/misión landmarks · AUTO Desk sr-only |

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
| V2.08 CTA                    | `fd16181e` · Proteger secundaria OPEN_UNPROTECTED                                                                                    |
| V2.09 polish                 | `b8192d3a` · tipografía/a11y                                                                                                         |

### User test V2.09 (ops propietario · ~10 min)

1. Mercado · valor sin plan → ¿ves **PRÓXIMA ACCIÓN** en menos de 10 s sin jerga?
2. Candidato / trigger → ¿**ESPERAR TRIGGER** o **ENTRADA LISTA** + «Revisar y confirmar» (no COMPRAR)?
3. Posición abierta sin stop → ¿**Mantener** + **Proteger** → Confirm → stop?
4. Posición protegida → misión Entrada✓ Stop✓ · Risk Box · AUTO Desk Asistido/Auto honestos?
5. Hoy · 4 cubos · menú Avanzado · ¿misma frase que Mercado?

## OUT / next (post-auditoría)

- ~~Smoke browser con posición PAPER abierta~~ **hecho 2026-09-04**
- ~~V2.08 / V2.09~~ **hecho**
- ~~Arranque + push `main` para auditor externo~~ **este relevo**
- Colapso nav L1 (ADR-040) solo tras cabina estable **y** veredicto auditor
- Tip GitHub `v2.x-*` **solo si** se pide explícitamente (no confundir con `v2.0-beta` motor)

## Pre-flight

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/operator-cabin-view.test.ts src/cognitive/daily-desk.test.ts
cd apps/web && npx vitest run src/features/trading/operativa-cockpit-card.test.tsx src/features/trading/decision-surface-journey.test.tsx src/features/mesa/mesa-hoy-view.test.ts
```
