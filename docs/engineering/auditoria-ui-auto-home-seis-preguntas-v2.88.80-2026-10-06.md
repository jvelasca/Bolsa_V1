# Auditoría UI AUTO — las seis preguntas de la HOME contra escenarios reales (`v2.88.80-beta`)

> **AsOf:** 2026-10-06 · **Estado:** **AUDITORÍA EN SOLO LECTURA** (no es código, no es un sello de release).
> **Base auditada:** tag `v2.88.80-beta` → commit `62a1fd300acfb9d39e9b2751c3ca3df0b6638bf0`, más el cierre de los dos P2 de robustez de telemetría (medición de `currentActivityAt` y timestamp futuro) aplicado sobre el árbol de trabajo.
> **Padres:** [auditoría pantalla por pantalla](./auditoria-ui-auto-pantalla-2026-10-06.md) · [spec de operación para usuario básico](./spec-auto-operacion-usuario-basico-2026-10-06.md) · [spec 3.0](./spec-auto-ui-refactor-3-0-2026-10-06.md).
> **Naturaleza:** UI / producto. **`Δ AUTO decision/execution motor = 0`**. Sin contrato HTTP nuevo (el consumo de `currentActivityAtMeasurement` es aditivo), sin Alembic, sin tocar el worker.

## 0. Pregunta

¿Las seis preguntas de la HOME de `/auto` se responden de forma inequívoca en una situación AUTO real — ausencia de datos, pausa, bloqueo, orden pendiente, fill parcial y operación cerrada — sin confundir intención con hecho, sin saltarse peldaños de la escalera y sin declarar un hueco como si fuera un dato?

Esta auditoría cierra el tramo que la [auditoría pantalla por pantalla](./auditoria-ui-auto-pantalla-2026-10-06.md) dejó abierto: aquella evaluó el tag `v2.88.73` contra una rúbrica estática; esta evalúa el tag `v2.88.80` contra **estados concretos del motor**, ya con los P1/P2/P3 de telemetría cerrados.

## 1. Línea base y deriva local

La línea base es el tag `v2.88.80-beta` (`62a1fd3`). Sobre el árbol de trabajo se aplica una única deriva **UI-only**, que es la que se audita junto al tag:

| Superficie | En el tag `v2.88.80` | Deriva local (auditada) |
| --- | --- | --- |
| Frescura de la actividad | `isActivityStale(activityAt, asOf)` | Añade guard fail-closed de `currentActivityAtMeasurement` y de timestamp futuro (`at > as`) |
| Consumo del instante | `currentActivityAtMeasurement` expuesto en el DTO pero no usado por la UI | La HOME y Sistema lo exigen para afirmar actividad |

Esa deriva es exactamente el cierre de los dos P2 residuales señalados en la auditoría de la versión. No toca el motor.

## 2. Rúbrica: las seis preguntas y su fuente de hecho

Cada respuesta de la HOME se traza a un helper puro (no a la página). La página ([auto-home-page.tsx](../../apps/web/src/features/auto/auto-home-page.tsx)) sólo compone; la verdad vive en [auto-basic-home.ts](../../apps/web/src/features/auto/auto-basic-home.ts) y [auto-home-summary.ts](../../apps/web/src/features/auto/auto-home-summary.ts).

| # | Pregunta | Helper | Fuente de hecho |
| --- | --- | --- | --- |
| 1 | ¿AUTO está funcionando? | `engineStateLabel(state)` | `header.state` (conjunto cerrado del motor) |
| 2 | ¿Qué está haciendo? | `isActivityStale(...)` + `activityLabel(...)` | `currentActivity` + `currentActivityMeasurement` + `currentActivityAt` + `currentActivityAtMeasurement` + `asOf` |
| 3 | ¿Qué activo? | `buildAutoBasicHome.assetLabel` | `instrumentId` de los ciclos en curso |
| 4 | ¿Qué ha decidido? | `buildAutoBasicHome.decisionLabel` | fijo `Sin dato todavía` (`PortfolioDecision` durable ausente) |
| 5 | ¿Qué ha ocurrido realmente? | `buildAutoBasicHome.happenedLabel` + `operationHappenedLabel` | pasos `ORDER`/`FILL` + `closed` + cantidades pedida/aplicada |
| 6 | ¿Qué dinero utiliza? | `buildAutoBasicHome.moneyLabel` | fijo `SIMULACIÓN — DINERO VIRTUAL` |

