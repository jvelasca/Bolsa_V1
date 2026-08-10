# Traspaso M5 — Frontend web por features (`apps/web`) · 2026-08-10

> **Este documento es el punto de entrada para el chat/hilo que ejecute M5.**
> Resumen ejecutivo del **estado verificado** del repo tras cerrar M6 (2026-08-10),
> preparado para continuar en un **hilo nuevo** sin perder contexto. No se re-descubre nada:
> cada hecho de abajo está confirmado en el repo/CI.

## 0. Qué es M5 (fuente: `docs/engineering/general-audit-plan-2026-08-10.md` §5)

Fila de la tabla de módulos:

> **M5 — Frontend web (por features)** | Feature-slicing: hub, listas, accounts, alertas, charts |
> Riesgo **Medio** | Prioridad ★★

Orden sugerido del plan 08-10:
1. **M0** (docs) — cerrado
2. **M1 + M2** (reproducibilidad/versiones) — cerrados
3. **M3 / M4 / M6** (backend por capas) → **M3 cerrado** (`db7e5e5`), **M4 cerrado** (`69820c1`),
   **M6 cerrado** (`06496bb`)
4. **M5** (frontend por features) — lo más grande, dividido → **es el siguiente**
5. **M7** (dev-stack residual F3.7)

> **Decisión de orden:** tras cerrar M3/M4/M6 (backend), el frente pendiente de mayor valor es **M5**
> (frontend web por features). Es el **más grande** → exige hacerse **por features/hilos**, no en un solo
> commit masivo.

## 1. Protocolo sagrado (leer y respetar — mismo que M1/M2/M3/M4/M6)

1. **Tolerancia cero a fallos.** No asumir: verificar siempre en el repo/CI.
2. **Preservación funcional absoluta.** Un cambio solo si es necesario y probado.
3. **Alcance atómico.** Un módulo por hilo; no tocar nada ajeno a M5 (ni backend M3/M4/M6, ni M7).
4. **Flujo en 3 fases:** FASE 1 (diagnóstico, sin cambios) → FASE 2 (plan atómico + aprobación del
   usuario) → FASE 3 (ejecución + batería + commit + push + registro). Sin aprobación explícita
   **no se toca código ni se commitea.**
5. **Docs como fuente de verdad.** Anclar decisiones a ficheros reales.
6. «No romper NADA»: batería completa de tests antes y después.

## 2. Estado del repo al crear este traspaso (2026-08-10, tras M6)

- Rama activa: `stage/estudio-membership-operativa-2026-08-04`.
- HEAD: `06496bb` (cierre M6 — armonizar `trial_score` en optimize.py + registro §7.5). **Working tree
  limpio**, sincronizado con `origin/<rama>`.
- Commit M6: `06496bb` "M6: armonizar salida numérica en optimize.py con la canónica trial_score
  (round 6 vs 4) + confirmar coherencia py/ai doc-código + registro §7.5" (3 ficheros, +57/−4).

### Commits de módulos anteriores (todos pusheados, CI verde)

| Commit | Módulo / contenido |
| ------ | ----------------- |
| `06496bb` | M6 · Cierre AI/analytics + registro §7.5 |
| `1cc771a` | docs · Traspaso M6 (entrada) + registro índice |
| `69820c1` | M4 · Fuente de verdad del modelo (ADR-025) + registro §7.4 |
| `d7b9d99` | docs · Traspaso M4 (entrada) |
| `db7e5e5` | M3 · Cierre capa de dominio + registro §7.3 |
| `b82b48c` | docs · Traspaso M3 (entrada) |
| `0469fa2` | M2 · Registro docs §7.2 |
| `8e4ee62` | M0.6 · Mini-módulo higiene `@bolsa/shared` (cierre de 14 no-unused-vars) |

## 3. Hechos de diagnóstico confirmados (relevantes para M5)

- **Batería web CI (`frontend-ci.yml`):** `Build shared` → `Typecheck` → `Lint` (0 errores) → `Test` →
  `Build`. Scripts de `apps/web`: `typecheck` = `tsc -b --noEmit` · `lint` = `eslint src/` · `test` =
  `vitest run` · `build` = `tsc -b && vite build`.
