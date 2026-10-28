# Diseño — recolocación de la operativa diaria (`Hoy` y `AUTO`)

> **AsOf:** 2026-10-28 · **Rama:** `ui/auto-hold-provenance-2026-10-28` · **Base auditada:** tag
> `v2.88.171-beta` · **Naturaleza:** **solo presentación**. No cambia motor, decisión, queries,
> contrato HTTP, `@bolsa/shared` ni migraciones.
> **Contrato aplicable:** [UI Contract 5.0](./spec-ui-contract-5-0-2026-10-08.md) (`UI5-01`…`UI5-21`,
> `R-G1`/`R-G2`, `RT-01`…`RT-04`) y [ADR-044](../adr/044-auto-workspace-information-architecture.md).

## 0. Qué se mueve y qué no

| Se mueve (presentación) | NO se mueve |
| --- | --- |
| Orden, agrupación y jerarquía tipográfica de bloques ya existentes | Motor, decisión, umbrales, sizing ni el pin PAPER |
| Dónde se declara un hecho que ya está en el árbol (cabecera vs pie) | Qué hechos existen y cómo se calculan (`@bolsa/shared`) |
| Rótulos de modo (`AUTO`/`SEMI`/`MANUAL`) junto a bloques ya existentes | El selector de modo: sigue **solo** en `demo-book-mode-panel` (`UI5-17`, `UI5-21`) |
| Enlaces cruzados entre superficies ya existentes | Rutas, `?view=`, `cycleId` ni `AUTO_NAV` (`UI5-03`) |

## 1. Inventario actual

### 1.1 `Hoy` — `apps/web/src/features/mesa/mesa-hoy-page.tsx`

| # | Bloque | Origen |
| --- | --- | --- |
| 1 | `h1` «Hoy» + fecha/cuenta + pregunta + `MesaDatosChip` | propio |
| 2 | Acciones: `Actualizar` + menú `Avanzado` (`MesaHoyDetailsMenu`) | propio |
| 3 | Aviso de error al consultar incidentes | propio |
| 4 | Sección de incidentes (banner + frase + enlace a Consola) | `MesaIncidentBanner` |
| 5 | Inbox de cuatro cubos (`requiere_accion`, `proteger`, `posiciones`, `oportunidades`, `no_operar`) | `DailyDeskInbox` |
| 6 | Pie: «Estado: …» + copy explicativo + enlace a Oportunidades | propio |

**Problema de lectura:** el estado operativo —el hecho que decide si hoy se puede operar— vive en el
**pie**, debajo de todo lo demás, mientras la cabecera no lo declara. Es el único hecho de primer
nivel que está en el sitio equivocado (`UI5-01`, `RT-01`).

### 1.2 `AUTO · Resumen` — `apps/web/src/features/auto/auto-home-page.tsx`

| # | Bloque | `data-testid` |
| --- | --- | --- |
| 1 | Estado del motor | `auto-home-state` |
| 2 | Oportunidades (TOP3 compacto) | `auto-home-opportunities` |
| 3 | Decisión de cartera (hueco declarado) | `auto-home-decision` |
| 4 | Por qué no operó (HOLD) | `auto-home-silence` |
| 5 | Operación (contador + tarjetas) | `auto-home-operations` |
| 6 | Dinero (cifras) | `auto-home-account-figures` |
| 7 | `<details>` «Ver actividad» | `auto-home-activity` |

**Problema de lectura:** (3) y (4) son **la misma pregunta** —¿por qué no hay una compra?— partida
en dos bloques consecutivos, y (5) y (6) son **la misma pregunta** —¿qué tengo en marcha?— también
partida. Siete bloques para cinco hechos (`UI5-04`, `RT-03`).

### 1.3 `AUTO · Operar` — `apps/web/src/features/auto/auto-operar-page.tsx`

| # | Bloque |
| --- | --- |
| 1 | Oportunidades (TOP3 completo + copy + enlace a Actividad) |
| 2 | Operaciones (lista o vacío + HOLD + enlace de diagnóstico) |

**Problema de lectura:** el HOLD aparece en **tres** sitios distintos según el estado (bloque de
vacío, línea suelta con operaciones, y otra vez en `Actividad`). El mismo hecho, tres posiciones.

## 2. Wireframe propuesto

### 2.1 `Hoy`

```text
Hoy · 28 oct 2026 · <cuenta> — ¿Qué requiere mi atención?
[Datos al día/día de baja calidad]        [Estado: ENTRADA PERMITIDA] [Actualizar] [Avanzado]

⚠ incidentes (solo si hay; banner + frase + Consola)

🔴 Requiere tu acción      (n)     ← propuestas a firmar, con chip SEMI · SIMULADO
🟠 Proteger                (n)
🟢 Posiciones              (n)
🔵 Oportunidades           (n)
⚪ Sin acción              (n)

[Oportunidades (n) →]  [Posiciones →]
```

