# Traspaso R-6 — Re-auditoría de superficie completa (web + api-python + shared): barrido read-only + corrección de los 4 Altos de dinero/verdad

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §5.
> **Fase:** R-6 — ampliación de la re-auditoría 2026-08-20 de "deuda abierta/operativa" a **superficie completa** (web + api-python + shared/domain/analytics), por barrido transversal **read-only** y corrección de los hallazgos de riesgo ALTO de dinero/verdad.
> **Estado:** **COMPLETADO en `main`** (3 commits de fix directos: `a64f4d0` F-1 + `da8aee5` F-4 + `8731827` F-2, en procesos de doc/push; árbol limpio a final de fase).
> **AsOf:** 2026-08-20.

---

## 1. Resumen

El hilo de re-auditoría 2026-08-20 arrancó acotado a "deuda abierta/operativa" que cerró **R-5**. Al retomar (2026-08-20) el usuario eligió **ampliar el alcance a la superficie completa** (la segunda rama que se planteó al arrancar). Se ejecutó un **barrido transversal read-only** con 3 subagentes en paralelo (web / api-python / shared+py), priorización por **riesgo de dinero / verdad de resultados** y fiel al freeze (sin features; el barrido fue análisis puro).

Resultado: **inventario de deuda NUEVA** (Alto ×4, Medio ×13, Bajo ×5) + **no-deuda confirmada**. Se pactó con el usuario **corregir los 4 Altos** y documentar/inventariar el resto. Los 3 que eran fixes acotados se corrigieron; el 4º (**F-3**) resultó ser un **diseño intencional con trade-off**, y se documentó sin tocar.

## 2. Cómo se ejecutó (protocolo)

- 3 subagentes **read-only** (generalPurpose) en paralelo, uno por superficie, con dimensiones explícitas (integridad/contrato/seguridad/buenas prácticas/tests) y **instrucción de NO reportar** la deuda ya cerrada (F1→R5).
- El coordinador **verificó personalmente** los hallazgos de riesgo Alto (y los key Medio) estudiando el código real antes de aceptarlos.
- Corrección: 3 subagentes acotados en paralelo (archivos disjuntos), **sin commitear**; batería por subagente; revisión de diffs por el coordinador; **aprobación del usuario por commit**; commits convencionales directos en `main`.

## 3. Hallazgos corregidos — 3 de los 4 Altos

### F-1 — Parser es-ES de cantidades (error ×1000) — `a64f4d0`

- **Problema:** `parseNumber` en `order-dialog.tsx` (`value.replace(",", ".")` + `parseFloat`) e `account-detail-panel.tsx` (`Number(amount.replace(",", "."))`) ignoraban el **separador de miles es-ES**. Escribir `1.500` (1500 acciones/€) se parseaba como **1.5 → error de magnitud ×1000** en órdenes, depósitos, retiradas y precio límite.
- **Fix:** `parseLocalizedNumber()` en `apps/web/src/lib/format.ts` — normaliza `.` como separador de miles (regex `\.(?=\d{3}(\.|,|$))`) y `,` decimal; devuelve `null` para entrada no numérica. Aplicada en `order-dialog.tsx` (4 call-sites: cantidad, valor, precio límite, valor estimado) y `account-detail-panel.tsx`. Validación de `qty` existente (`!isFinite(qty) || qty <= 0` line 121) conservada.
- Test: `apps/web/src/lib/format.test.ts` (9 casos). Casos: `1.500`→1500, `1500`→1500, `1,5`→1.5, `1.500,75`→1500.75, `0`→0, `1.5`→1.5, `1.234.567,89`→1234567.89, vacío/`abc`/`1,2,3`→null.
- **Matiz conocido (decision del parser):** `0.123` (fracción con 3 decimales) se interpreta como 123 por el rule de miles. Negligible en acciones/cantidades enteras de esta app (lotes enteros); anotado como trade-off del parser.

### F-4 — Lógica fiscal muerta/divergente en `packages/shared/src/tax-report.ts` — `da8aee5`

