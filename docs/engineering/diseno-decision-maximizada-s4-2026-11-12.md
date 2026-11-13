# Diseño · S4 Ventana maximizada de DECISIÓN · 2026-11-12

> Slice: **integración visual** de la ventana maximizada de DECISIÓN / OPERATIVA
> (`/trading`). El único titular pasa a ser la recomendación del dictamen; la
> actuación y el estado de cartera se separan; tendencia, fuerza y niveles pasan a
> contexto técnico.
>
> Invariantes: `Δ motor = 0` · `Δ decisión = 0` · sin migración · sin `contract:gen` ·
> S0/F4-067 sin tocar · sin commit · sin `git add`.

## 1 · Qué cambia y qué no

Antes, al maximizar DECISIÓN, la pantalla abría con «Análisis Diario» y «Estructura y
niveles», y la recomendación del día vivía dentro de **Evidencia**, una sección
colapsada. El orden de lectura invitaba a tomar el contexto técnico como una orden.

Ahora la ventana maximizada de escritorio se lee así:

1. **Recomendación principal** (hero, a ancho completo, fuera de la rejilla):
   dictamen S1 + confianza + motivos, chip de estado de cartera S3 y vía de actuación.
2. **ACCIÓN**: cockpit operativo (estado + CTA + próxima acción).
3. **CONTEXTO TÉCNICO**: análisis diario y estructura/niveles, con rótulo explícito
   de que informan y no autorizan.
4. **SEGUIMIENTO**: Lab + Mandato.
5. **EVIDENCIA**: pulso, detalle técnico, aprendizaje y AUTO.

No cambia:

- el motor, el dictamen, `compute_stance`, umbrales, gate, sizing ni ejecución;
- el dock lateral ni la ventana estrecha/móvil (misma composición que antes);
- el contrato, el esquema, las migraciones ni S0/F4-067;
- ningún texto de S1: el hero reutiliza `OperativaDictamenBlock`.

## 2 · Superficies: `dock` · `maximized` · `narrow`

`TradingOperativaPanel` recibe `surface?: "dock" | "maximized" | "narrow"`.

| Superficie | Cuándo | Composición | `data-surface` |
| --- | --- | --- | --- |
| `dock` | dock lateral de DECISIÓN | la de siempre (dictamen en Evidencia) | `dock` |
| `maximized` | ventana maximizada de escritorio | hero + rejilla S4 | `maximized` |
| `narrow` | ventana maximizada en estrecho/móvil | la de siempre, aunque `maximized` sea `true` | `narrow` |

`TradingLayout` decide: en la rama maximizada pasa `surface={narrow ? "narrow" :
"maximized"}`; en el dock pasa `surface="dock"`. `maximized` y `data-maximized` se
mantienen para no romper los tests y el comportamiento previos.

## 3 · El hero

`apps/web/src/features/trading/operativa-recomendacion-principal.tsx`.

- `data-testid="operativa-recomendacion-principal"`, `data-state` con la categoría de
  S3 y `data-action-hint` con la vía de actuación.
- Chip `Estado de cartera` (`data-testid="operativa-cartera-state"`, `data-state`) con
  `title` = `meaning · gaps` del clasificador. Etiquetas: «Recomendación favorable»,
  «Posición abierta», «Posición sin respaldo», «Sin oportunidad», «Sin datos
  suficientes».
- Fila `Actuación` (`data-testid="operativa-actuacion"`) con `data-action-hint` y
  `data-blocked-reason` cuando la entrada está bloqueada.
- Nota fija (`data-testid="operativa-recomendacion-aviso"`): «Esta ventana informa: la
  recomendación no ejecuta. La firma vive en Confirm y la operación en ACCIÓN.
  Tendencia, fuerza y niveles son contexto técnico, no órdenes.»
- Mientras el dictamen carga: `data-state="midiendo"`, sin chip de cartera y con
  «Midiendo recomendación…». No se inventa categoría a partir de una lectura ausente.

