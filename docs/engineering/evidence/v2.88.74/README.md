# Evidencia `v2.88.74-beta` — `AUTO · UI`: **el primer nivel no afirma posición ni dinero**

**Producto:** `V2.88.74-beta` · **Package:** `2.11.74-beta` · **AsOf:** 2026-10-06. **SIN migración.** **Δ motor = 0.** Contrato HTTP sin cambio.

**Padre:** [`v2.88.73`](../v2.88.73/README.md).

## Qué cambia

Solo presentación y read-model. El monitor no gana pasos nuevos.

- `ORDER` en primer nivel: «Orden anotada». `FILL`: «Precio aplicado».
- `POSITION` se pliega en `FILL` mientras no exista un paso `POSITION` propio. La nota del precio dice que no afirma la posición ni el dinero de la cuenta.
- El estado visible del ciclo sale de los pasos ya presentes: medición incompleta → «Sin dato todavía»; cierre medido → «Cerrada»; `FILL` alcanzado → «Precio aplicado»; `ORDER` sin fill → «Orden anotada»; si no → «Apartada».
- El contador de la HOME solo suma ciclos en «Precio aplicado».
- Sistema y la operación dejan de decir que AUTO usó un broker.
- Quedan en el sello, como diseño y no como pantallas: la [auditoría de `v2.88.73`](../../auditoria-ui-auto-pantalla-2026-10-06.md), la [spec de seis preguntas y tarjeta](../../spec-auto-operacion-usuario-basico-2026-10-06.md) y la [auditoría de este tag](../../auditoria-ui-auto-v2.88.74-2026-10-06.md).

## Por qué

En `v2.88.73-beta` un fill se leía como «Operación ejecutada» y «Posición abierta», y el contador de abiertas incluía reservas. Eso confunde intención con hecho. Este sello corta esas frases. No implementa la tarjeta ni el banner `SIMULACIÓN — DINERO VIRTUAL`: eso sigue en la spec.

## Qué no cambia

Núcleo financiero, Alembic (`050_idem_key_not_null`), worker, contratos HTTP, `PortfolioDecision` durable. `paperOrderStatusCopy` («Orden enviada — pendiente de ack») y «T1 ejecutado» siguen en la cartera que AUTO compone. Una cuenta `live` sigue pudiendo pintar `DINERO REAL` en la tira de AUTO.

## Cita POST-TAG

Pendiente del `Release tag CI` del tag anotado. No se inventa un veredicto.
