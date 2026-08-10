# Traspaso parcial — M5 frente `trading-dia-d-replay-panel.tsx` (feature-slicing) · cierre B.1+B.2

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD:** `8c1a4bc` (cabecera traspaso para B.1+B.2) · **Árbol limpio** · paso Lab `8ae445b` · paso Coach `d3315e8`
**Origen:** [traspaso-m5-frente-coach-cierre-2026-08-10.md](./traspaso-m5-frente-coach-cierre-2026-08-10.md) (§2.3
reorientación a otro frente) + registro **§7.6.b** de
[dev-continuation-plan-2026-08-09.md](./dev-continuation-plan-2026-08-09.md)

---

## 1. Qué se cerró en este hilo (frente trading-dia-d, pasos B.1 y B.2)

Tras agotar las islas JSX de `backtests-page.tsx` (paso 10, `BacktestResultFocusCoach`, `d3315e8`), este hilo
**reorientó M5 a otro frente** según §2.3 del traspaso M5. En FASE 1 se diagnosticó [mediante subagente de
exploración](22e3ea27-85b9-442b-a55e-e3130616353a) + lectura directa que `trading-dia-d-replay-panel.tsx`
(1.341 líneas, panel **Modo DÍA D**) era el mejor candidato de valor/riesgo: ya parcialmente sliced
(`BacktestReplayChart`, `BacktestMovieHud`, `BacktestEquityChart`, `DiaDReconciliationPanel`, `DiaDArchivePanel`)
y con **3 bloques JSX inline extraíbles** como thin wrappers (tabla de Operaciones, banner pending, panel Informe).

**Pasos ejecutados en este hilo** — cada uno con **batería completa en verde** (typecheck exit 0 · lint 0e/0w ·
test **140/707** · build exit 0, warnings code-splitting pre-existentes = M7), `git commit --no-verify`
(CRLF/lint-staged/prettier) + push a origin:

| Paso | Commit | Componente extraído | Props | Reducción orquestador |
|------|--------|---------------------|-------|----------------------|
| B.1 | `1303610` | `DiaDTradesPanel` (tabla de Operaciones, `apps/web/src/features/trading/dia-d-trades-panel.tsx`) | 4 | −58 líneas (~1.341 → ~1.283) |
| B.2 | `041457f` | `DiaDPendingTradeBanner` (banner propuesta pending, `apps/web/src/features/trading/dia-d-pending-trade-banner.tsx`) | 4 | −11 líneas (~1.283 → ~1.272) |

**Patrón — Diseño B (consistent con hilo previo):** thin wrappers con los callbacks de ciclo/estado **en el
orquestador** (`decideGate`, `setFocusTimestamp`, `replayCursor`, `pendingTrade`, `session.mode`) como props;
el JSX presentacional se traslada fielmente. No se mueve lógica de estado/handlers.

**Registros docs commiteados:** `0b2ffa6` (cabecera B.1) y `8c1a4bc` (cabecera B.1+B.2).
**Cobertura verificada:** el feature `trading/dia-d` tiene tests de lógica (`dia-d-gate-equity`,
`dia-d-evidence-archive-io`, `dia-d-verify-continuity`, `dia-d-session-evidence`, `dia-d-reconciliation`,
`dia-d-favorites`, `dia-d-trading-session-store`); los bloques extraídos son JSX presentacional sin test directo
→ la batería 140/707 pasa intacta en cada paso.

---

## 2. Punto de entrada del siguiente hilo

### 2.1 Estado de `trading-dia-d-replay-panel.tsx` (→ ~1.272 líneas)

- **Extraídos:** B.1 tabla de Operaciones (`DiaDTradesPanel`), B.2 banner de propuesta (`DiaDPendingTradeBanner`).
- **Queda por extraer — B.3: panel de Informe de sesión.** **OJO (hallazgo de FASE 1 verificado):** el informe se
  renderiza en **DOS ramas** que comparten el mismo `sessionReportBody` (derivado memoizado, ~línea 723):
  1. **Desktop** (`isWide && report`, ~líneas 1110-1181): bloque con `PanelResizeHandle` (drag para
     `layout.reportWidthPct`), toggle `reportOpen`/`setReportOpen` y `<aside id="dia-d-session-report-panel">`
     con `sessionReportBody`.
  2. **Móvil** (`!isWide && report`, ~líneas 1182-1202): `<details>` con `summary` (colapsar/expandir) y
     `<div id="dia-d-session-report-panel">` con el mismo `sessionReportBody`.
  → Extraer B.3 **no es un thin wrapper de un solo bloque**; implica decidir cómo encapsular dos ramas de
  presentación + el drag-resize del desktop. Acoplamiento **medio**: usa `sessionReportBody`, `reportOpen`,
  `setReportOpen`, `layout.reportWidthPct`, `pendingReportW.current`, `clampReportWidthPct`, `movieRowRef`.
