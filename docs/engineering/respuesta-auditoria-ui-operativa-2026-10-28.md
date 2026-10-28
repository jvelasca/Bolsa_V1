# Respuesta a la auditoría de UI operativa (2026-10-28) — cierre de los seis P1 y del comodín P2-04

> **Naturaleza:** documento **POST-TAG** de **respuesta**. El [acta](./auditoria-ui-operativa-profunda-2026-10-28.md)
> **no se reescribe**: se conserva tal como se publicó en `e421186e`, con su dictamen, sus
> referencias y sus límites. Aquí se registra, hallazgo por hallazgo, **qué cambió, con qué prueba
> y qué queda fuera**.
>
> El tag `v2.88.169-beta` (`d31df9b3` → `3ce94048`) **no se mueve** y **no se reabre**; este slice
> viaja **después** de él, sin tag nuevo. La ventana PAPER sigue **`INCONCLUSIVE`** (`0/2`, `0/32`):
> corregir la representación **no demuestra rentabilidad**.

## 0. Alcance medido

| Métrica | Valor |
| --- | --- |
| Commits del slice | **7** (`31974c6c`…`e7131edf`), uno por hallazgo, más el acta `e421186e` |
| Ficheros | **51** (+2 381 / −254) desde `e421186e` |
| `Δ contrato HTTP` | **ADITIVO**: `tradeFeesTotal` en `LedgerResponseDto` (P1-03) |
| `Δ motor` / `Δ decisión` | **0** — ninguna regla, umbral, peso, sizing ni salida cambia |
| Migración | **ninguna** (`head` sigue `058_estudio_daily_proposals`) |
| Bump | `2.11.169-beta` → `2.11.170-beta` (+ **13** `meta.bump`; guardián **2 passed**) |
| TAG | **sin tag nuevo**; `v2.88.169-beta` intacto |

## 1. P1-01 · un error de lectura no es una colección vacía

**Causa.** Seis superficies colapsaban tres estados en uno con `query.data ?? []`: *medido y
vacío* («no hay nada»), *no se pudo leer* (error de red/5xx) y *no consta* (query deshabilitada).
Las dos últimas no autorizan una frase de vacío.

**Cambio.**

- Helper puro y compartido `apps/web/src/components/query-absence.ts`: `queryCollectionState({
  isError, isLoading, count })` con precedencia **`error` > `loading` > `unavailable` > `empty` >
  `ready`** (un refetch fallido con datos previos sigue siendo `error`), más
  `collectionAbsenceLabel`, `collectionAbsenceCopy` e `isCollectionAbsent`.
- Componente `apps/web/src/components/collection-absence.tsx` (`<CollectionAbsence />`) que declara
  el hueco sin pintar el texto de colección vacía.
- Superficies: `history/history-page.tsx` (movimientos y operaciones), `trading/operativa-outcomes.tsx`
  (sesiones), `trading/use-pending-orders.ts` → `useInstrumentOrderPending` pasa a **tri-estado**
  (`null` = no se pudo leer) y se propaga como `reconLookupFailed` a `mesa/mesa-position-row.tsx` y
  `trading/operations-panel.tsx`, donde `execution-state.ts` lo convierte en `unknown` (nunca «sin
  orden pendiente»), `trading/dia-d-trades-panel.tsx` (`detail` ausente ⇒ hueco declarado, no `0`),
  `auto-monitor/dia-d-auto-panel.tsx` (`divergent`, `unmeasuredCount`, `limits.length` con
  `formatDiaDValue`) y `operational-console/ops-incidents-and-links.tsx` (`!isError` en el vacío).

**Prueba.** `query-absence.test.ts` (tabla de precedencia) y una prueba de render por superficie con
`mockRejectedValue`: `history-page-absence.test.tsx`, `operativa-outcomes-absence.test.tsx`,
`use-pending-orders.test.tsx`, `dia-d-trades-panel-absence.test.tsx`,
`dia-d-auto-panel-absence.test.tsx`, `ops-incidents-absence.test.tsx`. En todas: aparece
`No disponible` y **no** el texto de vacío.

