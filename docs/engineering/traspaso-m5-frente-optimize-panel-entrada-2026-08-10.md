# Traspaso M5 — entrada para el frente `backtest-optimize-panel.tsx` (feature-slicing Diseño B) · primera ola C-OPT.1+

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD de referencia:** `d713a17` (cierre del frente `create-account-wizard-dialog.tsx`) · árbol limpio · sincronizado con origin
**Origen/encadenamiento:** [traspaso-m5-frontend-2026-08-10.md](./traspaso-m5-frontend-2026-08-10.md) (punto de entrada canónico de M5) ·
sucesor de [traspaso-m5-frente-create-account-wizard-cierre-2026-08-10.md](./traspaso-m5-frente-create-account-wizard-cierre-2026-08-10.md) (cierre del frente anterior)
**Estado de M5:** **EN PAUSA** salvo retomar por decisión del usuario. Este doc prepara la **FASE 1 (diagnóstico, sin cambios)**
ya hecha, para que el chat que ejecute el frente empiece directo en **FASE 2 (plan) / FASE 3 (ejecución)** previa aprobación.

---

## 0. Objetivo del frente

Reducir `apps/web/src/features/backtests/backtest-optimize-panel.tsx` (~2.168 líneas) extrayendo sus **islas JSX
presentacionales de bajo riesgo** como componentes Diseño B. Es un orquestador denso de la funcionalidad de optimización
del Lab (30+ `useState`, 6 `useRef`, 3 `useMutation`, 1 `useQuery` de polling 1500 ms, varios `useEffect` de orquestación:
cola de jobs Coach→Lab, aplicación de semilla, adopción; ~975 líneas de JSX inline bajo un único `Card`).

## 1. FASE 1 ya realizada (diagnóstico, SIN cambios) — 2026-08-10

Subagente de exploración (nivel very thorough) leyó el fichero completo y clasificó los bloques JSX.

### 1.1 Bloques de BAJO RIESGO — extraíbles tipo Diseño B (data-only / 0 callbacks)

Son islas presentacionales puras: reciben datos y **no** tocan estado de orquestación, queries ni handlers complejos.

| # | Bloque (nombre tentativo de componente) | Naturaleza |
|---|-----------------------------------------|-----------|
| B0 | `OptimizeCardHeader` (riesgo **medio**-bajo) | CardHeader del panel (~9 props, 0 callbacks) |
| B1 | `OptimizeEmptyTip` | Tip vacío de la optimización |
| B2 | `OptimizeSummaryStrip` | Franja de resumen ({métricas agregadas}) |
| B3 | `ExperimentSummaryBanner` | Banner de resumen de experimento |
| B4 | `WalkForwardReportCard` | Card de informe Walk-Forward |
| B5 | `EdgeReportCard` | Card de informe Edge |
| B6 | `CpcvReportCard` | Card de informe CPCV |
| B7 | `AdoptionHintBanner` | Banner de pista de adopción |

> Las 4 cards de métricas (B4–B6) son las que más masa quitan con contrato mínimo. Las 4 cards de resumen (B2/B3/B4/B6)
> y el banner (B7) son **data-only** → máxima seguridad.

### 1.2 Riesgo medio (perímetro, opcional en ola posterior)

- Banner "Prueba origen" y parte del `CardHeader` (B0).

### 1.3 ACOPLAMIENTO ALTO — **NO tocar en primera ola** (criterio de riesgo M5)

- **Formulario avanzado B6** (~15 props + ~9 callbacks cruzados de validación OOS/WF/CPCV).
- **Editor de espacio de búsqueda B5** (handlers que mutan `space` algorítmicamente).
- **Botonera B8** (usa `handleRun`).
- **Comparación B12** (usa `handleSave`).
- **Select familia B4** (usa `setFamilyAndSpace` multi-estado).
- **Botones de adopción B11**.

## 2. Propuesta de FASE 2 (plan atómico sugerido — requiere aprobación del usuario antes de ejecutar)

**Primera ola (bajo riesgo, commit por paso + batería completa):**

| Paso | Componente a extraer | Props/callbacks esperados |
|------|----------------------|---------------------------|
| C-OPT.1 | `OptimizeSummaryStrip` + `OptimizeEmptyTip` | data-only |
| C-OPT.2 | `WalkForwardReportCard` + `EdgeReportCard` + `CpcvReportCard` | data-only (métricas) |
| C-OPT.3 | `ExperimentSummaryBanner` + `AdoptionHintBanner` | data-only |
| C-OPT.4 | `OptimizeCardHeader` | ~9 props / 0 callbacks |

**Ola posterior (solo si se aprueba explícitamente):** formulario avanzado, editor de espacio, botonera, comparación,
select familia, adopción — acoplamiento alto → requiere plan específico, riesgo residual documentado.

La numeración concreta (nombres definitivos de ficheros) y el mapeo línea→componente exacto se fijan en FASE 2 del chat
que ejecute, sobre el diff real. Este traspaso ancla el **criterio**, no el plan cerrado.

## 3. Reglas del juego (mantener en el nuevo chat — protocolo sagrado M5)

- **FASE 1 → FASE 2 → FASE 3.** FASE 1 ya hecha (este doc). En el chat: FASE 2 (plan atómico + aprobación explícita del
  usuario) → FASE 3 (ejecución + **batería completa por cada paso** + `git commit --no-verify` + push + registro §7.6).
  **Sin aprobación explícita no se toca código ni se commitea.**
- **Batería por paso (en `apps/web`):**
  | Comando | Esperado |
  |---------|----------|
  | `pnpm --filter @bolsa/web typecheck` | exit 0 |
  | `pnpm --filter @bolsa/web lint` | 0 errores (cosmético Node no bloqueante) |
  | `pnpm --filter @bolsa/web test` | 140 ficheros / 707 tests, 0 fallos |
  | `pnpm --filter @bolsa/web build` | exit 0 (solo warnings code-splitting = M7) |
- **No tocar** backend (M3/M4/M6) ni dev-stack (M7). El code-splitting >500 kB y el crash Vite F3.7 son **M7**, ajenos a M5.
- Herramientas: `pnpm` sí en PATH; shell **PowerShell** (no `&&`; usar `;`). Commits con `--no-verify` (CRLF/prettier en
  ficheros legacy). Push a `origin/stage/estudio-membership-operativa-2026-08-04`.
- Si el chat se satura, **cortar y preparar otro traspaso parcial** (documentar todo y actualizar GitHub) antes de continuar.
- Patrón **Diseño B** (consistente en todo M5): extraer SOLO JSX presentacional a componentes delgados que reciben datos +
  callbacks del orquestador; la lógica de negocio (estado, efectos, queries, handlers) **permanece en el orquestador**.
  Mover constantes UI locales si quedan huérfanas y retirar imports sin uso.

## 4. Estado de referencia para validar batería (HEAD `d713a17`)

- Rama limpia y sincronizada con `origin/stage/estudio-membership-operativa-2026-08-04`.
- Batería verificada en el frente anterior (create-account-wizard): typecheck exit 0 · lint 0e/0w · test **140/707** ·
  build exit 0.
- Fichero a modificar en este frente: `apps/web/src/features/backtests/backtest-optimize-panel.tsx`. NO es área
  Coach/TOP; la regla `coach-top-quality.mdc` **NO** aplica (a diferencia de backtest-explore/strategy-matrix).

---

_Traspaso de entrada del frente `backtest-optimize-panel.tsx` de M5. 2026-08-10._
