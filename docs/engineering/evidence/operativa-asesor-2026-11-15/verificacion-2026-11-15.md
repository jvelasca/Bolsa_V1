# Evidencia · operativa clara de Asesor · 2026-11-15

Ejecutado en Windows 10.0.26200, árbol de trabajo sin commit, sobre el frente A1–A5.

## 1 · Suites

```text
pnpm --filter @bolsa/shared typecheck
  (sin salida de error)

pnpm --filter @bolsa/shared test
  Test Files  108 passed (108)
       Tests  1041 passed | 1 todo (1042)

pnpm --filter @bolsa/web typecheck
  (sin salida de error)

pnpm --filter @bolsa/web test
  Test Files  395 passed (395)
       Tests  2957 passed (2957)

pnpm --filter @bolsa/web lint
  ✖ 23 problems (0 errors, 23 warnings)
```

Los 23 warnings son `react-hooks/exhaustive-deps` preexistentes en `backtests/`,
`charts/`, `decision-journal/`, `mesa/` y `operations/`; ninguno en `features/research/`.

## 2 · Build y contrato

```text
pnpm --filter @bolsa/web build
  vite v6.4.3 building for production...
  ✓ 2722 modules transformed.
  ✓ built in 4.79s

pnpm --filter @bolsa/web contract:check
  contract:check OK — openapi.json y schema.d.ts coinciden con el commit.
```

## 3 · Motor Python (sin cambios, sigue verde)

```text
uv run python -m pytest packages/py/application/tests/test_daily_opinion_service_hints.py -q
  ..............                                                           [100%]
  14 passed in 0.49s
```

## 4 · E2E · 11 de 11 en verde

La causa de las once fallas anteriores era de entorno: `PLAYWRIGHT_BROWSERS_PATH`
apuntaba a `%TEMP%\cursor-sandbox-cache\…\playwright`, una caché vacía, así que
`browserType.launch` abortaba antes de navegar. Los binarios ya estaban en
`%LOCALAPPDATA%\ms-playwright`; no se instaló nada.

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "$env:LOCALAPPDATA\ms-playwright"
$env:E2E_RUN="1"; pnpm --filter @bolsa/web exec playwright test gp-s5-rediseno
```

```text
Running 11 tests using 8 workers

  ok  S5.favorable_sin_posicion · Recomendación favorable sin posición
  ok  S5.sin_datos · Sin datos suficientes
  ok  S5.posicion_sin_respaldo · Posición sin respaldo
  ok  S5.salida_con_entradas_bloqueadas · Salida permitida con entradas bloqueadas
  ok  S5.posicion_con_respaldo · Posición abierta con respaldo
  ok  S5.entrada_bloqueada · Entrada bloqueada
  ok  S5.responsive · 3 → 2 → 1 columnas y superficie estrecha
  ok  S5.superficie dock · conserva la composición anterior
  ok  S5.S2 · estructura calculada declara que informa, no autoriza
  ok  S5.S3 · Asesor/Cartera clasifica la misma cartera
  ok  S5.S3 · Asesor/Cartera sin posición no inventa respaldo

  11 passed (16.9s)
```

Ninguna aserción ni ningún `data-testid` se tocó para llegar a verde.

## 5 · Revisión visual y contraste (claro y oscuro)

Capturas propias del expediente, tomadas con el escenario `posicion_con_respaldo` de
S5 y `data-theme` forzado:

| Archivo | Qué enseña |
| --- | --- |
| `asesor-cartera-dark.png` / `asesor-cartera-light.png` | Cartera con posición: un solo dictamen dentro de la fila y la columna de estado con su badge |
| `asesor-diario-dark.png` / `asesor-diario-light.png` | Hero del Diario con tokens: cuenta, fecha, Estudio y los cuatro KPI |

El Diario se capturó con un parte **de fixture** (el mock de S5 no incluye
`daily-ops-report`), con datos sintéticos y `estudioStatus: "ok"`; no es evidencia de
cifras, solo de composición y contraste.

Contraste medido con axe (WCAG 2A/2AA) sobre la pestaña Diario en los dos temas:

```text
[axe dark]   0 violaciones graves
[axe light]  1 violación seria: color-contrast
```

Los nodos que fallan en claro, todos del **armazón global** y ninguno del hero:

| Nodo | Contraste | Mínimo |
| --- | --- | --- |
| `<span>Asesor</span>` del menú superior (`text-primary` `#0d9488` sobre `#e2e8f0`) | 3,03:1 | 4,5:1 |
| Subtítulo de página `text-muted-foreground` (`#64748b` sobre `#f4f6f9`) | 4,39:1 | 4,5:1 |
| Enlaces «Mercado» y «Hoy» del subtítulo (`text-primary` sobre `#f4f6f9`) | 3,45:1 | 4,5:1 |
| Pestañas «Cartera» y «Análisis» (`text-muted-foreground` sobre `#f4f6f9`) | 4,39:1 | 4,5:1 |

