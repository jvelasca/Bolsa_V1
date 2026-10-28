# Evidencia `v2.88.170-beta` — la representación deja de afirmar lo que no se midió ni lo que no se ejecutó

## 1. Qué publica este sello

Sello de **corrección de representación** posterior a `v2.88.169-beta`, que responde al
[acta de auditoría profunda de UI operativa](../../auditoria-ui-operativa-profunda-2026-10-28.md)
(POST-TAG, read-only) y cierra sus **seis P1**, el hallazgo del comodín **P2-04** y los dos P2 que
seguían contradiciendo los criterios de cierre del dictamen (**P2-01** y **P2-02**).

- **`Δ motor = 0`**: ninguna regla, indicador, umbral, peso, sizing ni salida cambia.
- **`Δ decisión = 0`**: no se decide distinto; cambia **lo que la UI afirma** sobre lo ya decidido.
- **`Δ contrato HTTP = ADITIVO`**: `tradeFeesTotal` en `LedgerResponseDto` (P1-03), con
  `openapi.json`/`schema.d.ts` regenerados y `contract:check` verde.
- **SIN migración nueva**: `head` sigue `058_estudio_daily_proposals`.
- **Tag `v2.88.170-beta`** (anotado, unsigned; objeto `3e794841` → commit `babfe228`).
  `v2.88.169-beta` (`d31df9b3` → `3ce94048`) **no se mueve ni se reabre**. `Release tag CI` `40727162474`
  **verde** con `certify` `GREEN`; auditoría independiente del tag en
  [`auditoria-independiente-v2.88.170-beta-2026-10-28.md`](../../auditoria-independiente-v2.88.170-beta-2026-10-28.md).
- **Bump** `2.11.169-beta` → `2.11.170-beta` (+ `meta.bump` de los **13** CLIs;
  `test_dia_d_bump_guard`).

## 2. Los nueve hallazgos, en una línea cada uno

| # | Hallazgo | Corrección | Prueba ancla |
| --- | --- | --- | --- |
| P1-01 | Error de API pintado como colección vacía en 6 superficies | `queryCollectionState` con precedencia `error > loading > unavailable > empty > ready` + `<CollectionAbsence />` | `query-absence.test.ts` + una render test por superficie |
| P1-02 | `skipped`/`unknown` anunciados como «ejecutada» | `resolvePendingFill`: sin `transactionId` no hay ejecución; no borra ni reintenta | `pending-order-fill.test.ts` (tabla de 6 desenlaces) |
| P1-03 | «Comisiones acumuladas» sumadas de la página de 100 | agregado de servidor `tradeFeesTotal` (todo el histórico, sin custodia) | `test_list_ledger_total_fees.py` + `history-page-fees.test.tsx` |
| P1-04 | Comisiones en verde y compras en rojo | `ledgerAmountTone` (`cost`/`in`/`neutral`) con `data-tone` | `portfolio-cash.test.ts` + `history-page-tone.test.tsx` |
| P1-05 | «Tu universo de análisis es pequeño» sin dato | `rankingUnavailable`/`rankingLoading` y supresión del CTA acusatorio | `mesa-candidates-panel-absence.test.tsx` |
| P1-06 | Cartera caída leída como «sin posiciones ni stops» | `absenceState` en el KPI y «No disponible» en el resumen | `mesa-portfolio-absence.test.tsx` |
| P2-04 | El comodín se probaba sobre el código, no sobre el DOM | `formatPriceOrAbsent` en primer nivel; `data-freshness` deja de usar `—` | `history-page-dash-absence.test.tsx`, `data-freshness.test.ts` |
| P2-01 | Un P&L no medido se pintaba como ganancia | `lib/pnl-tone.ts`: `pnlTone` (`positive`/`negative`/`neutral`; hueco y cero ⇒ `neutral`) + `PNL_TONE_CLASS` | `pnl-tone.test.ts`, `mesa-position-row.test.tsx`, `mesa-daily-header-pnl-tone.test.tsx`, `operations-panel-pnl-tone.test.tsx` |
| P2-02 | «El riesgo está controlado» con incidencias no medidas | `riskVerdict` exige estado, cuadre y recuento medidos antes de `ok` | `auto-risk-summary.test.ts` (bloque P2-02) |

Detalle completo (causa → cambio → prueba → límite): [respuesta a la auditoría](../../respuesta-auditoria-ui-operativa-2026-10-28.md).

## 3. Ficheros

