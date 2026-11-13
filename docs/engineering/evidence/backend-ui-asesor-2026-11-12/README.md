# Evidencia · Asesor backend ↔ UI · 2026-11-12

> Alcance: cierre de las ocho observaciones (R-01…R-08) de la revisión estática del bloque
> de concordancia backend ↔ UI de Asesor: orden cache-first de H-2, tri-estado de la
> posición, memoización de estructura, polling del Diario y transparencia de precio.
>
> Método: lectura estática, ejecución **dirigida** de las suites del propio bloque y, desde el
> mismo 2026-11-12, los **gates locales** de §6 (shared completo, `contract:check` real,
> typecheck, lint, suite web completa, build y E2E dirigido con axe). Sin commit, sin migración,
> sin `contract:gen` con cambios, sin CI (no hay push autorizado), sin tocar S0/F4-067 ni
> `heading-order`.
>
> Veredicto: **PASS por lectura estática más gates locales en verde, con las ocho observaciones
> cerradas**. No es CI verde, ni una certificación dinámica, ni una aprobación de release.

## 1 · Conformidades comprobadas

| Afirmación | Dónde |
| --- | --- |
| La caché se lee antes de cualquier chip y `force_refresh` la salta | [`daily_opinion_service.py`](../../../packages/py/application/src/bolsa_application/daily_opinion_service.py) L177–221 |
| La cartera se mide una sola vez por consulta (`measure_open_positions`) | `daily_opinion_service.py` L187–192 |
| Los chips se piden solo para `miss_ids` y no repiten la lectura de cartera | `daily_opinion_service.py` L113–130 y L215–221 |
| Se sirve caché solo si la posición sigue siendo verificable | `daily_opinion_service.py` L207–212 |
| `None` significa «no medido» y no se degrada a `False` | [`daily_opinion_hints.py`](../../../packages/py/application/src/bolsa_application/daily_opinion_hints.py) L107–121 y L208–230 |
| No se persiste un dictamen con cartera no medida | `daily_opinion_service.py` L242 y L457–481 |
| El clasificador solo usa dictamen + posición medida + causa de `no_trade` | [`asesor-cartera.ts`](../../../packages/shared/src/cognitive/asesor-cartera.ts) L186–240 |
| La estructura se memoiza por identidad del array de velas | [`use-asesor-cartera-data.ts`](../../../apps/web/src/features/research/use-asesor-cartera-data.ts) L199–213 |
| Cotizaciones y velas a 5 min, cartera y estudios a 60 s | `use-asesor-cartera-data.ts` L55–58 |
| `refetchOnWindowFocus: false` en cotizaciones y velas | `use-asesor-cartera-data.ts` L282 y L313 |
| Diario con `refetchInterval` de 5 min y `staleTime` de 60 s | [`asesor-daily-ops-panel.tsx`](../../../apps/web/src/features/research/asesor-daily-ops-panel.tsx) L190–191 |
| «Midiendo», «ausente» y «medido» se exponen por separado | `use-asesor-cartera-data.ts` L472–474 y `asesor-cartera-panel.tsx` L410–460 |

## 2 · Observaciones cerradas

| # | Corrección | Archivos |
| --- | --- | --- |
| R-01 | El texto de `posicion_abierta` ya no niega las posturas que clasifica: «Hay posición abierta; la recomendación del dictamen conserva su propio nombre». La tabla §4 de S3 incluye `buy` con posición. | `asesor-cartera.ts` L106–110 · [`diseno-asesor-cartera-s3-2026-11-12.md`](../../diseno-asesor-cartera-s3-2026-11-12.md) §4 |
| R-02 | Un `ioScore` no medido suma el hueco «Calidad de señal sin medir» a la recomendación y a la fila; `uniqueGaps` lo deduplica con la causa `io_unmeasured`. | `asesor-cartera.ts` L533 |
| R-03 | Tests nuevos para `quotesLoading` (con y sin precio) y para `opinionsLoading` en recomendación y tendencia. | [`asesor-cartera-panel.test.tsx`](../../../apps/web/src/features/research/asesor-cartera-panel.test.tsx) L585–645 |
| R-04 | El precio declara su fuente: `source: "mercado" \| "cartera"`. Con precio de cartera la celda dice «Precio de cartera · Midiendo cierre…» o «· sin cierre de mercado»; con cotización sin fecha, «Cotización sin fecha declarada»; sin precio y cargando, «Midiendo cotizaciones…». | `asesor-cartera.ts` L246–272 y L455 · `use-asesor-cartera-data.ts` L409–428 · `asesor-cartera-panel.tsx` L410–460 · [`diseno-asesor-backend-ui-2026-11-12.md`](../../diseno-asesor-backend-ui-2026-11-12.md) §3–§4 |
| R-05 | Cifras no trazables retiradas; ver §4. | este documento |
| R-06 | Esta carpeta: evidencia propia del bloque, con comandos y salida real. | `docs/engineering/evidence/backend-ui-asesor-2026-11-12/` |
| R-07 | Corregida la atribución de los dos módulos Python: no son rutas de F4-067. | [`evidence/s3-asesor-cartera-2026-11-12/README.md`](../s3-asesor-cartera-2026-11-12/README.md) §1 |
| R-08 | Imports de `react-router-dom` agrupados en una sola sentencia. | `asesor-cartera-panel.tsx` L22 |

