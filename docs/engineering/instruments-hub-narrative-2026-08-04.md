# Instrumentos hub — filtros rápidos + Recomendación + narrativa (2026-08-04)

> Extiende [instruments-hub-2026-07-31](./instruments-hub-2026-07-31.md).  
> Complementa Estudio / IO de [trading-operativa-panel-2026-08-04](./trading-operativa-panel-2026-08-04.md).

**AsOf:** 2026-08-04

---

## 1. Decisiones

| # | Tema | Decisión |
|---|------|---------|
| 1 | Filtros rápidos | Chips favoritos en la barra del buscador + menú **(…)** (Todos / Estudio / Cartera / listas API). Persistidos en prefs hub. |
| 2 | Estudio en hub | Universo = membresía `visualization-store` (lista virtual), no listas API. |
| 3 | Columna Recom. | **Índice Operativo (IO)** — mismo criterio que Operativa (`computeIndiceOperativo`). Ordenable. Al activar chip Estudio → sort IO desc. |
| 4 | Narrativa | **No** en tabla `instruments`. Entidad `instrument_narratives` por `(instrumentId, scope)`. |
| 5 | Scope narrativa | `estudio` \| `trading` \| `global`. Source: `user` \| `ai` \| `system`. |
| 6 | Límites | ≤20 líneas · ≤4000 chars. Fresco p/ IA: 14 días (`isInstrumentNarrativeFresh`). |

---

## 2. UI

- Buscador + chips favoritos (contador Estudio) + **(…)** para anclar listas / ocultar filtros.
- Columna **Recom.** entre Cartera y FA.
- Detalle → sección **Evolución** (editor textarea + guardar/borrar).

Prefs: `bolsa-instruments-hub-prefs-v2` → `scopeFilter`, `scopeListId`.

---

## 3. API / BD

| Método | Ruta |
|--------|------|
| GET | `/api/instruments/{id}/narrative?scope=` |
| PUT | `/api/instruments/{id}/narrative` |
| DELETE | `/api/instruments/{id}/narrative?scope=` |

Migración: `20260804120000_instrument_narratives`.

Shared: `packages/shared/src/instrument-narrative.ts`.

---

## 4. Uso dual-monitor

1. Abrir segunda pestaña (icono ↗ barra superior).  
2. Ir a Instrumentos → chip **Estudio** (ordena por Recom.).  
3. Abrir detalle → **Evolución** para anotar el giro / tesis corta.

---

## 5. Código

- Hub: `instruments-page.tsx` · `instruments-hub-model.ts` · `instruments-hub-column-layout.ts`
- Narrativa UI: `instrument-narrative-editor.tsx` · detalle hub
- API: `instrument_narratives` routes + repo SQLAlchemy
