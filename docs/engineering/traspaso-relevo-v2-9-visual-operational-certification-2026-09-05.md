# RELEVO — V2.9 Visual and Operational Certification (2026-09-05)

> **Padre:** [relevo V2.8 Operator Cabin Certification](./traspaso-relevo-v2-8-operator-certification-2026-09-05.md) · tip [`v2.8-beta`](./traspaso-relevo-tag-v2-8-beta-2026-09-05.md) `a9ec6424`.  
> **Estado:** **CÓDIGO CERRADO** · incluido en tip [`v2.10-beta`](./traspaso-relevo-tag-v2-10-beta-2026-09-05.md) · package `1.39.0-beta` (sin tip `v2.9-beta` aparte).  
> **Para quién:** certificación visual/operacional de cabina · **NO MÁS PANELES** · no reabrir motor FSM.  
> **Arranque:** [arranque V2.9](./arranque-agente-v2-9-2026-09-05.md).

## Objetivo

V2.8 cerró Operator Cabin Certification (A3 · ARM chrome · E2E DOM · CI honesty).  
V2.9 **no añade funcionalidad de trading** ni paneles. Cierra P2 de certificación y un hallazgo de proceso:

1. **V2.46** — ARM chrome desde `autoActive` (MANUAL/SEMI nunca AUTO ARMADO) + state matrix.
2. **V2.47** — `orphan_recovery_failed` visible (nota + exceptionFact URGENT).
3. **V2.48** — `CABIN_TOUCH_TARGET` 44px · meta fuera de controles operativos.
4. **V2.49** — zoom de layout 100/125/150 (no `body.style.zoom`).
5. **V2.50** — snapshots acotados + contraste light/dark.
6. **V2.51** — traversal teclado cabina · CI stamp solo con `conclusion`.

## Freeze intacto

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · **AUTO sin controles de trading nuevos** · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty **intactos** · package `1.39.0-beta` · **no afirmar CI GREEN sin status checks del SHA**.

**Arm ≠ Execute · Arm ≠ autorización de operación · Confirm = firma · Ranking ≠ BUY.**

No se tocó el algoritmo de `RecoverOrphanOpeningFills.recover()`. El ciclo no se bloquea entero si recover lanza: fail-closed de Position + fail-visible de proceso.

## Entrega

| ID        | P2 / hallazgo              | Entrega                                                             | Evidencia                                       |
| --------- | -------------------------- | ------------------------------------------------------------------- | ----------------------------------------------- |
| **V2.46** | ARM chrome defensivo       | `cabinArmLabels(autoActive)` · `data-arm` desde posture             | `paper-auto-posture.test` · auto-desk · e2e v28 |
| **V2.47** | orphan recovery silencioso | nota `orphan_recovery_failed` → exceptionFact URGENT                | pytest cycle + daily report · shared projection |
| **V2.48** | Touch 44px + type          | `min-h-11` · botones AUTO/A3 `operativa`                            | cabin-visual · auto-desk · e2e ≥44              |
| **V2.49** | Zoom real de layout        | CSS viewport shrink + `deviceScaleFactor`                           | `gp-e2e-v28` 3 viewports × 100/125/150          |
| **V2.50** | Visual + contraste         | snapshots acotados · contraste 4.5:1 en chrome operacional          | `gp-e2e-v29`                                    |
| **V2.51** | Teclado + CI honesty       | AUTO → phrase → Confirm → Cancelar · docs no GREEN sin `conclusion` | e2e v28 · este relevo                           |

## Matriz de certificación (honestidad)

| Cubierto                                                                                                                                                                                      | Aproximación — no afirmar                                                   |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Overflow/layout a 125/150% equivalente (viewport CSS + DPR). 1024@150% cae bajo `md` (768px): el dock DECISIÓN está `hidden md:flex`; se certifica overflow del shell, no del cockpit oculto. | Zoom nativo completo del cromo Chrome/Edge                                  |
| Snapshots de superficies acotadas (cockpit, Position Card, AUTO, Chart focus). Goldens host-OS (`*-win32.png`); CI linux no compara píxeles (contraste sí).                                   | Toda la UI pixel-perfect · goldens Linux sin `--update-snapshots` en ubuntu |
| Contraste WCAG-ish en chrome operacional (light/dark, error, ARM, A3)                                                                                                                         | Auditoría visual de gráficos / T1-T2                                        |
| CI GREEN solo con `conclusion=success` del SHA                                                                                                                                                | GREEN por existir el workflow                                               |

## V2.51 — CI

| Pieza       | Valor                                                                                                        |
| ----------- | ------------------------------------------------------------------------------------------------------------ |
| Tip vigente | `v2.10-beta` (incluye V2.46–V2.51) · package `1.39.0-beta`                                                   |
| V2.9 código | este relevo · **sin** tip `v2.9-beta` aparte                                                                 |
| Stamp       | **CI GREEN: NO CERTIFICABLE** hasta run de Release-tag CI con `conclusion=success` sobre el SHA `v2.10-beta` |

Tras tip/dispatch: stamp **solo** con URL de run + `conclusion`. Si `statuses: []` / `workflow runs: []` → seguir **NO CERTIFICABLE**.

No ampliar `.gitleaks.toml`.

## Pre-flight local

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/paper-auto-posture.test.ts src/daily-desk-auto-projection.test.ts
cd apps/web && npx vitest run src/features/trading/auto-desk-panel.test.tsx src/features/trading/cabin-visual.test.ts src/features/trading/demo-book-auto-arm.test.ts
# python: test_paper_desk_lifecycle + test_paper_daily_report
E2E_RUN=1 pnpm e2e -- gp-e2e-v28
E2E_RUN=1 pnpm e2e -- gp-e2e-v29
```

## OUT / Next

- Tip [`v2.10-beta`](./traspaso-relevo-tag-v2-10-beta-2026-09-05.md) + bump `1.39.0-beta` — **autorizado** (incluye este corte; sin `v2.9-beta` aparte).
- **Next corte:** [V2.10 Seed Ops](./traspaso-relevo-v2-10-seed-ops-2026-09-05.md) · [arranque](./arranque-agente-v2-10-2026-09-05.md) · [runbook](./runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md) — birth estructural + Journal MFE·MAE (**incluido en el mismo tip**).
- Release-tag CI sobre `v2.10-beta` — GREEN solo con `conclusion=success`.
- Operator Cabin feature-complete salvo necesidad funcional real.
- No reabrir motor FSM / PAPER AUTO execute.
