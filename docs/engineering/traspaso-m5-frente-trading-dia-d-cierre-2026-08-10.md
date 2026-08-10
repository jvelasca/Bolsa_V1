# Traspaso parcial — M5 frente `trading-dia-d-replay-panel.tsx` (feature-slicing) · cierre B.1+B.2+B.3

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD:** `a8fede3` (paso B.3: DiaDSessionReportPanel — frente **cerrado**) · pasos: Lab `8ae445b` · Coach `d3315e8` ·
B.1 `1303610` · B.2 `041457f` · B.3 `a8fede3`
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
| B.3 | `a8fede3` | `DiaDSessionReportPanel` (panel Informe sesión, `apps/web/src/features/trading/dia-d-session-report-panel.tsx`) | 6 + `variant` | −67 líneas (~1.272 → ~1.205) — **cierra el frente** |

**Patrón — Diseño B (consistente con hilo previo):** thin wrappers con los callbacks de ciclo/estado **en el
orquestador** (`decideGate`, `setFocusTimestamp`, `replayCursor`, `pendingTrade`, `session.mode`) como props;
el JSX presentacional se traslada fielmente. No se mueve lógica de estado/handlers.

**B.3 — hallazgo de FASE 1 (verificado):** el informe se renderiza en **DOS sitios del DOM** (no dos ramas
intercambiables): **desktop** (`isWide && report`) vive **dentro** de `<div ref={movieRowRef}>` como flex-child
horizontal (`<PanelResizeHandle>` + `<aside>` redimensionable, o la pestaña vertical colapsada); **móvil**
(`!isWide && report`) vive **debajo** del movie-row como `<details>`. Por ello `DiaDSessionReportPanel` usa una prop
`variant: 'desktop' | 'mobile'` y se despliega en **dos sitios** guardados por `isWide`, preservando exactamente el
DOM. El cuerpo compartido (`sessionReportBody`) se pasa como `body`. **La lógica de drag-resize permanece en el
orquestador** (`reportPanelProps.onResizeDrag`/`onResizeDragEnd`, que usan `movieRowRef.current`,
`pendingReportW.current`, `clampReportWidthPct`, `pxToPct`, `setLayout`, `persistLayout`) → no se rompe el layout
drag-resize. `sessionReportBody` (~240 líneas, acoplamiento alto a archive/evidence/mutations) no se extrae.

**Registros docs commiteados:** `0b2ffa6` (cabecera B.1) y `8c1a4bc` (cabecera B.1+B.2).
**Cobertura verificada:** el feature `trading/dia-d` tiene tests de lógica (`dia-d-gate-equity`,
`dia-d-evidence-archive-io`, `dia-d-verify-continuity`, `dia-d-session-evidence`, `dia-d-reconciliation`,
`dia-d-favorites`, `dia-d-trading-session-store`); los bloques extraídos son JSX presentacional sin test directo
→ la batería 140/707 pasa intacta en cada paso.

---

## 2. Punto de entrada del siguiente hilo

### 2.1 Estado de `trading-dia-d-replay-panel.tsx` (→ ~1.205 líneas) — frente CERRADO

- **Extraídos (B.1-B.3):** `DiaDTradesPanel` (tabla de Operaciones), `DiaDPendingTradeBanner` (banner propuesta),
  `DiaDSessionReportPanel` (panel Informe de sesión, **dos ramas** desktop+móvil).
- **B.3 resuelto con Diseño B:** hallazgo verificado de que el informe vive en **DOS sitios del DOM** (desktop dentro
  del movie-row con drag-resize; móvil `<details>` debajo). `DiaDSessionReportPanel` acepta `variant:
  'desktop' | 'mobile'` y se despliega en dos sitios guardados por `isWide`; el cuerpo compartido (`sessionReportBody`)
  se pasa como `body`, y la lógica de drag-resize queda en el orquestador (`reportPanelProps.onResizeDrag`/
  `onResizeDragEnd` con `movieRowRef`/`pendingReportW`/`clampReportWidthPct`/`pxToPct`/`setLayout`/`persistLayout`).
- Resta del fichero: **orquestación** (replay movie, gate, IA narrative, layout drag/resize, archivo). **No quedan
  islas JSX autocontenidas de bajo riesgo** → el frente trading-dia-d está **cerrado** para feature-slicing.

### 2.2 Otros frentes de M5 (diagnóstico heredado — NO rehacer salvo cambio)

- `list-values-panel.tsx` (1.395), `instruments-page.tsx` (1.222): **ya feature-sliced**. Resta orquestación.
- `chart-drawings-layer.tsx` (1.979): canvas SVG monolítico, peor valor/riesgo.
- Diagnosticados en este hilo (acoplamiento alto → descartados): `backtest-optimize-panel.tsx` (2.251),
  `backtest-strategy-matrix-panel.tsx` (1.033), `ohlcv-chart.tsx` (974, sin JSX extraíble);
  `backtest-explore-panel.tsx` (1.456, MEDIO).
- El objetivo F4.8 (`backtests-page.tsx` <3.500, actual 5.127) sigue lejos porque el resto es orquestación, no JSX.

### 2.3 Opciones para el siguiente hilo (frente trading-dia-d CERRADO)

1. **Mover esfuerzo a otro frente de M5**: `backtest-explore-panel.tsx` (1.456, **MEDIO**) — el candidato restante de
   mejor valor/riesgo; o `backtest-optimize-panel.tsx`/`backtest-strategy-matrix-panel.tsx` (acoplamiento alto,
   requerirían FASE 1 detallada).
2. **Higiene M0/§6.2 CRLF** de `backtests-page.tsx` como commit de formateo propio (M0 out-of-M5).
3. **Refactor a custom hooks** (extraer handlers/queries de orquestación de los frentes grandes) — más invasivo,
   requiere recalibración explícita del patrón.

> **Progreso (2026-08-10, opción 1 EN CURSO):** el siguiente hilo inició `backtest-explore-panel.tsx` con **E.1
> (BacktestExploreBH) + E.2 (BacktestExploreHeader)**, área Coach/TOP (**regla `coach-top-quality.mdc`**, batería
> `pnpm test:coach`), HEAD `72061fd`. Traspaso del frente:
> [traspaso-m5-frente-backtest-explore-cierre-2026-08-10.md](./traspaso-m5-frente-backtest-explore-cierre-2026-08-10.md).

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
  `apps/web/src/features/trading/dia-d-pending-trade-banner.tsx`,
  `apps/web/src/features/trading/dia-d-session-report-panel.tsx`, importados desde
  `trading-dia-d-replay-panel.tsx`.