La línea de contexto del hero del Diario va sobre `--bolsa-card` (`#fff`) y da
**4,76:1**: pasa. El fallo restante es del token `--bolsa-muted-foreground` /
`--bolsa-primary` en toda la aplicación, no de la migración de tokens de A4, y quedó
registrado como **H-21**; **corregido el 2026-11-16** (§10).

## 6 · Inventario de componentes (líneas medidas en el cierre)

```text
  127  asesor-hub-tabs.tsx
  186  asesor-ui.tsx
   70  asesor-dictamen-cell.tsx
  252  asesor-cartera-panel.tsx              (antes 841)
  280  asesor-cartera-row.tsx
   78  asesor-cartera-filters.tsx
  262  asesor-cartera-technical-detail.tsx
   33  asesor-strength-bar.tsx
  485  asesor-opiniones-panel.tsx            (antes 574)
   64  opinion-channel-map.tsx
  189  asesor-telemetry-strip.tsx
  330  asesor-daily-ops-panel.tsx            (antes 576)
  139  asesor-daily-hero.tsx
   96  asesor-week-chart.tsx
  143  asesor-daily-channels.tsx
  292  lab-summary-panel.tsx
   69  lab-health-card.tsx
  297  lab-trial-history-panel.tsx
  101  lab-trial-detail-panel.tsx
   40  asesor-journal-bridge.tsx
```

## 7 · Guardas de primer nivel

```text
pnpm --filter @bolsa/web test -- research
  ✓ src/features/research/research-first-level.test.tsx (13 tests)
  ✓ src/features/research/asesor-daily-hero.test.tsx (5 tests)
  ✓ src/features/research/research-trial-result-block.test.tsx (2 tests)
  ✓ src/features/research/asesor-dictamen-cell.test.tsx (4 tests)
  Tests  72 passed (72)
```

Sin `?? 0` de dato ausente en `apps/web/src/features/research`:

```text
(rg "\?\? 0" apps/web/src/features/research → sin coincidencias)
```

## 8 · Cierre de H-5 · sexta categoría de cartera

`classifyAsesorCarteraState` ya distingue **seis** categorías. La nueva,
`senal_de_salida_sin_posicion` («Señal de salida sin posición»), recoge `overbought`,
`reduce` y `sell_exit` cuando no hay posición abierta. Antes, `overbought` caía en el
`default` y se leía «Dictamen no reconocido»; `reduce`/`sell_exit` se declaraban
«sin datos» con una grieta. Las dos cosas negaban un dato medido.

```text
pnpm --filter @bolsa/shared test -- asesor-cartera
  ✓ 46 passed

pnpm --filter @bolsa/web test -- asesor-cartera operativa-action-hint operativa-recomendacion
  ✓ 121 passed (15 archivos)
```

Pruebas que lo fijan: las tres posturas sin posición devuelven la categoría nueva sin
huecos; ninguna postura conocida devuelve «Dictamen no reconocido» (7 posturas × 2
estados de posición); la etiqueta y el `meaning` niegan explícitamente la sobrecompra y
la orden de venta; el panel pinta seis filas en el orden de `rank`; la pista de
actuación declara «Sin actuación» con texto propio para esta categoría.

## 9 · Estado del árbol

Sin `git add`, sin commit, sin tag y sin bump de versión. Los módulos nuevos quedan
como untracked en el árbol de trabajo, listos para revisión.

## 10 · Cierre de H-20 a H-23 (2026-11-16)

### 10.1 · Contraste después del cambio de tokens

