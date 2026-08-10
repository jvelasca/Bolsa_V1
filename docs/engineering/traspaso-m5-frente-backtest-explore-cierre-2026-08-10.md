# Traspaso parcial — M5 frente `backtest-explore-panel.tsx` (feature-slicing área Coach/TOP) · pasos E.1+E.2+E.3+E.4+E.5

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD:** `e66ddf7` (frente E.1–E.5 completo) · árbol limpio · pasos Lab `8ae445b` · Coach `d3315e8` ·
trading-dia-d B.1 `1303610` · B.2 `041457f` · B.3 `a8fede3` · backtest-explore E.1 `5dae5da` · E.2 `72061fd` ·
E.3 `fbf1ad0` · E.4 `e079a3f` · **E.5 `e66ddf7`**
**Origen:** [traspaso-m5-frente-trading-dia-d-cierre-2026-08-10.md](./traspaso-m5-frente-trading-dia-d-cierre-2026-08-10.md)
(§2.3 opción 1: reorientar a `backtest-explore-panel.tsx` 1.456 MEDIO) + registro **§7.6.b** de
[dev-continuation-plan-2026-08-09.md](./dev-continuation-plan-2026-08-09.md)

---

## 1. Qué se cerró en este hilo (frente backtest-explore, pasos E.1 a E.4)

Tras cerrar `trading-dia-d-replay-panel.tsx` (B.1+B.2+B.3), M5 reorientó al siguiente frente candidato de
`backtest-explore-panel.tsx` (1.456 líneas, panel **Coach / TOP a futuro**). La regla `coach-top-quality.mdc`
**aplica** (área Coach/TOP): cada paso exigió la batería estándar **+** `pnpm test:coach` (web 26/186 + API smoke
CORE-P live OK).

**FASE 1 (diagnóstico):** a diferencia de trading-dia-d, aquí **NO hay islas JSX autocontenidas de bajo riesgo**. El
orquestador (`BacktestExploreRanking`) tiene ~660 líneas de lógica de ciclo (profile/coachCtx/deepNote/coachFacts,
ack policy, `saveTopMutation` ~185 líneas de negocio, `llmMutation`, auto-save de Finalistas/ACK) que **no es
extraíble como JSX**. Los bloques JSX dependen de ~40 closures. Se **limitó el alcance a las islas de menor
acoplamiento** (Decisión de estrategia, coherente con el patrón Diseño B de 4-7 props): **E.1 vs B&H**, **E.2
cabecera**, **E.3 tabla de batería** y **E.4 regime + AT outlook**.

| Paso | Commit | Componente extraído | Dependencias | Reducción orquestador |
|------|--------|---------------------|--------------|----------------------|
| E.1 | `5dae5da` | `BacktestExploreBH` (evidencia vs buy & hold, `backtest-explore-bh.tsx`) | 1 (`coach`) | −15 líneas (~1.456 → ~1.441) |
| E.2 | `72061fd` | `BacktestExploreHeader` (cabecera + quorum + confianza + Guardar/Reanalizar + avisos, `backtest-explore-header.tsx`) | ~16 props (+2 callbacks) | −91 líneas (~1.441 → ~1.350) |
| E.3 | `fbf1ad0` | `BacktestExploreBatteryTable` (tabla de batería, `backtest-explore-battery-table.tsx`) | 10 props (`rows`, `symbol`, `okCount`, `progress`, `running`, `sort`, `onSortChange`, `selectedRunId`, `onSelectRun`, `onOptimizeCandidate`) | −186 líneas (~1.350 → ~1.164) |
| E.4 | `e079a3f` | `BacktestExploreAtOutlook` (banner regime + Análisis AT y outlook, `backtest-explore-at-outlook.tsx`) | 4 props (`regime`, `analysis`, `outlook`, `disclaimer`) | −19 líneas (~1.164 → ~1.145) |
| E.5 | `e66ddf7` | `BacktestExploreStarsGrid` (candidatas ★ grid + botones Lab, `backtest-explore-stars-grid.tsx`) | 7 props (`recommendations`, `starCeiling`, `postLab`, `running`, `onSelectRun`, `onOptimizeCandidate`, `onOptimizeSemifinal`) | −97 líneas (~1.145 → **~1.048**) |

