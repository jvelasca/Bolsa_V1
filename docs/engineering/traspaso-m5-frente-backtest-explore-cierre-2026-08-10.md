# Traspaso M5 — cierre formal del frente `backtest-explore-panel.tsx` (área Coach/TOP) · E.1–E.5 completos

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD:** `7172bb7` (frente backtest-explore **CERRADO**) · árbol limpio · sincronizado con origin ·
pasos Lab `8ae445b` · Coach `d3315e8` · trading-dia-d B.1 `1303610` · B.2 `041457f` · B.3 `a8fede3` ·
backtest-explore E.1 `5dae5da` · E.2 `72061fd` · E.3 `fbf1ad0` · E.4 `e079a3f` · E.5 `e66ddf7` · docs cierre `7172bb7`
**Origen:** [traspaso-m5-frente-backtest-explore-cierre-2026-08-10.md](./traspaso-m5-frente-backtest-explore-cierre-2026-08-10.md)
(pasos E.1–E.5) + registro **§7.6.b/c** de
[dev-continuation-plan-2026-08-09.md](./dev-continuation-plan-2026-08-09.md)

**Nota de versionado:** este documento es el **cierre formal y definitivo** del frente backtest-explore. Es
independiente pero sucesor del doc listado en "Origen" (que quedó como registro progresivo E.1–E.5). A partir del
HEAD `7172bb7`, este es el único de entrada para el siguiente hilo de M5.

---

## 1. Qué se cerró en este hilo (frente backtest-explore, pasos E.1 a E.5)

Tras cerrar `trading-dia-d-replay-panel.tsx` (B.1+B.2+B.3), M5 reorientó al siguiente frente candidato de
`backtest-explore-panel.tsx` (1.456 líneas, panel **Coach / TOP a futuro**). La regla `coach-top-quality.mdc`
**aplica** (área Coach/TOP): cada paso exigió la batería estándar **+** `pnpm test:coach` (web 26/186 + API smoke
CORE-P live OK).

**FASE 1 (diagnóstico inicial):** a diferencia de trading-dia-d, aquí **NO hay islas JSX autocontenidas de bajo
riesgo**. El orquestador (`BacktestExploreRanking`) tiene ~660 líneas de lógica de ciclo (profile/coachCtx/deepNote/
coachFacts, ack policy, `saveTopMutation` ~185 líneas de negocio, `llmMutation`, auto-save de Finalistas/ACK) que **no
es extraíble como JSX**. Los bloques JSX dependen de ~40 closures. Se limitó el alcance a las **islas de menor
acoplamiento** (Decisión de estrategia, coherente con el patrón Diseño B de 4-7 props). Se ejecutaron **E.1–E.5** en
orden, cada uno como paso atómico con batería completa:

| Paso | Commit | Componente extraído | Dependencias / Props | Reducción orquestador |
|------|--------|---------------------|----------------------|----------------------|
| E.1 | `5dae5da` | `BacktestExploreBH` (evidencia vs buy & hold, `backtest-explore-bh.tsx`) | 1 (`coach`) | −15 líneas (~1.456 → ~1.441) |
| E.2 | `72061fd` | `BacktestExploreHeader` (cabecera + quorum + confianza + Guardar/Reanalizar + avisos, `backtest-explore-header.tsx`) | ~16 props (+2 callbacks) | −91 líneas (~1.441 → ~1.350) |
| E.3 | `fbf1ad0` | `BacktestExploreBatteryTable` (tabla de batería, `backtest-explore-battery-table.tsx`) | 10 props (`rows`, `symbol`, `okCount`, `progress`, `running`, `sort`, `onSortChange`, `selectedRunId`, `onSelectRun`, `onOptimizeCandidate`) | −186 líneas (~1.350 → ~1.164) |
| E.4 | `e079a3f` | `BacktestExploreAtOutlook` (banner regime + Análisis AT y outlook, `backtest-explore-at-outlook.tsx`) | 4 props (`regime`, `analysis`, `outlook`, `disclaimer`) | −19 líneas (~1.164 → ~1.145) |
| E.5 | `e66ddf7` | `BacktestExploreStarsGrid` (candidatas ★ grid + botones Lab, `backtest-explore-stars-grid.tsx`) | 7 props (`recommendations`, `starCeiling`, `postLab`, `running`, `onSelectRun`, `onOptimizeCandidate`, `onOptimizeSemifinal`) | −97 líneas (~1.145 → **~1.048**) |

