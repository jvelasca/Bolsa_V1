# Metodología de soportes, resistencias y estructura — S2 · 2026-11-12

> **Qué fija este documento:** cómo se detectan los pivotes, cómo se agrupan en niveles, qué
> histórico se usa, qué pasa cuando no hay velas suficientes y qué significa cada estado de un
> nivel. Es la referencia ejecutable de [`market-structure.ts`](../../packages/shared/src/market-structure.ts).
>
> **Invariantes del slice:** `Δ motor = 0` · `Δ decisión = 0` · **sin migración**
> (`head` sigue `067_opinion_account_scope`) · **sin `contract:gen`** · `openapi.json` y
> `schema.d.ts` fuera del diff.
>
> **Relación con S1:** S2 no reabre la recomendación ni la tendencia del parte diario. El glosario
> de S1 ([`glosario-mercado-asesor-2026-11-12.md`](./glosario-mercado-asesor-2026-11-12.md)) sigue
> siendo la única fuente de las 7 posturas, los 19 motivos y `Lateral`/`Mixta`/`Neutra`. S2 añade
> un vocabulario **propio y separado** para estructura de pivotes.

---

## 0. Qué no es S2

- No es una señal, ni una orden, ni una autorización.
- No alimenta el motor, el gate, el sizing, el plan operativo ni el email de alarmas.
- No convierte un pivote aislado en soporte o resistencia.
- No sustituye los niveles que el usuario dibuja a mano (`SR_PRESETS`, plantillas `hline`/`hray`).
- No persiste nada en base de datos: un nivel es **reproducible**, no un hecho durable.

---

## 1. Definiciones

| Término | Definición operativa |
| --- | --- |
| **Pivote confirmado** | Barra `i` cuyo máximo (o mínimo) supera estrictamente los `pivotLookback` máximos (o mínimos) a cada lado. Necesita, por construcción, `pivotLookback` velas posteriores. |
| **Pivote no confirmado** | Extensión reciente de la serie que aún no tiene velas suficientes a la derecha. **No se inventa**: se declara y no genera nivel. |
| **Toque** | Cada pivote agrupado en un nivel. `touches` = número de pivotes del grupo. |
| **Zona** | Rango `[mínimo, máximo]` de los precios de los pivotes del grupo. |
| **Precio del nivel** | Media aritmética de los precios de los pivotes del grupo. |
| **Nivel activo (`detectado`)** | Nivel con toques suficientes, no roto, no en precio y con recencia suficiente. Es el **único** que se dibuja como línea válida. |
| **Nivel en precio (`en_precio`)** | El cierre actual está dentro de `0,25 × ATR` del precio del nivel. No se lee como S/R limpio. |
| **Nivel roto (`roto`)** | El cierre ha cruzado la zona en contra más de `0,5 × ATR` desde el último toque: soporte perdido o resistencia superada. |
| **Nivel no fiable (`no_fiable`)** | Tiene un solo toque, o dos toques antiguos, o queda absorbido por otro nivel más fuerte. |
| **No disponible (`no_disponible`)** | Faltan datos mínimos (velas, ATR, pivotes) o hay barras inválidas. Se declara la causa. |

---

## 2. Entrada y ventana histórica

- **Fuente:** las velas OHLCV que el gráfico ya carga para el instrumento y timeframe activos
  (`api.getOhlcv(instrumentId, 500, timeframe)` en
  [`chart-workspace-page.tsx`](../../apps/web/src/features/charts/chart-workspace-page.tsx)). No se
  pide histórico adicional ni se añade endpoint.
- **Ventana usada:** hasta las últimas **500** velas disponibles del timeframe visible.
- **Mínimo exigido:** **80** velas. Por debajo, `insufficient_history` y **ningún nivel calculado**.
- **Orden:** la serie se normaliza por `timestamp` ascendente antes de calcular. Si el llamante ya
  entrega orden ascendente, la normalización es una copia sin efectos.
- **Timeframe:** se declara en el resultado. El método no cambia con el timeframe; solo cambia la
  ventana temporal que representan esas 500 velas.

### Datos insuficientes o inválidos