Regla de copia heredada: el contador de «en curso» (`isOperationInCourse`) exige `closed === false`, medición de cierre `COMPLETE` y paso `ORDER` o `FILL` alcanzado. Una reserva no entra. Un ciclo cerrado no entra.

## 3. Matriz de escenarios

Seis escenarios reales contra las seis preguntas. La respuesta es la salida literal del helper con el estado dado.

| Escenario | P1 ¿Funcionando? | P2 ¿Qué hace? | P3 ¿Qué activo? | P4 ¿Qué decidió? | P5 ¿Qué ocurrió? | P6 ¿Qué dinero? |
| --- | --- | --- | --- | --- | --- | --- |
| (a) Sin datos (`header` ausente) | Sin dato todavía | Sin dato todavía | Sin dato todavía | Sin dato todavía | Sin dato todavía | SIMULACIÓN — DINERO VIRTUAL |
| (b) Pausa (`PAUSED`, sin actividad) | Detenido | Sin dato todavía | Sin dato todavía | Sin dato todavía | Sin operación en curso | SIMULACIÓN — DINERO VIRTUAL |
| (c) Bloqueo (`BLOCKED` + `currentActivity=BLOCKED` fresco) | Bloqueado | Bloqueado | Sin dato todavía | Sin dato todavía | Sin operación en curso | SIMULACIÓN — DINERO VIRTUAL |
| (d) Orden pendiente (`ORDER reached`, `FILL pending`) | Funcionando | (según tick) | `AAPL` | Sin dato todavía | Orden pendiente | SIMULACIÓN — DINERO VIRTUAL |
| (e) Fill parcial (`applied < requested`) | Funcionando | (según tick) | `AAPL` | Sin dato todavía | Ejecución parcial | SIMULACIÓN — DINERO VIRTUAL |
| (f) Operación cerrada (`closed=true`, `COMPLETE`) | Funcionando | (según tick) | Sin dato todavía | Sin dato todavía | Sin operación en curso | SIMULACIÓN — DINERO VIRTUAL |

Notas sobre la matriz:

- **P1** distingue `Funcionando` / `Detenido` / `Bloqueado` sin colapsar a un único «Activo». Tras el P3 de `v2.88.80`, `BLOCKED` es un hecho propio y ya no convive con `RUNNING`: la casilla es inequívoca.
- **P2** nunca deriva de `RUNNING`. Solo afirma con `currentActivity` medido `COMPLETE`, instante medido `COMPLETE`, sello legible, no futuro y dentro de 300 s. En (b)/(d)/(e)/(f) sin telemetría fresca dice «Sin dato todavía», no «Analizando» ni «Funcionando».
- **P4** es honesta y constante: no existe `PortfolioDecision` durable, así que siempre «Sin dato todavía». No inventa «Comprar»/«Vender».
- **P6** es invariante en los seis escenarios, incluso sin cuenta: el banner de simulación no depende del tipo de cuenta.

## 4. Hallazgos