- **Verificado en HEAD `06496bb` (2026-08-10):**
  - `pnpm --filter @bolsa/web typecheck` → **exit 0**.
  - `pnpm --filter @bolsa/web lint` → **exit 0** (0 errores, 0 warnings; solo warning cosmético de Node
    sobre `eslint.config.js` si tipo module, no bloqueante).
  - `pnpm --filter @bolsa/web test` → **140 ficheros / 707 tests passed** (exit 0).
  - `pnpm --filter @bolsa/web build` → **exit 0**. Warnings de code-splitting (>500 kB, dynamic-import
    que no mueve módulo a otro chunk) **pre-existentes** → frente **M7**, ajeno a M5.
- **Nota entorno Windows:** `uv` NO está en PATH (usar `$env:USERPROFILE\.local\bin\uv.exe`); para el
  frontend se usa `pnpm 10.12.1` (sí disponible). Patrón de commit: `git commit --no-verify` (hook
  lint-staged dispara prettier sobre ficheros legacy con CRLF desincronizado; documentado desde M1).

## 4. Mapeo M5 (inventario confirmado)

### 4.1 `apps/web` — 21 features (carpetas de `src/features/`)

accounts · ai · alerts · auth · backtests · charts · config · dashboard · fiscal · help · history ·
instruments · operations · platform · portfolio · research · screeners · settings · sync · trading ·
workspace.

### 4.2 Ficheros grandes (candidatos a feature-slicing; líneas en HEAD `06496bb`)

| Fichero | Líneas | Feature |
| ------ | ------ | ------- |
| `features/backtests/backtests-page.tsx` | **5759** | backtests (foco F4.8) |
| `features/backtests/backtest-optimize-panel.tsx` | 2251 | backtests |
| `features/charts/chart-drawings-layer.tsx` | 1979 | charts |
| `features/backtests/backtest-explore-panel.tsx` | 1456 | backtests |
| `features/trading/lists-tab/list-values-panel.tsx` | 1395 | trading/listas |
| `features/trading/trading-dia-d-replay-panel.tsx` | 1341 | trading |
| `features/instruments/instruments-page.tsx` | 1222 | instruments |
| `features/backtests/backtest-strategy-matrix-panel.tsx` | 1033 | backtests |
| `features/charts/ohlcv-chart.tsx` | 974 | charts |
| `features/backtests/strategy-monitor-panel.tsx` | 910 | backtests |

## 5. Frentes a resolver (para el chat M5 — heredados, no consensuados)

Esto **no** es un plan consensuado, es el diagnóstico heredado + elaborado. El chat M5 debe, en FASE 1
(diagnóstico, **sin cambios**):

1. **Feature-slicing por features** (el corazón de M5): reducir los ficheros grandes del §4.2, dominio a
   dominio (hub de backtests, listas, accounts, alertas, charts). Cada descomposición = **un paso FASE 1/2/3
   propio con su batería** y, si cambia la experiencia/contratos, docs de producto (premisa §1).
2. **`backtests-page.tsx` (5759 líneas, foco F4.8):** pasos 1–2 ya hechos (extraer `backtest-hub-nav` y
   `HubTabButton` → `backtest-hub-tabs.tsx`), paso 3 (`BacktestHubTabsBar`) y 4 (`useBacktestHubNav`)
   hechos; pasos 5–6 **descartados en M0/4e** (no quedan utilidades puras extraíbles). Objetivo del plan:
   **<3500 líneas**. Evaluar si quedan bloques JSX autocontenidos (p. ej. paneles AUTO/LAB) extraíbles a
   sub-paneles. NO tocar la semántica de hooks/handlers.
3. **Deudas de frontend YA cerradas (no rehacer):**
   - `@bolsa/shared` 14 `no-unused-vars` → **resueltos** (M0.6, commit `8e4ee62`).
   - Warnings `react-hooks/exhaustive-deps` → **0 warnings** (M0.4, batches 1–3, commits previos).