## 3 · Verificación dirigida ejecutada

Salida real de esta sesión (2026-11-12):

```text
uv run python -m pytest packages/py/application/tests/test_daily_opinion_service_hints.py \
  packages/py/application/tests/test_daily_opinion_stance.py -q
25 passed in 0.65s

pnpm --filter @bolsa/shared build
> tsc
(exit 0)

pnpm --filter @bolsa/shared test -- asesor-cartera
✓ src/cognitive/asesor-cartera.test.ts (44 tests)
Test Files  1 passed (1) · Tests  44 passed (44)

pnpm --filter @bolsa/web test -- asesor-cartera
✓ src/features/research/use-asesor-cartera-data.test.ts (8 tests)
✓ src/features/research/asesor-cartera-panel.test.tsx (26 tests)
Test Files  2 passed (2) · Tests  34 passed (34)

pnpm --filter @bolsa/web test -- research-first-level
✓ src/features/research/research-first-level.test.tsx (8 tests)
Test Files  1 passed (1) · Tests  8 passed (8)

pnpm --filter @bolsa/web typecheck
> tsc -b --noEmit
(exit 0)
```

La compilación de `packages/shared` precede a las suites web porque `apps/web` consume
`dist/`; no genera artefactos versionados.

## 4 · Cifras retiradas y cifras verificables

Las cifras comunicadas de **«2.922 tests web»** y **«mypy sobre 601 archivos»** no aparecen
en ningún documento de este bloque y **no se reproducen aquí**: se retiran.

Cifras verificables que sí están documentadas o medidas:

| Cifra | Origen |
| --- | --- |
| Web 388 archivos / 2.899 pruebas | [`certificacion-s5-rediseno-2026-11-12.md`](../../certificacion-s5-rediseno-2026-11-12.md) §7 |
| F4-067: 377 archivos / 2.801 pruebas · mypy 599 ficheros | [`acta-f4-067-opinion-account-scope-2026-11-12.md`](../../acta-f4-067-opinion-account-scope-2026-11-12.md) §7 |
| pytest 25 · shared 44 · web Asesor 34 · primer nivel 8 | §3 de este documento (ejecución de esta sesión) |
| Shared 107 archivos / 1.034 pruebas (+1 `todo`) | §6 de este documento (gates locales, 2026-11-12) |
| Web 389 archivos / 2.925 pruebas | §6 de este documento (gates locales, 2026-11-12) |

## 5 · Límites

- Revisión **estática** más suites **dirigidas** y, desde el 2026-11-12, los gates locales de §6:
  no es una auditoría independiente del diff.
- **CI no ejecutado**: los workflows corren en GitHub y requieren push/PR, que no está
  autorizado. Verde local ≠ CI verde.
- E2E ejecutado solo en su variante **mock** y **dirigida** (S5 y rutas tocadas). Los E2E
  `integrated`/`live` —API + PostgreSQL + barras— no se ejecutaron.
- La reserva de `heading-order` se reprodujo como **no bloqueante** (impacto `moderate`): el
  barrido axe de §6 falla solo con `critical`/`serious` y el gate unitario `heading-order`
  está verde. No se corrige aquí: sigue fuera de alcance.
