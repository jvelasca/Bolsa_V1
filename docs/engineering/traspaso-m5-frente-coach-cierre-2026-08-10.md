# Traspaso parcial — M5 frente Coach + frentes alternativos (frontend web por features)

**Head actualizado tras B.2:** `041457f`
**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD:** `041457f` (frente trading-dia-d, paso B.2: DiaDPendingTradeBanner) · paso Lab `8ae445b`
**Origen:** [traspaso-m5-f4-8-coach-lab-2026-08-10.md](./traspaso-m5-f4-8-coach-lab-2026-08-10.md) + registro **§7.6**
de [dev-continuation-plan-2026-08-09.md](./dev-continuation-plan-2026-08-09.md)

---

## 1. Qué se cerró (hilo Coach, paso Coach)

Feature-slicing de `apps/web/src/features/backtests/backtests-page.tsx`: de **5.759 → 5.127 líneas**, en **10 pasos
atómicos** + registro, **cada uno con batería completa en verde** (typecheck exit 0 · lint 0e/0w · test **140/707** ·
build exit 0; warnings code-splitting pre-existentes = **M7, fuera de alcance**). Commits `git commit --no-verify`
(hook lint-staged/prettier CRLF) + push a origin.

| Paso | Commit | Componente extraído |
|------|--------|---------------------|
| 1–8 | `0fce03b`…`c0dfe24` | `BacktestResult*` / `BacktestWizard*` (hilo previo) |
| 9 | `8ae445b` | `BacktestResultFocusLab` (hilo Coach + Lab) |
| 10 | `d3315e8` | `BacktestResultFocusCoach` (último island de M5) |
| — | `e746ed8` | registro §7.6 + traspaso Coach+Lab actualizados |

**Paso 9 (Lab, Diseño B):** extraído el bloque `resultFocus === "lab"` a `backtest-result-focus-lab.tsx`
(fine wrapper, ~14 props). Los callbacks acoplados (`onClearZoneSeed`, `onReanalyzeWithCoach`,
`onAutoHandoffStatus`, `onGoToCoach`) **permanecen en el orquestador** (Diseño B aprobado frente al Diseño A de
~200 líneas/27 props): la lógica de cierre de ciclo (`settleFullCycle` vía `onAutoHandoffStatus`) no se movió fuera
del orquestador, consistente con los pasos 1–8.

**Paso 10 (Coach, Diseño B):** extraído el bloque de result focus **Coach** a `backtest-result-focus-coach.tsx`
(thin wrapper, ~33 props): los 2 avisos «Sin lote de coach aún»/«Lista AUTO en marcha» + el `<div>` contenedor que
renderiza `BacktestExploreRanking`. Los callbacks acoplados de ciclo (`onAutoSaveStatus`→`settleFullCycle`,
`onSelectRun`, `onAwaitingAckChange`, `onCoachGateChange`, `onOptimizeCandidate`/`onOptimizeSemifinal`) **permanecen
en el orquestador** como props-closure (Diseño B, coherencia con pasos 1–9): la lógica del ciclo no se mueve.
Reducción neta en `backtests-page.tsx`: -25 líneas; el bloque JSX (~150 líneas) se traslada al fichero nuevo.
Con este paso M5 **agota las islas JSX del monólito**. Batería Coach adicional (`pnpm test:coach`, regla
`coach-top-quality.mdc`) en verde: web 26/186 + API smoke CORE-P live OK.

## 2. Punto de entrada del siguiente hilo

### 2.1 Estado de `backtests-page.tsx` (→ 5.127 líneas, objetivo F4.8 <3.500)

- **Extraído el result focus Coach** (`BacktestResultFocusCoach`, paso 10 → `backtest-result-focus-coach.tsx`):
  los 2 avisos «Sin lote de coach aún» / «Lista AUTO en marcha» + el bloque `tab === "run"`
  `{exploreRows.length > 0 && (resultFocus === "coach" || (Boolean(listAutoBoard) && fullCycleActive &&
  coachPass === "post_lab"))}` con su `<div>` y `<BacktestExploreRanking>`. **Diseño B**: ~33 props con los
  callbacks inline de ciclo (`onAutoSaveStatus`→`settleFullCycle`+`listAutoRef`, `onAwaitingAckChange`,
  `onSelectRun`, `onCoachGateChange`, `onOptimizeCandidate`, `onOptimizeSemifinal`) **permaneciendo en el
  orquestador**. Resta de M5 en `backtests-page.tsx`: lógica de orquestación (estado/queries/handlers), no JSX
  autocontenido. Objetivo F4.8 <3.500 sigue sin alcanzarse por el volumen de orquestación, no por islas JSX.

