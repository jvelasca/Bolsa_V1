# Diseño · S3 Cartera del Asesor · 2026-11-12

> Slice: pestaña **Cartera** de Asesor (`/research?tab=cartera`). Reúne, por valor,
> recomendación del dictamen, tendencia, fuerza, soportes/resistencias y momento, y los
> presenta como columnas independientes que **no se combinan**.
>
> Invariantes: `Δ motor = 0` · `Δ decisión = 0` · sin migración · sin `contract:gen` ·
> S0/F4-067 sin tocar · sin commit.
>
> Concordancia campo backend → celda y matriz «midiendo / ausente / medido»:
> [diseño backend ↔ UI de Asesor](./diseno-asesor-backend-ui-2026-11-12.md).

## 1 · Qué añade y qué no

Añade una vista de lectura que responde «¿qué dice el motor de cada valor que sigo y en qué
contexto está?» sin obligar a abrir ficha por ficha.

No añade:

- una segunda recomendación ni un score agregado;
- un CTA de compra, firma o encolado (eso vive en Mercado · Confirm);
- un endpoint nuevo, una migración ni un cambio de contrato;
- un recálculo de indicadores: tendencia, fuerza y niveles se **leen** de S1/S2.

## 2 · Universo

`membresía Estudio` ∪ `posiciones abiertas de la cuenta activa`, deduplicado por
`instrumentId`. El filtro «solo con posición» convierte la lista en una vista estricta de
cartera sin cambiar el modelo.

`decision-studies` se pide con `limit: 200` (la misma `queryKey` de OPERATIVA). Si el
servidor declara `total > estudios`, la cabecera avisa de que el listado vino recortado y la
lista **no** afirma «sin plan» sobre datos truncados.

## 3 · Modelo puro de la fila

`packages/shared/src/cognitive/asesor-cartera.ts` (sin React, sin IO, sin reloj):

| Bloque | Fuente | Nunca hace |
| --- | --- | --- |
| `recommendation` | dictamen diario + `marketStanceLabel` | no recalcula la postura |
| `trend` | `study.trends` (corto plazo → contexto) + `marketTrendLabel` | no infiere tendencia de los niveles |
| `strength` | `study.strength` / `strengthBand` | no calcula ADX ni lo deduce de la tendencia |
| `levels` | `computeMarketStructure` (S2), solo `detectado` | no pinta `0` como nivel |
| `moment` | fase del cockpit + `resolveThermometer` / geometría de salida | no autoriza entrada |
| `position` | `PositionDto` + `portfolioMeasured` | no confunde «no medida» con «sin posición» |
| `state` | dictamen + posición medida + causa de `no_trade` | **no** usa tendencia, fuerza ni niveles |

`structureProvenance` conserva método, versión, ventana, ATR, firma y número de pivotes para
el `Detalle técnico`; no se muestra en primer nivel.

## 4 · Las cinco categorías y su precedencia

| Orden | `state` | Etiqueta | Condición |
| --- | --- | --- | --- |
| 1 | `sin_datos` | Sin datos suficientes | cartera no medida · sin dictamen · `position_unmeasured` · `io_unmeasured` · `eod_data_stale` |
| 2 | `sin_datos` | Sin datos suficientes | postura `reduce`/`sell_exit` sin posición medida (incoherencia declarada) |
| 3 | `posicion_sin_respaldo` | Posición sin respaldo | posición abierta + `overbought` («Sin respaldo») o `review_strategy` |
| 4 | `posicion_abierta` | Posición abierta | posición abierta + `buy`, `hold_watch`, `reduce`, `sell_exit` o `no_trade` evaluado |
| 5 | `recomendacion_favorable` | Recomendación favorable | sin posición + `buy` |
| 6 | `evaluado_sin_oportunidad` | Sin oportunidad | sin posición + `hold_watch`, `no_trade` medido o `review_strategy` |

Notas duras:

- `overbought` se lee **«Sin respaldo»** (S1). No significa sobrecompra técnica.
- Un hueco de S/R **no** convierte la fila en `sin_datos`: se declara en la celda de niveles.
- La columna «Estado» es una categoría de presentación. Lleva `data-state` y tooltip con la
  precedencia; no es una señal de compra.

## 5 · Regla de no agregación (guarda falsable)

La recomendación visible es **solo** la del dictamen. Tendencia, fuerza, niveles y momento se
muestran en columnas distintas y el orden de la tabla no los usa: ordena por categoría y, dentro
de ella, por confianza del dictamen y símbolo.

Dos casos anclan la regla en tests:

1. contexto alcista completo (tendencia alcista fuerte, fuerza alta, estructura detectada) con
   `hold_watch` ⇒ sigue **Sin oportunidad** y recomendación **Mantener**;
2. `buy` con contexto flojo (fuerza muy baja, tendencia bajista, sin niveles fiables) ⇒ sigue
   **Recomendación favorable** porque manda el motor.

## 6 · Datos y caché