| Situación | Estado | Copy visible |
| --- | --- | --- |
| 0 velas | `no_disponible` | «Sin datos OHLCV» |
| 1–79 velas | `insufficient_history` | «Histórico insuficiente: N velas (mínimo 80)» |
| 80+ velas, ATR no calculable | `no_disponible` | «Sin ATR calculable en la ventana» |
| 80+ velas, sin pivotes confirmados | `no_disponible` | «Sin pivotes confirmados en la ventana» |
| Alguna barra con OHLC no finito o `high < low` | `no_disponible` | «Velas inválidas en la ventana» |
| Última vela en curso (intradía) | se calcula igual | Nota: «Última vela en curso: el ATR puede variar; los pivotes confirmados no repintan» |

Motivo: un resultado a medias sería peor que declarar el hueco. Si una sola barra invalida el
cálculo, se declara en vez de recortar la serie en silencio.

---

## 3. Pivotes

```text
swing high en i  ⇔  high[i] > high[i−k] para todo k ∈ [1..N]
                ∧  high[i] > high[i+k] para todo k ∈ [1..N]

swing low en i   ⇔  low[i] < low[i−k] para todo k ∈ [1..N]
                ∧  low[i] < low[i+k] para todo k ∈ [1..N]

N = pivotLookback = 3 (ventana de 7 velas)
```

- **Comparación estricta**: un empate (`high[i] === high[i+k]`) **no** genera pivote. Evita dos
  pivotes gemelos para el mismo techo.
- **Rango válido de `i`**: `N <= i <= bars.length - 1 - N`. Las primeras y últimas `N` velas no
  pueden confirmar pivote.
- **No se inventan** pivotes por el borde: se declaran como no confirmados.
- Cada pivote conserva `timestamp`, `price` y `type` (`high` / `low`). Ese trío es la procedencia
  que la UI muestra.

---

## 4. ATR (solo tolerancia geométrica)

- ATR de Wilder con `atrPeriod = 14` sobre la serie completa de la ventana.
- Se toma el **último ATR finito** como referencia (`atrRef`). Si no existe, `no_disponible`.
- El ATR **no** se usa para decidir direcciones ni para puntuar: solo para agrupar y para medir
  distancias. No se muestra como indicador de fuerza.
- `atrRef` viaja en el resultado para que la agrupación sea reproducible.

---

## 5. Agrupación de pivotes en niveles

1. Se ordenan los pivotes por precio.
2. Cada pivote se compara con el **centro** del grupo candidato (media de sus precios):
   se une si `|precio − centro| <= clusterAtrMultiple × atrRef`, con
   `clusterAtrMultiple = 0,75`.
3. Se usa el **centro**, no el último precio ni el extremo: así una secuencia de pivotes
   ligeramente escalonados no se encadena hasta fusionar un rango entero.
4. Un pivote que no encaja en ningún grupo abre uno nuevo.
5. `price` del grupo = media de sus pivotes. `zoneLow` / `zoneHigh` = mínimo y máximo.
6. Cada grupo se clasifica por el **tipo de sus pivotes**: mínimos ⇒ **soporte**,
   máximos ⇒ **resistencia**. La agrupación se hace por separado en cada lado, así que un grupo
   nunca mezcla tipos. Un soporte roto sigue siendo «soporte roto», no se renombra a
   resistencia: el nombre dice qué estructura era, no dónde está el precio hoy.
7. Se conservan como máximo **3 soportes y 3 resistencias**, priorizando los `detectado` y,
   dentro del mismo estado, los más cercanos al cierre. El resto se descarta y no se dibuja.

Regla de absorción: si dos grupos distintos caen dentro de `0,25 × ATR` y uno tiene más toques,
el débil pasa a `no_fiable` con motivo `absorbido_por_nivel_mas_fuerte`. Nunca se fusionan dos
niveles ya formados: fusionarlos borraría procedencia.

---

## 6. Estado de un nivel (precedencia)

El primer estado que encaja manda. Orden declarado en código y falsable por test:

| # | Estado | Condición | ¿Se dibuja? |
| --- | --- | --- | --- |
| 1 | `no_disponible` | Sin velas/ATR/pivotes válidos, o barras inválidas | No |
| 2 | `no_fiable` | `touches < 2`, o dos toques sin toque reciente, o `absorbido_por_nivel_mas_fuerte` | No (se declara) |
| 3 | `en_precio` | `|cierre − price| <= 0,25 × atrRef` | No (se declara) |
| 4 | `roto` | El cierre cruzó la zona en contra más de `0,5 × atrRef` | No (se declara) |
| 5 | `detectado` | `touches >= 2`, no roto, no en precio, con recencia suficiente | **Sí** |

