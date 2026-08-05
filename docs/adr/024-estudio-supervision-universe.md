# ADR-024 — Universo único «Estudio» (supervisión)

- **Estado:** Accepted (to-be) — 2026-08-06
- **Tipo:** decisión de producto / lifecycle de supervisión
- **Padres:** [ADR-019](./019-dual-universes-lab-vs-trading.md) · [ADR-020](./020-operating-mandate-tenure.md) · panel Operativa ([trading-operativa-panel-2026-08-04.md](../engineering/trading-operativa-panel-2026-08-04.md))
- **Diseño detallado:** [estudio-supervision-model-2026-08-06.md](../engineering/estudio-supervision-model-2026-08-06.md)
- **Implementación:** pendiente (mañana / siguiente stage). El as-is sigue con Estudio virtual + tip «Estudio personal» para CORE-R.

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

## 3. Consecuencias

- As-is (virtual + «Estudio personal») queda **superseded** como to-be; el código se alinea en el stage de implementación.
- HELP / tracker / list-auto-ops deben dejar de presentar «Estudio personal» como destino ideal tras el stage.
- Complementa ADR-019: LAB descubre/mantiene operativa conveniente; TRADING adopta — Estudio es el **puente de universo** por instrumento bajo supervisión.

## 4. No incluye

- AUTO execute / auto-adopt mandato.
- Purge de backtests al quitar de Estudio.
- Cambiar el embudo Lab interno (solo disparador y universo).
- Opinion EOD / Asesor (pueden reutilizar el mismo `estudioListId` más adelante).