- **Problema:** `tax-report.ts` duplicaba el cálculo fiscal del backend (`buildTaxReport` + helpers FIFO/average/realized gains) **sin importadores en TS** (dead) y **divergente** del dominio Python — p.ej. `feesPaidTotal` (line 248) sumaba fees de TODAS las transacciones sin filtro de ejercicio fiscal (frente a F-FIN-2 del BE). Riesgo de sobrecontar fees si alguien lo usara.
- **Fix:** eliminadas 262 líneas de cómputo muerto (`buildTaxReport`, `computeRealizedGains`, `computeFifoRealized`, `computeAverageRealized`, `toReportTx`, `sortByDate`, `isInFiscalYear`, `periodLabel`, `mapLedgerFeesToTransactions`, interfaces `TaxReportTransaction`/`BuildTaxReportInput`, imports huérfanos). **Conservados los DTO types** `TaxReportSummaryDto`/`RealizedGainLineDto`/`UnrealizedGainLineDto` (consumidos por `apps/web/src/features/fiscal/tax-report-page.tsx`). Re-export de `index.ts:83` intacto.

### F-2 — Retención de dividendos US 15 vs 30 — `8731827`

- **Problema:** dos catálogos paralelos `TAX_PRESETS` divergían en US: FE (`account-settings.ts`) = 15, dominio (`account_settings.py`) = **30** (fuente de verdad para dinero). Al crear cuenta US el FE prellenaba 15 y el BE lo almacenaba como tal, divergiendo del default canónico del dominio.
- **Fix:** `account-settings.ts` → `US.dividendWithholdingPct` 15→30; test de paridad nuevo `account-settings.test.ts` (ES=19/EU_OTHER=15/CUSTOM=0 corroborados).
- **Nota de proceso:** el hook `lint-staged` aplicó `prettier --write` full-file a `account-settings.ts` (comillas simples→dobles) dentro de este commit. Verificado: el único cambio **semántico** es US=30; el resto es formato puro. Alinea el archivo con `format:check`. (Equivale a la opción "prettier*account_settings" que el usuario \_podía* haber elegido; se aplicó por el hook.)

## 4. F-3 — Sync workspace solo-aditivo: DOCUMENTADO, NO tocado (decisión del usuario)

- **Veredicto:** el merge de `workspace-slice-account.ts`/`chart-list-snapshot.ts` es **additivo por diseño deliberado** (comentario en `syncWorkspaceFromServer`/`mergeWorkspaceChartState`: "evita que un pull/PUT remoto con menos tabs borre las abiertas en este dispositivo"). Un **borrado de drawings/snapshots en otro dispositivo nunca se propaga** (no hay tombstones/last-write-wins).
- **Decisión del usuario:** documentarlo como **deuda con trade-off intencional**, NO corregirlo en esta fase — un fix real (propagación de borrados / merge conflictivo con tombstones) es un **cambio del modelo de sync** que colisiona con el freeze "sin features nuevas" y tiene alto riesgo de regresión multi-dispositivo.
- **Anotado como** deuda de diseño futura (ver §6, listado f-F3).

## 5. Inventario de deuda NUEVA (de esta re-auditoría; priorizado por riesgo dinero/verdad)

El barrido read-only también produjo los siguientes hallazgos que **NO se corrigieron en esta fase** (inventario para fases futuras; se necesita decisión por fase).

### 🟠 Medio (representativos; listado completo en el resumen de hallazgos del hilo)