La fiabilidad va **antes** que la posición: un pivote aislado no se puede «romper» ni estar
«en precio» porque nunca fue estructura. Solo un nivel con al menos dos toques puede pasar a
`en_precio` o `roto`.

**Recencia suficiente** (`detectado`):

- `touches >= 3` ⇒ siempre suficiente.
- `touches === 2` ⇒ el último toque debe caer dentro del **25 % final** de la ventana
  (`lastTouchIndex >= bars.length - ceil(bars.length × 0,25)`).

Un nivel de dos toques antiguos es historia, no estructura vigente: se declara `no_fiable` con
motivo `sin_toque_reciente`.

### Motivos declarables (`reasons`)

| Código | Etiqueta visible |
| --- | --- |
| `sin_velas` | Sin datos OHLCV |
| `historico_insuficiente` | Histórico insuficiente |
| `velas_invalidas` | Velas inválidas en la ventana |
| `sin_atr` | Sin ATR calculable |
| `sin_pivotes` | Sin pivotes confirmados |
| `un_solo_toque` | Un solo toque |
| `sin_toque_reciente` | Dos toques sin toque reciente |
| `absorbido_por_nivel_mas_fuerte` | Absorbido por un nivel más fuerte |
| `precio_en_nivel` | El precio está en el nivel |
| `nivel_roto` | Nivel roto por el precio |
| `ultima_vela_en_curso` | Última vela en curso |

Ninguna superficie pinta estos códigos en crudo: pasan por `marketLevelStateLabel` y
`marketLevelReasonLabel`.

---

## 7. Estructura de tendencia (vocabulario propio)

Se calcula **solo** con pivotes confirmados. No usa el `study.trends` de S1.

- Entrada: los últimos **3** máximos y **3** mínimos confirmados.
- Tolerancia: `0,5 × atrRef` para considerar dos extremos «iguales».

| Estructura | Condición | Etiqueta visible |
| --- | --- | --- |
| `ascendente` | Los 3 máximos crecen y los 3 mínimos crecen (fuera de tolerancia) | Estructura ascendente |
| `descendente` | Los 3 máximos decrecen y los 3 mínimos decrecen | Estructura descendente |
| `en_rango` | Máximos y mínimos dentro de tolerancia entre sí | Estructura en rango |
| `sin_estructura` | Señales contradictorias o menos de 3 pivotes por lado | Sin estructura suficiente |

**`estructura en rango` ≠ `Lateral` de S1.** `Lateral` significa ADX ≤ 25 (fuerza del estudio);
`en_rango` significa que los pivotes no progresan. Se pintan por separado y con etiquetas distintas.

### ADX / DI como contexto separado

- Se leen del estudio si ya están disponibles; S2 **no** los calcula de nuevo ni los usa para
  detectar niveles.
- Lo primero que publica el estudio es `strength` (0–10) + `strengthBand`; si algún día llegan
  ADX/DI numéricos, se muestran como alternativa. Nunca se inventa un ADX.
- Se muestran en una línea aparte: «Fuerza del estudio: …» o «Sin dato de fuerza».
- No se fusionan con la estructura, no la contradicen y no la sobrescriben.

---

## 8. Trazabilidad

El resultado de `computeMarketStructure`:

```ts
type MarketStructureResultV1 = {
  methodId: "swing-atr-v1";
  methodVersion: 1;
  params: {
    pivotLookback: number;
    atrPeriod: number;
    clusterAtrMultiple: number;
    inPriceAtrMultiple: number;
    brokenAtrMultiple: number;
    maxLevelsPerSide: number;
    minBars: number;
  };
  window: { from: string | null; to: string | null; bars: number; timeframe: string };
  inputSignature: string;
  status: "ok" | "insufficient_history" | "no_disponible";
  reasons: string[];
  atrRef: number | null;
  close: number | null;
  supports: MarketLevelV1[];
  resistances: MarketLevelV1[];
  structure: MarketStructureTrendV1;
  /** Hecho declarado: la última vela puede seguir en curso. */
  lastBarMayBeOpen: boolean;
};
```

