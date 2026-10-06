# Auditoría UI AUTO — pantalla por pantalla (`v2.88.73-beta`)

> **AsOf:** 2026-10-06 · **Estado:** **AUDITORÍA EN SOLO LECTURA** (no es código, no es un sello).
> **Base:** tag `v2.88.73-beta` → `a30dadff` (núcleo financiero congelado, `Δ motor = 0`, Alembic `050`).
> **Padres:** [modelo semántico 1.0](./spec-auto-ui-semantic-model-1-2026-10-05.md) · [spec 3.0](./spec-auto-ui-refactor-3-0-2026-10-06.md) · [auditoría de cadena financiera](./auditoria-ui-cadena-financiera-2026-10-06.md) · [auditoría cockpit 2026-10-05](./auditoria-ui-auto-cockpit-2026-10-05.md).
> **Compañera:** [spec de operación para usuario básico](./spec-auto-operacion-usuario-basico-2026-10-06.md).
> **Naturaleza:** UI / producto. Sin cambio de motor, sin contrato HTTP, sin Alembic, sin tocar el worker.

## 0. Pregunta

¿Puede un usuario básico, en la UI del tag, responder en segundos qué está haciendo AUTO, sobre qué activo, qué decidió, y hasta dónde llegó la cadena (orden, ejecución, fill, materialización, posición, dinero) sin confundir intención con hecho?

## 1. Línea base y deriva local

La línea base es el **tag**. El árbol de trabajo posterior al tag cambia solo copy y plegado (no el motor). Esa deriva **no** es la UI certificada en GitHub:

| Superficie | En el tag | Deriva local (no es línea base) |
| --- | --- | --- |
| Etiqueta de `ORDER` | «Orden enviada» | «Orden anotada» |
| Etiqueta de `FILL` | «Operación ejecutada» | «Precio aplicado» |
| Fila `POSITION` | Derivada de `FILL` y visible como «Posición abierta» | Plegada en `FILL`; el precio declara que no afirma posición ni dinero |
| Estado del ciclo | «Abierto» / «Cerrado» si `closed` es afirmable | «Apartada» / «Orden anotada» / «Precio aplicado» / «Cerrada» |
| Contador de la HOME | Cuenta todo ciclo con `closed === false` y medición completa | Solo cuenta ciclos en «Precio aplicado» |
| Copy de Sistema | «qué hizo el broker» | «qué registró la simulación» |

El resto de pantallas citadas abajo coincide con el tag.

## 2. Rúbrica

Seis preguntas de primer nivel:

| # | Pregunta | Respuesta que el usuario debería ver |
| --- | --- | --- |
| 1 | ¿AUTO está funcionando? | Funcionando / Esperando / Detenido |
| 2 | ¿Qué está haciendo? | Analizando / Esperando / Comprando / Vendiendo |
| 3 | ¿Qué activo? | Símbolo, o «Sin dato todavía» |
| 4 | ¿Qué ha decidido? | Comprar / Vender / No hacer nada — distinto de haber comprado |
| 5 | ¿Qué ha ocurrido realmente? | Orden / Ejecutada / Parcial / Materializada |
| 6 | ¿Qué dinero utiliza? | Simulado. Nunca se presenta como dinero real |

Escalera que la UI no puede saltarse. Cada peldaño tiene hecho propio. Un peldaño alcanzado no pinta el siguiente:

```text
DECISIÓN → ORDEN → EJECUCIÓN → FILL → MATERIALIZACIÓN SIM → POSICIÓN → DINERO / P&L
```

Fallo de una celda: **afirma de más**, **se salta un estado**, **usa jerga** en primer nivel, o **declara el hueco**. Un tick de simulación o de posición sin traza propia es **afirmación prohibida**.

## 3. Matriz de las seis preguntas

Hecho que la UI puede copiar hoy, sin inventar: cabecera del monitor (`state`, sellos de decisión/heartbeat), pasos del ciclo (`SIGNAL` … `CYCLE_CLOSED`), tipo de cuenta y resumen de cuenta (capital). El monitor **no** trae un paso de materialización, ledger ni caja.

