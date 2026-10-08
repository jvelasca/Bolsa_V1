# Auditoría UI global — toda la aplicación sobre `v2.88.87-beta`

> **AsOf:** 2026-10-08 · **Estado:** **AUDITORÍA EN SOLO LECTURA** (no es código, no es un sello).
> **Base:** tag `v2.88.87-beta` → commit `6b70da1f` (objeto anotado `be7af907`), `Δ motor = 0`, contrato HTTP sin cambio, head Alembic `052_top3_opportunities`.
> **Padres:** [UI Contract 5.0](./spec-ui-contract-5-0-2026-10-08.md) · [spec AUTO UI definitiva](./spec-auto-ui-definitiva-2026-10-07.md) · [auditoría UI AUTO pantalla a pantalla](./auditoria-ui-auto-pantalla-2026-10-06.md) · [modelo semántico 1.0](./spec-auto-ui-semantic-model-1-2026-10-05.md) · [ADR-040](../adr/040-user-information-architecture.md) · [ADR-044](../adr/044-auto-workspace-information-architecture.md) · [domain-language](../domain-language.md).
> **Naturaleza:** UI / producto / semántica. **No** se audita motor, backend ni contrato HTTP. **No** se toca código en este slice.

---

## 0. Pregunta

`v2.88.87-beta` cerró la primera etapa de simplificación de AUTO (estado humano, centro de actividad, «¿Por qué?», ficha universal, TOP3). Con AUTO ya coherente por dentro, la pregunta cambia:

> ¿Se comporta **toda la aplicación** como **una sola aplicación**, con un único lenguaje operativo y una única jerarquía, o seguimos teniendo una aplicación excelente (AUTO) dentro de un conjunto heterogéneo?

La hipótesis de trabajo es que AUTO ya no es el problema; el problema es la **coherencia entre superficies** (HOME/Hoy, Mercado, Cartera, AUTO, Asesor, Laboratorio) y la **densidad** de la primera capa incluso dentro de AUTO.

---

## 1. Línea base y alcance

### 1.1 Superficies auditadas

| Grupo | Superficies | Rutas |
| --- | --- | --- |
| Barra administrativa | `AdminRail` | (global) |
| L1 de producto | Hoy · Mercado · Cartera · Asesor · Laboratorio | `/mesa`, `/trading`, `/history`+`/mesa?view=posiciones`, `/research`, `/backtests` |
| Espacio AUTO | Resumen · Operar · Actividad · Cartera · Riesgo · Análisis · Sistema | `/auto`, `/auto/operar`, `/auto/actividad`, `/auto/cartera`, `/auto/riesgo`, `/auto/analisis`, `/auto/sistema` |
| Detalle | Ficha universal de operación · Monitor experto | `/auto/operar/operacion/:cycleId`, `/auto-monitor` |
| Diagnóstico | Consola avanzada | `/operational-console` |

Fuente de labels/rutas: [`daily-nav.ts`](../../apps/web/src/features/confirm/daily-nav.ts) (L1) y [`auto-nav.ts`](../../apps/web/src/features/auto/auto-nav.ts) (AUTO). Sub-navegación montada por [`auto-workspace-layout.tsx`](../../apps/web/src/components/layout/auto-workspace-layout.tsx); grafo de rutas en [`app.tsx`](../../apps/web/src/app.tsx).

### 1.2 Fuera de alcance (declarado)

- Motor de decisión/ejecución, worker, umbrales, `TOP_N`, replay.
- Contrato HTTP / OpenAPI / `contract:gen`.
- Migraciones Alembic.
- Auditoría de accesibilidad `axe` en vivo (ya cubierta en `v2.88.54`/`v2.88.62`; se cita, no se reejecuta).
- Rendimiento.

---

## 2. Rúbrica

Diez dimensiones. Cada hallazgo se clasifica por severidad `P0` (bloquea la coherencia de producto) / `P1` (degrada la experiencia) / `P2` (pulido semántico).