**Patrón — Diseño B (consistente con B.1/B.3/E.2):** callbacks/handlers de ciclo **en el orquestador** como props-closure
(`saveTopMutation.mutate({})`, `llmMutation.mutate()`, `setSaveMsg`, `lastLlmFingerprintRef.current=''`,
`canSaveTop`); el JSX presentacional se traslada fielmente. En E.3 el `useMemo` de `ranked` (`sortExploreRows`) y el
const `SORT_OPTIONS` **migran al componente** (únicos consumidores eran la tabla); E.4 es data-only (4 props). **No se
movió lógica de ciclo**: las effects de auto-guardado (Finalistas/ACK/atajo), la mutation de negocio y el gate quedan
intactos en el orquestador.

**Batería verde (E.1 → E.5):** typecheck exit 0 · lint 0e/0w · test **140/707** · build exit 0 (warnings
code-splitting = M7) · **`pnpm test:coach` OK** (web 26/186 + API smoke CORE-P live OK) en cada paso.
**Cobertura verificada:** los componentes extraídos son JSX presentacional sin test directo; los tests de lógica del área
Coach (`backtest-deep-coach`, `coach-top-save`, `backtest-coach-coherence`, `coach-dual-audit`, etc.) pasan intactos.

---

## 2. Punto de entrada del siguiente hilo

### 2.1 Estado de `backtest-explore-panel.tsx` (ACTUALIZADO tras E.5: → ~1.048 líneas)

> **PUNTO DE HANDOFF (2026-08-10, tras E.5):** el hilo que ejecutó E.5 terminó con árbol limpio en HEAD `e66ddf7`.
> El próximo paso **recomendado**: **cerrar este frente en el estado actual** (E.1–E.5 completos) y mover esfuerzo a
> otro candidato de M5, **sin tocar** los banners de estado del ciclo (ALTO — tocan Coach²/ACK). Ver §2.3.

- **Extraídos (E.1–E.5):** `BacktestExploreBH` (vs B&H), `BacktestExploreHeader` (cabecera),
  `BacktestExploreBatteryTable` (tabla de batería), `BacktestExploreAtOutlook` (regime + AT outlook) y
  **`BacktestExploreStarsGrid` (candidatas ★ grid)**. El orquestador sigue teniendo la lógica de ciclo completa
  (saveTopMutation, llmMutation, auto-save, ACK, gate) + los **banners de estado del ciclo**
  (Revalidar/ACK¹/quorum/carry/prefs ACK/vetos).
- **Islas restantes y su riesgo (diagnóstico FASE 1):**
  - **Banners de estado del ciclo** (Revalidar/ACK¹/quorum/carry/prefs ACK/checkbox human/softWeak/weak/vetos): usa
    `postLab`, `running`, `deepNote`, `coachFacts`, `carryRows`, `ackPolicy`, `discrepancyAck`, `setDiscrepancyAck`,
    `softAckLatchedRef`, `onAwaitingAckChange`, `confidence`… **ALTO** — toca el ciclo Coach² (ACK / auto-guardado).

### 2.2 Otros frentes de M5 (diagnóstico heredado — NO rehacer salvo cambio)

- `list-values-panel.tsx` (1.395), `instruments-page.tsx` (1.222): **ya feature-sliced**. Resta orquestación.
- `chart-drawings-layer.tsx` (1.979): canvas SVG monolítico, peor valor/riesgo.
- Descartados (acoplamiento alto): `backtest-optimize-panel.tsx` (2.251), `backtest-strategy-matrix-panel.tsx` (1.033),
  `ohlcv-chart.tsx` (974, sin JSX extraíble).
