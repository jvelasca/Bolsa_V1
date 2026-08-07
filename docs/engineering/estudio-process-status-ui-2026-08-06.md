# Estudio — UI de procesos + Actualizar / Redescubrir (2026-08-06)

> **Padre:** [estudio-supervision-model-2026-08-06.md](./estudio-supervision-model-2026-08-06.md) · [ADR-024](../adr/024-estudio-supervision-universe.md)  
> **Ayuda:** [HELP.md](../HELP.md) § Estudio = supervisión  
> **Handoff:** [session-handoff-2026-08-06-estudio-process-ui.md](./session-handoff-2026-08-06-estudio-process-ui.md)  
> **Estado:** implementado (misma jornada que cadencias 3 capas).

---

## 1. Qué

Capa de UI sobre las 3 cadencias de Supervisión (ADR-024):

1. **Columna Procesos** (opcional, off por defecto) — 3 iconos por valor.
2. **Subtítulo bajo el nombre** en filas Estudio — resumen corto (`al día` / `toca V·F` / `sin sync`).
3. **Barra de progreso** en ese subtítulo mientras el valor se actualiza.
4. **Banner Estudio** — Supervisión ON/OFF + chips de cadencia V·F·R + progreso de pasada.
5. **Barra inferior de selección** — **Actualizar** y **Redescubrir** (y resto de acciones con icono).
6. **Manual / SEMI / AUTO** — fuera del panel Operativa por valor; en barra de estado → Cuentas.

## 2. Las 3 capas (recordatorio)

| Icono | Capa | Motor | Actualizar (clic) | Redescubrir |
|-------|------|-------|-------------------|-------------|
| Activity | **Vigilia** (V) | CORE-R mandato / PnL | Sí (tick forzado) | Sí (también) |
| Flask | **Frescura** (F) | Lista AUTO + `skip_fresh` | Sí (puede omitir embudo) | No aplica skip |
| RefreshCcw | **Redescubrir** (R) | Lista AUTO `forceRescan` | No | Sí (embudo completo) |

- **Actualizar** ≈ adelantar lo que Supervisión ON haría en vigilia + frescura (+ sync velas).
- **Redescubrir** = forzar búsqueda de nuevas estrategias TOP (costoso; `window.confirm`).

## 3. Sellos locales

Si CORE-R no encola nada (juicio OK), el icono de vigilia quedaba vacío.  
`estudio-lane-stamps.ts` (`localStorage` `bolsa-estudio-lane-stamps-v1`) guarda última pasada por instrumento×capa y emite `bolsa-estudio-lane-stamps` para re-render.

`resolveEstudioProcessStatus` hace `maxIso` entre cola CORE-R / Finalists freshness y el sello local.

## 4. Subtítulo bajo el nombre

`summarizeEstudioProcessLanes` → texto corto:

| Estado | Texto | Tono |
|--------|-------|------|
| Todas ok | `al día` | verde |
| Alguna stale/empty | `toca V` / `toca F·R`… | ámbar |
| Todas empty | `sin sync` | muted |
| Running | `actualizando…` + barra CSS | sky |

Componente: `list-name-process-subtitle.tsx`. Tooltip = títulos largos de cada capa (`ESTUDIO_LANE_PURPOSE` + estado + cadencia + cómo actualizar).

## 5. Botones (sin Shift) + alta

| Acción | Qué hace |
|--------|----------|
| **A Estudio** / alta | Membresía + **Actualizar ligero** automático de los ids nuevos (velas + vigilia + frescura). No Redescubrir. |
| Abrir lista Estudio | Si hay valores con V/F vacíos o caducados → Actualizar automático de esos ids (keep-alive Lab hasta arrancar). |
| **Actualizar** | `syncInstrument` → sellos F · CORE-R force · sello V · `emitEstudioLaneTick` `forceRescan: false` |
| **Redescubrir** | Confirm costoso → igual + `forceRescan: true` (capa R). Solo a demanda del usuario. |

Implementación compartida: `estudio-instruments-update.ts`.  
Ubicación botones: barra inferior de selección (lista Estudio). Iconos/procesos bajo el nombre y columna Procesos siguen mostrando qué está o no al día.

**Pausa suave (banner Supervisión):** botón ⏸ junto a la barra de progreso. Termina el valor en curso y no arranca el siguiente (Actualizar/alta o Lista AUTO). El label pasa a `Termina SYMBOL y para…`. Reanudar (▶) solo si la campaña Lab quedó en pausa.

## 6. Operativa de cuenta (no por valor)

Manual / SEMI / AUTO es de la **cuenta entera**.

| Antes | Ahora |
|-------|-------|
| Panel Operativa → sección Cuenta | Quitado del panel por valor |
| — | Barra de estado: badge `OPERATIVA: Semi` |
| — | Clic → `/accounts?selected=…&tab=config&focus=operativa` |
| — | `AccountDetailPanel` bloque Operativa + `DemoBookModePanel` |

Panel Operativa = **Recomendación** + **Info** (por activo).

## 7. Archivos clave

| Pieza | Path |
|-------|------|
| Estados / tooltips / summarize | `estudio-process-status.ts` |
| Sellos localStorage | `estudio-lane-stamps.ts` |
| Columna iconos | `lists-tab/list-process-status-cell.tsx` |
| Subtítulo + barra | `lists-tab/list-name-process-subtitle.tsx` |
| Banner + botones | `estudio-supervision-panel.tsx` |
| Actualizar / Redescubrir / alta | `estudio-instruments-update.ts` · callers: `list-values-panel.tsx`, `trading-operativa-panel.tsx` |
| Barra estado modo | `trading-status-bar.tsx` |
| Cuentas Operativa | `accounts/account-detail-panel.tsx` |
| Animación barra | `apps/web/src/index.css` (`.estudio-row-progress`) |

## 8. Criterio de éxito

Usuario ve a golpe de vista qué valores necesitan sync; fuerza Actualizar o Redescubrir sin atajos ocultos; no confunde modo de cuenta con estado del valor.
