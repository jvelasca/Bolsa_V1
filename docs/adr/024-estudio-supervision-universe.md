# ADR-024 — Universo único «Estudio» (supervisión)

- **Estado:** Accepted — 2026-08-06 (implementación stage 2026-08-06)
- **Tipo:** decisión de producto / lifecycle de supervisión
- **Padres:** [ADR-019](./019-dual-universes-lab-vs-trading.md) · [ADR-020](./020-operating-mandate-tenure.md) · panel Operativa ([trading-operativa-panel-2026-08-04.md](../engineering/trading-operativa-panel-2026-08-04.md))
- **Diseño detallado:** [estudio-supervision-model-2026-08-06.md](../engineering/estudio-supervision-model-2026-08-06.md)
- **Implementación:** lista API `estudio` + Supervisión ON + sin auto-add gráfico a Estudio + unsubscribe al quitar.  
  Lista virtual **Visualizados** (`__builtin:visualization__`) = espejo de pestañas abiertas (separada de Estudio).  
  UX listas: [visualizados-list-ux-2026-08-06.md](../engineering/visualizados-list-ux-2026-08-06.md).

---

## 1. Contexto

Hoy coexisten dos conceptos con nombres parecidos y roles distintos:

| Nombre | Qué es hoy | Efecto real |
|--------|------------|-------------|
| **Estudio** (virtual) | Membresía local (`visualization-store` / `__builtin:visualization__`) | Gate SEMI/AUTO · IO · auto-add al abrir gráfico |
| **Estudio personal** (API) | Lista API opcional con nombre “mágico” | Auto-sync CORE-R la prefiere si existe |

El usuario espera un flujo simple:

1. Elegir valores (IBEX, S&P, buscador…).
2. Pasarlos a **Estudio**.
3. Que eso implique supervisión (Lab / TOP / reevaluación / señales).
4. Quitar de Estudio = dejar de supervisar.

Eso **no** es el as-is: Lab y Lista AUTO exigen lista API; abrir gráfico ensucia Estudio; quitar de una lista no para campañas ni colas; «Estudio personal» añade confusión sin aportar una capacidad exclusiva.

## 2. Decisión

### 2.1 Una sola lista de producto: «Estudio»

- Desaparece el concepto de producto «Estudio personal».
- Estudio pasa a ser el **universo supervisable** persistido (lista API canónica), no “pestañas abiertas”.
- Catálogos (IBEX35, S&P100, …) siguen siendo fuentes; no son el universo de supervisión.

### 2.2 Activación: interruptor global «Supervisión ON/OFF»

- **Estudio** = membresía (elegible).
- **Supervisión ON** = arma Lista AUTO + CORE-R Auto-sync sobre los miembros de Estudio.
- Añadir/quitar entra/sale de esa cola; no se lanza un embudo suelto e incontrolado por cada alta.
- **Supervisión OFF** = pausa nuevos ticks/tandas; no borra membresía ni Finalistas.

### 2.3 Humano en el bucle (SEMI)

- Análisis y reevaluación: automáticos cuando Supervisión está ON.
- **Comprar/vender** y **cambiar mandato**: confirmación humana (SEMI), como hoy.
- AUTO execute / auto-adopt quedan fuera de este ADR (preparar el universo; no descongelar Camino D).

### 2.4 Gráfico ≠ membresía

- Abrir o cerrar un gráfico **no** añade ni quita de Estudio.
- Membresía solo por acción explícita («A Estudio» / «Quitar de Estudio»).

### 2.5 Quitar = unsubscribe

Al quitar un instrumento de Estudio:

- Excluir de campaña Lista AUTO pendiente / saltar si es el actual.
- Dismiss items abiertos CORE-R y propuestas F3 de supervisión de ese instrumento.
- **No** borrar Finalistas/TOP ni cerrar posiciones/mandato automáticamente; avisar si hay mandato activo.
- Copy UI: **«Eliminar de la lista»** (no «Dejar de supervisar» — evita confusión con Supervisión ON).

### 2.6 Cadencias en 3 capas (no un solo timer)

Un intervalo único no optimiza operativa: vigilar PnL ≠ rediscubrir estrategia.

| Capa | Pregunta | Motor | Cadencia típica (default · vela 1d al cierre) |
|------|----------|-------|---------------------------|
| **Vigilia** | ¿Mandato / PnL paper se degrada? | CORE-R Auto-sync | **1 día** (no cada hora) |
| **Frescura** | ¿Finalistas siguen válidos tras el cierre? | Lista AUTO + `skip_fresh` | **1 día** |
| **Redescubrimiento** | ¿Buscar otra estrategia? | Lista AUTO `forceRescan` + presupuesto | 30 días · 5 valores/tick |

Por valor se registran sellos de proceso: Finalistas `lastSearchAt` / freshness stamp, tablero Lista AUTO `lastSearchAt`, cola CORE-R `enqueuedAt` — para reportes y omitir lo ya fresco.

**UI lista Estudio:** columna **Sincro** = solo velas OHLCV. Columnas **Procesos** / **Últ. Lab** / **Últ. CORE-R** se activan en el **(···) de columnas de la tabla** (layout por `listId`, independiente de IBEX etc.; off por defecto). Cadencias solo en (···) de Supervisión. Bajo el **nombre**: resumen corto de procesos (`al día` / `toca V·F`…) + barra al actualizar. Desplegable de fila: precio compacto + bloque Operativa (capas). Botones separados **Actualizar** (vigilia+frescura+velas) y **Redescubrir** (embudo `forceRescan`, confirm costoso) — funcionan también con Supervisión OFF. Detalle UI: [estudio-process-status-ui-2026-08-06.md](../engineering/estudio-process-status-ui-2026-08-06.md).

- **Supervisión ON** = master arm; las capas solo corren si ON.
- UI: check ON/OFF + botón **(···)** para las tres cadencias (no el select al lado del check).
- Rediscover rota por la lista (`rediscoverCursor`) para no tumbar el browser.
- **Manual / SEMI / AUTO** = modo de la **cuenta** (barra de estado → Cuentas · Config · Operativa), no del panel Operativa por valor.
- SEMI sin cambio: confirmar operar / cambiar mandato.

## 3. Consecuencias

- As-is (virtual + «Estudio personal») queda **superseded** como to-be; el código se alinea en el stage de implementación.
- HELP / tracker / list-auto-ops deben dejar de presentar «Estudio personal» como destino ideal tras el stage.
- Complementa ADR-019: LAB descubre/mantiene operativa conveniente; TRADING adopta — Estudio es el **puente de universo** por instrumento bajo supervisión.

## 4. No incluye

- AUTO execute / auto-adopt mandato.
- Purge de backtests al quitar de Estudio.
- Cambiar el embudo Lab interno (solo disparador y universo).
- Opinion EOD / Asesor (pueden reutilizar el mismo `estudioListId` más adelante).