| Capa | Ficheros principales |
| --- | --- |
| Web · helpers | `components/query-absence.ts`, `components/collection-absence.tsx`, `features/trading/pending-order-fill.ts`, `lib/pnl-tone.ts` |
| Web · superficies | `history/history-page.tsx`, `trading/operativa-outcomes.tsx`, `trading/use-pending-orders.ts`, `trading/dia-d-trades-panel.tsx`, `auto-monitor/dia-d-auto-panel.tsx`, `operational-console/ops-incidents-and-links.tsx`, `mesa/mesa-hoy-page.tsx`, `mesa/mesa-candidates-panel.tsx`, `mesa/mesa-proteccion-kpi.tsx`, `mesa/mesa-positions-summary.tsx`, `mesa/mesa-libro-panel.tsx`, `mesa/mesa-position-row.tsx`, `mesa/mesa-daily-header.tsx`, `operations/operations-page.tsx`, `operations/mesa-operational-bar.tsx`, `trading/operations-panel.tsx`, `auto/auto-risk-summary.ts` |
| Shared | `portfolio-cash.ts` (`ledgerAmountTone`), `cognitive/data-freshness.ts` (`DATA_FRESHNESS_ABSENT_LABEL`) |
| Python | `application/accounts/ledger.py` (`total_trade_fees`), `api/v1/routes/accounts.py`, `schemas/accounts.py` |
| Contrato | `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`, `apps/web/src/lib/api.ts` |
| Bump | `package.json` (raíz) + `meta.bump` de `v2_87`, `v2_89`…`v2_100` |
| Docs | `CHANGELOG.md`, `PROJECT_STATE.md`, este README, `respuesta-auditoria-ui-operativa-2026-10-28.md`, `audit-pack-v2.88.170-beta-2026-10-28.md` |

El acta `auditoria-ui-operativa-profunda-2026-10-28.md` **no se modifica** en este sello.

## 4. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| `pnpm --filter @bolsa/web test` | **2539 passed / 338 ficheros** |
| `pnpm --filter @bolsa/shared test` | **861 passed / 100 ficheros** (+1 `todo`) |
| `pnpm typecheck` | **4/4 OK** |
| `pnpm lint` | **0 errores** / 23 avisos preexistentes |
| `pnpm contract:check` | **OK** |
| `pytest test_list_ledger_total_fees.py + test_dia_d_bump_guard.py` | **4 passed** |
| `pytest apps/api-python/tests/integration/test_accounts.py` | **5 passed** |
| `pnpm window:test` | **50 passed** |
| `pnpm window:freeze` | **`freeze OK`** tras el re-anclaje del pin |

Las suites completas (`web`, `shared`, `pytest`) las ejecuta el `Release tag CI`; este documento
**no** adelanta cifras que no se hayan medido.

## 5. Límites declarados

- **AUTO sigue OFF**; operativa **100 % PAPER virtual**, sin LIVE ni XTB real.
- La ventana PAPER sigue **`INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`): este sello **no la
  mueve** y **no demuestra rentabilidad**.
- Corregir la representación **no** corrige la fuente: un `unknown` de fill sigue siendo un
  desconocimiento real del bróker, y una cartera ilegible sigue siendo ilegible.
- El gate `FALSE_ZERO_SURFACES` **no** se amplía a Mesa/Mercado/AUTO: quedan `?? 0` de nivel 2 que
  alimentan cálculos, no cifras de primer nivel.
- Los **P2 restantes** (P2-03, P2-05…P2-12) y los **P3** siguen abiertos y declarados.
- El bump mueve `apps`, así que el pin PAPER se re-ancla **después** del commit del sello; los días
  anteriores quedan **`STALE`** y no se reinterpretan.

## 6. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | Un error de lectura nunca se pinta como vacío | `query-absence.test.ts` + las seis render tests fallan si vuelve `data ?? []` |
| 2 | Ningún desenlace distinto de `executed` dice «ejecutada» | `pending-order-fill.test.ts` falla si la copia de `skipped`/`unknown` imita la de `executed` |
| 3 | Las comisiones son el histórico, no la página | `history-page-fees.test.tsx` falla si la tarjeta suma las filas visibles |
| 4 | El color declara el papel, no el signo | `history-page-tone.test.tsx` falla si una `fee` sale verde |
| 5 | Sin ranking no se acusa al usuario de universo pequeño | `mesa-candidates-panel-absence.test.tsx` falla si reaparece el CTA |
| 6 | Cartera caída no es «sin stops» | `mesa-portfolio-absence.test.tsx` falla si reaparece la frase de seguridad |
| 7 | El hueco se declara en el texto, no con `—` | `history-page-dash-absence.test.tsx` y `data-freshness.test.ts` fallan si vuelve el comodín |
| 8 | Un P&L no medido nunca se colorea como positivo | `pnl-tone.test.ts` y las tres render tests fallan si vuelve `(x ?? 0) >= 0` |
| 9 | «Controlado» exige los tres componentes medidos | `auto-risk-summary.test.ts` falla si `fillLinkIssuesCount ?? 0` vuelve a producir `ok` |
| 10 | El contrato solo crece | `pnpm contract:check` falla si `openapi.json`/`schema.d.ts` divergen |
| 11 | El bump es coherente | `test_dia_d_bump_guard` falla si un `meta.bump` difiere de `package.json` |