| Pregunta | `/auto` Resumen | Operación | Cartera | Riesgo | Sistema | Monitor experto |
| --- | --- | --- | --- | --- | --- | --- |
| 1 Funcionando | «Activo» o «Sin dato todavía». El estado crudo del motor se aplana a «Funcionando correctamente». No hay Esperando ni Detenido. | No | No | Estado de integridad (`Normal` / `Atención` / `Bloqueado`), que es otra pregunta | Repite el resumen de la HOME | Estado crudo, venue, reloj, heartbeat |
| 2 Qué hace | Hora de última actividad y «Próximo análisis» o «Esperando nueva señal». No dice analizando / comprando / vendiendo | Lista de etapas, no una frase de acción | Posiciones y órdenes de la cuenta | No | La misma frase genérica | Campos técnicos (`text-[10px]`) |
| 3 Activo | No en el resumen. Solo dentro de cada operación abierta, si el contador la incluye | `instrumentId` en el título y en la identidad | Símbolo de la posición de cuenta | No | No | En la timeline |
| 4 Decisión | No | Etapa «Decisión de cartera» en `NOT_MEASURED` («Sin dato todavía»). Correcto: no hay `PortfolioDecision` durable. La selección TOP-N es otra fila | No | No | No | Pasos crudos |
| 5 Qué ocurrió | El estado visible del ciclo en el tag es «Abierto» o «Cerrado». «Abierto» cubre reserva, orden y fill | «Orden enviada» y «Operación ejecutada» se pintan «Hecho» cuando el paso existe. No hay ranura de materialización ni de parcial | «Operaciones abiertas» / «pendientes». Copy de mesa: «Orden enviada — pendiente de ack», «T1 ejecutado» | «Incidencias de enlace» (número). Riesgo por posición: «Sin dato todavía» | Reconciliación dentro del detalle técnico | Timeline completa, jerga |
| 6 Dinero | Tira transversal: `DINERO VIRTUAL · AUTO DEMO` y capital del resumen de cuenta | Hereda la tira. El resultado del ciclo (P&L) vive en la etapa Resultado, si el paso existe | Banner «CARTERA DEMO». Posiciones del panel de operaciones | No muestra efectivo | Enlaza al historial (ledger) | `venue` sin traducir en la cabecera |

Hueco común a todas las secciones de primer nivel: las preguntas 2, 4 y 5 no tienen una frase única. La HOME responde «qué puedo hacer» y «qué ha pasado» (enlaces a Análisis), que no están en esta rúbrica de seis preguntas.

## 4. Escalera en la historia de una operación

Fuente en el tag: `buildAutoOperationStory` y las etiquetas llanas. La fila se pinta si `foldedInto` es nulo. En el tag solo `EXIT` se pliega en `SETTLEMENT`. `POSITION` es fila propia, `kind = DERIVED`, copiada del paso `FILL`.

| Peldaño | Hecho durable en el tag | Texto de primer nivel si el paso está alcanzado | Fallo |
| --- | --- | --- | --- |
| Decisión | No hay paso de cartera. La etapa queda `NOT_MEASURED` | «Decisión de cartera · Sin dato todavía» | Declara el hueco. Correcto |
| Orden | Paso `ORDER` (registro de pedido). No es un envío a XTB | «Orden enviada · Hecho» | **Afirma de más.** «Enviada» se lee como salida al broker |
| Ejecución | No hay paso distinto de `FILL` | No hay fila | **Se salta el estado.** El fill ocupa el sitio de la ejecución |
| Fill | Paso `FILL` (precio y cantidad) | «Operación ejecutada · Hecho» | **Afirma de más.** El precio no cierra la cadena |
| Materialización SIM | El monitor no expone apply, ledger ni caja | No hay fila | **Se salta el estado.** La UI no puede poner un tick; tampoco lo declara como hueco propio |
| Posición | No hay paso `POSITION`. En el tag la fila copia el estado de `FILL` | «Posición abierta · Hecho» | **Afirmación prohibida.** Un fill se presenta como posición |
| Dinero / P&L | `CYCLE_CLOSED` trae P&L si el ciclo cerró con medición completa. La caja de la cuenta vive en el resumen de cuenta, no en el ciclo | «Resultado final» si hay cierre. Si no, la fila no está «Hecho» | El P&L de cuenta y el P&L del ciclo no se separan en la tarjeta. Un ciclo sin cierre no dice «dinero sin dato» |

