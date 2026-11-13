# Concordancia backend ↔ UI de Asesor · 2026-11-12

> Alcance: todo **Asesor** (`/research`), con profundidad en **Cartera** y correcciones
> puntuales en **Análisis** y **Diario**. Objetivo: usar en la UI los valores que el backend
> ya emite y dejar de pagar mediciones que la caché puede responder.
>
> Invariantes: `Δ motor = 0` · `Δ decisión = 0` · sin endpoint nuevo · sin migración · sin
> `contract:gen` · `openapi.json` / `schema.d.ts` intactos.

## 1 · Por qué este documento

El backend y la UI no estaban desalineados en el contrato: lo estaban en el **consumo**. El
servidor ya publicaba frescura del cierre, scores FA/TA, veredicto del motor, consenso,
invalidantes y distancias de nivel; la Cartera los ignoraba. A la vez, el servidor medía
chips antes de mirar la caché (hallazgo **H-2**) y el navegador recalculaba pivotes y ATR en
cada refresco de cotización.

Este documento fija el mapa **campo backend → celda UI** y la matriz **midiendo / ausente /
medido** para que un hueco nunca se lea como un cero.

## 2 · H-2: orden cache-first en `DailyOpinionService.query()`

Antes:

1. resolver ids;
2. `_resolve_hints()` → composite + fundamentales + posiciones;
3. leer caché;
4. servir o recalcular.

Cada consulta de 80 ids pagaba chips aunque las 80 filas estuvieran cacheadas.

Ahora:

1. resolver ids;
2. leer la caché del día/cuenta/fuente;
3. medir **solo posiciones** (`measure_open_positions`, una lectura);
4. servir la fila cacheada si `position_open` medido **coincide**;
5. medir chips (`composite`/`fundamentales`) **solo para los ids que no se sirven**;
6. calcular y persistir solo esos huecos.

Guardas que se conservan:

- `position_open = None` (cartera no medida) ⇒ no se sirve caché, no se persiste y el motor
  falla cerrado con `position_unmeasured`;
- `force_refresh=True` ⇒ se mide todo;
- hints internos (jobs de servidor) se confían y no pasan por medición;
- la separación por cuenta (`account_scope`) no cambia.

`measure_opinion_hints` acepta una `OpenPositionMeasurement` ya calculada para no repetir la
lectura de cartera cuando solo faltan chips.

## 3 · Inventario campo backend → celda UI

### Precio / Día

| Campo backend | Uso en UI |
| --- | --- |
| `price`, `changePct` | cierre y variación |
| `meta.lastBarDate` | «Cierre 2026-11-12» |
| `meta.expectedLastBarDate` | tooltip del aviso |
| `meta.freshnessStatus` | `stale` ⇒ aviso ámbar «Cierre desactualizado» |
| `quote.source = "mercado"` | precio del lote de cotizaciones; sin `lastBarDate` se declara «Cotización sin fecha declarada» |
| `quote.source = "cartera"` | mark de la posición; se declara «Precio de cartera · sin cierre de mercado» (o «· Midiendo cierre…» mientras carga el lote) |

### Recomendación

| Campo backend | Uso en UI |
| --- | --- |
| `stance`, `ioScore` | etiqueta del dictamen + confianza |
| `dictamenStars` | ★ del dictamen junto a la etiqueta |
| `faScore`, `taScore` | detalle técnico (componentes) |
| `gateStatus` | chip «Veto del motor» / «Aviso del motor» |
| `distress` | chip «Fundamental en riesgo» |
| `engineVersion`, `computedAt` | detalle técnico |
| `reasons` | primer motivo truncado; todos en el detalle |

### Tendencia

| Campo backend | Uso en UI |
| --- | --- |
| `trends[key=short_term]` | línea «Corto: …» |
| `trends[key=background]` | línea «Fondo: …» |
| `indicators.primary` | base del indicador |
| `indicators.confirmation` | confirmación (RSI/SMA) |
| `vigencia` | vigencia del parte |

### Fuerza

Se lee de `study.strength` / `strengthBand`. Se pinta el número (`X / 10`), la banda y una
barra con `role="img"` y `aria-label`; el color no es la única señal.

### Soportes / Resistencias

| Campo backend (S2) | Uso en UI |
| --- | --- |
| `supports[].price`, `resistances[].price` | S1 / R1 dibujables |
| `distancePct` | `-6,70 %` / `+6,70 %` con signo |
| `structure.id` | «Estructura ascendente» |
| `atrRef`, `close` | detalle técnico |
| `state` de cada nivel | conteo `detectado`/`en_precio`/`roto`/`no_fiable`/`no_disponible` |

Si no hay nivel dibujable, la celda declara el estado del **más cercano** («el más cercano
está roto») en vez de dejar un hueco genérico.

### Momento

| Campo backend | Uso en UI |
| --- | --- |
| `phase` | fase del cockpit |
| termómetro (`entry`, `stopVigente`, `target1`) | «Frío / Templado / Caliente / Extendido» |
| geometría (`entry`, `stopVigente`, `target1`, `target2`) | `E … · S … · T1 … · T2 …` |

