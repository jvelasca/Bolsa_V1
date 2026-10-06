# Evidencia `v2.88.78-beta` — `AUTO · UI`: **un reloj ausente no es una fase**

**Producto:** `V2.88.78-beta` · **Package:** `2.11.78-beta` · **AsOf:** 2026-10-06. **SIN migración.** **Δ motor = 0.** Contrato HTTP sin cambio. **Sin tag.** El tag anotado `v2.88.76-beta` no se mueve. `v2.88.77-beta` sigue sin tag.

**Padre de producto:** [`v2.88.77`](../v2.88.77/README.md).

## Qué cambia

Solo presentación. El monitor no gana pasos nuevos.

- Sin `nextDecisionAt`, HOME y Sistema no dicen «Esperando nueva señal» ni «Próximo análisis». La frase es «Sin dato todavía».
- Con ese reloj, se copia la hora: «Próxima decisión: HH:mm». No se llama análisis.
- «Última decisión» copia solo `lastDecisionAt`. Un `lastHeartbeatAt` no ocupa ese hueco. Sin sello, la frase entera es «Sin dato todavía».
- «¿Qué está haciendo?» sigue «Sin dato todavía». No aparecen Analizando, Esperando, Preparando, Bloqueado ni Sin actividad como fase inventada.

## Por qué

El bloque bajo las seis preguntas trataba un header cargado y sin próximo reloj como «Esperando nueva señal». El monitor solo rellena `nextDecisionAt` si hay instante durable e intervalo. Si falta, el hueco es desconocido, no una espera. El mismo bloque mezclaba el latido con la decisión.

## Qué no cambia

Núcleo financiero, Alembic (`050_idem_key_not_null`), worker, contratos HTTP, `PortfolioDecision` durable, paso de materialización. El criterio de operación en curso, las cabeceras «Orden pendiente», «Ejecución parcial» y «Precio aplicado», y el banner `SIMULACIÓN — DINERO VIRTUAL` permanecen. El tag `v2.88.76-beta` permanece.

## Cita POST-TAG

No hay tag de `v2.88.78-beta`. No se inventa un veredicto de `Release tag CI`.