| Código | Superficie    | Hallazgo                                                                                                                                                                                            |
| ------ | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B-1    | api           | `backtests.py:212-214` — `except Exception` → 500 con `detail=f"...{exc}"`: fuga de mensaje de excepción crudo al body HTTP.                                                                        |
| B-2    | api           | `scans.py:85-88` — `except Exception` se traga la persistencia de `ScanManifest` y devuelve 200 → huella fuente-de-verdad del scan perdida en silencio.                                             |
| B-3    | api           | `ai_governance.py:144-147` — `/ai/effectiveness` fail-open: cualquier fallo → 200 `insufficient_data` + filtra `PG: <exc>`.                                                                         |
| B-4    | api           | `ai_governance.py:387-401` — `/ai/intents/confirm` (puede ejecutar trade) no normaliza errores (sin try/except, vs `/portfolio/trade`) → 500 genérico.                                              |
| B-5    | api           | `strategies.py:159-164` — `create_strategy` create-then-update no atómico + parcheo de `id` en el blob.                                                                                             |
| B-6    | api           | `research.py:629` — `session.commit()` explícito a media ruta (único), antes de mapear DTO → fila persistida + 500 si falla el mapeo → reintento duplica.                                           |
| B-7    | py analytics  | `pattern_uptrend_v1.py:33` — `_pivot_indices` usa ventana 2-lateral (`index±window`) → no-causal; **no** está en `_NON_CAUSAL_OUTPUT_LINES` (guard asimétrico). Latente (hoy no alimenta backtest). |
| W-1    | web           | Poll sin cancel/AbortController + `setState` post-unmount + guard parcial de doble-ejecución (`pending-orders-monitor.tsx`, `list-hub-index-search.tsx`).                                           |
| W-2    | web           | `use-active-account.ts:99-103` — `setActiveAccountId` optimista sin `onError`/rollback si `setDefaultAccount` falla.                                                                                |
| W-3    | web           | `mandate-tenure-pnl.ts:37-41` — lo que no es `"buy"` cuenta como sell en tenure cashflow (fees/dividendos/transfers inflan PnL).                                                                    |
| W-4    | web           | `formatPct` `.toFixed(1)` vs `.toFixed(2)` (`backtest-strategy-matrix.ts:453` vs `chart-utils.ts:307`) → métrica desalineada entre matrix y ranking.                                                |
| S-1    | shared/domain | `calculateTradeFees` TS float sin redondeo vs `Decimal` 4dp ROUND_HALF_UP → diff en céntimos FE vs BE.                                                                                              |
| S-2    | web           | endpoints API duplicados por URL en `lib/api.ts` (brindges `fetch`).                                                                                                                                |
| S-3    | web           | `auth-store.ts` bootstrap de login con `fetch` crudo (drift potencial).                                                                                                                             |

### 🟢 Bajo

- L-1 `Timeframe` (5) vs `ChartTimeframe` (9) union legacy sub-tipa wire `30m/4h/1wk/1mo`.
- L-2 `gated` mode ignora `entry_short` en silencio (long-only no documentado).
- L-3 3 exports muertos (`format.ts:58-63`, `ibex35-operativa-audit.ts:519`, `lab-zone-verdict.tsx:130-142`).
- L-4 `backtest-finalists-freshness.ts` reescribe todo el map sin debounce.
- L-5 `mandates.py:84-100` `account_id` embebido viene del cliente (bajo en single-user).
- L-6 **Prettier de `packages/shared/src/account-settings.ts`** pre-existente: comillas simples. (Quedó resuelto en `8731827` por lint-staged).

### f-F3 — Deuda de diseño (documentada, no bug)

- Sync workspace únicamente aditivo → los borrados en otro device no se propagan (trade-off intencional; ver §4).

### ⚠️ Hábitos importantes (no-deuda confirmada, ~no re-auditar)

- **Domain purity: 0 violaciones** (import-linter limpio en `packages/py/domain`).
- **Fidelidad de tipos shared ↔ schemas: sin gaps nuevos** post R-3/R-4 (portfolio/account/position/execution/backtest/optimize verificados 1:1). **El contrato sigue VERDE (D5).**
- Correcciones de la ola F1→R5 confirmadas intactas (with_for_update, CORS, rate-limit, compare_digest, fail-closed prod, redacción secretos, causalidad chikou/fractales).
- Los `# noqa`/`# type: ignore` intencionales (SQLAlchemy 2.0 Mapped, longitud línea) no son deuda (mypy gate a 0).

### 🔴 Mayor agujero de cobertura (NUEVO para el próximo paso)

El subagente backend señala: **la lógica de dinero real (use-cases/repos/invariantes) vive en `packages/py/{application,infrastructure}`** — quedó **fuera del surface** pactado (eran web+api+shared). Si se quiere una auditoría profunda de dinero, es una **tanda separada** (recomendada dada la prioridad dinero/verdad).

## 6. Deuda futura / fuera de alcance de R-6 (no abrir sin decisión explícita)

