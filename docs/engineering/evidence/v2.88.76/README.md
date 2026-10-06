# Evidencia `v2.88.76-beta` — `AUTO · UI`: **la tarjeta muestra las seis ranuras**

**Producto:** `V2.88.76-beta` · **Package:** `2.11.76-beta` · **AsOf:** 2026-10-06. **SIN migración.** **Δ motor = 0.** Contrato HTTP sin cambio. **Tag anotado** `v2.88.76-beta` (incluye el corte local `v2.88.75-beta`, que no tiene tag propio).

**Padre de producto:** [`v2.88.75`](../v2.88.75/README.md). **Último tag anterior:** `v2.88.74-beta`.

## Qué cambia

Solo presentación y read-model. El monitor no gana pasos nuevos.

- Cada operación en curso de `/auto` tiene una tarjeta. Las ranuras Decisión, Orden, Ejecución, Simulación, Posición y Dinero se pintan siempre.
- Decisión es «Sin dato todavía»: no hay `PortfolioDecision` durable. Simulación es «Sin dato todavía»: no hay traza de apply. Un fill con cantidades iguales es «Precio aplicado» y `Hecho` en Ejecución; no dice «Materializada» ni «Completada».
- Posición y dinero de la tarjeta, cuando el resumen de cuenta llega, llevan el rótulo de cuenta («en la cuenta simulada»). No se leen como posición abierta por el fill.
- Bajo las seis preguntas, la HOME copia posición, resultado, efectivo simulado y riesgo. Sin resumen, las tres primeras son «Sin dato todavía». El riesgo sigue saliendo de la integridad ya medida.
- Oportunidades, DÍA-D, evidencia e investigación quedan detrás de «Ver actividad». «Ver detalles» abre `/auto-monitor?mode=current&cycle=…`.

## Por qué

`v2.88.75-beta` respondía las seis preguntas y dejaba la tarjeta fuera. Este corte muestra la escalera sin inventar los peldaños que el monitor no trae.

## Qué no cambia

Núcleo financiero, Alembic (`050_idem_key_not_null`), worker, contratos HTTP, `PortfolioDecision` durable, paso de materialización. La segunda línea `XTB conectado: no implica ejecución real` no se pinta. `paperOrderStatusCopy` («Orden enviada — pendiente de ack») y «T1 ejecutado» siguen en la cartera que AUTO compone. El sello oficial sigue siendo `v2.88.74-beta`.

## Cita POST-TAG

Pendiente del `Release tag CI` del tag anotado. No se inventa un veredicto.