**Límite.** El gate de censos `barrido-global-first-level.test.tsx` sigue **sin** ampliar su lista
`FALSE_ZERO_SURFACES` a Mesa/Mercado/AUTO: quedan `?? 0` de **nivel 2** (buckets del board,
contadores de incidencias) que alimentan cálculos, no cifras de primer nivel, y marcarlos como rojo
exigiría antes retirarlos. Se declara como deuda abierta, no como resuelto.

## 2. P1-02 · `skipped`/`unknown` no son «ejecutada»

**Causa.** `POST /api/pending-orders/:id/fill` devuelve seis desenlaces y **solo uno** mueve dinero
(`executed`, con `transactionId`). El monitor anunciaba «ejecutada @ precio» para todos, borraba la
orden y reintentaba cada 15 s.

**Cambio.** Resolutor puro `apps/web/src/features/trading/pending-order-fill.ts`:
`resolvePendingFill` → `{ kind, executed, removesOrder, retryable, copy, reason, transactionId }`.
Regla cerrada: **sin `transactionId` no hay ejecución**; `executed` sin transacción degrada a
`unknown`; un estado fuera del vocabulario también. Solo `executed` y `expired` retiran la orden;
`rejected_by_gate`, `skipped` y `unknown` **no** la borran, **no** re-lintan el enlace de mandato y
**no** se reintentan en la sesión (ref `unresolved`), invalidando `pending-orders` para espejar la
verdad del servidor. El precio se mantiene como **precio límite** (el servidor ejecuta a ese precio:
no se inventa un precio aplicado distinto).

**Prueba.** `pending-order-fill.test.ts`: tabla de los seis desenlaces que afirma que **ningún**
estado distinto de `executed` produce el texto «ejecutada» y que solo `executed`/`expired` retiran
la orden.

**Límite.** Un `unknown` no se resuelve por reintento: queda declarado y la orden sigue viva en el
servidor. La UI no puede saber si el bróker ejecutó sin confirmación; lo dice.

## 3. P1-03 · comisiones acumuladas reales (Δ aditivo de contrato)

**Causa.** «Comisiones acumuladas» sumaba las filas `fee` de la **página** (100 movimientos) y se
presentaba como el total del histórico: con más histórico, la cifra estaba subestimada.

**Cambio.**

- Servidor: `total_trade_fees` en `ListLedgerEntries`
  (`packages/py/application/src/bolsa_application/accounts/ledger.py`) delega en
  `total_fees_for_account` del repositorio (excluye custodia, por diseño); la ruta
  `apps/api-python/src/bolsa_api/api/v1/routes/accounts.py` lo publica y el esquema
  `apps/api-python/src/bolsa_api/schemas/accounts.py` lo expone como campo **aditivo**
  `tradeFeesTotal` de `LedgerResponseDto`.
- Contrato regenerado y verificado: `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`,
  `pnpm contract:check` **OK**.
- Cliente: `getAccountLedger` devuelve `{ data, tradeFeesTotal }`.
- UI: la tarjeta de Historial usa el agregado del servidor y se rotula **«Comisiones de operaciones
  (histórico)»**; `0,00 €` cuando el total medido es cero, `Sin dato todavía` / `No disponible`
  cuando no consta o la lectura falló.

**Prueba.** `packages/py/application/tests/test_list_ledger_total_fees.py` (150 filas `fee` con
página de 100 ⇒ total completo) y `apps/api-python/tests/integration/test_accounts.py` (campo en la
respuesta); en web, `history-page-fees.test.tsx` fija que la cifra **no** depende del tamaño de
página (1 fila visible, total 1 234,50) y que un total medido de cero se pinta como `0.00`, no como
hueco.

**Límite.** El agregado **excluye custodia** (es lo que mide `total_fees_for_account`); la tarjeta
lo dice en su título y en su `title`. La custodia se contabiliza aparte.

