# Evidencia `v2.88.94-beta` — `UI`: **UI 7.0 — cierre semántico y de usuario básico (UI-only · Δ motor = 0)**

**Producto:** `V2.88.94-beta` · **Package:** `2.11.94-beta` · **AsOf:** 2026-10-08. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`**: todo el diff vive en `apps/web/src/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D. **Contrato HTTP sin cambio.** Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.94-beta` junto al `package.json` (guardián `test_dia_d_bump_guard`).

> **Nota de árbol (honesta).** Este sello **no** mueve `packages/py/**`: es UI/copy + tests más el bump. `replay-repro` debe seguir `REPRODUCIDO` con la huella `1E3ADAC2…` para confirmarlo por CI.
> **Cierre semántico de usuario básico.** La revisión de `v2.88.93` dejó tres tensiones de producto: AUTO afirmaba una decisión que no existe («qué ha elegido AUTO»), Riesgo prometía una cifra no medida, y AUTO no era descubrible como **forma de operar**. Se cierran **sin falsificar datos** (`UNKNOWN ≠ 0`, `ranking ≠ decisión`) y con tests de copy falsables.

**Base:** [`evidence/v2.88.93/README.md`](../v2.88.93/README.md). Contrato: [`spec-ui-contract-5-0-2026-10-08.md`](../../spec-ui-contract-5-0-2026-10-08.md). Deuda previa: [`evidence/v2.88.93/README.md`](../v2.88.93/README.md) §4.

## 1. Cambios (por regla)

| # | Tensión de origen | Regla | Cierre | Implementación |
| --- | --- | --- | --- | --- |
| 1 | AUTO afirmaba una decisión inexistente | `UI5-12` | `operar.description` → «qué oportunidades ha encontrado AUTO y qué operaciones están en curso»; test de copy falsable (`no contiene "ha elegido"`). | [`auto-copy.ts`](../../../../apps/web/src/features/auto/auto-copy.ts), [`auto-copy.test.ts`](../../../../apps/web/src/features/auto/auto-copy.test.ts) |
| 2 | Bloque «Decisión» sin explicar la cadena | `UI5-12` | «Decisión de cartera» explica `oportunidad → ranking → (decisión pendiente) → orden`; el hueco se declara, no se deduce del TOP3. Deuda declarada: `PortfolioDecision` durable. | [`auto-home-page.tsx`](../../../../apps/web/src/features/auto/auto-home-page.tsx) |
| 3 | AUTO autónomo ≠ firma humana | `UI5-13`/`UI5-17` | «AUTO puede continuar su operativa simulada sin tu firma; las acciones que tú hagas sobre una posición sí requieren tu confirmación». Un solo término: **dinero virtual**. | [`auto-copy.ts`](../../../../apps/web/src/features/auto/auto-copy.ts), [`auto-cartera-page.tsx`](../../../../apps/web/src/features/auto/auto-cartera-page.tsx) |
| 4 | Riesgo prometía «cuánto puedes perder» | `UI5-16`/`UI5-18` | Pregunta → «¿Hay algún problema de riesgo ahora mismo?»; bloque «Riesgo ahora mismo»; veredicto conservado. | [`auto-copy.ts`](../../../../apps/web/src/features/auto/auto-copy.ts), [`auto-riesgo-page.tsx`](../../../../apps/web/src/features/auto/auto-riesgo-page.tsx) |
| 5 | AUTO no era descubrible como forma de operar | `UI5-21` (nuevo) | Chip-enlace `Operativa · AUTO/SEMI/MANUAL` en el chrome, **fuera** de `nav[aria-label="Principal"]`; informa y enlaza a `/auto`, no cambia el modo. | [`operative-mode-chip.tsx`](../../../../apps/web/src/components/layout/operative-mode-chip.tsx), [`app-top-bar.tsx`](../../../../apps/web/src/components/layout/app-top-bar.tsx) |
| 6 | Laboratorio denso en primer nivel | `UI5-01`/`R-G2`/`RT-01` | Primer nivel = `h1` + «¿Qué estamos aprendiendo?» + tres caminos; chrome avanzado (universo, DÍA-D, tabs incl. Jobs, ajustes) tras «Más opciones». Rutas/tabs intactas. | [`backtests-page.tsx`](../../../../apps/web/src/features/backtests/backtests-page.tsx) |
| 7 | Asesor reexponía experimentación | `UI5-01`/`R-G2` | Primer nivel responde «¿Por qué?» (Análisis/Journal/Diario + Laboratorio); métricas de experimentación tras `Detalle técnico`. | [`research-page.tsx`](../../../../apps/web/src/features/research/research-page.tsx) |
| 8 | Copy de Hoy no reflejaba el orden real | `UI5-01` | Pie alineado a atención → oportunidades → posiciones; test de orden de cubos. | [`mesa-hoy-page.tsx`](../../../../apps/web/src/features/mesa/mesa-hoy-page.tsx), [`daily-desk-inbox.test.tsx`](../../../../apps/web/src/features/mesa/daily-desk-inbox.test.tsx) |

## 2. Contrato enmendado (`UI5-21`)

[`spec-ui-contract-5-0-2026-10-08.md`](../../spec-ui-contract-5-0-2026-10-08.md) Bloque A gana `UI5-21` (**modo operativo persistente**: Información + Navegación, nunca acción; no es sexta puerta L1). Enmiendas: [ADR-040](../../../adr/040-user-information-architecture.md) §13, [ADR-044](../../../adr/044-auto-workspace-information-architecture.md) §2 y [ADR-045](../../../adr/045-ui-contract-5-0.md) §1.1. Vocabulario: [`domain-language.md`](../../../domain-language.md) §4.2 gana «Modo operativo persistente» y «Dinero virtual».

## 3. Verificación (local)

- `pnpm --filter @bolsa/web exec tsc --noEmit` → **OK** (exit 0).
- `pnpm --filter @bolsa/web exec eslint src` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes).
- `pnpm --filter @bolsa/web exec vitest run` → **279 ficheros / 1740 tests verdes** (+13 tests respecto a `2.11.93-beta`).
- `python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` → **1 passed** (`2.11.94-beta`).
- **`Δ motor = 0`**: `git diff --name-only -- packages/py` → **vacío**.

## 4. Qué no cambia / deuda declarada

- **Motor AUTO** de decisión/ejecución, worker, umbrales, Alembic (head `052_top3_opportunities`), `contract:gen`, contrato HTTP y esquema. Live/XTB real sigue fuera: el canal se declara `SIMULADO`.
- **`playwright` integrado** sigue `opt-in`/`skipped`; la certificación `axe` de la serie es **con mocks**.
- **Deuda durable backend (fuera de este ciclo):** `PortfolioDecision` durable expuesto en read-model, read-model de riesgo (máxima pérdida / riesgo por posición / límite diario), traza de materialización SIM, PIT histórico institucional y Execution Analysis.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.
