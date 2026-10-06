# Evidencia `v2.88.77-beta` — `AUTO · UI`: **en curso no es abierta**

**Producto:** `V2.88.77-beta` · **Package:** `2.11.77-beta` · **AsOf:** 2026-10-06. **SIN migración.** **Δ motor = 0.** Contrato HTTP sin cambio. **Sin tag.** El tag anotado `v2.88.76-beta` no se mueve.

**Padre de producto:** [`v2.88.76`](../v2.88.76/README.md).

## Qué cambia

Solo presentación y read-model. El monitor no gana pasos nuevos.

- El azulejo «Operaciones», la lista «¿Qué puedo hacer?» y la tarjeta usan el mismo criterio: orden o fill alcanzados, cierre medido como no cerrado. Una reserva no entra.
- El texto es «1 en curso», «N en curso» o «Sin operaciones en curso». Una orden sin fill ya no aparece junto a «Sin operaciones abiertas».
- `isOperationOpen` sigue siendo el hecho «Precio aplicado». La HOME no lo llama «abierta». Un fill con cantidades iguales sigue en curso, con cabecera «Precio aplicado», y no dice «Posición abierta», «Materializada» ni «Completada».
- La posición de cuenta sigue copiándose del resumen: «N posiciones en la cuenta simulada», o «Sin dato todavía» si el resumen no ha llegado.

## Por qué

En `v2.88.76-beta` la tarjeta contaba una orden pendiente como operación en curso y el azulejo solo contaba el precio aplicado como operación abierta. El usuario podía ver las dos frases a la vez.

## Qué no cambia

Núcleo financiero, Alembic (`050_idem_key_not_null`), worker, contratos HTTP, `PortfolioDecision` durable, paso de materialización. «¿Qué está haciendo?», Decisión y Simulación siguen «Sin dato todavía». Las cabeceras «Orden pendiente», «Ejecución parcial» y «Precio aplicado» no se renombran. El tag `v2.88.76-beta` permanece.

## Cita POST-TAG

No hay tag de `v2.88.77-beta`. No se inventa un veredicto de `Release tag CI`.
