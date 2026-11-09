# Carga diferida de rutas y bundle — Fase 3.1 — 2026-11-08

Cierre de `p3-lazy` (Fase 3 / 3.1 del plan de remediación). Las páginas de ruta salen del
chunk inicial; el shell sigue eager.

## Qué se cambió

- `apps/web/src/app-routes.ts` (nuevo): una sola fuente de verdad con un `import()`
  **literal** por página (25 páginas). De ahí se derivan los `React.lazy` de `ROUTE_PAGES`.
  - `lazyNamed` valida en runtime que el módulo exporte el componente con ese nombre, así
    que un rename se ve como error claro y no como pantalla en blanco.
  - Cada `import()` literal permite que Vite emita un chunk por página. Un specifier
    calculado (variable/mapa de strings) no sería analizable y volvería al bundle único.
- `apps/web/src/app.tsx`: cada `element` de ruta se envuelve en `<Suspense>` con
  `RouteFallback` (`data-testid="route-fallback"`, spinner + «Cargando página…»,
  `aria-live="polite"`).
- Eager, a propósito: `PlatformShell`, `AuthGate`, `AppErrorBoundary`,
  `AutoWorkspaceLayout` (layout de `/auto`) y `BacktestsPage` (keep-alive montado desde
  `PlatformShell`, no una ruta que se navegue).
- Guards actualizados: `operations-route.test.ts` ya no busca un `import` estático; exige
  el loader dinámico y que `/operations` monte `<OperationsPage />` (no un `Navigate`).
- `apps/web/src/app-routes.test.ts` (nuevo): 25 rutas declaran `React.lazy`, cada loader
  importa el módulo y exporta el componente con el nombre esperado, y `ROUTE_PAGES` no
  tiene claves de más/menos que `ROUTE_PAGE_LOADERS`.

## Medición antes/después

Método: `pnpm run build` (Vite 7, sin `manualChunks`) en el mismo árbol, antes y después
del cambio. Cifras del chunk principal (`dist/assets/index-*.js`):

| | Antes | Después | Δ |
| --- | ---: | ---: | ---: |
| JS minificado | 3.552,79 kB | 2.602,41 kB | **−950,38 kB (−26,8 %)** |
| JS gzip | 990,87 kB | 749,39 kB | **−241,48 kB (−24,4 %)** |

Chunks por página (minificado / gzip), muestra de los mayores:

```
chart-workspace-page   126,95 kB / 34,57 kB
screeners-page         100,90 kB / 26,15 kB
decision-journal-page   74,06 kB / 20,42 kB
auto-monitor-page       62,81 kB / 17,09 kB
mesa-hoy-page           58,44 kB / 16,05 kB
instruments-page        56,97 kB / 17,18 kB
accounts-page           44,64 kB / 12,21 kB
research-page           39,19 kB / 11,16 kB
```

Lectura honesta: el JS total del `dist` apenas cambia (≈3,55 MB → ≈3,58 MB; el +0,6 % es
el coste de los wrappers/preload por chunk). La ganancia es **tiempo hasta interactivo**:
el arranque ya no parsea las 25 páginas, solo el shell y la ruta activa. El chunk inicial
sigue por encima de 500 kB porque `PlatformShell` importa eagermente diálogos, monitores y
el keep-alive de backtests; partirlo es un trabajo distinto (p. ej. `manualChunks` por
vendor) y no se mezcla con esta fase.

## Verificación

```bash
cd apps/web
pnpm run typecheck
pnpm exec vitest run src/app-routes.test.ts src/features/operations/operations-route.test.ts
pnpm run build
```

- `typecheck`: OK.
- Tests focales: 5 passed.
- `build`: OK; el aviso de chunk >500 kB persiste y queda declarado arriba, no oculto.

## Nota operativa

`RouteFallback` es intencionadamente mínimo y sin lógica de negocio: aparece durante la
descarga de un chunk en una navegación cliente. Si el chunk falla (red caída tras un
deploy), React lanza el error al `AppErrorBoundary`; el fallback no lo enmascara.
