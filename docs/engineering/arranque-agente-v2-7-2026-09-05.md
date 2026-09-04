# ARRANQUE — V2.7 Operator Hardening · primer ID V2.39 (2026-09-05)

> **Leer primero:** [relevo V2.7 Operator Hardening](./traspaso-relevo-v2-7-operator-hardening-2026-09-05.md).  
> **Tip producto vigente (no reabrir):** [`v2.6-beta`](./traspaso-relevo-tag-v2-6-beta-2026-09-05.md) `50abd31d` / package `1.36.0-beta`.  
> **Para quién:** agente implementación · **NO MÁS PANELES** · no reabrir motor FSM · no tip/bump hasta cierre pedido.

## Estado al relevo

| Corte                            | Estado                                 |
| -------------------------------- | -------------------------------------- |
| V2.6 Pixel Premium (`v2.6-beta`) | tip `50abd31d` · **cerrado**           |
| Auditoría walk UI V2.6           | **hecho** (browser + pre-flight local) |
| V2.39 AUTO arm honesty           | **pendiente** ← **primer ID**          |
| V2.40 Touch cabina               | pendiente                              |
| V2.41 Cert visual operador       | pendiente                              |
| Tip `v2.7-beta`                  | **no**                                 |

## Primer ID a implementar

**V2.39 — AUTO arm honesty**

Problema (confirmado live): en [`auto-desk-panel.tsx`](../../apps/web/src/features/trading/auto-desk-panel.tsx), `setAutonomy("auto")` llama `saveAutoArm({ armed: true, confirmPhrase: "ACTIVAR AUTO" })` **sin** `tryArmAuto`. Cuentas ([`demo-book-mode-panel.tsx`](../../apps/web/src/features/trading/demo-book-mode-panel.tsx)) sí exige frase.

Entrega:

1. Extraer el formulario A3 (frase + Confirmar/Cancelar) a un componente compartido — **no** panel nuevo de Mercado.
2. `AutoDeskPanel`: click Automático → abrir formulario (si no armado) → solo `tryArmAuto` + `patchDemoBookPrefs({ mode: "auto" })`.
3. Si ya armado: permitir `mode: auto` como Cuentas.
4. Tests: un click no arma · frase incorrecta falla · frase `ACTIVAR AUTO` arma · no forjar `confirmPhrase`.
5. Mantener honesty copy Arm ≠ Execute · `PAPER_D_EXECUTE` off.

## Freeze (copiar al chat)

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles de trading nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty intactos · escalera T1→T2→trail (no reordenar) · package `1.36.0-beta` sin bump.

## Archivos clave

| Área          | Archivo                                                                                         |
| ------------- | ----------------------------------------------------------------------------------------------- |
| Bypass actual | `apps/web/src/features/trading/auto-desk-panel.tsx`                                             |
| A3 canónico   | `apps/web/src/features/trading/demo-book-mode-panel.tsx`                                        |
| Arm API       | `apps/web/src/features/trading/demo-book-auto-arm.ts` (`tryArmAuto`, `AUTO_ARM_CONFIRM_PHRASE`) |
| Touch token   | `apps/web/src/features/trading/cabin-visual.ts` (`CABIN_TOUCH_TARGET`)                          |
| Tests AUTO    | `apps/web/src/features/trading/auto-desk-panel.test.tsx`                                        |
| Tests A3      | `apps/web/src/features/trading/demo-book-mode-panel.test.tsx` · `demo-book-auto-arm.test.ts`    |

## Pre-flight mínimo (evidencia local)

```bash
cd packages/shared && pnpm exec vitest run src/cognitive/g-operator-02-golden-journey.test.ts src/cognitive/g-operator-03-protect-journey.test.ts src/cognitive/g-operator-05-ui-truth-v25.test.ts src/cognitive/operator-cabin-view.test.ts
cd apps/web && pnpm exec vitest run src/features/trading/decision-surface-journey.test.tsx src/features/trading/operator-cabin-ui.test.tsx src/features/trading/cabin-visual.test.ts src/features/trading/auto-desk-panel.test.tsx src/features/trading/demo-book-mode-panel.test.tsx src/features/trading/demo-book-auto-arm.test.ts src/features/charts/chart-focus-toggle.test.tsx
```

Última corrida auditoría (2026-09-05): shared **46/46** · web cabin **13/13** PASS. No afirmar CI GitHub GREEN.

## Prompt sugerido al abrir chat

> Lee `docs/engineering/arranque-agente-v2-7-2026-09-05.md` y el relevo V2.7. Freeze intacto. NO MÁS PANELES. Implementa **solo V2.39** (AUTO Desk → `tryArmAuto` + frase, UI A3 compartida con Cuentas). No tip/bump. No V2.40/V2.41 hasta cerrar V2.39.
