# M5/§M0.6.2 — Higiene de formato legacy (prettier) por lotes aislados — SALIDA / RELEVO

**Fecha:** 2026-08-11 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD:** `e498c68` (árbol limpio y sincronizado con `origin`)

> Este documento es el **punto de entrada del siguiente hilo** que retome esta línea.
> Consolida la estrategia, el protocolo de 8 pasos, el avance real (lotes 1-18) y los próximos dominios.
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
     originalmente): `optimize`→`explore`→`result`→`wizard`→`library`/`strategy-matrix`→`core-r`→`dia-d`→`assistant`→
     `optimize restantes`→`strategy-matrix restantes`→`list-auto`/`mass-compare`→`finalists`/`top` (hechos, lotes 2-13).
     Siguientes: `coach`/`lab`, `hub`/`chart`/`misc`. Cada sub-lote ≤ ~30 archivos. (`coach`/`lab` lote 14, `hub` lote 15, `chart` lote 16, `misc`/motores lote 17, cierre `library`/`estudio`/`ibex` lote 18 → **`features/backtests` completo**).
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

## 4. Estado de avance real (2026-08-11, HEAD `e498c68`)

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
| 10 | `9853e79` | backtests/optimize restantes | 16 |
| 11 | `ee381d7` | backtests/strategy-matrix restantes | 11 |
| 12 | `9975cd3` | backtests/list-auto + mass-compare | 11 |
| 13 | `f011918` | backtests/finalists + top | 17 |
| 14 | `6f8c668` | backtests/coach + lab | 21 |
| 15 | `6c32b06` | backtests/hub (hub del dominio hub/chart/misc) | 4 |
| 16 | `a42587e` | backtests/chart (parte del dominio hub/chart/misc) | 16 |
| 17 | `da2f7d9` | backtests/misc motores (parte del dominio hub/chart/misc) | 23 |
| 18 | `5bec6ed` | backtests/library + estudio/ibex/tests sueltos (CIERRE dominio hub/chart/misc) | 11 |
| 19 | `689c294` | features/accounts (PRIMER sub-lote del resto de apps/web/src, fuera de backtests) | 17 |
| 20 | `1081809` | features/workspace (sub-lote resto de apps/web/src, fuera de backtests) | 7 |
| 21 | `75f6595` | features/config + platform (sub-lote resto de apps/web/src, fuera de backtests) | 14 |
| 22 | `cbd0fff` | features/research (sub-lote resto de apps/web/src, fuera de backtests) | 10 |
| 23 | `4300674` | features/settings (sub-lote resto de apps/web/src, fuera de backtests) | 25 |
| 24 | `e38be2d` | features/instruments (sub-lote resto de apps/web/src, fuera de backtests) | 30 |
| 25 | `110667b` | stores (apps/web/src/stores, sub-lote resto de apps/web/src, fuera de backtests) | 31 |
| 26 | `465137a` | lib sub-batch A (apps/web/src/lib, 18 de 35, sub-lote resto de apps/web/src) | 18 |
| 27 | `0b8f04b` | lib sub-batch B (apps/web/src/lib, 17 de 35, CIERRE dominio lib) | 17 |

**Total formateado hasta aquí: 379 ficheros** con diff real en 27 commits propios de formateo (210 de `features/backtests`
en lotes 1-18 + 17 `accounts` lote 19 + 7 `workspace` lote 20 + 14 `config`+`platform` lote 21 + 10 `research` lote 22
+ 25 `settings` lote 23 + 30 `instruments` lote 24 + 31 `stores` lote 25 + 18 `lib` sub-batch A lote 26 + 17 `lib` sub-batch B lote 27). Todos con batería
`typecheck ✅ · lint 0e ✅ · test 140/707 ✅ · build ✅` (+ `test:coach` 26/186 ✅ en los lotes 14, 17 y 18, área Coach/TOP).

**Hallazgo de método (lotes 3, 4 y 5):** varios ficheros que `prettier --check` reporta `[warn]` son **falsos positivos
EOL** (contenido normalizado idéntico a HEAD). Se detectan porque **no aparecen en `git diff --cached --numstat`**
tras el `--write`+`git add`; deben **resetearse** (`git reset -- <file>`) y quedar fuera del commit. En los lotes 6-13
ningún fichero fue falso positivo (todos con diff real).