- `trading-dia-d-replay-panel.tsx` (~1.205): **cerrado** (B.1-B.3), es orquestación pura.
- El objetivo F4.8 (`backtests-page.tsx` <3.500, actual 5.127) sigue lejos (es orquestación, no JSX).

### 2.3 Opciones para el siguiente hilo

> **E.5 EJECUTADO (2026-08-10, commit `e66ddf7`):** este chat ejecutó la opción 1 (E.5) del hilo previo. Queda
> **PENDIENTE** decidir el siguiente paso (ver recomendación en §2.1 y opciones abajo).

1. **✅ HECHO — E.5: `BacktestExploreStarsGrid` (candidatas ★ grid).** Ejecutado en este chat (único paso atómico).
   - **Props (Diseño B):** `recommendations: TechnicalRecommendation[]`, `starCeiling: number`, `postLab: boolean`,
     `running?: boolean`, `onSelectRun`, `onOptimizeCandidate`, `onOptimizeSemifinal`.
   - **Migrado al componente:** `firstLabRec` y `labRecCount` (cálculo local con `isOptimizableStrategy`).
   - **NO se movió lógica de ciclo**: callbacks como props-closure; `postLab`/`running` solo para `disabled`.
   - **Batería verde:** typecheck exit 0 · lint 0e/0w · test **140/707** · build exit 0 (solo M7) ·
     **`pnpm test:coach` OK** (web 26/186 + API smoke CORE-P live PASS). Commit `--no-verify` `e66ddf7` + push + registro §7.6.
   - **Reducción del orquestador:** ~1.145 → **~1.048** (net −97, el bloque ~150 se traslada al fichero nuevo).
2. **RECOMENDADO (próximo paso): cerrar este frente en el estado actual (E.1–E.5)** y mover esfuerzo a otro candidato de M5.
   - No tocar los banners de estado del ciclo (ALTO — toca Coach²/ACK).
3. **Refactor a custom hooks** (extraer `saveTopMutation`/`llmMutation`/auto-save como hooks) — más invasivo, toca el
   ciclo Coach², requiere recalibración explícita.

---

## 3. Reglas del juego (mantener en el nuevo chat)

- **Protocolo sagrado** del traspaso M5: FASE 1 diagnóstico (sin cambios) → FASE 2 plan atómico + aprobación →
  FASE 3 ejecución + **batería completa por cada paso** (typecheck + lint 0 errores + **test** + build) +
  `git commit --no-verify` + push + registro §7.6.
- **Área Coach/TOP:** aplicar la regla `coach-top-quality.mdc` → batería extra **`pnpm test:coach`** (web 26/186 +
  API smoke CORE-P) en cada paso que toque el frente.
- **No tocar backend (M3/M4/M6)** ni **M7** (dev-stack: chunk >500 kB / crash Vite).
- **Batería TEST obligatoria en cada paso:** `pnpm --filter @bolsa/web test` (140 ficheros / 707 tests).
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
- `pnpm test:coach` → OK (web 26/186 + API smoke CORE-P)
- `pnpm --filter @bolsa/web build` → exit 0 (solo warnings code-splitting pre-existentes = M7)
- Ficheros nuevos de este hilo: `apps/web/src/features/backtests/backtest-explore-bh.tsx`,
  `apps/web/src/features/backtests/backtest-explore-header.tsx`,
  `apps/web/src/features/backtests/backtest-explore-battery-table.tsx`,
  `apps/web/src/features/backtests/backtest-explore-at-outlook.tsx` y
  `apps/web/src/features/backtests/backtest-explore-stars-grid.tsx`, importados desde
  `backtest-explore-panel.tsx`.
- **E.5 (`e66ddf7`)** añade: `backtest-explore-stars-grid.tsx` (nuevo) y reduce `backtest-explore-panel.tsx`
  de ~1.145 a **~1.048 líneas** (net −97).