**Reducción total del frente:** `backtest-explore-panel.tsx` de **1.456 → ~1.048 líneas** (**−408**).

**Patrón — Diseño B (consistente en todo el frente):** callbacks/handlers de ciclo **en el orquestador** como
props-closure (`saveTopMutation.mutate({})`, `llmMutation.mutate()`, `setSaveMsg`, `lastLlmFingerprintRef.current=''`,
`canSaveTop`); el JSX presentacional se traslada fielmente. En E.3 el `useMemo` de `ranked` (`sortExploreRows`) y el
const `SORT_OPTIONS` migraron al componente; en E.5 `firstLabRec`/`labRecCount` migraron (cálculo local con
`isOptimizableStrategy`). **No se movió lógica de ciclo**: las effects de auto-guardado (Finalistas/ACK/atajo), la
mutation de negocio y el gate quedan intactos en el orquestador.

**Batería verde (E.1 → E.5):** typecheck exit 0 · lint 0e/0w · test **140/707** · build exit 0 (warnings
code-splitting pre-existentes = M7) · **`pnpm test:coach` OK** (web 26/186 + API smoke CORE-P live OK) en cada paso.
**Cobertura verificada:** los componentes extraídos son JSX presentacional sin test directo; los tests de lógica del
área Coach (`backtest-deep-coach`, `coach-top-save`, `backtest-coach-coherence`, `coach-dual-audit`,
`backtest-coach-lote`, `coach-profile-*`, etc.) pasan intactos.

---

## 2. Decisión de cierre y punto de entrada del siguiente hilo

### 2.1 Estado final de `backtest-explore-panel.tsx` (→ ~1.048 líneas) — frente CERRADO

- **Extraídos (E.1–E.5):** `BacktestExploreBH` (vs B&H), `BacktestExploreHeader` (cabecera),
  `BacktestExploreBatteryTable` (tabla de batería), `BacktestExploreAtOutlook` (regime + AT outlook) y
  `BacktestExploreStarsGrid` (candidatas ★ grid). El orquestador conserva la lógica de ciclo completa
  (saveTopMutation, llmMutation, auto-save, ACK, gate) **+** los **banners de estado del ciclo**
  (Revalidar/ACK¹/quorum/carry/prefs ACK/checkbox human/softWeak/weak/vetos).
- **Riesgo ALTO restante (NO extraer):** los banners de estado del ciclo tocan el ciclo Coach² (ACK / auto-guardado) y
  dependen de refs/estado (`postLab`, `running`, `deepNote`, `coachFacts`, `carryRows`, `ackPolicy`, `discrepancyAck`,
  `setDiscrepancyAck`, `softAckLatchedRef`, `onAwaitingAckChange`, `confidence`…). **Decisión del usuario (2026-08-10):
  no tocarlos** y **cerrar el frente**.
- **Decisión del usuario (2026-08-10): CERRAR el frente backtest-explore en E.1–E.5 y DETENER M5.** No se ejecuta más
  feature-slicing en este hilo ni se toca el área Coach en esta rama sin una decisión nueva.

### 2.2 Otros frentes de M5 (diagnóstico heredado — NO rehacer salvo cambio)