## 5. Próximos sub-lotes por dominio restante en `features/backtests`

El feature es **plano** (sin subdirectorios); agrupar por **prefijo de nombre**. Lista **exacta de archivos pendientes**
(obtenida cruzando la lista completa con los ya formateados a HEAD `2e1f8d1`). Sub-lote sugerido siguiendo la misma
lógica por dominio funcional, cada uno **≤ ~30 archivos**:

- ~~**`optimize` restantes**~~ **HECHO (lote 10, `9853e79`)**: `backtest-optimize-compare.tsx`(+test), `backtest-optimize-delta.ts`,
  `backtest-optimize-from-seed.ts`(+test), `backtest-optimize-heatmap-panel.tsx`(+test), `backtest-optimize-panel.tsx`,
  `backtest-optimize-progress.tsx`, `backtest-optimize-seed.ts`(+test), `backtest-optimize-space.ts`(+test),
  `backtest-optimize-validation-hint.ts`(+test), `backtest-optimized-strategy.ts` = **16 files (+1333/−932 solo formato)**.
- ~~**`list-auto`/`mass-compare`**~~ **HECHO (lote 12, `9975cd3`)**: `backtest-list-auto.ts`(+tests: board/board-panel/persist/statusbar), `backtest-list-auto-board.ts`(+test), `backtest-list-auto-board-panel.tsx`, `backtest-list-auto-persist.ts`(+test), `backtest-list-auto-statusbar.test.ts`, `backtest-mass-compare.ts`(+test), `backtest-mass-compare-panel.tsx` = **11 files (+576/−430 solo formato)**.
- ~~**`coach`/`lab`**~~ **HECHO (lote 14, `6f8c668`)**: `coach-dual-audit.ts`(+test), `coach-llm-invariant.test.ts`, `coach-profile-policy.ts`(+test), `coach-top-save.ts`(+test), `coach-quorum-bar.tsx`, `coach-profile-battery-scenario.test.ts`; `lab-coach-handoff.ts`(+test), `lab-adoption-memory.ts`(+test), `lab-board-activity-banner.tsx`, `lab-zone-verdict.tsx`, `lab-coach-caf-smoke.test.ts`; `backtest-lab-board.tsx`(+`backtest-lab-board-types.ts`), `backtest-coach-lote.ts`(+test), `backtest-coach-coherence.test.ts` = **21 files (+1326/−1048 solo formato)**. Con batería `test:coach` 26/186 ✅ (área Coach/TOP).
- ~~**`finalists`/`top`**~~ **HECHO (lote 13, `f011918`)**: `backtest-finalists-freshness.ts`(+tests), `finalists-stability-summary.ts`(+test), `finalist-propose-supervised.ts`(+test), `promote-finalist-to-tracker.ts`(+test), `instrument-strategy-top-panel.tsx`(+test), `instrument-strategy-top-promote.ts`(+test), `instrument-top-match.ts`(+test), `instrument-top-strategy-type.ts`(+test) = **17 files (+807/−667 solo formato)**.
- ~~**`strategy-matrix` restantes**~~ **HECHO (lote 11, `ee381d7`)**: `backtest-strategy-matrix.ts`(+test), `strategy-matrix-column-layout.ts`(+test), `strategy-matrix-filter-carousel-prefs.ts`(+test), `strategy-monitor-panel.tsx`, `strategy-monitor.ts`(+test), `mine-strategies-filters.ts`(+test) = **11 files (+970/−785 solo formato)**.
- ~~ **`hub`** (parte del dominio `hub`/`chart`/`misc`) ~~ **HECHO (lote 15, `6c32b06`)**: `backtest-hub-layout.tsx`, `backtest-global-bar.tsx`, `backtest-history-tab.tsx`, `backtests-page.tsx` = **4 files (+161/−102 solo formato)**. `hub-nav`(+test)/`hub-tabs`(+test) YA estaban formateados.
- ~~ **`chart`** (parte del dominio `hub`/`chart`/`misc`) ~~ **HECHO (lote 16, `a42587e`)**: `backtest-chart-import-panel.tsx`, `backtest-equity-chart.tsx`, `backtest-replay-chart.tsx`, `backtest-stat-donut.tsx`, `backtest-ranking-table.tsx`, `backtest-universe-picker.tsx`, `backtest-zone-settings-dialog.tsx`, `backtest-zone-prefs.ts`(+test), `backtest-cursor-panel.tsx`, `backtest-favorites-menu.tsx`, `backtest-future-stars.tsx`(+test), `backtest-instrument-preview.tsx`, `backtest-movie-hud.tsx`, `backtest-movie-stats.ts` = **16 files (+721/−458 solo formato)**. Sin falsos positivos EOL (los 16 con diff real).
- ~~ **`misc` motores** (parte del dominio `hub`/`chart`/`misc`) ~~ **HECHO (lote 17, `da2f7d9`)**: `backtest-paper-checklist.tsx`, `backtest-paper-gate.ts`(+test), `backtest-run-context.ts`(+test), `backtest-batch-run.ts`, `backtest-export.ts`, `backtest-date-format.ts`, `backtest-split-layout.ts`, `backtest-hud-prefs.ts`, `use-backtest-hud-prefs.ts`, `backtest-buy-hold.ts`(+test), `backtest-deep-coach.ts`(+test), `backtest-oos-evidence.ts`(+test), `backtest-pbo.ts`(+test), `backtest-period.ts`(+test), `backtest-walk-forward-metrics.ts`(+test) = **23 files reales (+1389/−1087 solo formato)**. **1 falso +EOL** (`backtest-period-returns.ts`, contenido normalizado idéntico a HEAD) → fuera del commit. Área Coach/TOP (test:coach 26/186 ✅).
- ~~ **`library`/`estudio`/`ibex`/tests sueltos** (cierre del dominio `hub`/`chart`/`misc`) ~~ **HECHO (lote 18, `5bec6ed`)**: `chart-strategy-bridge.test.ts`, `drawing-replay-parity.test.ts`, `signal-evaluate-parity.test.ts`, `library-nav.ts`(+test), `library-strategy-buckets.ts`(+test), `estudio-list.test.ts`, `estudio-personal-list.test.ts`, `ibex35-operativa-audit.ts`(+test) = **11 files (+360/−295 solo formato)**. Sin falsos positivos EOL (los 11 con diff real). Área Coach/TOP (test:coach 26/186 ✅). **Con esto el dominio `hub`/`chart`/`misc` queda CERRADO (lotes 15-18).**
- ~~ **`accounts`** (primer sub-lote del **resto de `apps/web/src`**, fuera de `features/backtests`) ~~ **HECHO (lote 19, `689c294`)**: todos los `.ts`/`.tsx` de `features/accounts` = **17 files (+973/−656 solo formato)**: `account-detail-panel`, `account-investor-profile-select`, `account-scope-selector`, `account-settings-dialog`, `account-settings-panel`, `account-wizard-capital-step`, `account-wizard-commissions-step`, `account-wizard-identity-step`, `account-wizard-review-step`, `account-wizard-tax-step`, `accounts-page`, `create-account-wizard-dialog`, `investor-profile-panel`, `investor-profile-picker`, `paper-lab-evidence`(+test), `use-active-account`. Sin falsos positivos EOL (los 17 con diff real; solo `'→"` + line-wrapping). No es área Coach/TOP.
- ~~ **`workspace`** ~~ **HECHO (lote 20, `1081809`)**: todos los `.ts`/`.tsx` de `features/workspace` = **7 files (+107/−78 solo formato)**: `use-visualization-workspace-sync`, `visualization-workspace-sync`, `workspace-auto-save`, `workspace-bootstrap`, `workspace-picker-dialog`, `workspace-remote-sync`, `workspace-ui-bridge-register`. Sin falsos positivos EOL (los 7 con diff real; solo `'→"` + line-wrapping). No es área Coach/TOP.
- ~~ **`config` + `platform`** ~~ **HECHO (lote 21, `75f6595`)**: todos los `.ts`/`.tsx` de `features/config` + `features/platform` = **14 files (+601/−443 solo formato)**: `config`: `database-config-panel`, `notification-prefs`(+test), `notifications-settings-panel`, `platform-config-dialog`; `platform`: `mandate-tenure-pnl`(+test), `operating-mandate`(+test), `operating-mandate-sync`, `product-universe`(+test), `strategy-adoption`, `universe-chip`. Sin falsos positivos EOL (los 14 con diff real; solo `'→"` + line-wrapping). No es área Coach/TOP.
- ~~ **`research`** ~~ **HECHO (lote 22, `cbd0fff`)**: todos los `.ts`/`.tsx` de `features/research` = **10 files (+749/−452 solo formato)**: `asesor-daily-ops-panel`, `asesor-opiniones-panel`, `estudio-opinion-alarm-poller`, `opinion-channel-map.test`, `research-lab-evidence-summary`, `research-lab-evidence`(+test), `research-page`, `research-trial-result-block`, `use-asesor-alarma-badge`. Sin falsos positivos EOL (los 10 con diff real; solo `'→"` + line-wrapping). No es área Coach/TOP.
- ~~ **`settings`** ~~ **HECHO (lote 23, `4300674`)**: todos los `.ts`/`.tsx` de `features/settings` = **25 files (+1927/−1433 solo formato)**: `ai-platform-section`, `ai-platform-tracker`(+test), `backtesting-help-section`, `backtesting-tracker`(+test), `chart-platform-section`, `chart-platform-tracker`, `data-capture-section`, `data-market-tracker`, `data-sync-summary-card`, `decision-replay-panel`, `dia-d-evidence-archive-help-card`, `effectiveness-panel`, `general-settings-section`, `market-providers-status-card`, `paper-paths-copy`(+test), `settings-redirect-page`, `settings-section`, `supervised-f3-panel`, `value-analysis-section`, `value-analysis-tracker`, `watchlist-help-section`, `watchlist-lists-tracker`. Sin falsos positivos EOL (los 25 con diff real; solo `'→"` + line-wrapping). No es área Coach/TOP.
- ~~ **`instruments`** ~~ **HECHO (lote 24, `e38be2d`)**: todos los `.ts`/`.tsx` de `features/instruments` = **30 files (+2128/−1399 solo formato)**: `composite-leg-labels`(+test), `fundamental-card-panel`, `instrument-detail-page`, `instrument-dictamen-evolution`(+test), `instrument-narrative-editor`(+test), `instrument-sync-dialog`, `instruments-hub-column-layout`(+test), `instruments-hub-detail-panel`, `instruments-hub-enrichment`(+test), `instruments-hub-filter-bar`, `instruments-hub-model`(+test), `instruments-hub-scores`(+test), `instruments-hub-split-layout`, `instruments-hub-trackers`(+test), `instruments-page`, `use-activate-instrument-tracking`, `use-ensure-instrument-fundamentals`, `use-instrument-data-freshness`, `use-instrument-live-quotes-batch`, `use-instrument-sync`(+test ya formateado), `use-instruments-hub-enrichment`, `use-instruments-hub-scores`, `use-instruments-hub-trackers`. Sin falsos positivos EOL (los 30 con diff real; `use-instrument-sync.test.ts` quedó `(unchanged)`. solo `'→"` + line-wrapping). No es área Coach/TOP.
- ~~ **`stores`** ~~ **HECHO (lote 25, `110667b`)**: todos los `.ts` de `apps/web/src/stores` = **31 files (+1911/−1207 solo formato)**: `active-account-store`, `alerts-store`(+test), `auth-store`, `chart-cursor-store`, `core-r-review-queue-store`(+test), `dia-d-evidence-archive-store`(+test), `dia-d-trading-session-store`(+test), `estudio-membership-store`, `estudio-process-running-store`, `instruments-hub-preferences-store`, `list-auto-activity-store`, `list-chrome-layout-store`, `list-tracker-results-store`, `notification-prefs-store`, `screener-activity-store`, `screener-preferences-store`, `supervised-f3-queue-store`(+test), `tracker-alarm-inbox-store`(+test), `trade-preferences-store`, `trading-layout-store`, `trading-ui-store`, `ui-store`, `visualization-store`, `workspace-store`, `workspace-ui-bridge`. Sin falsos positivos EOL (los 31 con diff real; solo `'→"` + line-wrapping). No es área Coach/TOP.
- ~~ **`lib` sub-batch A** ~~ **HECHO (lote 26, `465137a`)**: primer sub-lote (18 de 35) de `apps/web/src/lib` = **18 files (+1299/−897 solo formato)**: `api-base-url`, `api`(+808/−574, el más grande), `chart-list-membership`(+test), `chart-list-snapshot`, `chart-tab-uniqueness`(+test), `close-chart-on-list-removal`, `datetime-input`, `default-lists`, `draw-tool-favorites-storage`, `draw-tool-session-storage`, `instrument-search.test`, `list-carousel-config`, `list-column-layout`, `list-hub-column-layout`, `list-selection-guard`, `list-sort-with-recommendation.test`. Sin falsos positivos EOL (los 18 con diff real; solo `'→"` + line-wrapping). No es área Coach/TOP.
- ~~ **`lib` sub-batch B** ~~ **HECHO (lote 27, `0b8f04b`)**: segundo sub-lote (17 de 35) de `apps/web/src/lib` = **17 files (+518/−388 solo formato)**: `list-sort-with-recommendation`, `list-sync`(+test), `list-utils`, `query-client`, `query-invalidation`, `routes`, `scan-results-column-layout`(+test), `screener-split-layout`(+test), `scroll-list-instrument-into-view`(+test), `search-ranking`, `use-media-query`, `utils`, `workspace-payload`. Sin falsos positivos EOL (los 17 con diff real; solo `'→"` + line-wrapping). No es área Coach/TOP. **Con esto el dominio `lib` queda CERRADO (lotes 26-27, 35 files).**