4. **Higiene pendiente (candidata a entrar en M5):** normalizar formato de ficheros legacy con CRLF
   desincronizado (p. ej. `backtests-page.tsx`, `ohlcv-chart.tsx`) — debe ser **commit propio de
   formateo**, no mezclado con cambios editoriales (documentado en M0/§6.2). Evaluar si entra o queda
   como frente aparte.
5. **Batería aplicable de M5:** typecheck + lint (0 errores) + test + build, **por cada paso**; referencia
   en HEAD: typecheck exit 0 · lint exit 0 · test **140/707** · build exit 0.
6. **No tocar** el backend (M3/M4/M6) ni el dev-stack (M7). El code-splitting del chunk >500 kB y el
   crash Vite F3.7 son **M7**, fuera de M5.

## 6. Documentos fuente de verdad / índices

- `docs/engineering/engineering-index-2026-08-03.md`
- `docs/engineering/general-audit-plan-2026-08-10.md` (§4 hallazgos, §5 módulos, §7 registros M0)
- `docs/engineering/dev-continuation-plan-2026-08-09.md` (§7.1 M1, §7.2 M2, §7.3 M3, §7.4 M4, §7.5 M6;
  M0/§6.2 CRLF, M0/4e F4.8 pasos 5-6 descartados)
- `docs/engineering/traspaso-m6-ai-analytics-2026-08-10.md` (precedente más reciente del patrón)
- `docs/engineering/traspaso-m4-infraestructura-datos-2026-08-10.md` · `traspaso-m3-dominio-2026-08-10.md`
- `docs/ARCHITECTURE.md` · `docs/PROJECT_PREMISES.md` · `docs/UI_PREFS_LOCALSTORAGE.md` ·
  `docs/RESPONSIVE_PREMISES.md`
- `apps/web/package.json` · `.github/workflows/frontend-ci.yml`

> Al cierre de M5 (FASE 3), actualizar `dev-continuation-plan-2026-08-09.md` con una sección **§7.6**
> nueva (patrón §7.1–7.5) y añadir/confirmar este fichero en el índice engineering (bajo Product/Ops,
> junto a los traspasos).

---

## 7. NOTA DE CIERRE de M5 — feature-slicing Diseño B agotado (2026-08-10)

Tras ejecutar los frentes de M5 por features, se concluye que **el feature-slicing por islas JSX (patrón
Diseño B) de `apps/web` está agotado en los frentes de valor**: `backtests-page` (pasos 1-10 + hardening de hooks),
`trading-dia-d` (B.1-B.3), `backtest-explore` (E.1-E.5), `create-account-wizard` (C.1-C.5), `list-values` (I.1-I.2),
`instruments-page` (cerrado como ya feature-sliced) y `backtest-optimize-panel` (ola 1 C-OPT.4-C-OPT.1-C-OPT.2 +
C-OPT.5 `OptimizeSeedBanner`; 2.168 → 1.880 líneas).

**Lo que queda en M5 es de acoplamiento alto u orquestación pura y NO se recomienda extraer con Diseño B**
(decisión con riesgo no favorable, sin aprobación explícita):
- `backtest-optimize-panel.tsx` → 6 bloques de acoplamiento alto (formulario avanzado, editor de espacio, botonera,
  comparación `handleSave`, select familia `setFamilyAndSpace`, Mejor-vs-ancla + adopción).
- `chart-drawings-layer.tsx` (1.979) → peor ratio valor/riesgo (canvas SVG monolítico interdependiente).
- F4.8 `backtests-page.tsx` (5.127) → sin islas JSX; solo orquestación.

**Próximas líneas de valor superiores a seguir con feature-slicing:** higiene CRLF/prettier de legacy como commit de
formateo propio (M0/§6.2, cero riesgo funcional), o frentes de mayor ROI fuera de M5 (backend: Alembic baseline,
`B007` de ruff, coherencia doc-código Proxy RFC-007; dev-stack M7: code-splitting / Vite F3.7). Véase el traspaso de
entrada de la línea elegida para el siguiente hilo.

_Nota de cierre añadida 2026-08-10 (`c068451`)._