| Frente | Tamaño | Estado / valor |
|--------|--------|----------------|
| `list-values-panel.tsx` | 1.395 | **ya feature-sliced**; restaría orquestación (JSX extraíble bajo/medio — requiere FASE 1 si se ataca). |
| `instruments-page.tsx` | 1.222 | **ya feature-sliced**; restaría orquestación (JSX extraíble bajo/medio — requiere FASE 1 si se ataca). |
| `chart-drawings-layer.tsx` | 1.979 | canvas SVG monolítico, **peor valor/riesgo**. |
| `backtest-optimize-panel.tsx` | 2.251 | **descartado** (acoplamiento alto). |
| `backtest-strategy-matrix-panel.tsx` | 1.033 | **descartado** (acoplamiento alto). |
| `ohlcv-chart.tsx` | 974 | **descartado** (sin JSX extraíble). |
| `backtest-explore-panel.tsx` | ~1.048 | **CERRADO (este hilo)** — solo isla ALTO (Coach²/ACK) restante. |
| `trading-dia-d-replay-panel.tsx` | ~1.205 | **cerrado** (B.1-B.3), orquestación pura. |
| F4.8 `backtests-page.tsx` | 5.127 | objetivo <3.500 sigue lejos (**es orquestación**, no JSX). |

### 2.3 Recomendación para el siguiente hilo

**M5 queda en pausa por decisión del usuario (2026-08-10).** Si se retoma, orden de valor/riesgo propuesto:

1. **FASE 1 diagnóstico de `list-values-panel.tsx` (1.395)** o `instruments-page.tsx` (1.222): confirmar si pese a estar
   feature-sliced hay alguna isla JSX inline de bajo riesgo pendiente. Son los siguientes frentes de mejor ratio.
2. **Higiene M0/§6.2 CRLF** de `backtests-page.tsx` como commit de formateo propio (M0, fuera del alcance de M5).
3. **Refactor a custom hooks** (extraer handlers/queries de orquestación de los frentes grandes) — más invasivo, requiere
   recalibración explícita.
4. **No recomendado:** `chart-drawings-layer.tsx` (1.979, peor valor/riesgo).

> **Nota transversal:** el área Coach/TOP (backtest-explore, strategy-matrix, instrument-strategy-top, coach-top-save)
> exige la regla `coach-top-quality.mdc` y la batería `pnpm test:coach` en cualquier hilo que la toque. Mantener el
> pilar del embudo (Universo → Coach → Lab → Finalistas) inviolable.

---

## 3. Reglas del juego (mantener en el nuevo chat)

- **Protocolo sagrado** del traspaso M5: FASE 1 diagnóstico (sin cambios) → FASE 2 plan atómico + aprobación →
  FASE 3 ejecución + **batería completa por cada paso** (typecheck + lint 0 errores + **test** + build) +
  `git commit --no-verify` + push + registro §7.6.
- Área Coach/TOP: aplicar la regla `coach-top-quality.mdc` → batería extra **`pnpm test:coach`** en cada paso que la toque.
- **No tocar backend (M3/M4/M6)** ni **M7** (dev-stack: chunk >500 kB / crash Vite).
- **Batería TEST obligatoria:** `pnpm --filter @bolsa/web test` (140 ficheros / 707 tests).
- Herramientas: `pnpm 10.12.1` sí en PATH; `uv` NO (usar `$env:USERPROFILE\.local\bin\uv.exe`). Shell **PowerShell**
  (no `&&`; usar `;`).
- Commits con `git commit --no-verify` (CRLF/lint-staged/prettier). Push a
  `origin/stage/estudio-membership-operativa-2026-08-04`.
- Si el chat se satura, **cortar y preparar otro traspaso parcial** (documentar todo y actualizar GitHub) antes de
  continuar.

## 4. Estado de referencia para validar batería

- `pnpm --filter @bolsa/web typecheck` → exit 0
- `pnpm --filter @bolsa/web lint` → exit 0 (0e/0w)
- `pnpm --filter @bolsa/web test` → 140 ficheros / 707 tests, 0 fallos
- `pnpm --filter @bolsa/web build` → exit 0 (solo warnings code-splitting pre-existentes = M7)
- `pnpm test:coach` → OK (web 26/186 + API smoke CORE-P)
- Ficheros nuevos del frente (importados desde `backtest-explore-panel.tsx`):
  `backtest-explore-bh.tsx`, `backtest-explore-header.tsx`, `backtest-explore-battery-table.tsx`,
  `backtest-explore-at-outlook.tsx` y `backtest-explore-stars-grid.tsx` (en `apps/web/src/features/backtests/`).
