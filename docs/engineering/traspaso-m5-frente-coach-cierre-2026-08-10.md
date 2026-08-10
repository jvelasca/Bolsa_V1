# Traspaso parcial — M5 frente Coach + frentes alternativos (frontend web por features)

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD:** `cbc7aff` (cierre frente Coach+M5 + traspaso parcial nuevo) · **Árbol limpio** · paso Lab `8ae445b`
**Origen:** [traspaso-m5-f4-8-coach-lab-2026-08-10.md](./traspaso-m5-f4-8-coach-lab-2026-08-10.md) + registro **§7.6**
de [dev-continuation-plan-2026-08-09.md](./dev-continuation-plan-2026-08-09.md)

---

## 1. Qué se cerró (hilo Coach + Lab, paso Lab)

Feature-slicing de `apps/web/src/features/backtests/backtests-page.tsx`: de **5.759 → 5.152 líneas**, en **9 pasos
atómicos** + registro, **cada uno con batería completa en verde** (typecheck exit 0 · lint 0e/0w · test **140/707** ·
build exit 0; warnings code-splitting pre-existentes = **M7, fuera de alcance**). Commits `git commit --no-verify`
(hook lint-staged/prettier CRLF) + push a origin.

| Paso | Commit | Componente extraído |
|------|--------|---------------------|
| 1–8 | `0fce03b`…`c0dfe24` | `BacktestResult*` / `BacktestWizard*` (hilo previo) |
| 9 | `8ae445b` | `BacktestResultFocusLab` (hilo Coach + Lab) |
| — | `e746ed8` | registro §7.6 + traspaso Coach+Lab actualizados |

**Paso 9 (Lab, Diseño B):** extraído el bloque `resultFocus === "lab"` a `backtest-result-focus-lab.tsx`
(fine wrapper, ~14 props). Los callbacks acoplados (`onClearZoneSeed`, `onReanalyzeWithCoach`,
`onAutoHandoffStatus`, `onGoToCoach`) **permanecen en el orquestador** (Diseño B aprobado frente al Diseño A de
~200 líneas/27 props): la lógica de cierre de ciclo (`settleFullCycle` vía `onAutoHandoffStatus`) no se movió fuera
del orquestador, consistente con los pasos 1–8.

## 2. Punto de entrada del siguiente hilo

### 2.1 Estado de `backtests-page.tsx` (→ 5.152 líneas, objetivo F4.8 <3.500)

- Queda **sin extraer** el result focus **Coach** (`BacktestExploreRanking`, ~130 líneas), en la pestaña
  `tab === "run"`, bloque `{exploreRows.length > 0 && (resultFocus === "coach" || (Boolean(listAutoBoard) &&
  fullCycleActive && coachPass === "post_lab"))}` + los avisos «Sin lote de coach aún» / «Lista AUTO en marcha»
  (~150 líneas totales en `backtests-page.tsx`).
- **Acoplamiento (FASE 1 verificado):** ~30+ props con callbacks inline de ciclo: `onAutoSaveStatus` (llama
  `settleFullCycle` + `listAutoRef`), `onAwaitingAckChange` (toca `setAwaitingAck`/`setAwaitingAckStage` +
  `coachPass`), `onSelectRun`, `equityByRunId` (usa `queryClient`), `onCoachGateChange`, `onOptimizeCandidate`,
  `onOptimizeSemifinal`. 3 bloques condicionales ligados a `listAutoBoard`/`fullCycleActive`.

### 2.2 Frentes alternativos de M5 — evaluados, **no** ofrecen slicing JSX de bajo riesgo

| Frente | Líneas | Diagnóstico (FASE 1) |
|--------|--------|----------------------|
| `trading/lists-tab/list-values-panel.tsx` | 1.395 | **Ya feature-sliced** (`ListCarousel`, `ListItemAccordion`, `SortedApiList`, `SortedVisualizationList`, `PortfolioKeyboardList`, `PendingOrdersKeyboardList`, banner Estudio…). Resta lógica de orquestación. |
| `instruments/instruments-page.tsx` | 1.222 | **Ya feature-sliced** (`InstrumentsHubFilterBar`, `InstrumentsHubSplitLayout`, `SyncBadge`, `ListsCell`, `ScoreCell`, `SeguimientoCell`, `PortfolioCell`). Resta orquestación. |
| `charts/chart-drawings-layer.tsx` | 1.979 | Canvas SVG monolítico + editor interdependiente (estado de dibujo, coordenadas, eventos). Peor ratio valor/riesgo. |

### 2.3 Opciones para el siguiente hilo

1. **Extraer el Coach con Diseño B** (thin wrapper ~30+ props, callbacks de ciclo en el orquestador): -~50–60
   líneas reales, sin tocar la semántica de ciclo. Última isla JSX de M5.
2. **Cerrar M5** en el estado actual (paso 9 + registro) y mover esfuerzo a otro frente/feature (p. ej. ficheros
   <1.200 líneas de §4.2 del traspaso M5, o higiene M0/§6.2 CRLF de backtests-page como commit de formateo propio).
3. **Refactor a custom hooks** (extraer handlers/queries de orquestación de los frentes grandes) — más invasivo,
   fuera del patrón de slicing JSX aprobado; requiere recalibración explícita.

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
