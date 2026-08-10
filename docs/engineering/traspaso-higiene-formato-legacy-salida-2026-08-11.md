# M5/§M0.6.2 — Higiene de formato legacy (prettier) por lotes aislados — SALIDA / RELEVO

**Fecha:** 2026-08-11 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD:** `2e1f8d1` (árbol limpio y sincronizado con `origin`)

> Este documento es el **punto de entrada del siguiente hilo** que retome esta línea.
> Consolida la estrategia, el protocolo de 8 pasos, el avance real (lotes 1-9) y los próximos dominios.
> No hay nada que redescubrir: cada hecho está verificado en el repo/CI.

---

## 0. Qué es esto (1 línea)

Normalizar el formato **Prettier** de los ficheros legacy de `apps/web` desincronizados con la configuración actual,
en **lotes aislados por dominio** (cada uno = commit de formateo único, batería verde + push). Ataca la causa raíz de
por qué el proyecto commitea con `git commit --no-verify` (para evitar que el hook `lint-staged/prettier --write`
formatee masivamente el estilo antiguo en el diff editorial).

## 1. Aclaración de alcance (CRLF NO es deuda commiteada)

- El repo tiene `.gitattributes` con `* text=auto eol=lf`: **git ya almacena en LF** en el índice y normaliza el
  working copy en Windows. Los ficheros que el checkout local reporta como CRLF **no son deuda de git**.
- **El problema real es FORMATO Prettier**: `prettier --check "apps/web/src/**/*.{ts,tsx,css,json}"` reporta
  **643 archivos** desincronizados (`.prettierrc` vacío = defaults). Prettier reformatea contenido (indentación, saltos
  de línea, `'→"` en props JSX, etc.). Por eso se requiere **commits propios de formateo** (premisa M0/§6.2).

## 2. Estrategia: lotes aislados + commit de formateo propio

- **Regla de oro:** cada lote = solo formateo Prettier (sin cambio funcional) → batería → commit `--no-verify` → push.
- **Orden** (mejor ratio valor/riesgo):
  1. `components/ui` + `components/layout` — hecho (LOTE 1).
  2. `features/backtests` **subdividido por dominio funcional** (directorio plano y enorme; ~210 files desincronizados
     originalmente): `optimize`→`explore`→`result`→`wizard`→`library`/`strategy-matrix`→`core-r`→`dia-d`→`assistant`
     (hechos). Siguientes: `lab`, `optimize` restantes, `chart`/`strategy-monitor`, etc. Cada sub-lote ≤ ~30 archivos.
  3. El resto de `apps/web/src` por sub-lotes.

## 3. Protocolo por lote (FASE 3) — 8 pasos

1. `git status` limpio.
2. `npx prettier --check <lista archivos>` sobre el subconjunto → confirmar desincronizados (≤ ~30).
3. `npx prettier --write <lista archivos>` sobre SOLO ese subconjunto.
4. **Falsos positivos EOL:** `git add <todos>` y leer `git diff --cached --numstat`. Los que **no aparezcan**
   (numstat vacío) son falsos positivos EOL (contenido idéntico a HEAD; git los normaliza a LF) y se **resetean**
   (`git reset -- <file>`), quedando fuera del commit. Solo se commitean los ficheros con diff de contenido real.
5. Batería: `pnpm --filter @bolsa/web typecheck` · `lint` (0e) · `test` (140/707) · `build` (exit 0).
6. `git diff --cached --stat` → confirmar que es solo formato (sin borrados funcionales).
7. Commit `--no-verify` + push.
8. Registrar en `dev-continuation-plan-2026-08-09.md` (§7.6.i) y en este documento / `engineering-index`.

> **Nota de ejecución (verificado en lotes 6-16 del hilo previo):** el `--write` sobre el dominio completo incluye
> producción `.ts`/`.tsx` **y sus `.test.ts`** (precedente LOTE 3). Hacer el check/write con la lista explícita de
> archivos del dominio. **Los commits `--no-verify` requieren la aprobación del usuario** en la tarjeta nativa de
> auto-review (flujo ya validado para los 9 lotes).

## 4. Estado de avance real (2026-08-11, HEAD `2e1f8d1`)

| Lote | Commit | Dominio | Ficheros con contenido real |
|------|--------|---------|-----------------------------|
| 1 | `d39bbbb` | components/ui + layout | 15 |
| 2 | `0ceeb5b` | backtests/optimize | 8 |
| 3 | `7c174c7` | backtests/explore | 7 (bh = falso +EOL) |
| 4 | `d96123d` | backtests/result | 5 (detail/finalists/ranking = falso +EOL) |
| 5 | `9fa403a` | backtests/wizard | 2 (mass-compare/probe-list = falso +EOL) |
| 6 | `68c9dac` | backtests/library + strategy-matrix | 5 |
| 7 | `f241872` | backtests/core-r | 13 |
| 8 | `0a96220` | backtests/dia-d | 8 |
| 9 | `1cb6ee7` | backtests/assistant | 17 |

**Total formateado hasta aquí: 80 ficheros** con diff real en 9 commits propios de formateo. Todos con batería
`typecheck ✅ · lint 0e ✅ · test 140/707 ✅ · build ✅`.

**Hallazgo de método (lotes 3, 4 y 5):** varios ficheros que `prettier --check` reporta `[warn]` son **falsos positivos
EOL** (contenido normalizado idéntico a HEAD). Se detectan porque **no aparecen en `git diff --cached --numstat`**
tras el `--write`+`git add`; deben **resetearse** (`git reset -- <file>`) y quedar fuera del commit. En los lotes 6-9
ningún fichero fue falso positivo (todos con diff real).