- El **estado operativo** sube del pie a la cabecera como chip de información (no interactivo).
- El **pie** se queda solo con los enlaces cruzados; desaparece el copy que repetía lo que ya dicen
  los cubos.
- **No** se añaden pestañas: el mecanismo único de profundidad sigue siendo `Avanzado` (`RT-04`).

### 2.2 `AUTO · Resumen`

```text
Resumen — qué está haciendo AUTO y qué ha ocurrido
[insignia humana: AUTO / activo / …]  · última actividad · próximo análisis

Oportunidades
  TOP3 compacto            → universo completo en Hoy → Oportunidades

Decisión
  ¿Qué ha decidido AUTO?   <decisión de cartera | Sin dato todavía>
  ¿Y si no operó?          <HOLD: motivo humano | no evaluable>   → Ver por qué

Tu operación
  <N operaciones en curso> + tarjetas            → Ver todas en Operar
  Posiciones · Efectivo · P&L · Riesgo

▸ Ver actividad  (D→hoy · Evidencia · Investigación · Detalle técnico · ¿Por qué?)
```

- Se **fusionan** «Decisión de cartera» y «Por qué no operó» en un bloque `Decisión` con dos hechos
  rotulados: es una pregunta, no dos (`R-G2`).
- Se **fusionan** «Operación» y «Dinero» en `Tu operación`: qué hay abierto y con cuánto.
- Los siete bloques bajan a **cinco** sin perder ningún hecho ni ningún `data-testid`.

### 2.3 `AUTO · Operar`

```text
Operar — oportunidades y operaciones

Oportunidades
  TOP3 completo            → Hoy → Oportunidades · Ver toda la actividad

Operaciones
  [HOLD: por qué no se abrió nada]     ← una sola vez, siempre en el mismo sitio
  · <símbolo> · <peldaño> · AUTO · SIMULADO        → Ver operación
  · …
  Diagnóstico avanzado → Consola avanzada
```

- El HOLD se pinta **una sola vez** y **siempre** en el mismo lugar: primera línea de `Operaciones`.
- El bloque de vacío deja de tener su propia copia del HOLD.

## 3. Claridad del modo `SEMI`

Hoy el modo se cambia en un único sitio (`demo-book-mode-panel`) y se informa en un chip del chrome
(`operative-mode-chip`), pero **dentro de `Hoy`** una propuesta pendiente de firma no declara que es
`SEMI`: el usuario ve «Confirmar» sin saber en qué modo está operando.

**Cambio propuesto (información, no acción):** cuando el cubo `requiere_accion` tenga propuestas a
firmar, su cabecera muestra el chip canónico `ModeBadge` con `SEMI · SIMULADO`. El chip **no** cambia
el modo (`UI5-17`, `UI5-21`); el CTA sigue siendo el mismo botón que abre Confirm.

## 4. Matriz de no-cambios

| Elemento | Se conserva |
| --- | --- |
| Rutas y `?view=` | Idénticas (`/mesa`, `?view=posiciones|oportunidades|decisiones|journal`) |
| `AUTO_NAV` y sus cuatro puertas | Idénticas (`UI5-03`) |
| `data-testid` existentes | Todos, para no romper `web` ni E2E |
| Estados de ausencia | `queryCollectionState`, `CollectionAbsence`, `MeasurementValue` intactos (`UI5-14`, `UI5-16`) |
| Nivel 1 sin jerga | `first-level-gate.ts` sigue verde (`R-G1`) |
| Un solo `h1` por pantalla | `heading-order` sigue verde |
| Modo de operativa | Se sigue cambiando **solo** en `demo-book-mode-panel` |

## 5. Riesgos y gates

| Riesgo | Mitigación |
| --- | --- |
| Mover un bloque y duplicar un hecho (`UI5-04`) | Cada hecho se pinta una vez; el test de la superficie lo fija |
| Añadir un segundo mecanismo de profundidad (`RT-04`) | No se añaden pestañas; el disclosure sigue siendo `Avanzado` / «Ver actividad» |
| Romper tests por `data-testid` | Los `data-testid` se conservan; solo cambia su contenedor |
| Introducir jerga en primer nivel (`R-G1`) | `first-level-gate` + revisión de los literales nuevos |
| Cambiar comportamiento por «limpiar» | No se tocan queries, handlers ni payloads; solo JSX de presentación |

## 6. Checkpoint

Este documento es el wireframe a aprobar. La implementación (tareas `ui-hoy-layout`,
`ui-auto-layout`, `ui-semi-clarity`) se ejecuta sobre estas cinco decisiones:

1. Estado operativo de `Hoy` en la cabecera, no en el pie.
2. Ningún mecanismo de profundidad nuevo (`RT-04`).
3. `Hoy`: chip `SEMI · SIMULADO` en el cubo de propuestas, sin selector.
4. `AUTO · Resumen`: siete bloques → cinco, mismo orden de hechos.
5. `AUTO · Operar`: HOLD una sola vez, primera línea de `Operaciones`.