- No se demuestra `Δ motor = 0` por ejecución ni la ausencia de migraciones nuevas.
- No se midió el comportamiento en runtime: número real de lecturas de cartera por consulta
  ni efecto real del memo. Solo se leyó su implementación y sus tests.
- S0/F4-067 y el seguimiento de `heading-order` siguen fuera de alcance y sin autorización.

## 6 · Gates pendientes ejecutados (local, 2026-11-12)

Ejecución local sobre el árbol de `feat/f4-067-opinion-account-scope` en `HEAD` = `bcdc4584`,
con el índice vacío. Foto previa y posterior de `git status --porcelain=v1`: **121 entradas en
ambas**, sin cambios de índice ni de contenido versionado tras los gates.

### 6.1 · Comandos y salida real

```text
pnpm --filter @bolsa/shared build
> tsc
(exit 0)

pnpm --filter @bolsa/shared typecheck
> tsc --noEmit
(exit 0)

pnpm --filter @bolsa/shared test
✓ src/cognitive/asesor-cartera.test.ts (44 tests)
✓ src/market-structure.test.ts (34 tests)
✓ src/market-vocabulary.test.ts (40 tests)
Test Files  107 passed (107)
     Tests  1034 passed | 1 todo (1035)
  Duration  3.92s
(exit 0)

pnpm --filter @bolsa/web contract:check
contract:check OK — openapi.json y schema.d.ts coinciden con el commit.
(exit 0)

pnpm --filter @bolsa/web typecheck
> tsc -b --noEmit
(exit 0)

pnpm --filter @bolsa/web lint
✖ 23 problems (0 errors, 23 warnings)
(exit 0)

pnpm --filter @bolsa/web test
Test Files  389 passed (389)
     Tests  2925 passed (2925)
  Duration  40.25s
(exit 0)

pnpm --filter @bolsa/web build
dist/assets/index-rPzZtHHc.js  2,665.04 kB │ gzip: 768.71 kB
✓ built in 5.62s
(exit 0)

$env:E2E_RUN="1"
pnpm --filter @bolsa/web exec playwright test gp-s5-rediseno
11 passed (15.9s)
(exit 0)

pnpm --filter @bolsa/web exec playwright test gp-e2e-ui5-0-axe-touched-routes-mock
35 passed (25.7s)
(exit 0)
```

### 6.2 · Lectura de cada gate

| Gate | Resultado | Nota |
| --- | --- | --- |
| Shared build / typecheck | exit 0 | `dist/` reconstruido; no versionado |
| Shared suite completa | 107 archivos · 1.034 pruebas | cubre las 44 de `asesor-cartera` más `market-structure` y `market-vocabulary`, que §3 no ejecutaba |
| `contract:check` | OK | gate **real**: `uv` 0.12.3 disponible, volcó el spec desde FastAPI y regeneró `schema.d.ts`; ambos quedaron **byte a byte idénticos** a la copia previa (comparación SHA-256) |
| Web typecheck | exit 0 | `tsc -b --noEmit` |
| Web lint | 0 errores · 23 warnings | los 23 son `react-hooks/exhaustive-deps` de deuda legacy, ya declarados no bloqueantes en `frontend-ci.yml` |
| Web suite completa | 389 archivos · 2.925 pruebas | +1 archivo y +26 pruebas respecto a las 388/2.899 de la certificación S5: son los tests añadidos por este bloque |
| Web build | exit 0 · 5,62 s | solo warning de tamaño de `index-*.js`; preexistente |
| E2E S5 | 11 passed | los 6 escenarios de producto, responsive 3→2→1, dock, S2 y las dos filas de Asesor/Cartera; axe sin `critical`/`serious` |
| E2E axe rutas tocadas | 35 passed | 17 rutas × 2 cortes + command palette, incluida `/trading @desktop` con la deuda `heading-order` (moderate, no bloqueante) |

### 6.3 · Incidencias de entorno (no de producto)

- Primer intento de E2E: `browserType.launch` falló con `ENOENT` sobre
  `…\cursor-sandbox-cache\…\chromium_headless_shell-1234`. La variable
  `PLAYWRIGHT_BROWSERS_PATH` apuntaba a una caché vacía de sandbox, no a
  `%LOCALAPPDATA%\ms-playwright`. Se instaló el Chromium pineado
  (`playwright install chromium`, build `chromium-headless-shell v1234`) y se ejecutó con la
  variable retirada. Ningún test llegó a evaluar la UI en ese intento: fue un fallo de arranque.