### 2.2 Frentes alternativos de M5 — evaluados, **no** ofrecen slicing JSX de bajo riesgo

| Frente | Líneas | Diagnóstico (FASE 1) |
|--------|--------|----------------------|
| `trading/lists-tab/list-values-panel.tsx` | 1.395 | **Ya feature-sliced** (`ListCarousel`, `ListItemAccordion`, `SortedApiList`, `SortedVisualizationList`, `PortfolioKeyboardList`, `PendingOrdersKeyboardList`, banner Estudio…). Resta lógica de orquestación. |
| `instruments/instruments-page.tsx` | 1.222 | **Ya feature-sliced** (`InstrumentsHubFilterBar`, `InstrumentsHubSplitLayout`, `SyncBadge`, `ListsCell`, `ScoreCell`, `SeguimientoCell`, `PortfolioCell`). Resta orquestación. |
| `charts/chart-drawings-layer.tsx` | 1.979 | Canvas SVG monolítico + editor interdependiente (estado de dibujo, coordenadas, eventos). Peor ratio valor/riesgo. |

### 2.3 Opciones para el siguiente hilo

1. ~~Extraer el Coach con Diseño B~~ — **HECHO** (paso 10, `BacktestResultFocusCoach`, ~33 props).
   M5 ya no deja islas JSX autocontenidas en `backtests-page.tsx`.
2. **Reorientar M5 a otro frente — EN CURSO**: se inició el frente `trading-dia-d-replay-panel.tsx` (1.341 líneas),
   el mejor candidato de valor/riesgo (parcialmente sliced y con thin wrappers limpios). **Pasos B.1 y B.2 hechos**:
   `DiaDTradesPanel` (tabla de Operaciones) y `DiaDPendingTradeBanner` (banner trade pendiente). **Pendiente:**
   **B.3** panel Informe sesión (acoplamiento medio). Otros candidatos del §4.2 (acoplamiento alto, descartados en
   FASE 1): `backtest-optimize-panel.tsx` (2.251), `backtest-strategy-matrix-panel.tsx` (1.033),
   `backtest-explore-panel.tsx` (1.456, MEDIO), `ohlcv-chart.tsx` (974, sin JSX extraíble).
3. **Refactor a custom hooks** (extraer handlers/queries de orquestación de los frentes grandes) — más invasivo,
   fuera del patrón de slicing JSX aprobado; requiere recalibración explícita.

> **Progreso (2026-08-10):** el hilo de reorientación ejecutó **B.1 + B.2** en `trading-dia-d-replay-panel.tsx`
> (`DiaDTradesPanel`, `DiaDPendingTradeBanner`). Se preparó un **traspaso parcial nuevo** para el siguiente hilo:
> [traspaso-m5-frente-trading-dia-d-cierre-2026-08-10.md](./traspaso-m5-frente-trading-dia-d-cierre-2026-08-10.md).

## 3. Reglas del juego (mantener en el nuevo chat)

- **Protocolo sagrado** del traspaso M5: FASE 1 diagnóstico (sin cambios) → FASE 2 plan atómico + aprobación →
  FASE 3 ejecución + **batería completa por cada paso** + `git commit --no-verify` + push + registro §7.6.
- **No tocar backend (M3/M4/M6)** ni **M7** (dev-stack: chunk >500 kB / crash Vite).
- **Batería TEST obligatoria en cada paso:** `pnpm --filter @bolsa/web test` (actual 140 ficheros / 707 tests).
  Verifica cobertura de tests del área tocada.
- Herramientas: `pnpm 10.12.1` sí en PATH; `uv` NO (usar `$env:USERPROFILE\.local\bin\uv.exe`). Shell es
  **PowerShell** (no usar `&&`; usar `;`).
- Commits con `git commit --no-verify` (CRLF/lint-staged/prettier). Push a
  `origin/stage/estudio-membership-operativa-2026-08-04`.
- Si el chat se satura, **cortar y preparar otro traspaso parcial** (documentar todo y actualizar GitHub) antes de
  continuar. No olvides las premisas: leer a fondo la doc de entrada y avisar al usuario cuando el chat se sature.

## 4. Estado de referencia para validar batería

- `pnpm --filter @bolsa/web typecheck` → exit 0
- `pnpm --filter @bolsa/web lint` → exit 0 (0e/0w)
- `pnpm --filter @bolsa/web test` → 140 ficheros / 707 tests, 0 fallos
- `pnpm --filter @bolsa/web build` → exit 0 (solo warnings code-splitting pre-existentes = M7)