`DECISION` ya no se confunde con TOP-N (eso quedó cerrado en el modelo semántico). El salto peligroso del tag está **después** de la orden: enviada → ejecutada → posición abierta, sin ejecución, sin parcial y sin materialización.

## 5. Recorrido

### 5.1 Tira de realidad

Montada en el layout de `/auto/*` ([auto-workspace-layout.tsx](../../apps/web/src/components/layout/auto-workspace-layout.tsx), [auto-reality-strip.tsx](../../apps/web/src/features/auto/auto-reality-strip.tsx)).

Con cuenta `simulated` o `paper` el primer nivel dice `DINERO VIRTUAL · AUTO DEMO`, «No envía órdenes a XTB» y el capital del resumen de cuenta, con medición `NO MEDIDO` si el resumen no llegó. Un tipo de cuenta ausente queda en ámbar (`TIPO DE CUENTA NO CONFIRMADO`), no en verde.

Huecos respecto a la rúbrica:

- La frase permanente pedida es `SIMULACIÓN — DINERO VIRTUAL`. Hoy dice `DINERO VIRTUAL · AUTO DEMO`.
- No existe la frase «XTB conectado: no implica ejecución real».
- Si la cuenta activa es `live`, el helper pinta `DINERO REAL` y «Broker LIVE conectado» **dentro de AUTO**. AUTO no tiene camino de ejecución real. Esa frase roja en el espacio AUTO mezcla la cuenta con la operativa automática.

### 5.2 `/auto` Resumen

[auto-home-page.tsx](../../apps/web/src/features/auto/auto-home-page.tsx). Tres fichas (AUTO, Operaciones, Riesgo), luego «¿Qué está haciendo AUTO?», «¿Qué puedo hacer?» y «¿Qué ha pasado?».

En el tag, «N abiertas» cuenta ciclos con `closed === false` y medición completa. Una reserva y una orden sin fill también tienen `closed === false`. El contador las presenta como operaciones abiertas: **afirmación prohibida** (intención contada como posición).

«Funcionando correctamente» no nombra activo ni acción. El DTO de cabecera no trae símbolo ni lado; la UI no debe inventarlos. Hoy el hueco se disfraza de frase genérica en lugar de «Sin dato todavía» en las casillas de activo y de acción.

Estados de carga y de error sí están separados del vacío («Sin operaciones abiertas»).

### 5.3 `/auto/operar` y la operación

[auto-operar-page.tsx](../../apps/web/src/features/auto/auto-operar-page.tsx) separa oportunidades (enlace a la Mesa, con «Ranking ≠ orden») de la lista de ciclos. La identidad legible distingue dos ciclos del mismo símbolo por día. En el tag el cuarto segmento es «Abierto» o «Cerrado», así que dos ciclos abiertos del mismo día y símbolo siguen pareciéndose, y «Abierto» no dice si hay orden, fill o posición.

[auto-operacion-page.tsx](../../apps/web/src/features/auto/auto-operacion-page.tsx) en el tag describe la lectura como «qué hizo el broker». [AutoOperationStoryPanel](../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx) parte la historia en hechos, contexto y «qué aprendemos», y guarda el detalle técnico plegado. Eso cumple el resumen-arriba del modelo. No cumple la escalera: falta la tarjeta de ranuras y sobran afirmaciones de §4.

### 5.4 `/auto/cartera`

[auto-cartera-page.tsx](../../apps/web/src/features/auto/auto-cartera-page.tsx) abre con «CARTERA DEMO — posiciones simuladas» y «No se envían órdenes reales a XTB», y luego monta `OperationsPanel` (posiciones abiertas, órdenes pendientes, acciones que encolan Confirm).

El panel compone copy de mesa que el espacio AUTO no traduce:

- `paperOrderStatusCopy`: «Orden enviada — pendiente de ack» ([paper-order.ts](../../packages/shared/src/cognitive/paper-order.ts)).
- Etapa de ciclo «T1 ejecutado» ([lifecycle-stage-label.ts](../../packages/shared/src/cognitive/lifecycle-stage-label.ts)), usada por la superficie de decisión que el panel puede mostrar junto a la posición.

«T1 ejecutado» y «orden enviada» se leen como hecho de broker. En AUTO son registros de simulación. El banner DEMO está encima; el copy de la fila lo contradice.

### 5.5 `/auto/riesgo`

