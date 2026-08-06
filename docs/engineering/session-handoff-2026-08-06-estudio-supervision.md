# Handoff — Modelo único Estudio / supervisión (2026-08-06)

> Rama docs: `stage/estudio-membership-operativa-2026-08-04` (o la que lleve el commit de docs)  
> **Padre:** [estudio-supervision-model-2026-08-06.md](./estudio-supervision-model-2026-08-06.md) · [ADR-024](../adr/024-estudio-supervision-universe.md)

## Implementado (2026-08-06)

- Lista API canónica `estudio` (`ensure_estudio_list`, merge «Estudio personal»).
- Membresía UI → API + cache `visualization-store`.
- Sin auto-add al abrir gráfico.
- **Supervisión ON** en Operativa → Configuración (CORE-R + Lista AUTO).
- Quitar de Estudio → dismiss CORE-R/F3 + excluir campaña.
- HELP / tracker / tests actualizados.

## Smoke

1. GET `/api/lists` → existe id `estudio`.
2. IBEX → seleccionar → Pasar a Estudio → aparece en chip Estudio.
3. Abrir gráfico de otro valor → **no** entra en Estudio.
4. Operativa → Supervisión ON → Lista AUTO sobre Estudio (o confirmación tandas).
5. Quitar de Estudio → sale de cola CORE-R / F3.