| # | Dimensión | Qué se busca |
| --- | --- | --- |
| D1 | Duplicidades de información | El mismo hecho con el mismo peso en dos sitios |
| D2 | Lenguaje técnico en primer nivel | Jerga de ingeniería visible al usuario básico |
| D3 | Estados contradictorios entre pantallas | Dos superficies afirman cosas distintas del mismo hecho |
| D4 | Botones que no dicen qué va a ocurrir | Acción ambigua o etiqueta que promete de más |
| D5 | Diferencias AUTO / SEMI / MANUAL | El modo no es evidente o se deduce |
| D6 | Vocabulario de operación | "Ejecutada", "abierta", "operación", "posición", "orden" mal usados |
| D7 | Información importante escondida | El dato clave exige conocer la arquitectura |
| D8 | Información secundaria sobredimensionada | El detalle ocupa el primer nivel |
| D9 | Navegación que exige conocer la arquitectura | Hay que saber que existe "Sistema" para responder "¿funciona?" |
| D10 | Coherencia HOME → AUTO → Oportunidades → Operaciones → Cartera → Análisis | El recorrido mental es continuo y sin saltos |

---

## 3. Matriz pantalla a pantalla

### 3.1 `AdminRail`

Hoy mezcla, en una sola lista sin agrupar, ítems de naturaleza distinta: `Overview`, `Cuentas`, `Perfiles`, `Estadísticas` (stub), `AUTO`, `Fiscal`, `Consola avanzada`. No hay separación visual entre **producto**, **administración** y **diagnóstico**; `Perfiles`/`Estadísticas` son acciones, no rutas; `AUTO` es un espacio de producto; `Consola avanzada` es diagnóstico. D2, D9.

### 3.2 L1 de producto

| Superficie | Pregunta que responde | Observación |
| --- | --- | --- |
| Hoy `/mesa` | ¿Qué hago hoy? | Motor de la L1 (ADR-040); resumen + vistas `posiciones`/`oportunidades`/`decisiones`/`journal` tras «Avanzado» |
| Mercado `/trading` | ¿Qué ocurre? | Terminal denso por diseño; jerga de ejecución en primer nivel en algunos paneles |
| Cartera | ¿Qué tengo? | Navega a `/mesa?view=posiciones` (Posiciones/Órdenes/Riesgo) + `/history` (Historial): una sola cartera, pero la topología mezcla vistas de Hoy con una ruta propia |
| Asesor `/research` | ¿Por qué ocurre? | Dictamen/ledger; lenguaje científico |
| Laboratorio `/backtests` | ¿Qué aprendemos? | Universo LAB; no mezcla con TRADING por ADR-019 |

### 3.3 Espacio AUTO (7 secciones)

`AUTO_NAV.items` declara las siete puertas con el mismo rango visual en la sub-navegación: `Resumen`, `Operar`, `Actividad`, `Cartera`, `Riesgo`, `Análisis`, `Sistema`. D9: el usuario básico no debería saber que existe un subsistema llamado "Sistema".

- **Resumen** [`auto-home-page.tsx`](../../apps/web/src/features/auto/auto-home-page.tsx): encadena badge de estado → seis preguntas → cifras de cuenta → tarjetas de operación → tres tiles (`AUTO`/`Operaciones`/`Riesgo`) → `¿Qué está haciendo AUTO?` → `¿Qué puedo hacer?` (que contiene el TOP3 + operaciones en curso + «Ver todas las operaciones») → `Ver actividad`. Responde varias veces lo mismo (D1: estado del motor en el badge, en las seis preguntas y en el tile `AUTO`; operaciones en curso en tarjetas, en `¿Qué puedo hacer?` y en el tile `Operaciones`); sin jerarquía de cockpit (D8).
- **Operar** [`auto-operar-page.tsx`](../../apps/web/src/features/auto/auto-operar-page.tsx): monta el TOP3 completo **y** explica alrededor del dato («El ranking completo y su explicación viven en la Mesa…», «Ranking ≠ orden…», dos enlaces). D8: demasiada explicación alrededor del primer dato.
- **Cartera** [`auto-cartera-page.tsx`](../../apps/web/src/features/auto/auto-cartera-page.tsx): banner DEMO + `OperationsPanel surface="auto"`. Comparte superficie con la Cartera L1; riesgo de devenir "segunda cartera" si no se rotula como vista de la **misma** cuenta (D3/D10).
- **Riesgo** [`auto-riesgo-page.tsx`](../../apps/web/src/features/auto/auto-riesgo-page.tsx): tres KPIs (Estado, Integridad, Incidencias) + cuatro campos que **todos** copian `positionRiskLabel` ("Sin dato todavía"), con nota de que el detalle vive en Cartera → Riesgo. Primer nivel aún nombra "integridad de cartera" e "incidencias de enlace" (D2 semi-cubierto).
- **Análisis** [`auto-analisis-page.tsx`](../../apps/web/src/features/auto/auto-analisis-page.tsx): cuatro pestañas-pregunta; la jerga OOS vive dentro de los paneles (D2 acotado a cuerpo).
- **Sistema** [`auto-sistema-page.tsx`](../../apps/web/src/features/auto/auto-sistema-page.tsx): `Estado de AUTO` + monitor/timeline/reservas/concurrencia/broker/reconciliación plegados; `Auditoría` con enlaces. Es la superficie correcta para diagnóstico, pero **hoy es una puerta de primer nivel** (D9).

