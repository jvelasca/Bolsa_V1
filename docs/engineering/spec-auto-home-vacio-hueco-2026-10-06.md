# Spec — AUTO HOME: distinción «vacío» vs «hueco» en las seis preguntas

> **AsOf:** 2026-10-06 · **Estado:** **DISEÑO CONGELADO** (no es código).
> **Base auditada:** `v2.88.80-beta` → commit `62a1fd300acfb9d39e9b2751c3ca3df0b6638bf0`, más el cierre de los dos P2 de telemetría (medición de `currentActivityAt` + timestamp futuro).
> **Padres:** [spec de operación para usuario básico](./spec-auto-operacion-usuario-basico-2026-10-06.md) §3 · [auditoría de las seis preguntas](./auditoria-ui-auto-home-seis-preguntas-v2.88.80-2026-10-06.md) (hallazgo H2).
> **Naturaleza:** UI / copy / helper puro. **`Δ AUTO decision/execution motor = 0`**. Sin contrato HTTP, sin Alembic.

Este documento congela cómo la HOME distingue, en el copy de primer nivel, el **vacío** («no hay operación en curso») del **hueco** («hay operación pero el hecho no está medido»). Es el cierre del hallazgo H2 de la auditoría de las seis preguntas. No implementa el cambio; lo deja falsable para el slice de implementación.

## 0. Propósito

La spec de usuario básico §3 ya fija los **cuatro estados**: carga, error, vacío y hueco. En el código, la pregunta 5 («¿Qué ha ocurrido realmente?») los distingue correctamente, pero la pregunta 3 («¿Qué activo?») **colapsa vacío y hueco en el mismo rótulo** `Sin dato todavía`. Este documento fija la corrección mínima y su semántica exacta.

## 1. Los cuatro estados (definición normativa)

| Estado | Significado | Rótulo de primer nivel |
| --- | --- | --- |
| Carga | La query aún no ha resuelto | «Cargando estado de AUTO…» (renderizado por la página) |
| Error | La query falló | «No se pudo cargar el estado de AUTO.» |
| **Vacío** | El monitor respondió y **no hay operación en curso** | `Sin operación en curso` |
| **Hueco** | Hay operación en curso pero **el hecho concreto no está medido** | `Sin dato todavía` |

Regla dura: **vacío y hueco no comparten rótulo.** Un `Sin dato todavía` nunca debe significar «no hay operación», y un `Sin operación en curso` nunca debe significar «no lo sé».

## 2. Estado actual (post-v2.88.80 + P2)

En [auto-basic-home.ts](../../apps/web/src/features/auto/auto-basic-home.ts), `buildAutoBasicHome`:

- `currentOperations` filtra `cycles` con `isOperationInCourse` (exige `closed === false`, medición `COMPLETE` y paso `ORDER`/`FILL` alcanzado). Un ciclo cerrado o no medido queda **fuera**.
- **P5** (`happenedLabel`) ya distingue: `Sin operación en curso` (vacío) vs `Sin dato todavía` (hueco, vía `operationHappenedLabel`).
- **P3** (`assetLabel`) no distingue: sus dos ramas de fallo devuelven el mismo `Sin dato todavía`.

```ts
const assetLabel =
    currentOperations.length === 0
      ? AUTO_HOME_NO_DATA_LABEL            // ← vacío, mal rotulado como hueco
      : symbols.every((symbol) => symbol !== AUTO_HOME_NO_DATA_LABEL)
        ? [...new Set(symbols)].join(", ")
        : AUTO_HOME_NO_DATA_LABEL;         // ← hueco real (op en curso sin símbolo)
```

El defecto es exactamente la primera rama: `currentOperations.length === 0` es **vacío**, no hueco.

## 3. Diseño propuesto

### 3.1 Cambio mínimo (una rama)

```ts
const assetLabel =
    currentOperations.length === 0
      ? AUTO_NO_CURRENT_OPERATION         // vacío, alineado con P5
      : symbols.every((symbol) => symbol !== AUTO_HOME_NO_DATA_LABEL)
        ? [...new Set(symbols)].join(", ")
        : AUTO_HOME_NO_DATA_LABEL;        // hueco real
```