## 5. Próximos sub-lotes por dominio restante en `features/backtests`

El feature es **plano** (sin subdirectorios); agrupar por **prefijo de nombre**. Lista **exacta de archivos pendientes**
(obtenida cruzando la lista completa con los ya formateados a HEAD `2e1f8d1`). Sub-lote sugerido siguiendo la misma
lógica por dominio funcional, cada uno **≤ ~30 archivos**:

- **`optimize` restantes** (junto a los 8 ya hechos): `backtest-optimize-compare.tsx`(+test), `backtest-optimize-delta.ts`,
  `backtest-optimize-from-seed.ts`(+test), `backtest-optimize-heatmap-panel.tsx`(+test), `backtest-optimize-panel.tsx`,
  `backtest-optimize-progress.tsx`, `backtest-optimize-seed.ts`(+test), `backtest-optimize-space.ts`(+test),
  `backtest-optimize-validation-hint.ts`(+test), `backtest-optimized-strategy.ts`.
- **`list-auto`/`mass-compare`** : `backtest-list-auto.ts`(+tests: board/board-panel/persist/statusbar), `backtest-list-auto-board.ts`(+test), `backtest-list-auto-board-panel.tsx`, `backtest-list-auto-persist.ts`(+test), `backtest-list-auto-statusbar.test.ts`, `backtest-mass-compare.ts`(+test), `backtest-mass-compare-panel.tsx`.
- **`coach`/`lab`** : `coach-dual-audit.ts`(+test), `coach-llm-invariant.test.ts`, `coach-profile-policy.ts`(+test), `coach-top-save.ts`(+test), `coach-quorum-bar.tsx`, `backtest-coach-*.ts`(+tests), `backtest-lab-board.tsx`(+types), `lab-board-activity-banner.tsx`, `lab-zone-verdict.tsx`, `lab-*`(memory/handoff/caf-smoke).
- **`finalists`/`top`** : `backtest-finalists-freshness.ts`(+tests), `finalists-stability-summary.ts`(+test), `finalist-propose-supervised.ts`(+test), `promote-finalist-to-tracker.ts`(+test), `instrument-strategy-top-panel.tsx`(+test), `instrument-strategy-top-promote.ts`(+test), `instrument-top-match.ts`(+test), `instrument-top-strategy-type.ts`(+test).
- **`strategy-matrix` restantes** : `backtest-strategy-matrix.ts`(+test), `strategy-matrix-column-layout.ts`(+test), `strategy-matrix-filter-carousel-prefs.ts`(+test), `strategy-monitor-panel.tsx`, `strategy-monitor.ts`(+test), `mine-strategies-filters.ts`(+test).
- **`hub`/`chart`/`misc`** : `backtest-hub-layout.tsx`, `backtest-hub-nav.ts`(+test), `backtest-hub-tabs.tsx`(+test), `backtest-global-bar.tsx`, `backtest-history-tab.tsx`, `backtest-chart-import-panel.tsx`, `backtest-equity-chart.tsx`, `backtest-replay-chart.tsx`, `backtest-stat-donut.tsx`, `backtest-ranking-table.tsx`, `backtest-universe-picker.tsx`, `backtest-zone-settings-dialog.tsx`, `backtest-zone-prefs.ts`(+test), `backtests-page.tsx`, `backtest-cursor-panel.tsx`, `backtest-favorites-menu.tsx`, `backtest-future-stars.tsx`(+test), `backtest-instrument-preview.tsx`, `backtest-movie-hud.tsx`, `backtest-movie-stats.ts`, `backtest-paper-checklist.tsx`, `backtest-paper-gate.ts`(+test), `backtest-run-context.ts`(+test), `backtest-batch-run.ts`, `backtest-export.ts`, `backtest-date-format.ts`, `backtest-split-layout.ts`, `backtest-hud-prefs.ts`, `use-backtest-hud-prefs.ts`, `backtest-buy-hold.ts`(+test), `backtest-deep-coach.ts`(+test), `backtest-oos-evidence.ts`(+test), `backtest-pbo.ts`(+test), `backtest-period.ts`(+test), `backtest-period-returns.ts`, `backtest-walk-forward-metrics.ts`(+test), `chart-strategy-bridge.test.ts`, `drawing-replay-parity.test.ts`, `library-nav.ts`(+test), `library-strategy-buckets.ts`(+test), `estudio-list.test.ts`, `estudio-personal-list.test.ts`, `ibex35-operativa-audit.ts`(+test), `signal-evaluate-parity.test.ts`.

> Cuando se acabe `features/backtests`, seguir con el **resto de `apps/web/src`** por sub-lotes, con el mismo protocolo.

> **Nota de método para el siguiente hilo:** recomendar arrancar por un dominio con pocos archivos y sin mezclar dominios,
> p. ej. **`optimize` restantes** primero (dominio conocido de los lotes 2-9), y seguir el protocolo exactamente paso a
> paso, verificando el `git diff --cached --numstat` (paso 4) en cada lote.


## 6. Documentos fuente de verdad / índices

- `docs/engineering/traspaso-higiene-formato-legacy-entrada-2026-08-10.md` (ENTRADA original; protocolo + estrategia).
- `docs/engineering/dev-continuation-plan-2026-08-09.md` (§7.6.i → registro detallado de cada lote).
- `docs/engineering/engineering-index-2026-08-03.md` (índice; este documento anclado).
- `docs/engineering/traspaso-m5-frontend-2026-08-10.md` (§7 nota de cierre M5).
- `.gitattributes` · `.prettierrc` (vacío = defaults).
