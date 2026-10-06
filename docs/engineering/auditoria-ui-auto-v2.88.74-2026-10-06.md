# Auditoría UI AUTO — tag `v2.88.74-beta`

> **AsOf:** 2026-10-06 · **Estado:** auditoría del árbol sellado (no es un segundo producto).
> **Base:** tag `v2.88.74-beta` (el commit de ventana que pinnea el funcional de este sello). Sustituye, como línea base, la deriva local descrita en la [auditoría de `v2.88.73`](./auditoria-ui-auto-pantalla-2026-10-06.md).
> **Diseño que aún no está en pantalla:** [spec de seis preguntas y tarjeta](./spec-auto-operacion-usuario-basico-2026-10-06.md).
> **`Δ motor = 0`.** Sin Alembic nuevo. Sin contrato HTTP nuevo.

## Pregunta

En el tag publicado, ¿el primer nivel sigue presentando un fill como posición o como dinero, y responde ya las seis preguntas del usuario básico?

## Lo que este tag cierra respecto a `v2.88.73`

Comprobado en el árbol del sello (mismos ficheros que lleva el tag):

| Afirmación de `v2.88.73` | En `v2.88.74` |
| --- | --- |
| «Orden enviada · Hecho» | «Orden anotada» ([auto-story-plain-labels.ts](../../apps/web/src/features/auto/auto-story-plain-labels.ts)) |
| «Operación ejecutada · Hecho» | «Precio aplicado» |
| «Posición abierta · Hecho» copiada de `FILL` | `POSITION` plegada en `FILL`; la nota dice que el precio no afirma posición ni dinero ([auto-operation-story.ts](../../packages/shared/src/cognitive/auto-operation-story.ts)) |
| Estado «Abierto» para reserva, orden y fill | «Apartada» / «Orden anotada» / «Precio aplicado» / «Cerrada» / «Sin dato todavía» ([auto-operational-monitor.ts](../../packages/shared/src/cognitive/auto-operational-monitor.ts)) |
| Contador de abiertas con `closed === false` | Solo ciclos en «Precio aplicado» ([auto-home-summary.ts](../../apps/web/src/features/auto/auto-home-summary.ts)) |
| Sistema: «qué hizo el broker» | «qué registró la simulación» ([auto-copy.ts](../../apps/web/src/features/auto/auto-copy.ts)) |

## Lo que el tag todavía no responde

| # | Pregunta | En el tag |
| --- | --- | --- |
| 1 | ¿AUTO está funcionando? | «Activo» o «Sin dato todavía», y «Funcionando correctamente» si el estado crudo es conocido. No hay Funcionando / Esperando / Detenido. |
| 2 | ¿Qué está haciendo? | Hora de actividad y «Próximo análisis» o «Esperando nueva señal». No hay Analizando / Comprando / Vendiendo. |
| 3 | ¿Qué activo? | En la identidad de cada ciclo, no en la ficha de la HOME. |
| 4 | ¿Qué ha decidido? | «Decisión de cartera · Sin dato todavía». Sigue sin traza de cartera. Correcto no inventarla. |
| 5 | ¿Qué ha ocurrido realmente? | Orden anotada o precio aplicado. No hay ranura de parcial ni de materialización. |
| 6 | ¿Qué dinero? | `DINERO VIRTUAL · AUTO DEMO` si la cuenta no es `live`. El banner `SIMULACIÓN — DINERO VIRTUAL` no está. Si la cuenta es `live`, la tira sigue pudiendo decir `DINERO REAL` dentro de AUTO. |

Siguen en la cartera que AUTO monta: «Orden enviada — pendiente de ack» ([paper-order.ts](../../packages/shared/src/cognitive/paper-order.ts)) y «T1 ejecutado» ([lifecycle-stage-label.ts](../../packages/shared/src/cognitive/lifecycle-stage-label.ts)).

La tarjeta de operación de la spec no está implementada. La HOME no tiene las seis casillas.

## Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | El tag dice «Orden anotada» y «Precio aplicado», y pliega `POSITION` en `FILL`. | Que `git grep` del tag encuentre «Orden enviada» o «Operación ejecutada» en `auto-story-plain-labels.ts`, o que `POSITION` no tenga `foldedInto: "FILL"`. |
| 2 | El contador de la HOME solo incluye «Precio aplicado». | Que `isOperationOpen` del tag vuelva a usar `closed === false`. |
| 3 | La HOME no nombra activo ni lado. | Que `buildAutoHomeSummary` del tag exponga símbolo o comprar/vender. |
| 4 | Una cuenta `live` puede pintar `DINERO REAL` en AUTO. | Que `buildAutoReality` del tag ignore `accountType === "live"`. |