Cada `MarketLevelV1` incluye `kind`, `price`, `zoneLow`, `zoneHigh`, `touches`, `state`,
`reasons`, `pivots[]`, `lastTouchAt`, `distancePct`, `distanceAtr`.

- `inputSignature`: huella estable de ventana + parámetros + primera/última vela. Permite memoizar
  en la UI sin recalcular y sin depender de la identidad del array.
- La UI ofrece «Ver procedencia»: fechas y precios de los pivotes que forman el nivel.
- **Trazable** significa reproducible con esas velas y esos parámetros. No se guarda en BD, no se
  convierte en hecho durable y no viaja por el contrato HTTP.

---

## 9. Qué ve el usuario

| Elemento | Detalle |
| --- | --- |
| Línea de nivel | Solo `detectado`. Discontinua, con etiqueta `S·calc` / `R·calc` y color propio, distinto del verde/rojo de los presets manuales. |
| Panel de lectura | Estado global, estructura, ADX/DI de contexto, y un bloque por nivel con precio, zona, toques, estado y distancia. |
| Nivel no dibujado | Se lista con su estado y su motivo: «No fiable · Un solo toque», «Roto», «En precio», «No disponible». |
| Coincidencia con el plan | Si un nivel calculado coincide con entrada/stop/T1/T2 (`0,25 × ATR`), se atenúa y se declara la coincidencia. Los niveles operativos mandan. |
| Sin niveles | Se declara el hueco con la causa. Nunca se pinta una línea «de relleno». |

---

## 10. Matriz de pruebas (falsable)

`packages/shared/src/market-structure.test.ts`:

1. Pivote confirmado con `N = 3`; la última vela nunca confirma.
2. Empate en el máximo ⇒ **no** genera pivote.
3. Agrupación a `0,60 × ATR` ⇒ mismo grupo; a `0,90 × ATR` ⇒ grupos distintos.
4. `price` = media, `zoneLow`/`zoneHigh` = extremos del grupo.
5. Un toque ⇒ `no_fiable` + `un_solo_toque`.
6. Dos toques recientes ⇒ `detectado`; dos toques antiguos ⇒ `no_fiable` + `sin_toque_reciente`.
7. Tres toques antiguos ⇒ `detectado`.
8. Cierre dentro de `0,25 × ATR` ⇒ `en_precio`.
9. Cierre cruzando la zona más de `0,5 × ATR` ⇒ `roto`.
10. Soporte por debajo, resistencia por encima; máximo 3 por lado.
11. 79 velas ⇒ `insufficient_history`; 80 velas ⇒ se calcula.
12. Barra con `high < low` ⇒ `no_disponible` + `velas_invalidas`.
13. Estructura ascendente, descendente, en rango y contradictoria.
14. `inputSignature` estable ante el mismo input y distinto ante otra ventana.
15. El array de velas de entrada no se muta.
16. Golden fixture: resultado completo estable.

`apps/web/src/features/charts/market-structure-chart-levels.test.ts`:

- Solo `detectado` produce líneas.
- `no_fiable`, `roto`, `en_precio` y `no_disponible` no producen línea.
- La etiqueta `S·calc`/`R·calc` no coincide con «Soporte»/«Resistencia» de `SR_PRESETS`.

`apps/web/src/features/market-structure/market-structure-readout.test.tsx`:

- Declara histórico insuficiente sin pintar niveles.
- Muestra procedencia y motivo en un nivel no fiable.
- ADX/DI aparece como contexto separado de la estructura.

---

## 11. Límites declarados

1. La detección depende de `pivotLookback`: con `N = 3`, un giro de dos velas no es pivote.
2. La agrupación por ATR cambia con la volatilidad: en un valor muy volátil, dos precios lejanos
   en términos absolutos pueden ser el mismo nivel.
3. Un nivel **no** es una predicción: describe dónde hubo rechazo, no dónde tiene que volver.
4. El ATR de referencia es el último de la ventana: si la última vela está en curso, puede variar.
5. Los pivotes confirmados no repintan, pero un nivel `detectado` puede pasar a `roto` con una vela
   nueva: el estado se recalcula, la procedencia no se reescribe.
6. S2 v1 se limita a Instrumento y OPERATIVA. Asesor, listas y Estudio quedan fuera de alcance.