Se retocaron dos tokens del bloque `[data-theme="light"]` de `apps/web/src/index.css` y se
repitió el barrido sobre cuatro superficies en los dos temas. Criterio: **0 violaciones
`critical`/`serious`**.

| Token | Antes | Después | Sobre `--background` `#f4f6f9` | Sobre `--muted` `#e8eef5` | Sobre `--accent` `#e2e8f0` |
| --- | --- | --- | --- | --- | --- |
| `--bolsa-muted-foreground` | `#64748b` | `#566578` | 4,39 → **5,50** | **5,10** | **4,83** |
| `--bolsa-primary` | `#0d9488` | `#0e7268` | 3,45 → **5,35** | **4,96** | **4,70** |
| `--bolsa-primary-foreground` | `#f0fdfa` | sin cambio | — | — | **5,55** sobre el nuevo primary |

Por qué `#0e7268` y no teal-700 `#0f766e`: el nodo real que fallaba era «Asesor» del menú
superior, que se sienta sobre `--bolsa-accent` `#e2e8f0`. Ahí teal-700 da **4,44:1** y
seguiría incumpliendo por una centésima; `#0e7268` da 4,70:1. El tema oscuro no cambió.

Medición reproducible: `gp-e2e-ui5-0-aa-theme-captures-mock.spec.ts` (salida en
`aa-axe-sweep.txt`).

```text
[light][asesor-cartera] graves=0 · ninguna
[dark][asesor-cartera] graves=0 · ninguna
[light][asesor-diario] graves=0 · ninguna
[dark][asesor-diario] graves=0 · ninguna
[light][mesa] graves=0 · ninguna
[dark][mesa] graves=0 · ninguna
[light][backtests] graves=0 · ninguna
[dark][backtests] graves=0 · ninguna
```

**Procedencia de las capturas.** El primer barrido no forzaba el tema: `data-theme` se
resuelve desde `bolsa-ui-prefs-v1` (`ui-store`), cuyo valor por defecto es **oscuro**, de
modo que el barrido «claro» corría con el tema por defecto. En disco, las capturas
`aa-asesor-cartera-light.png`, `aa-mesa-light.png` y `aa-backtests-light.png` eran byte a
byte iguales a sus pares oscuros (mismo MD5): el lado sin respaldo era el **claro**, no el
oscuro. El 2026-11-16 se repitieron las cuatro superficies con el tema forzado antes de
navegar (`addInitScript` sobre `bolsa-ui-prefs-v1`), aserción de `<html data-theme>` antes
de medir y guarda que falla si la pareja claro/oscuro sale idéntica. Comprobación de fondo
sobre los PNG: `#f4f6f9` (244,246,249) en claro y `#0b0f14` (11,15,20) en oscuro, ambos a
1600×1000.

Capturas: `aa-asesor-cartera-{light,dark}.png`, `aa-asesor-diario-{light,dark}.png`,
`aa-mesa-{light,dark}.png`, `aa-backtests-{light,dark}.png`, `aa-axe-sweep.txt`.

### 10.2 · Tabla de nodos corregidos

| Nodo | Antes | Ahora |
| --- | --- | --- |
| `<span>Asesor</span>` del menú superior | 3,03:1 (`#0d9488` sobre `#e2e8f0`) | 4,70:1 |
| Subtítulo de página | 4,39:1 | 5,50:1 |
| Enlaces «Mercado» / «Hoy» del subtítulo | 3,45:1 | 5,35:1 |
| Pestañas «Cartera» / «Análisis» | 4,39:1 | 5,50:1 |
| Botón primary (texto `#f0fdfa`) | 3,45:1 sobre `#0d9488` | 5,55:1 sobre `#0e7268` |

### 10.3 · Diario tolerante a un parte parcial (H-22)

El panel y el gráfico ya no leen `.length` ni `.map` a ciegas:

| Caso | Antes | Ahora |
| --- | --- | --- |
| Parte completo | pinta la lista | igual (sin regresión) |
| Parte sin `tradesToday` | error boundary | «Sin dato todavía · el parte del día no trajo los movimientos» |
| `tradesToday: []` | «Sin compras/ventas registradas hoy» | igual: el cero se midió |
| Parte sin `week` | SVG con una barra inventada | «Sin dato todavía · el parte del día no trajo la semana» |
| `week: []` | SVG vacío | «Sin movimientos registrados esta semana» |
| Parte sin `summary` | excepción en el hero | cuatro KPI con «Sin dato todavía» |
| Parte sin `channels`/`opinions` | excepción en el panel de canales | canales y dictámenes declaran la ausencia |