### Posición

`PositionDto` + `portfolioMeasured`. «Cartera sin medir» solo cuando la cartera no se leyó;
«Sin posición» solo cuando se leyó y no hay posición.

### Estudio del parte

`consensus`, `invalidation`, `nextReviewAt`, `expectedRR`, `riskAmount`, `direction`,
`hasOperationalPlan` y `decisionSummary` viven en el **detalle técnico**, no en primer nivel.

## 4 · Matriz «midiendo / ausente / medido»

| Estado | Cómo se declara | Dónde |
| --- | --- | --- |
| Midiendo | «Midiendo cotizaciones…», «Midiendo…» | precio sin ningún valor mientras llega el lote; cierre en medición cuando el precio es de cartera; niveles mientras cargan las velas; recomendación mientras llega el dictamen |
| Ausente | causa concreta («Sin precio», «Sin dictamen», «Sin nivel fiable», «Histórico insuficiente (N velas)») | misma celda |
| Medido | valor + fecha/fuente | misma celda |

Reglas duras:

- un hueco **nunca** se colapsa a `0` ni a verde;
- un score del dictamen sin medir se pinta «Sin medir» y **suma un hueco declarado** a la
  fila y a la cabecera; no se sustituye por `0` ni por ★3;
- el comodín `—` no se usa como dato ausente en primer nivel;
- la cabecera declara cuántos valores están **sin medir** y cuántos tienen el cierre
  desactualizado.

## 5 · Procesos del navegador

- `structureForBars` se memoiza con `WeakMap<readonly OhlcvBarDto[], MarketStructureResultV1>`.
  La identidad del array de velas solo cambia al refetchear, así que un refresco de cotización
  o de dictamen no recalcula ATR ni pivotes de toda la lista.
- `staleTime`: cotizaciones 5 min (son cierres de BD), cartera y estudios 60 s.
- `refetchOnWindowFocus: false` en velas y cotizaciones: evita la tormenta de N peticiones al
  volver a la pestaña.
- `quotesLoading`, `opinionsLoading` y `barsLoading` se exponen por separado para distinguir
  «midiendo» de «no medido».
- Diario baja `refetchInterval` a 5 min con `staleTime` de 60 s: es un resumen diario.
- Análisis cuenta y declara los valores **sin dictamen** en vez de omitirlos, y muestra
  scores, veredicto y motor en el detalle técnico de cada fila.

## 6 · Guardas de no agregación

- La recomendación visible es solo la del dictamen.
- Tendencia, fuerza, niveles y momento son columnas independientes y no intervienen en el
  orden ni en el estado.
- `state` sigue calculándose solo con dictamen + posición medida + causa de `no_trade`.
- Asesor no tiene CTA de compra ni de firma: explica; operar vive en Mercado y firmar en
  Confirm.
- No se añaden campos obligatorios al contrato: la ampliación del modelo compartido es
  aditiva y opcional en la entrada.

## 7 · Archivos

**Backend**

- `packages/py/application/src/bolsa_application/daily_opinion_hints.py`
- `packages/py/application/src/bolsa_application/daily_opinion_service.py`
- `packages/py/application/tests/test_daily_opinion_service_hints.py`

**Modelo compartido y UI**

- `packages/shared/src/cognitive/asesor-cartera.ts` (+ tests)
- `apps/web/src/features/research/use-asesor-cartera-data.ts` (+ tests)
- `apps/web/src/features/research/asesor-cartera-panel.tsx` (+ tests)
- `apps/web/src/features/research/asesor-opiniones-panel.tsx` (+ tests)
- `apps/web/src/features/research/asesor-daily-ops-panel.tsx`
- `apps/web/src/features/research/research-first-level.test.tsx`

## 8 · Verificación

```bash
uv run python -m pytest packages/py/application/tests/test_daily_opinion_service_hints.py \
  packages/py/application/tests/test_daily_opinion_stance.py -q
pnpm --filter @bolsa/shared test
pnpm --filter @bolsa/shared typecheck
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web contract:check
```

Ejecución dirigida y sus límites declarados:
[evidencia backend ↔ UI](./evidence/backend-ui-asesor-2026-11-12/README.md).

## 9 · Fuera de alcance

- Endpoint batch de OHLCV o de key-levels.
- Portar `swing-atr-v1` a Python o persistir niveles.
- Tocar `compute_stance`, umbrales, gate, sizing, ejecución, AUTO.
- `PROJECT_STATE.md` y `CHANGELOG.md`.

## Ver también

- [Evidencia backend ↔ UI Asesor](./evidence/backend-ui-asesor-2026-11-12/README.md)
- [Diseño S3 · Cartera del Asesor](./diseno-asesor-cartera-s3-2026-11-12.md)
- [Auditoría de integración F4](./auditoria-integracion-fase4-2026-11-11.md)
