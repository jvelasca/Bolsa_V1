# Handoff — UI procesos Estudio + operativa en barra (2026-08-06)

> **Rama típica:** `stage/estudio-membership-operativa-2026-08-04` (o la activa del stage)  
> **Padre:** [estudio-process-status-ui-2026-08-06.md](./estudio-process-status-ui-2026-08-06.md)  
> **Modelo:** [estudio-supervision-model-2026-08-06.md](./estudio-supervision-model-2026-08-06.md) · [ADR-024](../adr/024-estudio-supervision-universe.md)  
> **Handoff previo (membresía/cadencias):** [session-handoff-2026-08-06-estudio-supervision.md](./session-handoff-2026-08-06-estudio-supervision.md)  
> **Repo:** [jvelasca/Bolsa_V1](https://github.com/jvelasca/Bolsa_V1) (público)

---

## Contexto para el siguiente agente

Stage ADR-024 ya tenía lista API `estudio`, Supervisión ON, 3 cadencias y «Eliminar de la lista».  
Esta continuación cerró UX confusa:

1. Manual/SEMI/AUTO **no** es por valor → sacado de Operativa; visible en barra de estado → Cuentas.
2. Bajo el nombre en Estudio: resumen de procesos (no «gráfico abierto · visto…»).
3. **Actualizar** ≠ **Redescubrir** (dos botones; rediscubrir con aviso + confirm).
4. Sellos locales para que Vigilia pase a verde aunque CORE-R no encole.

## Implementado (esta pasada)

- `estudio-lane-stamps.ts` + evento UI.
- `list-name-process-subtitle.tsx` + `summarizeEstudioProcessLanes`.
- Banner progreso + chips cadencia V·F·R; Actualizar / Redescubrir en barra inferior.
- `trading-status-bar`: badge `OPERATIVA: Semi|Manual|Auto` → Cuentas `?tab=config&focus=operativa`.
- `account-detail-panel`: bloque Operativa + `DemoBookModePanel`.
- Panel Operativa: sin sección Cuenta/modos.
- Docs: este handoff · `estudio-process-status-ui-2026-08-06.md` · HELP / registry / ADR-024 amend.

## Smoke (nuevo agente)

1. Barra inferior → `OPERATIVA: …` → Cuentas · Config · bloque Operativa cambia modo.
2. Lista Estudio → bajo el nombre: `al día` / `toca V` / `sin sync`.
3. Seleccionar valor → barra inferior **Actualizar** → iconos/progresión; frescura puede omitir embudo; vigilia sella.
4. Barra inferior **Redescubrir** → confirm costoso → embudo `forceRescan`. Banner: chips V·F·R (no botones duplicados).
5. Columna Procesos (··· cabecera tabla): 3 iconos; tooltip con «Vigilia: supervisa…».
6. Abrir gráfico de un valor **fuera** de Estudio → **no** entra en Estudio.
7. Panel Operativa lateral: solo Recomendación / Info (sin Manual/SEMI/AUTO).

## Tests útiles

```bash
cd apps/web
npx vitest run src/features/trading/estudio-process-status.test.ts
# opcional: prefs supervisión
npx vitest run src/features/trading/estudio-supervision.test.ts
```

## No tocar

- `PAPER_D_EXECUTE` / AUTO execute (ADR-023 Proposed).
- Belief→Coach Fase 2/5c.
- Purge de Finalistas al eliminar de Estudio.

## Lectura mínima

1. ADR-024  
2. `estudio-process-status-ui-2026-08-06.md`  
3. Este handoff  
4. `HELP.md` § Estudio = supervisión  
5. Código: `list-values-panel.tsx` → `updateSelectedInstruments`
