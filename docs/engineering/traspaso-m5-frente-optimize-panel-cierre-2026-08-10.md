# Traspaso M5 — CIERRE PARCIAL del frente `backtest-optimize-panel.tsx` (bajo + medio riesgo) · 2026-08-10

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD de referencia:** `3572739` (banner Prueba origen extraído) · árbol limpio · sincronizado con origin
**Origen/encadenamiento:** [traspaso-m5-frente-optimize-panel-entrada-2026-08-10.md](./traspaso-m5-frente-optimize-panel-entrada-2026-08-10.md) (entrada del frente) ·
[traspaso-m5-frontend-2026-08-10.md](./traspaso-m5-frontend-2026-08-10.md) (punto de entrada canónico de M5) ·
registro vivo [dev-continuation-plan-2026-08-09.md](./dev-continuation-plan-2026-08-09.md) §7.6.f / §7.6.g
**Estado de M5:** **EN PAUSA** salvo decisión del usuario. Este doc cierra **parcialmente** el frente: la **ola 1
(data-only, bajo riesgo)** y el bloque de **riesgo medio** (banner "Prueba origen") están ejecutados y pusheados;
quedan los **bloques de alto acoplamiento** pendientes, que requieren plan específico + aprobación explícita si se
retoman.

---

## 0. Objetivo del frente (recuperación de contexto)

Reducir `apps/web/src/features/backtests/backtest-optimize-panel.tsx` (era ~2.168 líneas al inicio del frente)
extrayendo sus **islas JSX presentacionales de bajo riesgo** como componentes Diseño B. Es un orquestador denso de la
funcionalidad de optimización del Lab (30+ `useState`, 6 `useRef`, 3 `useMutation`, 1 `useQuery` polling 1500 ms,
varios `useEffect` de orquestación: cola de jobs Coach→Lab, aplicación de semilla, adopción).

## 1. Ola 1 YA EJECUTADA (aprobada por el usuario, 2026-08-10)

FASE 2 (plan atómico) presentado y aprobado; FASE 3 ejecutada con **batería completa en verde por paso** (typecheck
exit 0 · lint 0e/0w · test **140/707** · build exit 0, warnings code-splitting = M7). Commits `--no-verify` + push.

| Paso | Commit | Componente (fichero) | Reducción orquestador |
|------|--------|----------------------|----------------------|
| C-OPT.4 | `e965d15` | `OptimizeCardHeader` (`optimize-card-header.tsx`) — incluye `AdoptionHintBanner`, que vivía dentro del header | −61 netas |
| C-OPT.1 | `edb0eb8` | `OptimizeSummaryStrip` (`optimize-summary-strip.tsx`) + `OptimizeEmptyTip` (`optimize-empty-tip.tsx`) | −25 |
| C-OPT.2 | `889570f` | `WalkForwardReportCard` (`optimize-walk-forward-report.tsx`) + `EdgeReportCard` (`optimize-edge-report.tsx`) + `CpcvReportCard` (`optimize-cpcv-report.tsx`) | −167 |
| C-OPT.5 | `3572739` | `OptimizeSeedBanner` (`optimize-seed-banner.tsx`) — banner "Prueba origen" (riesgo medio §1.2) | −55 netas |

**`backtest-optimize-panel.tsx`: 2.168 → 1.880 líneas (−288).**

**Ajuste del plan vs traspaso:** `ExperimentSummaryBanner` = `OptimizeSummaryStrip` (C-OPT.1); `AdoptionHintBanner`
vivía dentro del CardHeader → se extrajo en C-OPT.4. La ola 1 agota las **islas data-only / bajo riesgo** del fichero.
Los helpers de formateo migraron a los componentes; los imports quedan retirados del orquestador. Posteriormente se
extrajo además el bloque de **riesgo medio** (`OptimizeSeedBanner`, C-OPT.5), agotando también el §1.2 del traspaso.

## 2. Deuda anotada — bloques NO tocados (acoplamiento alto; requieren plan + aprobación)

1. **Formulario avanzado** (capital/barras/timeframe/métodos/OOS/WF/CPCV): ~15 props + ~9 callbacks de validación
   cruzada OOS/WF/CPCV. Alto acoplamiento.
2. **Editor de espacio de búsqueda**: handlers que mutan `space` vía `patchSma`/`patchRsi` (algorítmico).
3. **Botonera**: usa `handleRun`, `toggleMethod`, `setExpanded`.
4. **Comparación**: `BacktestOptimizeCompareTable` + `handleSave` + `rankBy` + `savedRowId`.
5. **Select familia**: usa `setFamilyAndSpace` multi-estado.
6. **Botones de adopción + banner de estado del Mejor vs ancla**: `bestVsAnchor`, `handleSave`, `saveStrategyMutation`,
   `savedRowId`.

> Extraer cualquiera de estos bloques implicaría mover lógica de estado/mutations/handlers fuera del orquestador o
> añadir muchos callbacks-closure. Según el criterio Diseño B de M5, **no se tocan** sin un plan específico y
> aprobación explícita, documentando el riesgo residual en cada caso.

## 3. Reglas del juego (mantener — protocolo sagrado M5)

- **FASE 1 → FASE 2 → FASE 3.** FASE 1, la ola 1 y el paso de riesgo medio (C-OPT.5) ya hechos. **Sin aprobación
  explícita no se toca código ni se commitea.**
- **Batería por paso (en `apps/web`):** `typecheck` exit 0 · `lint` 0 errores · `test` 140/707 · `build` exit 0.
- **No tocar** backend (M3/M4/M6) ni dev-stack (M7). El code-splitting >500 kB y el crash Vite F3.7 son **M7**.
- Shell **PowerShell** (no `&&`; usar `;`). Commits con `git commit --no-verify` (hook lint-staged/prettier CRLF).
  Push a `origin/stage/estudio-membership-operativa-2026-08-04`.
- Si el chat se satura, **cortar y preparar otro traspaso parcial** (documentar todo y actualizar GitHub) antes de
  continuar. Patrón **Diseño B**: extraer SOLO JSX presentacional a componentes delgados que reciben datos + callbacks
  del orquestador; la lógica de negocio permanece en el orquestador.

## 4. Estado de referencia para validar batería (HEAD `3572739`)

- Rama limpia y sincronizada con `origin/stage/estudio-membership-operativa-2026-08-04`.
- Batería verificada en cada paso: typecheck exit 0 · lint 0e/0w · test **140/707** · build exit 0.
- Fichero a modificar (si se continúa): `apps/web/src/features/backtests/backtest-optimize-panel.tsx` (**1.880
  líneas**). NO es área Coach/TOP; la regla `coach-top-quality.mdc` **NO** aplica.
- Estado del frente: agotadas las islas **data-only / bajo riesgo** (ola 1) y el bloque de **riesgo medio** (banner
  "Prueba origen"). **Solo quedan los 6 bloques de acoplamiento alto** del §2 → requieren plan específico + aprobación
  si se retoman (riesgo residual documentado).
- Restante de M5 (otros frentes): `chart-drawings-layer.tsx` (1.979, peor valor/riesgo), F4.8 `backtests-page.tsx`
  (5.127, ya sin islas JSX).

---

_Traspaso de cierre parcial del frente `backtest-optimize-panel.tsx` de M5. 2026-08-10._
