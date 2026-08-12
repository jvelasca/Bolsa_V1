# Traspaso — F5c Frontend Clean-up (2026-08-12)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5 (sub-entrada de la Auditoría consolidada, junto a F1/F2/F3b/F5a/F3a/F4/F5b).
> **Fuentes de verdad (leer primero):** [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md) (P2.6/P2.8/P2.1 + D0–D5) · [traspaso-f5b-backend-seguridad-2026-08-12.md](./traspaso-f5b-backend-seguridad-2026-08-12.md) (§8: siguiente fase tras F5b).
> **Rama de ejecución:** `stage/f5c-frontend-cleanup-2026-08-12` (desgajada desde `stage/f1-*`, tras merge PR #35/F5b).
> **Regla del hilo:** NO tocar código fuera del alcance F5c pactado. Cambios validados con la batería antes del commit.
> **Estado:** F5c COMPLETADO (P2.8 + P2.6) con **P2.1 diferido a hilo propio** (decisión del usuario). Ver §4–§7.

---

## 0. Alcance pactado (decisión del usuario, este hilo)

Tras F5b (backend/seguridad), el usuario eligió la opción **F5c clean-up frontend**: la parte
frontend de F5 que F5b dejó pendiente. Alcance pactado D5 (cero features) sobre los hallazgos:

- **P2.8** — Higiene frontend: `toLocaleString("es-ES")` duplicado (centralizar), timers `window.set*`,
  `as unknown as`. Se ejecuta (parcial, ver §5 — los `as unknown as` quedan como residue registrado).
- **P2.6** — `packages/shared`: sin script `test` propio + lógica duplicada TS↔Py. Se ejecuta
  (script `test` + config vitest + test de paridad del Policy Gate).
- **P2.1** — God-components `backtests-page.tsx` (~4930 líneas) y `workspace-store.ts` (~3980):
  **NO se parte en este hilo.** Decisión del usuario de **diferir a hilo propio dedicado** (mismo
  patrón M5: cada frente god-component se partió en un chat aparte con batería por paso).

## 1. Diagnóstico confirmado en código

- **P2.8 `toLocaleString`**: 45 call sites con `toLocaleString("es-ES")` / `toLocaleDateString("es-ES")`
  dispersos en ~30 ficheros de features; **ninguno en `src/lib`** (no había util de formato compartido).
  Además ~8 helpers locales duplicados (`formatDateTime`, `formatBarDate`, `formatNumber`…) en varios
  ficheros.
- **P2.8 timers**: 11 llamadas "bare" a `setTimeout`/`setInterval` (sin `window.`) en 9 ficheros;
  los handles se tipaban como `ReturnType<typeof setTimeout>` (= `Timeout` de Node, por `@types/node`
  - `lib: DOM`) cuando el uso real es id de timer de browser.
- **P2.6**: `packages/shared` (~108 fuentes) **sin script `test`**; su único test
  (`market-indices.test.ts`) era **huérfano** — lo ignoraban todos los runners (el vitest de
  `apps/web` sólo incluye `src/**/*.test.ts`). No hay config vitest en shared. Lógica TS↔Py duplicada:
  `cognitive/policy-gate.ts` ↔ `analytics/cognitive/policy_gate.py` (contrato RFC-008 idéntico);
  `ai-indicator-series.ts` ↔ `signals/technical_rating_v1.py` + `indicators/compute.py`;
  `ai-indicator-series.ts` (parte data-quality) ↔ `signals/data_quality_v1.py`.
- **P2.1**: `workspace-store.ts` = **un solo store** Zustand monolítico (~3983 líneas, ~100 acciones,
  ~60 consumidores, lee estados hermanos con `get()`; NO maneja backtests/trials/accounts/auth).
  `backtests-page.tsx` = **un solo `BacktestsPage`** (303–5129) de orquestación: ya había ~30
  subcomponentes extraídos (M5), quedan bloques de lógica/state acoplados
  (`settleFullCycle` 2764–2968, `runListBatch` 1243–1371, `runCoachBattery` 1437–1612,
  `startOptimizeFromExplore` 1939–2080) + ~70 `useState`/15 `useRef` que cierran sobre decenas de
  setters/refs → extracción no mecánica.

## 2. Decisiones de diseño (F5c)

- **P2.8**: crear `apps/web/src/lib/format.ts` como **punto único del locale "es-ES"** con helpers
  que **preservan la semántica exacta** de cada call site: `formatDateTime`, `formatDateTimeShort`,
  `formatDateTimeCompact`, `formatDate`, `formatNumber`, `formatNumber0`, `formatFxRate` + variantes
  genéricas con opciones (`formatDateWith`, `formatDateTimeWith`, `formatNumberWith`). Cada local
  helper duplicado delega al módulo compartido.
- **P2.8 timers**: migrar las 11 llamadas a `window.setTimeout`/`window.setInterval` y tipar los
  handles como `number` (en vez de `ReturnType<typeof setTimeout>`) para coherencia con el uso real
  (id opaco para `clearTimer`).
- **P2.6**: `packages/shared` gana `vitest.config.ts` (ambiente node; alias `@bolsa/shared` → `src/index.ts`
  y `@src` para resolver desde **fuente** en vez de `dist`, evitando depender de un build previo) +
  script `test` (`vitest run`). Se añade `policy-gate.test.ts` que congela el **contrato TS** del
  Policy Gate (reglas incondicionales + vetos) y documenta la paridad con el lado Python. Se añade
  paso `Test shared` a `frontend-ci.yml` para que sus tests corran en CI.
- **P2.1 (diferido)**: no se toca. Registrado como deuda de hilo dedicado (§5).

## 3. Implementación (por sub-área)

| Fichero(s)                                                                      | Qué                                                                                                     |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `apps/web/src/lib/format.ts` (nuevo)                                            | Util central de locale "es-ES" (fechas/números/tipos) con helpers específicos + variantes con opciones. |
| `apps/web/src/lib/format.test.ts` (nuevo)                                       | 7 tests (locale, separadores, decimales fx) en vitest.                                                  |
| 29 call sites / helpers locales en `apps/web/src/features/**`                   | Migración de `toLocaleString("es-ES")`/`toLocaleDateString("es-ES")` a `lib/format` (P2.8).             |
| 9 ficheros (`stores/auth-store.ts`, `stores/workspace-store.ts`, `features/**`) | 11 timers bare → `window.set*` + tipos `number` (P2.8).                                                 |
| `packages/shared/package.json`                                                  | script `test: vitest run` (P2.6).                                                                       |
| `packages/shared/vitest.config.ts` (nuevo)                                      | Config vitest (node, alias a src, include `src/**/*.test.ts`).                                          |
| `packages/shared/src/cognitive/policy-gate.test.ts` (nuevo)                     | 8 tests de paridad TS↔Py del Policy Gate (P2.6).                                                        |
| `.github/workflows/frontend-ci.yml`                                             | Pasos `Typecheck shared` + `Test shared` (los tests del paquete ahora corren en CI; antes huérfanos).   |

## 4. Validación (batería aplicada)

- **pytest**: no se tocó backend → sin cambios (verde en rama base).
- **shared**: `pnpm --filter @bolsa/shared test` → **10 passed** (market-indices 2 + policy-gate 8);
  `typecheck` ✓; `lint` ✓.
- **web**: `typecheck` ✓ · `lint` 0 errores (solo warning preexistente de eslint.config) · `test`
  **714 passed** (141 ficheros; incluye +7 del nuevo `format.test.ts` frente al baseline 707).
- **CI**: `frontend-ci.yml` ahora ejecuta `test shared` y `typecheck shared` además del web; sin
  cambio de dependencias → `pnpm install --frozen-lockfile` no se ve afectado (solo scripts/files).

## 5. Deuda / fuera de alcance (registrado, NO resuelto)

- **P2.1 — God-components `backtests-page.tsx` y `workspace-store.ts`**: **hilo propio dedicado**
  (decisión del usuario). Mapa ya levantado para ese hilo: workspace-store es un solo store de ~100
  acciones (→ slicning Zustand compartiendo persist), backtests-page es una orquestación con lógica
  acoplada (settleFullCycle/runListBatch/runCoachBattery/startOptimizeFromExplore cierran sobre decenas
  de setters/refs). Ver mapas completos en el historial de este hilo.
- **P2.8 residue**: los **8 `as unknown as`** (core-r-sync.ts ×3, backtest-explore-panel.tsx ×2,
  supervised-f3-sync.ts, trading-dia-d-replay-panel.tsx, y 1 en test) se **registran como bridges
  tipados intencionales** hacia payloads `Record<string, unknown>` (serialización a servidor);
  sustituirlos por DTOs fuertemente tipados es de la fase de **fidelidad de contratos (F5a §6)**,
  no de higiene P2.8.
- **P2.6 residue**: duplicación TS↔Py en `ai-indicator-series.ts` (technical_rating/data_quality) y
  `execution-policies`/`position-policies`/`tracker-definitions`/`tax-report` vs python: **solo se
  añadió test de paridad del policy-gate** (el más claro). Reconciliar el resto de duplicados es fase
  posterior (quién es fuente de verdad TS vs Py) y exige un acuerdo de diseño, NO se tocó.
- **Timers**: en `apps/web/src` quedan 30 llamadas ya `window.`-prefixed (bien) — no requieren cambio.

## 6. Registro

| Fecha      | Acción                                                                                                                                                  |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-12 | Rama `stage/f5c-frontend-cleanup-2026-08-12` desde `stage/f1-*` (base `96da863` = tip F5b mergeado). Alcance pactado: F5c frontend (P2.8+P2.6+P2.1).    |
| 2026-08-12 | P2.8: `lib/format.ts` + test; migración de 29 call sites/helpers locales (commit `e72650d`, 31 ficheros).                                               |
| 2026-08-12 | P2.8b: 11 timers → `window.set*` + tipos `number` (commit `d908ac2`, 8 ficheros).                                                                       |
| 2026-08-12 | P2.6: script `test` + `vitest.config.ts` en shared + `policy-gate.test.ts` (8 tests) + pasos CI `Typecheck/Test shared` (commit `d9ae632`, 4 ficheros). |
| 2026-08-12 | Batería final: shared 10✓ + web typecheck✓ lint✓ test 714✓. Push rama.                                                                                  |
| 2026-08-12 | **Decisión usuario**: cerrar F5c (P2.8+P2.6) y **diferir P2.1 a hilo propio**. Cierre: traspaso + engineering-index + texto exacto.                     |

## 7. Protocolo recurrente (obligatorio en TODOS los hilos)

> Norma permanente del proyecto. Al cerrar: preparar el siguiente con su `traspaso-*`, entrada
> única en `engineering-index`, y entregar en el chat el **texto exacto** para pegar en el próximo.

## 8. Texto exacto de traspaso — siguiente hilo (tras F5c)

```text
Texto de traspaso → nuevo chat (F5c completado — siguiente fase tras F5c)

CONTEXTO INMEDIATO: F5c (Frontend clean-up de la parte frontend de F5) COMPLETADO en rama
  stage/f5c-frontend-cleanup-2026-08-12 (desde stage/f1-* tras merge PR #35/F5b; base 96da863).
  - P2.8 formato es-ES centralizado: nuevo apps/web/src/lib/format.ts (punto único del locale,
    helpers específicos + variantes con opciones; preserva semántica exacta) + format.test.ts (7).
    Migrados 29 call sites/helpers locales (`toLocaleString("es-ES")` dispersos en ~30 ficheros).
  - P2.8 timers: 11 llamadas bare → window.setTimeout/setInterval y handles tipados number
    (antes ReturnType<typeof setTimeout>=Timeout de Node). Verificado typecheck+lint+test.
  - P2.6 packages/shared: script "test" (vitest run) + vitest.config.ts (alias a src, node);
    test de paridad policy-gate.test.ts (8) TS↔Py (RFC-008); pasos CI Frontend "Typecheck shared"
    + "Test shared" (antes el único test era huérfano, ningún runner lo ejecutaba).
  - BATERÍA (verde): shared test 10✓ typecheck✓ lint✓ · web typecheck✓ lint 0 test 714✓ (141 f).
  - COMMITS: e72650d (P2.8 formato) · d908ac2 (P2.8 timers) · d9ae632 (P2.6 shared). Rama pushada.

DEUDA REGISTRADA → fases posteriores:
  - P2.1 god-components (backtests-page.tsx ~4930 líneas orquestación + workspace-store.ts ~3983
    líneas un solo store, ~100 acciones, ~60 consumidores): HILO PROPIO DEDICADO (decisión usuario).
    Mapa listo en este hilo: workspace-store → slicing Zustand compartiendo persist; backtests-page
    → extraer settleFullCycle/runListBatch/runCoachBattery/startOptimizeFromExplore (cierran sobre
    decenas de setters/refs, no mecánico).
  - P2.8 residue "as unknown as" (8): bridges tipados intencionales a Record<string,unknown> para
    serialización; sustituir por DTOs → fase fidelidad contratos (F5a §6).
  - P2.6 residue: reconciliar duplicación TS↔Py restante (ai-indicator-series ↔ technical_rating/
    data_quality; execution-policies/position-policies/tracker-definitions/tax-report ↔ py): exige
    acuerdo de diseño de fuente de verdad, no tocado.
  - Deuda previa sin resolver: P1.9 API thin (hilo propio), P1.3 auth full (D4 diferido), F5a §6
    fidelidad DTOs/openapi-fetch, mypy preexistente por fases.

Lee PRIMERO: docs/engineering/traspaso-f5c-frontend-cleanup-2026-08-12.md (§4-§7) y su fuente
  audit-consolidado-internas-externas-2026-08-11.md (P2.1/P2.6/P2.8 + D0-D5). Para la fase siguiente
  usa engineering-index-2026-08-03.md y el plan de la fase declarada.
NO toques código fuera del alcance de la fase que se declare.
```