## 4. P1-04 · el color del asiento declara su papel, no su signo

**Causa.** El color salía de `entry.amount >= 0`: una **comisión** (negativa) se pintaba como una
compra y una compra (salida de caja) se leía como pérdida.

**Cambio.** `ledgerAmountTone(entry)` en `packages/shared/src/portfolio-cash.ts`:
`cost` (comisión, custodia, retirada), `in` (venta, dividendo, ingreso/depósito) y `neutral`
(compra, transferencia, ajuste). El importe **conserva su signo** —el tono es color, no aritmética—
y la fila expone `data-tone`. Aplicado en `history/history-page.tsx`,
`accounts/account-detail-panel.tsx` y `dashboard/dashboard-page.tsx`.

**Prueba.** `packages/shared/src/portfolio-cash.test.ts` (mapeo completo) y
`history-page-tone.test.tsx`: fila `fee` con `data-tone="cost"` y **sin** verde, compra `neutral`,
venta `in`.

**Límite.** El tono no reordena ni agrupa: sigue siendo una tabla cronológica.

## 5. P1-05 · el universo «0» solo si se midió

**Causa.** Sin ranking (query caída o scan sin completar) la Mesa pintaba `Universo 0`, `Operables 0`
y el CTA acusatorio «Tu universo de análisis es pequeño», que atribuye al usuario un diagnóstico que
el sistema no midió.

**Cambio.** `mesa/mesa-hoy-page.tsx` deriva `rankingUnavailable` / `rankingLoading` de
`scanJobsQuery` / `universeListQuery` / `studiesQuery` y los pasa a `MesaCandidatesPanel`. El panel
resuelve `rankingState` con el mismo helper de P1-01, muestra `Sin dato todavía` / `No disponible`
en «Universo», «Operables» y `maxQuality`, y **suprime** `smallUniverse` y `lowQualityDay` mientras
no haya medición; el bloque vacío deja de afirmar «no hay oportunidades».

**Prueba.** `mesa-candidates-panel-absence.test.tsx`: con ranking ausente/error **no** aparece el CTA
acusatorio y sí el rótulo del hueco.

**Límite.** Los `?? 0` que alimentan el *builder* del ranking (`screenedCount`, `hitCount`,
`universeCount`) siguen existiendo como entrada de cálculo; lo que se corrige es **lo que se
afirma en primer nivel**. Un scan completo con `0` hits sigue diciendo `0`, porque ahí sí se midió.

## 6. P1-06 · cartera caída ≠ «sin posiciones ni stops»

**Causa.** `positions = portfolio?.positions ?? []` con `open === 0` producía «Sin posiciones
abiertas — no hay stop que confirmar»: una afirmación de **seguridad** sobre un dato que no se leyó.

**Cambio.** `mesa/mesa-hoy-page.tsx` deriva `portfolioUnavailable`/`portfolioLoading`;
`mesa-proteccion-kpi.tsx` recibe `absenceState` y, en `error`/`loading`/`unavailable`, pinta
`No disponible — no se pudo leer la cartera; no hay recuento de stops` (o «Cargando la cartera…»),
nunca la frase de seguridad ni `0 / 0`. `mesa-positions-summary.tsx` declara `No disponible` en vez
de «Sin posiciones». `mesa-libro-panel.tsx` y `trading/operations-panel.tsx` usan
`formatPriceOrAbsent` en sus figuras.

**Prueba.** `mesa-portfolio-absence.test.tsx`: `getPortfolio` rechazado ⇒ aparece el hueco y **no**
la frase de seguridad; con cartera leída y cero posiciones **sí** se declara el cero medido; el KPI
compacto no pinta `0`.

**Límite.** `error` y `empty` siguen siendo estados distintos y **no** se intercambian: lo que se
prohíbe es presentar el fallo como si fuera una medición.