[auto-riesgo-page.tsx](../../apps/web/src/features/auto/auto-riesgo-page.tsx). Primer nivel: estado de integridad, integridad de cartera, incidencias de enlace. Riesgo abierto, máxima pérdida y límite diario salen «Sin dato todavía» y enlazan a su superficie. No inventa un cero. No responde activo, decisión ni escalera. Correcto como sección de riesgo; no sustituye la HOME.

### 5.6 `/auto/analisis`

[auto-analisis-page.tsx](../../apps/web/src/features/auto/auto-analisis-page.tsx). Cuatro preguntas (qué ha pasado, por qué, si funciona, qué aprendemos) sobre DÍA-D, evidencia, laboratorio y asesor. Conocimiento cross-ciclo. No es el estado de una operación en curso. La jerga de los paneles (veredictos OOS, mediciones) sigue en el cuerpo de la pestaña, debajo de una pregunta en lenguaje llano.

### 5.7 `/auto/sistema` y `/auto-monitor`

Sistema pone el resumen llano arriba y pliega monitor, reservas, concurrencia, «Broker / ejecución» y reconciliación. En el tag la descripción de la sección dice «qué hizo el broker». El bloque experto conserva `venue`, reloj y heartbeat en el monitor ([auto-monitor-header.tsx](../../apps/web/src/features/auto-monitor/auto-monitor-header.tsx)).

`/auto-monitor` sigue fuera del espacio `/auto/*`. Es el nivel auditor. No debe ser la puerta de entrada. Hoy la operación enlaza ahí para el detalle técnico, que es el sitio correcto de Decision, Reservation, ExecutionEvent, Ledger, Reconciliation e Idempotency.

## 6. Afirmaciones prohibidas en el tag

1. «Posición abierta · Hecho» copiado de `FILL`.
2. «Operación ejecutada» para un precio y una cantidad.
3. «Orden enviada» para un registro que no sale a XTB.
4. «N abiertas» contando reservas y órdenes sin fill.
5. «Abierto» como único estado entre reserva y fill.
6. `DINERO REAL` dentro de AUTO cuando la cuenta activa es `live`, sin camino de ejecución real de AUTO.
7. «T1 ejecutado» y «Orden enviada — pendiente de ack» en la cartera que AUTO compone.

## 7. Lo que el tag ya hace bien

- La tira verde de dinero virtual está en todas las secciones AUTO cuando la cuenta no es `live`.
- Un tipo de cuenta ausente no se pinta en verde.
- `DECISION` de cartera permanece «Sin dato todavía». TOP-N es otra fila.
- `EXIT` no duplica `SETTLEMENT`.
- Carga, error y vacío de la HOME y de Operar son estados distintos.
- Riesgo no rellena huecos con `0`.
- El detalle técnico de la historia y de Sistema está plegado.
- El capital de la tira usa `MeasurementValue`: sin resumen de cuenta, la medición es `NO MEDIDO`.

## 8. Residuo que el diseño debe respetar

El monitor no expone materialización, ledger ni caja como pasos del ciclo. La UI no los inventa. Una ranura de materialización sin ese paso se queda en «Sin dato todavía». La posición y el efectivo de la cuenta pueden mostrarse como hechos **de cuenta** (resumen ya existente), rotulados como cuenta SIM, y no como «esta operación ya movió el libro».

`PortfolioDecision` durable sigue abierta. La casilla «qué ha decidido» no puede afirmar Comprar o Vender hasta que exista esa traza. Mientras tanto: «Sin dato todavía».

## 9. Falsabilidad de esta auditoría

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | En el tag, `FILL` alcanzado pinta «Operación ejecutada» y «Posición abierta». | Que el tag ya pliegue `POSITION` o use «Precio aplicado». |
| 2 | La HOME del tag no nombra activo ni lado. | Que `buildAutoHomeSummary` del tag exponga símbolo o comprar/vender. |
| 3 | «Abierto» en el tag agrupa reserva, orden y fill. | Que el `statusLabel` del tag distinga esos pasos. |
| 4 | Una cuenta `live` pone `DINERO REAL` en el layout de AUTO. | Que `buildAutoReality` ignore `accountType === "live"` dentro de `/auto`. |
| 5 | No hay paso de materialización en la historia. | Que `STORY_STAGE_SPECS` del tag tenga una etapa con traza de apply distinta de `FILL`. |