La única rama que puede afirmar cero es la que pasó por `Array.isArray`. El gate de primer
nivel se amplió para prohibir `?? []` en los tres módulos del Diario: normalizar a
colección vacía es la misma mentira que `?? 0`.

### 10.4 · Jerarquía de encabezados (H-23)

`heading-order` en `/research`: `<h3>Cartera del Asesor</h3>` colgaba del `h1`. Preexistente
—idéntico en `HEAD`— y detectado al repetir el barrido de este cierre. Se corrigió con
`CardTitle level="h2"` en Cartera y Análisis, como documenta el propio componente. El
barrido `gp-e2e-ui5-0-axe-touched-routes-mock` pasa a **35/35**.

### 10.5 · Suites de este cierre

```text
pnpm --filter @bolsa/shared build      → OK
pnpm --filter @bolsa/web typecheck     → OK
pnpm --filter @bolsa/web test          → 397 archivos, 2968 pruebas, 0 fallos
pnpm --filter @bolsa/web lint          → 0 errores (23 avisos preexistentes)
pnpm --filter @bolsa/web contract:check→ OK (openapi.json y schema.d.ts sin cambios)
playwright gp-s5-rediseno              → 11/11
playwright gp-e2e-ui5-0-axe-…          → 35/35
playwright gp-e2e-ui5-0-aa-theme-…     → 8/8 (capturas y AA por tema, 2026-11-16)
```

Pruebas nuevas: `asesor-daily-ops-panel.test.tsx` (5 casos: completo, parcial, `null`
explícito, cero medido, semana vacía) y `asesor-week-chart.test.tsx` (5 casos, incluida la
guarda de fuente que prohíbe `?? []` en el gráfico).

## 11 · Dictamen del revisor (2026-11-16)

Revisión técnica de H-20 a H-23 sobre la evidencia de §10. **PASS técnico** de los cuatro
puntos, con el alcance y las salvedades que se declaran al final de esta sección.

| id | Dictamen | Fundamento |
| --- | --- | --- |
| H-22 | PASS | La frontera de lectura conserva la diferencia entre dato presente, lista vacía y dato ausente: solo la rama que pasó por `Array.isArray` afirma cero, y el hueco se declara. No convierte ausencia en cero ni en colección vacía, que es la condición para que el Diario no presente información no medida como resultado. |
| H-20 | PASS | `AsesorDailyOpsPanel` acepta `className` y lo compone con `cn("space-y-4", className)`, coherente con sus paneles hermanos, sin alterar el contrato de datos ni el tamaño por sí solo. |
| H-21 | PASS | El contraste se ajusta sobre el fondo real del menú (`--bolsa-accent` `#e2e8f0`), no sobre un fondo supuesto: la medición justifica `#0e7268` (4,70:1) frente a teal-700 (4,44:1). El bloque `[data-theme="dark"]` queda intacto. |
| H-23 | PASS | `heading-order` corregido con `CardTitle level="h2"` en Cartera y Análisis; defecto previo, detectado al repetir el barrido. Barrido L1 completo en 35/35. |

Verificación que sostiene el dictamen: **2968/2968** pruebas de `@bolsa/web`, **11/11** en
`gp-s5-rediseno` y **35/35** en `gp-e2e-ui5-0-axe-touched-routes-mock`; y las ocho
combinaciones superficie × tema del barrido AA en **0 graves** (§10.1). La evidencia previa
de S5 se preserva: al repetir las capturas AA no se sobrescribieron
`asesor-cartera-{light,dark}.png` ni `asesor-diario-{light,dark}.png`.

Límites de alcance: Δ motor = 0, Δ decisión = 0, sin migraciones, sin regeneración de
contratos, sin cambios en `openapi.json`, sin commit ni tag.

Este dictamen es un cierre técnico de H-20 a H-23: **no** constituye una auditoría
independiente de los cambios ni una certificación de release. H-15, ★/confianza y OHLCV
batch siguen expresamente fuera de alcance y no se abren tareas adicionales.