- Resta del fichero: orquestación (replay movie, gate, IA narrative, layout drag/resize, archivo). No hay más
  islas JSX de bajo riesgo detectadas salvo B.3.

### 2.2 Otros frentes de M5 (diagnóstico heredado — NO rehacer salvo cambio)

- `list-values-panel.tsx` (1.395), `instruments-page.tsx` (1.222): **ya feature-sliced**. Resta orquestación.
- `chart-drawings-layer.tsx` (1.979): canvas SVG monolítico, peor valor/riesgo.
- Diagnosticados en este hilo (acoplamiento alto → descartados): `backtest-optimize-panel.tsx` (2.251),
  `backtest-strategy-matrix-panel.tsx` (1.033), `ohlcv-chart.tsx` (974, sin JSX extraíble);
  `backtest-explore-panel.tsx` (1.456, MEDIO).
- El objetivo F4.8 (`backtests-page.tsx` <3.500, actual 5.127) sigue lejos porque el resto es orquestación, no JSX.

### 2.3 Opciones para el siguiente hilo

1. **Completar B.3** (panel Informe sesión) en `trading-dia-d-replay-panel.tsx` — el cierre del frente. Requiere
   FASE 1 propio primero (ver hallazgo de las 2 ramas + drag-resize); riesgo medio.
2. **Cerrar el frente trading-dia-d en el estado actual** (B.1+B.2) y mover esfuerzo a otro frente de M5
   (p. ej. `backtest-explore-panel.tsx` 1.456 (MEDIO), o higiene M0/§6.2 CRLF de backtests-page como commit de
   formateo propio).
3. **Refactor a custom hooks** (extraer handlers/queries de orquestación de los frentes grandes) — más invasivo,
   requiere recalibración explícita del patrón.

---

## 3. Reglas del juego (mantener en el nuevo chat)

- **Protocolo sagrado** del traspaso M5: FASE 1 diagnóstico (sin cambios) → FASE 2 plan atómico + aprobación →
  FASE 3 ejecución + **batería completa por cada paso** (typecheck + lint 0 errores + **test** + build) +
  `git commit --no-verify` + push + registro §7.6.
- **No tocar backend (M3/M4/M6)** ni **M7** (dev-stack: chunk >500 kB / crash Vite).
- **Batería TEST obligatoria en cada paso:** `pnpm --filter @bolsa/web test` (actual 140 ficheros / 707 tests).
  Verifica cobertura de tests del área tocada.
- Herramientas: `pnpm 10.12.1` sí en PATH; `uv` NO (usar `$env:USERPROFILE\.local\bin\uv.exe`). Shell es
  **PowerShell** (no usar `&&`; usar `;`).
- Commits con `git commit --no-verify` (CRLF/lint-staged/prettier). Push a
  `origin/stage/estudio-membership-operativa-2026-08-04`.
- Si el chat se satura, **cortar y preparar otro traspaso parcial** (documentar todo y actualizar GitHub) antes de
  continuar. No olvides las premisas: leer a fondo la doc de entrada y avisar al usuario cuando el chat se sature.
- Si se toca el área Coach/TOP, aplicar la regla `coach-top-quality.mdc` (batería `pnpm test:coach`).

## 4. Estado de referencia para validar batería

- `pnpm --filter @bolsa/web typecheck` → exit 0
- `pnpm --filter @bolsa/web lint` → exit 0 (0e/0w)
- `pnpm --filter @bolsa/web test` → 140 ficheros / 707 tests, 0 fallos
- `pnpm --filter @bolsa/web build` → exit 0 (solo warnings code-splitting pre-existentes = M7)
- Ficheros nuevos de este hilo: `apps/web/src/features/trading/dia-d-trades-panel.tsx`,
  `apps/web/src/features/trading/dia-d-pending-trade-banner.tsx`, ambos importados desde
  `trading-dia-d-replay-panel.tsx`.