### 3.4 Oportunidades: `Hoy` vs `AUTO`

`Hoy → Oportunidades` enlaza a Mesa (`mesaOportunidadesHref()`), y `AUTO → Operar` pinta el TOP3 del motor. Son **dos listas potencialmente distintas** sin copy que explique la relación («universo completo» vs «subconjunto que AUTO está usando»): D3/D10. La arquitectura protege `ranking ≠ decisión` (correcto), pero no explica la relación entre ambos universos.

### 3.5 Ficha universal de operación

`/auto/operar/operacion/:cycleId` monta la ficha de seis bloques (`decidió`/`hizo`/`cambió`/`precio`/`dinero`/`estado`) y mantiene `precio aplicado ≠ posición materializada`. Correcta; el hallazgo es que la **insignia de modo** (AUTO/SEMI/MANUAL) no es visible de forma sistemática en la ficha ni en las listas (D5).

### 3.6 Consola avanzada

`/operational-console` conserva el nombre "Consola avanzada" (acertado, comunica "no es operativa diaria"). Único ajuste: jerarquía en la `AdminRail` (D9).

---

## 4. Hallazgos

### P0 — bloquean la coherencia de producto

| ID | Dimensión | Hallazgo | Evidencia |
| --- | --- | --- | --- |
| `G-01` | D1, D8 | La HOME de AUTO responde **varias veces** lo mismo: estado del motor (badge + seis preguntas + tile `AUTO`), operaciones en curso (tarjetas + `¿Qué puedo hacer?` + tile) | `auto-home-page.tsx` |
| `G-02` | D6, D10 | No existe una **gramática universal** de la escalera de operación: cada superficie usa etiquetas propias para los mismos peldaños | `auto-operation-sheet.ts`, paneles de Cartera/Mercado |
| `G-03` | D5 | El **modo** (AUTO/SEMI/MANUAL) no es una insignia visible por operación; el usuario debe deducirlo o conocer la arquitectura | `operations-panel.tsx`, ficha de operación |

### P1 — degradan la experiencia

| ID | Dimensión | Hallazgo | Evidencia |
| --- | --- | --- | --- |
| `G-04` | D9, D8 | AUTO expone **7 puertas** al mismo nivel; `Riesgo`, `Análisis` y `Sistema` son segundo nivel | `auto-nav.ts`, `auto-workspace-layout.tsx` |
| `G-05` | D1 | El **TOP3** aparece con el mismo peso en HOME y en Operar | `auto-top3-panel.tsx` (HOME + Operar) |
| `G-06` | D3, D10 | `Hoy → Oportunidades` (universo completo) y `AUTO → Operar` (TOP3) no explican su relación | `mesaOportunidadesHref` vs `AutoTop3Panel` |
| `G-07` | D2 | Riesgo de primer nivel usa "integridad de cartera"/"incidencias de enlace" antes que un veredicto humano ("Controlado") | `auto-riesgo-page.tsx` |
| `G-08` | D4, D8 | Enlaces y botones se mezclan visualmente: no hay separación dura Acción / Navegación / Información | global |
| `G-09` | D9 | `AdminRail` mezcla producto, administración y diagnóstico sin agrupar | `admin-rail.tsx` |

### P2 — pulido semántico