| Dato | `queryKey` | Notas |
| --- | --- | --- |
| Cartera | `["portfolio", accountScope]` | misma que OPERATIVA |
| Estudios | `["decision-studies", accountId, "mesa"]` | misma que OPERATIVA, `limit: 200` |
| Dictámenes | `["instrument-daily-opinions", ids, accountId, false]` | reutiliza `useInstrumentDailyOpinions` |
| Cotizaciones | `["asesor-cartera-quotes", idsKey]` | lote de 200 (`INSTRUMENT_QUOTES_BATCH_LIMIT`) |
| Velas | `["asesor-cartera-bars", idsKey, "1d"]` | `staleTime` 5 min |
| Velas por valor | `["ohlcv", id, "1d"]` | se lee de caché y se puebla con `fetchQuery` (500 velas, 60 s), compartida con el gráfico |

`loadAsesorCarteraBars` es una función pura respecto a React, exportada y testeada:

- concurrencia máxima **4**;
- reutiliza la caché existente sin fetch;
- un fallo por instrumento se declara (`failedIds`) y no tumba la lista;
- deduplica ids.

No hay endpoint batch de OHLCV y S0 impide tocar contrato: el cargador queda aislado para
sustituirlo por un endpoint cuando S0 lo permita, sin cambiar modelo ni UI.

## 7 · Columnas (primer nivel)

| Columna | Contenido | Hueco declarado |
| --- | --- | --- |
| Valor | símbolo, nombre, «Ver en Mercado» | — |
| Precio / Día | cierre, variación y fecha de la vela; aviso si el cierre está desactualizado | «Sin precio» · «Midiendo…» |
| Recomendación | etiqueta de las 7 posturas + confianza + ★ del dictamen + chips de veto/riesgo + primer motivo | «Sin dictamen» · «Midiendo…» |
| Tendencia | «Corto: …» + «Fondo: …» + base + confirmación + vigencia | «Sin dato de tendencia» |
| Fuerza | `strength` / 10 + banda + barra accesible | «Sin dato de fuerza» |
| Soportes / Resistencias | S1 y R1 dibujables con su distancia con signo + estructura | «Sin nivel fiable» · «Histórico insuficiente (N velas)» · estado del nivel más cercano |
| Momento | fase del cockpit + termómetro, o geometría `E · S · T1 · T2` | «Sin entrada publicada» · «Sin geometría publicada» |
| Posición | «Sin posición» solo si la cartera se leyó | «Cartera sin medir» |
| Estado | una de las cinco categorías + `Detalle técnico` | — |

Cabecera: «Universo en Estudio y posiciones de la cuenta activa. Cada columna mide una cosa
distinta; la lista no combina señales ni autoriza compras. La recomendación es la del
dictamen».

Accesibilidad: tabla con `caption` (oculto), `scope="col"` en cabeceras y color no exclusivo
(el texto y `data-state` llevan la información). En pantallas estrechas hay scroll horizontal;
no se ocultan columnas.

## 8 · Detalle técnico

Único disclosure permitido (`TechnicalDetail`, sin `<details>` paralelos). Contiene:

- dictamen: fecha de cierre de referencia, origen, confianza, valoración, motivos y motivos
  diagnósticos ocultos; componentes IO/FA/TA, veredicto del motor, `distress`, versión y
  `computedAt`;
- parte diario: fuerza y vigencia, tendencia de corto y de fondo, base y confirmación,
  consenso, R/R esperado, riesgo, dirección, próxima revisión e invalidantes;
- estructura: método y versión, ventana, ATR, pivotes, firma y conteo de estados de nivel;
- momento: fase, si es termómetro o geometría de posición, y las cuatro cotas;
- huecos declarados de la fila.

## 9 · Archivos

**Nuevos**

- `packages/shared/src/cognitive/asesor-cartera.ts`
- `packages/shared/src/cognitive/asesor-cartera.test.ts`
- `apps/web/src/features/research/use-asesor-cartera-data.ts`
- `apps/web/src/features/research/use-asesor-cartera-data.test.ts`
- `apps/web/src/features/research/asesor-cartera-panel.tsx`
- `apps/web/src/features/research/asesor-cartera-panel.test.tsx`
- `docs/engineering/diseno-asesor-cartera-s3-2026-11-12.md`
- `docs/engineering/evidence/s3-asesor-cartera-2026-11-12/README.md`

**Modificados**

- `packages/shared/src/cognitive/index.ts` — exporta el dominio nuevo.
- `apps/web/src/features/research/research-page.tsx` — `HubTab`, `parseTab`, botón y montaje
  de la pestaña «Cartera» antes de «Análisis», y enlace en el primer nivel de Tesis.
- `apps/web/src/features/research/research-first-level.test.tsx` — añade el panel al gate.
- `apps/web/src/features/trading/operativa-recomendacion-vocabulary.test.tsx` — añade el panel
  a los textos retirados.

## 10 · Fuera de alcance

- Rediseño maximizado de DECISIÓN.
- Endpoint batch de key-levels u OHLCV.
- Persistencia de niveles o de la lista.
- Cambios en `compute_stance`, umbrales, gate, sizing o ejecución.
- Capturas finales y axe E2E del cierre S5.
