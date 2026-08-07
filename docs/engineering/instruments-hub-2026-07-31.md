# Instrumentos hub — vista por valor (2026-07-31)

> Contrato de producto bloqueado tras pausa estratégica.  
> Complementa [research-radar-unification](./research-radar-unification-2026-07-31.md) y [account-premises](./account-premises-demo-vs-paper-2026-07-31.md).

**AsOf:** 2026-07-31

---

## 1. Decisiones bloqueadas

| # | Tema | Decisión |
|---|------|---------|
| 1 | Rol de `/instruments` | **Hub por valor**: catálogo BD en tabla + búsqueda + orden + atajos operativos. |
| 2 | Seguimiento | **No** se edita aquí. Seguimiento = **Tracker (Radar B)**. En la fila: estado + CTA → Screeners. |
| 3 | Espacio «Seguimiento» dedicado | **No** hasta que I3 (chips multi-estrategia) se quede corto. |
| 4 | Dueños de verdad | Listas → Trading Lists · Carteras → cuenta DEMO · Scores → FIE/Composite · Trackers → Screeners. Instrumentos = **proyección**. |
| 5 | Modos alarma | aviso=`inform`/`alert` · semi=F3 · auto=`paper_auto` (off-by-default DEMO). Sin redefinir policies. |

```text
Instrumentos (hub / tabla)
    │  ve · filtra · ordena · atajos
    ├─ Listas · Carteras DEMO · FA/TA (fases I1–I2)
    └─ Seguimiento* ──deep-link──► Radar (trackers)
                                       └─ alarmas → inbox / F3 / (futuro auto)
```

\*En fila: chips + CTA; no editor de schedule/política.

---

## 2. Fases

| Fase | Qué | Estado |
|------|-----|--------|
| **I0** | Tabla + buscador + sort (α / precio / Δ%) + atajos Trading · (i) · detalle · Backtesting | ✅ |
| **I1** | Columnas listas (N + chips) + posición/PnL cuenta activa | ✅ |
| **I2** | Score FA + TA/Composite ordenables | ✅ |
| **I3** | Columna Seguimiento (hasta 3 slots) + CTA Radar / activar | ✅ |
| **I4** | Ruta `/seguimiento` solo si I3 no basta | opcional |
| **I5** | Chips Estudio/Cartera/Lista + Recom. (IO) + narrativa Evolución | ✅ |

---

## 3. UI I0–I5

- Cabecera + contador filtrado.
- Buscador: símbolo, nombre, yahoo, ISIN, sector, **nombre de lista**.
- Filtros rápidos: chips favoritos **Todos · Estudio · Cartera · listas ancladas** + menú **(…)** (misma estética que el carrusel de Listas).
- Split **lista | detalle** (responsive ≥lg horizontal; móvil apilado) con `PanelResizeHandle`; clic fila → despliega el panel de detalle (colapsable a rail). Dentro: secciones verticales Resumen / Gráfico / Análisis / **Evolución** / Coach (acordeón, persistente). Scroll vertical propio en el panel detalle. Preferencias en `localStorage` (`bolsa-instruments-hub-prefs-v2`): columnas + split **wide** / **stack** por separado + secciones abiertas — alineado con la premisa global [UI_PREFS_LOCALSTORAGE.md](../UI_PREFS_LOCALSTORAGE.md).
- Columnas: anchos fijos alineados cabecera↔fila; **Ajustar al contenido** mide cabeceras + celdas.
- Columnas: Activo · Precio · Δ% · Listas · Cartera · **Recom.** · FA · TA · Seguim. · **Últ. vela** · Datos · Coach · Acciones.
- **Recom.:** Índice Operativo (mismo criterio que Operativa). Al activar Estudio → sort Recom. desc.
- **Últ. vela:** `meta.lastBarDate` (+ hora de sync si la vela es solo fecha).
- FA = Score_FUND 0–100; TA = pierna técnica Composite 0–100.
- **Seguimiento:** chips / Activar Finalistas→Radar (sin editor de schedule en hub).
- **Evolución:** narrativa ≤20 líneas en `instrument_narratives` — [instruments-hub-narrative-2026-08-04](./instruments-hub-narrative-2026-08-04.md).

Datos:
- I1: `getLists` + `getList` (invert) · `getPortfolio` · Estudio = `visualization-store`
- I2: `POST …/fundamentals/query` (chunks 80) · `POST …/composite/query` (chunks 40, horizon swing) · IO cliente
- I3: `getTrackers` + `getTracker(id)` + `getExecutionPolicies` · cobertura pin ∪ lista (I1)
- I5: `GET/PUT/DELETE …/instruments/{id}/narrative`

Código: `instruments-page.tsx` · `instruments-hub-model.ts` · `instruments-hub-enrichment.ts` · `instruments-hub-scores.ts` · `instruments-hub-trackers.ts` · `instrument-narrative-editor.tsx` · `use-instruments-hub-*.ts` · `use-activate-instrument-tracking.ts`.

**No** se edita schedule/política en el hub (dueño = Screeners / Radar).

---

## 4. Relacionados

- Unificación Radar: `research-radar-unification-2026-07-31.md`
- Narrativa / IO hub: `instruments-hub-narrative-2026-08-04.md`
- Trackers: `docs/HYBRID_TRACKERS.md` · ADR-010
- Listas: `lists-universes-design-2026-07-30.md`
