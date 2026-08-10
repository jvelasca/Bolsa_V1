# Traspaso parcial — M5 frente `backtest-explore-panel.tsx` (feature-slicing área Coach/TOP) · pasos E.1+E.2

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD:** `72061fd` (paso E.2: BacktestExploreHeader) · árbol limpio · pasos Lab `8ae445b` · Coach `d3315e8` ·
trading-dia-d B.1 `1303610` · B.2 `041457f` · B.3 `a8fede3` · backtest-explore E.1 `5dae5da` · E.2 `72061fd`
**Origen:** [traspaso-m5-frente-trading-dia-d-cierre-2026-08-10.md](./traspaso-m5-frente-trading-dia-d-cierre-2026-08-10.md)
(§2.3 opción 1: reorientar a `backtest-explore-panel.tsx` 1.456 MEDIO) + registro **§7.6.b** de
[dev-continuation-plan-2026-08-09.md](./dev-continuation-plan-2026-08-09.md)

---

## 1. Qué se cerró en este hilo (frente backtest-explore, pasos E.1 y E.2)

Tras cerrar `trading-dia-d-replay-panel.tsx` (B.1+B.2+B.3), M5 reorientó al siguiente frente candidato de
`backtest-explore-panel.tsx` (1.456 líneas, panel **Coach / TOP a futuro**). La regla `coach-top-quality.mdc`
**aplica** (área Coach/TOP): cada paso exigió la batería estándar **+** `pnpm test:coach` (web 26/186 + API smoke
CORE-P live OK).

**FASE 1 (diagnóstico):** a diferencia de trading-dia-d, aquí **NO hay islas JSX autocontenidas de bajo riesgo**. El
orquestador (`BacktestExploreRanking`) tiene ~660 líneas de lógica de ciclo (profile/coachCtx/deepNote/coachFacts,
ack policy, `saveTopMutation` ~185 líneas de negocio, `llmMutation`, auto-save de Finalistas/ACK) que **no es
extraíble como JSX**. Los bloques JSX dependen de ~40 closures. Se **limitó el alcance a las islas de menor
acoplamiento** (Decisión de estrategia, coherente con el patrón Diseño B de 4-7 props): **E.1 vs B&H** y **E.2
cabecera**.

| Paso | Commit | Componente extraído | Dependencias | Reducción orquestador |
|------|--------|---------------------|--------------|----------------------|
| E.1 | `5dae5da` | `BacktestExploreBH` (evidencia vs buy & hold, `backtest-explore-bh.tsx`) | 1 (`coach`) | −15 líneas (~1.456 → ~1.441) |
| E.2 | `72061fd` | `BacktestExploreHeader` (cabecera + quorum + confianza + Guardar/Reanalizar + avisos, `backtest-explore-header.tsx`) | ~16 props (+2 callbacks) | −91 líneas (~1.441 → ~1.350) |

**Patrón — Diseño B (consistente con B.1/B.3):** callbacks/handlers de ciclo **en el orquestador** como props-closure
(`saveTopMutation.mutate({})`, `llmMutation.mutate()`, `setSaveMsg`, `lastLlmFingerprintRef.current=''`,
`canSaveTop`); el JSX presentacional se traslada fielmente. **No se movió lógica de ciclo**: las effects de
auto-guardado (Finalistas/ACK/atajo), la mutation de negocio y el gate quedan intactos en el orquestador.

**Batería verde (E.1 + E.2):** typecheck exit 0 · lint 0e/0w · test **140/707** · build exit 0 (warnings
code-splitting = M7) · **`pnpm test:coach` OK** (web 26/186 + API smoke CORE-P live OK) en cada paso.
**Cobertura verificada:** los dos componentes son JSX presentacional sin test directo; los tests de lógica del área
Coach (`backtest-deep-coach`, `coach-top-save`, `backtest-coach-coherence`, `coach-dual-audit`, etc.) pasan intactos.

---

## 2. Punto de entrada del siguiente hilo

### 2.1 Estado de `backtest-explore-panel.tsx` (→ ~1.350 líneas)

- **Extraídos (E.1, E.2):** `BacktestExploreBH` (vs B&H) y `BacktestExploreHeader` (cabecera). El orquestador sigue
  teniendo la lógica de ciclo completa (saveTopMutation, llmMutation, auto-save, ACK, gate) + los bloques JSX de
  **candidatas ★ (grid)**, **banners de estado del ciclo** (Revalidar/ACK¹/quorum/carry/prefs ACK/vetos), **regime +
  «Análisis AT y outlook»** y la **tabla de batería**.
- **Islas restantes y su riesgo (diagnóstico FASE 1):**
  - **Tabla de batería** (`<details>` grande): usa `ranked`, `sort`, `onSortChange`, `onSelectRun`, `selectedRunId`,
    `onOptimizeCandidate`, `isOptimizableStrategy`, `optimizeFamilyProxyNote`. **Bajo/medio** — ~6-8 props, candidata
    siguiente.
  - **Candidatas ★ (grid + botones Lab)**: usa `deepNote.recommendations`, `coachFacts.starCeiling`, `onOptimizeSemifinal`,
    `onOptimizeCandidate`, `onSelectRun`, `postLab`, `running`, `isOptimizableStrategy`, `optimizeFamilyProxyNote`.
    **Medio/alto** — ~10-15 props con callbacks de ciclo.
  - **Banners de estado del ciclo** (Revalidar/ACK¹/quorum/carry/prefs ACK/checkbox human/softWeak/weak/vetos): usa
    `postLab`, `running`, `deepNote`, `coachFacts`, `carryRows`, `ackPolicy`, `discrepancyAck`, `setDiscrepancyAck`,
    `softAckLatchedRef`, `onAwaitingAckChange`, `confidence`… **ALTO** — toca el ciclo Coach² (ACK / auto-guardado).
  - **Regime + «Análisis AT y outlook» `<details>`**: usa `deepNote.regime`, `deepNote.analysis`/`outlook`/`disclaimer`.
    **Bajo** — candidata, pero menor recompensa (~27 líneas).

### 2.2 Otros frentes de M5 (diagnóstico heredado — NO rehacer salvo cambio)

- `list-values-panel.tsx` (1.395), `instruments-page.tsx` (1.222): **ya feature-sliced**. Resta orquestación.
- `chart-drawings-layer.tsx` (1.979): canvas SVG monolítico, peor valor/riesgo.
- Descartados (acoplamiento alto): `backtest-optimize-panel.tsx` (2.251), `backtest-strategy-matrix-panel.tsx` (1.033),
  `ohlcv-chart.tsx` (974, sin JSX extraíble).
- `trading-dia-d-replay-panel.tsx` (~1.205): **cerrado** (B.1-B.3), es orquestación pura.
- El objetivo F4.8 (`backtests-page.tsx` <3.500, actual 5.127) sigue lejos (es orquestación, no JSX).

### 2.3 Opciones para el siguiente hilo

1. **Continuar `backtest-explore-panel` con las islas restantes de bajo riesgo** — E.3 (tabla de batería), E.4
   (regime + AT outlook). Cada una con batería completa + `test:coach`. Evitar los banners de estado del ciclo (ALTO).
2. **Cerrar este frente en el estado actual (E.1+E.2)** y mover esfuerzo a otro candidato de M5.
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
  `apps/web/src/features/backtests/backtest-explore-header.tsx`, ambos importados desde
  `backtest-explore-panel.tsx`.
