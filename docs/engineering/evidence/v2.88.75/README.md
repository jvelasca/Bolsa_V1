# Evidencia `v2.88.75-beta` — `AUTO · UI`: **el dinero de AUTO es simulado y la HOME responde seis preguntas**

**Producto:** `V2.88.75-beta` · **Package:** `2.11.75-beta` · **AsOf:** 2026-10-06. **SIN migración.** **Δ motor = 0.** Contrato HTTP sin cambio. **Sin tag propio:** este corte queda dentro de [`v2.88.76-beta`](../v2.88.76/README.md).

**Padre:** [`v2.88.74`](../v2.88.74/README.md).

## Qué cambia

Solo presentación y read-model. El monitor no gana pasos nuevos.

- La ejecución AUTO declara siempre `DINERO VIRTUAL` · `AUTO DEMO` y `No envía órdenes a XTB`. Una cuenta `live` no cambia ese banner a `DINERO REAL`. Se muestra aparte como `Cuenta conectada: XTB LIVE`. Una cuenta ausente deja el banner en simulación y declara la cuenta `NO MEDIDO`.
- La tira de `/auto/*` abre con `SIMULACIÓN — DINERO VIRTUAL`.
- `header.state` se traduce solo para `RUNNING`, `PAUSED`, `BLOCKED`, `DEGRADED` y `REQUIRES_ATTENTION`. Cualquier otro token, incluidos `UNKNOWN`, `WAITING` y `STOPPED`, es «Sin dato todavía». HOME y Sistema usan la misma frase. El valor crudo sigue en el detalle técnico.
- `/auto` muestra las seis preguntas. «¿Qué está haciendo?» y «¿Qué ha decidido?» son «Sin dato todavía». «¿Qué ha ocurrido realmente?» es «Sin operación en curso» si no hay orden o fill en curso. Un fill sin cantidad pedida y aplicada medidas no se llama «Precio aplicado». Varias operaciones en curso no se colapsan en la primera.

## Por qué

En `v2.88.74-beta` la HOME decía dinero virtual y la tira podía decir `DINERO REAL` si la cuenta activa era `live`. Además, cualquier estado conocido del monitor se leía como «Funcionando correctamente». Este corte separa la cuenta del modo AUTO y deja de afirmar que un estado conocido es un funcionamiento correcto. La HOME empieza a responder las seis preguntas de la spec sin inventar los hechos que no existen.

## Qué no cambia

Núcleo financiero, Alembic (`050_idem_key_not_null`), worker, contratos HTTP, `PortfolioDecision` durable. No hay paso de materialización, así que no se dice «Materializada» ni «Completada». La tarjeta de operación no está. Los bloques anteriores de la HOME (baldosas, oportunidades, DÍA-D) siguen debajo de las seis preguntas. `paperOrderStatusCopy` («Orden enviada — pendiente de ack») y «T1 ejecutado» siguen en la cartera que AUTO compone. La segunda línea `XTB conectado: no implica ejecución real` no se pinta: el shell de AUTO no tiene un hecho medido de bridge.

## Cita POST-TAG

No hay tag de `v2.88.75-beta`. La auditoría en GitHub es la de `v2.88.76-beta`.