`OperativaDictamenBlock` gana `variant?: "compact" | "hero"` (por defecto `compact`).
En `hero` solo cambia la escala tipográfica y la copia de carga; textos, testids
(`operativa-dictamen`, `operativa-dictamen-motivos`) y reglas de S1 son idénticos.

## 4 · Vía de actuación (helper puro)

`apps/web/src/features/trading/operativa-action-hint.ts` — sin React, sin IO, sin reloj.

Salidas: `entrada_disponible` · `entrada_bloqueada` · `salida_en_accion` ·
`sin_actuacion`. Motivos de bloqueo, **en el mismo orden que `canPropose`**:
`sin_cuenta` → `cartera_sin_medir` → `estudios_sin_medir` → `modo_sin_propuesta` →
`entradas_bloqueadas` → `fuera_de_estudio`. Se declara el primero que falla; no se
acumulan motivos.

Precedencia de la pista:

1. `sin_datos` ⇒ `sin_actuacion` (no se describe ninguna vía).
2. posición abierta ⇒ `salida_en_accion` (la salida vive en ACCIÓN).
3. categoría distinta de `recomendacion_favorable` ⇒ `sin_actuacion`.
4. `recomendacion_favorable` + compuertas ⇒ `entrada_disponible` o `entrada_bloqueada`.

Regla dura: `sin_actuacion` **nunca** significa «sin posición». La ausencia de posición
solo la declara la cartera medida. El helper no autoriza: `canAct` describe la vía, el
CTA del cockpit sigue mandando.

## 5 · Estado de cartera (S3, reutilizado)

`classifyAsesorCarteraState` de `@bolsa/shared` con
`opinion: activeOpinion ?? null` y
`position: { measured: positionMeasured, hasOpenPosition }`, donde
`hasOpenPosition = |quantity| > 0` sobre la posición leída.

No se recalcula nada: tendencia, fuerza y niveles no pueden promover la fila a
«Recomendación favorable». El estado es de presentación y no se persiste.

## 6 · Rejilla `.operativa-maximized-grid`

En `apps/web/src/index.css`, dentro del contenedor `.operativa-panel-scroll`
(`container-type: inline-size`):

| Corte | Columnas | Reparto |
| --- | --- | --- |
| base | 1 | hero · acción · contexto · seguimiento · evidencia |
| `≥ 52rem` | 2 | fila 1: acción \| contexto · fila 2: seguimiento \| evidencia |
| `≥ 78rem` | 3 | acción (26rem) \| contexto \| seguimiento · evidencia a lo ancho |

El hero queda fuera de la rejilla, a ancho completo. `align-items: start` evita que las
columnas se estiren por el contenido de la más larga. No se oculta ningún bloque en
ningún corte.

## 7 · Estados que la ventana debe demostrar

| Caso | `data-state` | Chip | Vía |
| --- | --- | --- | --- |
| `buy` sin posición | `recomendacion_favorable` | Recomendación favorable | entrada disponible |
| `hold_watch` con posición | `posicion_abierta` | Posición abierta | salida en ACCIÓN |
| `overbought` con posición | `posicion_sin_respaldo` | Posición sin respaldo | salida en ACCIÓN |
| cartera no medida / sin dictamen | `sin_datos` | Sin datos suficientes | sin actuación |
| dictamen cargando | `midiendo` | — | — |

`overbought` nunca imprime «Sobrecomprado» ni «sobrecompra»: la etiqueta es la de S1
(«Sin respaldo»).

## 8 · Fuera de alcance

- endpoint batch de OHLCV o key-levels;
- cambios en el dock lateral o en la ventana estrecha;
- persistencia de la composición o de los estados;
- cualquier cambio en motor, contrato, migración o S0/F4-067;
- botones de compra, firma o ejecución dentro del hero;
- `CHANGELOG.md`, `PROJECT_STATE.md`, `openapi.json`, `schema.d.ts`.