## 7. P2-04 · el comodín se prueba sobre el texto renderizado

**Causa.** El gate `findFirstLevelDashes` lee el **código fuente**; un `—` construido por
composición o un `formatPrice(null)` no lo disparan. La prueba debía mirar el DOM.

**Cambio.**

- `history/history-page.tsx`: columna **Saldo** con `formatPriceOrAbsent`.
- `operations/operations-page.tsx`: **Patrimonio** y **P&L no realizado** con
  `formatPriceOrAbsent`, y el recuento de posiciones viaja como `undefined` (hueco) en vez de `?? 0`;
  `operations/mesa-operational-bar.tsx` declara `Sin dato todavía` cuando no hay lectura, en lugar de
  `Posiciones 0`.
- `packages/shared/src/cognitive/data-freshness.ts`: `label` de `unknown`/`invalid` deja de ser el
  comodín `—` y pasa a **`Sin dato todavía`**, con constante exportada
  `DATA_FRESHNESS_ABSENT_LABEL`; `applyPartialSampleLabel` compara contra esa constante.
- `barrido-global-first-level.test.tsx`: `features/operations/operations-page.tsx` entra en
  `DASH_SURFACES` (el gate de fuente se conserva como complemento rápido, no como falsificador
  principal).

**Prueba.** `history-page-dash-absence.test.tsx`: con `balanceAfter` ausente, la celda **Saldo** es
exactamente `Sin dato todavía` y no hay nodo `—`; con saldo medido se conserva la cifra.
`mesa-portfolio-absence.test.tsx` (bloque P2-04): patrimonio y P&L sin medir se declaran como texto.
`mesa-operational-bar.test.tsx`: cartera caída ⇒ `Posiciones Sin dato todavía`, nunca `Posiciones 0`.
`data-freshness.test.ts`: `unknown` e `invalid` afirman el rótulo oficial y **no** el comodín.

**Límite.** `—` sigue permitido como **puntuación** en prosa y como valor de **nivel 3**
(`TechnicalDetail`); las aserciones buscan el nodo de texto suelto (`queryByText("—")`), no la raya
dentro de una frase.

## 8. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| `pnpm --filter @bolsa/web test` | **2525 passed / 335 ficheros** |
| `pnpm --filter @bolsa/shared test` | **861 passed / 100 ficheros** (+1 `todo`) |
| `pnpm typecheck` | **4/4 OK** (`tsc -b --noEmit`, sin salida) |
| `pnpm lint` | **0 errores** / 23 avisos preexistentes |
| `pnpm contract:check` | **OK** — `openapi.json` y `schema.d.ts` coinciden |
| `pytest packages/py/application/tests -k "ledger or fees"` | **48 passed**, 2927 deselected |
| `pytest apps/api-python/tests -k "ledger or tax"` | **30 passed**, 1394 deselected |
| `pytest test_dia_d_bump_guard.py` | **2 passed** |
| `pnpm window:test` | **50 passed** |
| `pnpm window:freeze` | **`freeze OK`** tras el re-anclaje del pin |

Las suites completas de Python las ejecuta el CI; este documento **no** adelanta cifras que no se
hayan medido.

## 9. Lo que este cierre NO hace

- **No** emite tag nuevo ni mueve `v2.88.169-beta`; la auditoría se responde **encima** del sello.
- **No** reescribe el acta ni sus hallazgos: la trazabilidad exige que el dictamen original quede
  como estaba, con sus P1 abiertos en la fecha en que se redactó.
- **No** cierra los P2 restantes (P2-01 verde con P&L nulo, P2-02, P2-03, P2-05…P2-12) ni los P3:
  siguen declarados y abiertos.
- **No** cambia motor, umbrales, AUTO, PAPER ni migraciones; el único Δ de contrato es el campo
  aditivo `tradeFeesTotal`.
- **No** demuestra rentabilidad: AUTO **OFF**, operativa **100 % PAPER virtual**, ventana
  **`INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`).