> Cuando se acabe `features/backtests`, seguir con el **resto de `apps/web/src`** por sub-lotes, con el mismo protocolo.

> **Nota de método para el siguiente hilo (relevo):** `optimize` restantes (10, `9853e79`), `strategy-matrix` restantes
> (14, `6f8c668`), `hub` (15, `6c32b06`), `chart` (16, `a42587e`), `misc`/motores (17, `da2f7d9`) y cierre
> `library`/`estudio`/`ibex` (18, `5bec6ed`) ya están HECHOS. **El dominio `hub`/`chart`/`misc` está CERRADO y
> `features/backtests` queda COMPLETO.** Lotes 19-27 del resto de `apps/web/src`: **`accounts` (19, `689c294`),
> `workspace` (20, `1081809`), `config`+`platform` (21, `75f6595`), `research` (22, `cbd0fff`), `settings` (23,
> `4300674`), `instruments` (24, `e38be2d`), `stores` (25, `110667b`), `lib` sub-batch A (26, `465137a`),
> `lib` sub-batch B (27, `0b8f04b`).** Tras los lotes 19-27, el `prettier --check` amplio (excl. `features/backtests`) marca **250 files**
> desincronizados restantes.
> Recomendar arrancar el siguiente sub-lote por un dominio con pocos archivos y sin mezclar dominios:
>
> **Siguiente: otro dominio del resto de `apps/web/src`** (fuera de `features/backtests`, que queda completo) por
> sub-lotes, con el mismo protocolo de 8 pasos (features de otros dominios —charts, instruments, trading,
> screeners—, lib, stores, components/ui, layout, etc.), ejecutando `prettier --check` por
> sub-lote y verificando el `git diff --cached --numstat` (paso 4). Correr `test:coach` cuando el sub-lote toque área
> Coach/TOP. Hechos: `accounts` (19), `workspace` (20), `config`+`platform` (21), `research` (22), `settings` (23),
> `instruments` (24), `stores` (25), `lib` sub-batch A (26), `lib` sub-batch B (27, cierre de dominio).


## 6. Documentos fuente de verdad / índices

- `docs/engineering/traspaso-higiene-formato-legacy-entrada-2026-08-10.md` (ENTRADA original; protocolo + estrategia).
- `docs/engineering/relevo-higiene-formato-lotes-24-27-2026-08-11.md` (RELEVO del hilo: estado verificado HEAD `e498c68`, protocolo 8 pasos + encodificación, dominios pendientes, docs a tocar).
- `docs/engineering/dev-continuation-plan-2026-08-09.md` (§7.6.i → registro detallado de cada lote).
- `docs/engineering/engineering-index-2026-08-03.md` (índice; este documento anclado).
- `docs/engineering/traspaso-m5-frontend-2026-08-10.md` (§7 nota de cierre M5).
- `.gitattributes` · `.prettierrc` (vacío = defaults).