- El Vite de `localhost:5173` ya estaba levantado y respondiendo 200; Playwright lo reutilizó
  (`reuseExistingServer: true`) en lugar de arrancar otro. No se mató ningún proceso.
- El spec S5 **regeneró** los PNG de
  [`evidence/s5-rediseno-2026-11-12/`](../s5-rediseno-2026-11-12/README.md). Son capturas de
  evidencia, no baselines de `toHaveScreenshot`; la carpeta no está versionada y no aparece en
  `git status`.

### 6.4 · Lo que estos gates siguen sin acreditar

- CI: no ejecutado (sin push/PR autorizado).
- E2E `integrated`/`live`: no ejecutados (exigen API, PostgreSQL y barras).
- Comportamiento en runtime: la suite prueba contratos y render, no el número real de lecturas
  de cartera por consulta ni el efecto del memo.
- S0/F4-067 y la corrección de `heading-order`: intactos.

## 7 · Veredicto

**PASS por lectura estática más gates locales en verde**, con R-01…R-08 cerradas, las suites
dirigidas de §3 y los gates de §6 (shared completo, `contract:check` real, typecheck, lint,
suite web completa, build y E2E dirigido con axe). Se conserva la naturaleza del dictamen: no
es CI verde, no es certificación dinámica —faltan E2E `integrated`/`live` y medición en
runtime— y no es aprobación de una nueva release. S0/F4-067 y `heading-order` siguen fuera de
alcance.

## 8 · Continuación: frentes pendientes cerrados (2026-11-12, segunda sesión)

Sesión posterior sobre el mismo árbol, `HEAD` = `bcdc4584`, índice vacío. **Sin `add`, `commit`,
`push`, tags ni cambio de rama.** El recuento de `git status --porcelain` pasa de 121 a 126
entradas; ninguna entrada previa se revierte ni se limpia. Los ficheros nuevos de esta sesión son
`test_instrument_daily_opinions_query_reads.py`, `use-asesor-cartera-data.hook.test.tsx`,
`test_estudio_daily_ops_portfolio_reads.py` y `decision-window-freeze-dispatch-2026-11-12.md`,
además del `h2` en el readout y de esta misma sección. Esta sección sustituye, para el árbol de trabajo, las reservas de §5 sobre `heading-order`
y E2E `integrated`/`live`.

### 8.1 · `heading-order` de `/trading`

El único salto real era `h1` «Mercado» → `h3` «Estructura y niveles calculados» del readout S2.
Corregido en [`market-structure-readout.tsx`](../../../apps/web/src/features/market-structure/market-structure-readout.tsx)
(L247): el título pasa a `h2` con las mismas clases, mismo texto y mismo `aria-label`. Se añaden
dos tests en [`market-structure-readout.test.tsx`](../../../apps/web/src/features/market-structure/market-structure-readout.test.tsx):
nivel 2 sin `h3` cuando se muestra, y ausencia de headings con `showHeading={false}`.

`pnpm --filter @bolsa/web test -- market-structure-readout` → **12 passed**.
`pnpm --filter @bolsa/web test -- trading-operativa` → **29 passed**.
El barrido axe integrado confirma **0 violaciones `heading-order`** en `/trading` en ambos
viewports.

### 8.2 · Medición en runtime

Convertidas en tests las cuatro afirmaciones que solo estaban leídas. Sin tocar producción.

| Afirmación | Test |
| --- | --- |
| Una lectura de cartera por consulta | `test_daily_opinion_service_hints.py`: `positions.calls == [ACCOUNT]` y `== [ACCOUNT, ACCOUNT]` |
| 0 lecturas con hints internos | `test_internal_hints_skip_position_read_even_when_port_is_injected` (puerto inyectado) |
| Chips solo para `miss_ids` | `FakeFundamentals.calls` + asertos en los tests de miss |
| El troceo no multiplica lecturas | `test_chunking_of_miss_ids_does_not_multiply_portfolio_reads` (81 ids → composite `[40,40,1]`, FA `[80,1]`, una lectura) |
| Una lectura por parte diario | `test_estudio_daily_ops_portfolio_reads.py` (25 ids → 3 trozos, una lectura) |
| Wiring real de la ruta | `test_instrument_daily_opinions_query_reads.py` (3 tests) |
| El memo sobrevive a refresco de cotizaciones | `use-asesor-cartera-data.hook.test.tsx` (contador de `computeMarketStructure`) |

