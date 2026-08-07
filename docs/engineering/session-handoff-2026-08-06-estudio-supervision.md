# Handoff — Modelo único Estudio / supervisión (2026-08-06)

> Rama: `stage/estudio-membership-operativa-2026-08-04`  
> **Padre:** [estudio-supervision-model-2026-08-06.md](./estudio-supervision-model-2026-08-06.md) · [ADR-024](../adr/024-estudio-supervision-universe.md)

## Implementado

- Lista API canónica `estudio` (`ensure_estudio_list`, merge «Estudio personal»).
- Membresía UI → API + cache `visualization-store`.
- Sin auto-add al abrir gráfico.
- **Supervisión ON** solo en banner lista Estudio.
- Quitar → **«Eliminar de la lista»** + dismiss CORE-R/F3 + excluir campaña.
- **Cadencias 3 capas** (`estudio-supervision.ts` + `EstudioSupervisionHost`):
  - Rápida → CORE-R (`vigilanceMinutes`)
  - Media → Lista AUTO + skip_fresh (`freshnessMinutes`)
  - Lenta → forceRescan + presupuesto rotatorio (`rediscoverMinutes` / `rediscoverBudgetPerTick`)
- UI: check ON/OFF + (···); keep-alive BacktestsPage mientras Supervisión ON.
- Fix pestañas «Abrir gráficos»: ids únicos + apertura en lote.

## Continuación misma jornada (procesos UI)

Ver handoff dedicado: [session-handoff-2026-08-06-estudio-process-ui.md](./session-handoff-2026-08-06-estudio-process-ui.md)  
(doc: [estudio-process-status-ui-2026-08-06.md](./estudio-process-status-ui-2026-08-06.md)).

- Subtítulo procesos bajo el nombre · sellos locales · Actualizar / Redescubrir separados.
- Modo cuenta en barra de estado → Cuentas (fuera del panel Operativa por valor).

## Smoke

1. GET `/api/lists` → existe id `estudio`.
2. IBEX → seleccionar → Pasar a Estudio → aparece en chip Estudio.
3. Abrir gráfico de otro valor → **no** entra en Estudio.
4. Banner → Supervisión ON → frescura inicial Lista AUTO.
5. (···) → cambiar vigilia / frescura / redisc. + presupuesto.
6. Eliminar de la lista → sale de cola CORE-R / F3.
7. Abrir gráficos multi → cambiar de pestaña → todas siguen.
8. (+ UI) Actualizar vs Redescubrir · `OPERATIVA:` en barra · subtítulo `al día`/`toca…`.
