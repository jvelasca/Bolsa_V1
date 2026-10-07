# Evidencia `v2.88.87-beta` — `AUTO · UI`: **AUTO/UI REFACTOR 4.0 — estado humano, centro de actividad, «¿Por qué?» transversal, ficha universal y TOP 3 OPORTUNIDADES**

**Producto:** `V2.88.87-beta` · **Package:** `2.11.87-beta` · **AsOf:** 2026-10-07. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`** y **contrato HTTP sin cambio**: todo el slice es UI/read-model en `apps/web/**`; consume el contrato del TOP3 ya regenerado en `v2.88.85-beta` (`getLatestTop3Opportunities`) sin añadir endpoints. **Tag anotado `v2.88.87-beta`**.

**Padre de producto:** [`v2.88.86`](../v2.88.86/README.md). Auditoría que motivó el slice:
[`auditoria-ui-auto-pantalla-2026-10-06.md`](../../auditoria-ui-auto-pantalla-2026-10-06.md). Spec de referencia:
[`spec-auto-ui-refactor-3-0-2026-10-06.md`](../../spec-auto-ui-refactor-3-0-2026-10-06.md).

## Qué cambia

Cierra, sin tocar motor, el tramo UI del espacio AUTO con cinco piezas y un barrido semántico:

1. **Estado humano unificado (P1).** [`auto-human-state.ts`](../../../../apps/web/src/features/auto/auto-human-state.ts)
   (`buildAutoHumanState`) colapsa el estado interno del motor y la telemetría a **cinco** estados
   (`FUNCIONANDO`/`ANALIZANDO`/`ESPERANDO`/`ATENCIÓN`/`DETENIDO`) con una frase-resumen en lenguaje
   de usuario; [`auto-human-state-badge.tsx`](../../../../apps/web/src/features/auto/auto-human-state-badge.tsx)
   lo pinta en `/auto` (HOME) y `/auto/sistema`.
2. **Centro de actividad (P1).** [`auto-activity-feed.ts`](../../../../apps/web/src/features/auto/auto-activity-feed.ts)
   (`buildAutoActivityFeed`) fusiona los pasos de ciclo alcanzados (`steps[].at`) y el reloj de decisión
   de la telemetría de mercado en **una única** timeline cronológica inversa;
   [`auto-actividad-page.tsx`](../../../../apps/web/src/features/auto/auto-actividad-page.tsx) la sirve en
   `/auto/actividad`, con cada hecho enlazado a la operación canónica
   (`/auto/operar/operacion/:cycleId`) y una entrada propia en la sub-navegación (`Actividad`).
3. **«¿Por qué?» transversal (P1).** [`auto-why.ts`](../../../../apps/web/src/features/auto/auto-why.ts)
   (`buildAutoStateWhy`) clasifica cada condición en **tres** estados (`ok`/`no`/`unknown`, donde `unknown`
   dice «Sin dato todavía» y no finge un fallo); [`auto-why-button.tsx`](../../../../apps/web/src/features/auto/auto-why-button.tsx)
   es un *disclosure* accesible (`aria-expanded`/`aria-controls`) reutilizable, montado en la HOME.
4. **Ficha universal de operación (P2).** [`auto-operation-sheet.ts`](../../../../apps/web/src/features/auto/auto-operation-sheet.ts)
   compone seis bloques canónicos (`decidió`/`hizo`/`cambió`/`precio`/`dinero`/`estado`) **sin saltarse
   peldaños** ni re-derivar cifras; [`auto-operation-sheet-view.tsx`](../../../../apps/web/src/features/auto/auto-operation-sheet-view.tsx)
   la pinta en `/auto/operar/operacion/:cycleId`.
5. **TOP 3 OPORTUNIDADES (P3).** [`auto-top3-opportunities.ts`](../../../../apps/web/src/features/auto/auto-top3-opportunities.ts)
   + [`use-auto-top3-opportunities.ts`](../../../../apps/web/src/features/auto/use-auto-top3-opportunities.ts)
   + [`auto-top3-panel.tsx`](../../../../apps/web/src/features/auto/auto-top3-panel.tsx) copian el ranking
   del motor (`GET /api/top3-opportunities/latest`) **sin recalcular** el score; cada slot declara
   `Estado: propuesta` y, si viene degradado, «Puntuado sin evidencia completa» (**ranking ≠ decisión**).
   Montado en HOME y Operar.
6. **Barrido semántico P0.** [`operations-panel.tsx`](../../../../apps/web/src/features/trading/operations-panel.tsx)
   gana `surface="auto"`: en `/auto/cartera` el vocabulario pasa a «Posiciones» / «Sin posiciones en la
   cuenta simulada», y «… abiertas» queda solo para Mercado/Hoy.

## Invariantes de honestidad (no negociables)

- **`UNKNOWN ≠ 0`.** Un hueco (cargando/error/sin cabecera/medición `UNKNOWN` o `PARTIAL`) se declara
  «Sin dato todavía»; nunca se colapsa a un estado verde.
- **No re-derivar.** El estado humano agrupa hechos ya producidos por `auto-home-summary`; el TOP3 copia
  el DTO del motor; la ficha de operación no recalcula cifras.
- **Ranking ≠ decisión.** El TOP 3 describe oportunidades rankeadas y por defecto las declara `Estado:
  propuesta`; no afirma una compra ni una decisión de cartera.
- **HOME/nav (P3) sin cambio.** La reducción de navegación global (ADR-040) no se aplica: las cinco
  puertas L1 y el aterrizaje `/mesa` siguen vigentes.

## Verificación

- **Frontend (vitest):** suites nuevas `auto-human-state.test.ts`, `auto-activity-feed.test.ts`,
  `auto-why.test.ts`, `auto-operation-sheet.test.ts`, `auto-top3-opportunities.test.ts`,
  `auto-actividad-page.test.tsx` y `operations-panel-labels.test.ts`, más el ajuste de
  `auto-nav.test.ts`, `auto-pages.test.tsx`, `auto-cartera-page.test.tsx` y
  `auto-workspace-layout.test.tsx`. Cada afirmación nueva lleva test de falsabilidad.
- **Local:** `typecheck`, `lint`, `prettier --check` y la suite web completa verdes; navegación real
  verificada en navegador (Playwright MCP) sobre `/auto/*`. El guardián `test_dia_d_bump_guard` verde
  (los 9 CLIs `v2_89`…`v2_97` sellan `2.11.87-beta` junto al `package.json`).
- **Contrato:** sin regeneración (`contract:check` no cambia).

## Qué no cambia

Motor AUTO de decisión/ejecución (`Δ motor = 0`), ledger, posiciones, settlement, el contrato HTTP y el
esquema (head `052_top3_opportunities`).

## Cita POST-TAG

**Tag anotado `v2.88.87-beta`.** `Release tag CI` **pendiente de medición** tras el push del tag.