| # | Severidad | Hallazgo | Veredicto |
| --- | --- | --- | --- |
| H1 | P3 | **P5 en operación cerrada.** Un ciclo `closed=true` queda fuera de `isOperationInCourse`, de modo que «¿Qué ha ocurrido realmente?» responde «Sin operación en curso» en lugar de reflejar el cierre medido («Cerrada»). | Ambiguo para el usuario básico, pero **dentro de la spec** (§3: «Sin ciclo en curso → Sin operación en curso»). La HOME sólo habla de lo *en curso*; lo cerrado vive detrás de «Ver actividad»/Análisis. Documentar, no bloquear. |
| H2 | P3 | **P3 en ausencia/cierre.** «¿Qué activo?» cae a «Sin dato todavía» (hueco) mientras P5 dice «Sin operación en curso» (vacío). Dos estados distintos, ambos honestos, pero un usuario no experto puede leer el hueco de P3 como «no se sabe el activo» cuando en realidad no hay operación. | Aceptable; distinguir en copy sería una mejora, no un fallo. |
| H3 | OK | **P1/P2 en `BLOCKED`.** Con kill activo, `state=BLOCKED` y `currentActivity=BLOCKED` producen «Bloqueado» en ambas casillas, sin la incoherencia `RUNNING + BLOCKED` de `v2.88.79`. | Cerrado por el P3. |
| H4 | OK | **Frescura.** Los dos P2 de la deriva (medición del instante + timestamp futuro) están cerrados y cubiertos por tests unitarios y de componente. | Cerrado. |

### 4.1 Hipótesis confirmadas

- La hipótesis de P5 en operación cerrada se **confirma**: `happenedLabel` devuelve «Sin operación en curso» (H1).
- La hipótesis de P1 en `BLOCKED` se **confirma** como correcta: no colisiona con `RUNNING` (H3).
- La hipótesis de P3 en ausencia/cierre se **confirma**: es un hueco distinto del vacío de P5 (H2).

## 5. Afirmaciones prohibidas (verificadas como ausentes)

1. «Posición abierta · Hecho» copiado de `FILL` — **no aparece** (la ranura Simulación queda «Sin dato todavía»).
2. «Operación ejecutada» para un precio y una cantidad — **no aparece** («Precio aplicado» / «Ejecución parcial»).
3. «Orden enviada» para un registro que no sale a XTB — **no aparece** («Orden pendiente»).
4. «N abiertas» contando reservas y órdenes sin fill — **no aparece** («N en curso», solo fill/orden alcanzados).
5. `DINERO REAL` dentro de AUTO — **no aparece** (banner `SIMULACIÓN — DINERO VIRTUAL` permanente).
6. «Analizando» derivado de `RUNNING` — **no aparece** (P2 exige actividad medida y fresca).

## 6. Falsabilidad de esta auditoría

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | En (f) operación cerrada, P5 dice «Sin operación en curso», no «Cerrada». | Que `buildAutoBasicHome` incluya ciclos cerrados en `currentOperations`. |
| 2 | P2 nunca deriva de `RUNNING`. | Que `doingLabel` afirme una fase sin `currentActivity` medido `COMPLETE`. |
| 3 | P2 exige `currentActivityAtMeasurement === COMPLETE`. | Que `isActivityStale` ignore la medición del instante. |
| 4 | Un timestamp futuro no se afirma. | Que `isActivityStale` devuelva `false` con `activityAt > asOf`. |
| 5 | P4 permanece «Sin dato todavía». | Que `decisionLabel` derive de `SELECTION`/TOP-N. |
| 6 | P6 es invariante (banner de simulación). | Que `moneyLabel` dependa de `header` o del tipo de cuenta. |
| 7 | `Δ motor = 0`. | Que el diff toque el worker, umbrales, Alembic o `openapi.json`. |

## 7. Conclusión

Las seis preguntas de la HOME son **inequívocas** para los seis escenarios, con dos matices honestos (H1 y H2) que no son fallos sino decisiones de producto ya fijadas en la spec: la HOME habla de lo *en curso*, no de lo *cerrado*, y distingue hueco («Sin dato todavía») de vacío («Sin operación en curso»).

El siguiente salto de calidad no está en esta HOME sino en los dos límites ya declarados por la spec: (1) la **decisión de cartera durable** (`PortfolioDecision`) para que P4 deje de ser un hueco permanente, y (2) la **materialización** (`apply`) para que la ranura Simulación de la tarjeta deje de ser «Sin dato todavía». Ambos son de backend/spine, fuera del alcance de esta auditoría de UI.