- Ampliar auditoría a `packages/py/application + infrastructure` (lógica de dinero real) — **tanda nueva recomendada**.
- Corregir los Altos restantes se descartó por decisión (B-_/W-_/S-\* del §5 son Medio/Bajo). Cada uno = una fase acotada si se decide.
- F-3 sync solo-aditivo (ver §4).
- Heredadas del relevo: `MandateTenure`/`MandateTradeLink` web-only; inner `data` AI shape-abierto por diseño; alias wrapper cosmético; transferencias/dividendos (P2.3); `BP/.L`→`BP.L` en BD.
- **Freeze vigente:** sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA · auth JWT diferida (D4).

## 7. Batería (toda verde al cerrar)

| Comprobación                                   | Resultado                                                                 |
| ---------------------------------------------- | ------------------------------------------------------------------------- |
| `@bolsa/web typecheck`                         | ✅                                                                        |
| `@bolsa/web lint`                              | ✅ (solo warning preexistente `MODULE_TYPELESS_PACKAGE_JSON`, inofensivo) |
| `@bolsa/web test` (vitest)                     | ✅ 141 ficheros / 716 tests (incl. `format.test.ts` 9 casos)              |
| `@bolsa/shared typecheck`                      | ✅                                                                        |
| `@bolsa/shared lint`                           | ✅                                                                        |
| `@bolsa/shared test`                           | ✅ 4 ficheros / 17 tests (incl. `account-settings.test.ts` 2 nuevos)      |
| Prettier check (todos los archivos del cambio) | ✅                                                                        |

## 8. Texto de traspaso (para el próximo chat)

> CONTEXTO (2026-08-20): **R-6 — Re-auditoría de superficie completa COMPLETADA en `main`**. Alcance **ampliado** (por decisión del usuario) de "deuda abierta" a **toda la superficie** (web + api-python + shared/domain/analytics). Barrido transversal **read-only** (3 subagentes en paralelo, priorización por riesgo dinero/verdad; verificado personalmente por el coordinador). Inventario de deuda nueva: **Alto ×4, Medio ×13, Bajo ×5** + no-deuda confirmada.
>
> **Corregidos (4 Altos → 3 + 1 documentado):**
> **F-1** `a64f4d0` `fix(trading): parser tolerante es-ES` — `parseLocalizedNumber` en `lib/format.ts`, aplicado en `order-dialog.tsx` + `account-detail-panel.tsx`. Corrige el **error ×1000** al escribir `1.500` en órdenes/depósitos.
> **F-4** `da8aee5` `refactor(shared): eliminar logica fiscal muerta` — `tax-report.ts` 262 líneas de cómputo fiscal duplicado/divergente eliminadas; conserva los DTO types. Elimina el riesgo del `feesPaidTotal` sin filtro de ejercicio (F-FIN-2).
> **F-2** `8731827` `fix(shared): alinear retencion US` — `TAX_PRESETS.US.dividendWithholdingPct` 15→30 (dominio=fuente de verdad); test de paridad. Nota: lint-staged aplicó prettier full-file (solo formato; único valor US=30).
> **F-3** (sync workspace solo-aditivo) **DOCUMENTADO como deuda con trade-off, NO tocado** — merge aditivo intencional; fix de propagación de borrados = cambio del modelo sync (collides con freeze).
>
> Árbol limpio, CI a confirmar tras push. Estado vivo: `docs/engineering/PROJECT_STATE.md` (LEER PRIMERO, §6/§7) · `docs/engineering/engineering-index-2026-08-03.md` §5 · este traspaso (`traspaso-r6-reauditoria-superficie-2026-08-20.md`).
>
> **SIGUIENTES (candidatos por decisión):** (1) **auditar `packages/py/{application,infrastructure}`** = lógica de dinero real (mayor agujero de cobertura, quedó fuera del surface); (2) corregir los Medio de normalización de errores backend (B-1 fuga excepción, B-2 ScanManifest tragado, B-3 fail-open effectiveness, B-4 confirm sin try) y S-1 redondeo; (3) checklist operativo manual pendiente del relevo (secret scanning, `TRUSTED_PROXIES` prod, `BP/.L`→`BP.L`, logs dev).
>
> Regla: una fase = un subagente acotado + batería + aprobación por commit + relevo documentado al cerrar chat. Freeze vigente: sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA. Auth JWT diferida (D4).