Salida real: `27 passed` (hints + estudio), `1 passed` (parte diario), `3 passed` (ruta API),
`9 passed` (hook + suite previa), `typecheck` exit 0.

### 8.3 · Decisión de `window:freeze`

Creado [`decision-window-freeze-dispatch-2026-11-12.md`](../../decision-window-freeze-dispatch-2026-11-12.md)
con la tabla medida y el catálogo de opciones. Corregida el §5.2 del
[acta F4-067](../../acta-f4-067-opinion-account-scope-2026-11-12.md): el pin coincide con el árbol
del tag `v2.88.188-beta` (`53285f18`), no con la punta de `main` (`ae6410bf`), que ya movió `apps/`.
No se tocó el pin, ni el gate, ni los workflows. `window:freeze` sigue en `TREE_MOVED` (exit 1),
como debe.

### 8.4 · E2E integrados ejecutados (local)

| Suite | Variables | Resultado |
| --- | --- | --- |
| `gp-e2e-ui5-0-axe-integrated` | `E2E_INTEGRATION=1`, `E2E_ALLOW_DEV_DB=1`, `E2E_AXE_REQUIRED=1` | **32 passed / 0 failed / 0 skipped** |
| `gp-v288-s5` | + `E2E_S5_REQUIRED=1`, `E2E_REPO_ROOT` | **8 passed / 0 failed / 0 skipped** (AAPL con 123 barras tras sync) |
| `gp-e2e-auto-daily-chain-live` | + `E2E_LIVE_REQUIRED=1`, worker vivo | **2 passed / 0 failed / 0 skipped** (regimen `neutral`, `no_plan=0`) |

El live se ejecutó con la cola durable drenando de verdad: `estudio_daily` `queued → running →
completed` y `dia_d_value_replay` `completed`; el teardown dejó 0 residuos. Con las variables
`*_REQUIRED=1` activas, cualquier precondición ausente habría sido fallo duro, no skip.

### 8.5 · Gates locales repetidos

| Gate | Resultado |
| --- | --- |
| Shared build / typecheck | exit 0 |
| Shared suite | 107 archivos · 1.034 pruebas (+1 `todo`) |
| `contract:check` | OK — artefactos idénticos al commit |
| Web typecheck | exit 0 |
| Web lint | 0 errores · 23 warnings heredados |
| Web suite | **390 archivos · 2.928 pruebas** (+1 archivo, +3 pruebas) |
| Web build | exit 0 |
| E2E mock S5 | 11 passed |
| E2E axe rutas tocadas | 35 passed |

### 8.6 · Incidencias de entorno de esta sesión

- **Chromium**: la sesión heredaba `PLAYWRIGHT_BROWSERS_PATH` apuntando a una caché de sandbox
  vacía. Resuelto apuntando a `%LOCALAPPDATA%\ms-playwright`; no se instaló nada.
- **Vite**: tras reconstruir `packages/shared/dist`, el servidor de `:5173` entró en un bucle de
  recarga por invalidación de import circular en `instrument-strategy-top-panel.tsx`, y
  `page.goto` no estabilizaba `load`. Se ejecutaron los E2E mock contra una instancia limpia en
  `:5174`, cerrada al terminar. **No se mató el servidor del usuario**: `:5173` siguió vivo
  (PID 9284). Los 11/11 y 35/35 se obtuvieron así; el fallo previo era de entorno, no de producto.

### 8.7 · Reservas que siguen vivas

- **CI no ejecutado**: sin push/PR no hay CI verde. Además, `window:freeze` seguiría rojo en
  cualquier rama que toque `apps/` o `packages/`, y hoy también en `main` por `ae6410bf`.
- No es certificación dinámica integral: se ejecutaron los tres E2E integrados, pero no el job
  `certify` ni los E2E `opt-in` de evidencia.
- No es aprobación de release.
- No hay `add`/`commit`/`push`: todo lo anterior vive en el árbol de trabajo y queda sin publicar.
- S0/F4-067 no se modifica: el frente se cerró **documentalmente**; su resolución técnica sigue
  exigiendo autorización propia.