| ID | Dimensión | Hallazgo | Evidencia |
| --- | --- | --- | --- |
| `G-10` | D6 | Copy del TOP3 impreciso: «Las tres mejores oportunidades operables que AUTO ha detectado…» sugiere "las tres mejores del mercado" | `auto-top3-panel.tsx` L46-48 |
| `G-11` | D6 | Cartera L1 usa "posiciones abiertas" incluso cuando son posiciones de la cuenta simulada | `daily-nav.ts` (`CARTERA_POSICIONES_HINT`) |
| `G-12` | D2, D8 | Explicación alrededor del dato en Operar (dos párrafos) que debería vivir bajo «¿Por qué?» | `auto-operar-page.tsx` |
| `G-13` | D3 | `AUTO / Cartera` puede leerse como cartera independiente si no se rotula como vista de la misma cuenta | `auto-cartera-page.tsx`, `daily-nav.ts` |

---

## 5. Lo que ya está bien (no reabrir)

- Estado humano unificado y fail-closed (`FUNCIONANDO`/`ANALIZANDO`/`ESPERANDO`/`ATENCIÓN`/`DETENIDO`), `UNKNOWN ≠ 0` ([`auto-human-state.ts`](../../apps/web/src/features/auto/auto-human-state.ts)).
- `Sin dato todavía` como estado honesto del dato ausente (nunca `0`).
- «¿Por qué?» tri-estado (`ok`/`no`/`unknown`).
- `precio aplicado ≠ posición materializada` y `ranking ≠ decisión` en AUTO.
- Centro de actividad único (`/auto/actividad`) con lenguaje de hechos.
- Barrido semántico de `/auto/cartera` («Sin posiciones en la cuenta simulada»).
- Nombre "Consola avanzada" para diagnóstico.
- Cinco puertas L1 (ADR-040) y AUTO como espacio no-L1 (ADR-044).
- Accesibilidad `axe`: `0` `critical`/`serious` en las rutas certificadas en `v2.88.54`/`v2.88.62`.

---

## 6. Mapa hallazgo → regla del contrato

Cada hallazgo se resuelve por una regla de [`spec-ui-contract-5-0-2026-10-08.md`](./spec-ui-contract-5-0-2026-10-08.md); cada regla es falsable.

| Hallazgo | Regla |
| --- | --- |
| `G-01` | `UI5-04` (HOME = cockpit) |
| `G-02` | `UI5-09` (escalera universal) |
| `G-03` | `UI5-10` (insignia de modo) |
| `G-04` | `UI5-03` (nav visible de AUTO) |
| `G-05` | `UI5-06` (TOP3 en tres niveles) |
| `G-06` | `UI5-07` (universo vs subconjunto) |
| `G-07` | `UI5-18` (Riesgo human-first) |
| `G-08` | `UI5-17` (Acción ≠ Navegación ≠ Información) |
| `G-09` | `UI5-08` (AdminRail en tres grupos) |
| `G-10` | `UI5-06`, `UI5-07` |
| `G-11` | `UI5-13` (Cartera única / rotulada) |
| `G-12` | `UI5-05` (¿Qué puedo hacer?) + `UI5-06` |
| `G-13` | `UI5-13` |

---

## 7. Falsabilidad de esta auditoría

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | La HOME de AUTO repite el estado del motor en tres sitios. | Que `auto-home-page.tsx` pinte el estado una sola vez. |
| 2 | No hay una escalera universal compartida. | Que exista un módulo común de etiquetas de peldaño usado por todas las superficies. |
| 3 | El modo no es una insignia por operación. | Que `operations-panel.tsx` o la ficha pinten `AUTO/SEMI/MANUAL` de forma sistemática. |
| 4 | AUTO expone 7 puertas al mismo nivel. | Que `AUTO_NAV.items` agrupe Riesgo/Análisis/Sistema en un segundo nivel. |
| 5 | `Hoy` y `AUTO` muestran oportunidades sin explicar su relación. | Que exista copy explícito "universo completo / subconjunto" con enlace cruzado. |
| 6 | El copy del TOP3 sugiere "las mejores del mercado". | Que `auto-top3-panel.tsx` use "oportunidades que AUTO ha situado en los primeros puestos". |
| 7 | La `AdminRail` no agrupa por producto/administración/diagnóstico. | Que `admin-rail.tsx` separe los ítems en tres grupos con encabezado. |
| 8 | `Consola avanzada` es un nombre correcto y se mantiene. | Que el contrato proponga renombrarla a "Consola operativa" como término visible. |