Sólo cambia el rótulo de la primera rama: `AUTO_HOME_NO_DATA_LABEL` → `AUTO_NO_CURRENT_OPERATION`. No se toca la semántica de filtrado, no se toca el motor, no se añade campo al DTO.

### 3.2 Semántica resultante de P3 («¿Qué activo?»)

| Situación | Rótulo | Estado |
| --- | --- | --- |
| Operación en curso con símbolo | `AAPL` (o `AAPL, MSFT`) | dato |
| Operación en curso sin símbolo | `Sin dato todavía` | hueco |
| Sin operación en curso | `Sin operación en curso` | vacío |
| Carga / error | `Sin dato todavía` (la página pinta su propio estado) | carga / error |

### 3.3 Por qué `Sin operación en curso` y no una frase nueva

- Coincide con el wireframe de la spec §3, que ya contempla `Sin operación` en esa zona.
- Mantiene **una sola fuente de verdad** para el vacío (`AUTO_NO_CURRENT_OPERATION`), compartida por P3 y P5.
- No añade una tercera constante que habría que mantener sincronizada.

## 4. Límite explícito (fuera de este diseño)

Hay un matiz más profundo que **no** se cierra aquí, y que afecta a P3 y P5 por igual: un ciclo con `closed` no medido (p. ej. `closed === null`) queda fuera de `currentOperations`, de modo que «hay ciclos pero no se puede clasificar si están en curso» se presenta como **vacío** («Sin operación en curso») en lugar de **hueco** («Sin dato todavía»).

Ese caso es coherente con la spec («evidencia incompleta no dice operación terminada», y tampoco afirma que esté en curso), pero si se quisiera distinguir habría que introducir un tercer hecho «ciclos presentes pero no clasificables» en `buildAutoBasicHome`. Queda como P3 baja de seguimiento, **no** se mezcla con este cambio para no ampliar el alcance.

## 5. Tests afectados (al implementar)

En [auto-basic-home.test.ts](../../apps/web/src/features/auto/auto-basic-home.test.ts):

1. El test «sin ciclo en curso distingue el vacío del hueco» (caso `cycles: []`) pasa de
   `expect(home.assetLabel).toBe(AUTO_HOME_NO_DATA_LABEL)` a
   `expect(home.assetLabel).toBe(AUTO_NO_CURRENT_OPERATION)`.
2. Añadir un caso de **hueco real**: un ciclo en curso (`isOperationInCourse` true) **sin** `instrumentId`, y verificar
   `expect(home.assetLabel).toBe(AUTO_HOME_NO_DATA_LABEL)`.
3. Añadir un caso de **vacío**: `cycles: []` y verificar `assetLabel === AUTO_NO_CURRENT_OPERATION` y `happenedLabel === AUTO_NO_CURRENT_OPERATION` (consistencia P3/P5).

En [auto-home-page.test.tsx](../../apps/web/src/features/auto/auto-home-page.test.tsx): verificar que ningún test afirme `auto-home-q-asset` con «Sin dato todavía» cuando no hay operación en curso (hoy no hay ninguno, pero es la guarda).

## 6. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | P3 con `cycles: []` dice «Sin operación en curso», no «Sin dato todavía». | Que `assetLabel` devuelva `AUTO_HOME_NO_DATA_LABEL` con lista vacía. |
| 2 | P3 con operación en curso sin símbolo dice «Sin dato todavía». | Que `assetLabel` devuelva vacío para un símbolo ausente. |
| 3 | P3 y P5 comparten el mismo rótulo de vacío. | Que cada una use una constante distinta para el vacío. |
| 4 | Δ motor = 0. | Que el diff toque el worker, umbrales, Alembic o `openapi.json`. |

## 7. Alcance de implementación

Un solo cambio de una línea en `assetLabel`, más la actualización/añadido de los tests de §5. Sin tocar la tarjeta (`auto-operation-card.ts`, que es por-ciclo y nunca llega al caso vacío), sin tocar `isOperationInCourse`, sin tocar el DTO.
