# Traspaso parcial — M5 hilo F4.8 · Coach + Lab (frontend web por features)

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD al crear:** `30a2785` (registro §7.6) · **HEAD al ejecutar el paso Lab:** `8ae445b`
**Origen:** [traspaso-m5-frontend-2026-08-10.md](./traspaso-m5-frontend-2026-08-10.md) + registro **§7.6** de
[dev-continuation-plan-2026-08-09.md](./dev-continuation-plan-2026-08-09.md)

---

## 1. Qué se cerró (hilo F4.8 previo)

Feature-slicing de `apps/web/src/features/backtests/backtests-page.tsx`: de **5.759 → 5.179 líneas (-580)**,
en 8 pasos atómicos + registro, **cada uno con batería completa en verde** (typecheck exit 0 · lint 0e/0w ·
test **140/707** · build exit 0; warnings code-splitting pre-existentes = **M7, fuera de alcance**).
Commits `git commit --no-verify` (hook lint-staged/prettier CRLF) + push a origin.

| Paso | Commit | Fichero extraído |
|------|--------|------------------|
| 1 | `0fce03b` | `backtest-result-fundamental.tsx` |
| 2 | `4baa43e` | `backtest-result-ranking.tsx` |
| 3 | `7498ee1` | `backtest-wizard-mass-compare.tsx` |
| 4 | `21b9187` | `backtest-wizard-advanced-options.tsx` |
| 5 | `8e693c9` | `backtest-wizard-list-auto.tsx` |
| 6 | `2ecfd77` | `backtest-wizard-probe-list.tsx` |
| 7 | `13d52af` | `backtest-result-detail.tsx` |
| 8 | `c0dfe24` | `backtest-result-focus-finalists.tsx` |
| — | `30a2785` | registro §7.6 en `dev-continuation-plan-2026-08-09.md` |
| 9 | `8ae445b` | `backtest-result-focus-lab.tsx` (hilo Coach + Lab, paso Lab) |

> **Progreso (2026-08-10):** el hilo Coach + Lab extrajo el **Lab** en el paso 9 → `BacktestResultFocusLab`
> (Diseño B). `backtests-page.tsx` queda en **5.152 líneas (-607)**. Solo queda el **Coach** por decidir (ver §2.2).

**Cobertura verificada:** feature `backtests` tiene **74 ficheros de test** que cubren la lógica subyacente de
los módulos extraídos (`backtest-period`, `backtest-mass-compare`, `backtest-list-auto*`, `backtest-hub-tabs/nav`,
etc.). La batería `test 140/707` pasó en cada paso.

## 2. Punto de entrada del siguiente hilo (Coach + Lab)

Los bloques de **result focus Coach** y **Lab** de `backtests-page.tsx` quedan **sin extraer** por recalibración
aprobada: son los islands de mayor acoplamiento con el orquestador del ciclo completo. Objetivo final F4.8:
`backtests-page.tsx` **< 3.500 líneas** (faltan ~1.700 para llegar; este hilo es una parte del total).

> **Progreso del hilo Coach + Lab (2026-08-10):** el bloque **Lab ya se extrajo** en el paso 9 (`8ae445b`) →
> `BacktestResultFocusLab` (~fine wrapper con callbacks en el orquestador, Diseño B). Queda **solo el Coach**
> (`BacktestExploreRanking`, ~130 líneas) sin extraer por acoplamiento ~30+ props (ver §2.2 opción 2 vs 3).

### 2.1 Bloques candidatos (actuales en HEAD `8ae445b`, en la pestaña `tab === "run"`)

- **Lab** — **EXTRAÍDO** en `BacktestResultFocusLab` (`backtest-result-focus-lab.tsx`), paso 9 `8ae445b`. El
  `onAutoHandoffStatus` (~130 líneas, lógica de cierre de ciclo) **permanece en el orquestador** como prop.

### 2.2 Recomendación de estrategia

Dado el acoplamiento, **no** transpone el bloque entero a props (serían 40+ props/handlers). Opciones por orden
de riesgo creciente:
1. **Lab — YA EXTRAÍDO** (paso 9 `8ae445b` → `BacktestResultFocusLab`, Diseño B): computados (`labZones`,
   `optimizeSeed`, `coachProfilePolicy.*`) como props y los handlers acoplados (`reanalyzeLabWithCoach`,
   `setLabZones`, `setOptimizeSeed`, `onAutoHandoffStatus`, `onGoToCoach`) como callbacks **en el orquestador**.
2. Queda **Coach** (`<BacktestResultFocusCoach>`): requiere decidir qué callbacks acoplados
   (`onAwaitingAckChange`, `onCoachGateChange`, `onAutoSaveStatus`, `onSelectRun`, `onOptimizeCandidate`,
   `onOptimizeSemifinal`) se pasan tal cual y cuáles se reescriben con los setters que recibe.
3. Alternativa segura: **detener** la descomposición de Coach (quedaría en ~30+ props) y dedicar el resto de
   M5 a los **otros frentes** de feature-slicing del traspaso M5 (list-values, instruments, charts) donde el
   valor/riesgo es mejor.

## 3. Reglas del juego (mantener en el nuevo chat)

- **Protocolo sagrado** del traspaso M5: FASE 1 diagnóstico (sin cambios) → FASE 2 plan atómico + aprobación →
  FASE 3 ejecución + **batería completa por cada paso** (typecheck + lint 0 errores + **test** + build) +
  `git commit --no-verify` + push + registro §7.6.
- **No tocar backend (M3/M4/M6)** ni **M7** (dev-stack: chunk >500 kB / crash Vite; ya documentado en el plan).
- **Batería TEST obligatoria en cada paso** (solicitud explícita del usuario): `pnpm --filter @bolsa/web test`
  (actual 140 ficheros / 707 tests). Verifica cobertura de tests del área tocada.
- Herramientas: `pnpm 10.12.1` sí en PATH; `uv` NO (usar `$env:USERPROFILE\.local\bin\uv.exe`). Shell es
  **PowerShell** (no usar `&&` como separador; usar `;`).
- Commits con `git commit --no-verify` (CRLF/lint-staged/prettier). Push a
  `origin/stage/estudio-membership-operativa-2026-08-04`.
- Si el chat se satura, **cortar y preparar otro traspaso parcial** (documentar todo y actualizar GitHub) antes de
  continuar.

## 4. Estado de referencia para validar batería

- `pnpm --filter @bolsa/web typecheck` → exit 0
- `pnpm --filter @bolsa/web lint` → exit 0 (0e/0w)
- `pnpm --filter @bolsa/web test` → 140 ficheros / 707 tests, 0 fallos
- `pnpm --filter @bolsa/web build` → exit 0 (solo warnings code-splitting pre-existentes = M7)
- Ficheros extraídos en el hilo: los 8 `backtest-*.tsx` arriba, todos importados desde `backtests-page.tsx`
  (tree-shaking/imports coherentes, sin imports huérfanos tras limpieza en cada paso).
