# Handoff — Estudio membresía / bulk / gate SEMI (2026-08-04)

> Rama: `stage/estudio-membership-operativa-2026-08-04`  
> Padre: [trading-operativa-panel-2026-08-04.md](./trading-operativa-panel-2026-08-04.md)  
> **Sucesor to-be (no implementado aquí):** [ADR-024](../adr/024-estudio-supervision-universe.md) · [estudio-supervision-model-2026-08-06.md](./estudio-supervision-model-2026-08-06.md) · [handoff 2026-08-06](./session-handoff-2026-08-06-estudio-supervision.md)

## Hecho

- Label **Estudio**; carrusel oculta API homónimas.
- Membresía explícita (abrir gráfico añade; cerrar no quita).
- IO ranking = store Estudio.
- Check cabecera + **A Estudio** / **Quitar de Estudio**.
- SEMI/AUTO gate en propose (Finalistas + alarmas); MANUAL libre.

## Smoke

1. Carrusel: un solo chip Estudio.
2. IBEX → seleccionar todos → A Estudio → IO «El n de N».
3. SEMI + valor fuera de Estudio → Proponer F3 error claro.
4. MANUAL → propose sin exigir Estudio.
5. Cerrar pestaña: valor sigue en Estudio.
